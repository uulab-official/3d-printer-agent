# Changelog

## 0.19.0 — 2026-11-17

- After a failed print ([docs/RECOVERY.md](docs/RECOVERY.md)): “출력 실패” now takes up to six reasons (first layer, warping, stringing, too tight, too loose, weak, blurry letters, under-extrusion, mid-print failure), stored with the user-reported outcome. `GET /api/jobs/{id}/recovery` returns general next steps per reason and, where geometry can help, an edit sentence (for example “여유 0.2mm 늘려줘”, “글자 크기 2mm 늘려줘”) that is offered only when the existing edit parser turns it into a valid in-range edit of the current model. “모델 수정 검토” fills the contextual edit and opens its review; nothing changes until the person applies it and regenerates. Reasons are refused for success/not-tested outcomes; older records open unchanged.
- Review fixes for 0.17–0.18: print progress is re-read every five minutes instead of 30 seconds and without the version query (`include_version: false`), with a “지금 다시 읽기” button, because P1/A1 integrations warn against frequent full-state pushes; following ends on any finish/failure/idle report even when the printer does not repeat the job name; a stop no longer waits behind a pending pause/resume (they use a separate lock and the stop button stays enabled); retained unsaved outcome drafts keep their failure reasons; recovery edits always use the rule engine, never an external model; remembered printers are named by the entered host and serial, with the printer-reported product name only as a hint.

## 0.18.0 — 2026-11-17

- Pause, resume and stop a running print from the progress panel. Buttons follow the printer's reported state (pause while running, resume while paused, stop while preparing, running or paused); stop asks for a second confirmation. `POST /api/printers/print/control` builds only these three commands, requires the previously pinned certificate, the printer state in which the command applies and `stop_confirmed` for a stop, then waits up to 15 seconds for the printer to report the new state. Commands sent for the current job are recorded on it without the access code. Verified against the synthetic printer in a real browser; not on a physical printer.

## 0.17.0 — 2026-11-17

- Remember a printer: after a successful status read with “이 브라우저에 프린터 기억하기” ticked, the browser keeps the host, serial, reported product name and certificate fingerprint (never the access code). On the next visit the most recent printer is filled in and its fingerprint stays pinned, so a different device answering at that address is stopped before the code is sent. Saved printers can be chosen or deleted; clearing the pin also clears the remembered one. Storage failures leave the app working.
- Follow a started print: after a send reports `started`, the card re-reads the printer every 30 seconds and shows its reported state, progress, remaining time and layer, stopping on the printer's own finish/failure/idle report for that job, when the printer inputs change, after 12 hours or on request. A reported finish asks the person to check the print and record the outcome; it is not a measured result.

## 0.16.0 — 2026-11-17

- Where to buy ([docs/STORES.md](docs/STORES.md)): the purchase view opens with a dated directory of 28 Korean filament stores whose operation was confirmed on 2026-11-17 (own site, Naver store directory or current Naver Shopping listings), filterable by material, “Bambu 정품”, official store/importer, own brand or multi-brand reseller, and by name (Korean brand aliases such as 뱀부). It includes the official Bambu Lab Korea store and Bambu's Korean dealers found by search. 6 listed stores without current evidence are kept in a separate “운영을 확인하지 못한 곳” group, and 퓨어필라 is excluded (its domain is no longer registered). Prices and stock are never stored; links open the store in a new tab with `noopener noreferrer`; seller claims are labelled as claims. Not advertising.

## 0.15.0 — 2026-11-17

- Send to printer ([docs/PRINT_SEND.md](docs/PRINT_SEND.md)): a job's verified, single-plate sliced 3MF can be uploaded to a Bambu printer over implicit FTPS (990) and started with the MQTT `project_file` command. `POST /api/printers/print/review` reads the printer once (idle/finished state, reported nozzle vs sliced nozzle, filament-to-AMS-slot or external-spool choice) and returns a single-use, 3-minute token bound to the job, file hash, printer and certificate; `POST /api/printers/print/start` needs that token, the access code and an explicit bed-clear confirmation, re-checks the file, certificate and printer state, uploads and size-checks the file, sends the command and waits for the printer's own start report. Stages (ready, uploaded, command sent, printer reported start) are returned separately and recorded on the job without the access code. Requires LAN-only and Developer Mode on current firmware.
- New `printer_send.py` keeps the start command out of the read-only status module; `scripts/fake_bambu_printer.py --ftps-port` adds a synthetic implicit-FTPS upload and start/reject handling. `PPA_PRINTER_FTPS_PORT` exists only for that local synthetic check.
- Model view: a 프린터로 보내기 card appears once the current model has a verified slice, with slot selectors, a review summary, a bed-clear confirmation and the stage results.
- Verified locally end to end against the synthetic printer with a keychain sliced by the installed Studio 02.09.01.70 on macOS; not yet verified on a physical printer.

## 0.14.0 — 2026-11-17

- Model colours ([docs/COLORS.md](docs/COLORS.md)): every template takes an optional filament colour (`color`) and a name tag also takes a letter colour (`accent_color`), from eleven named colours. Requests and edits read Korean and whole-word English colour names (“빨간 글자로 "지우" 키링, 판은 흰색”, “글자를 파랑으로 바꿔줘”); conflicting colours ask, and letter colours on other templates are refused. The parameter panel has a colour group with swatches, copy/paste carries colours, and the preview paints the chosen colours with a legend. Unchosen colours are omitted from canonical parameters, so earlier jobs, recipes and hashes keep their shape.
- A name tag whose letters differ in colour also gets `model-colors.3mf`: the plate (filament 1) and the letters (filament 2), split at the plate top with a volume check, as parts of one object in Bambu Studio's part/filament format. Sliced locally with Studio 02.09.01.70 and two filaments, layers 1–10 used filament 1 and 11–20 filament 2 with one filament change.
- Natural-language edits now also change the name-tag text (“이름을 지우로 바꿔줘”), letter size/height, hole diameter, border and plate thickness, and combine them (“글자를 "Mia"로 바꾸고 글자 크기 15mm”).
- Fix: an edited name tag could not be regenerated (the edit check required width, depth and height, which a name tag does not use), and the browser rejected every text edit because it accepted only numeric operations.

## 0.13.0 — 2026-11-17

- Owner-friendly launch: `printer-agent` opens the app in the default browser once the server answers (only when started from a terminal; `--no-browser` or `PPA_NO_BROWSER=1` turns it off, and CI/services never get a window). Starting it again while it runs prints the running address (and opens it) instead of a bind error. A port held by another program prints a Korean message with the next port; a data folder used by another running copy fails before the server starts with the app's message instead of a traceback.
- README “시작하기” starts with installing the latest release wheel; the stale v0.8.0 numbers are removed.
- The Studio CLI check (`doctor --probe-slicer`, “설치된 슬라이서 확인” and the check before each slice) runs `--help` in a temporary folder. The macOS Studio CLI writes a `result.json` receipt into its working directory even for `--help`, so the check used to leave that file in whatever folder the app was started from. A stray copy committed at the repository root in 0.12.1 is removed (it was never in the wheel) and `/result.json` is ignored.

## 0.12.1 — 2026-11-17

- Fix Studio-project slicing on macOS: the project command now always passes `--outputdir` (the job folder). Without it the macOS Studio CLI wrote the sliced 3MF into its own app bundle (`BambuStudio.app/Contents/Resources`) and the app reported a missing output. Linux behaviour is unchanged (the job folder was already the working directory). The project path now also requires `--outputdir` in the CLI help.
- `scripts/qualify_bambu.py --studio-executable PATH` runs the same four native cases with an already installed Studio of the pinned version (for example on macOS) instead of downloading the Linux AppImage; the bootstrap run keeps Studio program settings in an isolated `--datadir`. Observed on macOS 27 (arm64) with Studio 02.09.01.70: all four cases passed.
- The name keychain card no longer shows “undefined × undefined × undefined mm”; it shows the default text and letter size. The “기본값을 쓴 치수” note uses each template's panel labels (테두리 여백·받침 두께 for the keychain, 등판·앞턱 두께·홈 여유 for the phone stand).

## 0.12.0 — 2026-11-16

- New `name_tag` template (이름 키링): raised text of 1–20 letters (Hangul, Latin, digits, spaces and a few marks) on a rounded plate with a ring-hole tab, always one solid. Width and depth follow the text; height is base plus letter height. Letters use a pinned bold sans system font per platform (Arial Bold on macOS/Windows, DejaVu Sans Bold on Linux, else the Arial-named fallback); the result names the font and says another computer may draw slightly different letters. Invalid letter outlines (some decorative fonts overlap their strokes) fail with a clear reason instead of producing an open mesh. Requests such as “이름이 민수인 키링”, “"Samantha" 키링” and “서연이라고 적힌 키링” set the text; letter size, height, plate thickness, border and hole size are editable and copy/paste as text. Contextual edits set a new text string. Printability estimates the letter stroke at about 10% of the letter height.
- `text` is the first non-numeric parameter (`schemas.TEXT_FIELDS`); like the other later fields it appears only in this template's canonical parameters, so earlier jobs and hashes keep their shape.
- Fix a mirrored model preview: the projection now places the camera on the −Y side (CAD front), so the top view shows +Y up and text reads normally. Symmetric templates hid this before.
- Installed-package qualification creates a name tag on each platform and compares STEP and 3MF sizes with the job's reported size.

## 0.11.0 — 2026-11-16

- Reconnect no longer stays “연결 확인 중” while the saved filament and Studio lists load after a successful bootstrap. A list request cut off by a server restart had kept the reconnect control disabled; this caused the intermittent CI failure in the restart-recovery browser case.
- MakerWorld-style parameter panel: the current template's dimensions are grouped into size, thickness and shape; each field has a one-line explanation, -/+ steppers with a per-field step clamped to the allowed range, and a synced slider. Existing number inputs keep their ids and behaviour.
- Copy and paste settings: “설정 복사” copies the template and dimensions as a small JSON document (falling back to a selected text box when the clipboard is refused); “붙여넣기” validates the format, template, fields, ranges and integer counts and applies through the existing replacement confirmation.

## 0.10.0 — 2026-11-16

- Production-readiness review fixes: laptop/monitor stands are declined and stands for other objects (headphones, cameras) ask instead of becoming phone stands; counts after `x` (“2x3칸”, “6mm x 5개”) are not read as sizes; template words win over everyday item names; “등판 두께” is the wall. Printability reports only thicknesses the solid actually has (no constraint-only “outer wall” for the comb and frame), skips degenerate triangles, and a review failure no longer blocks a valid model. History and the journey no longer call a blocked or failed slice “prepared”; only a prepared project or a successful slice counts. The comparison's model-cost column follows the current model, the previous-model outline compares only the same template and is cleared with storage changes, and only 3MF links mark the preparation step as downloaded. New UI colours meet WCAG AA contrast. SECURITY.md documents the printer LAN boundary.

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
