"""Build an offline report from explicit, read-only experiment sources."""
import csv
from datetime import datetime
import hashlib
import json
from pathlib import Path
import shutil
import sqlite3
import xml.etree.ElementTree as ET

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SOURCES = [
    ("S1", "skill_comparison_20260914"),
    ("S2", "skill_physics_comparison_20260914"),
    ("S3", "skill_validation_20260914_142655_740280"),
    ("S4", "skill_validation_20260914_152742"),
    ("S5", "skill_validation_20260914_160353"),
    ("M1", "support_construction_comparison_20260914_182948/medium"),
]
NOTES = {
    "S1N": ("旧流程 / 首轮对照", "33 块成品，未仿真。"),
    "S1K": ("旧流程 / 首轮对照", "Planner 曾超时；15 块候选被提出异议，未通过构建审核。"),
    "S2N": ("证据门槛 / 同批对照", "7 块成品；实际物理得分 0。"),
    "S2K": ("证据门槛 / 同批对照", "Planner 三次尝试均超时；无成品。已观察到的 token 不为零。"),
    "S3K": ("扩大技能预算 / 单臂验证", "总调度上限 1800 秒；中断时 46 块，没有正式 BSG；Build token 未完整落库。"),
    "S4K": ("移除固定等待 / 单臂验证", "单次非 Planner 请求提高到 1200 秒；总上限仍为 1800 秒。中断时 69 块，无正式 BSG。"),
    "S5K": ("两小时上限 / 单臂验证", "蓝图 103 块，实际导出 73 块，省略 30 根 Brace。用户接受该成品后单独仿真；不等同于完成原蓝图。"),
    "M1N": ("结构化改造前 / 同批对照", "156 块整机，旧流程审核完成；尚无物理测试。"),
    "M1K": ("结构化改造前 / 同批对照", "149 块只是一个子结构，原设计该子结构为 159 项；301 轮后被旧逻辑批准。另一子结构中断，没有完整桥梁。"),
    "M2N": ("结构化流程 / 中断后续跑", "保留 Planner，补充实际连接面证据后续跑。18 块整机。驱动用时仅覆盖续跑；请求日志还包含首次草拟。"),
    "M2K": ("结构化流程 / 正常建模尝试", "144 块整机已导出；Markdown 结束标记误判令装配任务失败。58 次装配响应仍计入请求日志，原任务状态未改写。"),
}
AUDIT = {}


def record_source(path):
    path = Path(path).resolve()
    key = str(path.relative_to(ROOT))
    AUDIT[key] = hashlib.sha256(path.read_bytes()).hexdigest()
    return key


def load(path):
    record_source(path)
    return json.loads(Path(path).read_text(encoding="utf-8"))


def event_rows(path):
    record_source(path)
    with path.open(encoding="utf-8") as stream:
        for number, line in enumerate(stream, 1):
            yield number, json.loads(line)


def trace(root, task):
    if task["stage"] == "plan":
        paths = list((root / "plan").glob(f"planner_{task['id']}.jsonl"))
    else:
        paths = list(root.rglob(f"requests_{task['id']}.jsonl"))
    totals = {"calls": 0, "errors": 0, "unmatched": 0, "seconds": 0,
              "input": 0, "output": 0, "compactions": 0, "roles": {}}
    starts, finishes, responses = set(), set(), set()
    max_chars = 0
    for path in paths:
        for _, event in event_rows(path):
            kind = event.get("event")
            request = event.get("request_id")
            if kind == "request_start":
                starts.add(request)
                max_chars = max(max_chars, event.get("input_chars", 0))
            elif kind in ("request_end", "request_error"):
                finishes.add(request)
                if request in responses:
                    raise ValueError("Duplicate terminal request event: " + request)
                responses.add(request)
                role = totals["roles"].setdefault(event["role"], {
                    "calls": 0, "errors": 0, "seconds": 0, "input": 0, "output": 0})
                if kind == "request_end":
                    for key, field in (("input", "prompt_tokens"), ("output", "completion_tokens")):
                        value = event["usage"][field]
                        totals[key] += value
                        role[key] += value
                    totals["calls"] += 1
                    role["calls"] += 1
                else:
                    totals["errors"] += 1
                    role["errors"] += 1
                totals["seconds"] += event["elapsed_seconds"]
                role["seconds"] += event["elapsed_seconds"]
            elif kind == "context_compacted":
                totals["compactions"] += 1
    totals.update(unmatched=len(starts - finishes), max_input_chars=max_chars)
    return totals if starts else None


def geometry(root):
    result = {"preflight_pass": 0, "preflight_fail": 0, "batch_pass": 0,
              "batch_fail": 0, "preflight_seconds": 0, "batch_seconds": 0,
              "failure_codes": {}, "examples": []}
    for path in sorted(root.rglob("*.jsonl")):
        if not (path.name.startswith("blueprint") or path.name == "batches.jsonl"):
            continue
        for number, event in event_rows(path):
            kind = event.get("event")
            if kind not in ("blueprint_preflight", "batch_result"):
                continue
            prefix = "preflight" if kind == "blueprint_preflight" else "batch"
            ok = event["result"]["ok"]
            result[prefix + ("_pass" if ok else "_fail")] += 1
            result[prefix + "_seconds"] += event.get("elapsed_seconds", 0)
            if not ok:
                failure = event["result"].get("failure") or {}
                code = failure.get("code", "unknown")
                result["failure_codes"][code] = result["failure_codes"].get(code, 0) + 1
                result["examples"].append({
                    "source": str(path.relative_to(ROOT)), "line": number, "code": code,
                    "operation": failure.get("id"), "detail": failure.get("detail", "")[:800]})
    return result


def read_tasks(root):
    db = root / "task_database.db"
    record_source(db)
    with sqlite3.connect(f"file:{db}?mode=ro", uri=True) as conn:
        conn.row_factory = sqlite3.Row
        rows = [dict(row) for row in conn.execute(
            "SELECT id,stage,status,token_input,token_output,turn,duration,retry_count,"
            "created_at,updated_at FROM task ORDER BY created_at")]
    for row in rows:
        row["wall_seconds"] = (datetime.fromisoformat(row["updated_at"])
                               - datetime.fromisoformat(row["created_at"])).total_seconds()
        row["trace"] = trace(root, row)
    return rows


def case_from(raw, identifier, source):
    root = Path(raw["db"]).parent
    tasks = read_tasks(root)
    stages = []
    for stage in ("plan", "draft", "build", "assemble"):
        selected = [task for task in tasks if task["stage"] == stage]
        if not selected:
            continue
        traces = [task["trace"] for task in selected if task["trace"]]
        stages.append({
            "stage": stage, "tasks": len(selected),
            "db_minutes": sum(task["duration"] or 0 for task in selected),
            "db_missing_durations": sum(task["duration"] is None for task in selected),
            "db_turns": sum(task["turn"] or 0 for task in selected),
            "db_input": sum(task["token_input"] or 0 for task in selected),
            "db_output": sum(task["token_output"] or 0 for task in selected),
            "wall_seconds": sum(task["wall_seconds"] for task in selected),
            "trace": ({key: sum(t[key] for t in traces) for key in
                       ("calls", "errors", "unmatched", "seconds", "input", "output", "compactions")}
                      if traces else None),
        })
    trace_values = [task["trace"] for task in tasks if task["trace"]]
    if trace_values:
        assert len(trace_values) == len(tasks), "Partial trace coverage requires explicit accounting"
    recorded_in = sum(task["token_input"] or 0 for task in tasks)
    recorded_out = sum(task["token_output"] or 0 for task in tasks)
    observed_in = (sum(t["input"] for t in trace_values) if trace_values
                   else raw.get("observed_token_input_lower_bound", recorded_in))
    observed_out = (sum(t["output"] for t in trace_values) if trace_values
                    else raw.get("observed_token_output_lower_bound", recorded_out))
    machines = raw.get("machines", [])
    blocks = max((m["num_blocks"] for m in machines), default=None)
    candidate = {"M2N": ("xplauguj", 18), "M2K": ("7obu80bf", 144)}.get(identifier)
    if candidate:
        machine_id, blocks = candidate
        bsg = root / "machine" / machine_id / f"{machine_id}.bsg"
        assert len(ET.parse(bsg).getroot().findall("./Blocks/Block")) == blocks
        record_source(bsg)
    else:
        machine_id = max(machines, key=lambda m: m["num_blocks"])["id"] if machines else None
    start = raw.get("started_at") or min(t["created_at"] for t in tasks)
    end = max(t["updated_at"] for t in tasks)
    result = {
        "id": identifier, "level": raw["level"], "arm": raw["arm"],
        "model": "qwen3.8-max-0902", "project": root.name,
        "label": NOTES[identifier][0], "note": NOTES[identifier][1],
        "started_at": start, "last_task_update": end,
        "driver_seconds": raw.get("elapsed_seconds"),
        "wall_seconds": (datetime.fromisoformat(end) - datetime.fromisoformat(start)).total_seconds(),
        "db_minutes": sum(t["duration"] or 0 for t in tasks),
        "db_turns": sum(t["turn"] or 0 for t in tasks),
        "db_input": recorded_in, "db_output": recorded_out,
        "observed_input": observed_in, "observed_output": observed_out,
        "usage_basis": "request_end" if trace_values else "DB + observed failed Planner responses",
        "trace_calls": sum(t["calls"] for t in trace_values) if trace_values else None,
        "unmatched_requests": sum(t["unmatched"] for t in trace_values) if trace_values else None,
        "construction_complete": raw.get("construction_complete", all(t["status"] == "completed" for t in tasks)),
        "machine_id": machine_id, "blocks": blocks, "physics": None,
        "skills": sorted({r["id"] for r in raw.get("skill_reads", [])}),
        "tasks": tasks, "stages": stages, "source": record_source(source),
    }
    if identifier.startswith("M2"):
        result["geometry"] = geometry(root)
        for path in (root / "plan").glob("*.jsonl"):
            for _, event in event_rows(path):
                if event.get("event") == "read_skill":
                    result["skills"].append(event["argument"])
        result["skills"] = sorted(set(result["skills"]))
    return result


def add_physics(case):
    root = ROOT / "datacache" / (case["project"] + "_sim")
    metrics_path = root / "simulation_metrics.json"
    if not metrics_path.exists():
        return
    metrics = load(metrics_path)
    assert len(metrics) == 1
    metric = metrics[0]
    assert case["blocks"] == metric["num_blocks"]
    machine = metric["machine_id"]
    base = root / "simulation" / machine / f"simulation_log_{machine}_sim"
    runtime = load(base.with_suffix(".runtime.json"))
    csv_path = base.with_suffix(".csv")
    record_source(csv_path)
    with csv_path.open(newline="") as stream:
        rows = list(csv.reader(stream))
    positions = sorted([float(r[0]), float(r[3])] for r in rows if len(r) == 5 and r[1] == "ID_Ballast")
    weights = sorted([float(r[0]), float(r[2])] for r in rows if len(r) == 3 and r[1] == "ID_Ballast")
    crossing = next((p for p in positions if p[1] < 4), None)
    assert runtime["physics_stopped"] and positions[-1][0] == 17
    assets = HERE / "assets"
    assets.mkdir(exist_ok=True)
    screenshot = base.with_suffix(".loaded.png")
    record_source(screenshot)
    shutil.copy2(screenshot, assets / (case["id"] + ".png"))
    evidence = HERE / "evidence"
    evidence.mkdir(exist_ok=True)
    shutil.copy2(csv_path, evidence / (case["id"] + ".csv"))
    shutil.copy2(base.with_suffix(".runtime.json"), evidence / (case["id"] + ".runtime.json"))
    case["physics"] = {
        "score": metric["ballast_max_weight_at_threshold"], "pass": metric["pass"],
        "hold": metric["hold_time_above_threshold"], "mass": metric["total_mass"],
        "crossing": crossing[0] if crossing else None, "min_height": metric["ballast_min_height"],
        "time_range": [positions[0][0], positions[-1][0]], "positions": positions,
        "position_rows": len(positions), "weight_rows": len(weights),
        "screenshot": f"assets/{case['id']}.png", "csv": f"evidence/{case['id']}.csv",
        "runtime": f"evidence/{case['id']}.runtime.json", "metrics_source": record_source(metrics_path),
        "discarded_conflicting_keys": runtime["discarded_conflicting_keys"],
    }


def main():
    excluded = load(ROOT / "report/excluded_records.json")
    excluded_names = {item["project"] for item in excluded["excluded"]}
    cases = []
    for prefix, directory in SOURCES:
        source = ROOT / "datacache" / directory / "skill_comparison_report.json"
        for raw in load(source):
            assert Path(raw["db"]).parent.name not in excluded_names
            identifier = prefix + ("K" if raw["arm"] == "with_skills" else "N")
            cases.append(case_from(raw, identifier, source))
    for identifier, project in (
        ("M2N", "support_medium_no_skills_20260915_112355"),
        ("M2K", "support_medium_with_skills_20260915_130148"),
    ):
        source = ROOT / "datacache" / project / "manifest.json"
        manifest = load(source)
        raw = dict(manifest["cases"][0])
        if identifier == "M2N":
            resume = load(source.with_name("resume_manifest.json"))["cases"][0]
            raw["elapsed_seconds"] = resume["elapsed_seconds"]
        cases.append(case_from(raw, identifier, source))
    for case in cases:
        add_physics(case)
    assert len(cases) == 11
    assert sum(c["physics"] is not None for c in cases) == 4
    assert not any(c["project"] in excluded_names for c in cases)
    for path in ("skill/CONSTRUCTION_ACCEPTANCE.md", "spatial/construction.py", "spatial/runtime.py",
                 "spatial/agent.py", "spatial/build.py", "skill/library.py", "prompt.yaml",
                 "analyze/sim_support.py", "simulation/windows_runner.py"):
        record_source(ROOT / path)
    data = {"generated_at": datetime.now().astimezone().isoformat(), "cases": cases,
            "excluded": excluded["excluded"], "source_sha256": AUDIT}
    (HERE / "data.json").write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    template = (HERE / "template.html").read_text(encoding="utf-8")
    payload = json.dumps(data, ensure_ascii=False).replace("<", "\\u003c")
    (HERE / "index.html").write_text(template.replace("__REPORT_DATA__", payload), encoding="utf-8")
    print("id | driver seconds | DB minutes | observed input/output | trace responses | score")
    for c in cases:
        print(c["id"], c["driver_seconds"], round(c["db_minutes"], 2),
              c["observed_input"], c["observed_output"], c["trace_calls"],
              c["physics"]["score"] if c["physics"] else None)


if __name__ == "__main__":
    main()
