# Local production-readiness implementation plan

Baseline: `97a2c05667cdb48ae9c573c27b5008dacaff684e`.
Spec: [local-production-readiness](../specs/2026-11-14-local-production-readiness.md).

User authorization covers implementation and main commits/pushes. Preserve unrelated changes. Independent file-owned tasks may proceed in parallel; root integrates contracts and obtains a fresh final review. Existing blocked local browser/native execution is not retried.

## Progress

- [x] Inspect current source and remote main; reproduce user-impacting runtime, UX and installation gaps through independent audits.
- [x] Define bounded lifecycle, data, recovery, pagination and package qualification interfaces.
- [x] Runtime/storage implementation and behavior regressions.
- [x] Diagnostics/CLI and installed-package qualification implementation.
- [x] UI reconnection, draft protection and reliable history implementation.
- [x] API/lifespan/provider integration and actual browser workflow definitions.
- [ ] Full local required gates, installed wheel verification and independent final review.
- [ ] Publish with expected-head protection; inspect application, cross-platform package and native CI.
- [ ] Record observed evidence and remaining platform/hardware limits; publish documentation follow-up.

## File ownership

1. Storage implementer: `print_agent/storage.py`, `tests/test_storage.py`, new focused storage tests. Own recovery, receipts, exact verified bytes and pagination. Do not change API/CLI/UI.
2. Delivery implementer: new `print_agent/runtime.py`, `print_agent/__main__.py`, `tests/test_cli.py`, new runtime tests, new `scripts/qualify_install.py`, new package qualification workflow. Own data-path selection, lease, diagnostics and installed-wheel gate. Root owns packaging/version changes and existing workflows.
3. UI implementer: `print_agent/static/app.js`, `index.html`, `style.css`, `tests/test_ui_state.cjs`. Own session recovery, protected model/history transitions, cursor UI and storage/connection display. Do not change browser tests or backend.
4. Root: `print_agent/app.py`, `planner.py`, API/provider tests, browser tests, package/version metadata and all documentation. Integrate lifecycle, admission control, session bytes, downloads and provider streaming.

## Gates

- Reproduce target defects before implementing them; meaningful regression tests cover failure and recovery, not code structure.
- Python 3.12 full unittest suite; JavaScript syntax and controller regressions; browser test discovery; diff checks; wheel contents matching source.
- Fresh read-only integrated review, followed by focused fixes and verification of concrete findings.
- Real Chromium workflows in Actions on the exact code commit; inspect relevant screenshots, downloaded files and reports.
- Installed wheel on Ubuntu 24.04, macOS 15 and Windows 2025, Python 3.12; actual CAD/API/persistence/recovery using a Unicode/space-containing data path outside the checkout. Native Studio evidence remains a separate workflow.
- Never treat a configured workflow as a passed result. Preserve tested wheel/checksum and platform reports. Record failed attempts and any corrections honestly.

## Initial audit evidence

Two stores lost a successfully written outcome during a concurrent slice update. Missing/stale SQLite index entries survived reopening even when their canonical job files were valid. A reserved job stayed `generating` after reopening. A truncated real model 3MF returned HTTP 200. Provider streams consumed 1,048,576 bytes before the nominal 100,000-byte rejection. Non-ASCII session bytes caused HTTP 500.

Controller probes showed no page-exit protection for model-only edits/active CAD, unconfirmed history replacement of an unfinished draft, an old failed history refresh erasing a newer successful list, and an expired session retaining the old token while the reconnect control stayed hidden. A 101st historical job was readable by ID but unreachable through listing.

`doctor --data-dir <regular file>` returned success, while a failed CadQuery import escaped without a report. Installed-wheel checks only covered imports/assets on Linux. All probes used temporary/synthetic inputs, with no physical printer or live provider.

## Integration and review ledger

The initial full integration run passed 325 of 328 Python checks. Three existing API checks exposed an unintended addition to the no-query history response. The original `{jobs}` shape was restored; pagination metadata is returned only when paging parameters are requested. The subsequent complete suite passed 331 checks, including new review regressions.

Independent review reproduced stale successful responses crossing a reconnect, a previous slice remaining current when the new source failed integrity checks, compressed provider allocation before the response cap, and diagnostics incorrectly promising repair of an incompatible schema. Focused regressions failed before correction. Fixes reject old connection-epoch results without replay, begin a slice attempt before source verification, request/restrict identity encoding before reading, and preserve unrecognized database schemas without a repair promise. Narrow re-review and actual package/browser qualification are recorded with the observed results in the verification log.
