# Studio Filament Tuning Implementation Plan

> **For agentic workers:** Use subagent-driven development with explicit file ownership and independent review. Implementation and main/release delivery are already authorized. Root owns publication; workers do not commit or push a shared index.

**Goal:** Ship v0.5.0 with explicit, traceable filament-setting edits that reach prepared current CAD and a separately qualified native slice.

**Architecture:** A pure allowlisted derivation engine produces reviewed immutable revision recipes from verified Studio originals. A revision store and strict API feed current-CAD composition, existing native verification, history and recovery. The UI separates draft, review, applied revision and prepared/sliced results.

**Tech Stack:** Python 3.12 stdlib/FastAPI/CadQuery, dependency-free JavaScript, Playwright, existing package/native/release workflows; no new dependency.

**Spec:** [studio-filament-tuning-design](../specs/2026-11-15-studio-filament-tuning-design.md).

## Global Constraints

- Baseline `4c090f1a511da68fae16425da566a3e109b74783`; target 0.5.0. Keep original source receipts, SQLite schemas, backups, no-revision jobs and role bundles compatible.
- Exactly six fields and pinned bounds from the spec; native one-element string arrays, immutable selected plate, user-selected provenance. No arbitrary configuration/profile conversion.
- Root source bytes remain unchanged. Edited settings preserve all untouched values; empty changes preserve original settings bytes. Reconstruct effective bytes from original+recipe at every preparation/execution.
- Same existing Studio version `02.09.01.70`, single-filament/nozzle/extruder. Preserve old native cases and add the edited case; do not treat test fixtures as manufacturer or physical validation.
- No local native/Chromium launch or escalation. Observe actual browser/native execution in CI. Existing commit/push authorization persists.
- Workers own disjoint files and report their exact diff/test evidence; root integrates. No worker changes to app version/docs, main or remote resources.

## Review Focus

1. Partial or numerically unchanged input must not mutate untouched settings or publish a fake change: Task 1.
2. A changed selected plate/source/review cannot redirect an allowed alias or authorize a different revision: Tasks 1 and 3.
3. Corrupt/missing source or revision must not leave old prepared/sliced artifacts looking current: Tasks 2 and 3.
4. Late review/create/revalidate results after edit/cancel/reconnect cannot replace current draft/revision or enable stale native execution: Task 4.
5. Restored history must retain effective settings and reprepare against current storage, with no old absolute-path execution: Tasks 3–5.

## Task 1: Pure derivation and current-CAD composer

**Files/owner:** worker; create `print_agent/studio_settings.py`, `tests/test_studio_settings.py`; modify `print_agent/studio_project.py`, `tests/test_studio_project.py` only.

**Interfaces:** implement `settings_editor`, `derive_settings`, `make_revision`, `verify_revision` and the keyword extension to `build_project_3mf` exactly as specified in the spec. Publish precise resulting dictionary shapes to the root before downstream integration. Keep the existing inspector/public original shape unchanged. Set composer modifier to `3D Printer Agent 0.5.0` and adjust its version expectation tests.

- [x] Write/run failing behavioral cases: six fields with literal changes; each selected-plate mapping; unknown/identity/G-code/process keys refused; integer/decimal/type/length/baseline bounds; whole-proposal atomicity; numeric no-op original bytes; all untouched values preserved.
- [x] Implement pure derivation, editor/review and exact immutable recipe validation. Use documented canonical identity hashing and deterministic serialization.
- [x] Extend composition with original snapshot plus optional verified revision; embed original/effective/revision metadata and truthful receipts without changing the source or mesh.
- [x] Verify focused tests and no-revision regression, retain red/green evidence, self-review and request independent task review.

## Task 2: Native plan and real qualification

**Files/owner:** worker; `print_agent/slicer.py`, `tests/test_project_slicer.py`, `scripts/qualify_bambu.py` only.

**Interfaces:** `prepare_project_slice(input_path, job_dir, source_filename, source_content, *, source_id=None, executable_path=None, settings_revision=None)` consumes Task 1. New plan fields `settings_revision`, `settings_review`; exact optional staged record `settings-revision.json`.

- [x] Write/run failing cases for edited preparation without Studio, effective expectations, original/current/recipe/receipt/argv/hash tampering before and after probe, wrong native values and unchanged old source path.
- [x] Stage and rederive the optional revision at every existing validation boundary. Preserve original `project_source`; native snapshot/readback uses effective settings. Complete setting and geometry checks stay strict.
- [x] Add fourth actual production native case, keeping the three existing cases unchanged in meaning: six different synthetic values, current CAD different from source, independent prepared and native all-setting/mesh comparison, unchanged original and recipe, retained evidence.
- [x] Run focused tests, self-review and request independent task review. Actual native execution follows the main publication in CI.

## Task 3: Immutable revision store and API

**Files/owner:** root; create `print_agent/studio_revisions.py`, `tests/test_studio_revisions.py`, `tests/test_studio_settings_api.py`; modify `print_agent/app.py` and relevant existing API tests only if required.

**Interfaces:** `StudioSettingsRevisionStore(root, sources)` with `create`, `read`, `get` and public envelope specified in the design. Four settings/revision endpoints; `/api/slice` chooses exactly one of three sources.

- [x] Write/run real temporary-file and HTTP failures for missing feature, atomic invalid proposal, source/review mismatch, publication failure/collision, symlink/tamper, missing source/revision and request/session validation.
- [x] Implement complete validation before exclusive publication, atomic bounded revision record, every-read source+recipe verification, backwards-compatible app startup and clear 404/409/422 behavior.
- [x] Pass only server-read original/recipe to Task 2; verify new/failed/interrupted requests invalidate old artifacts and preserve independent originals. Test read/reprepare after restart and backup/restore to a new directory.
- [x] Run focused integration tests and independent integrity review.

## Task 4: Guided editor and browser workflows

**Files/owner:** worker; `print_agent/static/index.html`, `print_agent/static/app.js`, `print_agent/static/style.css`, `tests/test_ui_state.cjs`, `tests/browser/workflow.spec.cjs` only.

**Interfaces:** consume Task 3 endpoints, exact proposal/review/envelope and Task 2 plans from the design. Coordinate shapes with Task 1; do not accept or send full settings snapshots. Existing `studioRevision` is a numeric UI revision; use distinct names for settings records.

- [x] Write/run failing controllers for six-field editor, exact invalid strings and no partial apply, review→apply, cancel/reset, explicit source replacement, source/model/revision/epoch stale responses, exit protection, old/new history and reconnect without replay.
- [x] Implement the guided Studio editor with source/effective differences and user-selected labeling. Keep manual JSON and separate filament drafts intact; input changes detach stale prepared/native results.
- [x] Add actual desktop/mobile success/recovery workflows: import, edit all six, review/apply, actual CAD preparation, inspect downloads, reselect edited history, invalid/stale edits and actual restart. Retain first and reopened/reprepared JSON bodies and exact draft readbacks where practical, plus focused screenshots.
- [x] Run controllers/syntax and independent workflow review; actual Chromium evidence is observed in CI.

## Task 5: Installed evidence, release and user documentation

**Files/owner:** root; `scripts/qualify_install.py`, version metadata, README, CHANGELOG, user/status/verification docs and workflow paths if needed.

- [x] Extend actual installed-wheel qualification to create/review/apply all six edits; verify changed-only settings and current CAD; retain source/revision/prepared responses; reopen after restart.
- [x] Include original+revision+prepared bytes in backup/restore, then freshly prepare from the same revision ID on the restored server. Preserve all previous CAD, ownership, draft and recovery checks.
- [x] Set 0.5.0, document actual supported fields, source/edited semantics, reset/history/recovery and qualified bounds. Mark pending CI honestly until it completes.
- [x] Run full required Python/controller/syntax/diff and wheel/source/installed checks. Independent whole-change review; resolve reproduced consequential findings.
- [x] Publish reviewed source with expected-head protection; inspect actual application/package/native gates and downloaded evidence, verify v0.5.0 public assets, then commit a docs-only observed-evidence follow-up.

## Ledger

- Product and integration read-only audits selected the gap between project settings and editable output. Direct project controls were selected over arbitrary profile conversion.
- Official pinned native schema was read to confirm integer temperatures, six field bounds and all plate mappings. These are format limits, not hardware or material advice.
- Ruling: include selected-plate temperatures because the existing core snapshot already binds an immutable plate and both required keys, and all five native schemas were verified; forbid plate changes and zero values. Cost if wrong: scope can be reduced before release without altering originals.
- Ruling: immutable complete override recipes use the original as their single baseline, avoiding chains and overwrites. No independent revision library or extra SQL store is needed.
- Ruling: disjoint engine/native/UI files may be developed in parallel against the frozen contract; root owns storage/API/qualification/docs and publication. Shared-index commits by workers are forbidden.
- Ruling: continued implementation and main/push/release were explicitly authorized earlier; routine design/worktree/release permission is not requested again.
- Isolated worktree: `/workspace/scratch/d9925436ef0d/3d-printer-agent-filament-tuning`, branch `feature/studio-filament-tuning`. Baseline/full runtime evidence follows below.


## Observed completion — 2026-11-15

Implemented and independently reviewed as `c88b4eec5c35c3a44274388ec9d16846a3acb3b2`.
Same-source application CI `43660589695`, package CI `43660589594`, and native CI
`43660589608` passed on attempt 1. Promotion `43660942959` published v0.5.0; public
readback verified all seven assets against the qualified bytes. Follow-up documentation
records actual outcomes in `docs/VERIFICATION.md` without moving the release tag.
