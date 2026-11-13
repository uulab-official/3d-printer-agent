# Saved filament workspaces and guided edits

## Goal

Complete the local workflow: import a child and its parents, edit a common setting without rewriting JSON, save, reload, reopen, review again and download evidence. Preserve originals and exact unfinished drafts. The user has authorized implementation and publication to main.

## Storage and API contract

A separate `ProfileWorkspaceStore` stores whole snapshots atomically in SQLite under the configured data directory. CAD jobs remain separate. Workspace records contain `id`, `title`, `revision`, `created_at`, `updated_at`, and `snapshot`; list entries omit the snapshot and include `document_count`. IDs are UUID hex strings. Updates and deletes use an expected revision and return HTTP 409 on conflict.

Snapshot version 1 contains exactly:

```json
{
  "schema_version": 1,
  "documents": [{"filename": "child.json", "profile": {}, "draft_text": "unfinished JSON is allowed"}],
  "target_index": 0,
  "profile_text": "",
  "setup": {
    "printer_model": "", "printer_preset": "", "nozzle_diameter": "",
    "plate_type": "", "extruder": "", "feed_mode": "",
    "material_id": "", "material_identity_status": "unknown"
  }
}
```

`profile` is the unmodified imported JSON object. `draft_text` preserves the exact editor text and need not parse. `profile_text` is used only with an empty document collection; with documents it must be empty. There are at most 64 documents, a valid target index (zero for an empty collection), eight known string-valued setup fields, and a trimmed title of 1–120 characters. Original documents retain the existing 2 MiB aggregate bound. The entire snapshot is limited to 8 MiB and JSON depth 64; no nonfinite numbers or integers that browser JSON cannot preserve. No review is restored as current.

Routes:

- GET `/api/profile-workspaces` → `{workspaces: [summary, ...]}`.
- POST `/api/profile-workspaces` with `{title, snapshot}` → record.
- GET `/api/profile-workspaces/{id}` → record.
- PUT `/api/profile-workspaces/{id}` with `{title, snapshot, expected_revision}` → next record.
- DELETE `/api/profile-workspaces/{id}` with `{expected_revision}` → `{deleted: true, id}`.

The existing local session, origin and JSON boundary protects writes. Workspace writes and profile resolution with baseline evidence have an 8 MiB HTTP bound; normal endpoints keep 2 MiB. Each current and baseline resolver document set still has its own 2 MiB bound.

## Editing and evidence

Guided controls cover nozzle and first-layer nozzle temperatures, flow ratio, maximum volumetric speed, and the selected plate's two temperatures. They edit only the selected draft, retaining envelope metadata, unrelated fields and `inherits`. Scalar/singleton-array and numeric/string representations are preserved. Multi-value arrays remain advanced-only. An empty control does not become zero or a fabricated default. Removing an override deletes only the selected field; restoring the original and removing one document are explicit operations.

The guided editor operates on imported document records. A pasted JSON document can explicitly become a document record before guided editing, making its initial user-supplied content the local comparison baseline. These originals are evidence of what the user supplied, not authentication of a publisher or a measurement.

The resolver accepts optional `baseline: {documents, target_name}`. It compares the selected original chain's effective settings with the edited chain, independent of JSON key order. Its report includes `edit_review` and preserved imported documents. Changes to unused documents do not invalidate the selected chain's validation claim. Changed effective settings, or an unavailable original baseline, invalidate any positive supplied validation claim; the original claim is retained in evidence. A new review must not reinstate the old validation label after an ancestor edit. Standalone review without a baseline keeps the existing reported-claim semantics.

## Interaction guarantees

- Explicit save, save-as-copy, open and delete; show unsaved changes.
- Save/open/delete failures retain current input. Conflicts never force overwrite.
- An edit during save remains unsaved. An edit or workspace switch during load cannot be overwritten by a late response.
- Opening or deleting work that would lose local edits requires an in-product confirmation.
- Restoring a workspace restores inputs and invalidates old review/downloads.
- Import, target changes, edits, removal and restore use the existing revision invalidation rule.

## Verification

Behavior tests cover persistence across store/app restarts, malformed draft round trips, atomic revision conflicts, bounds and mutation protection. Controller tests cover numeric shape, inherited overrides, originals, stale saves/loads and dirty state. Real Chromium CI covers save/reload/open/review/download on desktop and mobile. Reproduce and fix validation claims surviving inherited edits. No native Studio, live LLM or physical-print qualification is implied.
