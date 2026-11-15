# Recorded print-volume review

## Intent

Continue the authorized production-readiness work on the existing local application.
A supported Studio source currently permits preparing a 120 × 80 × 35 mm model
against a recorded 10 × 10 × 5 mm build volume. Correct that gap before any native
attempt, and show the next useful action in the Korean UI.

## Decisions

Keep the existing Python/CadQuery and dependency-free browser architecture. Derive
dimensions from the verified generated 3MF bytes, not browser input or cached job
dimensions. Review the actual original/effective settings on every preparation.
The Studio composition boundary enforces this itself. The application's manual
full-config path also requires the review; the standalone adapter remains usable
for legacy external STL inputs without claiming that they were reviewed.

The pure evaluator recognizes an axis-aligned rectangular outer area, rectangular
exclusions in groups of four points, and upright 0°/90° bounding-box placements.
It handles translated and negative-origin rectangles, clockwise/counterclockwise
perimeters, and an optional closing point. It never infers a rectangle from an
arbitrary polygon's bounding box. A bounded candidate search provides a placement
witness outside explicit rectangular exclusions. It does not change the model.

Use the statuses `fits`, `height_exceeded`, and `needs_review`. Height overflow is
definitive for this upright path. Failure at 0°/90° does not prove that all diagonal
placements are impossible. Unsupported polygons or unresolved extruder/wrapping
geometry require review. A report permits automatic preparation only when
`can_prepare` is true. Absolute comparison tolerance is 0.000001 mm; there is no
implicit physical clearance or automatic scale change.

The pinned upstream source is Bambu Studio commit
`56a57d00a591360cf41bf21383915ee5bf357be5`. `PrintConfig.cpp` declares a single zero
point as the default bed exclusion and zero as default optional extruder height;
`Print.cpp` consumes complete groups of four exclusion points. Empty/absent values
and the observed default sentinels imply no explicit additional region in this
bounded comparison, not measured hardware freedom. Nontrivial unsupported
per-extruder geometry remains unknown.

## Report and lifecycle

`review_print_volume(coordinates, settings)` returns schema version 1, status,
`can_prepare`, `scope: upright_bounding_box_0_90`, three model dimensions, three
recorded volume dimensions (null where unknown), per-orientation outcomes,
optional placement witness and rotation, `placement_applied: false`, structured
issues, limitations, and tolerance. The generated-CAD wrapper adds model and
settings SHA-256. The plan and successful preparation receipt retain this report.
Execution rederives the report and rejects changed/deleted review data. Historical
downloads remain readable; historical plans are not promoted to current reviews.

A rejected preparation stages no new project or native execution. The existing
slice-attempt lifecycle invalidates old current downloads. The UI displays a
compact comparison, clear blockers and a direct route back to model dimensions.
Changing CAD, settings, source, or connection clears the displayed current report.
Noninteractive toast feedback must not intercept the next pointer action.

## Scope and alternatives

The chosen bounded geometric check is deterministic and testable without hardware.
Delegating the entire decision to native Studio leaves the demonstrated bad
preparation downloadable and requires an installation. A general polygon packer
would add substantial geometry and placement semantics beyond this release.
Brims, skirts, supports, purge structures, movement clearances, material suitability,
actual native placement and physical printing remain separate checks. Source
settings and original geometry are preserved exactly.

## Acceptance

Reject the demonstrated height/bed cases without staging; prove normal and 90°
fits; handle exclusions, boundaries, negative origins, diagonal counterexamples,
malformed inputs and unsupported areas; preserve geometry/settings identity;
reject forged/stale reports; exercise both application preparation modes and the
desktop/mobile review flow. Run Python, controller, package and native regression
gates, recording observed results rather than extrapolating hardware qualification.
