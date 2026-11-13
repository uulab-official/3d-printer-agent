# Studio preset archive implementation plan

**Goal:** Bring real Studio export formats into the local filament editor and
preserve accepted drafts, source identity and saved workspace behavior.

**Architecture:** Bounded Python ZIP parser; authenticated JSON endpoint;
optional origin on existing review/workspace documents; one atomic browser
collection-append path. No new dependency or native execution path.

**Stack:** Python 3.12, stdlib ZIP/base64, FastAPI/Pydantic, dependency-free
browser JavaScript, unittest, Node controller harness and Playwright CI.

**Spec:** [Studio preset archives](../specs/2026-11-13-studio-preset-archive-design.md)

## Tasks

- [x] Parser owner: add `preset_archive.py` and fail-first parser regressions.
      Verify pinned native structures, identity classification, byte hashes,
      manifest consistency, atomic errors and resource limits.
- [x] Root: add optional validated origin to preset reports and workspace
      documents, then the bounded import API. Fail-first API and persistence
      tests must preserve original settings and previous workspaces.
- [x] UI owner: add Studio-export input; refactor atomic append and preserve
      pasted/incomplete drafts; carry origin through all snapshot/report paths.
      Add meaningful controller and desktop/mobile browser scenarios.
- [x] Root: document supported formats, instructions, limits and evidence in
      README, filament docs, changelog and status. No native-readiness claims.
- [x] Independent review: inspect the parser, API, provenance and UI state
      transitions. Resolve concrete issues with reproducing regressions.
- [x] Verify locally: `python -m unittest discover -v`, UI syntax/controller
      tests, browser test discovery and Python wheel/static assets.
- [x] Publish reviewed change to `main`; inspect actual CI results and browser
      artifacts. Record exact verification results and final remote commit.

Feature commit: `516ff0340e4ce8a0ddb5afe6a70037e269a7c9b2`.
Application CI `43380405229` passed 215 Python / 48 controller / 20 real browser
checks; native regression CI `43380405138` passed both existing adapter cases.
Downloaded browser reports, six screenshots and native artifacts were inspected.
Evidence-record follow-up changes documentation only.

## Review focus

Do not flatten or relabel presets, trust archive names as publisher evidence,
read member paths from disk, retain partial archive imports, replace unfinished
work, or let a delayed import overwrite a newer edit/workspace. Origin metadata
must survive round trips without becoming a setting or a calibration claim.
