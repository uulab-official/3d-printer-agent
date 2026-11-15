# Recorded Print Volume Implementation Plan

> **For agentic workers:** Use the existing authorized execution workflow. Steps use checkbox syntax for progress.

**Goal:** Prevent automatic preparation of a generated CAD model whose recorded build-volume comparison fails or cannot be established.

**Architecture:** A pure bounded evaluator is shared through a generated-3MF parser. Studio composition and the application's full-config route rederive reports from verified bytes; UI and persisted receipts consume the same report.

**Tech Stack:** Python 3.12, CadQuery, FastAPI, plain JavaScript, Node.js 22+, Playwright.

**Spec:** `docs/superpowers/specs/2026-11-15-print-volume-design.md`

## Global Constraints

- Preserve source settings, original geometry, typed request boundaries, and existing job identity.
- No printer commands, new paid service, or new dependency.
- Compare upright enclosing rectangles at 0°/90° with 0.000001 mm tolerance; unsupported cases remain unknown.
- A positive comparison is not a completed placement, slice, or physical print.
- Retain readable old archives and invalidate current results on changed input.

## Review Focus

- Concave, crossed, duplicated, nonfinite or malformed bed/exclusion points must not obtain a positive comparison.
- A diagonal-only possibility must not be described as globally impossible.
- Replaced model bytes or altered review data must not retain a positive execution plan.
- A failed new attempt must remove the old current download while preserving historical originals.
- A source change while a request is in flight must not display an obsolete review.

### Task 1: Pure geometry evaluator

Files: `print_agent/print_volume.py`, `tests/test_print_volume.py`.
Interface: `review_print_volume(coordinates, settings) -> dict` per spec.

- [x] Write and run meaningful failing cases for height, 0°/90°, unsupported polygons, explicit exclusions, sentinel constraints, and numerical boundaries.
- [x] Implement bounded recognition, placement enumeration, Korean issues and precise scope.
- [x] Run `python -m unittest tests.test_print_volume -v`.

### Task 2: Enforce server review before preparation

Files: `studio_project.py`, `slicer.py`, `app.py`, dedicated integration tests.
Consumes the pure evaluator; produces `plan.print_volume` and `receipt.print_volume`.

- [x] Reproduce oversized preparation with committed real CAD fixtures before the fix.
- [x] Extract the existing strict generated-model parser without broadening accepted formats.
- [x] Review verified bytes and settings before staging, bind hashes and rederive at execution.
- [x] Require the same check in the manual application path; preserve generic standalone STL adapter behavior.
- [x] Verify no native launch or stale artifact and unchanged geometry/settings after success.

### Task 3: Complete the visible workflow

Files: `static/`, controller tests, new browser tests.
Consumes the report contract from Task 2, preserving existing request identity guards.

- [x] Add failing controller checks, then dimensions/status/rotation/reasons and return-to-edit action.
- [x] Invalidate report with existing result state; distinguish historical reports.
- [x] Fix noninteractive toast pointer interception.
- [x] Exercise blocked source → fitting source → changed-source invalidation in desktop/mobile browsers.

### Task 4: Qualify and record

Files: package qualification script, README, changelog, status and feature guide.

- [x] Extend installed qualification with a passing report and rejected undersized source.
- [x] Run complete required tests, package/install checks and fresh independent code review.
- [x] Commit and push, run same-source CI/package/native gates, resolve failures, and integrate to main under existing authorization.
- [x] Record exact completed scope and remaining hardware/product qualifications; publish only after the existing release gate accepts the same source.

## Execution notes

Baseline `5e60857`: 609 Python tests and 183 controller checks passed locally.
The local execution service disconnected briefly and recovered; the checkout and
baseline evidence survived. Work continues on `feat/print-volume-preflight`.

Local implementation verification completed with **646 Python tests** and **191
controller checks**, JavaScript syntax and clean diff checks. Independent review
found a boundary-value display issue, fixed with nine-decimal volume formatting.
A separate legacy source-receipt regression reproduced an upgrade rejection;
display-only geometry fields now leave canonical persisted inspections unchanged.
Original receipts and revision bytes survive reopening and fresh preparation.

Browser execution is deferred to the required CI gate because this workspace's
Chromium launch is blocked by its IPC policy. Browser discovery finds four new
cases (two workflows on desktop/mobile). Native and three-platform installed
qualification must complete on the exact release source before promotion.


Final main source `ac35c089ee441190b381f7531e60c7d921616352` passed application
CI `43720570098` (646 Python, 191 UI, 54 real Chromium cases), installed package
CI `43720570141` (287 checks on each of three platforms) and native
CI `43720570129` (four synthetic Studio paths), all on attempt 1.
Promotion `43721011244` published v0.8.0 at 2026-11-15 13:50:01 UTC.
The two final comparison screenshots and exact source/wheel bytes were checked.

The extra volume fixture exposed an outdated two-source expected catalog in the
installed qualification harness; the correction verifies preservation of existing
rows before refreshing the three-source snapshot. Fresh final-source evidence is
recorded in `docs/VERIFICATION.md`; earlier incomplete results are not combined.

All seven public release assets were downloaded without authentication. Six
reference files match the qualified originals byte for byte; release evidence
identifies the exact final source, three gate IDs, attempts and success states.
The immutable public tag was independently checked against the source commit.
