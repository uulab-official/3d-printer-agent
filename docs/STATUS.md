# Development status

Date: 2026-11-13 (Asia/Seoul).

Canonical repository: [uulab-official/3d-printer-agent](https://github.com/uulab-official/3d-printer-agent). The initial local prototype is the open-source v0.1 baseline. This is an experimental local application, not a claim of production or physical-print qualification.

## Implemented

The app generates three parameterized CAD models; reviews user-supplied filament evidence and calibration changes; prepares Bambu CLI jobs; calculates user-entered delivered prices; and stores job artifacts and user reports. The optional LLM adapter only proposes supported typed model parameters. The Korean UI provides the same operations locally.

The filament workflow now imports related JSON documents, selects an editable target, resolves supported explicit single-parent inheritance, shows each value's source and assignment history, and exports an evidence report with the submitted setup. Missing parents can be added to the collection. Changes invalidate old results. See [FILAMENT_PRESETS.md](FILAMENT_PRESETS.md) for the supported subset and official-source references. This does not fill Studio defaults or certify a full native configuration.

Studio `.bbsflmt`, `.bbscfg` and preset `.zip` imports add filament documents directly, retain exact archive/member byte identity outside the original profile, and report excluded printer/process documents. The bounded parser does not extract files or execute Studio. Collection imports preserve pasted profiles and unfinished drafts, skip identical originals, reject conflicting names, and commit only after complete validation. Origin round-trips through saved workspaces and review reports. See [FILAMENT_ARCHIVES.md](FILAMENT_ARCHIVES.md) for source-derived format support and limits; a successful import does not resolve missing system parents or native variants.

Named filament workspaces preserve original documents, exact unfinished drafts, the selected target and all setup inputs across app restarts. A separate SQLite store uses revision checks for atomic updates and conflicts. Common-setting controls edit the selected draft while preserving inheritance and original evidence. Baseline comparison invalidates positive validation claims after effective settings change, including inherited parent changes. Reopening a saved workspace restores inputs and requires a fresh review. See [FILAMENT_WORKSPACES.md](FILAMENT_WORKSPACES.md).

An expandable evidence editor records the selected profile's seven applicability fields and four source fields independently of the current setup. Numeric and evidence changes share one atomic apply/cancel flow; raw profiles are wrapped only in the edited draft when evidence is applied. Original documents, unknown fields, validation claims and archive origins remain intact. Reports compare the target's own scope/source/validation separately from effective settings, and changed scope or validation makes a currently positive claim stale. Source-only corrections are recorded without implying new measurements or publisher authentication. This extends the existing workspace and review contracts without another endpoint or storage schema.

Native slicing preparation now assembles supplied machine/process/filament files with an explicit plate selection, validates native metadata and value representations, and rechecks staged configuration hashes and derived expectations before execution. An explicit UI/doctor probe reports the installed CLI's observed version/capabilities. Verified archive results include their SHA-256 and native version. See [BAMBU_STUDIO.md](BAMBU_STUDIO.md) for the supported subset and usage.

The original local validation is documented in [VERIFICATION.md](VERIFICATION.md). Current unit, package and browser results are recorded per commit in [GitHub Actions](https://github.com/uulab-official/3d-printer-agent/actions). A workflow definition alone is not evidence of a successful run.

### Filament applicability and source editor checks — 2026-11-13

[Final application CI 43403222805](https://github.com/uulab-official/3d-printer-agent/actions/runs/43403222805), on code commit `c1784c2e06df585016958f07c18717af447b2105`, passed **229 Python tests, 61 controller tests and 24 real Chromium workflows** (12 desktop and 12 mobile viewport). There were no failed, flaky or skipped browser tests. Wheel build/install, packaged assets and execution outside the source tree passed. All 17 packaged application files also matched the inspected local source byte-for-byte.

New browser flows cover raw archive profiles, seven scope and four source fields, independent current setup, atomic numeric/evidence edits, partial-number rejection, cancellation, preserved legacy values, save/reload/open and downloaded reports. Four final reports passed 84 independent content/hash assertions: original documents and archive byte receipts remain intact, effective settings stay unchanged for evidence-only edits, source claim-only warnings remain explicit, and changed applicability makes the current positive claim stale while retaining stronger mismatch blockers. Each desktop/mobile report pair is byte-identical. Source-only corrections retaining matching positive claims were separately exercised in the browser workflow. Four final desktop/mobile screenshots were inspected, with fixed-navigation and reduced-scale inspection limits recorded in the verification log.

The initial feature CI passed 20 existing workflows but failed the four new ones because populated native fieldset contents were not rendered. The observed failure was corrected with ordinary labelled groups, with no asserted browser-internal root cause. Real-browser checks now require visible evidence inputs; the final run passed without forced actionability. Independent review also caught a partial-number input being mistaken for deletion; present and absent nozzle evidence now retain that invalid input and reject the whole pending edit atomically.

[Final native regression CI 43403222786](https://github.com/uulab-official/3d-printer-agent/actions/runs/43403222786) passed on the same code commit with actual Studio `02.09.01.70`. The original STL cube and CadQuery cable-comb 3MF each passed 32 adapter checks, 30 independent setting comparisons and nine qualification checks. Fresh downloaded evidence passed 92 independent assertions against committed source, input geometry and output archive/G-code/settings. This is regression evidence for the unchanged synthetic native path, not native qualification of the evidence editor or user hardware. Artifact hashes, initial failures and exact limits are in [VERIFICATION.md](VERIFICATION.md). The following evidence-record commit changes documentation only.

### Studio preset archive checks — 2026-11-13

[Application CI 43380405229](https://github.com/uulab-official/3d-printer-agent/actions/runs/43380405229), on feature commit `516ff0340e4ce8a0ddb5afe6a70037e269a7c9b2`, passed **215 Python tests, 48 controller tests and 20 real Chromium workflows** (10 desktop and 10 mobile viewport). There were no failed, flaky or skipped browser tests. Wheel build/install, packaged assets and execution outside the source tree passed.

The new browser flows exercise typeless Studio filament archives, exact original text and byte hashes, missing-parent recovery, guided edits, save/reload/open, report download, mixed printer bundles, pasted-input preservation, repeated-import handling and atomic rejection. Six desktop/mobile screenshots were inspected. The two downloaded archive reports were independently compared with the exact committed synthetic ZIP fixture: archive/member hashes and all canonical document hashes match, the original 215 and edited 220 values remain separate, and desktop/mobile reports are byte-identical. These values are test data, not material recommendations.

Independent review found and fixed malformed manifest types and forged ZIP prefix sizes/CRCs. Complete bounded DEFLATE/STORED stream checks now reject hidden trailing data; the exact counterexamples and full regression suite passed. Archive origins remain input receipts rather than authority or measurement claims. The source-derived fixtures do not qualify a captured GUI export, native preset installation or physical printing.

[Native regression CI 43380405138](https://github.com/uulab-official/3d-printer-agent/actions/runs/43380405138) passed on the same feature commit. Actual Studio `02.09.01.70` sliced the original STL cube and CadQuery cable-comb 3MF through the unchanged adapter. Each passed 32 adapter checks and 30 independently recomputed setting comparisons. The downloaded evidence, exact committed adapter/script hashes and original geometry were rechecked separately. This tests the existing synthetic native path; it does not convert archive import into native qualification. Later evidence-record edits change documentation only.

### Native Bambu checks — 2026-11-13

[Final application CI 43376181601](https://github.com/uulab-official/3d-printer-agent/actions/runs/43376181601), on `2e29040597b3f948a7bdb01bf5da34ebaf991a69`, passed **181 Python tests, 38 controller tests and 14 real Chromium workflows**, with no failed, flaky or skipped browser tests. Wheel build/install, packaged assets and execution outside the source tree passed. The helper's desktop/mobile screens and assembled file values were checked; final downloaded reports and archive integrity were verified. Subsequent evidence-record edits are documentation only.

[Native run 43376181533](https://github.com/uulab-official/3d-printer-agent/actions/runs/43376181533), on `2e29040597b3f948a7bdb01bf5da34ebaf991a69`, passed with the actual digest-pinned Studio `02.09.01.70` on Ubuntu 24.04. The app's public adapter functions sliced an original STL cube and the existing original CadQuery cable-comb 3MF. Each returned `sliced`, matched 30 independently declared core settings, and passed archive/G-code/digest checks. The downloaded evidence and exact adapter/script hashes were independently checked. Official CLI examples were also exercised unchanged in a separate bootstrap phase.

This qualifies the tested native adapter path with synthetic single-filament settings. It does not qualify a manufacturer's preset, native default resolution, user-machine inheritance, other versions/platforms or physical printing. The current lineage-free path requires a root machine classified `from: system` and an exact process compatibility entry. Inputs are never relabeled to manufacture compatibility. Unsupported user-machine lineage and selected-plate zero temperatures are explained before execution; malformed/deep/overflowing read-back values require review instead of crashing.

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

Native results are version- and fixture-specific; see [VERIFICATION.md](VERIFICATION.md) for observed Linux Studio execution. macOS/Windows native installation, other Studio versions, real LLM servers and physical printing require separate qualification. The original local environment blocked Chromium IPC; the later successful GitHub Actions run supplies the separate real-browser evidence. Mobile viewport emulation is not a test on a physical phone.

Source authenticity checks, Studio default/include/variant resolution, MakerWorld access/customization and live product collection are future capabilities. Many current official presets require those additional resolution rules. No external platform API is assumed to be available or authorized until verified.

## Next product milestones

1. **Exact filament to usable settings:** identify a product and hardware setup, retrieve attributable source material, resolve full preset inheritance, and show unknown/conflicting values.
2. **One real Bambu setup:** verify the installed Studio version, full configuration, slice read-back and measured physical result for one known printer/nozzle/plate/filament combination.
3. **Beginner discovery and customization:** introduce useful-object recommendations and model-source-aware edits, with original files and reuse conditions recorded.
4. **Website and local companion:** add a hosted discovery surface with an explicitly paired local execution component; keep heavy CAD/native work on the user's machine.
5. **Condition-aware shopping and memory:** compare observed offers under matching purchase conditions and reuse outcomes only for matching setups.

The detailed scope is in [PRODUCT_ROADMAP.md](PRODUCT_ROADMAP.md). [BENCHMARKS.md](BENCHMARKS.md) defines proposed future evaluations, not achieved scores.
