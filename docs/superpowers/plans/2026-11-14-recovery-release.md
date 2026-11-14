# Recovery and Release Implementation Plan

> **For agentic workers:** Use the task briefs and independent review gates. File ownership separates parallel implementation; root integrates and publishes.

**Goal:** Ship v0.3 with verified complete-workspace recovery and durable promotion of the exact qualified wheel.

**Architecture:** Offline backup owns the existing data lease and streams a versioned archive. Shared lightweight compatibility checks protect startup and restore. Release publication consumes exact successful CI artifacts. UI fixes remain within the current local controller.

**Tech Stack:** Python 3.12 stdlib/FastAPI/CadQuery, dependency-free JavaScript, Playwright, GitHub Actions/REST.

**Spec:** [recovery-release-design](../specs/2026-11-14-recovery-release-design.md).

## Global Constraints

- Baseline `3570f8587cb8373843455ea12ba3cd5c486151fb`; target app version 0.3.0.
- Preserve canonical and original bytes; no existing destination replacement, automatic replay, arbitrary generated code execution or physical printing.
- Backup limits: 20,000 files, 512 MiB each, 4 GiB total, 8 MiB manifest; format version 1.
- Only actual CI/release observations establish completion. Keep platform/native/hardware scopes separate.
- Known local Chromium IPC and native dependency blockers are not retried or escalated.

## Review Focus

- Existing or concurrently created restore destination must remain intact, including empty folders and symlinks.
- A byte-valid backup of incompatible canonical SQLite data must not become an apparently empty workspace.
- Declared ZIP lengths/paths cannot override actual streamed byte/hash/inventory checks.
- Same-session form edits must invalidate late comparison errors as well as successes.
- A release must reference the exact tested wheel/commit; partial runs, wrong provenance and reruns must not replace published bytes.

## Tasks

### Task 1: Offline archive lifecycle

Files: new `print_agent/backup.py`, `tests/test_backup.py`. Produces the three backup functions and `BackupError` in the spec; consumes `DataDirectoryLease` and root-provided `require_compatible_data`.

- [x] Reproduce missing backup behavior and focused refusal/preservation cases using fresh fixture data.
- [x] Implement streamed create/inspect/staged restore and portable atomic no-replace publication.
- [x] Verify exact canonical records and unfinished drafts round-trip; reject malformed, changed, over-budget, nonportable and colliding data without altering source/targets.
- [x] Report focused checks and independent review findings.

### Task 2: Compatibility, CLI and installed-product integration

Files: root owns `runtime.py`, `app.py`, `__main__.py`, related runtime/API/CLI tests, `scripts/qualify_install.py`, version metadata and documentation.

- [x] Reproduce unknown workspace schema startup mutation and assert unchanged databases on refusal.
- [x] Implement the lightweight shared preflight before any production store mutation.
- [x] Add validated CLI commands and behavior tests while preserving existing serve/doctor invocations.
- [x] Extend actual installed-product qualification through source backup and restored HTTP/CAD/workspace operation on all three OS jobs.
- [x] Document operating limits, verified Ubuntu preparation, version and update/restore instructions.

### Task 3: Purchase draft correctness

Files: `static/app.js`, `tests/test_ui_state.cjs`, `tests/browser/workflow.spec.cjs`; optional narrowly needed HTML/CSS only.

- [x] Record the programmatic 1000-to-2000 state probe separately from real form locking; preserve the current disabled controls while pending.
- [x] Invalidate old successes/errors using exact input state, and protect unsaved purchase input/active comparison on exit.
- [x] Verify real pending form locking, matched delayed response, subsequent edit invalidation and explicit retry with unchanged arithmetic/API.

### Task 4: Durable qualified release

Files: new release promotion script/tests and `.github/workflows/release.yml`. Consumes existing three workflow paths and shared wheel/report format; no build at publication.

- [x] Pin same-repository current-main event/run selection and artifact/source/version/receipt verification with focused fixture failures.
- [x] Implement minimal-permission completion workflow and resumable exact-draft publication; never replace published versions/assets.
- [x] Verify completed release assets after actual package/application/native CI succeeds; retain honest pending/blocked state otherwise.

### Integration and delivery

- [x] Fresh independent review of archive, startup, UI and release boundaries; correct reproduced important defects.
- [x] Full local Python/controller/syntax/diff and final wheel/source checks.
- [x] Publish main with expected-head protection; inspect all actual CI results and artifacts.
- [x] Verify published release byte identity and record exact results/limits in a docs-only follow-up.

## Integration ledger

- The archive/CLI implementation passed its focused tests; the first integrated local gate passed 391 Python tests and 122 controllers. Browser discovery found 34 definitions; execution remained pending CI.
- Fresh archive/startup review reproduced WAL sidecar mutation, acceptance of reordered/incorrectly typed SQLite columns and an unsupported ZIP version escaping the JSON boundary. Root added failing regressions, isolated WAL probing, checked ordered column metadata and normalized the specific ZIP exception. The reviewer independently closed all three findings with exact file/row preservation, committed-WAL read-back and a real CLI subprocess.
- The integration review found no important UI/installed-qualification issue and confirmed the pending-form audit correction.
- Release review reproduced retained artifact-name collisions after failed-job reruns and workflow-attempt changes during asset upload. The five added regressions passed with all 25 release tests after correction. Focused independent re-review reran both original reproductions and all five regressions, and closed both findings.
- The first reviewed local Python gate passed 402 tests. The 122-controller/syntax checks passed; 34 browser definitions were discovered. The built wheel contains 20 application files identical to source. Prepared-commit installed-wheel smoke passed 133 checks outside the checkout.
- Feature commit `e15030fb7526ac2e75542be9d94579a1c2007291` passed application and native CI, but package run 43594078275 failed on Windows backup. Fresh path metadata and common path/descriptor identity semantics corrected cached zero IDs, creation/change-time differences and inferred executable bits without removing same-origin change detection. Commit `7c70cb6f0ce0d746150e486a2ed9196604950002` passed all three gates, including 133 checks per OS; the local Python gate reached 405.
- Actual promotion 43595184660 stopped with HTTP 415 before any release write. A header-aware failing regression reproduced the Actions artifact endpoint's required JSON media type; release asset bytes retain octet-stream. Independent focused review closed the fix, all 406 local Python tests passed and the full artifact verifier passed against actual qualified artifacts. Native workflow path filters now include release infrastructure so this correction can satisfy all three same-SHA gates; native jobs and application files are unchanged.
- Final code commit `18e0af01a92e6204116836fc9cb8e09089340211` passed application CI 43595546992 (406 Python, 122 controller, 34 real browser), package CI 43595547010 (133 checks per OS) and native CI 43595546864, all on attempt 1. Fresh package and native artifacts passed 435 and 95 independent checks respectively.
- Fresh browser evidence passed 97 independent checks; six purchase/storage component captures were inspected. The recorded mobile crop overlap and horizontally scrollable columns limit visual claims. Actual pending-form locking, edit invalidation, explicit retry and arithmetic passed; the exit test covers a cancelable event rather than a native confirmation dialog.
- Promotion 43595774058 published v0.3.0 / release 445286167 at 2026-11-14 12:38:19 UTC. The tag points to the exact final code commit; seven uploaded/read-back assets contain the qualified 153,564-byte wheel with SHA-256 `c19f456dea74dfa47dedeeb4726c67c2556ce6655c1a1aed72ff8a2e3bbcb35d`. Both gate revalidations remained unchanged. The final follow-up records these observed results and operating limits in documentation only.
- Independent public-release verification passed 31 checks, downloading all seven public assets without authentication and comparing their bytes with the API, promotion report and qualified package evidence. The release evidence document was reconstructed independently; no duplicate release or assets were present.
