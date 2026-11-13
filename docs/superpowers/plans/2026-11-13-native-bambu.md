# Native Bambu integration implementation plan

Design: `docs/superpowers/specs/2026-11-13-native-bambu-design.md`.

1. Reproduce the output-path, metadata/type, identity, plate-selection and mutable-readback contract errors with focused tests; fix the adapter and preserve strict staged inputs.
2. Expose the explicit native CLI probe through authenticated API and an opt-in doctor flag; align full configuration request limits.
3. Implement separate-file assembly, source previews, pending-change invalidation and version/archive-digest presentation in the UI; extend controller and browser scenarios.
4. Run an original small model through a digest-pinned native release on Ubuntu, preserving official configuration examples and all observed diagnostics. Use the result to determine a truthful adapter qualification fixture.
5. Review changes independently, fix concrete findings, run local required gates, and document actual capabilities and limits.
6. Commit/push the integrated change to `main`, verify the full CI and native qualification results, inspect retained artifacts, and record exact evidence.

Ownership is split between adapter/tests, UI/tests, native workflow/script, and root API/CLI/docs. The temporary native investigation branch must not change the local `main` checkout or overwrite concurrent edits. No downloaded binaries, third-party configuration files, runtime stores or generated QA artifacts belong in the commit.
