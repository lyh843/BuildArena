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
    def test_explicit_compatible_pair_overrides_legacy_qwen_pair(self):
        env = {
            "OPENAI_API_KEY": "compatible-test-key",
            "OPENAI_BASE_URL": "https://compatible.example.invalid/v1",
            "API_KEY_ALI": "legacy-test-key",
            "ALI_BASE_URL": "https://legacy.example.invalid/v1",
        }
        with patch.dict(os.environ, env, clear=True), patch("dotenv.load_dotenv"):
            config = ModuleType("config")
            config.__dict__.update(runpy.run_path(str(ROOT / "config.py")))
            with patch.dict(sys.modules, {"config": config}):
                registry = runpy.run_path(str(ROOT / "agents" / "__init__.py"))
        for client in [*registry["model_clients"].values(),
                       *registry["planner_model_clients"].values()]:
            settings = client.dump_component().config
            self.assertEqual(settings["api_key"].get_secret_value(), env["OPENAI_API_KEY"])
            self.assertEqual(settings["base_url"], env["OPENAI_BASE_URL"])
            asyncio.run(client.close())

    def test_compatible_endpoint_never_uses_legacy_key(self):
        with patch.dict(os.environ, {
            "OPENAI_BASE_URL": "https://compatible.example.invalid/v1",
            "API_KEY_ALI": "legacy-test-key",
        }, clear=True), patch("dotenv.load_dotenv"):
            with self.assertRaisesRegex(ValueError, "requires OPENAI_API_KEY"):
                runpy.run_path(str(ROOT / "config.py"))

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
                        registry = runpy.run_path(
                            str(ROOT / "agents" / "__init__.py")
                        )
                        clients = registry["model_clients"]
                        planners = registry["planner_model_clients"]

                expected = {"qwen3-max-preview", "qwen-plus", "qwen-flash", "qwen3.8-max-0902"} if enabled else set()
                self.assertEqual(set(clients), expected)
                self.assertEqual(set(planners), {"qwen3.8-max-0902"} if enabled else set())
                if enabled:
                    base = clients["qwen3.8-max-0902"]
                    planner = planners["qwen3.8-max-0902"]
                    self.assertIsNot(base, planner)
                    self.assertEqual(base._client.timeout, 1200)
                    self.assertEqual(planner._client.timeout, 600)
                    self.assertEqual(planner._create_args,
                                     {**base._create_args, "timeout": 600})
                    self.assertEqual(planner._create_args["extra_body"], {
                        "enable_thinking": True, "thinking_budget": 4096,
                    })
                    self.assertEqual(planner.dump_component().config["max_retries"], 1)
                for client in [*clients.values(), *planners.values()]:
                    settings = client.dump_component().config
                    self.assertEqual(settings["api_key"].get_secret_value(), "test-key")
                    self.assertEqual(settings["base_url"], env["ALI_BASE_URL"])
                    asyncio.run(client.close())


if __name__ == "__main__":
    unittest.main()
