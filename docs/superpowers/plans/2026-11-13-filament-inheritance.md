# Imported filament inheritance Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** Let a user import related filament JSON files, inspect supported explicit inheritance and its evidence, and review the result for their setup.

**Architecture:** A pure resolver returns a report and invokes the existing profile reviewer. FastAPI exposes one bounded endpoint. The existing UI imports/selects documents, displays provenance and exports the report without applying it to a printer.

**Tech Stack:** Python 3.12, FastAPI/Pydantic, plain JavaScript, unittest, Playwright.

**Spec:** docs/superpowers/specs/2026-11-13-filament-inheritance-design.md

## Global Constraints

- Preserve original documents and values; no inferred defaults or publisher verification.
- 1–64 documents, 2 MiB total serialized input, maximum chain depth 32, JSON nesting depth 64.
- Full config and native verification remain false.
- No native printing, arbitrary paths, shell commands or additional runtime dependencies.
- Publish to main after checks; respect concurrent remote changes.

## Review Focus

- Duplicate or differently cased names/metadata must not silently select a parent.
- Include, nil and variant-dependent values must not look fully resolved.
- Parent identity/scope/measurement claims must not become target claims.
- A late file-read/API response must not revive a result after the user edits inputs.
- Report downloads must contain exact supplied values and no stale setup evaluation.

### Task 1: Pure resolver and behavior tests

Files: print_agent/preset_library.py; tests/test_preset_library.py.

Interface: resolve_profile_documents(documents: list[dict], target_name: str, setup: dict) -> dict, with the exact response fields in the spec.

- [x] Write tests for root/child/grandchild overlays, whole-array replacement, assignment provenance, original preservation and target-only claims.
- [x] Demonstrate tests failing before the implementation.
- [x] Implement resolution, canonical hashes, exact graph validation, bounds and actionable blockers.
- [x] Test missing/duplicate names, cycles, depth, unsupported include/variants/nil/null, reserved-key casing and malformed input.
- [x] Run python -m unittest tests.test_preset_library -v and review evidence semantics.

### Task 2: API and imported-profile UI

Files: print_agent/app.py; print_agent/static/index.html; print_agent/static/app.js; print_agent/static/style.css; tests/test_app.py; tests/test_ui_state.cjs; tests/browser/workflow.spec.cjs.

Interfaces: POST /api/profiles/resolve consumes documents/target_name/setup and returns Task 1's report. Existing /api/profiles/review remains compatible.

- [x] Add strict request models, the route and API tests for valid resolution, missing parent, empty/over-limit documents and session protection.
- [x] Add multiple-file import, additive parent loading, target selection and collection clear controls.
- [x] Render chain, field origins/override history, review or blockers, and download an evidence report.
- [x] Add revision guards and revoke report links on any relevant change; test a stale asynchronous response.
- [x] Exercise real file imports, child overrides, missing-parent recovery, report content and invalidation in desktop/mobile browser tests.
- [x] Run Python and UI tests, JavaScript syntax checks, and collect real CI browser evidence.

### Task 3: Documentation, review and publication

Files: README.md; CHANGELOG.md; docs/STATUS.md; docs/FILAMENT_PRESETS.md; docs/VERIFICATION.md; docs/PRODUCT_ROADMAP.md as needed.

- [x] Explain the supported subset, report format, canonical hashes, source references and remaining Studio defaults/native qualification.
- [x] Independently review the implementation against the spec and resolve concrete findings.
- [x] Commit and push the tested implementation to main without overwriting concurrent changes.
- [x] Confirm the remote commit and GitHub Actions result; update the verification record with observed evidence.


## Execution notes

The user authorized continued development and publication to main. Independent workers implemented the pure resolver and UI against the shared contract; root integrated the API, documentation and review fixes. The initial source checkout was preserved, and work continued from the current public main.

Ruling: bound the complete JSON payload to 64 nesting levels before copying or review. An independent reviewer reproduced HTTP 500 from a small, deeply nested document; the API regression failed before the change and passed afterwards for both profile and setup inputs. The full Python suite then passed 116 tests, and the UI controller suite passed 10. This restriction can reject unusually nested vendor extensions, which are now reported as input errors.

Completed implementation commit: e3b6650a5a6858aab9452a0c2692aad6880dc2f3, published to main. [GitHub Actions run 43351259244](https://github.com/uulab-official/3d-printer-agent/actions/runs/43351259244) passed 116 Python, 10 UI-controller and 10 real Chromium browser tests, plus wheel installation and execution outside the source tree. Desktop and mobile screenshots were inspected, and downloaded report originals, edited values and canonical hashes matched. The final independent review reported no remaining reproducible findings after the nesting fix.
