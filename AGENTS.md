# Development guidance

## Product goal

Help people discover useful things to print, customize models, prepare settings for their exact printer and filament, and learn from recorded outcomes. The current release is a local web app with three fixed CAD templates. Read README.md and docs/STATUS.md before expanding its capabilities.

## Architecture

- `print_agent/app.py`: FastAPI routes, local session and request boundary.
- `schemas.py`, `planner.py`: typed geometry parameters and rules/optional LLM planning.
- `geometry.py`: deterministic CadQuery solids, mesh preview, exports and reproduction source.
- `profiles.py`: supplied evidence, exact scope matching and calibration review.
- `slicer.py`: local Bambu Studio CLI preparation, execution and output verification.
- `offers.py`, `storage.py`: user-entered offer calculation and per-job artifacts/history.
- `static/`: dependency-free Korean UI and Canvas mesh viewer.

Keep web UI operations and tool implementations separate. A future hosted website should use a local companion for CAD/native applications; the current loopback server is not a hosted multi-user service.

## Verification

Use Python 3.12 for the supported development path. Run behavior tests relevant to a change, and the full required CI gates before merging.

```bash
python -m pip install -r requirements.txt
python -m unittest discover -v
node --check print_agent/static/app.js
node tests/test_ui_state.cjs
```

Browser test instructions and CI are in CONTRIBUTING.md and `.github/workflows/ci.yml`. Test fixtures must not require a paid LLM, a Bambu account, real printer credentials or physical printing. Live/native validation must be reported separately from fixture tests.

When a test cannot run, record its concrete blocker. A successful HTTP response, generated CAD file, sliced file, printer connection and physical print are separate states. Do not claim a later state from evidence of an earlier one.

## Implementation invariants

- Never execute arbitrary code or shell commands returned by an LLM. Accept typed, supported tool parameters.
- Preserve source identity and measured/user-reported validation as separate facts. Missing settings, shipping or hardware capabilities remain unknown.
- Do not flatten an inherited profile by deleting `inherits`; resolve its complete configuration with per-field evidence before supporting it.
- Keep generation artifacts and source files reproducible. Never overwrite the user's imported source model.
- A changed draft must not keep an old preview/download looking current. A failed new slice must not retain the old slice as the current result.
- Keep provider keys in local environment variables; do not return them to the browser, commit them, or include them in issue logs.
- New model sources require recorded origin and applicable reuse terms. Do not imply a supported external API without verifying it.

## Repository workflow

Respect existing user changes and branch rules. Keep commits focused, explain behavior and evidence, and update the changelog/status when the public capability changes. Avoid generated caches, runtime databases and personal project settings in commits. Sample CAD files are intentional versioned artifacts; their manifests record hashes.

LICENSE applies to this project's code and original examples. Dependencies and externally acquired models retain their own terms.
