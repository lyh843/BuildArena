"""One construction sample per task/difficulty, with persistent coverage records."""

import argparse
import csv
from datetime import datetime
import hashlib
import json
from pathlib import Path
import signal
import sqlite3
import subprocess
import sys
import time


ROOT = Path(__file__).resolve().parents[1]
MODEL = "qwen3.8-max-0902"


def save_manifest(path, data):
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(data, indent=2), encoding="utf-8")
    temporary.replace(path)


def summarize(manifest):
    report = []
    for case in manifest["cases"]:
        row = dict(case)
        db = Path(case["db"])
        if db.exists():
            with sqlite3.connect(db) as connection:
                connection.row_factory = sqlite3.Row
                row["tasks"] = [dict(record) for record in connection.execute(
                    "SELECT id,stage,status,raise_objection,retry_count,error_info,"
                    "token_input,token_output,duration FROM task")]
                row["machines"] = [dict(record) for record in connection.execute(
                    "SELECT id,status,approved,num_blocks,cost,file_path FROM machine")]
        sim_dir = db.parent.with_name(db.parent.name + "_sim")
        sim_db = sim_dir / "simulation_database.db"
        row["simulation_tasks"] = []
        if sim_db.exists():
            with sqlite3.connect(sim_db) as connection:
                connection.row_factory = sqlite3.Row
                row["simulation_tasks"] = [dict(record) for record in connection.execute(
                    "SELECT id,stage,status,bind_machine,result_path,error_info,"
                    "token_input,token_output,duration FROM task")]
        all_tasks = row.get("tasks", []) + row["simulation_tasks"]
        row["recorded_token_input"] = sum(task["token_input"] or 0 for task in all_tasks)
        row["recorded_token_output"] = sum(task["token_output"] or 0 for task in all_tasks)
        metrics = sim_dir / "simulation_metrics.json"
        row["simulation_metrics"] = json.loads(metrics.read_text()) if metrics.exists() else None
        # Missing physics is not a measured zero or a task pass.
        row["physics_pass"] = (
            any(item.get("pass") is True for item in row["simulation_metrics"])
            if row["simulation_metrics"] else None
        )
        row["simulation_complete"] = bool(row["simulation_tasks"]) and all(
            task["status"] == "completed" for task in row["simulation_tasks"])
        rejected = any(task["raise_objection"] or task["status"] in ("failed", "error")
                       for task in row.get("tasks", []))
        row["sample_success"] = (
            False if rejected or case["construction_status"] in ("error", "interrupted")
            else row["physics_pass"] if row["simulation_complete"] else None
        )
        report.append(row)
    return report


def build_batch(path):
    from agents import PLANNER_REQUEST_TIMEOUT
    from scheduler.task_db import init_db, insert_config, load_config
    from script.run_construction import load_levels_yaml

    if path.exists():
        raise FileExistsError(f"Batch already exists; use its databases to resume: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    manifest = {
        "created_at": datetime.now().isoformat(), "model": MODEL,
        "samples_per_group": 1, "construction_timeout_seconds": 1800,
        "concurrent_constructions": 2,
        "model_settings": {"max_tokens": 16384, "timeout": 180, "max_retries": 1,
                           "extra_body": {"enable_thinking": True, "thinking_budget": 4096}},
        "planner_request_timeout_seconds": PLANNER_REQUEST_TIMEOUT,
        "input_sha256": {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
                         for name in ("levels.yaml", "prompt.yaml")},
        "cases": [],
    }
    for level in load_levels_yaml(str(ROOT / "levels.yaml")):
        category, difficulty = level["category"], level["level"]
        project = f"{category}_{difficulty}_{MODEL.replace('.', '-')}_{stamp}"
        db = ROOT / "datacache" / project / "task_database.db"
        if db.exists():
            raise FileExistsError(db)
        config = load_config(str(ROOT / "prompt.yaml"))
        config["project"] = {"name": project, "goal": level["task"]}
        for agent in config["agents"].values():
            agent["model"] = MODEL
        global_config = {"name": project, "goal": level["task"], "n_sample": 1, "max_workers": 1}
        init_db(str(db))
        insert_config(config, global_config, bind_task="root", db_path=str(db))
        manifest["cases"].append({
            "category": category, "level": difficulty, "db": str(db),
            "scene": f"support_{difficulty}" if category == "support" else "Barren Expanse",
            "construction_status": "queued",
            "log": str(db.parent / "construction.log"),
        })
    save_manifest(path, manifest)
    run_cases(path, manifest)


def run_cases(path, manifest):
    """Run frozen cases with the existing scheduler and preserve interrupted attempts."""
    active = []
    queued = list(manifest["cases"])
    try:
        while queued or active:
            while queued and len(active) < manifest["concurrent_constructions"]:
                case = queued.pop(0)
                stream = open(case["log"], "x", encoding="utf-8")
                try:
                    process = subprocess.Popen([
                        sys.executable, "-B", "-u", "-m", "scheduler.scheduler",
                        "--db_path", case["db"], "--timeout",
                        str(manifest["construction_timeout_seconds"]),
                    ], cwd=ROOT, stdout=stream, stderr=subprocess.STDOUT)
                except BaseException:
                    stream.close()
                    raise
                case["construction_status"] = "running"
                case["started_at"] = datetime.now().isoformat()
                active.append((case, process, stream, time.monotonic()))
                print(f"START {case['category']}/{case['level']} {case.get('arm', '')}", flush=True)
                save_manifest(path, manifest)
            for item in list(active):
                case, process, stream, start = item
                code = process.poll()
                if code is None:
                    continue
                stream.close()
                case.update(construction_status="ended" if code == 0 else "error",
                            exit_code=code, elapsed_seconds=round(time.monotonic() - start, 2))
                active.remove(item)
                print(f"END {case['category']}/{case['level']} {case.get('arm', '')} exit={code}", flush=True)
                save_manifest(path, manifest)
            time.sleep(2)
    finally:
        for case, process, stream, start in active:
            process.send_signal(signal.SIGINT)
        for case, process, stream, start in active:
            process.wait()
            stream.close()
            case["construction_status"] = "interrupted"
        save_manifest(path, manifest)
        save_manifest(path.with_name("coverage_report.json"), summarize(manifest))
    print(f"Construction coverage recorded: {path}", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=("build", "report"))
    parser.add_argument("--manifest", type=Path, required=True)
    args = parser.parse_args()
    if args.phase == "build":
        build_batch(args.manifest.resolve())
    else:
        manifest = json.loads(args.manifest.read_text())
        output = args.manifest.with_name("coverage_report.json")
        report = summarize(manifest)
        save_manifest(output, report)
        with output.with_suffix(".csv").open("w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=[
                "category", "level", "construction_status", "available_machine_block_counts",
                "simulated_rounds", "simulation_complete", "physics_pass", "sample_success",
                "metric", "best_measured_value", "recorded_token_input", "recorded_token_output",
            ])
            writer.writeheader()
            for case in report:
                machines = case.get("machines", [])
                candidates = [machine for machine in machines if machine["approved"]] or machines
                metric = {"transport": "max_transport_distance",
                          "support": "ballast_max_weight_at_threshold",
                          "lift": "total_propulsion_force" if case["level"] == "soft"
                          else "max_height"}[case["category"]]
                measurements = case["simulation_metrics"] or []
                values = [result[metric] for result in measurements if metric in result]
                writer.writerow({
                    **{key: case[key] for key in (
                        "category", "level", "construction_status", "simulation_complete",
                        "physics_pass", "sample_success", "recorded_token_input",
                        "recorded_token_output")},
                    "available_machine_block_counts": json.dumps(
                        [machine["num_blocks"] for machine in candidates]),
                    "simulated_rounds": len(measurements), "metric": metric,
                    "best_measured_value": max(values) if values else None,
                })
        print(output)


if __name__ == "__main__":
    main()
