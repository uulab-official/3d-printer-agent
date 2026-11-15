# Reusable Studio setups and verified CAD snapshots

## Problem and decision

Studio imports and immutable setting revisions survive on disk, but v0.5 has no list or named workspace for them. A person who imports and edits settings before making CAD cannot rediscover that work after closing the page. A later failed preparation can also replace the only history link. This release makes those retained inputs useful independently of CAD.

Implementation decision: keep immutable originals and revision recipes as they are, add a small SQLite store of named references and exact drafts, and expose a paginated metadata catalog for both new workspaces and pre-existing originals/revisions. Mutating source receipts to add names would weaken their exact verification contract. Automatically copying every archive into every workspace would duplicate data and obscure identity. A separate reference store follows the existing filament workspace conflict model and participates in startup/restore checks.

This is a maintainer implementation decision under the user's continuing instruction to improve and publish the project, not a claim that the user selected a particular schema.

## Scope and invariants

- Python 3.12; existing dependency-free Korean UI; no new runtime dependencies.
- Local single-user application; three fixed CAD templates; the existing Studio 02.09.01.70, single-filament/nozzle/extruder and six-field edit scope remain.
- Original archives and revision recipes remain immutable. Named labels are user labels, never material identity, compatibility, manufacturer recommendations or physical print validation.
- Save and reopen without a CAD job. Existing v0.4/v0.5 source and revision directories must be discoverable without reimporting or knowing an ID.
- Lists are recorded metadata, not fresh verification. Read only bounded receipt/recipe/row metadata for the requested page; do not decompress source archives when listing.
- Opening deeply verifies the selected source and optional revision. It presents a candidate and exact saved draft; applying that candidate remains explicit. Never restore a prior current review, ready state, prepared download or execution permission.
- A missing/corrupt edited reference must not fall back to the original. One unreadable entry must not hide healthy entries. A failed or stale open preserves current inputs.
- Save/update/delete use optimistic concurrency. Deleting a workspace removes only the named record; retain its originals, recipes and existing job artifacts.
- Draft values are exact strings, including whitespace and unfinished/invalid numbers. Storage limits differ from the existing 32-character validation limit: six fields, at most 512 Unicode characters each, at most 16 KiB for the complete UTF-8 snapshot.
- Tests use synthetic settings and existing CAD fixtures. Actual Chromium and native Studio execution run in GitHub CI only; do not launch or install a local browser or native Studio executable.

## Persistent and API contracts

`studio-workspaces.sqlite3` has `studio_workspaces(id TEXT PRIMARY KEY, title TEXT NOT NULL, revision INTEGER NOT NULL CHECK(revision >= 1), created_at TEXT NOT NULL, updated_at TEXT NOT NULL, snapshot_json TEXT NOT NULL)`. It is an authoritative store, not a rebuildable index. Existing data roots without it are compatible. Startup and restore must reject an incompatible database without mutating it.

A snapshot has exactly:

```json
{
  "schema_version": 1,
  "source_id": "32 lowercase hexadecimal characters",
  "settings_revision_id": null,
  "source_sha256": "64 lowercase hexadecimal characters",
  "settings_sha256": "64 lowercase hexadecimal characters",
  "effective_settings_sha256": "64 lowercase hexadecimal characters",
  "draft_values": null
}
```

`settings_revision_id` may be an existing immutable revision ID. `draft_values` may be an object containing exactly the six public keys returned by `settings_editor`, each with a string value. The server compares all references and hashes to a freshly read supported source and, if selected, rederived revision. For an original setup the effective settings hash equals the original settings hash. No review result or full archive is accepted in a snapshot. Titles trim surrounding whitespace and contain 1–120 characters. Revisions are positive, non-boolean safe integers below `2**53 - 1`.

`StudioWorkspaceStore(root, sources, revisions)` provides:

- `create(title, snapshot) -> record`
- `update(workspace_id, title, snapshot, expected_revision) -> record`
- `get(workspace_id) -> {workspace: record, source: public_source, settings_revision: revision_envelope|null, editor: settings_editor_with_source_id}`
- `delete(workspace_id, expected_revision) -> None`
- `list_entries(kind, *, limit=25, before=None) -> {items, next_cursor}`

Records contain exactly `id, title, revision, created_at, updated_at, snapshot`. Every saved-row read validates JSON with duplicate/nonfinite rejection, exact shape, bounds, ID, timestamps and revision before exposure. `StudioWorkspaceIntegrityError` means a saved row/reference is unreadable (409); `WorkspaceConflict` means a stale mutation (409); missing records remain 404; invalid new input remains 422. GET must not rewrite a record to repair it.

HTTP endpoints:

- `GET /api/studio-library?kind=workspaces|sources|revisions&limit=25&before=<id>`
- `POST /api/studio-workspaces` with `{title,snapshot}` (201)
- `GET /api/studio-workspaces/{id}` (deep verification)
- `PUT /api/studio-workspaces/{id}` with `{title,snapshot,expected_revision}`
- `DELETE /api/studio-workspaces/{id}` with `{expected_revision}` (204)

Catalog pages use descending ID order and an exclusive `before` ID cursor, not an assertion of chronological order. Limit is 1–100. Directory enumeration may inspect names, but only the selected page's bounded metadata is opened. Each item has `id`, `kind` (`workspace|source|revision`), `title`, `created_at`, `updated_at`, `source_id`, `settings_revision_id`, `revision` (integer only for workspaces), `has_draft`, `metadata_status` (`recorded|unreadable`), `detail`, and `summary` (a bounded human-readable string). Use null for unavailable identifiers/timestamps, a safe label and explanation for unreadable metadata. Do not put draft text or archives into list responses. Original filenames, dates, short IDs, recorded printer/nozzle/plate/material/process and changed-field names should help distinguish equal filenames; render only text.

## User flow

Add a Studio settings library near the current Studio import/editor, with three catalog choices, refresh/load-more, record selection/open, title, save, save-copy and delete-workspace controls. The copy explains that list entries are recorded inputs and opening verifies them. Saving uses the applied source/revision plus an optional exact six-field draft. An import is discoverable even if no named workspace was saved.

Opening any library entry creates a candidate, preserving current applied inputs until explicit replacement. A named candidate carries its descriptor and saved draft together; on selection the descriptor, source, revision and draft are installed as one coherent input state. Saved invalid input may be edited again, but cannot be reviewed/applied as a valid revision without the existing validation. Switching an edited workspace to original settings remains explicit.

Track workspace identity/revision and saved signature separately from Studio request epochs. A save response may acknowledge the submitted snapshot while leaving later typing dirty; it may not rewrite input text. Opening, saving, list updates and deletion must ignore late responses from a different selection, storage root or connection. Conflicts preserve the draft and offer save-copy or fresh open. Cancellation preserves everything. Exit protection includes unsaved Studio workspace title/draft changes, but a successfully saved unchanged draft should be reopenable without relying on a CAD job.

## Two focused integrity repairs

1. **Verified CAD snapshot:** `/api/slice` must use the bytes returned by `JobStore.read_artifact`, not discard them and reopen a path. Both `prepare_slice` and `prepare_project_slice` accept a keyword-only `input_bytes: bytes | None = None`; provided bytes are the sole staged model content. The standalone path-based adapter reads one bounded snapshot and validates/stages that same snapshot. Published Studio project receipts must bind to the job's original recorded model hash. Replacing the model path after verification must either prepare the verified original or fail without publishing a different model.
2. **Existing filament workspace corruption:** validate saved profile workspace rows using their write contract before returning them, with `WorkspaceIntegrityError` mapped to 409. Build/validate the entire browser restoration value before changing epochs, documents, guided edits, controls or saved identity. A corrupt record with an out-of-range target, missing setup fields or wrong snapshot type leaves the current draft intact and reports the error.

## Release evidence

Required evidence is source-bound: full Python/controller tests; real desktop/mobile Chromium scenarios including zero-CAD save/reload/open and invalid drafts; an installed shared wheel on Ubuntu/macOS/Windows with restart, whole backup/restore to a new root, discovery and fresh preparation; the existing four native Studio cases; and independent artifact/public release readback. Claims distinguish fixture, installed-package, browser, native archive and physical-print evidence. Preserve known native diagnostics and screenshot limitations in documentation unless actual new evidence resolves them.
