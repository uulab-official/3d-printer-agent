# Studio Project Settings Implementation Plan

> **For agentic workers:** Use subagent-driven implementation and independent reviews with disjoint file ownership. Root integrates, observes actual CI and publishes. Continued implementation and main delivery are already authorized.

**Goal:** Ship v0.4.0 with a single Studio-project import that prepares the current CAD with recorded global settings and supports a separately verified native slice.

**Architecture:** A bounded pure parser/composer feeds immutable source storage. The existing job lifecycle gains a distinct prepared-project artifact and a separate project-native plan. The Korean UI manages candidate, applied source, preparation and native result independently.

**Tech Stack:** Python 3.12 stdlib/FastAPI/CadQuery, dependency-free JavaScript, Playwright and existing GitHub qualification/release workflows.

**Spec:** [studio-project-design](../specs/2026-11-14-studio-project-design.md).

## Global Constraints

- Baseline `9ded114ea401deee47d4e6c2096ae55d9f05a18e`; target 0.4.0. Existing saved jobs, filament workspaces, backup format and bundle API remain compatible.
- Project budgets: 16 MiB compressed, 128 MiB expanded, 4,096 entries, 2 MiB settings JSON, 2 MiB root XML, 24 MiB whole import request. Existing endpoints keep their budgets.
- Initial native version `02.09.01.70`, FFF, one filament/nozzle/active extruder. Preserve exact global settings bytes. Unsupported valid inputs return actionable inspection results; malformed inputs publish nothing.
- Never copy source geometry, object/plate overrides, painting, cached G-code or per-height scripts into current CAD. Never execute host post-processing or caller-supplied commands/paths. Do not relabel project JSON into role configs.
- Original archives and records remain immutable and verified; a prepared project is separate from a sliced artifact and a physical print. Prepared-project download does not require installed Studio.
- Native construction/marker behavior must pass the isolated experiment and final production-path CI; record the actual marker decision. Local native/Chromium restrictions are not retried or escalated.
- File ownership is exclusive below. Do not commit or push from worker tasks; root publishes reviewed snapshots with expected-head protection. Read-only reviews do not modify implementation files.

## Review Focus

- Forged ZIP lengths/CRC, duplicate JSON and XML entities must not hide unverified settings or exceed budgets: Task 1.
- An incomplete/changed immutable source, existing import destination or missing legacy receipt must not become a valid prepared download: Task 3.
- Changed plan/source/model bytes or mismatched runtime version must prevent native execution; no previous slice stays current: Tasks 2 and 3.
- A late import/prepare success or error after cancellation, model replacement or reconnect must not overwrite current work: Task 4.
- Source-template geometry must never appear in a result claimed to be current CAD; native setting normalization must be reported rather than assumed absent: Tasks 1, 2 and 5.

## Task 0: Native compatibility experiment

Isolated worktree: `/workspace/scratch/d9925436ef0d/3d-printer-agent-project-spike`, branch `qualification/studio-project-20261114`. Only its workflow and qualification script change. Product main stays at the baseline until reviewed implementation.

- [x] Read pinned official CLI/3MF loader and actual retained native output; distinguish project JSON from full role configs.
- [x] Verify clean baseline: 406 Python tests passed.
- [x] Construct two diagnostic derivatives from a native-produced cube source and committed cable-comb CAD: honest new Application versus retained original source Application plus explicit modifier/origin.
- [x] Run both in actual native CI, saving failures as well as successes, 30 core setting comparisons, all-setting differences, original/new mesh topology and dimensions, and G-code evidence.
- [x] Record the qualified format decision below before freezing production composition. Keep the experiment separate from the production native gate.

## Task 1: Bounded inspection and deterministic project composition

**Owner/files:** worker; new `print_agent/studio_project.py`, `tests/test_studio_project.py`, shared `tests/studio_project_fixtures.py` and optional clearly attributed fixture JSON under `tests/fixtures/`.

**Interfaces:**
- `inspect_studio_project(filename: str, content: bytes) -> dict` returns the exact snapshot contract in the spec.
- `build_project_3mf(model_bytes: bytes, snapshot: dict) -> tuple[bytes, dict]` returns deterministic derived bytes and receipt. Receipt includes schema version, source archive/settings hashes, source producer metadata, generated model SHA, derived project SHA/bytes, modifier and geometry preservation facts.
- Export input/qualification constants for reuse; import no web/CAD/native runtime and execute nothing.
- `tests.studio_project_fixtures.project_bytes(...) -> bytes` is a synthetic fixture helper for API/browser tests, not evidence of an authentic GUI export. Fixture overrides support malformed, unsupported and changed-source cases.

- [x] Write failing behavior tests for valid single-material inspection without Studio, unsupported version/multiple materials/nozzles, exact settings byte preservation, original/current geometry separation and deterministic output.
- [x] Add focused refusal tests for actual ZIP budgets/CRC/local inventory, unsafe names/types, duplicate JSON/depth, malformed/DTD XML, host programs and missing/ambiguous producer metadata. Include a forged short uncompressed-size counterexample.
- [x] Implement the parser and qualified composer while preserving unknown global settings and immutable input bytes; do not infer values or source authority.
- [x] Run focused tests; save red/green evidence and report exact limits. Independent review inspects important parser/derivation boundaries before integration.

## Task 2: Native project plan and actual new-path qualification

**Owner/files:** worker; `print_agent/slicer.py`, new `tests/test_project_slicer.py`, `scripts/qualify_bambu.py`. Coordinate only through Task 1's public interfaces.

**Interfaces:**
- `prepare_project_slice(input_path: Path, job_dir: Path, source_filename: str, source_content: bytes, *, source_id: str | None = None, executable_path: str | None = None) -> dict`.
- Project plan fields: `kind: studio_project`, `project_prepared`, `project_path`, `project_sha256`, `project_receipt`, `project_source` (public origin/summary/source ID), plus existing readiness/argv/expected-settings/file-hash fields.
- Existing `execute_slice(plan, timeout_seconds=180)` dispatches the project plan through equivalent tamper/output checks and the exact qualified runtime/options. Legacy role-bundle plans remain unchanged.
- Public prepared project path exists after successful composition even when `ready` is false because native is absent. Failures before complete composition expose no project artifact.

- [x] Write failing tests for executable-absent composition, exact supported execution plan, wrong runtime refusal, source/settings/model/derived/argv tampering, existing output refusal and missing/mismatched readback.
- [x] Implement separate project-plan staging/validation with original source and generated input staged in a new directory. Re-derive/verify the expected project before native execution; accept no unverified browser plan.
- [x] Extend production native qualification to use a newly native-generated source project and a different current CAD. Save source, derived project, receipts, native output, setting comparisons and mesh/G-code evidence.
- [ ] Preserve existing native smoke cases and verify the new path independently. Run focused tests, then request independent review. Actual native execution occurs in CI.

## Task 3: Immutable sources, API and prepared downloads

**Owner/files:** root; new `print_agent/studio_sources.py`, `tests/test_studio_api.py`, `tests/test_studio_sources.py`; `print_agent/app.py`, `print_agent/storage.py`, relevant storage/API tests.

**Interfaces:**
- `StudioProjectStore(root: Path)`; methods `import_project(filename, content)`, `get(source_id)`, `read(source_id) -> (snapshot, bytes)`, `archive(source_id) -> (filename, bytes)`.
- Public inspection contains source ID, schema version, source/producer/summary, settings hash, support/issues/warnings; excludes raw settings and native expectations. IDs are server-chosen UUID hex and paths never derive from submitted filenames.
- HTTP routes and exclusive `/api/slice` request choice exactly follow the spec. Backend errors preserve the existing structured error/session boundary.
- Prepared artifact kind: `prepared_three_mf`. Its receipt and lifecycle are separate from `sliced_three_mf`; job ZIP and legacy-job receipt verification include it correctly.

- [x] First reproduce missing import/API/prepared download behavior using real bounded fixture bytes. Verify session/origin/body limits and exactly-one source choice.
- [x] Implement immutable complete source publication and verified reads/downloads. Test collisions, read tampering, symlinks, invalid IDs, failed writes and reopening a persisted source without modifying it.
- [x] Integrate source store after the existing lease/compatibility preflight; record original/source/derivation in the existing job lifecycle. Tests cover no native install, source change, download hash mismatch, failed/new/interrupted attempts and an old job without modern receipts.
- [x] Verify restart/backup restoration of source IDs and original bytes, without changing SQLite schema or stored filament drafts.
- [x] Run focused/full integration tests and request independent review of data integrity and lifecycle changes.

## Task 4: Guided project import and state correctness

**Owner/files:** worker; `print_agent/static/index.html`, `print_agent/static/app.js`, `print_agent/static/style.css`, `tests/test_ui_state.cjs`, `tests/browser/workflow.spec.cjs`.

**Consumes:** Task 3's public inspection and endpoints, Task 2 plan/result, and `prepared_three_mf` job artifact. No direct client configuration-to-native conversion.

- [x] Add failing controller scenarios for candidate/apply/cancel preserving exact prior JSON, stale success/error after a newer file/model/epoch, source revalidation after reconnect/storage change, pending-input exit protection and recorded history requiring fresh prepare.
- [x] Add the primary single-file project flow and compact recorded setup summary; keep existing role JSON controls under advanced disclosure. Allow inspection before model generation or native installation.
- [x] Bind native preparation and downloads to current source/model/context; distinguish prepared-project download from native-sliced output. Provide actionable missing/unsupported/error states and explicit replacement choices.
- [x] Add two real browser scenarios per viewport: import/prepare/download/history with actual CAD/API and explicit unsupported/failure/replacement/race/reconnect preservation. Synthetic network failures are labeled; no fixture native process is called Studio.
- [ ] Run controller/syntax checks; actual browser CI and focused viewport screenshots verify the final path. Review code independently before publishing.

## Task 5: Mode-consistent navigation, installed qualification and release

**Owner/files:** root or narrow worker for planner only; `print_agent/planner.py`, planner/provider tests; root owns `scripts/qualify_install.py`, version metadata, docs/changelog and release integration.

- [x] Reproduce the same explicit material/purchase request routing differently in template versus LLM mode. Extract the existing deterministic intent routing and run it before any provider call in both modes; verify ordinary CAD requests still use the selected engine.
- [x] Extend actual installed-wheel qualification: import a labeled synthetic project, prepare/download the current CAD without Studio, verify raw settings and geometry, reopen history, then include new source/prepared bytes in the three-OS backup/restore checks. Keep original canonical/unfinished draft checks.
- [x] Set version 0.4.0 and document supported project settings, ignored source features, prepared-versus-sliced semantics, source/backup behavior and remaining qualifications.
- [ ] Full Python/controller/syntax/diff and final wheel/source/installed checks; fresh independent whole-change review. Correct reproduced important defects before delivery.
- [ ] Publish with expected-head protection, inspect actual application/package/native CI and artifacts, then verify automatic v0.4.0 release and public byte identity. Record exact evidence in a docs-only follow-up.

## Implementation ledger

- Audits found the novice full-JSON bottleneck and confirmed that existing filament reports cannot supply native configurations. A separate project-source path is selected; arbitrary edited-preset overlay is deferred until its own baseline/diff contract.
- A fresh builder review found no important unanswered design questions outside the explicitly pending native experiment.
- 406 baseline Python tests passed in the isolated native experiment worktree. No local Chromium/native retry or provider call was made.
- Native experiment and production implementation are pending; workflow definitions and source inspection alone do not establish success.

### Native experiment observed

- Branch commit `519f7b5fae9a23743b8e983a92aed3060765dcac`, actual native run [43597797224](https://github.com/uulab-official/3d-printer-agent/actions/runs/43597797224), evidence artifact `14115128319`, SHA-256 `72d87cf53bf8c67f84fb7c99a0d6e3de7e7262a4f465da0f9e9da3dec1df3bf9`. Both probes ran; the overall diagnostic workflow failed because the honest-new-Application probe exited `-11` without an output. This failure is retained, not hidden or reported as a passing workflow.
- Preserving the supplied `BambuStudio-02.09.01.70` source compatibility marker passed all nine case checks: native exit/logs, 30 core settings, new mesh, G-code, all snapshot keys compared and unchanged original/source/derived inputs. Production composition therefore preserves only a source's actually supplied qualified marker and separately records modifier, source hash and current CAD hash. Foreign sources never receive a fabricated Bambu marker.
- The new geometry retains 1,384 vertices, 1,332 triangles and 80 × 18 × 12 mm bounds; maximum translated vertex error is 0.000003738 mm. Source cube and current geometry are different.
- Prepared input copies all 612 global values and their raw bytes exactly. Native export records 613 keys: 610 unchanged, `wipe_tower_x/y` moved by arrangement, and empty `upward_compatible_machine` added. These normalizations must be reported; the native roundtrip is not byte-identical.
- This isolated compatibility experiment is not the final application path qualification. Production adapter, parser, HTTP, storage and browser CI remain pending.

### Implementation and prepublication checks

- Parser/composer and immutable source/API/prepared-storage paths implemented. Independent review reproduced three P2 issues (native value representations/project identity, missing-source HTTP500, unsupported ZIP extraction-version HTTP500), fixed with red/green regression evidence. An explicit-null slice hash regression from the shared artifact refactor was also restored to the earlier refusal contract.
- New source import uses 24 MiB request budget; other paths retain 2/8 MiB. Prepared downloads have independent receipts including legacy jobs; new attempts and interruption detach both current slice artifacts.
- Deterministic routing now precedes provider selection for explicit material/purchase requests in either mode. Thirty planner/provider tests passed; no live provider was called.
- Preliminary full Python run passed 457 tests before final review additions. A preliminary uncommitted installed wheel passed 154 actual local CAD/HTTP/restart/backup/restore checks outside the checkout, including source/prepareddownload restoration. Its receipt is explicitly labeled as an uncommitted development snapshot with a placeholder commit, and is not release evidence. Final source/wheel/CI gates remain required.
- Native runtime validation is being extended to compare actual mesh vertices/connectivity and legal placement transforms, not only qualification-time geometry. UI controller checks currently 137 passed; final browser scenarios/review pending.

- Final local source checks passed 467 Python tests and 137 controller checks; JavaScript/Python syntax and whitespace checks passed. Two new browser scenarios are defined and discovered at both viewports (38 total); no local browser/native launch was attempted. A separate production native case is wired after the unchanged legacy cases. Fresh independent UI/native review passed with 137 controller checks, 69 slicer checks and retained actual-native geometry readback. The final local wheel includes all 22 source-matching application files. Actual same-SHA CI/publication remains pending.
