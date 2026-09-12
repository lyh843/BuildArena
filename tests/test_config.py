import asyncio
import os
from pathlib import Path
import runpy
import sys
from types import ModuleType
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


class ConfigTests(unittest.TestCase):
    def test_only_configured_providers_are_registered(self):
        for enabled in (False, True):
            with self.subTest(ali_enabled=enabled):
                env = {
                    "API_KEY_ALI": "test-key" if enabled else "",
                    "ALI_BASE_URL": "https://example.invalid/compatible-mode/v1",
                    "OPENAI_API_KEY": "must-not-enable-openai",
                }
                with patch.dict(os.environ, env, clear=True), patch(
                    "dotenv.load_dotenv"
                ) as load_dotenv:
                    config = ModuleType("config")
                    config.__dict__.update(runpy.run_path(str(ROOT / "config.py")))
                    load_dotenv.assert_called_once_with(ROOT / ".env")
                    with patch.dict(sys.modules, {"config": config}):
                        clients = runpy.run_path(
                            str(ROOT / "agents" / "__init__.py")
                        )["model_clients"]

                expected = {"qwen3-max-preview", "qwen-plus", "qwen-flash", "qwen3.8-max-0902"} if enabled else set()
                self.assertEqual(set(clients), expected)
                for client in clients.values():
                    settings = client.dump_component().config
                    self.assertEqual(settings["api_key"].get_secret_value(), "test-key")
                    self.assertEqual(settings["base_url"], env["ALI_BASE_URL"])
                    asyncio.run(client.close())


if __name__ == "__main__":
    unittest.main()
