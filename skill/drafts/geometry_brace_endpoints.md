---
id: geometry_brace_endpoints
title: Check actual Brace endpoint separation before specifying reinforcement
summary: BuildArena rejects coincident connector face centers. Plan separated endpoints and verify them in the geometry engine; contacting wooden faces do not define a usable Brace span.
version: 0.1.0
policy_mode: reference_only
applicability:
  categories: [support]
  levels: [soft, medium, hard]
  roles: [planner]
  stages: [plan]
validation:
  human_review: pending
  geometry_checks: regression_tested
  physics_trials: not_run
  evidence: [tests/test_construction.py]
sources:
  - file: datacache/support_hard_qwen3-8-max-0902_20260914_183535_833102_pair1_with_skills/machine/wzecw1do/objection_wzecw1do_to_3vlmrh9g.txt
    locator: Verified attempts, Brace 14/26/38/15
code_evidence:
  - path: spatial/build.py
    symbol: Machine.check_connection / Machine.connect_blocks
---

# Scope

This is an incident-derived BuildArena tool constraint, not a universal physics
law and not knowledge extracted from the statics textbook.

Four actual failed connection attempts in the September 14, 2026 Hard south
substructure had coincident face centers. For example, block 7 face E and block 8
face F both lay at [0, -6, 0]. Do not treat the agent's larger estimate of invalid
braces as individually verified failures.

# Policy

- Two touching wooden blocks may be valid while a Brace between their touching
  faces has zero length. Check endpoint centers, not just block centers.
- Use actual face labels and the engine's virtual coordinates.
  `Machine.check_connection` reports separation and the minimum of 0.01.
  `Machine.connect_blocks` enforces that same check before adding a connector.
- Do not infer impossibility from a sketch. Replay the candidate, retain the
  specific operation and measured endpoint evidence, then repair pending steps.
- An occupied face is not by itself forbidden for this connector API.
- Choosing another face can change load paths, lever arms and joint behavior.
  Nonzero separation is necessary for this tool, not sufficient proof of
  collision freedom, structural equivalence, stiffness or strength.

# Verification

Offline regression checks the rejected zero-length connection, successful
nonzero connection, sequential execution and repair. Physics performance and
human review remain pending. Only Planner retrieves this skill; downstream
agents receive the shared tool's short result rather than this whole document.
