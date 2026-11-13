# Filament evidence editor

Date: 2026-11-13. Baseline: `9509c904aebdf788ba78b7701ccc4d05dbd1ec44`.

## Goal and decision

Continue the user's authorized implementation and publication work by removing the need to hand-write an envelope merely to record a filament profile's applicability and source. The implementation scope below is the maintainer agent's decision after inspecting the current contracts, not an additional user-selected specification.

The selected document gets a compact, expandable editor for seven `scope` fields and four `source` fields. These describe the selected profile's supplied evidence and remain separate from the eight current-use setup inputs. There is no automatic copying from current setup, parent metadata, filenames or today's date, and no control that creates positive measurement claims.

## Editing contract

- Extend the existing single pending guided-edit transaction. Numeric settings and evidence share apply/cancel, save/review auto-apply, dirty state, locks and stale-response invalidation.
- Validate every pending replacement before modifying the selected draft. An invalid nozzle or numeric setting leaves all edits pending and the JSON untouched.
- A raw profile becomes `{settings: originalRaw, ...editedEvidence}` only when evidence edits are applied. Rendering, cancellation, unchanged values and numeric-only edits do not wrap it.
- Existing envelopes preserve unknown top-level and metadata keys, validation claims, inheritance and all unedited value representations. Imported `entry.profile`, other documents and archive `origin` remain unchanged.
- Text fields retain explicit text; an empty field removes only that key, explained next to the editor. URL and retrieved-at are plain text records, not fetch or date-normalization operations. Authority permits existing/custom strings.
- A new scope nozzle is one positive finite number. Existing scalar/string/singleton-array representations are preserved. Unsupported legacy fields/groups are visible and read-only, with JSON guidance; do not silently coerce or repair them.
- Saved workspace schema and endpoints remain unchanged. Restoring a workspace restores inputs, not old review results.

## Review contract

Keep `edit_review.status`, `changed_fields` and `field_sources[*].edited` about resolved effective settings. Add `evidence_status` (`compared` or `untracked`) and `evidence_changes` for the selected target's own scope/source/validation fields.

Compare each group's immediate keys by canonical JSON. Raw/missing groups are empty; a missing key differs from explicit null. Record `path`, `before_present`, `after_present`, and independent deep copies of present `before`/`after` values. Unknown keys count. A uniquely identifiable selected target on each side permits evidence comparison even when a parent is missing; missing/ambiguous targets remain untracked. Parent metadata never becomes child evidence.

Effective setting changes retain the existing validation invalidation policy. Scope or validation changes also make a currently positive claim stale, with an explicit evidence-change reason. Source-only corrections do not invalidate matching measurements. Lowering a claim to unverified remains unverified. Preserve original/current claim objects, maintain stronger blockers, and do not fabricate a review for an unresolved report. Baseline-unresolved behavior stays conservative.

## Acceptance and limits

Controller tests cover atomic apply/cancel, wrapping and type preservation, originals/origins, unsupported input, pending locks and races. Backend/API tests cover additive comparison, selected-target isolation and validation policy. Real desktop/mobile browser flows cover source/scope entry, mixed pending edits, saving/reopening, review/report contents and layout. Run existing Python, controller, package and native regression gates; inspect actual CI artifacts before recording success.

This milestone records user-supplied evidence. It does not authenticate a publisher, fill native Studio defaults, perform calibration, qualify a real material, add native execution support or print hardware.
