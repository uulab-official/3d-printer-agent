# Native Bambu Studio integration design

## Goal

Make the existing local slicing workflow match an observed Bambu Studio CLI contract, and make configuration preparation understandable without hand-authoring the wrapper JSON. Continue on the user's authorized `main` publication path after review and verification.

## Scope

- Correct output path handling, native preset metadata/types and setting identities against the pinned Bambu Studio v02.09.01.70 source.
- Bind an explicitly selected build plate to both CLI execution and exported-setting verification. Preserve temperature values supplied by the user.
- Detect altered staged settings and expected values before execution; record the probed version and verified archive SHA-256.
- Add an explicit installation/CLI probe in the local UI and `doctor --probe-slicer`. Opening the app and ordinary `doctor` remain discovery-only.
- Assemble a bundle from one machine, one process and one to sixteen filament JSON files, with a plate choice. Preserve the documents and the manual JSON input path. Stage changes separately and invalidate previous preparation.
- Run the pinned real native release against an original small model in a separate Ubuntu qualification workflow. Keep native results separate from subprocess fixtures and physical printing.

## Boundaries

The helper accepts existing full configurations; it does not synthesize a complete vendor profile. Unresolved inheritance/includes, unsupported representations and missing selected-plate temperatures are actionable blockers. Do not remove inheritance metadata or guess a variant to manufacture a passing result. Official CLI examples are fetched by immutable digest for investigation and retain their original terms; they are not vendored as project-authored recommendations.

Native success requires a fresh archive containing G-code and verified core settings. A CLI version probe, process exit code, or geometry-only 3MF alone is insufficient. Output time and material estimates remain unknown until a version-specific parser is implemented. This milestone does not connect to a printer or claim a measured print result.

## API and state

`POST /api/slicer/probe {}` returns the environment object directly, with `available` (file discovery), `cli_supported` (actual help contract), `path`, `version`, `capabilities`, `diagnostics`, and `printer_status: not_checked`. It uses the existing local token/origin boundary and accepts no executable or command from the browser.

`POST /api/slice` retains its current route and carries a maximum 8 MiB JSON request. Bundles add required `plate_type` using native CLI enum values. Machine/process/filament inputs are unchanged JSON objects with correct `type`, nonempty `name`, and accepted `from` metadata. Empty native settings IDs may be filled by Studio from `name`; conflicting explicit IDs are rejected.

The file helper keeps accepted staged files separate from manual JSON. Import failure preserves existing text and accepted files. Changing files or plate invalidates preparation and blocks prepare/execute until assembly or cancellation. Late file/probe results cannot silently restore an obsolete plan.

## Evidence

Use focused regression tests for native contract failures and request/state transitions, the existing complete Python/controller/browser/package gates, and real native logs with exact executable/input/output hashes. Independent review precedes publication. Record native environment limitations and the actual qualification outcome without upgrading synthetic evidence into printer compatibility.
