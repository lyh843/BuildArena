# Support Framework And Experiment Report

Open `index.html` directly in a desktop browser. No server, CDN, API key,
network connection, or JavaScript package install is needed.

## Contents

- `index.html`: generated Chinese report, with embedded data.
- `data.json`: 11 experiment records, stage/task/request metrics and source hashes.
- `assets/`: four original loaded-game screenshots.
- `evidence/`: four scored CSVs and native runtime records.
- `template.html`: editable report layout and explanatory text.
- `build_report.py`: read-only source extraction and report generation.
- `check_report.py`: basic consistency, local-link and JavaScript syntax checks.
- `../excluded_records.json`: explicitly invalidated samples; always excluded.

Source-code, database, and original-experiment links expect this directory to
remain under the repository's `report/`. Embedded tables, charts, screenshots,
and copied telemetry remain available when this report directory is moved.

## Rebuild

Run from the repository root:

```bash
/home/lyh/miniconda3/envs/BuildArena/bin/python -B report/support-20260915_193834/build_report.py
/home/lyh/miniconda3/envs/BuildArena/bin/python -B report/support-20260915_193834/check_report.py
```

No construction or simulation is performed. Failed construction states are
preserved. Database usage and traced request usage are separate accounting
views, never added together. Interrupted or unreturned usage remains unknown.
The September 11 Support Soft sample is invalidated by the user and excluded.
Desktop layout only; no mobile or extensive browser test suite.
