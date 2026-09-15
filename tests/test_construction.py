import asyncio
import copy
import json
import sqlite3
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from autogen_agentchat.base import TaskResult
from autogen_agentchat.messages import TextMessage
from autogen_core import FunctionCall
from autogen_core.models import AssistantMessage, UserMessage, FunctionExecutionResult, FunctionExecutionResultMessage
from autogen_ext.models.replay import ReplayChatCompletionClient

from scheduler.task_db import Task, init_db, insert_task, get_task, mark_task_failed
from spatial.agent import MultiAgents
from spatial.build import Machine
from spatial.construction import BatchExecutor, Blueprint, BUILD_OPERATIONS, Operation
from spatial.runtime import IncompleteConstruction, TracedClient, WorkingContext, require_completion
from tests.test_skills import call, completion


MODEL_INFO = dict(vision=False, function_calling=True, json_output=False,
                  family="unknown", structured_output=False)
RECIPE = [
    {"id": "base", "op": "start", "params": {}},
    {"id": "wood", "op": "attach_block_to",
     "params": {"base_block": "$base", "face": "E", "new_block": "Small Wooden Block"}},
]


class ConstructionTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.machine = Machine(name="test", db_path=str(self.root / "task.db"),
                               save_dir=self.temp.name)
        self.tools = [method for name, method in self.machine.operations.items()
                      if name in BUILD_OPERATIONS]
        self.executor = BatchExecutor(self.machine, self.tools, self.root / "batches.jsonl")
        self.blueprint = Blueprint(self.root / "blueprints.jsonl", "Build two blocks",
                                   self.executor.tools, executor=self.executor)

    async def submit(self, operations=RECIPE):
        return await self.blueprint.submit_blueprint(
            [Operation.model_validate(op) for op in operations], "Preserve bank contacts")

    async def test_turn_limit_never_counts_as_completion(self):
        for reason, messages in [
            ("Maximum number of turns 300 reached.", [TextMessage(source="guidance", content="Next brace")]),
            ("Text 'TERMINATE' mentioned", [TextMessage(source="builder", content="TERMINATE")]),
            (None, []),
        ]:
            with self.assertRaises(IncompleteConstruction):
                require_completion(TaskResult(messages=messages, stop_reason=reason), "guidance")
        require_completion(TaskResult(
            messages=[TextMessage(source="guidance", content="Done. TERMINATE")],
            stop_reason="Text mentioned"), "guidance")

    async def test_completion_accepts_formatted_final_marker_not_embedded_mentions(self):
        for marker in ("**TERMINATE**", "__TERMINATE__", "`TERMINATE`"):
            require_completion(TaskResult(messages=[
                TextMessage(source="guidance", content="Final full review complete.\n\n" + marker)],
                stop_reason="Text 'TERMINATE' mentioned"), "guidance")
        for content in ("NOT_TERMINATE", "TERMINATE later after inspection"):
            with self.assertRaises(IncompleteConstruction):
                require_completion(TaskResult(messages=[
                    TextMessage(source="guidance", content=content)],
                    stop_reason="Text 'TERMINATE' mentioned"), "guidance")

    async def test_batch_prefix_retry_conflict_and_actual_endpoint_evidence(self):
        bad = {"id": "brace", "op": "connect_blocks",
               "params": {"block_a": "$base", "face_a": "E", "block_b": "$wood",
                          "face_b": "F", "connector": "Brace"}}
        result = self.executor.run([*RECIPE, bad])
        self.assertFalse(result["ok"])
        self.assertEqual(len(self.executor.completed), 2)
        self.assertEqual(self.machine.num_blocks, 2)
        self.assertEqual(result["failure"]["endpoints"]["distance"], 0)
        self.assertEqual(result["failure"]["code"], "faces_too_close")
        self.executor.run([*RECIPE, bad])
        self.assertEqual(self.machine.num_blocks, 2)
        conflict = copy.deepcopy(RECIPE[0])
        conflict["params"] = {"init_shift": [2, 0, 0]}
        self.assertFalse(self.executor.run([conflict])["ok"])
        good = copy.deepcopy(bad)
        good["params"]["face_b"] = "E"
        self.assertTrue(self.executor.run([good])["ok"])
        self.assertEqual(self.machine.num_blocks, 3)
        # The start block's E face is occupied, but its nonzero Brace is legal.
        self.assertFalse(self.machine.geometry_snapshot()["blocks"]["1"]["faces"]["E"]["attachable"])

    async def test_invalid_face_reports_available_actual_faces(self):
        wrong = copy.deepcopy(RECIPE)
        wrong[1]["params"]["face"] = "south"
        result = self.executor.run(wrong)
        faces = result["failure"]["actual_blocks"]["1"]["faces"]
        self.assertIn("E", faces)
        self.assertIn("normal", faces["E"])
        self.assertIn("center", faces["E"])

    async def test_versioned_patch_preflight_and_completion(self):
        self.assertTrue((await self.submit())["ok"])
        self.assertTrue((await self.blueprint.validate_blueprint())["ok"])
        self.assertEqual(self.machine.num_blocks, 0)  # Temporary geometry only.
        self.assertTrue((await self.blueprint.approve_blueprint(1, "Intent checked"))["ok"])
        self.assertFalse((await self.blueprint.execute_next_batch(["wood"], 1))["ok"])
        self.assertTrue((await self.blueprint.execute_next_batch(["base"], 1))["ok"])
        self.assertFalse(self.blueprint.complete())
        self.assertFalse((await self.blueprint.patch_blueprint(
            0, [], [], [], "stale"))["ok"])
        self.assertFalse((await self.blueprint.patch_blueprint(
            1, [], ["base"], [], "delete executed"))["ok"])
        self.assertFalse((await self.blueprint.patch_blueprint(
            1, [], ["wood"], [Operation(id="wrong", op="attach_block_to", params={
                "base_block": "$missing", "face": "E", "new_block": "Small Wooden Block"})],
            "missing reference"))["ok"])
        self.assertEqual(self.blueprint.version, 1)
        self.assertTrue((await self.blueprint.execute_next_batch(["base", "wood"], 1))["ok"])
        self.assertTrue(self.blueprint.complete())

    async def test_model_request_error_is_logged(self):
        client = TracedClient(ReplayChatCompletionClient([]), self.root / "requests.jsonl", "builder")
        with self.assertRaises(ValueError):
            await client.create([UserMessage(source="user", content="test")])
        events = [json.loads(line) for line in (self.root / "requests.jsonl").read_text().splitlines()]
        self.assertEqual([event["event"] for event in events], ["request_start", "request_error"])
        self.assertEqual(events[0]["request_id"], events[1]["request_id"])

    async def test_nonretryable_failure_consumes_scheduler_retry_budget(self):
        db = str(self.root / "terminal.db")
        init_db(db)
        insert_task(name="bounded repair", stage="build", content="test", db_path=db)
        with sqlite3.connect(db) as connection:
            task_id = connection.execute("SELECT id FROM task").fetchone()[0]
        mark_task_failed(task_id, "local_repair_exhausted", db, retryable=False)
        task = get_task(task_id, db)
        self.assertEqual(task.status, "failed")
        self.assertEqual(task.retry_count, task.max_retries)

    async def test_context_summary_failure_keeps_original_discussion(self):
        context = WorkingContext(ReplayChatCompletionClient([]), lambda: "protected task",
                                 self.root / "context.jsonl", max_chars=4000, keep_messages=2)
        for text in ("x" * 4100, "last instruction", "latest failure"):
            await context.add_message(UserMessage(source="user", content=text))
        with self.assertRaises(ValueError):
            await context.get_messages()
        self.assertEqual(len(context._messages), 3)
        self.assertEqual(context._messages[0].content, "x" * 4100)

    async def test_context_summarizes_only_on_threshold_and_preserves_tool_pairs(self):
        client = ReplayChatCompletionClient([completion("Rejected zero-length brace; repair pending")])
        context = WorkingContext(client, lambda: "version=2; required=all; pending=brace",
                                 self.root / "context.jsonl", max_chars=4000, keep_messages=2)
        await context.add_message(UserMessage(source="user", content="x" * 4100))
        await context.add_message(UserMessage(source="user", content="recent guidance"))
        await context.add_message(AssistantMessage(
            source="builder", content=[FunctionCall(id="c", name="read", arguments="{}")]))
        await context.add_message(FunctionExecutionResultMessage(content=[
            FunctionExecutionResult(call_id="c", name="read", content="failure")]))
        messages = await context.get_messages()
        self.assertIn("version=2", messages[0].content)
        self.assertEqual(len(client.create_calls), 1)
        self.assertIsInstance(messages[-2], AssistantMessage)
        self.assertIsInstance(messages[-1], FunctionExecutionResultMessage)
        self.assertNotIn("x" * 100, str(messages))
        await context.get_messages()
        self.assertEqual(len(client.create_calls), 1)
        saved = await context.save_state()
        await context.clear()
        await context.load_state(saved)
        self.assertIn("zero-length", context.summary)

    async def test_context_does_not_silently_drop_protected_facts(self):
        client = ReplayChatCompletionClient([])
        context = WorkingContext(client, lambda: "x" * 4001, self.root / "events",
                                 max_chars=4000)
        with self.assertRaisesRegex(IncompleteConstruction, "canonical facts"):
            await context.get_messages()

    async def test_structured_draft_and_build_use_one_builder_request_for_two_blocks(self):
        drafter = ReplayChatCompletionClient([
            call("submit_blueprint", operations=RECIPE, interfaces="Preserve bank contacts"),
            completion("No open issues."),
        ], model_info=MODEL_INFO)
        reviewer = ReplayChatCompletionClient([
            call("validate_blueprint"), call("finish_review", version=1, review="Intent checked"),
        ], model_info=MODEL_INFO)
        builder = ReplayChatCompletionClient([
            call("execute_next_batch", operation_ids=["base", "wood"], version=1),
        ], model_info=MODEL_INFO)
        guidance = ReplayChatCompletionClient([
            completion("Execute base and wood at version 1."),
            call("finish_build", review="Both blocks meet the recipe."),
        ], model_info=MODEL_INFO)
        config = {"construction": {"structured": True},
                  "agents": {role: {"name": role, "model": role, "system_message": "Follow task"}
                             for role in ("drafter", "draft_reviewer", "builder", "guidance")}}
        clients = dict(drafter=drafter, draft_reviewer=reviewer, builder=builder, guidance=guidance)
        task = Task(id="test", stage="draft", content="Build two blocks",
                    db_path=str(self.root / "task.db"))
        with patch.dict("spatial.agent.model_clients", clients), \
                patch("spatial.agent.get_config", return_value=SimpleNamespace(config=config)), \
                patch.object(Machine, "to_file"):
            agents = MultiAgents(verbose=False)
            draft = await agents.draft(task)
            result = await agents.build(task.model_copy(update={"stage": "build", "content": draft.result}))
        self.assertEqual(result.result["num_blocks"], 2)
        self.assertEqual(len(builder.create_calls), 1)
        self.assertEqual(result.result["local_repairs"], 0)
        self.assertEqual(len(drafter.create_calls), 2)  # No full-blueprint summary request.

    async def test_local_repair_changes_only_pending_operation_then_continues(self):
        replacement = copy.deepcopy(RECIPE[1])
        replacement["params"]["face"] = "F"
        clients = {
            "drafter": ReplayChatCompletionClient([
                call("patch_blueprint", base_version=1, replacements=[replacement],
                     delete_ids=[], append=[], reason="Use the opposite side; keep interfaces"),
                completion("Interface and functional intent remain unchanged."),
            ], model_info=MODEL_INFO),
            "draft_reviewer": ReplayChatCompletionClient([
                call("validate_blueprint"),
                call("finish_review", version=2, review="Reviewed changed face and interfaces"),
            ], model_info=MODEL_INFO),
            "guidance": ReplayChatCompletionClient([
                completion("Execute base and wood at version 1."),
                completion("Execute remaining wood at version 2."),
                call("finish_build", review="Recipe completed after local repair"),
            ], model_info=MODEL_INFO),
            "builder": ReplayChatCompletionClient([
                call("execute_next_batch", operation_ids=["base", "wood"], version=1),
                call("execute_next_batch", operation_ids=["wood"], version=2),
            ], model_info=MODEL_INFO),
        }
        config = {"agents": {role: {"name": role, "model": role, "system_message": "Follow task"}
                             for role in clients}}
        task = Task(id="test", stage="build", db_path=str(self.root / "task.db"))
        document = dict(version=1, interfaces="Preserve bank contacts",
                        operations=RECIPE, task="Build two blocks")
        detect = self.machine.collision_detect
        failed = False

        def fail_once(*args, **kwargs):
            nonlocal failed
            if self.machine.num_blocks == 2 and not failed:
                failed = True
                return "Injected collision at first pending attachment"
            return detect(*args, **kwargs)

        with patch.dict("spatial.agent.model_clients", clients), \
                patch.object(self.machine, "collision_detect", side_effect=fail_once), \
                patch.object(self.machine, "to_file"):
            result = await asyncio.wait_for(MultiAgents(False).build_recipe(
                task, config, self.machine, str(self.root), document), timeout=15)
        self.assertEqual(result.result["local_repairs"], 1)
        self.assertEqual(result.result["blueprint_version"], 2)
        self.assertEqual(self.machine.num_blocks, 2)
        self.assertEqual(sum(op["op"] == "start" for op in self.machine.operation_history), 1)
        events = [json.loads(line) for line in (self.root / "requests_test.jsonl").read_text().splitlines()]
        self.assertEqual(sum(event["event"] == "local_repair_start" for event in events), 1)

    async def test_repair_budget_exhaustion_does_not_approve(self):
        bad = [*RECIPE, {"id": "brace", "op": "connect_blocks", "params": {
            "block_a": "$base", "face_a": "E", "block_b": "$wood", "face_b": "F", "connector": "Brace"}}]
        document = dict(version=1, interfaces="unchanged", operations=bad, task="Build bridge")
        config = {"construction": {"max_local_repairs": 0}}
        task = Task(id="test", stage="build", db_path=str(self.root / "task.db"))
        with self.assertRaisesRegex(IncompleteConstruction, "local_repair_exhausted"):
            await MultiAgents(False).build_recipe(task, config, self.machine, str(self.root), document)
        self.assertEqual(self.machine.num_blocks, 0)

    async def test_actual_prefix_drift_is_not_hidden_by_replay(self):
        await self.submit()
        await self.blueprint.validate_blueprint()
        await self.blueprint.approve_blueprint(1, "Reviewed")
        await self.blueprint.execute_next_batch(["base"], 1)
        self.machine.blocks["1"].shift([4, 0, 0])
        result = await self.blueprint.validate_blueprint()
        self.assertFalse(result["ok"])
        self.assertEqual(result["failure"]["code"], "executed_prefix_state_drift")

    async def test_legacy_turn_limit_cannot_reach_scheduler_approval(self):
        config = {"construction": {"structured": False}, "agents": {
            role: {"name": role, "model": role, "system_message": "Follow task"}
            for role in ("builder", "guidance")}}
        client = ReplayChatCompletionClient([], model_info=MODEL_INFO)
        task = Task(id="test", stage="build", content="old blueprint",
                    db_path=str(self.root / "task.db"))
        result = TaskResult(messages=[TextMessage(
            source="guidance", content="Next brace remains")],
            stop_reason="Maximum number of turns 300 reached.")
        from scheduler import runner
        with patch.dict("spatial.agent.model_clients", dict(builder=client, guidance=client)), \
                patch("spatial.agent.get_config", return_value=SimpleNamespace(config=config)), \
                patch.object(MultiAgents, "run_team_stream", return_value=result), \
                patch.object(Machine, "to_file"), \
                patch("scheduler.runner.insert_machine") as insert, \
                patch("scheduler.runner.mark_machine_unverified") as approve:
            with self.assertRaisesRegex(IncompleteConstruction, "turn_limit"):
                await runner.run_build(task, {})
            insert.assert_not_called()
            approve.assert_not_called()

    async def test_historical_medium_batches_match_single_operations(self):
        path = Path("datacache/support_medium_qwen3-8-max-0902_20260914_183535_730926_pair1_with_skills"
                    "/machine/xlsrk4pu/xlsrk4pu.json")
        if not path.exists():
            self.skipTest("Optional local historical trace is absent")
        history = json.loads(path.read_text())
        operations = [{"id": f"step{index}", "op": item["op"], "params": item["params"]}
                      for index, item in enumerate(history) if item["op"] in BUILD_OPERATIONS]
        single = Machine(name="single", db_path=str(self.root / "single.db"), save_dir=self.temp.name)
        one = BatchExecutor(single, [method for name, method in single.operations.items()
                                    if name in BUILD_OPERATIONS], self.root / "single.jsonl")
        for operation in operations:
            self.assertTrue(one.run([operation])["ok"])
        for index in range(0, len(operations), 5):
            self.assertTrue(self.executor.run(operations[index:index + 5])["ok"])
        self.assertEqual(single.geometry_snapshot()["blocks"], self.machine.geometry_snapshot()["blocks"])
        self.assertEqual(self.machine.num_blocks, 149)
        self.assertEqual(len(operations), 149)
        self.assertEqual((len(operations) + 4) // 5, 30)


if __name__ == "__main__":
    unittest.main()
