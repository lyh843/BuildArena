"""Small offline checks for report data, JavaScript syntax, and local links."""
from html.parser import HTMLParser
import json
from pathlib import Path
import subprocess

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


class Page(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []
        self.ids = set()
        self.scripts = []
        self.script = None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if attrs.get("id"):
            assert attrs["id"] not in self.ids, "Duplicate element ID"
            self.ids.add(attrs["id"])
        for key in ("href", "src"):
            if attrs.get(key):
                self.links.append(attrs[key])
        if tag == "script":
            self.script = {"type": attrs.get("type"), "content": ""}

    def handle_data(self, text):
        if self.script is not None:
            self.script["content"] += text

    def handle_endtag(self, tag):
        if tag == "script" and self.script is not None:
            self.scripts.append(self.script)
            self.script = None


def main():
    data = json.loads((HERE / "data.json").read_text())
    content = (HERE / "index.html").read_text()
    page = Page()
    page.feed(content)
    assert len(data["cases"]) == 11
    excluded = {entry["project"] for entry in data["excluded"]}
    assert not any(c["project"] in excluded for c in data["cases"])
    assert "449.51" not in content
    assert "__REPORT_DATA__" not in content
    assert not (ROOT / "datacache/analysis_simulation/sim_support_soft_qwen3-8-max-0902_u7t5a75l.json").exists()
    assert not (ROOT / "datacache/support_soft_qwen3-8-max-0902_20260911_170706_sim/simulation_metrics.json").exists()
    for link in page.links:
        if link.startswith("#"):
            assert link[1:] in page.ids, link
        else:
            assert (HERE / link).exists(), link
    for case in data["cases"]:
        assert sum(t["token_input"] or 0 for t in case["tasks"]) == case["db_input"]
        assert sum(t["token_output"] or 0 for t in case["tasks"]) == case["db_output"]
        if case["trace_calls"] is not None:
            for key in ("input", "output"):
                assert sum(t["trace"][key] for t in case["tasks"]) == case["observed_" + key]
            assert sum(t["trace"]["calls"] for t in case["tasks"]) == case["trace_calls"]
        if case["physics"]:
            for key in ("screenshot", "csv", "runtime"):
                assert (HERE / case["physics"][key]).is_file()
            assert case["physics"]["time_range"][1] == 17
    assert {c["id"]: c["physics"]["score"] for c in data["cases"] if c["physics"]} == {
        "S2N": 0.0, "S5K": 361.81, "M2N": 0.0, "M2K": 561.14}
    for script in page.scripts:
        if script["type"] == "application/json":
            assert json.loads(script["content"]) == data
        else:
            subprocess.run(["node", "--check", "-"], input=script["content"], text=True, check=True)
    print(f"PASS: 11 experiments, 4 physical results, {len(page.links)} static links, copied evidence, JS syntax.")
    print("No browser screenshot, mobile testing, model calls, or new game runs.")


if __name__ == "__main__":
    main()
