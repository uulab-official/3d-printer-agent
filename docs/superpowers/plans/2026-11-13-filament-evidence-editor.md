# Filament evidence editor implementation plan

Baseline: `9509c904aebdf788ba78b7701ccc4d05dbd1ec44`.
Specification: [filament-evidence-editor](../specs/2026-11-13-filament-evidence-editor.md).

- [x] Inspect current selected-document, workspace, baseline and validation contracts; agree on a bounded implementation with independent backend and UI audits.
- [x] Add failing backend regression cases for evidence comparison and claim invalidation, then implement the additive resolver contract.
- [x] Add failing controller regressions, then implement progressive evidence inputs and one atomic pending-edit transaction with preservation and race guards.
- [x] Add desktop/mobile browser flows and API coverage for actual saved source/scope evidence and downloaded reports.
- [x] Update usage, API, status and changelog documentation to describe the implemented behavior and its limits.
- [x] Run full local gates, inspect the diff and obtain an independent read-only review; fix concrete findings and rerun the affected checks.
- [ ] Publish the verified implementation to authorized `main`, inspect actual application/native CI and their evidence artifacts, then record only observed results in a documentation follow-up.

## Ownership

- Backend agent: `print_agent/preset_library.py`, `tests/test_preset_library.py`.
- UI agent: `print_agent/static/app.js`, `index.html`, `style.css`, `tests/test_ui_state.cjs`.
- Root: browser/API tests, documentation, integration, publication and CI evidence.
- Independent reviewer: read-only review of the final integrated diff and relevant counterexamples.

No new API, database migration, dependency or physical printer action is planned. Existing native qualification runs are regression checks for the unchanged native path.

## Local verification before publication

The new backend and controller cases first reproduced missing evidence comparison, retained positive scope claims, and the missing editor. The additional numeric-input counterexample (`value === ''` with `validity.badInput`) reproduced unintended removal; the fix keeps this invalid value pending even for an originally absent nozzle and rejects the complete edit atomically.

The integrated local checks passed: 229 Python tests, 61 controller checks, JavaScript syntax and `git diff --check`. The wheel built successfully; all 17 packaged application files matched the inspected source byte-for-byte. Browser discovery lists 24 desktop/mobile scenarios. Actual browser and native CI outcomes will be recorded only after execution and artifact inspection; the known local Chromium IPC restriction was not bypassed.

An independent read-only review found the same partial-number deletion counterexample and rechecked its fix with both present and absent nozzle evidence, plus pending setting/source edits. The final review found no remaining actionable issue across resolver, UI, API/browser scenarios and documentation. The new real-browser scenario also types an unfinished `-` to check this DOM behavior in CI.

## First real-browser findings

Feature commit `79388aa8f49f2ac9d3078229eeeba6454c7a6a21` passed Python/controller/package checks in [CI 43401274545](https://github.com/uulab-official/3d-printer-agent/actions/runs/43401274545), but its 20 existing browser workflows passed while all four new workflows timed out on invisible evidence inputs. Downloaded screenshots and traces showed an open disclosure and populated native fieldset containers, with visible help paragraphs but no rendered fieldset content. The loaded stylesheet matched the source; no application hiding rule explained it. The precise browser-internal cause is not established.

The correction uses ordinary labelled `role=group` containers and visible headings, retaining all control IDs, labels, state and transaction semantics. Tests now assert actual group-input visibility immediately and attach layout diagnostics on failure. A separate expectation was corrected to compare the deliberately JSON-serialized display of a publisher containing quotes. Independent review found no new blocker; 61 controller checks, syntax, diff and wheel/source checks passed before the next actual browser run. Native [run 43401274272](https://github.com/uulab-official/3d-printer-agent/actions/runs/43401274272) passed for the initial commit; this is not yet evidence for a later commit.
