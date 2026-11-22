# Development guidance

## Product goal

Help people discover useful things to print, customize models, prepare settings for their exact printer and filament, and learn from recorded outcomes. The current release is a local web app with eight fixed CAD templates, including a system-font name tag, a Cherry MX-compatible keycap and a round cup with an optional drain hole. `text` is the only non-numeric parameter (`schemas.TEXT_FIELDS`). Fields added after the original eleven appear in canonical parameters only for templates that use them (`schemas.LATER_FIELDS`), so earlier jobs, recipes and review hashes keep their exact shape. Read README.md and docs/STATUS.md before expanding its capabilities.

## Architecture

- `print_agent/app.py`: FastAPI routes, local session and request boundary.
- `schemas.py`, `planner.py`: typed geometry parameters and rules/optional LLM planning.
- `model_edits.py`, `geometry_rules.py`: contextual parameter edits, canonical review records and shared pure geometry constraints.
- `geometry.py`: deterministic CadQuery solids, mesh preview, exports and reproduction source.
- `printer_beds.py`: build-plate sizes with sources for the preview's plate view (visual reference; slicer settings stay the authority).
- `printability.py`: advisory pure-geometry printability review (reference 0.4 mm nozzle) stored with each generated result; never blocks generation.
- `model_import.py`, `imports.py`: imported STL/3MF meshes (bounded parsing, mesh facts, ranked placements, oriented 3MF) and their unchanged, hash-verified originals.
- `print_volume.py`: bounded recorded build-volume comparison; generated CAD identity and preparation gates stay in the existing parser/adapter boundaries.
- `profiles.py`: supplied evidence, exact scope matching and calibration review.
- `preset_library.py`: explicit single-parent values, per-field evidence and original-baseline comparison.
- `workspaces.py`: atomic saved filament inputs, exact drafts and revision conflicts, separate from CAD jobs.
- `inventory.py`: filament spools the person enters, weigh-ins and deducted prints (one JSON file per spool with revisions).
- `glossary.py`: validated plain-language glossary and the five-step first-run guide, sent with bootstrap.
- `slice_compare.py`: four process-only variants of a supplied bundle and the estimates read from their verified slices.
- `slicer.py`: local Bambu Studio CLI preparation, execution and output verification.
- `studio_project.py`, `studio_sources.py`: bounded project inspection/composition and immutable verified originals.
- `studio_workspaces.py`: named Studio input references, exact drafts, bounded recorded-metadata catalogs and revision conflicts.
- `studio_settings.py`, `studio_revisions.py`: six-field proposals, immutable user-selected revisions and original-based rederivation.
- `printer_lan.py`: read-only Bambu LAN discovery and status (fixed `pushall`/`get_version` requests only, private IP literals, session certificate pin, access codes never stored or returned).
- `printer_moonraker.py`: read-only Klipper status through Moonraker (four fixed `GET` requests, private IP literals, optional API key never stored or returned); Snapmaker U1, Voron and other Klipper printers.
- `offers.py`, `storage.py`: user-entered offer calculation and per-job artifacts/history.
- `static/`: dependency-free Korean UI and Canvas mesh viewer.

Keep web UI operations and tool implementations separate. A future hosted website should use a local companion for CAD/native applications; the current loopback server is not a hosted multi-user service.

## Verification

Use Python 3.12 for the supported development path and Node.js 22 or newer for the full development suite, including Python tests of JavaScript JSON round trips. Run behavior tests relevant to a change, and the full required CI gates before merging.

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
- Contextual model edits preserve every unspecified parameter and project origin. Apply only a reviewed current-scope selection; rederive it and recheck any parent artifact identity before reserving CAD. Retain unsaved outcome notes with the original job/storage identity whenever replacing a job.
- Saved filament workspaces restore inputs, not current reviews. Preserve imported originals and invalid draft text; stale revision writes must not overwrite another tab's saved changes.
- Keep provider keys in local environment variables; do not return them to the browser, commit them, or include them in issue logs.
- New model sources require recorded origin and applicable reuse terms. Do not imply a supported external API without verifying it.

## Repository workflow

Respect existing user changes and branch rules. Keep commits focused, explain behavior and evidence, and update the changelog/status when the public capability changes. Avoid generated caches, runtime databases and personal project settings in commits. Sample CAD files are intentional versioned artifacts; their manifests record hashes.

LICENSE applies to this project's code and original examples. Dependencies and externally acquired models retain their own terms.
