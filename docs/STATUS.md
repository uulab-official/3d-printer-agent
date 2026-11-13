# Development status

Date: 2026-11-13 (Asia/Seoul).

Canonical repository: [uulab-official/3d-printer-agent](https://github.com/uulab-official/3d-printer-agent). The initial local prototype is the open-source v0.1 baseline. This is an experimental local application, not a claim of production or physical-print qualification.

## Implemented

The app generates three parameterized CAD models; reviews user-supplied filament evidence and calibration changes; prepares Bambu CLI jobs; calculates user-entered delivered prices; and stores job artifacts and user reports. The optional LLM adapter only proposes supported typed model parameters. The Korean UI provides the same operations locally.

The filament workflow now imports related JSON documents, selects an editable target, resolves supported explicit single-parent inheritance, shows each value's source and assignment history, and exports an evidence report with the submitted setup. Missing parents can be added to the collection. Changes invalidate old results. See [FILAMENT_PRESETS.md](FILAMENT_PRESETS.md) for the supported subset and official-source references. This does not fill Studio defaults or certify a full native configuration.

Named filament workspaces preserve original documents, exact unfinished drafts, the selected target and all setup inputs across app restarts. A separate SQLite store uses revision checks for atomic updates and conflicts. Common-setting controls edit the selected draft while preserving inheritance and original evidence. Baseline comparison invalidates positive validation claims after effective settings change, including inherited parent changes. Reopening a saved workspace restores inputs and requires a fresh review. See [FILAMENT_WORKSPACES.md](FILAMENT_WORKSPACES.md).

The original local validation is documented in [VERIFICATION.md](VERIFICATION.md). Current unit, package and browser results are recorded per commit in [GitHub Actions](https://github.com/uulab-official/3d-printer-agent/actions). A workflow definition alone is not evidence of a successful run.

### Saved filament workspace checks — 2026-11-13

[CI run 43371025397](https://github.com/uulab-official/3d-printer-agent/actions/runs/43371025397), on feature commit `101c87fea6bb27852b24bd3f18b0545c12c06915`, passed **149 Python tests, 27 UI-controller tests and 14 real Chromium tests** (seven desktop and seven mobile viewport scenarios). Wheel build/install, packaged static assets and execution outside the source tree also passed. No browser test was skipped or flaky.

The final import-help correction, commit `156fa5abb7c0bbc483656fd923d8e2b931a12a4a`, passed the same complete checks in [CI run 43371431939](https://github.com/uulab-official/3d-printer-agent/actions/runs/43371431939). It changes only the wording of the separate 2 MiB original/draft collection limits. Subsequent verification-record changes are documentation only.

New browser flows cover guided inherited overrides, save/reload/open, preserved original evidence, stale validation claims, exact unfinished drafts, original restoration, individual removal, cross-tab conflicts, saving a separate copy and deleting only its saved record. The two downloaded workspace reports were independently checked for original/edited values, retained positive source claims, changed effective settings, all eight setup inputs and canonical hashes. Desktop/mobile screenshots were inspected.

Independent backend and UI reviews preceded publication. Two reproduced UI issues were fixed with regressions: a pending workspace open could discard a later file selection, and smaller edited drafts could let oversized preserved originals into a collection. The final importer checks both collections before accepting files; pasted-original adoption has the same bound. JSON key ordering alone does not label a document edited.

### Filament import checks — 2026-11-13

Local and GitHub Actions checks passed: **116 Python tests and 10 UI-controller tests**, plus JavaScript syntax checks. The new regressions cover inheritance evidence, exact names and blockers, request bounds, late UI responses and invalidated downloads. An independent review found a deeply nested JSON request could return HTTP 500; the reproduced failure now returns HTTP 422 with a depth-limit explanation.

[CI run 43351259244](https://github.com/uulab-official/3d-printer-agent/actions/runs/43351259244), on commit `e3b6650a5a6858aab9452a0c2692aad6880dc2f3`, passed **all 10 Chromium browser tests**: five desktop and five mobile viewport scenarios, with no skipped or flaky tests. This includes missing-parent recovery, edited-value provenance, downloaded report contents, stale-result invalidation, unsupported include handling and malformed imports, along with the existing CAD workflows. Wheel build/install and execution outside the source tree also passed. The downloaded reports from both browser projects were independently checked for original/edited values and matching canonical hashes, and their screenshots were inspected.

### Earlier v0.1 baseline

Repository adoption checks passed locally and in a fresh GitHub Actions environment: **90 Python tests and 5 UI-controller tests**. The additional regressions keep invalid optional LLM URLs from breaking template mode and make failed CAD jobs inspectable in history.

[CI run 43152391860](https://github.com/uulab-official/3d-printer-agent/actions/runs/43152391860), on commit `22b7f57acffbc8a4be35a3df5211f85a2f2b22ce`, also passed **all 6 Chromium browser tests**, with no skipped or flaky tests. Desktop and mobile viewport scenarios exercised real CAD generation, preview zoom, a 3MF download checked against its manifest hash, outcome/history handling, missing profile evidence, unknown shipping and failed-job inspection. Wheel build, installation and execution outside the source directory passed in the same run. Browser evidence is retained by Actions for seven days; the workflow log records the test outcome.

## Remaining qualifications

Actual Bambu Studio versions, macOS/Windows native installation, real LLM servers and physical printing require separate qualification. The original local environment blocked Chromium IPC; the later successful GitHub Actions run supplies the separate real-browser evidence. Mobile viewport emulation is not a test on a physical phone.

Source authenticity checks, Studio default/include/variant resolution, MakerWorld access/customization and live product collection are future capabilities. Many current official presets require those additional resolution rules. No external platform API is assumed to be available or authorized until verified.

## Next product milestones

1. **Exact filament to usable settings:** identify a product and hardware setup, retrieve attributable source material, resolve full preset inheritance, and show unknown/conflicting values.
2. **One real Bambu setup:** verify the installed Studio version, full configuration, slice read-back and measured physical result for one known printer/nozzle/plate/filament combination.
3. **Beginner discovery and customization:** introduce useful-object recommendations and model-source-aware edits, with original files and reuse conditions recorded.
4. **Website and local companion:** add a hosted discovery surface with an explicitly paired local execution component; keep heavy CAD/native work on the user's machine.
5. **Condition-aware shopping and memory:** compare observed offers under matching purchase conditions and reuse outcomes only for matching setups.

The detailed scope is in [PRODUCT_ROADMAP.md](PRODUCT_ROADMAP.md). [BENCHMARKS.md](BENCHMARKS.md) defines proposed future evaluations, not achieved scores.
