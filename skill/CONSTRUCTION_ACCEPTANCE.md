# Construction Workflow: Three-Batch Acceptance

Date: 2026-09-15

## Scope

New configurations generated from `prompt.yaml` enable structured substructure
drafting/building. Planner skill retrieval remains unchanged. Existing frozen
configurations without `construction.structured` retain legacy drafting; their
turn-limit approval bug is still fixed. Historical logs and blueprints are not
rewritten.

Assembly, refinement and legacy prose blueprints retain their existing tools;
they receive completion guards and request tracing, not recipe batching.
No paid model evaluation or Windows game physics was launched for this change.

## Batch 1: Completion and Evidence

- A max-turn stop or missing final reviewer completion raises
  `IncompleteConstruction`, before machine insertion/approval by the runner.
- Recipe completion additionally requires every approved operation, exact final
  geometry matching preflight, and no current collisions.
- Partial machines remain checkpoints, not approved components.
- Known incomplete construction failures exhaust automatic scheduler retries.
  Structured build errors do not automatically restart construction from zero.
- `Machine.check_connection` and `connect_blocks` share the endpoint distance
  rule. Coincident faces fail; occupied faces alone do not forbid a Brace.
- Model requests log start/end/error, role, request ID, elapsed time and usage.
  An unmatched start means interrupted/in-flight, not zero-cost completion.

## Batch 2: Batches and Hybrid Context

- Guidance selects the next 1..5 canonical IDs; Builder makes one
  `execute_next_batch` call. Existing geometry tools execute sequentially.
- The first failure stops execution and retains successful operations.
  Stable IDs prevent duplicate additions on same-session retries.
- Code supplies canonical task, constraints, interfaces, blueprint version and
  verified progress. Builders receive the next five operations; blueprint
  inspection and actual block details remain available on demand.
- Long discussion is summarized by the configured role's LLM only at a threshold.
  The summary replaces old model context rather than being appended to an
  unbounded history. Tool call/result pairs remain intact.
- Summaries are non-authoritative; structural facts are never summarized.
  Invalid summaries, failed summary requests or oversized protected context fail
  explicitly, without silently deleting the original discussion.
- Budgets cover model-context characters, not exact tokens or fixed system/tool
  schemas. Defaults: Builder/Guidance 60,000; Drafter/Reviewer 120,000; keep 8 recent
  messages. Summary usage is included in successful stage totals and request logs.

## Batch 3: Patches, Repair and Experience

- Drafter submits one structured recipe with stable operation IDs. Later patches
  validate base version, references, duplicate IDs and the executed prefix.
- Reviewer replays the recipe in a temporary Machine using the real geometry
  implementation, then explicitly reviews functional intent and interfaces.
  No additional full-blueprint formatting request follows approval.
- A failed live batch triggers up to two local review/repair rounds. Each invalidates
  old approval. Completed operations and assembly interfaces are locked.
- Actual prefix drift requires reconciliation; it is not hidden by a clean
  temporary replay. Interface/intent changes require escalation, not automatic
  "equivalent strength" claims. Process-restart recovery is not implemented.
- `geometry_brace_endpoints@0.1.0` records four verified Hard failures, links the
  shared code check and regression tests, and remains pending human review.
  Successful geometry does not establish physical strength.

## Offline Acceptance

Final result: 63 tests passed on 2026-09-15 (3.734 seconds reported by unittest,
excluding interpreter/import startup). `git diff --check` passed. Existing
unclosed-file ResourceWarnings remain in legacy machine/history and scheduler
code; they did not fail the suite.

Run in the existing BuildArena environment:

```bash
/home/lyh/miniconda3/envs/BuildArena/bin/python -B -m unittest discover -s tests
```

`tests/test_construction.py` covers completion/approval blocking, same-ID retries,
zero-length and nonzero occupied-face connections, patches, preflight isolation,
prefix drift, summary thresholds/failure, request error logging, local repair
continuation and scheduler retry exhaustion.

Historical Medium `xlsrk4pu` replay produces identical full geometry for single
operations and batches: 149 components, 149 single-operation calls versus 30
batch calls. The original history is a partial 159-item design, not a completed
bridge. This comparison proves execution equivalence, not live LLM latency savings.
The local historical test skips explicitly when that datacache is unavailable.

The Replay-model integration test constructs two blocks with one Builder request.
Real model response time, summary quality, total billed tokens and game scores
still require a new explicitly launched experiment with fresh configuration.

## Logs for the Next Experiment

- `plan/planner_<task>.jsonl`: Planner request and skill events.
- `draft/requests_<task>.jsonl`: drafting/review requests and team messages.
- `draft/blueprint_<task>.jsonl`: versions, patches, geometry preflight and approval.
- `machine/<id>/requests_<task>.jsonl`: construction/review/summary requests and repairs.
- `machine/<id>/batches.jsonl`: operations, successful prefix, failure and tool time.
- `machine/<id>/blueprints.jsonl`: construction-time versions and preflight time.

Group request events by request ID and role to separate model latency, tool time
and summary overhead. Do not add request usage to the same successful DB usage
again. Interrupted-stage request logs remain usable even without a final message
file. Existing 600s/1200s request timeouts and the scheduler wall-clock budget are
unchanged; local repairs run within that same scheduler budget.
