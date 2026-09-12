from pathlib import Path
import runpy
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch


ROOT = Path(__file__).resolve().parents[1]


class SimulationOperationsTests(unittest.TestCase):
    def load_operations(self):
        modules = {
            name: MagicMock()
            for name in ("pyautogui", "pyperclip", "pynput", "pynput.mouse")
        }
        with patch.dict(sys.modules, modules):
            return runpy.run_path(str(ROOT / "simulation" / "operations.py"))

    def test_windows_focus_requires_an_exact_visible_game_window(self):
        focus = self.load_operations()["windows_focus_window"]
        for title, visible, expected in (
            ("Besiege - Steam Community", True, False),
            ("Besiege", False, False),
            ("Besiege", True, True),
        ):
            with self.subTest(title=title, visible=visible):
                gui = MagicMock()
                gui.GetWindowText.return_value = title
                gui.IsWindowVisible.return_value = visible
                gui.EnumWindows.side_effect = lambda callback, name: callback(42, name)
                with patch.dict(sys.modules, {"win32gui": gui}):
                    self.assertEqual(focus("Besiege"), expected)
                if expected:
                    gui.SetForegroundWindow.assert_called_once_with(42)
                else:
                    gui.SetForegroundWindow.assert_not_called()

    def test_simulation_without_a_game_window_sends_no_input(self):
        run = self.load_operations()["run_simulation_sequence"]
        with tempfile.TemporaryDirectory() as output_dir, patch.dict(
            run.__globals__,
            {"focus_window": lambda name: False},
        ):
            log = Path(output_dir) / "simulation_log_missing_game.csv"
            log.write_text("existing log", encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, "No input was sent"):
                run("missing_game", output_dir, 0.1)
            self.assertEqual(log.read_text(encoding="utf-8"), "existing log")
        run.__globals__["pyautogui"].assert_not_called()
        self.assertEqual(run.__globals__["pyautogui"].mock_calls, [])


if __name__ == "__main__":
    unittest.main()
