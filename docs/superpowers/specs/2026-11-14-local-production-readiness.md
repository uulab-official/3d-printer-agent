# Reliable local operation and installed-package qualification

Date: 2026-11-14 (Asia/Seoul). Baseline: `97a2c05667cdb48ae9c573c27b5008dacaff684e`.

The user requested production-grade progress and has already authorized implementation and publication to `main`. Routine implementation decisions are resolved here without another approval round. This milestone hardens the actual local product; external model/shopping services, hosted multi-user deployment and physical printer actions are separate capabilities.

## Observed problems

Independent audits reproduced lost updates from two servers sharing a data root; stale or missing history indexes; abandoned jobs remaining `generating`; modified 3MF bytes downloading successfully; a provider response limit applied only after full buffering; malformed session tokens returning 500; expired sessions without an accessible reconnect action; unprotected model drafts/history replacement; stale history responses erasing a newer list; and saved jobs beyond the first 100 being unreachable.

`doctor` also returned success for a data path that is a regular file and emitted no diagnostic report when CadQuery could not import. Existing installed-wheel checks only verify imports/assets on Linux. These observations define the work, rather than a generic production checklist.

## Decisions

1. Keep the existing synchronous generation contract. Admit one CAD operation at a time and return an explicit retryable busy response before reserving another job. Do not pretend a network timeout cancels CAD or replay uncertain writes automatically.
2. Hold one OS-backed exclusive lease per data directory for the application's lifespan, before any store creation/recovery. Explicit `test_mode=True` retains the isolated test factory behavior; actual CLI qualification exercises ownership.
3. Select storage by CLI argument, then nonempty `PPA_DATA_DIR`, then an existing recognizable legacy `./data`, otherwise a stable per-user application-data directory. Never move or delete legacy data automatically. Show the absolute active location and source in diagnostics and the UI.
4. Reconcile valid job files into the derived SQLite history index under exclusive ownership. Mark abandoned `generating` jobs `interrupted` once, preserve their request and partial files, and offer no validated download. Preserve damaged records; expose a readable diagnostic entry instead of discarding healthy history or rewriting the damaged source.
5. Save artifact receipts with new jobs. Download verified byte snapshots and build bundles from those same verified bytes. Detect size/hash changes and missing files with a typed integrity error. Support legacy receipts in their existing manifest; do not fabricate original evidence.
6. Provide deterministic cursor pagination for history, preserving the existing `jobs` array contract. The UI loads 20 items per page, protects current work before replacement and ignores superseded requests.
7. Provide a visible connection status, explicit reconnect without page reload, a stable `session_expired` error code and pending-work exit protection. Preserve current fields/results during reconnect; never automatically repeat a mutation.
8. Make optional LLM responses stream within a 100,000-byte budget and a whole-request deadline; non-success bodies are not buffered. Continue accepting only supported typed parameters.
9. Qualify the exact wheel outside the checkout on Python 3.12 with Ubuntu 24.04, macOS 15 and Windows 2025 runners. Exercise real CAD, HTTP/downloads, storage ownership and restart persistence. Retain wheel/checksum/platform reports. Native Bambu execution remains a separate Linux qualification.

## Shared interfaces

### Runtime module — `print_agent/runtime.py`

- `resolve_data_directory(explicit: Path | None = None) -> dict`: `{'path': absolute_string, 'source': 'argument'|'environment'|'legacy'|'user_default', 'legacy': bool}`. Only recognizable legacy data is adopted; document its cwd-dependent compatibility behavior.
- `DataDirectoryLease(root: Path)`: context manager that creates the directory if needed and acquires an exclusive nonblocking OS lock before application stores are opened. Same-root rejection must not rewrite data. Keep the lock file stable; the OS releases the lease when the process exits. Raise `DataDirectoryInUse` with an actionable message.
- `diagnose(data_dir=None, *, probe_slicer=False) -> dict`: structured version/platform/Python, required component/asset/storage checks, optional provider/slicer observations, `ready` boolean and selected `storage`. Missing optional providers/slicer do not make local CAD unavailable. No secrets/environment dump. Catch import failures independently. Only explicit `probe_slicer=True` runs native help.

The root integrates `resolve_data_directory` and the lease into `create_app` lifespan. The CLI reports the selected path; it does not acquire a second lease around the already-owned application.

### Storage additions — `print_agent/storage.py`

- Preserve `reserve()` callers; accept keyword-only `request=None, design_source=None` to save the generation input before CAD. Store a source snapshot without inventing a completed result.
- `recover() -> dict`: explicit startup-only reconciliation under the caller's lease, returning integer `indexed`, `interrupted`, `unreadable` counts. No recovery during a second store's ordinary construction.
- `list_jobs_page(*, limit=20, before=None) -> dict`: `{'jobs': [...], 'next_cursor': string|null}`; descending `(created_at, id)` ordering; validated bounded opaque cursor; limit 1..100. Keep `list_jobs()` returning its legacy first-100 list.
- `read_artifact(job_id, kind) -> tuple[Path, bytes]`: validate path/receipt, read once, return the exact verified content. `artifact_path` retains its Path contract for native integration but verifies integrity too. `bundle()` uses verified bytes, not a second file read.
- `ArtifactIntegrityError(ValueError)` and `JobRecordError(ValueError)` map to HTTP 409 with respective `artifact_integrity` / `job_record_unreadable` codes. Damaged input bytes remain untouched.
- `begin_slice(job_id)` persists a `latest_slice.phase='running'` attempt and clears the previous sliced download before preparation/execution. `record_slice` completes its phase. Startup recovery marks an unfinished slice `interrupted`, preserves the valid CAD result and exposes no old slice as the current download. The generation interruption count remains specific to CAD jobs.

### HTTP/UI additions

- Bootstrap adds `storage: {path, source, legacy, recovery: {indexed, interrupted, unreadable}}`.
- Invalid/missing session token: HTTP 403 with existing human `detail` and `code: 'session_expired'`; compare safe bytes for malformed headers.
- `GET /api/jobs?limit=20&before=...` returns paged result; default limit 100 preserves existing clients' visible batch.
- Model/slicer resource busy: HTTP 409, `code: 'resource_busy'`, `Retry-After`; no new job reservation while CAD is occupied.
- Keep source, geometry, slicing and physical-print facts distinct. New history statuses are `interrupted` and `unreadable`.
- History replacement must explicitly confirm before changing unfinished model fields. Cancel preserves existing exact strings, source, preview and downloads. Ordinary template/reset changes should follow the same policy when work would be lost.
- A dirty-work predicate covers model edits/request, pending model operation, staged slicer input and existing filament workspace dirtiness. This milestone does not claim persistent recovery of the browser's inaccessible raw invalid-number text across full reload.
- Refresh and pagination preserve the last successfully loaded list on error. Stale requests cannot replace new results or trigger unrelated global connection state.

## Verification and qualification boundary

Use behavior-first regressions for the observed failures, full required Python/UI gates, actual CI Chromium flows and installed-package tests. Check downloaded evidence against the exact tested commit. Test same-root exclusion with real processes, restart recovery, damaged artifacts, paging past 100, session recovery without replay and unfinished draft cancellation. Do not retry known-blocked local Chromium/native execution or escalate permissions.

The new wheel gate reports its observed operating system, architecture, Python/CAD versions and checksum. This does not establish native Bambu support on macOS/Windows, real model-server quality, user-hardware compatibility or physical-print quality. Do not claim an external deployment, release asset or successful gate before observing it.
