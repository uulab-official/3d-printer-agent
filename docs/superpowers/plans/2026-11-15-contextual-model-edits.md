# Contextual model edits implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Review and apply contextual parameter edits without losing unspecified dimensions, source identity or unsaved print notes; persist reproducible edit provenance.

**Spec:** `docs/superpowers/specs/2026-11-15-contextual-model-edits-design.md`

**Architecture:** Pure typed edit derivation, verified parent snapshots in JobStore, API revalidation before CAD, explicit UI candidate state, no new database or external integration.

**Global constraints:** Work in `/workspace/scratch/d9925436ef0d/3d-printer-agent-filament-tuning`, branch `feature/contextual-model-edits`, baseline `418897e1378ef3252665115434873ae78c599cb4`. No local browser/Chromium or native Bambu/AppImage install, execution, retry or escalation. Root alone stages/commits/pushes; agents edit only owned paths. No provider secrets, real printer credentials or paid/live APIs. Read AGENTS.md and the relevant spec sections. Preserve existing behavior and all required gates. Add failing behavior regressions before product fixes. Root runs the full integrated suites; workers run their focused tests to avoid concurrent whole-suite churn. Parallel ownership is disjoint and overrides the skill's generic serial-worker preference under the active developer delegation instruction.

## Task 1: Pure edit engine and bounded planning

**Own:** `print_agent/model_edits.py`, `print_agent/geometry_rules.py`, `print_agent/geometry.py`, `print_agent/planner.py`, `tests/test_model_edits.py`, `tests/test_planner.py`, and a new focused `tests/test_model_edit_provider.py` if useful. Do not change app, storage, static, qualification or release files.

- [x] Read the spec's pure contract and provider sections and existing geometry reproduction/planner tests.
- [x] Add regression tests for unchanged fields, relative/absolute mm/cm changes, strict operations, invalid cross-field geometry, stale/malformed selections, hash/record rederivation and ambiguous or mixed requests. Include the existing conflicting XYZ-triple bug before fixing it. Observe expected red results.
- [x] Implement the exact public functions and canonical record contract in the spec. Extract pure `_validate_geometry` without changing standalone-source behavior.
- [x] Extract the protected provider transport to `request_llm_json`; preserve existing provider tests and add typed-edit provider behavior/invalid-response tests.
- [x] Run focused unit suites and existing reproduction tests. Report exact commands/results, any unresolved concern and owned-file changes to the task report; do not commit.

**Review focus:** no implicit parameter resets, no partial understanding, strict numeric/boolean boundaries, preserved stream/deadline guarantees, reproducible canonical records.

## Task 2: Immutable edit records and verified parent snapshots

**Own:** `print_agent/storage.py`, new `tests/test_model_edit_records.py`. Do not edit Task 1's modules or app/static files. Consume the exact pure functions from Task 1; tests can wait for that module to exist while implementing storage fixtures.

- [x] Add failing behavior tests for reserve/finish/read record validation, manifest/bundle preservation and tampering; verify actual file receipts, not just object equality.
- [x] Implement `JobStore.model_edit_parent(job_id, base_parameters)` with verified job, manifest and original 3MF identity as specified.
- [x] Add optional `model_edit` argument to `reserve`; validate and deep-copy before folder creation; revalidate at finish against actual result and in `_read` against saved parameters. Old jobs remain valid. Do not recursively open historical parents while reading child jobs.
- [x] Test mismatched/missing/corrupt parents, immutable base/selection snapshots, and backup-compatible canonical files. Run focused storage tests and report evidence. Do not commit.

**Review focus:** no partial job on invalid selection, no unverified artifact identity, strict saved-record rederivation, compatibility with legacy jobs and immutable recipe identity.

## Task 3: Contextual-edit UX and lossless job replacement

**Own:** `print_agent/static/app.js`, `print_agent/static/index.html`, `print_agent/static/style.css`, `tests/test_ui_state.cjs`, `tests/browser/workflow.spec.cjs`. Consume the API/record contracts from the spec; do not edit server modules or qualification files.

- [x] Reproduce unsaved-outcome loss and dirty new-plan replacement in controller tests before fixing them.
- [x] Add the Korean edit panel, request scope, complete response validation, before/after candidate, explicit apply/cancel, source preservation, selection detach after manual edits and history/job edit provenance display.
- [x] Protect all job replacement/invalidation paths, including same-dimension regeneration, by retaining dirty outcome notes with old job and storage identity. Route new-plan results through existing replacement confirmation after the request completes. Failures/cancel/stale responses preserve exact inputs.
- [x] Add behavior tests for stale scope/reconnect/failure/cancel, out-of-order completion and complete-response validation, unchanged fields and payload provenance. Do not reimplement the Python engine in JS; validate review consistency and defer authoritative derivation to generation.
- [x] Add real browser CI flows for contextual recipe edit and dirty new-plan preservation on desktop/mobile. Save structured evidence and screenshots using CSP-safe existing helpers. Do not execute/install browsers locally.
- [x] Run Node syntax/controller tests; report exact results and browser scenarios awaiting CI. Do not commit.

**Review focus:** no stale candidate application, no lost notes or falsely current artifacts, reliable busy release, keyboard/mobile accessibility, honest latest-edit provenance.

## Task 4: API, installed qualification, review and release

**Owner:** root. **Own:** `print_agent/app.py`, new `tests/test_model_edits_api.py`, `scripts/qualify_install.py`, `scripts/promote_release.py`, release-gate tests, version/docs files. Wait for the producers before integrated tests.

- [x] Add failing API tests for current-parameter planning, optional verified parent, provider validation-before-network, selection/result mismatch and changed/missing parent rejection before reserve/CAD.
- [x] Wire POST `/api/model-edits/plan` and optional generation selection. Exclude metadata from GeometryRequest and revalidate parent as a 409 `model_edit_parent_changed` before side effects.
- [x] Extend installed qualification with actual beginner-recipe CAD edit, job/manifest/bundle readback, restart, backup/restore and current Studio preparation. Add required promotion checks and preserve existing evidence.
- [x] Bump package/runtime/Studio producer version to 0.7.0 and document exact feature limits and usage.
- [x] Obtain design, scoped implementation and whole-change reviews; resolve concrete findings. Run full Python, Node and local installed qualification, without local browser/native execution.
- [x] Commit and push authorized main change; verify same-source CI, three-OS package and native gates. Read back structured evidence and focused browser screenshots. Publish the qualified wheel through existing promotion; independently verify public release assets, then record final status evidence in a docs-only followup.

Completed on source [`62317af8c71c95956db5194bf65934d8dea96c73`](https://github.com/uulab-official/3d-printer-agent/commit/62317af8c71c95956db5194bf65934d8dea96c73): [CI](https://github.com/uulab-official/3d-printer-agent/actions/runs/43695898464), [three-OS package qualification](https://github.com/uulab-official/3d-printer-agent/actions/runs/43695898395), and [native qualification](https://github.com/uulab-official/3d-printer-agent/actions/runs/43695898460) all passed on attempt 1. [Promotion](https://github.com/uulab-official/3d-printer-agent/actions/runs/43696240528) published [v0.7.0](https://github.com/uulab-official/3d-printer-agent/releases/tag/v0.7.0) at 2026-11-15 08:49:17 UTC. Independent public readback passed 67 checks against all seven unauthenticated downloads and the qualified source tag. The final evidence and limits are recorded in [VERIFICATION.md](../../VERIFICATION.md).

**Review focus:** source-to-artifact identity, no generation before validation, meaningful installed lifecycle checks, observed evidence and precise public claims.
