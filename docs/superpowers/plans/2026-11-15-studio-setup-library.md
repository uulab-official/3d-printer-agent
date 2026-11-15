# Studio Setup Library Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Rediscover and reuse Studio inputs without CAD, preserve exact unfinished drafts, and close two demonstrated integrity gaps.

**Architecture:** Add an authoritative SQLite store referencing existing immutable sources/revisions and a bounded metadata catalog. Restore verified inputs through an explicit UI candidate, and carry verified CAD bytes through both preparation adapters.

**Tech Stack:** Python 3.12, FastAPI, SQLite, dependency-free JavaScript, unittest, Node controller checks, GitHub-hosted Playwright/native qualification.

**Spec:** `docs/superpowers/specs/2026-11-15-studio-setup-library-design.md`

## Global Constraints

- Python 3.12; no new runtime dependencies; local single-user Korean UI.
- Existing Studio 02.09.01.70/single-filament/nozzle/extruder/six-field scope; no manufacturer, hardware or print-success inference.
- Original archives and revision recipes remain immutable; new records store inputs only.
- Exact six draft strings, at most 512 characters each, 16 KiB UTF-8 snapshot, title 1–120 trimmed characters, positive safe integer revisions below `2**53 - 1`.
- Actual Chromium/native Studio execution is GitHub CI only. Do not install or launch either locally.
- Root alone owns Git staging/commits/publication and shared API/release integration; implementers edit only their task files.

## Review Focus

1. Equal filenames and orphaned old imports/revisions: identify both and open the intended immutable record without CAD (Tasks 1, 3, 4).
2. Invalid/overlong/whitespace draft strings: exact preservation across reload and backup, without restoring a review (Tasks 1, 3, 4).
3. Late responses, cross-tab conflict and storage-root changes: preserve newly typed inputs and do not apply stale references (Tasks 1, 3).
4. Corrupt metadata beside healthy entries: bounded list survives, explicit open reports failure, current input stays intact (Tasks 1, 3, 4).
5. CAD replaced after receipt verification: stage the verified original or fail; never publish a different model under the old job identity (Tasks 2, 4).

---

### Task 1: Persist and discover Studio inputs

**Files:** Create `print_agent/studio_workspaces.py`, `tests/test_studio_workspaces.py`; modify `print_agent/runtime.py`, `print_agent/workspaces.py`, `tests/test_runtime.py`, `tests/test_workspaces.py` and only directly affected persistence/backup tests. Do not edit app.py/static/qualification scripts.

**Interfaces:** Produce all `StudioWorkspaceStore` methods, snapshot/record/catalog contracts and `StudioWorkspaceIntegrityError` exactly as the spec. Export `WorkspaceIntegrityError` from existing `workspaces.py`. Reuse existing `WorkspaceConflict`. Root provides HTTP exception/route/lifespan integration. Catalog sources/revisions may use existing private bounded-read helpers; do not modify immutable receipt formats. Existing missing third database is valid; malformed authoritative database is not repairable.

- [x] Write failing store tests for zero-job original/edited workspace restart with exact `" 1. "` and a 33-character invalid draft, page continuity, equal filenames, legacy sources/revisions, and archive-reader-disabled list.
- [x] Add corruption tests for bounded oversized/malformed/duplicate/nonfinite rows, mismatched source/revision/hashes, one unreadable catalog item, stale update/delete across two store instances, no source/revision deletion, and unchanged incompatible database bytes.
- [x] Add failing raw profile workspace read tests for invalid target index, missing setup fields and wrong snapshot type. Show rejection before returning the record.
- [x] Implement strict validation, conditional transactions, metadata pagination and compatibility checks. Deep verification occurs on named create/update/open; list never opens archives. Profile get validates existing rows with an explicit integrity error.
- [x] Run relevant unittest modules and record exact red/green evidence and file list in the task report. Full shared suite runs once after integration.

### Task 2: Preserve verified CAD through preparation

**Files:** Modify `print_agent/slicer.py`, `print_agent/storage.py`, `tests/test_slicer.py`, `tests/test_studio_project.py`, `tests/test_project_slicer.py`, `tests/test_storage.py`, `tests/test_prepared_storage.py`, `tests/test_storage_integrity.py` as needed. Root owns API call sites. No other production files.

**Interfaces:** Extend `prepare_slice(..., executable_path=None, *, input_bytes=None)` and existing keyword-only `prepare_project_slice(..., input_bytes=None)` with optional immutable bytes. `JobStore.read_artifact(job_id, 'three_mf')` already produces `(path, bytes)`; root passes both. Do not change positional call compatibility for standalone qualification.

- [x] Write a failing regression that verifies existing cable-comb CAD, replaces its path with existing tray bytes, then prepares and publishes. Assert no published project can contain the replacement under the original receipt.
- [x] Cover both role-bundle and project adapters, and rejection of invalid/empty/oversized supplied bytes without relying on an executable launch.
- [x] Implement one bounded input snapshot, validate/stage those same bytes, and bind project publication to the stored original model receipt. Preserve existing failure cleanup and standalone behavior.
- [x] Run focused slicer/storage/project tests with fake subprocesses only; report observed red/green results and interface details.

### Task 3: Make saved setups usable in the browser

**Files:** Modify `print_agent/static/app.js`, `print_agent/static/index.html`, `print_agent/static/style.css` (or existing stylesheet), `tests/test_ui_state.cjs`, `tests/browser/*.spec.*` as appropriate. No backend or qualification files.

**Interfaces:** Consume the HTTP endpoint, snapshot, envelope and list contracts verbatim from the spec. Existing original/revision endpoints open legacy entries. Named GET returns `{workspace,source,settings_revision,editor}`; POST/PUT return record; DELETE 204. Catalog kind query is plural; item kind singular. Save only the current applied source/revision and exact optional six-field draft. Lists are not verification. Root integrates endpoints before browser CI.

- [x] Add failing Node regressions for atomic raw profile restoration, candidate-based named original/edited restore, exact invalid draft preservation, conflict/save-copy, late open/save, cancellation and root-change behavior.
- [x] Implement catalog, refresh/load-more, open, title, save/save-copy/delete controls near Studio inputs. Preserve existing CAD/manual JSON/profile workspaces until explicit user changes.
- [x] Build the whole raw profile restoration value before mutating any current state, and display integrity failures without dropping guided edits or editor contents.
- [x] Add actual-browser desktop/mobile scenarios: import before CAD, save original/edited variants and unfinished text, reload, find without IDs, open candidate, explicit apply, continue draft, and prepare new current CAD. Include legacy discovery and server-returned corruption/input-preservation behavior. Capture useful focused screenshots without fixed-header/skiplink obstruction.
- [x] Run syntax and Node controller suite. Do not run/install Chromium locally; actual browser evidence is CI-only. Report pending CI scenarios honestly.

### Task 4: Integrate, qualify and publish v0.6.0

**Files:** Root owns `print_agent/app.py`, `tests/test_app.py` and/or new `tests/test_studio_workspace_api.py`, `scripts/qualify_install.py`, related release qualification tests/configuration, version files and public docs, spec/plan/ledger. Other ownership changes require coordination.

**Interfaces:** Wire Task 1 store after compatibility check and root lease, strict payloads and 409 integrity codes. Use Task 2 verified snapshot on all `/api/slice` branches. Preserve every existing gate and native-case requirement.

- [x] Write failing API behavior tests for zero-job named save/open, security/strict bodies, conflicts, source/revision failure with no fallback, corrupt profile GET 409, and verified CAD mutation boundary.
- [x] Integrate stores/routes/error handling and snapshot-byte handoff. Run focused API tests.
- [x] Extend installed-wheel qualification: discover old originals/revisions, save original/edited/invalid-draft workspaces before CAD, restart and list/open them, backup and restore to another root, preserve exact draft/IDs, and prepare new CAD from reopened edited settings. Assert catalog metadata is not a current review and named delete retains originals/recipes.
- [x] Update version to 0.6.0 and public capability/limitation/upgrade docs. Run full Python and Node checks, build/install shared wheel outside checkout, and verify installed qualification.
- [x] Obtain fresh task and whole-change review, resolve concrete findings, then commit/push authorized main with compare-and-swap and exact tree comparison.
- [x] Inspect exact-source CI/browser, three-platform shared-wheel, four-case native and promotion artifacts, including screenshots and archive/model/settings/backup evidence. Verify all public release bytes and immutable tag independently. Update docs with actual evidence in a docs-only follow-up commit and finish with a concise Korean outcome/limits report.

## Completion record — 2026-11-15

Implemented and independently reviewed all four tasks. Feature source `1cae4ba` was followed by the actual CI harness correction `34b5fd6` and same-source native trigger correction `020b552`; no production CSP or release gate was weakened. Final release source is `020b5520e90e450b401ae4a912ef8b8ad1dc8228`.

Actual final-source gates: CI 43690192580 (554 Python, 167 controller, 46 Chromium); package 43690192608 (235 checks on each of three operating systems); native 43690192597 (four synthetic cases), all successful on attempt 1. Promotion 43690554701 published v0.6.0 / release 445886425 at 2026-11-15T07:35:04Z. Fresh public download/readback passed 67 checks for all seven assets and the exact source tag. Browser/package/native retained-data reviews passed 306 / 383 / 247 checks respectively; the 247 native assertions comprise 238 independent data checks and nine record consistency checks. Six new component PNGs were visually inspected.

The documentation follow-up records these actual observations and current catalog refresh behavior. It leaves the qualified app bytes and release tag unchanged. Detailed diagnosis and evidence limits, including native stdout diagnostics and physical-print exclusions, are in docs/VERIFICATION.md.
