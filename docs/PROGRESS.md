# Progress — 2026-11-12 first workflow

## Open-source repository adoption

- User selected `uulab-official/3d-printer-agent` as the public project repository. Its initial state was empty, with `main` as the default branch.
- Added MIT licensing, package metadata, contribution/report templates, current project status and agent development guidance.
- Added pinned GitHub Actions and a locked Playwright suite for real desktop/mobile workflows. CI results live with each tested commit.
- Reproduced and fixed malformed optional LLM URLs breaking app bootstrap, and failed CAD history dereferencing a missing model. Local checks: 90 Python tests, 5 controller tests passed.

## Original local prototype record

- Environment verified: CadQuery creates valid solids; no Bambu Studio found.
- Existing uulab-official/3d-modeling-skills README reviewed; no remote files modified.
- Ruling: new standalone source directory, provisional name, no public repo creation — product name/repository not selected.
- Ruling: parallel work uses disjoint modules and a fixed contract — preserves speed without shared-file edits.
- Ruling: real geometry and source-backed local settings first; live data/physical print/LLM performance remain unverified until actually connected.
- Implemented: three CAD templates, scoped profile review, calibration invalidation, Bambu CLI adapter, rules/optional LLM planner, manual price comparison, local API/SQLite history and Korean static UI.
- 88 unittest cases passed in the complete suite, including actual CAD exports/reimport and standalone source reproduction. Provider and slicer protocol tests use synthetic responses; they are not native/live qualification.
- Independent review reproduced five behavior issues: object nouns overriding material/shopping intent; old slice aliases surviving new failures; ignored unsupported template parameters; decimal/count parsing; LLM prose claiming execution. Regression tests and fixes were applied.
- Actual sample files: 120×80×35 mm three-compartment tray, 80×18×12 mm cable holder, 65×65×7 mm inset frame. Details and hashes: docs/EXAMPLE_EVIDENCE.json.
- UI preview uses the generated mesh with a dependency-free Canvas projection. No pre-rendered success imagery or invented printer statistics.
- Browser QA was attempted with Playwright. Bundled browser was absent; installed Chromium was then blocked by the environment's IPC socket policy. Requested escalation was rejected by the configured approval policy. No permissions or sandbox controls were altered. API/static checks continue; browser layout/interaction remain unverified.
