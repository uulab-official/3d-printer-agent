# Studio filament setting revisions — v0.5 design

## Intent and authorization

Continue the user's authorized production implementation and main/release delivery. The user wants help with difficult filament settings and a usable path through CAD and Bambu Studio. v0.4 can preserve a Studio project's global settings, but editing a separate filament report does not affect that project. This increment lets a person deliberately edit six settings of their supported project, inspect the differences, and prepare the current CAD with those values.

Implementation choices below are the assistant's decisions under the standing request to continue. They are not additional user requirements. Preserve the existing Python local application and dependency-free Korean UI; no new service, provider or paid dependency is needed.

## Approaches and chosen scope

1. Convert the separate filament report into a native preset: rejected for this increment. A report lacks the complete machine/process/project configuration and applicable native inheritance contract.
2. Rewrite and reimport the supplied archive: rejected. It would obscure the immutable original and introduce unnecessary copies of source geometry and cached G-code.
3. **Selected:** immutable setting revision recipes rooted in the verified original. Derive effective settings on the server, keep the original archive, and reuse current-CAD composition and native readback.

Direct controls live in the Studio-project section. They do not convert or modify the separate filament workspace. A revision is reusable from its prepared job's history; a standalone preset library is outside this increment.

## Supported edits and official schema evidence

The source must already pass the existing Studio `02.09.01.70`, FFF, single-filament/nozzle/active-extruder contract. Changing settings cannot repair or relabel an unsupported source. The plate, printer, material name, nozzle diameter, G-code, topology, process settings and unknown keys are not editable here.

| Public field | Native setting | Accepted user text |
|---|---|---|
| `nozzle_temperature` | Same key | Integer 1–360 °C |
| `nozzle_temperature_initial_layer` | Same key | Integer 1–360 °C |
| `filament_flow_ratio` | Same key | Decimal greater than 0, at most 2 |
| `filament_max_volumetric_speed` | Same key | Decimal greater than 0, at most 200 mm³/s |
| `bed_temperature` | `<selected_plate_prefix>_temp` | Integer 1–120 °C |
| `bed_temperature_initial_layer` | `<selected_plate_prefix>_temp_initial_layer` | Integer 1–120 °C |

All native values stay one-element string arrays. Bed aliases map only through the original `curr_bed_type` and existing `PLATE_BED_PREFIXES`. No plate switching, aliases for other plates or zero-as-supported conversion. Integer fields accept decimal digits only; decimal fields accept decimal digits with an optional complete fractional part of at most six digits. Bound text to 32 characters; reject signs, exponent notation, booleans/numbers/null/arrays/objects, blanks, partial numbers and nonfinite values. Leading/trailing whitespace may be stripped, but unfinished text is retained in the browser on error. Canonical changed values use plain decimal notation with insignificant trailing zeros removed. Numerically unchanged submissions preserve the exact original native value and do not create a change.

The pinned official [PrintConfig.cpp](https://github.com/bambulab/BambuStudio/blob/56a57d00a591360cf41bf21383915ee5bf357be5/src/libslic3r/PrintConfig.cpp), Git blob `f5f7e77f7354fc992f5117acc9d32341e5eaf1ae`, declares `max_temp = 360`, nozzle `coInts`, flow maximum 2, maximum volumetric speed maximum 200, and all five selected-plate pairs as `coInts` with maximum 120. The app retains its existing strictly positive core/selected-bed requirement. These are supported input/schema bounds, not measured hardware limits, material recommendations or manufacturer certification. A changed value is always `user_selected`.

Existing source receipts and public source inspections retain their v0.4 shape. A new editor response can explain an unsupported editable-field representation without changing how the original archive is stored or inspected.

## Pure derivation contract

New `print_agent/studio_settings.py` is a standard-library-only policy/derivation module. It may use the existing bounded Studio settings parser and assessment. It must never execute native code, write files or mutate its inputs.

- `settings_editor(snapshot: dict) -> dict`: return `schema_version`, `source_sha256`, `settings_sha256`, `fields`, `source_summary`, and `warnings`. Each field has `key`, `native_key`, Korean `label`, `unit`, `kind` (`integer` or `decimal`), `original` (the original native array's string), canonical string `value`, numeric `minimum`/`maximum`, and boolean `exclusive_minimum`. Temperature minimum is 1 inclusive; decimal minimum is 0 exclusive. Do not return arbitrary raw settings or expected native commands.
- `derive_settings(snapshot: dict, proposal: dict) -> tuple[dict, dict]`: verify the original snapshot and the proposal's exact keys `source_sha256`, `settings_sha256`, `values`. `values` maps only the six public keys to strings. Return an effective snapshot and a public review.
- The review has `schema_version: 1`, `source_sha256`, `settings_sha256`, `effective_settings_sha256`, canonical changed-only `values`, ordered `changes`, `changed_count`, `provenance: "user_selected"`, `effective_summary`, `review_sha256` and explanatory warnings. Each change has `field`, `native_key`, exact native `before` and `after` arrays. Hash an identity containing exactly `schema_version`, `source_sha256`, `settings_sha256`, `effective_settings_sha256`, `values`, `changes`, `provenance`, using UTF-8 `json.dumps(..., ensure_ascii=False, allow_nan=False, sort_keys=True, separators=(',', ':'))` without a trailing newline. Exclude presentation text. Changes follow the six-field table order.
- With no actual changes, preserve the exact original settings text/hash. Otherwise deep-copy parsed settings, replace only allowed keys, serialize deterministically as UTF-8 JSON, reassess the complete configuration, and update the effective snapshot's settings text/hash, summary and native expectations. All unedited JSON values must be deeply equal; none may be added or removed. Source archive identity and producer remain those of the original.
- `make_revision(snapshot, proposal, *, source_id, revision_id, created_at, review_sha256) -> dict`: verify UUID hex IDs, an aware ISO timestamp, nonzero changes and the supplied review hash, then return the immutable record below. This is a pure constructor, not a filesystem publication.
- `verify_revision(snapshot, revision, *, source_id) -> tuple[dict, dict]`: require the exact record schema, source ID and types, rederive from the original and compare all recorded identity/change fields. Return the effective snapshot and review; reject contradictions.

Record schema: `schema_version: 1`, `revision_id`, `created_at`, `source_id`, `proposal` (the canonical three-key proposal), `review_sha256`, `effective_settings_sha256`, `changes`, `provenance: "user_selected"`. No parent chains: every revision describes the full current set of overrides relative to one original source. A zero-change review is allowed; a zero-change stored revision is rejected, and the UI can explicitly return to the original instead.

Extend `build_project_3mf(model_bytes, snapshot, *, settings_revision=None, source_id=None)` without weakening the existing no-revision validation. The supplied snapshot is always the ORIGINAL. For a revision, use `verify_revision` and build with its effective settings. The original/source metadata remains original; add revision ID, review hash and original/effective settings hashes to the derivative's metadata. The changed receipt sets `settings_preserved: false`, records original/effective identities, changes and revision ID. The existing `settings_sha256` identifies the effective embedded bytes. No-change preparation still preserves original settings bytes; the app modifier becomes version 0.5.0, so whole-archive byte equality across app versions is not claimed.

## Immutable storage and API

New `StudioSettingsRevisionStore(root, sources)` in `studio_revisions.py` uses `studio-settings-revisions/<server UUID>/revision.json`. Validate fully before exclusive directory creation; atomically publish the complete JSON record, bounded to 64 KiB. Never overwrite a collision; remove only its own failed publication. Every read revalidates the record and referenced original. Source IDs and revision IDs, never filenames, control paths. No SQLite schema or backup format change.

- `create(source_id, proposal, review_sha256) -> public envelope`.
- `read(revision_id) -> (original_snapshot, original_bytes, revision_record)`.
- `get(revision_id) -> public envelope` with exactly `revision`, `review`, `source` (the existing public source with ID/archive URL).
- Missing source/revision returns 404; stored tampering returns 409; invalid proposals, unsupported source/field/value and review mismatch return 422. Invalid input publishes no revision and does not change the original.
- `GET /api/studio-projects/{source_id}/settings` returns the editor descriptor plus `source_id`.
- `POST /api/studio-projects/{source_id}/settings/review` accepts the three-key proposal and returns the review plus `source_id`.
- `POST /api/studio-projects/{source_id}/settings/revisions` accepts the three-key proposal plus `review_sha256`, returns the public envelope with status 201.
- `GET /api/studio-settings-revisions/{revision_id}` returns the reverified public envelope.
- `POST /api/slice` adds `studio_settings_revision_id`; exactly one of that, `studio_project_id`, or `config_bundle` must be present. The revision determines its original source. Keep existing request budgets and local session/origin controls. Browser-provided snapshots, paths, receipts, commands or before-values are never accepted.

## Native plan and recovery

Extend `prepare_project_slice(..., *, source_id=None, executable_path=None, settings_revision=None)` using the existing positional arguments. Reinspect original bytes, verify any revision against that original, and build the current CAD. New plans expose `settings_revision` and `settings_review` separately from original `project_source`. A no-revision plan may leave these null.

For a revision, stage `settings-revision.json`, include it in the exact file inventory and hashes, and bind revision identity in preparation metadata/receipt. `_validate_project_plan` reconstructs original → verified recipe → effective settings → exact prepared archive both before and after executable probing. Never trust recorded effective values alone. Compare native output to the EFFECTIVE pre-execution settings using the unchanged complete-setting and geometry checks. Original→effective changes remain a separate report; native differences are not exempt merely because a user edited a field.

Job history retains source, revision, review and prepared download. Reopening restores recorded information, not permission to execute an old plan. Reverify the source/revision and require fresh preparation. A new attempt, interrupted operation, tampered original/revision or changed draft detaches previous current results. Verified prepared files remain separately downloadable after native failure, according to the existing contract. Backup captures revision files and original/prepared artifacts; restore to a different directory must allow a fresh preparation using the same revision ID.

## UI behavior

The Studio source summary gains an explicit settings editor. Opening obtains the server descriptor; fields show original and proposed values with units, contextual labels and the selected plate. Do not show implementation IDs in the primary flow. An optional details area may expose hashes and revision origin.

Keep three separate concepts: unfinished input strings, a reviewed candidate change set, and the currently applied original/revision. User action sequence is edit → review differences → apply → prepare current CAD. Cancel preserves the previously applied selection. Reset-to-original is explicit. A source replacement with unfinished Studio edits must offer an explicit keep/replace choice; existing manual JSON and separate filament drafts are never overwritten.

Any changed edit string invalidates stale preview/download and native execution eligibility. Subsequent editing invalidates its previous review. Bound descriptor/review/create/revalidate responses to source identity, edit revision, model/context, storage path and connection epoch. Cancel, newer edits/selections and reconnect must make late success/error responses inert. Preserve exact invalid text and recoverable drafts on errors; no automatic replay of creates or slices after reconnect. All pending/unapplied changes participate in existing exit protection.

Recorded history shows the source and original→effective differences. Rechecking an edited record retrieves its stored revision, then presents a candidate for explicit selection. It must not silently select the bare original, lose overrides or use an old execution plan. No-revision v0.4 jobs retain their existing behavior.

## Evidence and release gates

- Behavioral tests first for allowed edits, atomic multi-field rejection, source/review mismatch, decimals/types/size bounds, all plate mappings, no-op byte preservation, unchanged unknown keys, and recipe/plan tampering.
- Store/API tests use real temporary files and the existing HTTP boundary: collisions, incomplete publication, missing/tampered sources/records, unchanged originals, restart and backup/restore, exclusive source choices and invalidation of old artifacts.
- Controller scenarios cover invalid exact strings, explicit apply/cancel/reset, stale responses and source/model/connection changes, history/recovery and exit protection. Add actual desktop/mobile browser workflows with retained original/CAD/changed project/revision/review bodies and screenshots, including real server restart.
- Preserve the three existing native cases. Add a FOURTH production project case changing all six values on the same actual native-produced synthetic source, preparing different current CAD, and independently checking changed values, every unedited value, all normalizations and actual mesh/G-code.
- Extend the single-wheel three-OS qualification with edited preparation/download/restart/history, backup/restore of the revision, and fresh preparation after restoration. Record actual bytes and source; no local native/Chromium retries or escalation.
- Set 0.5.0, update user and maintenance docs, independently review the change, commit/push with expected-head protection, observe all three same-source gates, and verify the automatically published wheel and public assets. Follow with documentation-only observed evidence.

Captured GUI exports, physical hardware/printing, manufacturer recommendations, new Studio versions, live LLM quality, arbitrary presets, shopping feeds, MakerWorld and hosted pairing are not established by this increment.
