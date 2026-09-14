import copy
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from autogen_core import FunctionCall
from autogen_core.models import CreateResult, RequestUsage
from autogen_ext.models.replay import ReplayChatCompletionClient

from scheduler.task_db import Task
from spatial.agent import MultiAgents, Objection
from spatial.build import Assembly, Machine


def bridge_prefix(machine):
    """The 15-block state from the rejected September 14 Support Soft run."""
    machine.start(init_shift=[0, 0, 7])
    for base, face in [
        (1, "E"), (2, "E"), (3, "E"), (4, "E"),
        (1, "F"), (6, "E"), (7, "E"), (8, "E"),
        (1, "A"), (10, "B"), (11, "E"), (12, "E"), (13, "E"), (10, "A"),
    ]:
        machine.attach_block_to(base, face, "Small Wooden Block")


def completion(content):
    return CreateResult(
        content=content, finish_reason="stop" if isinstance(content, str) else "function_calls",
        usage=RequestUsage(prompt_tokens=11, completion_tokens=7), cached=False,
    )


def call(name, **arguments):
    return completion([FunctionCall(id=name, name=name, arguments=json.dumps(arguments))])


class GeometryEvidenceTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.db = str(Path(self.directory.name) / "task_database.db")
        self.machine = Machine(name="build", db_path=self.db, save_dir=self.directory.name)
        self.task = Task(id="build", stage="build", parent_id="draft", db_path=self.db)
        self.objection = Objection(self.task, self.machine)
        self.add_parent_objection = self.enterContext(patch("spatial.agent.add_task_objection"))
        self.update_task = self.enterContext(patch("spatial.agent.update_task_raise_objection"))

    def occupied_face_failure(self):
        self.machine.start()
        self.machine.attach_block_to("1", "A", "Small Wooden Block")
        self.machine.attach_block_to("1", "A", "Small Wooden Block")

    def assert_denied(self, guard, evidence_id=""):
        result = guard.update_task_objection(
            "Blocks 16-27 overlap", "Unverified rejection, TERMINATE", evidence_id)
        self.assertFalse(json.loads(result)["accepted"])
        self.assertNotIn("TERMINATE", result)
        self.assertFalse(guard.objection_raised)
        self.assertFalse(Path(guard.objection_file_path).exists())
        self.add_parent_objection.assert_not_called()
        self.update_task.assert_not_called()
        return json.loads(result)

    async def test_missing_or_fabricated_evidence_cannot_reject_any_construction_stage(self):
        self.machine.start()
        for stage in ("build", "refine", "assemble"):
            with self.subTest(stage=stage):
                guard = Objection(self.task.model_copy(update={"stage": stage}), self.machine)
                self.assert_denied(guard)
                state = await guard.inspect_geometry(["1", "999"])
                self.assertIsNone(state["evidence_id"])
                self.assertTrue(state["blocks"]["1"]["faces"]["A"]["attachable"])
                self.assertEqual(state["missing_block_ids"], ["999"])
                self.assert_denied(guard, "invented-id")

    async def test_real_occupied_face_requires_inspection_and_saves_evidence(self):
        self.occupied_face_failure()
        self.assert_denied(self.objection)
        state = await self.objection.inspect_geometry(["1"])
        self.assertTrue(state["evidence_id"])
        self.assertEqual(state["failure"]["code"], "face_occupied")
        self.assertEqual(state["failure"]["params"]["base_block"], "1")
        self.assertFalse(state["blocks"]["1"]["faces"]["A"]["attachable"])
        self.assertEqual(state["blocks"]["1"]["faces"]["A"]["attached_to"]["block_id"], "2")
        self.assertEqual(state["blocks"]["1"]["faces"]["A"]["attached_to"]["face"], "F")
        self.machine.get_block_details("1")
        self.machine.get_machine_summary()
        result = self.objection.raise_objection_build(
            "Face 1.A occupied", "The recorded attachment failed.", state["evidence_id"])
        self.assertEqual(result, "Objection raised, TERMINATE")
        self.assertTrue(self.objection.objection_raised)
        self.add_parent_objection.assert_called_once_with(task_id="draft", db_path=self.db)
        self.update_task.assert_called_once()
        saved = Path(self.objection.objection_file_path).read_text()
        self.assertIn(state["evidence_id"], saved)
        self.assertIn('"face_occupied"', saved)
        self.assertIn('"state"', saved)
        events = [json.loads(line) for line in self.objection.geometry_audit_path.read_text().splitlines()]
        self.assertEqual([event["event"] for event in events],
                         ["objection_check", "geometry_inspection", "objection_check"])
        self.assertFalse(events[0]["accepted"])
        self.assertTrue(events[-1]["accepted"])
        repeated = self.objection.raise_objection_build("Again", "Again", state["evidence_id"])
        self.assertEqual(json.loads(repeated)["reason"], "objection_already_raised")
        self.update_task.assert_called_once()

    async def test_collision_evidence_retains_attempt_and_pairs_after_rollback(self):
        self.machine.start()
        for base, face in [("1", "E"), ("1", "A"), ("2", "A"), ("3", "B")]:
            self.machine.attach_block_to(base, face, "Small Wooden Block")
        self.assertEqual(self.machine.num_blocks, 4)
        self.assertFalse(self.machine.in_collision()[0])
        state = await self.objection.inspect_geometry(["3"])
        self.assertTrue(state["evidence_id"])
        self.assertEqual(state["failure"]["code"], "collision")
        self.assertEqual(state["failure"]["collision_pairs"], [["4", "5"]])
        self.assertEqual(state["failure"]["params"]["face"], "B")
        self.assertIn("4", state["blocks"])
        self.assertFalse(state["current_collision"])
        self.assertTrue(state["blocks"]["3"]["faces"]["B"]["attachable"])
        self.assertIn("TERMINATE", self.objection.raise_objection_build(
            "Attachment overlaps block 4", "See attempted block 5 and rollback.",
            state["evidence_id"]))

    async def test_refine_shift_failure_is_captured_after_rollback(self):
        self.machine.start()
        self.machine.attach_block_to("1", "A", "Small Wooden Block")
        self.machine.shift_block("2", [-0.5, 0, 0])
        state = await self.objection.inspect_geometry(["2"])
        self.assertEqual(state["failure"]["operation"], "shift_block")
        self.assertEqual(state["failure"]["collision_pairs"], [["1", "2"]])
        self.assertFalse(state["current_collision"])
        self.assertIn("TERMINATE", self.objection.raise_objection_refine(
            "Shift collides with root", "Actual refinement failure.", state["evidence_id"]))

    async def test_coincident_connector_endpoints_require_actual_failed_connection(self):
        self.machine.start()
        self.machine.attach_block_to("1", "A", "Small Wooden Block")
        self.machine.connect_blocks("1", "A", "2", "F", "Brace")
        state = await self.objection.inspect_geometry(["1"])
        self.assertEqual(state["failure"]["code"], "faces_too_close")
        self.assertEqual(state["blocks"]["1"]["faces"]["A"]["center"],
                         state["blocks"]["2"]["faces"]["F"]["center"])
        self.assertTrue(state["evidence_id"])

    async def test_repeated_failure_requires_a_new_inspection(self):
        self.occupied_face_failure()
        before = await self.objection.inspect_geometry(["1"])
        self.machine.attach_block_to("1", "A", "Small Wooden Block")
        result = self.assert_denied(self.objection, before["evidence_id"])
        self.assertEqual(result["reason"], "stale_geometry_evidence")
        after = await self.objection.inspect_geometry(["1"])
        self.assertTrue(after["evidence_id"])
        self.assertNotEqual(before["evidence_id"], after["evidence_id"])
        self.assert_denied(self.objection, before["evidence_id"])

    async def test_edits_reset_replay_and_unwrapped_changes_invalidate_evidence(self):
        changes = {
            "add": lambda: self.machine.attach_block_to("1", "B", "Small Wooden Block"),
            "remove": lambda: self.machine.remove_block("2"),
            "shift": lambda: self.machine.shift_block("2", [0.2, 0, 0]),
            "twist": lambda: self.machine.twist_block("2", 90),
            "reset": lambda: self.machine.reset(),
            "rebuild_same_blocks": lambda: self.machine.rebuild_from_history(
                copy.deepcopy(self.machine.operation_history)),
            "direct_geometry_edit": lambda: self.machine.blocks["2"].shift([0.2, 0, 0]),
        }
        for name, change in changes.items():
            with self.subTest(change=name):
                self.machine.reset()
                self.occupied_face_failure()
                state = await self.objection.inspect_geometry(["1"])
                change()
                result = self.assert_denied(self.objection, state["evidence_id"])
                self.assertEqual(result["reason"], "stale_geometry_evidence")
                self.assertIsNone((await self.objection.inspect_geometry(["1"]))["evidence_id"])

    async def test_argument_errors_are_not_geometry_failure_evidence(self):
        self.machine.start()
        for base, face, block in [
            ("999", "A", "Small Wooden Block"),
            ("1", "NO_SUCH_FACE", "Small Wooden Block"),
            ("1", "A", "Brace"),
        ]:
            with self.subTest(base=base, face=face, block=block):
                self.machine.attach_block_to(base, face, block)
                self.assertIsNone((await self.objection.inspect_geometry(["1"]))["evidence_id"])
                self.assert_denied(self.objection)

    async def test_non_geometry_errors_cannot_reuse_previous_failure(self):
        self.occupied_face_failure()
        previous = await self.objection.inspect_geometry(["1"])
        self.machine.flip_spin("1")
        self.assert_denied(self.objection, previous["evidence_id"])
        self.assertIsNone((await self.objection.inspect_geometry(["1"]))["evidence_id"])

    async def test_unavailable_block_needs_actual_catalog_failure(self):
        self.machine.start()
        self.machine.attach_block_to("1", "A", "Not a real block")
        state = await self.objection.inspect_geometry(["1"])
        self.assertEqual(state["failure"]["code"], "block_unavailable")
        self.assertTrue(state["evidence_id"])

    async def test_evidence_is_not_transferable_or_loaded_from_old_logs(self):
        self.occupied_face_failure()
        state = await self.objection.inspect_geometry(["1"])
        other = Objection(self.task.model_copy(update={"id": "other"}), self.machine)
        self.assert_denied(other, state["evidence_id"])
        restarted = Machine(name="build", db_path=self.db, save_dir=self.directory.name)
        self.assertTrue(any(row["op"] == "failed" for row in restarted.operation_history_full))
        restarted.start()
        other = Objection(self.task, restarted)
        self.assertIsNone((await other.inspect_geometry(["1"]))["evidence_id"])
        self.assert_denied(other, state["evidence_id"])

    async def test_original_false_rejection_is_blocked_and_blocks_16_to_27_fit(self):
        bridge_prefix(self.machine)
        self.assertEqual(self.machine.num_blocks, 15)
        self.assert_denied(self.objection)
        state = await self.objection.inspect_geometry(["7", "8", "9", "15"])
        self.assertIsNone(state["evidence_id"])
        self.assertTrue(state["blocks"]["7"]["faces"]["A"]["attachable"])
        self.assertEqual(state["blocks"]["7"]["faces"]["A"]["center"], [0.5, -2, 7])
        self.assertTrue(state["blocks"]["15"]["faces"]["E"]["attachable"])
        for expected, (base, face) in enumerate(
            [(7, "A"), (8, "A"), (9, "A")] + [(base, "B") for base in range(1, 10)], 16,
        ):
            with self.subTest(block=expected):
                self.machine.attach_block_to(base, face, "Small Wooden Block")
                self.assertEqual(self.machine.num_blocks, expected)
                self.assertFalse(self.machine.in_collision()[0])
                self.assertIsNone(self.machine.geometry_failure)

    async def test_assembly_reports_actual_state_even_when_failed_move_does_not_rollback(self):
        self.machine.start()
        folder = Path(self.directory.name) / "machine/build"
        self.machine.save_operation_history(folder / "build.json")
        assembly = Assembly(name="assembly", db_path=self.db, save_dir=self.directory.name)
        assembly.add_machine("build")
        assembly.add_machine("build")
        guard = Objection(self.task.model_copy(update={"id": "assembly", "stage": "assemble"}), assembly)
        state = await guard.inspect_geometry([])
        self.assertEqual(state["failure"]["operation"], "add_machine")
        self.assertEqual(state["failure"]["collision_pairs"], [["A_1", "B_1"]])
        self.assertFalse(state["current_collision"])
        assembly.add_machine("build", init_shift=[2, 0, 0])
        self.assert_denied(guard, state["evidence_id"])
        assembly.shift_machine("B", [-2, 0, 0])
        state = await guard.inspect_geometry(["A_1"])
        self.assertEqual(state["failure"]["operation"], "shift_machine")
        self.assertTrue(state["current_collision"])
        self.assertIn("B_1", state["blocks"])
        self.assertIn("TERMINATE", guard.raise_objection_build(
            "Substructures collide", "Actual current collision.", state["evidence_id"]))

    async def test_autogen_denied_objection_does_not_stop_builder(self):
        bridge_prefix(self.machine)
        model_info = dict(vision=False, function_calling=True, json_output=False,
                          family="unknown", structured_output=False)
        builder = ReplayChatCompletionClient([
            call("get_block_details", block_id="7"),
            call("attach_block_to", base_block="7", face="A", new_block="Small Wooden Block"),
            call("get_machine_summary"),
        ], model_info=model_info)
        guidance = ReplayChatCompletionClient([
            call("raise_objection_build", key_failure="Blocks 16-27 overlap",
                 objection="Claimed occupied faces"),
            call("inspect_geometry", block_ids=["7", "16"]),
            completion("The requested one-block continuation is complete. TERMINATE"),
        ], model_info=model_info)
        config = {"agents": {
            name: {"name": name, "model": name, "system_message": "Build the requested block."}
            for name in ("builder", "guidance")
        }}
        original_config = copy.deepcopy(config)
        agents = MultiAgents(verbose=False)

        async def run_without_delays(team, task):
            return await team.run(task=task)

        with patch("spatial.agent.get_config", return_value=SimpleNamespace(config=config)), \
                patch.dict("spatial.agent.model_clients", {"builder": builder, "guidance": guidance}), \
                patch("spatial.agent.Machine", return_value=self.machine), \
                patch.object(self.machine, "to_file"), \
                patch.object(agents, "run_team_stream", side_effect=run_without_delays):
            result = await agents.build(self.task.model_copy(update={
                "content": "Continue the existing structure by adding block 16 at block 7's east face.",
            }))
        self.assertFalse(result.objection)
        self.assertEqual(result.result["num_blocks"], 16)
        self.assertEqual(len(builder.create_calls), 3)
        self.assertEqual(len(guidance.create_calls), 3)
        tools = {tool["name"] for tool in guidance.create_calls[0]["tools"]}
        self.assertEqual(tools, {"inspect_geometry", "get_block_details", "raise_objection_build"})
        self.assertIn("verified tool evidence", guidance.create_calls[0]["messages"][0].content)
        self.assertEqual(config, original_config)
        self.update_task.assert_not_called()


if __name__ == "__main__":
    unittest.main()
