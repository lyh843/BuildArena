import multiprocessing
from pathlib import Path
import tempfile
import time
import sys
import sqlite3
import unittest
from unittest.mock import MagicMock, patch

from PIL import Image
import yaml

from simulation import dispatch
from simulation.windows_runner import button_state, telemetry_rows, consolidate_telemetry
from simulation import windows_runner


ROOT = Path(__file__).resolve().parents[1]


class WindowsBridgeTests(unittest.TestCase):
    def test_black_capture_with_a_bright_cursor_is_still_unusable(self):
        image = Image.new("RGB", (1920, 1200), "black")
        image.paste("white", (0, 1190, 10, 1200))
        self.assertFalse(windows_runner.usable_capture(image))
        self.assertTrue(windows_runner.usable_capture(
            Image.new("RGB", (1920, 1200), (80, 120, 150))))

    def test_conflicting_clipboard_positions_are_not_speed_measurements(self):
        rows = telemetry_rows(
            "7.84, ID_1, -3.44, 0.93, 59.59\n"
            "7.88, ID_1, -3.46, 0.93, 5\n"
            "7.88, ID_1, -3.46, 0.93, 59.99\n"
            "7.92, ID_1, -3.48, 0.93, 60.31\n"
            "7.92, ID_1, -3.48, 0.93, 60.31\n"
            "7.92, ID_1, true\n"
        )
        cleaned, conflicts = consolidate_telemetry(rows, 30)
        self.assertEqual(conflicts, [(7.88, "ID_1", 5)])
        self.assertEqual(len(cleaned), 3)
        self.assertFalse(any(float(row[0]) == 7.88 for row in cleaned))
        self.assertTrue(any(len(row) == 3 for row in cleaned))

    def test_controller_is_configured_like_other_agents(self):
        config = yaml.safe_load((ROOT / "prompt.yaml").read_text(encoding="utf-8"))
        self.assertNotIn("controller", config)
        self.assertIn("controller", config["agents"])
        for name, agent in config["agents"].items():
            self.assertIn("model", agent, name)
            agent["model"] = "qwen-plus"
        self.assertEqual(config["agents"]["controller"]["model"], "qwen-plus")

    def test_telemetry_ignores_unrelated_clipboard_and_nonfinite_numbers(self):
        rows = telemetry_rows(
            "private clipboard\nLua error\n"
            "0.04, ID_1, 1, 2, 3\n0.04, ID_Ballast, 5\n"
            "0.04, ID_2, true\nnan, ID_1, 1, 2, 3\n"
            "0.1, ID_1, inf, 2, 3\n0.1, somebody, 1, 2, 3\n"
        )
        self.assertEqual(len(rows), 3)
        self.assertEqual(rows[0], ["0.04", "ID_1", "1", "2", "3"])
        self.assertEqual(telemetry_rows("0.32,ID_1,0.0", auxiliary_ids=set()), [])
        self.assertEqual(telemetry_rows("0.32,ID_1,0,true,0"), [])
        self.assertEqual(len(telemetry_rows("0.32,ID_Ballast,5", {"ID_Ballast"})), 1)

    def test_play_button_must_have_a_recognized_state(self):
        self.assertEqual(button_state(Image.new("RGB", (40, 45), (255, 30, 80))), "stopped")
        self.assertEqual(button_state(Image.new("RGB", (40, 45), (0, 240, 240))), "running")
        with self.assertRaises(RuntimeError):
            button_state(Image.new("RGB", (40, 45), "black"))

    def test_wsl_dispatch_does_not_import_gui_and_requires_output(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            profile = root / "profile.json"
            profile.write_text("{}", encoding="utf-8")
            (root / "sample.bsg").write_text("<Machine/>", encoding="utf-8")
            csv_file = root / "simulation_log_sample.csv"
            with patch.object(dispatch, "WINDOWS_PYTHON", "native-python.exe"), \
                    patch.object(dispatch, "WINDOWS_PROFILE", str(profile)), \
                    patch.object(dispatch, "windows_path", side_effect=lambda path: str(path)), \
                    patch.object(dispatch.subprocess, "run") as native:
                with self.assertRaisesRegex(RuntimeError, "did not produce telemetry"):
                    dispatch.run_simulation_sequence("sample", directory, 30, True)
                command = native.call_args.args[0]
                self.assertEqual(command[:2], ["native-python.exe", "-B"])
                self.assertEqual(command[-1], "--set-ground")
                self.assertEqual(native.call_args.kwargs, {"check": True, "timeout": 120})
                csv_file.write_text("0.0,ID_1,0,0,0\n", encoding="utf-8")
                self.assertEqual(dispatch.run_simulation_sequence("sample", directory, 17), str(csv_file))
                self.assertNotIn("--set-ground", native.call_args.args[0])
                with self.assertRaises(ValueError):
                    dispatch.run_simulation_sequence("sample", directory, 0)

    def test_scheduler_timeout_reaps_a_real_child(self):
        from scheduler.scheduler import Scheduler
        from scheduler.task_db import get_task, init_db, insert_task, fetch_tasks_by_stage

        with tempfile.TemporaryDirectory() as directory:
            db = str(Path(directory) / "task_database.db")
            init_db(db)
            insert_task(name="timeout_test", stage="plan", content="test", db_path=db)
            task = fetch_tasks_by_stage("plan", db)[0]
            child = multiprocessing.Process(target=time.sleep, args=(30,), name=f"plan_{task.id}")
            child.start()
            scheduler = Scheduler({"max_workers": 1}, db, timeout=-1)
            scheduler.active_processes.append(child)
            try:
                with self.assertRaises(TimeoutError):
                    scheduler.run()
                self.assertFalse(child.is_alive())
                self.assertEqual(get_task(task.id, db).status, "failed")
                self.assertEqual(scheduler.active_processes, [])
            finally:
                if child.is_alive():
                    child.terminate()
                child.join()

    def test_native_logging_failure_stops_physics_and_hides_lua(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            saved = root / "SavedMachines"
            saved.mkdir()
            source = 'print("ID_1")'
            lua = root / "main.lua"
            lua.write_text(source, encoding="utf-8")
            bsg = root / "sample.bsg"
            bsg.write_text(
                f'<Machine><Data><StringArray key="lua_data">{source}</StringArray></Data></Machine>',
                encoding="utf-8",
            )
            profile = {
                "client_size": [1920, 1200],
                "saved_machines": str(saved), "lua_file": str(lua),
                "positions": {
                    "open_folder": [396, 42], "enter_name": [948, 254],
                    "open_machine": [1218, 254], "log": [460, 200],
                    "lua_indicator": [160, 155],
                    "start_stop": [40, 42],
                },
            }
            gui, keyboard, clipboard, operations = [MagicMock() for _ in range(4)]
            gui.FindWindow.return_value = gui.GetForegroundWindow.return_value = 42
            gui.IsWindowVisible.return_value = True
            gui.IsIconic.return_value = False
            gui.GetClientRect.return_value = (0, 0, 1920, 1200)
            gui.ClientToScreen.side_effect = lambda hwnd, point: point
            operations.windows_focus_window.return_value = True
            operations.copy_text.side_effect = ["sample\u200b", "", ""]
            image = Image.new("RGB", (1920, 1200), (80, 120, 150))
            panel_visible = False
            def hotkey(*keys, **kwargs):
                nonlocal panel_visible
                if keys == ("ctrl", "l"):
                    panel_visible = not panel_visible
                    color = (180, 30, 70) if panel_visible else (80, 120, 150)
                    image.paste(color, (157, 152, 163, 158))
            keyboard.hotkey.side_effect = hotkey
            modules = {
                "win32gui": gui, "pyautogui": keyboard, "pyperclip": clipboard,
                "simulation.operations": operations,
            }
            with patch.dict(sys.modules, modules), \
                    patch("PIL.ImageGrab.grab", side_effect=lambda **kwargs: image.copy()), \
                    patch.object(windows_runner.time, "sleep"), \
                    patch.object(windows_runner, "button_state", side_effect=[
                        "stopped", "stopped", "running", "running", "stopped",
                    ]):
                with self.assertRaisesRegex(RuntimeError, "No numeric Lua telemetry"):
                    windows_runner.run(profile, bsg, root / "output", 5)
            clicks = operations.windows_click.call_args_list
            self.assertEqual(sum(call.args == (40, 42) for call in clicks), 2)
            self.assertEqual(keyboard.hotkey.call_args_list[-1].args, ("ctrl", "l"))
            self.assertFalse((root / "output/simulation_log_sample.csv").exists())

    def test_analysis_router_returns_the_computed_metrics(self):
        from analyze.sim_common import route_simulation_analysis
        result = {"pass": False, "num_blocks": 2}
        with patch("analyze.sim_transport.main", return_value=result), \
                patch("analyze.sim_common.copy_passed_bsg"):
            returned = route_simulation_analysis(
                "datacache/transport_soft_qwen-plus_20260911_120000_sim/"
                "simulation/sample/simulation_log_sample_sim_1.csv"
            )
        self.assertIs(returned, result)

    def test_gui_errors_are_not_automatically_retried(self):
        from scheduler import worker
        from scheduler.task_db import (
            get_task, init_db, insert_task, fetch_tasks_by_stage,
            fetch_and_mark_one_simulation_task,
        )
        with tempfile.TemporaryDirectory() as directory:
            db = str(Path(directory) / "simulation_database.db")
            init_db(db)
            insert_task(name="gui_error", stage="simulation", content="test", db_path=db)
            task = fetch_tasks_by_stage("simulation", db)[0]
            with patch.object(worker, "init_loop", return_value=MagicMock()), \
                    patch.object(worker, "do_worker", side_effect=RuntimeError("lost focus")), \
                    patch.object(worker.asyncio, "all_tasks", return_value=set()):
                worker.worker_process(task)
            self.assertEqual(get_task(task.id, db).status, "error")
            self.assertFalse(fetch_and_mark_one_simulation_task(1, db))

    def test_simulation_database_copy_includes_uncheckpointed_wal(self):
        from script.run_simulation import init_simulation_db
        from scheduler.task_db import init_db, insert_config
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            original = root / "original/task_database.db"
            target = root / "simulation/simulation_database.db"
            machines = root / "original/machine"
            machines.mkdir(parents=True)
            init_db(str(original))
            insert_config(
                {"project": {"goal": "test"}},
                {"name": "test", "max_workers": 1},
                db_path=str(original),
            )
            with sqlite3.connect(original) as connection:
                connection.execute("PRAGMA wal_autocheckpoint=0")
                connection.execute("CREATE TABLE wal_probe (value INTEGER)")
                connection.execute("INSERT INTO wal_probe VALUES (42)")
                connection.commit()
                self.assertTrue(Path(str(original) + "-wal").is_file())
                init_simulation_db(
                    str(original), str(target), str(machines),
                    str(root / "simulation/machine"), 1, "control", "test",
                )
                with sqlite3.connect(target) as copied:
                    self.assertEqual(copied.execute("SELECT value FROM wal_probe").fetchone(), (42,))


if __name__ == "__main__":
    unittest.main()
