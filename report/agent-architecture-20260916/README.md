# Current Agent Architecture

Verified against the local working tree on **2026-09-16**, including uncommitted
framework improvements. This is an implementation diagram, not a future plan.

- `agent-workflow.svg`: standalone, editable vector artwork, 2400 x 1590.
- `agent-workflow.png`: rendered preview of the same SVG.
- `validation.json`: XML/reference, canvas-boundary and label-overlap checks.
- `render.py`: reproduce the preview with system librsvg and Cairo; no downloads.

The visual follows the supplied reference: white background, dashed workflow
boundary, blue vector agents, bold role labels and paired review loops.
Labels use English, as in the reference. Agents are original vector drawings,
not cropped from the supplied picture. No external assets, fonts or scripts
are needed to open the SVG.

## Source Map

| Component | Implementation |
| --- | --- |
| Task definitions and default structured settings | `levels.yaml`, `prompt.yaml:1` |
| Planner, optional skill tools and design-requirement handoff | `spatial/agent.py:482`, `skill/library.py:175`, `scheduler/runner.py:19` |
| Skill applicability, lexical TF-IDF, budgets, snapshots | `skill/library.py:57`, `skill/library.py:150` |
| Drafter / Reviewer and current-version approval | `spatial/agent.py:251`, `spatial/agent.py:297` |
| Versioned operations, patches and temporary geometry replay | `spatial/construction.py:113` |
| Guidance / Builder, sequential 1-5 operation batches | `spatial/agent.py:312`, `spatial/construction.py:28` |
| Failed-batch evidence and at most two local repairs | `spatial/construction.py:41`, `spatial/agent.py:367` |
| Threshold-triggered LLM discussion summary + protected state | `spatial/runtime.py:91`, `spatial/agent.py:239` |
| Geometry, collisions, face occupancy and Brace endpoints | `spatial/build.py:725`, `spatial/build.py:874` |
| Actual-state evidence before legacy-path objection | `spatial/agent.py:66` |
| Explicit completion; no approval from internal thoughts | `spatial/runtime.py:21`, `spatial/agent.py:432` |
| Optional Refine and assembly of approved substructures | `scheduler/runner.py:62`, `scheduler/scheduler.py:11` |
| Task dependencies, workers, SQLite and request tracing | `scheduler/scheduler.py:99`, `scheduler/task_db.py`, `spatial/runtime.py:39` |
| Controller and up to three Transport trials | `spatial/agent.py:702`, `scheduler/runner.py:175` |
| Task adapters, Windows bridge and game-side Lua | `simulation/simulation_transport.py`, `simulation/dispatch.py`, `simulation/windows_runner.py`, `spatial/build.py:1281` |
| Telemetry metrics and results | `analyze/sim_transport.py`, `analyze/sim_support.py`, `analyze/sim_lift.py` |

## Important Boundaries

1. Skills are optional and Planner-only. Disabling skills leaves the construction
   machinery unchanged. Downstream agents see relevant conclusions in their plan,
   not direct retrieval tools. Skill Python is returned as reference text, never run.
2. Book extraction and experience curation are offline, not autonomous runtime
   learning. Draft skills require explicit opt-in. Retrieval is lexical TF-IDF,
   not semantic embeddings or graph expansion.
3. Batching, versioned local repair and WorkingContext apply to structured
   substructure Draft/Build. Refine and Assemble reuse Builder/Guidance with
   legacy dialogue; they are not separate new agent roles and do not use those
   structured-context facilities.
4. The completion/evidence box is a guard, not an additional LLM agent. The
   structured path validates recipe completion and actual geometry; legacy
   build/refine/assembly objections require fresh actual-state evidence.
5. Local repairs preserve executed operations and assembly interfaces. There are
   at most two attempts, inside the existing run budget. Unreconciled state or
   exhausted limits still fail explicitly; there is no guaranteed recovery.
6. Refinement is conditional on rotating blocks; assembly is conditional on
   multiple substructures. Their dashed enclosure represents those optional
   stages, not mandatory phases for every task.
7. Physics is a separate run. Transport's trajectory feedback changes control,
   not the built geometry or the skill library. Three trials are a maximum,
   not three independent construction samples. Support/Lift skip Controller.
8. The final game-files node represents the approved candidate. Failed or partial
   builds can also leave `.bsg` checkpoints, but those are not approved outputs.
9. Code checks use the repository's current geometric representation, not a
   physical-strength proof. A geometry pass does not imply game success.

## Regenerate Preview

From the repository root:

```bash
/usr/bin/python3 report/agent-architecture-20260916/render.py
```

The source map and SVG are hand-maintained. Review them when the workflow changes.
