# Changelog

## Unreleased — 2026-11-13

- Save and reopen named filament workspaces with imported originals, exact unfinished drafts, selected target and setup; revision checks prevent cross-tab overwrites.
- Edit common nozzle/flow/volumetric/plate settings while retaining inheritance and value representation; remove individual documents or restore imported originals.
- Compare effective settings with the original chain and invalidate positive validation claims after inherited edits or an unavailable baseline, retaining the source evidence.
- Import related filament JSON files, select and edit a target, and add missing parents without losing the collection.
- Resolve supported explicit single-parent inheritance with exact names, preserved documents, canonical JSON hashes and per-field assignment history.
- Review the result against the supplied setup and download the evidence report; changed inputs invalidate prior results and late responses.
- Report missing parents, duplicates, cycles and unsupported include/variant/nil constructs without inventing settings or claiming a full Studio configuration.

## 0.1.0 — 2026-11-12

Initial open-source development release.

- Local Korean web UI and typed API for three parametric CAD templates.
- Actual STL, STEP, 3MF and reproduction-source exports with geometry checks and manifests.
- Exact-scope filament profile review, calibration-change review and unknown/missing evidence states.
- Bambu Studio discovery and CLI adapter with output validation; native printer integration remains unqualified.
- Optional OpenAI-compatible planner adapter and API-key-free template mode.
- User-entered delivered-price comparison, local job history and separate user-reported outcomes.
- MIT license, contribution/report templates and automated unit, packaging and browser checks.

This release does not provide free-form CAD editing, MakerWorld search/remixing, live shopping data or physical printer control. See docs/STATUS.md for observed validation and the next development priorities.
