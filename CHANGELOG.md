# Changelog

## 0.10.0 — 2026-11-16

- Material setup starts with the profile and the printer/material conditions; saving the workspace moves below them. A short guide explains exporting a preset bundle from Bambu Studio (menu names may vary by version). After a printer status read, the setup card offers to fill the printer model and nozzle diameter and to choose an AMS slot's filament identifier, filling empty fields only and asking the user to confirm against the installed hardware.

- Purchase comparison prices the current model: the printability material item carries numeric `grams` (solid-PLA upper bound), the offers view states the current model's grams, and the comparison adds a material-cost upper-bound column per product (shipping-excluded values are labelled) with a note that real usage comes from the slicer. The model card's material line links to the comparison.

- Request parsing for everyday phrases: two-number sizes (“30x20cm”, each number may carry its own unit) are no longer ignored silently; inner sizes are flagged as used for the outside; “케이블 3개” sets the slot count; a stand's bare “두께” is the device thickness; round photo sizes (“10cm 원형”, “지름 50mm”) set the pocket and grow an unspecified frame to fit. Pen holders, business-card holders, earphone trays, photo frames and tablet stands start from announced sizes; monitor and laptop stands are declined because they carry load. Default notes list Korean field names on one line.

- History items carry a display-only `summary` (template's distinguishing dimensions, printability status, slice state) so same-title jobs can be told apart; the list shows those facts, a short outcome note and filters for success, failure and unrecorded results over the loaded pages, stating how many of the loaded records match.
- A healthy connection with nothing to recover collapses to one line; problems keep the full explanation.
- When the printer status view has read a finish or failure report, the result card shows it as a hint for the user's own record and never selects a result.

- Journey bar on the model screen: four steps (dimensions, make and check, print preparation, recorded result) with each step's state and one next action that jumps to the right section. It is sticky on desktop and a 2×2 grid on mobile; it resets when inputs change. A printability warning is shown but no longer blocks the next action once the user moves on. Downloading the 3MF marks preparation as “downloaded”, never as printed.
- “가장 쉬운 출력 방법” guide in the result card: download the 3MF, open it in Bambu Studio, slice and send there, then record the result here. Studio project preparation stays optional.

- New `phone_stand` template: base, front lip and a back plate leaning 50–80° from horizontal, with a slot of device thickness plus clearance. Rule and LLM planning, Korean requests (“휴대폰 거치대”, “각도 70도”, “폰 두께”, “앞턱 높이”), degree-unit contextual edits and a desk starting project. Planning grows an unspecified depth so the back stays over the base and asks for the minimum when the user's depth is too short.
- The three new fields appear in canonical parameters only for the phone stand (`schemas.LATER_FIELDS`), so existing jobs, starting-project recipes and contextual-edit hashes keep their exact eleven-field shape.
- Preview: isometric/front/side/top view presets, orange bounding-box dimension lines (hidden for axes facing the viewer), depth-tested crease edges, camera-relative lighting and optional overhang highlighting. The preview stage no longer overflows its card, so the zoom toolbar is no longer clipped.
- Printability review on every generated model, stored with the job result: thinnest template feature against a stated 0.4 mm nozzle / 0.42 mm line, flat bed contact ratio, height-to-footprint ratio, >45° overhang area, fit clearance (cable comb and frame only) and a solid-PLA material upper bound. Warnings name the parameter to change and offer a jump-to-field action.
- Recheck a saved job for a 0.2/0.4/0.6/0.8 mm nozzle (`POST /api/jobs/{id}/printability`) without changing the stored job; offer the nozzle reported by the printer status view as an explicit one-click choice, and an explicit check for jobs saved before v0.10.
- After regenerating with new dimensions, show the previous model as an optional, labelled dashed outline in the same view.
- Advisory only: generation is never blocked and no slicer or physical result is implied. Installed-package qualification adds one printability check per template.

## 0.9.0 — 2026-11-16

- Add a read-only **printer status** view: discover Bambu printers announcing on the local network (SSDP) and read one printer's reported state over LAN-mode MQTT/TLS with its access code.
- Report connection stages separately (`unreachable`, `tls_failed`, `certificate_changed`, `access_rejected`, `subscribe_rejected`, `no_report`, `protocol_error`, `reporting`) and keep printer-reported print state, progress, layers, temperatures, nozzle, error/HMS codes, AMS slot materials and firmware distinct from measured outcomes. Missing fields stay unknown.
- Publish only two fixed requests (`pushall`, `get_version`); no print, motion, temperature or file command can be constructed. Accept private, link-local and loopback IP literals only, one reader at a time and at most one read per printer every 5 s.
- Show the device certificate fingerprint (issuer not verified) and pin it per host/serial for the page session; a different certificate stops before the access code is sent. Access codes are never stored, logged or returned, including in validation errors.
- Implement the bounded MQTT 3.1.1 subset with the standard library (no new dependency). Fixture tests use a loopback fake TLS broker with test-only certificates; installed-package qualification adds two printer-status checks. Physical printer connection remains separately qualified.

## 0.8.0 — 2026-11-15

- Review the actual generated CAD envelope against recorded printer volume before Studio composition and the application's full-config preparation. Reject height overflow and unresolved placement without staging or native execution.
- Recognize strict rectangular beds and rectangular exclusions; check 0°/90° bounding-box placements without resizing, moving or rotating the original model. Unsupported and diagonal-only possibilities remain reviewable rather than being described as impossible.
- Bind reports to model/settings hashes, rederive before execution, preserve them in history and full workspace backup, and require installed lifecycle evidence before release promotion.
- Show a Korean dimensions comparison and return-to-edit action; distinguish historical comparisons and clear stale reports/downloads when inputs change. Noninteractive toast messages no longer intercept pointer actions.
- Preserve the canonical v0.7 source inspection and revision records while enriching response-only volume summaries. Keep near-boundary dimensions distinct in the comparison table.
- Keep previous prepared downloads readable. Old execution plans need fresh preparation under the new review rules. Actual hardware, toolpath structures and physical printing remain separately qualified.


## 0.5.0 — 2026-11-15

- Edit six supported Studio project filament settings with original values, units, pinned format bounds, explicit difference review and separate application to the current CAD.
- Preserve the original project and every untouched setting; record immutable user-selected revisions with original, review and effective-setting identities. Numeric no-ops preserve the original representation and do not publish empty revisions.
- Reconstruct each effective configuration from its original and recorded proposal at read, preparation and native execution boundaries. Keep original and edited receipts distinct and compare the complete effective configuration after native slicing.
- Preserve exact invalid drafts, ignore obsolete asynchronous responses, require a choice before replacing active edits, and reopen edited history through its recorded revision without reverting silently to original settings.
- Carry original, revision, current CAD and prepared artifacts through actual restart and whole-workspace restoration; freshly prepare in the restored directory without reusing old paths.
- Extend installed-package qualification on all three desktop platforms and retain the three previous native cases with a fourth six-edit case. Actual observed qualification and release publication are recorded separately in `docs/VERIFICATION.md`.

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
