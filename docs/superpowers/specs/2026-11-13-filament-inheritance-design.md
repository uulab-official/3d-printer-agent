# Imported filament inheritance design

Date: 2026-11-13 (Asia/Seoul).

## Goal and scope

Continue the accepted filament-settings milestone with a usable local workflow: import related JSON presets, select a target, resolve its supported explicit inheritance, inspect each value's origin and overridden values, and review it against the user's hardware conditions. User authorization includes implementation, commits and publication to main.

This iteration resolves values explicitly present in supplied files. It does not synthesize Studio's built-in defaults, certify a full slicer configuration, authenticate publishers, handle physical printing, or download presets automatically.

## Approach

Selected implementation choice: resolve uploaded documents locally in a pure Python module and reuse the existing profile reviewer. Remote preset lookup would need source/version management; driving a native Studio installation would require platform qualification. Those remain later steps. The existing FastAPI app and dependency-free Korean UI remain the foundation.

## Input contract

POST /api/profiles/resolve accepts documents (1–64 objects with filename and profile), target_name (the exact settings.name), and setup. A profile is either a raw filament preset or the existing settings/scope/source/validation envelope. The existing 2 MiB request limit applies; the pure resolver checks the same serialized bound. Filenames are labels only and are never opened as filesystem paths.

Profiles need unique, exact names. Each present type must be filament. Inheritance follows one exact parent name, without alias, filename, ID, case or fuzzy fallback. Empty or omitted inherits ends the chain. Maximum chain depth is 32. The complete JSON payload is limited to 64 nesting levels before recursive copies or profile review.

Parent values are overlaid by child values, with whole-value replacement for supported arrays and objects. Nonempty include, variant-related settings, nil or null setting values, noncanonical casing of reserved metadata, non-string inherits, cycles, duplicate names and unsupported types block resolution. A missing target or parent returns needs_input with the missing name. Missing defaults and scope are never fabricated.

Target-only identity metadata: name, type, from, version, setting_id, instantiation, url, user_id, base_id, updated_time, is_custom_defined, alias, renamed_from, filament_settings_id. Other explicit values, including description and filament_id, follow supported inheritance. Nonempty compatibility condition expressions remain subject to the existing review gate.

## Output contract

resolve_profile_documents(documents, target_name, setup) returns:
- schema_version: 1; status: resolved, needs_input or blocked; target_name.
- documents: original filename/profile pairs plus sha256 of canonical JSON (sorted keys, UTF-8, compact separators). This is not the original file-byte hash.
- chain: root-to-target entries with name, filename and sha256, empty unless resolution succeeds.
- field_sources: field to preset_name, filename, sha256, inherited and history; history preserves every explicit assignment with its value in root-to-target order.
- resolved_profile: target envelope with resolved settings, or null on failure. The chain directives are omitted only after complete supported resolution; the original documents retain them.
- review: existing evaluate_profile result, or null when resolution fails.
- issues: code/message entries; warnings: strings.
- full_config: false and native_verified: false on every result.
- setup: a preserved copy of the submitted hardware conditions so the review is reproducible.

Scope, publisher and validation claims come only from the target envelope; ancestor claims are not promoted. Resolving a chain is independent of readiness, compatibility or physical validation.

## UI and lifecycle

The existing file input accepts multiple JSON documents. A labeled target selector chooses the editable target; users may add missing parent files and clear the collection. The standard review action uses the resolve endpoint when files are loaded and the existing review endpoint for pasted standalone JSON.

Show missing parent names or blockers, root-to-target chain, setting/value/source table and expandable assignment history. A downloadable evidence JSON contains the originals and computed result. It is labeled a review report, not a Studio-importable full preset.

Changes to the target JSON, target selection, imported files or hardware inputs immediately invalidate prior results and downloads. Asynchronous file reads and API responses must not restore stale results. Imported JSON is rendered with textContent. A failed import preserves the previous editable input, makes the failure visible and leaves no stale successful result.

Each file has an editable draft. The API documents represent the submitted drafts; the UI download additionally includes imported_documents (the initially parsed uploads) and edited_filenames. Clearing the collection keeps the current editable JSON available for standalone review.

## Evidence and qualification

Official implementation reference: bambulab/BambuStudio commit 930fe93851afbc76b1c64dd37d8728b6a9afc89c, Config.cpp metadata parsing, Preset.cpp inheritance/variants, Config.hpp nil application, and PresetBundle.cpp default initialization. Detailed source links will be recorded in docs/FILAMENT_PRESETS.md.

Behavioral tests cover resolution and blockers, API request boundaries, UI invalidation, and desktop/mobile import-to-report workflows. Synthetic settings are marked as fixtures and never described as manufacturer recommendations.
