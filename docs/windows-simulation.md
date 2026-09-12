# WSL to Windows Simulation

Verified on September 11, 2026. Native game automation is integrated with the
WSL construction and simulation commands. This is a current-version engineering
validation, not an exact reproduction of the paper's model/game snapshots.

## Installed Runtime

- WSL repository: `/home/lyh/BuildArena`
- Windows repository: `\\wsl.localhost\Ubuntu\home\lyh\BuildArena`
- Native Python: `C:\Users\a\AppData\Local\BuildArena\venv\Scripts\python.exe`
- Python version: 3.11.8, used only for native game automation.
- Construction and analysis remain in the existing WSL `BuildArena` environment.
- Automation requirements: `simulation/windows-requirements.txt`
- Besiege: `E:\SteamLibrary\steamapps\common\Besiege`, version 1.90-25346.
- Lua Scripting Mod: version 1.2.0, Workshop item `2383785201`, enabled.

The Windows environment is separate from the existing global Python installation.
To reinstall its dependencies from PowerShell:

```powershell
$repo = '\\wsl.localhost\Ubuntu\home\lyh\BuildArena'
$python = "$env:LOCALAPPDATA\BuildArena\venv\Scripts\python.exe"
& $python -m pip install -r "$repo\simulation\windows-requirements.txt"
& $python -m pip check
```

The repository's full Python requirement is still 3.12 or later. The smaller
Windows environment only imports `simulation.operations` and its GUI dependencies;
it is not an installation of the full construction pipeline.

## Game Files

The actual game directories are below `Besiege_Data`, not directly below Besiege:

- `E:\SteamLibrary\steamapps\common\Besiege\Besiege_Data\SavedMachines`
- `E:\SteamLibrary\steamapps\common\Besiege\Besiege_Data\CustomLevels`

Added without overwriting existing saves:

- `SavedMachines\buildarena_smoke_20260911_141711.bsg`
- `CustomLevels\support_soft.blv`
- `CustomLevels\support_medium.blv`
- `CustomLevels\support_hard.blv`

The smoke machine contains one starting block and an embedded Lua position logger.
The `SavedMachines` setting remains a WSL staging directory. Two Windows bridge
settings have been added to the local `.env`; API credentials were not changed.

## Smoke Result

Artifacts are in `datacache/buildarena_smoke_20260911_141711/`:

- `trajectory_raw.csv`: repeated clipboard captures from the Lua log.
- `trajectory.csv`: deduplicated, time-sorted position records.
- `smoke_report.json`: measured results, environment details, and limitations.
- `height_vs_time.png`: height plotted against simulation time.
- `14_trial_stopped.png`: final game screenshot with simulation stopped.
- `probe_trajectory.csv`: separate two-second telemetry preflight.

The main trial recorded 252 positions from 0.04 to 10.08 seconds, at a uniform
0.04-second interval (25 Hz), with no missing intervals. The block fell from a
maximum height of 5.02 to a settled height of 0.45 game units. No model API was
called.

The trial reused `windows_click`, `copy_text`, `save_to_csv`, and
`clean_simulation_csv` from `simulation.operations` in a native Windows process
launched from WSL. Analysis in WSL reused `robust_read_csv`,
`calculate_max_height`, and `calculate_max_speed` from `analyze.sim_common`.

## Desktop Preparation

The user loaded the smoke machine in an empty level-editor scene and opened the
Lua panel with Ctrl+L. This manual setup precedes the automated start, periodic
log copying, stop, and CSV processing.

Recorded geometry, in physical pixels:

- Desktop: 2560 x 1440.
- Game client area: 1920 x 1200, starting at desktop coordinate (320, 134).
- Start/stop button within the client: (40, 42).
- Lua log text within the client: (460, 200).

Translate client coordinates with `win32gui.ClientToScreen` before clicking.
These measurements are not reusable after resizing or moving the relevant UI.
The existing `click_fractional_position` helper instead uses desktop fractions;
its default positions must not be assumed to match this windowed setup.

Only operate while Besiege is visible and focused. Keep its desktop unlocked,
avoid simultaneous manual mouse/keyboard use, and stop the simulation in a
`finally` block. Clear the text clipboard before copying and validate numeric
telemetry before saving it. For screenshots, capture the focused client rectangle:
`ImageGrab.grab(window=hwnd)` returned stale frames with this game.

## Integrated Pipeline

Construction no longer imports Windows GUI dependencies in WSL. All three task
adapters call `simulation.dispatch`, which converts paths using `wslpath` and
launches only `simulation/windows_runner.py` in the native Windows environment.
Geometry generation, task databases, Qwen requests, and analysis stay in WSL.

Local `.env` settings:

```dotenv
BUILD_ARENA_WINDOWS_PYTHON=/mnt/c/Users/a/AppData/Local/BuildArena/venv/Scripts/python.exe
BUILD_ARENA_WINDOWS_PROFILE=/home/lyh/BuildArena/datacache/windows_profile.json
```

The JSON profile contains the Windows SavedMachines and LuaRoot paths, the
1920 x 1200 client size, and calibrated client-relative UI positions. It is
machine-local and intentionally excluded from Git. Keep the Lua panel and log
in their calibrated positions. Either initial Lua visibility is accepted.

For Transport and Lift, enter Barren Expanse and stop physics. For Support,
load the corresponding `support_soft`, `support_medium`, or `support_hard` level.
Support/Lift share the bridge, but have not had a real model sample validated
here. Do not switch scenes, move panels, resize the game, lock the desktop, or
use the mouse/keyboard during automation.

To construct a **new paid sample**, from the repository root:

```bash
conda run --no-capture-output -n BuildArena python -B -m script.run_construction \
  --model qwen-plus --category transport --level soft \
  --n_sample 1 --n_worker 1 --timeout 1800
```

Use the database path printed by construction in the next command:

```bash
conda run --no-capture-output -n BuildArena python -B -m script.run_simulation \
  --db datacache/PROJECT/task_database.db --max-workers 1 --timeout 900
```

Transport follows the existing up-to-three-round control/feedback protocol.
This command makes additional Qwen control calls and operates the Windows game.
Successful simulation stages are analyzed automatically, producing
`datacache/PROJECT_sim/simulation_metrics.json` and per-round JSON files under
`datacache/analysis_simulation/`. A failed benchmark result is still a valid
measurement; it is distinct from an automation failure.

For construction-stage token, turn, and duration metrics, with no API calls:

```bash
conda run -n BuildArena python -B -m analyze.sampling_path_analysis \
  datacache/PROJECT/task_database.db \
  --output datacache/PROJECT/construction_metrics.csv
```

Block counts are stored in the construction database's `machine` table and in
the simulation metrics. Do not treat three feedback rounds as three independent
samples, or discard objected/failed construction attempts from the denominator.

## Validation And Recovery

The full automatic loading preflight is
`datacache/windows_bridge_preflight_20260911_05/`: 125 position rows covering
0.04 through 5.00 seconds, stopped automatically. Earlier preflight directories
preserve UI-calibration failures and are not benchmark samples.

The single Qwen construction run is
`datacache/transport_soft_qwen-plus_20260911_152514/`. It generated two blocks
(one Starting Block, one Powered Wheel), then raised a build objection. It was
not resampled or manually repaired. Its incomplete machine is used to diagnose
the downstream control/physics/analysis loop; it remains a failed task sample.

All three Qwen control/feedback rounds completed through the WSL bridge, with
30 seconds requested per round, automatic BSG loading, physics, CSV return, and
metric generation. All three rounds failed the four-wheel requirement:

| Round | Blocks | Wheels | Max distance | Max speed | Pass |
| --- | --- | --- | --- | --- | --- |
| 1 | 2 | 1 | 47.4306 | 3.0208 | false |
| 2 | 2 | 1 | 15.0517 | 2.7726 | false |
| 3 | 2 | 1 | 14.5402 | 3.1425 | false |

Distance is the repository's maximum horizontal distance from the origin, not
distance traveled toward the target. Round 1 moved in the wrong direction.
These three rounds belong to **one failed sample**, not three samples.

Construction recorded 40,393 input and 17,830 output tokens. The three control
stages recorded another 19,966 input and 3,293 output tokens. Combined:
60,359 input and 21,123 output tokens, 81,482 total. These are stored usage
counts, not a monetary invoice.

Position data starts at 0.32--0.36 seconds and ends at 30.00 seconds. Interior
timestamps are continuous at 0.04-second intervals; the first 7--8 expected
frames per block are missing. A few partially copied position rows had only
three columns; the repository analyzer filtered those out. The bridge parser
has since been tightened to accept three-column auxiliary records only for
IDs whose generated Lua actually emits them. Original trial CSVs are retained.

The native runner verifies the game window, client size, filename readback,
embedded Lua against the loaded LuaRoot file, and telemetry block IDs. It uses
the Lua clock, bounded by a wall-clock timeout, and limits exported rows to the
requested simulation interval. Runtime JSON files record hashes and observed
time ranges; raw telemetry and before/loaded/stopped screenshots are retained.

GUI failures are marked `error` and are not blindly retried. Physics is stopped
in `finally` when the game remains controllable. Missing/changed windows or
unrecognizable UI can still require a manual stop. A black capture aborts input.
Existing telemetry and different game saves with the same name are not replaced.

Before resuming after a GUI error, inspect the database's `error_info` and game
screenshots, fix the scene/profile, and preserve the failed attempt's artifacts.
`--resume` resets failed/interrupted tasks, but deliberately does not reset
GUI `error` tasks. Requeue an inspected task explicitly only after resolving
the cause; do not remove logs or reset failures just to obtain a passing result.

Construction `--timeout` now reaps worker processes. Simulation shutdown allows
an active bounded native run to stop first, so cleanup may extend the scheduler
deadline by up to 120 seconds. Simulation database copying uses SQLite backup
instead of copying the main file without its WAL.
Configuration loading also preserves absolute path roots, so absolute database
paths no longer turn into incorrect paths below the working directory.

## Reproduction Limits

- This used Besiege 1.90-25346, not the paper's 1.75-23370.
- A one-block drop in the level editor is not a Transport, Support, or Lift sample.
- `qwen-plus` is an API alias, not a pinned paper-era model snapshot.
- One sample does not estimate the paper's success rates.
- The controller configuration is now nested under `agents` and inherits the
  selected model; task prompts and scoring thresholds were not rewritten.
- GUI clipboard telemetry can have missing frames. Inspect time gaps in the raw
  and cleaned CSV before treating fine-grained velocity metrics as precise.

Safety regression tests:

```bash
conda run -n BuildArena python -B -m unittest discover -s tests -v
```

Windows focus now requires an exact, visible game-window title. Missing-game
checks stop before sending input or deleting an existing log.
