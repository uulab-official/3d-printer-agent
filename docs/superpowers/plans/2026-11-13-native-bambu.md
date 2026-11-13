# Native Bambu integration implementation plan

Design: `docs/superpowers/specs/2026-11-13-native-bambu-design.md`.

1. Reproduce the output-path, metadata/type, identity, plate-selection and mutable-readback contract errors with focused tests; fix the adapter and preserve strict staged inputs.
2. Expose the explicit native CLI probe through authenticated API and an opt-in doctor flag; align full configuration request limits.
3. Implement separate-file assembly, source previews, pending-change invalidation and version/archive-digest presentation in the UI; extend controller and browser scenarios.
4. Run an original small model through a digest-pinned native release on Ubuntu, preserving official configuration examples and all observed diagnostics. Use the result to determine a truthful adapter qualification fixture.
5. Review changes independently, fix concrete findings, run local required gates, and document actual capabilities and limits.
6. Commit/push the integrated change to `main`, verify the full CI and native qualification results, inspect retained artifacts, and record exact evidence.

Ownership is split between adapter/tests, UI/tests, native workflow/script, and root API/CLI/docs. The temporary native investigation branch must not change the local `main` checkout or overwrite concurrent edits. No downloaded binaries, third-party configuration files, runtime stores or generated QA artifacts belong in the commit.

## Completion evidence

Steps 1–6 are complete. Feature commit `b746d0b2f54fc361fa72fc82374ffe2012683096` and focused overflow correction `2e29040597b3f948a7bdb01bf5da34ebaf991a69` are on `main`. The final code passed [application CI 43376181601](https://github.com/uulab-official/3d-printer-agent/actions/runs/43376181601): 181 Python tests, 38 controller tests, 14 Chromium workflows and package checks. It also passed [native CI 43376181533](https://github.com/uulab-official/3d-printer-agent/actions/runs/43376181533) with the real Studio release, unchanged official examples, and both original STL/3MF adapter inputs. Each app output matched 30 independent core expectations. Source/output hashes, reports and helper screenshots were inspected.

Actual native runs identified a machine-lineage/process-compatibility requirement absent from the earlier test double. The current supported path now requires a native root machine and exact process compatibility, preserves user metadata, and explains unsupported lineage. An independent oracle correction retained strict comparison while representing four native speed fields as the observed singleton arrays. Separate review found and reproduced deep/malformed/overflowing project-setting failures; regression tests cover their corrected needs-review/blocking behavior. Qualification remains version-specific and synthetic; no physical printer, vendor preset recommendation or full native inheritance resolver was qualified. See `docs/VERIFICATION.md` for exact evidence and remaining limits.

The final verification-record commit is documentation only and preserves the tested application, tests and workflows.
