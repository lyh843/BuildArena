import asyncio
import csv
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from scheduler import runner
from scheduler.scheduler import PlanManager
from scheduler.task_db import (
    Task, fetch_tasks_by_stage, init_db, insert_task,
    update_plan_sub_structures, mark_task_completed,
)
from simulation import simulation_lift
from spatial.agent import Objection, ProcessContext
from script.run_coverage import main as coverage_main, save_manifest, summarize
from script.run_simulation import validate_scenes


class CoveragePipelineTests(unittest.TestCase):
    def test_batches_cannot_mix_support_terrains_or_barren_expanse(self):
        def db(name):
            return f"/tmp/project_root/{name}/task_database.db"
        self.assertEqual(validate_scenes([
            db("transport_soft_model"), db("lift_hard_model"),
        ]), "Barren Expanse")
        for names in (("support_soft_model", "support_hard_model"),
                      ("support_soft_model", "lift_soft_model")):
            with self.assertRaisesRegex(ValueError, "each scene separately"):
                validate_scenes([db(name) for name in names])

    def test_coverage_distinguishes_unmeasured_and_rejected_samples(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            db = root / "transport_soft_test/task_database.db"
            init_db(str(db))
            case = {"db": str(db), "construction_status": "ended",
                    "category": "transport", "level": "soft"}
            manifest = {"cases": [case]}
            path = root / "manifest.json"
            save_manifest(path, manifest)
            self.assertEqual(json.loads(path.read_text()), manifest)
            self.assertIsNone(summarize(manifest)[0]["sample_success"])
            metrics = db.parent.with_name(db.parent.name + "_sim") / "simulation_metrics.json"
            metrics.parent.mkdir()
            save_manifest(metrics, [{"pass": True}])
            self.assertIsNone(summarize(manifest)[0]["sample_success"])
            sim_db = str(metrics.parent / "simulation_database.db")
            init_db(sim_db)
            insert_task("physics", "simulation", "test", db_path=sim_db)
            physics = fetch_tasks_by_stage("simulation", sim_db)[0]
            mark_task_completed(physics.id, db_path=sim_db)
            self.assertTrue(summarize(manifest)[0]["sample_success"])
            case["construction_status"] = "error"
            self.assertFalse(summarize(manifest)[0]["sample_success"])
            save_manifest(path, manifest)
            with patch("sys.argv", ["run_coverage", "report", "--manifest", str(path)]):
                coverage_main()
            with (root / "coverage_report.csv").open(newline="") as stream:
                exported = list(csv.DictReader(stream))
            self.assertEqual(len(exported), 1)
            self.assertEqual(exported[0]["sample_success"], "False")
            self.assertEqual(exported[0]["best_measured_value"], "")

    def test_design_approved_parts_enter_assembly_once_without_physics_approval(self):
        with tempfile.TemporaryDirectory() as directory:
            db = str(Path(directory) / "task_database.db")
            init_db(db)
            insert_task("plan", "plan", "test", db_path=db)
            plan = fetch_tasks_by_stage("plan", db)[0]
            update_plan_sub_structures(plan.id, 2, db)
            folder = Path(directory) / "plan"
            folder.mkdir()
            (folder / f"plan_{plan.id}.json").write_text(json.dumps({
                "overall_structure": "assemble", "sub_structures": {
                    "sub_structure_1": "engine", "sub_structure_2": "chassis",
                },
            }))
            for sub in (1, 2):
                insert_task(f"part{sub}", "build", "blueprint", db_path=db,
                            bind_plan=plan.id, sub_structure=sub)
            result = ProcessContext([], {
                "result": "part", "has_spinful": False, "cost": 1, "num_blocks": 2,
            }, 0, 0, 0, False)
            with patch.object(runner.agents, "build", new=AsyncMock(return_value=result)):
                for task in fetch_tasks_by_stage("build", db):
                    asyncio.run(runner.run_build(task, {}))
            manager = PlanManager(plan.id, "config", "test", db)
            self.assertTrue(manager.check_satisfied())
            manager.insert_assemble_task()
            manager.insert_assemble_task()
            self.assertEqual(len(fetch_tasks_by_stage("assemble", db)), 1)

    def test_every_lift_level_fires_water_cannons(self):
        with tempfile.TemporaryDirectory() as directory:
            path = str(Path(directory) / "machine/rocket/rocket.json")
            for level, duration in (("soft", 10), ("medium", 30), ("hard", 30)):
                with self.subTest(level=level):
                    machine = MagicMock()
                    machine.blocks = {1: SimpleNamespace(
                        name="Water Cannon", local_id="ID_1", tracking=False,
                    )}
                    with patch.object(simulation_lift, "Assembly", return_value=machine), \
                            patch.object(simulation_lift.shutil, "copy"), \
                            patch.object(simulation_lift, "run_simulation_sequence") as dispatch:
                        simulation_lift.main(path, level)
                    machine.change_control_key.assert_called_once_with(
                        block_id="ID_1", action="hold_to_fire", new_key="Alpha1")
                    machine.add_control_sequence.assert_called_once_with(
                        time=2, key="Alpha1", hold_for=duration)
                    self.assertEqual(dispatch.call_args.kwargs["duration"], duration)

    def test_draft_objection_creates_its_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            objection = Objection(Task(id="draft", stage="draft", parent_id="plan",
                                       db_path=str(Path(directory) / "task_database.db")))
            with patch("spatial.agent.add_task_objection"), \
                    patch("spatial.agent.update_task_raise_objection"):
                objection.update_task_objection("invalid plan", "reason")
            self.assertTrue(Path(objection.objection_file_path).is_file())
            self.assertTrue(objection.objection_raised)


if __name__ == "__main__":
    unittest.main()
