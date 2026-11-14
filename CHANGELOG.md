# Changelog

## 0.4.0 — 2026-11-14

- Import a single supported Bambu Studio project, show its recorded printer/nozzle/material/plate/process, and explicitly apply its global settings to the current app-generated CAD.
- Bound and verify the complete source archive, preserve exact settings bytes and original-source receipts, and generate a deterministic derivative with separate source/modifier/model provenance.
- Provide a verified prepared-project download without requiring Studio. Keep preparation, actual native slicing and physical printing separate in the API, job artifacts and UI.
- Add an independently staged direct-project native path, exact runtime/version checks, source/CAD/receipt/argv revalidation and full-setting roundtrip differences alongside core readback.
- Preserve candidate/applied/manual inputs through failed imports, cancellation, stale responses, reconnects and history. Require source revalidation and fresh preparation before replaying a recorded job.
- Extend installed-wheel qualification through project import/preparation/download/history and exact source/prepared backup restoration on each desktop OS; retain the existing native smoke cases and add a separate actual project-source case.
- Route explicit material and purchase requests to the existing workflows in both template and LLM modes without a provider call.

## 0.3.0 — 2026-11-14

- Add offline `backup`, `backup-info` and `restore` commands for complete saved CAD and filament workspaces, including original records, private receipts, exact unfinished drafts and partial files.
- Stream a bounded versioned archive, verify every payload hash and actual ZIP layout, hold the data-directory lease during capture, and publish complete backups/restores without replacing existing files or folders.
- Refuse unknown SQLite schemas and corrupt canonical workspace stores before production startup mutates either store; retain the established preservation/rebuild path for a corrupt derived history index.
- Extend the installed-wheel qualification through live-owner refusal, exact backup/restore byte comparison, rejection of corrupt archives and existing destinations, and restored HTTP operation with verified downloads on all three desktop OS jobs.
- Protect unsaved purchase inputs and active comparisons on page exit. Keep existing pending-form locking and ignore superseded success/error responses using the exact captured input state.
- Add a minimal-permission release workflow that verifies all three successful current-main workflows and promotes their exact qualified wheel and evidence without rebuilding or replacing published versions. Actual publication and platform results are recorded in `docs/VERIFICATION.md`.
- Document Ubuntu system-library preparation, complete-workspace backup limits, new-folder restore and update/rollback procedures; link the guide from the UI storage details.

## 0.2.0 — 2026-11-14

- Hold an exclusive operating-system lease for each running app's data directory; reject a second writer before opening stores or attempting recovery.
- Use a stable per-user data location for new installations, retain recognizable legacy `./data` without moving it, and show the selected absolute path in the UI and diagnostics.
- Reconcile job files into the history index at startup, mark interrupted generation/slicing explicitly, preserve typed generation requests and damaged source records, and never expose partial files as validated downloads.
- Verify artifact sizes and SHA-256 receipts before downloading; serve and bundle the same verified bytes, including sliced output, while retaining a documented legacy-receipt compatibility path.
- Reconnect to a restarted local server without reloading the page or replaying a mutation. Protect unfinished model/slicer/outcome work on page exit and before history/template/reset replacement.
- Page through older history with deterministic cursors, retain the last loaded list on failure and ignore superseded responses.
- Reject occupied CAD/slicer requests before queueing or reserving another job. Clear a previous slice when a new attempt begins, including failed or interrupted preparation.
- Stream optional model-provider responses within a bounded byte budget and total deadline; do not read upstream error bodies or expose credentials.
- Make `doctor` report required dependency/assets/storage failures as structured diagnostics with a nonzero exit code, while keeping unconfigured optional integrations nonblocking.
- Add installed-wheel qualification for Linux, macOS and Windows with actual CAD/STEP/3MF read-back, HTTP/downloads, directory ownership and restart persistence. Workflow definitions are not results; observed runs are recorded separately in `docs/VERIFICATION.md`.

### Earlier additions included in 0.2.0

- Discover six original starting projects by purpose and optional placement-space dimensions, with measurement guidance and explicit horizontal-rotation results.
- Prepare a selected project's editable dimensions without generating CAD automatically; preserve unfinished drafts while browsing and require an explicit choice before replacing them.
- Record server-resolved recipe identity, original parameters and actual customizations in generated jobs, manifests and bundles; reject stale or spoofed source selections before job creation.
- Keep recommendation responses separate from current model state; discard obsolete responses and retain existing work through invalid input, failed requests and reconnects.
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
