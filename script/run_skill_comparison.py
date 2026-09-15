"""Paired, planner-only skill ablation. Construction does not operate the game GUI."""

import argparse
from datetime import datetime
import hashlib
from importlib.metadata import version
import json
from pathlib import Path

from script.run_coverage import ROOT, MODEL, run_cases, save_manifest, summarize
from skill.library import DEFAULT_DIRECTORY, configure_planner_skills


def model_request_settings(client):
    config = client.dump_component().config
    # AutoGen's component schema drops extra_body, although it is sent on create().
    config = {**config, **getattr(client, "_create_args", {})}
    return {key: config[key] for key in (
        "model", "max_tokens", "timeout", "max_retries", "extra_body",
        "temperature", "top_p", "seed", "parallel_tool_calls",
    ) if key in config}


def prepare_comparison(path, *, model=MODEL, level="soft", pairs=1, timeout=7200,
                       skills_dir=DEFAULT_DIRECTORY, allow_drafts=False):
    from agents import model_clients, planner_model_clients
    from scheduler.task_db import init_db, insert_config, load_config
    from script.run_construction import find_level_task, load_levels_yaml

    if path.exists():
        raise FileExistsError(f"Existing comparison must not be overwritten: {path}")
    if pairs < 1 or timeout < 1:
        raise ValueError("pairs and timeout must be positive")
    if model not in model_clients:
        raise ValueError("Requested model is not configured")
    task = find_level_task(load_levels_yaml(str(ROOT / "levels.yaml")), "support", level)
    if not task:
        raise ValueError(f"Unknown support level: {level}")
    path.parent.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    treatment = {}
    configure_planner_skills(
        treatment, category="support", level=level, snapshot_dir=path.parent / "skills_snapshot",
        directory=skills_dir, allow_drafts=allow_drafts,
    )
    manifest = {
        "created_at": datetime.now().isoformat(), "model": model, "pairs": pairs,
        "samples_per_group": pairs, "construction_timeout_seconds": timeout,
        "concurrent_constructions": 2, "workers_per_case": 1,
        "model_settings": model_request_settings(model_clients[model]),
        "planner_model_settings": model_request_settings(
            planner_model_clients.get(model, model_clients[model])),
        "packages": {name: version(name) for name in (
            "autogen-agentchat", "autogen-core", "autogen-ext", "openai",
        )},
        "skills": treatment["skills"],
        "comparison": "original vs planner-only lexical TF-IDF; no graph expansion",
        "budget_note": "Same per-request and wall-clock limits; extra skill calls are charged. "
                       "No equal-total-token cap. Provider defaults remain unset in both arms.",
        "physics_note": "Separate, scene-verified simulation required; missing physics is null.",
        "input_sha256": {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
                         for name in (
                             "levels.yaml", "prompt.yaml", "agents/__init__.py",
                             "skill/library.py", "spatial/agent.py", "spatial/construction.py",
                             "spatial/runtime.py", "spatial/build.py", "scheduler/worker.py",
                             "scheduler/runner.py", "scheduler/scheduler.py",
                             "script/run_skill_comparison.py",
                         )},
        "cases": [],
    }
    for pair in range(1, pairs + 1):
        for arm in (("without_skills", "with_skills") if pair % 2 else
                    ("with_skills", "without_skills")):
            project = f"support_{level}_{model.replace('.', '-')}_{stamp}_pair{pair}_{arm}"
            db = ROOT / "datacache" / project / "task_database.db"
            config = load_config(str(ROOT / "prompt.yaml"))
            config.pop("skills", None)
            config["project"] = {"name": project, "goal": task}
            for agent in config["agents"].values():
                agent["model"] = model
            if arm == "with_skills":
                config["skills"] = treatment["skills"]
            global_config = {"name": project, "goal": task, "n_sample": 1, "max_workers": 1}
            init_db(str(db))
            insert_config(config, global_config, bind_task="root", db_path=str(db))
            manifest["cases"].append({
                "pair": pair, "arm": arm, "category": "support", "level": level,
                "db": str(db), "scene": f"support_{level}", "construction_status": "queued",
                "log": str(db.parent / "construction.log"),
            })
    save_manifest(path, manifest)
    return manifest


def comparison_report(manifest):
    report = summarize(manifest)
    for case in report:
        tasks = case.get("tasks", [])
        case["construction_complete"] = (
            bool(tasks) and all(task["status"] == "completed" and not task["raise_objection"]
                                for task in tasks)
            and any(machine["approved"] for machine in case.get("machines", []))
        )
        if not case["construction_complete"] and case["construction_status"] in (
            "ended", "error", "interrupted"
        ):
            case["sample_success"] = False
        events = []
        for path in sorted((Path(case["db"]).parent / "plan").glob("planner_*.jsonl")):
            for line in path.read_text(encoding="utf-8").splitlines():
                try:
                    events.append(json.loads(line))
                except json.JSONDecodeError:
                    # An interrupted append is not proof that its model request was free.
                    case["incomplete_planner_log"] = True
        reads = [event for event in events if event["event"] == "read_skill"]
        case["skill_reads"] = [
            {key: event["result"][key] for key in ("id", "version", "sha256")}
            for event in reads if "content" in event["result"]
        ]
        case["skill_search_calls"] = sum(event["event"] == "search_skills" for event in events)
        case["skill_tool_errors"] = sum(
            "error" in event.get("result", {}) for event in events
            if event["event"] in ("read_skill", "search_skills"))
        usage = [event["message"].get("models_usage") or {}
                 for event in events if event["event"] == "message"]
        case["planner_token_input"] = sum(item.get("prompt_tokens", 0) for item in usage)
        case["planner_token_output"] = sum(item.get("completion_tokens", 0) for item in usage)
        case["planner_attempts"] = sum(event["event"] == "planner_start" for event in events)
        case["planner_model_responses"] = sum(bool(item) for item in usage)
        case["planner_elapsed_seconds"] = sum(
            event["elapsed_seconds"] for event in events
            if event["event"] in ("planner_result", "planner_error"))
        for direction in ("input", "output"):
            persisted_planner = sum(task.get(f"token_{direction}") or 0
                                    for task in tasks if task.get("stage") == "plan")
            case[f"observed_token_{direction}_lower_bound"] = (
                case.get(f"recorded_token_{direction}", 0)
                + max(0, case[f"planner_token_{direction}"] - persisted_planner)
            )
        case["usage_caveat"] = (
            "DB tokens cover persisted successful stages. Planner JSONL additionally covers "
            "observed failed-attempt responses; never add it to DB totals without deduplication. "
            "In-flight requests, provider retries and failed downstream stages may be unaccounted."
        )
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=("build", "report"))
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--model", default=MODEL)
    parser.add_argument("--level", choices=("soft", "medium", "hard"), default="soft")
    parser.add_argument("--pairs", type=int, default=1)
    parser.add_argument("--timeout", type=int, default=7200)
    parser.add_argument("--skills-dir", type=Path, default=DEFAULT_DIRECTORY)
    parser.add_argument("--allow-draft-skills", action="store_true")
    args = parser.parse_args()
    path = args.manifest.resolve()
    if args.phase == "build":
        manifest = prepare_comparison(
            path, model=args.model, level=args.level, pairs=args.pairs, timeout=args.timeout,
            skills_dir=args.skills_dir, allow_drafts=args.allow_draft_skills,
        )
        try:
            run_cases(path, manifest)
        finally:
            save_manifest(path.with_name("skill_comparison_report.json"), comparison_report(manifest))
    else:
        manifest = json.loads(path.read_text(encoding="utf-8"))
        save_manifest(path.with_name("skill_comparison_report.json"), comparison_report(manifest))
    print(path.with_name("skill_comparison_report.json"))


if __name__ == "__main__":
    main()
