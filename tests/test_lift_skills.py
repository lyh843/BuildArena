"""Offline document/retrieval checks; never execute the embedded Lift policies."""

import ast
import json
from pathlib import Path
import re
import unittest

from skill.library import DEFAULT_DIRECTORY, SkillLibrary


LIFT_IDS = {
    "lift_thrust_budget", "lift_mass_balance", "lift_thrust_alignment",
    "lift_heating_layout", "lift_startup_asymmetry", "lift_symmetric_assembly",
}
CONTEXT = dict(category="lift", level="hard", role="planner", stage="plan")


class LiftSkillTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.library = SkillLibrary(allow_drafts=True)

    def test_documents_and_static_reference_code(self):
        self.assertEqual({k for k in self.library.documents if k.startswith("lift_")}, LIFT_IDS)
        for ident in sorted(LIFT_IDS):
            with self.subTest(skill=ident):
                doc = self.library.documents[ident]
                meta, content = doc["metadata"], doc["content"]
                for key in ("prerequisites", "environment_constraints", "sources", "code_evidence"):
                    self.assertTrue(meta[key])
                self.assertEqual(meta["version"], "0.1.0")
                self.assertEqual(meta["policy_mode"], "reference_only")
                self.assertEqual(meta["validation"]["human_review"], "pending")
                for key in ("logic_tests", "geometry_checks", "physics_trials"):
                    self.assertEqual(meta["validation"][key], "not_run")
                self.assertEqual(re.findall(r"^# (\d+)\.", content, re.M), list("123456789"))
                for source in meta["sources"]:
                    self.assertEqual(source["license_status"], "unconfirmed")
                    self.assertEqual(len(source["pdf_pages"]), len(source["printed_pages"]))
                    self.assertTrue(all(type(n) is int and n > 0 for n in source["pdf_pages"]))
                for evidence in meta["code_evidence"]:
                    self.assertTrue(Path(evidence["path"]).is_file())
                snippets = re.findall(r"```python\n(.*?)```", content, re.S)
                self.assertEqual(len(snippets), 2)
                source = "\n".join(snippets)
                tree = ast.parse(source)
                compile(tree, ident, "exec")  # Compilation only, no evaluation.
                self.assertGreaterEqual(sum(isinstance(n, ast.Assert) for n in ast.walk(tree)), 8)
                for node in ast.walk(tree):
                    self.assertNotIsInstance(node, (ast.Import, ast.While))
                    if isinstance(node, ast.ImportFrom):
                        self.assertEqual((node.module, node.level), ("math", 0))
                    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                        self.assertNotIn(node.func.id, {"exec", "eval", "open", "__import__", "input"})

    def test_bilingual_retrieval(self):
        queries = {
            "lift_thrust_budget": ("起飞推重比 整机质量 推力区间", "rocket thrust weight budget"),
            "lift_mass_balance": ("质心配平 质量加权 火把重排", "center of mass centroid balance"),
            "lift_thrust_alignment": ("喷流反冲方向 合力 质心偏心力矩", "thrust alignment resultant nozzle torque"),
            "lift_heating_layout": ("火把热球 炮体表面 加热覆盖", "steam heating torch coverage"),
            "lift_startup_asymmetry": ("启动不同步 角冲量 热失配", "startup transient asymmetry angular impulse"),
            "lift_symmetric_assembly": ("对称总装 底盘 发动机实例 接口", "hard symmetric assembly chassis interfaces"),
        }
        for expected, phrases in queries.items():
            for query in phrases:
                with self.subTest(query=query):
                    self.assertEqual(self.library.search(query, CONTEXT)[0]["id"], expected)

    def test_category_level_and_review_filters(self):
        with self.assertRaisesRegex(ValueError, "allow_drafts"):
            SkillLibrary()
        for level in ("soft", "medium", "hard"):
            eligible = {ident for ident in self.library.documents
                        if self.library.eligible(ident, {**CONTEXT, "level": level})}
            expected = LIFT_IDS if level == "hard" else LIFT_IDS - {"lift_symmetric_assembly"}
            self.assertEqual(eligible, expected)
        for category in ("support", "transport"):
            for ident in LIFT_IDS:
                self.assertFalse(self.library.eligible(ident, {**CONTEXT, "category": category}))

    def test_relations_have_existing_endpoints(self):
        edges = json.loads((DEFAULT_DIRECTORY / "relations.json").read_text())
        for edge in edges:
            self.assertIn(edge["source"], self.library.documents)
            self.assertIn(edge["target"], self.library.documents)
            if edge["source"] in LIFT_IDS:
                self.assertEqual(edge["review_status"], "pending")
                self.assertTrue(edge["reason"])
                self.assertTrue(edge["condition"])


if __name__ == "__main__":
    unittest.main()
