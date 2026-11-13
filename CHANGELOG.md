# Changelog

## Unreleased — 2026-11-13

- Edit a selected filament profile's supplied applicability and source in a guided form, separately from the current-use setup, without hand-writing an envelope.
- Apply numeric and evidence edits together; preserve raw originals, unknown fields, value representations, inheritance and archive origins through cancel/save/reopen.
- Report selected-target scope/source/validation changes separately from effective settings; invalidate positive claims for changed scope or validation while keeping source-only corrections distinct.
- Import Studio `.bbsflmt`, `.bbscfg` and preset `.zip` archives directly into filament workspaces, reporting excluded printer/process entries and retaining original settings.
- Preserve archive/member byte identity separately from profile settings through editing, save/reopen, baseline comparison and evidence reports.
- Make collection imports atomic: retain pasted profiles and unfinished drafts, skip identical originals, reject conflicting names, and ignore stale import responses.
- Assemble native machine/process/filament JSON files with an explicit plate choice; preserve source objects, manual input, and staged-change invalidation.
- Add an authenticated, explicit installed-slicer probe and `doctor --probe-slicer`, keeping ordinary discovery free of native execution.
- Correct native export filenames, preset metadata/JSON representations and setting-ID expectations; bind plate temperatures and read-back to the selected native plate.
- Require the supported native root machine classification and an exact process compatibility entry; explain unsupported user-machine lineage before launching Studio.
- Revalidate staged configuration and expected values before execution; record the observed Studio version and verified archive SHA-256.
- Bound native project-setting JSON depth, block unreadable input metadata and report malformed output as needing review; reject unsupported zero temperatures on the selected plate while retaining unselected values.
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
