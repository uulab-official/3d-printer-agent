# Development status

Date: 2026-11-12 (Asia/Seoul).

Canonical repository: [uulab-official/3d-printer-agent](https://github.com/uulab-official/3d-printer-agent). The initial local prototype is the open-source v0.1 baseline. This is an experimental local application, not a claim of production or physical-print qualification.

## Implemented

The app generates three parameterized CAD models; reviews user-supplied filament evidence and calibration changes; prepares Bambu CLI jobs; calculates user-entered delivered prices; and stores job artifacts and user reports. The optional LLM adapter only proposes supported typed model parameters. The Korean UI provides the same operations locally.

The original local validation is documented in [VERIFICATION.md](VERIFICATION.md). Current unit, package and browser results are recorded per commit in [GitHub Actions](https://github.com/uulab-official/3d-printer-agent/actions). A workflow definition alone is not evidence of a successful run.

Repository adoption checks passed locally and in a fresh GitHub Actions environment: **90 Python tests and 5 UI-controller tests**. The additional regressions keep invalid optional LLM URLs from breaking template mode and make failed CAD jobs inspectable in history.

[CI run 43152391860](https://github.com/uulab-official/3d-printer-agent/actions/runs/43152391860), on commit `22b7f57acffbc8a4be35a3df5211f85a2f2b22ce`, also passed **all 6 Chromium browser tests**, with no skipped or flaky tests. Desktop and mobile viewport scenarios exercised real CAD generation, preview zoom, a 3MF download checked against its manifest hash, outcome/history handling, missing profile evidence, unknown shipping and failed-job inspection. Wheel build, installation and execution outside the source directory passed in the same run. Browser evidence is retained by Actions for seven days; the workflow log records the test outcome.

## Remaining qualifications

Actual Bambu Studio versions, macOS/Windows native installation, real LLM servers and physical printing require separate qualification. The original local environment blocked Chromium IPC; the later successful GitHub Actions run supplies the separate real-browser evidence. Mobile viewport emulation is not a test on a physical phone.

Source authenticity checks, inherited-profile resolution, MakerWorld access/customization and live product collection are future capabilities. No external platform API is assumed to be available or authorized until verified.

## Next product milestones

1. **Exact filament to usable settings:** identify a product and hardware setup, retrieve attributable source material, resolve full preset inheritance, and show unknown/conflicting values.
2. **One real Bambu setup:** verify the installed Studio version, full configuration, slice read-back and measured physical result for one known printer/nozzle/plate/filament combination.
3. **Beginner discovery and customization:** introduce useful-object recommendations and model-source-aware edits, with original files and reuse conditions recorded.
4. **Website and local companion:** add a hosted discovery surface with an explicitly paired local execution component; keep heavy CAD/native work on the user's machine.
5. **Condition-aware shopping and memory:** compare observed offers under matching purchase conditions and reuse outcomes only for matching setups.

The detailed scope is in [PRODUCT_ROADMAP.md](PRODUCT_ROADMAP.md). [BENCHMARKS.md](BENCHMARKS.md) defines proposed future evaluations, not achieved scores.
