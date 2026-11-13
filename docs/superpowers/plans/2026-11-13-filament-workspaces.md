# Filament workspace implementation plan

Design: `docs/superpowers/specs/2026-11-13-filament-workspaces-design.md`.

1. Implement a bounded, atomic, revision-aware workspace store with meaningful persistence and conflict tests.
2. Extend explicit profile resolution with original-baseline comparison and stale-validation evidence; cover parent edits, unchanged chains, unused documents and unavailable originals.
3. Integrate API payloads/routes, request budgets and authenticated mutation tests.
4. Add saved-workspace controls, guided numeric edits, individual document recovery and dirty/concurrency handling. Extend controller and real browser scenarios.
5. Review the integrated diff independently, fix concrete findings and run local Python/controller/package gates.
6. Update user and contributor documentation, commit/push to main with a ref lease, run real browser CI and inspect its evidence.
7. Record exact successful verification and remaining native limits, then verify the final remote commit and clean local tree.

Implementation ownership is split by file to permit parallel work without overwriting another contributor's changes. No runtime databases, browser reports or personal settings belong in commits.

## Completion evidence

Feature commit: `101c87fea6bb27852b24bd3f18b0545c12c06915`. [CI run 43371025397](https://github.com/uulab-official/3d-printer-agent/actions/runs/43371025397) passed 149 Python tests, 27 controller tests, 14 Chromium workflows and package installation checks. Independent review findings were reproduced and fixed before publication. Downloaded reports, canonical hashes and desktop/mobile screenshots were inspected. A subsequent UI copy correction (`156fa5abb7c0bbc483656fd923d8e2b931a12a4a`) clarifies the separate original/draft collection limits. See `docs/VERIFICATION.md` for the complete evidence and remaining qualification boundaries.

The copy correction also passed every gate with the same test counts in [final CI run 43371431939](https://github.com/uulab-official/3d-printer-agent/actions/runs/43371431939). Steps 1–7 are complete; the final record update changes documentation only and preserves the tested application, tests and workflow.
