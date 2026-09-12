# Nine-Group Qwen Coverage

Started September 11, 2026, 17:07:06 (Asia/Shanghai).
This is one sample per group, not a success-rate reproduction.

## Model And Protocol

The configured Alibaba-compatible endpoint listed `qwen3.8-max-0902`.
A real tool-call preflight returned the same model ID and valid tool arguments
(320 input, 39 output tokens). This verifies the account's API identifier and
tool-call compatibility, not the identity of underlying hosted weights.
Credentials and complete client configuration are not stored in this report.

- Model for every agent, including controller: `qwen3.8-max-0902`.
- Maximum output per request: 16,384 tokens.
- Thinking enabled; requested thinking budget: 4,096.
- Request timeout: 180 seconds; SDK retries: 1.
- One plan per category/difficulty; two concurrent construction schedulers,
  each with one worker and a 1,800-second overall timeout.
- The repository's existing stage retries and multi-agent turn limits remain.
- Task descriptions, agent prompts and evaluation thresholds are unchanged.
- Build objections and failures remain in the sample denominator.
- Transport uses up to three control-feedback trials for the same machine.
- Windows physics must run serially in the appropriate scene.
- Besiege 1.90-25346 and Lua Scripting Mod 1.2.0 are used.

The construction manifest includes hashes of `levels.yaml` and `prompt.yaml`.
Artifacts are under `datacache/coverage_qwen38_20260911/`; the manifest points
to all nine project databases and construction logs. Run the following without
API calls to refresh the status report:

```bash
conda run -n BuildArena python -B -m script.run_coverage report \
  --manifest datacache/coverage_qwen38_20260911/manifest.json
```

The report distinguishes a missing measurement (`null`) from a measured
physics failure (`false`), and rejects objected construction even if an
incomplete machine happens to pass a downstream threshold. An exited
construction scheduler alone does not imply successful construction.
Task token counts include persisted stages; interrupted calls may not be
included, so these are not billing totals.

## Coverage Results

Updated September 11, 2026 after the original Support Soft machine replay.
The report command exports both `coverage_report.json` and `coverage_report.csv`.
Distances and weights below are repository/game units, not SI measurements.

| Task | Level | Construction blocks | Physics trials | Result / metric |
| --- | --- | --- | --- | --- |
| Transport | Soft | 7 | 3 | Pass; best radial displacement 275.51 |
| Transport | Medium | 6 | 3 | Fail; best cargo displacement 2.33 |
| Transport | Hard | 18 | 3 | Fail; best cargo displacement 6.25 |
| Support | Soft | 38 | 1 | Pass; threshold weight 449.51, hold time 4.60 s |
| Support | Medium | 3 parts of 13 each | 0 | Assembly timed out; no complete machine or physics measurement |
| Support | Hard | No complete machine | 0 | Construction timed out; no physics measurement |
| Lift | Soft | 2, rejected partial | 1 diagnostic | Fail; no Water Cannon, estimated thrust 0 |
| Lift | Medium | No complete machine | 0 | Repeated API timeouts; no physics measurement |
| Lift | Hard | No complete machine | 0 | Construction timed out; no physics measurement |

Two of nine attempted samples pass the repository's thresholds within this
budget. This is not a statistically meaningful success rate or nine completed
physics samples. Transport feedback trials and separate GUI diagnostics do
not increase the sample count. Support's pass also does not mean the load
survived the full 17 seconds: its height eventually fell below the threshold.

## Execution Repairs

Before starting the batch:

1. Design-approved, unverified parts can enter assembly. Previously assembly
   waited for a verification stage that is not implemented in this pipeline.
   This is assembly readiness, not physical verification.
2. Non-rotating accepted builds receive the same design-approved status as
   accepted refinements. Refined machine paths use the machine ID.
3. All Lift difficulties activate their Water Cannons after a two-second
   settling interval; previously Soft did not activate the firing key.
4. Draft objections create their output directory before recording rejection.
5. Exhausted multi-part plans fail explicitly instead of idling indefinitely.

These changes are covered by the focused regression suite, alongside existing
Windows bridge safety and SQLite backup tests.

## Interpretation Limits

- One sample per group is a functional coverage check, not a stable estimate
  of success probability, and cannot establish a causal model improvement.
- The old `qwen-plus` sample had two blocks and only one wheel. Its build
  objection involved wheel orientation and an incorrect claim about available
  repair tools. That implicates reasoning and agent/tool coordination; it is
  not evidence of a general intelligence limit.
- Transport's repository `pass` mostly checks radial displacement, with a
  four-wheel requirement on Soft. It does not independently certify arrival
  at `(10,10)` or the Hard return trip. Inspect trajectories as well.
- Lift Soft's analyzer estimates thrust from cannon burning state and mass,
  rather than directly measuring the force described in the task text.
- Large Lift machines track four randomly chosen non-starting blocks under
  the original adapter. Untracked cannons limit burning-state metrics.
- Support needs three different terrain saves, with 5/10/20-unit gaps.
- Raw BSG files include automatically added cargo. The repository analyzer's
  `num_blocks` explicitly excludes Ballast; construction counts are also
  retained independently.
- Clipboard sampling and the newer game version limit exact comparability
  with the original paper.

## Telemetry Repairs During Coverage

Transport Soft round 2 had conflicting position records at `7.88, ID_1`:
one clipboard capture truncated `59.99` to `5`. This produced an artificial
maximum speed of 1,382.75. The original CSV and runtime metadata are preserved
with `.original` in their filenames, alongside the unchanged raw log.
Both conflicting readings were excluded, yielding a maximum speed of 10.3017.
The same conflict rule is now applied to every exported trial, including
auxiliary weight records; no performance-based outlier filter is used.

The native runner also rejects almost-black captures with a bright cursor,
checks Lua-panel visibility, and removes keyboard focus from the Lua log before
toggling the panel. Failure to hide a panel after physics has verifiably stopped
is recorded as a cleanup warning instead of discarding valid telemetry.

Transport Soft round 3 initially failed to capture the Lua panel. Its original
failure metadata and screenshots are preserved as `.attempt1.*`. The exact same
BSG and model-generated control sequence were replayed without another model
call. Replay captured all 30 seconds but initially failed to hide the Lua panel;
its CSV was recovered from the raw log after checking all expected block IDs,
the timestamp range, and the stopped-game screenshot. Its runtime JSON records
this recovery explicitly. All three Transport Soft rounds are now complete.

## Support Scene Recovery

The custom level initially remained in editor mode, and its Lua panel reset
to a different position. `datacache/windows_profile_support.json` calibrates
that panel separately. The native runner initially refused to start because
its visibility check failed, then refused to accept a run when the game did
not enter the running state. The user reported a build-boundary obstruction.
The level file requests `DisableBounds=True`; the game also warns that some
rules apply only outside editor mode. Closing the editor alone did not solve
the start failure. The user subsequently reported resolving the obstruction.
The exact final UI setting changed by the user was not independently recorded.

Two in-game machine saves, `u7t5a75l_manual_20260911.bsg` and
`u7t5a75l_resolved_20260911.bsg`, were compared with the original BSG. All 39
block GUIDs, types and transforms (including the added ballast), the global
transform and embedded Lua matched numerically within serialization precision.
Game serialization changed some non-geometric metadata. No machine movement
was detected in these snapshots; the current terrain was not re-exported for
comparison. This remains a manually prepared scene, not a fully automated
environment reproduction.

The resolved snapshot produced one complete diagnostic trial: 835 rows,
0.32--17.00 seconds, threshold weight 222.27 and hold time 2.32 seconds.
Earlier partial logs are not accepted measurements. Diagnostic artifacts
remain under `datacache/coverage_qwen38_20260911/support_soft_manual/` and are
excluded from the coverage sample count and project metrics.

The exact original BSG was then replayed without a model call or machine edit.
It produced 836 rows, 0.32--17.00 seconds, no conflicting readings, and a
confirmed stopped game. Its SHA-256 is
`b90c67d00545f7bed6d95b8b21e1c5942c51ea3714399639d5eee9566b163410`.
Task `uovh7c6j` was marked completed only after checking the CSV, runtime
metadata and hash; its earlier error information remains. The standard
simulation CLI resumed only to generate metrics. The two complete trials
gave different threshold weights; both are retained rather than selecting a
diagnostic result as the official sample.
