# Verified recovery and durable releases

Baseline: `3570f8587cb8373843455ea12ba3cd5c486151fb`. User authorization covers continued implementation, commits, main pushes and production delivery. Version target: **0.3.0**. Implementation choices below are the maintainer's choices under that continuing instruction.

## Intent and approaches

Users need to preserve their whole local workspace before an update or PC move, verify a backup, restore without overwriting an existing workspace, and reinstall the exact qualified package after Actions artifacts expire. Existing model ZIP exports deliberately omit canonical storage fields and are not backups. The current release workflow retains wheel bytes only for 14 days.

The approaches considered were live browser backup/restore, verified offline CLI operations, and manual copying documentation. Offline CLI operations are selected: the existing OS lease provides a consistent application boundary and backup remains usable if CAD or web dependencies are broken. Live restore would need a broader coordinated maintenance state and is deferred. Manual copying remains possible but cannot establish inventory or archive integrity.

For distribution, promote the exact shared wheel after all existing CI gates, rather than rebuilding at release time. The release workflow uses only GitHub's scoped job token and public repository resources; no new account or paid service is introduced.

## Backup contract

New lightweight `print_agent.backup` functions:

- `create_backup(data_dir: Path, output: Path) -> dict`
- `inspect_backup(archive: Path) -> dict`
- `restore_backup(archive: Path, destination: Path) -> dict`
- `BackupError(ValueError)` for concise actionable failures.

Creation requires an existing recognizable data directory and an explicit new output outside it. It acquires `DataDirectoryLease` before inventory/copy. A live server rejects backup. Preserve all regular files, canonical/private job records, both databases, sources, outcomes and partial files. Exclude only the root `.printer-agent.lock`; reject links, special files and nonportable/colliding paths rather than silently omit data. Archive verification concerns bytes, not healthy application data, publisher authenticity or physical printing.

The archive uses `manifest.json` and `data/<relative path>` entries. Manifest format is `3d-printer-agent-backup`, version 1, with app version, UTC creation timestamp, exact file inventory (`path`, `bytes`, `sha256`) and totals. Bounds: **20,000 files, 512 MiB per file, 4 GiB total uncompressed, 8 MiB manifest**; enforce limits on actual streamed bytes as well as declared metadata. Do not load an entire workspace into RAM. Reject duplicate keys, nonfinite metadata, undeclared/missing members, path traversal, drive/UNC paths, reserved Windows names, trailing dots/spaces, backslashes, casefold/Unicode-normalization collisions, encryption, symlinks and unsupported ZIP codecs. Accept stored/deflated entries only.

Create through a private sibling temporary file, verify all bytes, then publish without replacing an existing output. Inspection verifies complete inventory/hashes without extraction, application import, database opening or execution. Reports include `status`, `application_version`, `file_count`, `total_bytes`, `archive_bytes`, `archive_sha256`, and absolute `archive_path`; status is `created`, `verified` or `restored`, with `data_dir` for restore.

Restore validates into a private sibling staging directory. Call the lightweight compatibility gate on staged data. Publish a complete directory with an atomic **no-replace** operation; any preexisting destination, including an empty directory/symlink or one created during publication, must survive unchanged. Platform-specific no-replace primitives may be used with no unsafe overwrite fallback; actual Linux/macOS/Windows CI must qualify them. Failure removes only owned staging files, leaves the destination absent and does not touch source/other folders. Restore does not start the app, change its default path, repair records, execute generated code or replay operations.

CLI preserves serve/doctor and adds:

```text
printer-agent backup --data-dir SOURCE --output ARCHIVE
printer-agent backup-info --archive ARCHIVE
printer-agent restore --archive ARCHIVE --destination NEW_FOLDER
```

All outputs are JSON. Actionable backup/runtime/IO errors exit 1 without a traceback or archive contents. Invalid argument combinations exit 2. Explicit archive/output/destination are mandatory; no overwrite/merge/force switch.

## Compatibility correction

`runtime.require_compatible_data(root: Path) -> dict` performs read-only checks before either production store is created or recovered. It allows absent/empty initialized stores and physically corrupt **derived history** that the existing recovery can preserve/rebuild. Unknown schemas, unavailable reads and corrupt **canonical workspace** data raise `StorageCompatibilityError(RuntimeError)`. On rejection neither database is changed and the other store is not created. Restore uses the same gate, without importing CAD/web modules. The gate does not certify every job file or physical result.

## Purchase comparison correction

Preserve the existing form lock while comparison is pending, including the externally associated currency selector. Defensive controller guards ignore comparison successes and failures if code changes exact input state after submission, including numerically equal spelling, empty/invalid numeric inputs, currency and shipping conditions. The audit's initial late-price reproduction used a programmatic change; it was not a normal edit through the locked UI. Do not make inputs editable merely to reproduce it. Nonempty/invalid purchase input or an in-flight comparison participates in the existing page-exit protection. Comparisons are not saved workspaces. Preserve the existing input-only price calculation; no shopping network calls.

## Release promotion

An automatic workflow on successful completion of the three named workflows checks **the same current main push commit** and latest run outcomes for `.github/workflows/ci.yml`, `package-qualification.yml`, and `native-bambu.yml`. Fork/PR/other branch/old commit events cannot publish. Incomplete gates are a reported no-op. Download the existing package artifacts, verify GitHub archive digests, wheel receipt and installed reports/source/version identity, and publish those exact qualified bytes with checksums and a release evidence manifest.

Use minimal `actions: read` and `contents: write` permissions. Never execute downloaded code/artifacts or reveal tokens/signed URLs. An existing version/tag is never moved and existing assets are never overwritten or deleted. Create a draft, upload/verify its complete expected assets, then publish. A partial failure leaves a draft; reruns may resume only the exact matching draft/source and matching existing bytes. A published release is immutable to this workflow. No rebuilt wheel, unqualified success claim, permanent availability claim before actual publication, signing claim or automatic app updater.

## Verification and limits

Meaningful failing regressions precede behavior changes. Full Python/controller/syntax gates remain required. Add real-browser delayed comparison tests and extend the existing three-OS installed-wheel gate through live-owner rejection, real backup, read-only inspection, fresh-path restore, exact source/draft preservation, restored server startup/downloads and failed restore preservation. The native regression remains a separate Linux synthetic path. Inspect actual CI artifacts and public release bytes before reporting completion. No local browser/native retries or privilege escalation; no real provider or physical printer is used.

Installation docs must describe the `libgl1` package used by verified Ubuntu CI separately from pip dependencies. Explain that backup is unencrypted, contains saved local data, does not capture unsaved browser drafts, and preserves bytes without asserting healthy data. Preserve rollback guidance and the distinction from model exports.
