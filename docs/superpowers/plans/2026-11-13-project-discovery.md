# Useful Project Discovery Implementation Plan

> **For agentic workers:** Use the subagent-driven-development workflow for scoped implementation and independent review. The user has already authorized continuing implementation and publication to `main`; routine design choices do not require another approval.

**Goal:** Let a beginner find a useful local starting project and generate a customized CAD model with its original recipe recorded.

**Architecture:** A pure Python catalog/matcher supplies the Korean UI and a typed local API. Model generation keeps its existing geometry contract; the server resolves the optional selected recipe before saving its snapshot alongside the job and manifest.

**Tech Stack:** Existing Python 3.12, FastAPI/Pydantic, CadQuery, dependency-free JavaScript/CSS, unittest/Node and Playwright CI.

**Spec:** [project-discovery-design](../specs/2026-11-13-project-discovery-design.md).

## Global constraints

- Baseline `ce7d0854ffa8e3ee37ed7e2e7934b2a22156a457`; preserve unrelated user changes.
- Six catalog recipes, three existing geometry templates; no new dependency, database migration or paid model/service.
- Space means placement bounding box, never printer compatibility or a continuing fit claim after customization.
- Resolve source identity server-side before job reservation; reject stale hashes and arbitrary provenance metadata.
- Source identity, CAD validation, slicing and physical printing remain separate facts.
- Preserve old clients/jobs and current filament/native flows.
- Do not retry the known blocked local Chromium or native runtime; use actual CI for those observations.

## Review focus

- Filter/plan/bootstrap responses arriving after input changes must not replace current work.
- Empty numeric strings with `badInput` must not turn into omitted constraints or erase unfinished drafts.
- History must retain its saved recipe snapshot even if the current catalog changes.
- Partial space constraints and horizontal rotation must never swap height or invent missing axes.
- Generated parameter edits must not keep downloads/preview/source labels pointing to a different result.

## Execution decisions and progress

Ruling: implement in the existing clean checkout and publish to `main` with a compare-and-swap lease — the user explicitly requested main commits/pushes; unexpected remote movement will be inspected before publication.

Ruling: parallelize independent file-owned implementation tasks — backend, UI and root integration own disjoint files; the session's parallel-work instruction takes precedence over a generic serial-agent guideline. Root performs integration and a fresh independent final review.

Ruling: filter optional placement dimensions rather than printer beds — this gives useful narrowing without assuming any hardware capabilities. Recommendation text states the bounding-box limitation.

- [x] Inspect current contracts and complete independent backend/UI design audits.
- [x] Write bounded design and exact shared interfaces; resolve routine choices using the user's standing execution authorization.
- [x] Task 1: catalog, typed matching, recipe identity and persisted origin.
- [x] Task 2: discovery UI, draft/source transitions and controller checks.
- [x] Task 3: local API integration, browser workflow definitions and documentation.
- [x] Run full local gates, inspect package contents and complete independent review.
- [x] Publish implementation, inspect actual application/native CI and downloaded evidence.
- [x] Record observed verification in a documentation-only follow-up without changing the tested code.

## Task 1: Catalog and source identity

**Owner/files:** backend implementer owns new `print_agent/discovery.py`, new `tests/test_discovery.py`, `print_agent/storage.py`, `tests/test_storage.py`. Do not edit `app.py`, schemas, UI, browser tests or documentation.

**Interfaces:** implement `AvailableSpace`, `DiscoveryRequest`, `ProjectSelection`, `StaleProjectSelection`, `project_catalog()`, `recommend_projects(request)`, `resolve_project_selection(selection, spec)` exactly as the spec. Extend `JobStore.finish(job_id, result, *, design_source=None)` additively. Root consumes the types/functions in routes; UI consumes bootstrap/catalog and matching JSON.

- [x] Write failing tests for six real recipes, independent canonical hashes, fresh-copy isolation, purpose filtering, optional axes, exact-boundary matches, width/depth rotation, height failures and zero matches.
- [x] Include strict boundary cases: boolean/string/nonfinite/zero dimensions, unknown purpose/field, malformed selection, unknown ID, stale hash and mismatched template.
- [x] Implement the pure catalog/matcher and server-built source snapshot; show a failing test before its corresponding implementation.
- [x] Generate every recipe with real CadQuery into temporary directories, re-read STEP and verify expected outer dimensions and one valid solid.
- [x] Add source-preservation tests for job/manifest/bundle and new store instance; keep source absent for legacy generation. Ensure mutation of passed source cannot change saved results.
- [x] Run `python -m unittest tests.test_discovery tests.test_storage -v`, self-review and report exact results/remaining limits. Root commits the integrated changes.

## Task 2: Beginner UI and source state

**Owner/files:** UI implementer owns `print_agent/static/app.js`, `index.html`, `style.css`, `tests/test_ui_state.cjs`. Do not edit backend, browser tests or docs.

**Interfaces:** bootstrap `discovery` and `POST /api/discovery` match the spec. Generation sends optional `project_selection: {id, recipe_sha256}`; returned job has optional `design_source`. Existing `applyDraft`, `invalidateCurrentJob`, `renderJob` and workflow locks remain authoritative.

- [x] Write controller failures for browsing/filter preservation, explicit application, replacement cancel preserving invalid partial strings, source detach, generic/reset/plan source clearing, and history using its saved snapshot.
- [x] Add accessible responsive purpose filters, optional placement dimensions, catalog cards, result/empty/error states and a separate project detail/apply action. Keep the existing three template cards.
- [x] Test and implement stale recommendation response rejection, filter edits during a request, bootstrap retry preservation, and workflow-busy action/confirmation guards.
- [x] Keep source selection independent from the browsed card, render supplied text safely, record customized dimensions through the ordinary generation API, and expose source detachment without changing numeric input strings.
- [x] Run `node --check print_agent/static/app.js` and `node tests/test_ui_state.cjs`; self-review and report results. Root commits the integrated changes.

## Task 3: API, browser flows and product documentation

**Owner/files:** root owns `print_agent/app.py`, new `tests/test_discovery_api.py`, `tests/browser/workflow.spec.cjs`, README/CHANGELOG/docs and the plan ledger.

**Interfaces:** consume Task 1 functions without changing their contract; flat `ModelPayload(GeometryRequest)` adds `project_selection`. Keep the existing CAD lock and error logging. Resolve selection before reserving any job; pass source only through the keyword argument to storage.

- [x] Add failing API tests for session protection, deterministic filtered recommendations without CAD jobs, legacy model requests, custom source preservation across detail/manifest/bundle/restart, and reject-before-reserve cases.
- [x] Implement bootstrap data, `POST /api/discovery`, stale-selection HTTP 409 and the compatible model payload.
- [x] Add two desktop/mobile browser scenarios: actual curated-project customization/generation/download/history, and preservation/invalid-space/no-results/async recovery/explicit replacement behavior. Check mobile horizontal overflow and capture useful evidence at normal viewport scale.
- [x] Update usage/API contracts/status/changelog and roadmap current-capability text without claiming external search, measurements or hardware qualification.
- [x] Run Python full suite, JS syntax/controller, browser discovery, whitespace checks and wheel/source consistency. Fix concrete failures, not unrelated optional refactors.
- [x] Request fresh read-only integrated review; resolve material findings and rerun relevant checks.
- [x] Publish with a remote lease, inspect actual CI and its final browser/native artifacts, then record observed counts, hashes and scope in a documentation-only follow-up.

## Verification ledger

The new API tests first reproduced missing catalog/route/source behavior. The backend tests first reproduced missing matching and source persistence, then passed all 25 targeted cases. All six catalog recipes were actually generated with CadQuery and re-read as STEP, checking dimensions and a single valid solid. The API integration and existing route tests passed all 24 cases, including selected/customized geometry, file hashes, manifest/bundle/restart provenance and rejection before job reservation.

The integrated Python suite passed **255 tests** in 28.070 seconds. UI checks initially passed 79 cases. A fresh independent review reproduced two additional gaps: numerically equal input text (`120.0`) could skip replacement confirmation, and a refreshed catalog could leave obsolete candidates applicable. Both counterexamples failed before their fixes. Exact input-string comparison and explicit stale state on preserved catalog refresh now pass **81 controller checks**, including an independent narrow re-review. The frame illustration was also corrected to a square exterior with a circular inset. No review blockers remain.

Final JavaScript syntax and whitespace checks passed. The wheel rebuilt after the UI fixes, and all **18 packaged application files** matched the inspected source bytes. Browser discovery lists **28 scenarios**, 14 per viewport project. This count is a definition, not an execution result. The planned real-browser run explicitly includes one delayed real recommendation response and one labelled synthetic HTTP 503 to exercise recovery; actual CAD generation is never mocked. Known local Chromium/runtime restrictions were not bypassed.

### Observed publication and CI evidence

Feature commit `b3e21154b06e587959a7118d83150c27fc1bcd83` was published to `main` with a compare-and-swap lease. [Application CI 43425172431](https://github.com/uulab-official/3d-printer-agent/actions/runs/43425172431) completed successfully at that exact commit: **255 Python tests, 81 controller tests and 28 actual Chromium workflows**, split 14 desktop/14 mobile viewport. All browser scenarios passed once, with zero failed, flaky or skipped tests. Wheel build/install, static assets and execution outside the source tree passed. These are observed results, superseding the pre-publication scenario count above.

The fresh browser artifact's byte hash and ZIP integrity were checked before inspection. **57 independent assertions** confirmed the exact tested commit, first-attempt results, submitted purpose/space query, original recipe hashes, preserved source/customization and downloaded file contents. Independent XML parsing confirmed both 3MF models contain 96 vertices with bounds 152 × 90 × 30 mm; the saved original recipe retains width 150 mm and records only `width` as customized. Desktop/mobile recommendation responses are byte-identical, while the separately generated manifests and 3MF files are not.

Independent visual reviews inspected five desktop and five mobile component captures. Main controls and source/status distinctions were readable without blocking overlap. Minor mobile unit wrapping and a sticky-header crop artifact were recorded. Purpose/space controls, expanded source details, full-page behavior, frame-card rendering and measured contrast were outside the screenshot-review scope; the functional browser checks provide separate interaction evidence.

[Native regression CI 43425172549](https://github.com/uulab-official/3d-printer-agent/actions/runs/43425172549) also succeeded at the exact feature commit. Actual Studio `02.09.01.70` sliced the original STL cube and CadQuery cable-comb 3MF; each passed 32 adapter, 30 independent setting and nine qualification checks. The newly downloaded artifact passed **95 independent assertions** against its bytes, exact committed source, original geometry and native output/settings. This remains regression coverage for the unchanged synthetic slicing path, not qualification of discovery-to-native behavior, manufacturer/user presets, hardware or physical printing.

Artifact sizes, hashes, retention dates and explicit inspection limits are recorded in [VERIFICATION.md](../../VERIFICATION.md). The follow-up changes only that verification log, [STATUS.md](../../STATUS.md) and this plan; application code, tests and workflows remain identical to the tested feature commit.
