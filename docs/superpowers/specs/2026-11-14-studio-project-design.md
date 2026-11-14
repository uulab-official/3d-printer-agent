# Studio Project Settings Design

Date: 2026-11-14. Baseline: `9ded114ea401deee47d4e6c2096ae55d9f05a18e`. Target: 0.4.0.

## Intent

A beginner who already has a working Studio project should be able to bring its recorded printer, material and global print settings into the current app-generated CAD without locating three flattened configuration JSON files. The original archive, original model and imported settings remain distinct from the new CAD and native result. The user has authorized continued implementation, verification and main publication; the choices below are implementation decisions, not new user requirements.

## Approaches

1. Expand the explicit filament resolver into Studio's complete machine/process/filament defaults, include, variant and migration engine. This would require a substantially broader version-specific compatibility implementation.
2. Patch the existing full-config bundle from a reviewed filament draft. This preserves an expert route but still requires the beginner to locate the same full JSON files, and needs an additional baseline/diff contract.
3. Import a saved Studio project's merged global settings and compose a new project with the current validated CAD. **Selected**, subject to actual native qualification. This uses an existing user's snapshot and gives them a single-file workflow. Per-object/per-plate overrides, source geometry and painting do not transfer.

The separate filament editor and its `full_config: false` reports remain unchanged. Native defaults or manufacturer values are never invented from those reports. A later audited edit bridge can build on this source identity.

## Native prerequisite

The official CLI loads complete project settings from a 3MF. Its exported project JSON has `from: project`, not a loadable machine/process/filament role. Do not relabel it or remove inheritance metadata to force the existing bundle path.

Pinned source: BambuStudio `56a57d00a591360cf41bf21383915ee5bf357be5`, runtime `02.09.01.70`; see `src/BambuStudio.cpp` and `src/libslic3r/Format/bbs_3mf.cpp`. The CLI treats the original Application metadata differently for Bambu and foreign projects. An isolated native experiment must choose the qualified composition before product code is frozen. Prefer an honest new Application marker if the actual runtime supports it. If a derivative needs to preserve a source compatibility marker, require that exact marker in the supplied source, preserve it rather than manufacture it, record its origin, and add explicit modifier/source/model metadata. Do not claim the new geometry was authored in Studio.

The experiment must distinguish original cube geometry from new cable-comb geometry, inspect nonempty G-code, compare 30 independent core settings, and record every project-settings roundtrip difference. A successful exit alone is insufficient. Native identity/composition details are finalized from that observation in the implementation ledger.

## Supported input and data contract

- Input: a user-selected `.3mf`, at most **16 MiB compressed**, **128 MiB expanded**, **4,096 ZIP entries**, **2 MiB settings JSON** and **2 MiB root model XML**. The complete JSON import request is at most **24 MiB**; existing endpoints retain their current budgets.
- Verify every ZIP member's actual bytes/CRC and declared structure within the bounds, including ignored members. Reject encrypted/unsupported compression, duplicate or escaping names, hidden/trailing payloads, links and special files. Ordinary empty directory entries may be accepted. Do not extract arbitrary members to disk.
- Require a valid UTF-8 `Metadata/project_settings.config` object without duplicate keys, nonfinite values or excessive depth. Require the supported producer/format metadata in `3D/3dmodel.model`; reject XML DTD/entity declarations and malformed metadata. A filename or Application marker is a format claim, not publisher authentication.
- Initial qualified scope: Studio **02.09.01.70**, FFF, **one filament, one nozzle and one active extruder**. Preserve complete global settings text exactly. Inspect required native core settings, explicit plate, printer/process/material identity and positive selected-bed temperatures. Unsupported versions or multiple materials/extruders return actionable unsupported inspection results; malformed input fails atomically.
- No host post-processing programs, browser-selected executable paths or arbitrary command arguments. Native G-code settings remain inert configuration data; the app never sends a print job.

`inspect_studio_project(filename: str, content: bytes) -> dict` returns:

```text
schema_version: 1
source: {filename, bytes, sha256}
producer: {application, format_version, settings_version}
settings_text: exact decoded UTF-8 bytes
settings_sha256: SHA-256 of the original settings bytes
summary: {printer_model, printer_preset, process_preset, nozzle_diameter,
          plate_type, filament_name, filament_type, nozzle_temperature,
          nozzle_temperature_initial_layer, bed_temperature,
          bed_temperature_initial_layer, filament_flow_ratio,
          filament_max_volumetric_speed}
expected_settings: core native readback map
supported: boolean
issues: [{code, message, field?}]
warnings: [string]
```

Summary values retain recorded strings/scalar representations rather than inferring exact physical hardware or SKU. `settings_text` and `expected_settings` stay in the internal snapshot, not the normal public inspection response. Inspection is available without installed Studio or a generated model.

## Source storage and HTTP

`StudioProjectStore` in `print_agent/studio_sources.py` owns immutable input archives under `<data>/studio-projects/<uuid>/`, plus a versioned receipt. Only the server chooses IDs and paths. Writes publish complete new records; collisions, failed writes, symlinks and changed bytes cannot replace existing sources. Reads verify the receipt and re-inspect the original bytes. No new SQLite schema is needed. Existing full-workspace backup includes these files automatically.

- `import_project(filename, content) -> public inspection with source_id`.
- `get(source_id) -> public inspection`; `read(source_id) -> (internal snapshot, original bytes)`.
- `archive(source_id) -> (original filename, original bytes)` for verified download.
- `POST /api/studio-projects/import` accepts `{filename, content_base64}` under the existing session/origin boundary.
- `GET /api/studio-projects/{source_id}` verifies and returns the inspection.
- `GET /api/studio-projects/{source_id}/archive` returns the exact verified original.
- Extend `/api/slice` to accept **exactly one** of existing `config_bundle` or `studio_project_id`, alongside `job_id` and `execute`. Do not accept client snapshots, filesystem paths or execution plans. Existing bundle requests keep their behavior.

## Derived project and native plan

`build_project_3mf(model_bytes: bytes, snapshot: dict) -> tuple[bytes, dict]` is deterministic. It accepts only the app's supported generated millimeter 3MF with one mesh/build instance; it preserves mesh topology and dimensions. It combines that model with the exact global settings text and the qualified minimum container/plate metadata. It does not copy the source model, object/plate overrides, painting, thumbnails, cached slice/G-code or per-height scripts. Source and modifier metadata plus a derivation receipt identify this distinction.

`prepare_project_slice(input_path: Path, job_dir: Path, source_filename: str, source_content: bytes, *, source_id: str | None = None, executable_path: str | None = None) -> dict` creates a separate `kind: studio_project` plan. It stages the original source, original generated CAD, derived project and receipt in a new job directory, with complete file hashes. The plan retains source/summary identity and source ID for reopening. It includes `project_prepared`, `project_path`, `project_sha256`, `project_receipt`, `ready`, fixed argv and expected settings.

Project composition and a verified `prepared_three_mf` download work even when Studio is missing. `ready` refers to native execution readiness, not composition. Native execution additionally verifies the exact qualified version and advertised options. It rechecks staged bytes, snapshot, expected settings, geometry derivation and fixed arguments before execution. Both success and failure preserve source evidence; stale previously sliced files are detached at the start of a new request. Existing role-bundle plans remain supported.

`JobStore.record_slice` records a prepared-project receipt independently of a sliced-output receipt. The new artifact kind is `prepared_three_mf`; it is never labeled a sliced/print-ready file. Download and job ZIP verification use the same byte-receipt rules as existing artifacts, including historical jobs with legacy receipts. Interrupted preparation never exposes a partial artifact. Job history retains source identity, summary and source ID but does not auto-replay native work.

## User flow and state

Add a primary project-import section to the existing model page's Bambu card. Keep manual full JSON input under an advanced disclosure. Show filename and recorded printer, nozzle, plate, material and process in a compact stacked summary, with hash/version details available. Explain that these are project records, not measurements of the installed printer, and only global settings transfer.

The state distinguishes a newly inspected candidate from the applied source and any manual bundle text. A candidate does not automatically replace a prepared plan. Explicit apply/replacement/cancel preserves exact prior text and imported material drafts. A malformed/unsupported import leaves previously applied input available and identifies which candidate failed. Import can precede model generation or native installation. The action to compose requires a supported source and the current validated CAD; native execution remains separate and explicit.

Bind asynchronous responses to file selection revision, source identity, current model ID/hash, slice context and connection epoch. New selection, cancellation, model change or reconnect makes older successes **and errors** ineligible. Model replacement can retain the selected source as input but requires new preparation; old downloads must not appear current. Reconnect preserves input and never resubmits a mutation. A changed storage directory detaches source handles until explicit revalidation/reselection. Unapplied source changes, replacement choices and active imports receive page-exit protection.

History shows the recorded source and prepared/sliced state; selecting its source re-verifies the original archive. Opening history alone cannot enable execution. Prepared and sliced downloads have distinct labels.

## Small accompanying routing correction

Explicit material and purchase requests use the existing deterministic tab actions in both template and LLM modes before contacting a model provider. This fixes mode-dependent navigation without expanding the typed tool boundary, exposing keys or claiming a live LLM evaluation.

## Verification and completion

Use test-first behavior checks for archive boundaries, exact settings/geometry preservation, source immutability, prepared-artifact verification, unsupported versions/multiple materials, request choice/session limits, changed/late input and cancellation. Keep changes in separate owned files and perform independent implementation review before integration.

Actual CI must include new browser workflows at desktop/mobile sizes, a new native project-source path with different source/current geometry and independent readback, and installed-package source/import/preparation/download/history/backup/restore checks on three OSes. The original native smoke alone does not qualify the new path. Run full Python/controller and installed-wheel checks before main delivery; the release workflow must publish exactly the new qualified wheel. Record exact source hashes, test counts, CI runs, release assets and remaining limits.

No hosted site, general PC control, manufacturer preset resolution, external model geometry import/remix, real LLM-provider quality or physical printing is claimed by this release. No new paid service or cloud runtime is required. Known local Chromium/native runtime restrictions are not retried or escalated.
