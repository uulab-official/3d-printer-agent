# Development status

Date: 2026-11-12 (Asia/Seoul).

Canonical repository: [uulab-official/3d-printer-agent](https://github.com/uulab-official/3d-printer-agent). The initial local prototype is the open-source v0.1 baseline. This is an experimental local application, not a claim of production or physical-print qualification.

## Implemented

The app generates three parameterized CAD models; reviews user-supplied filament evidence and calibration changes; prepares Bambu CLI jobs; calculates user-entered delivered prices; and stores job artifacts and user reports. The optional LLM adapter only proposes supported typed model parameters. The Korean UI provides the same operations locally.

The original local validation is documented in [VERIFICATION.md](VERIFICATION.md). Current unit, package and browser results are recorded per commit in [GitHub Actions](https://github.com/uulab-official/3d-printer-agent/actions). A workflow definition alone is not evidence of a successful run.

Repository adoption checks passed locally: **90 Python tests and 5 UI-controller tests**. The additional regressions keep invalid optional LLM URLs from breaking template mode and make failed CAD jobs inspectable in history. Six real-browser tests are defined for desktop and mobile; their actual run result is reported by CI.

## Remaining qualifications

Actual Bambu Studio versions, macOS/Windows native installation, real LLM servers and physical printing require separate qualification. The original local environment blocked Chromium IPC, so its static/Canvas/controller checks must not be reported as a full browser pass. GitHub Actions is configured to perform that missing real-browser path.

Source authenticity checks, inherited-profile resolution, MakerWorld access/customization and live product collection are future capabilities. No external platform API is assumed to be available or authorized until verified.

## Next product milestones

1. **Exact filament to usable settings:** identify a product and hardware setup, retrieve attributable source material, resolve full preset inheritance, and show unknown/conflicting values.
2. **One real Bambu setup:** verify the installed Studio version, full configuration, slice read-back and measured physical result for one known printer/nozzle/plate/filament combination.
3. **Beginner discovery and customization:** introduce useful-object recommendations and model-source-aware edits, with original files and reuse conditions recorded.
4. **Website and local companion:** add a hosted discovery surface with an explicitly paired local execution component; keep heavy CAD/native work on the user's machine.
5. **Condition-aware shopping and memory:** compare observed offers under matching purchase conditions and reuse outcomes only for matching setups.

The detailed scope is in [PRODUCT_ROADMAP.md](PRODUCT_ROADMAP.md). [BENCHMARKS.md](BENCHMARKS.md) defines proposed future evaluations, not achieved scores.
