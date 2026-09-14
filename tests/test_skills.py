import asyncio
import ast
import json
from pathlib import Path
import re
import shutil
import sqlite3
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from autogen_core import FunctionCall
from autogen_core.models import CreateResult, RequestUsage
from autogen_ext.models.replay import ReplayChatCompletionClient

from scheduler.task_db import Task, load_config
from scheduler.worker import save_context
from script import run_skill_comparison as comparison
from skill.library import DEFAULT_DIRECTORY, SkillLibrary, SkillSession, configure_planner_skills
from spatial.agent import AvailableBlocks, MultiAgents


PLAN = """<building_plan><overall_structure><description>Bridge</description></overall_structure>
<sub_structures><sub_structure_1><name>Bridge</name><design_requirements>
support_contact_fbd@0.1.0: design contact only; verify both bank contacts after settling.
</design_requirements></sub_structure_1></sub_structures></building_plan>"""
CONTEXT = dict(category="support", level="soft", role="planner", stage="plan")


def completion(content):
    return CreateResult(content=content, finish_reason="stop" if isinstance(content, str)
                        else "function_calls",
                        usage=RequestUsage(prompt_tokens=11, completion_tokens=7), cached=False)


def call(name, **arguments):
    return completion([FunctionCall(id=name, name=name, arguments=json.dumps(arguments))])


class SkillTests(unittest.TestCase):
    def test_retrieval_filters_drafts_and_ranks_bilingual_queries(self):
        with self.assertRaisesRegex(ValueError, "allow_drafts"):
            SkillLibrary()
        library = SkillLibrary(allow_drafts=True)
        for query, expected in (
            ("跨中弯矩", "support_midspan_bending"),
            ("normal tangential friction mu static", "support_contact_friction"),
            ("plan contact fbd loads complete", "support_contact_fbd"),
        ):
            self.assertEqual(library.search(query, CONTEXT)[0]["id"], expected)
        self.assertEqual(library.search("friction", {**CONTEXT, "category": "lift"}), [])
        self.assertEqual(library.search("friction", {**CONTEXT, "stage": "simulation"}), [])
        self.assertEqual(library.search("zzzzunknownzzzz", CONTEXT), [])
        self.assertEqual(library.search("", CONTEXT), [])

    def test_snapshot_integrity_tool_budgets_and_no_path_reads(self):
        async def exercise(settings, log):
            session = SkillSession(settings, task_id="one", log_path=log)
            result = await session.search_skills("contact")
            self.assertLessEqual(len(result["candidates"]), 5)
            self.assertIn("error", await session.read_skill("../../config.py"))
            result = await session.read_skill("support_contact_fbd")
            self.assertEqual(result["policy_mode"], "reference_only")
            self.assertIn("def plan_contact_fbd", result["content"])
            self.assertEqual(result["validation"]["human_review"], "pending")
            await session.read_skill("support_contact_fbd")
            self.assertEqual((await session.read_skill("support_contact_fbd"))["error"],
                             "read_budget_exhausted")
            await session.search_skills("contact")
            self.assertEqual((await session.search_skills("contact"))["error"],
                             "search_budget_exhausted")
            self.assertLessEqual(session.chars, session.budget["max_chars"])
            limited = SkillSession({**settings, "budget": {"max_chars": 1}},
                                   task_id="two", log_path=log)
            self.assertIn("error", await limited.search_skills("contact"))
            self.assertEqual(limited.candidates, set())
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = {}
            configure_planner_skills(config, category="support", level="soft",
                                     snapshot_dir=root / "snapshot", allow_drafts=True)
            log = root / "events.jsonl"
            asyncio.run(exercise(config["skills"], log))
            self.assertTrue(all(json.loads(line)["task_id"]
                                for line in log.read_text().splitlines()))
            changed = root / "snapshot" / "support_contact_fbd.md"
            changed.write_text(changed.read_text() + "\nModified after freeze\n")
            with self.assertRaisesRegex(ValueError, "snapshot changed"):
                SkillSession(config["skills"], task_id="three", log_path=log)

    def test_invalid_and_reserved_skill_content_rejected(self):
        content = (DEFAULT_DIRECTORY / "support_contact_fbd.md").read_text()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "test.md"
            for text in (content + "\nTERMINATE\n",
                         content.replace("reference_only", "executable"),
                         content.replace("id: support_contact_fbd", "id: ../../config")):
                path.write_text(text)
                with self.assertRaises(ValueError):
                    SkillLibrary(directory, allow_drafts=True)
            path.write_text(content)
            (path.parent / "duplicate.md").write_text(content)
            with self.assertRaisesRegex(ValueError, "Duplicate"):
                SkillLibrary(directory, allow_drafts=True)

    def test_trusted_repository_reference_policies(self):
        # Explicit offline test of these five repository fixtures, never a retrieval capability.
        assertion_count = 0
        for path in sorted(DEFAULT_DIRECTORY.glob("support_*.md")):
            snippets = re.findall(r"```python\n(.*?)```", path.read_text(), re.S)
            self.assertEqual(len(snippets), 2, path.name)
            source = "\n".join(snippets)
            tree = ast.parse(source)
            assertion_count += sum(isinstance(node, ast.Assert) for node in ast.walk(tree))
            with self.subTest(skill=path.stem):
                exec(compile(tree, str(path), "exec"), {})
        self.assertEqual(assertion_count, 51)


class PlannerSkillTests(unittest.IsolatedAsyncioTestCase):
    async def run_planner(self, directory, responses, *, enabled, iterations=4):
        config = load_config("prompt.yaml")
        config["agents"]["planner"]["model"] = "replay"
        if enabled:
            configure_planner_skills(config, category="support", level="soft",
                                     snapshot_dir=Path(directory) / "skills", allow_drafts=True)
            config["skills"]["max_tool_iterations"] = iterations
        client = ReplayChatCompletionClient(
            responses, model_info=dict(vision=False, function_calling=True,
                                       json_output=False, family="unknown", structured_output=False))
        task = Task(id="plan_test", stage="plan", content="Build a support bridge",
                    db_path=str(Path(directory) / "task_database.db"))
        with patch("spatial.agent.get_config", return_value=SimpleNamespace(config=config)), \
                patch.dict("spatial.agent.model_clients", {"replay": client}):
            result = await MultiAgents(verbose=False).plan(task)
        await client.close()
        return result, client, config, task

    async def test_off_keeps_original_prompt_tools_and_one_model_call(self):
        with tempfile.TemporaryDirectory() as directory:
            result, client, config, task = await self.run_planner(
                directory, [completion(PLAN)], enabled=False)
            self.assertEqual(len(client.create_calls), 1)
            self.assertFalse(client.create_calls[0]["tools"])
            self.assertEqual(client.create_calls[0]["messages"][0].content,
                             config["agents"]["planner"]["system_message"].replace(
                                 "{available_blks}", AvailableBlocks))
            self.assertEqual((result.token_input, result.token_output), (11, 7))

    async def test_tools_produce_xml_transfer_requirements_and_serializable_logs(self):
        with tempfile.TemporaryDirectory() as directory:
            result, client, config, task = await self.run_planner(directory, [
                call("search_skills", query="contact fbd"),
                call("read_skill", skill_id="support_contact_fbd"),
                completion(PLAN),
            ], enabled=True)
            self.assertEqual(len(client.create_calls), 3)
            self.assertEqual((result.token_input, result.token_output), (33, 21))
            requirements = result.result["sub_structures"]["sub_structure_1"]["design_requirements"]
            self.assertIn("support_contact_fbd@0.1.0", requirements)
            with patch("scheduler.worker.get_config", return_value=SimpleNamespace(config=config)):
                save_context(result.context, task, directory)
            messages = json.loads((Path(directory) / "plan_plan_test_messages.json").read_text())
            self.assertEqual(sum(row["type"] == "ToolCallRequestEvent" for row in messages), 2)
            events = [json.loads(line) for line in
                      (Path(directory) / "plan/planner_plan_test.jsonl").read_text().splitlines()]
            self.assertTrue(any(event["event"] == "planner_result" for event in events))
            self.assertEqual(sum(event["event"] == "read_skill" for event in events), 1)

    async def test_tool_iteration_limit_still_requests_final_plan(self):
        with tempfile.TemporaryDirectory() as directory:
            result, client, _, _ = await self.run_planner(directory, [
                call("search_skills", query="contact"),
                completion(PLAN),
            ], enabled=True, iterations=1)
            self.assertEqual(len(client.create_calls), 2)
            self.assertIn("sub_structures", result.result)

    async def test_missing_xml_is_retried_and_both_calls_are_accounted(self):
        with tempfile.TemporaryDirectory() as directory:
            result, client, _, _ = await self.run_planner(
                directory, [completion("not XML"), completion(PLAN)], enabled=False)
            self.assertEqual(len(client.create_calls), 2)
            self.assertEqual((result.token_input, result.token_output), (22, 14))

    async def test_empty_xml_is_a_format_error_not_an_attribute_error(self):
        with tempfile.TemporaryDirectory() as directory:
            result, client, _, _ = await self.run_planner(
                directory, [completion("<building_plan></building_plan>"), completion(PLAN)],
                enabled=False)
            self.assertEqual(len(client.create_calls), 2)
            self.assertIn("sub_structures", result.result)

    async def test_failed_tool_loop_keeps_observed_usage(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError, "No more mock responses"):
                await self.run_planner(directory, [call("search_skills", query="contact")],
                                       enabled=True)
            events = [json.loads(line) for line in
                      (Path(directory) / "plan/planner_plan_test.jsonl").read_text().splitlines()]
            self.assertEqual(events[-1]["event"], "planner_error")
            self.assertEqual(events[-1]["token_input"], 11)


class ComparisonTests(unittest.TestCase):
    def test_request_snapshot_preserves_thinking_without_credentials(self):
        client = SimpleNamespace(
            dump_component=lambda: SimpleNamespace(config={
                "api_key": "must-not-log", "model": "replay", "timeout": 180,
            }),
            _create_args={"model": "replay", "extra_body": {
                "enable_thinking": True, "thinking_budget": 4096,
            }},
        )
        settings = comparison.model_request_settings(client)
        self.assertEqual(settings["extra_body"]["thinking_budget"], 4096)
        self.assertNotIn("must-not-log", json.dumps(settings))

    def test_pair_has_same_task_model_and_downstream_prompts(self):
        client = ReplayChatCompletionClient([])
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name in (
                "levels.yaml", "prompt.yaml", "agents/__init__.py", "skill/library.py",
                "spatial/agent.py", "scheduler/worker.py", "scheduler/runner.py",
                "scheduler/scheduler.py", "script/run_skill_comparison.py",
            ):
                (root / name).parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(comparison.ROOT / name, root / name)
            path = root / "comparison/manifest.json"
            with patch.object(comparison, "ROOT", root), \
                    patch.dict("agents.model_clients", {"replay": client}):
                manifest = comparison.prepare_comparison(
                    path, model="replay", pairs=1, timeout=60, allow_drafts=True)
            configs = []
            for case in manifest["cases"]:
                with sqlite3.connect(case["db"]) as db:
                    file_path = db.execute("SELECT file_path FROM config").fetchone()[0]
                configs.append(load_config(file_path))
            self.assertNotIn("skills", configs[0])
            self.assertTrue(configs[1]["skills"]["enabled"])
            self.assertEqual(configs[0]["agents"], configs[1]["agents"])
            self.assertEqual(configs[0]["project"]["goal"], configs[1]["project"]["goal"])
            self.assertEqual(len(configs[1]["skills"]["snapshot"]), 5)
            self.assertTrue(all(case["construction_status"] == "queued"
                                for case in manifest["cases"]))
            with self.assertRaises(FileExistsError):
                comparison.prepare_comparison(path)

    def test_report_does_not_equate_construction_with_physics(self):
        row = {
            "db": "/tmp/nonexistent_comparison_test/task_database.db",
            "construction_status": "ended", "tasks": [
                {"status": "completed", "raise_objection": None},
            ], "machines": [{"approved": True}], "sample_success": None,
            "physics_pass": None,
        }
        with patch.object(comparison, "summarize", return_value=[row]):
            report = comparison.comparison_report({})[0]
            self.assertTrue(report["construction_complete"])
            self.assertIsNone(report["sample_success"])
            self.assertEqual(report["skill_reads"], [])
            row["tasks"][0]["status"] = "processing"
            report = comparison.comparison_report({})[0]
            self.assertFalse(report["construction_complete"])
            self.assertFalse(report["sample_success"])

    def test_report_adds_failed_planner_usage_without_double_counting_success(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "plan").mkdir()
            (root / "plan/planner_test.jsonl").write_text("\n".join(json.dumps({
                "event": "message", "message": {
                    "models_usage": {"prompt_tokens": value, "completion_tokens": 5},
                },
            }) for value in (11, 22)))
            row = {
                "db": str(root / "task_database.db"), "construction_status": "running",
                "tasks": [{"stage": "plan", "status": "completed", "raise_objection": None,
                           "token_input": 22, "token_output": 5}],
                "machines": [], "recorded_token_input": 122, "recorded_token_output": 15,
            }
            with patch.object(comparison, "summarize", return_value=[row]):
                report = comparison.comparison_report({})[0]
            self.assertEqual(report["observed_token_input_lower_bound"], 133)
            self.assertEqual(report["observed_token_output_lower_bound"], 20)


if __name__ == "__main__":
    unittest.main()
