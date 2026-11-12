# 3D Printer Agent First Workflow Implementation Plan

> For agentic workers: execute disjoint components against the contracts below; run meaningful behavior tests, then an independent review.

**Goal:** Deliver an executable local first workflow and verified sample print files.
**Architecture:** A local FastAPI host serves a static UI and typed tool operations. CAD and profile decisions are deterministic; optional LLM planning never executes unvalidated code.
**Tech Stack:** Python 3.12, FastAPI, uvicorn, CadQuery, httpx, plain JavaScript and a Canvas mesh viewer.
**Spec:** docs/superpowers/specs/2026-11-12-first-workflow.md

## Global Constraints
Follow every constraint in the spec. Project name is provisional. No physical printer actions. Do not fabricate results or prices. Keep source authority separate from measured validation. No inherited partial profile as full config. Loopback-only service; no secrets in responses or artifacts.

## Review Focus
1. Dimension and unit parsing must reject or clarify unsupported values rather than silently generating the wrong part.
2. A profile for a different machine/nozzle/material must never appear ready.
3. Slicer success requires a fresh sliced artifact, not exit code alone.
4. External sites must not be able to mutate local jobs or invoke tools.
5. Each output and preview must correspond to the same requested parameters and job.

## Tasks
- [x] Geometry module and actual export tests: print_agent/geometry.py, tests/test_geometry.py.
- [x] Profile evidence engine and calibration tests: print_agent/profiles.py, tests/test_profiles.py.
- [x] Bambu executable/command/result adapter and tests: print_agent/slicer.py, tests/test_slicer.py. Native Bambu execution remains unverified.
- [x] Root: planner, offers, API, storage, CLI and their integration tests.
- [x] Korean web UI, Canvas preview, import/export/history; static references and JavaScript syntax checked.
- [ ] Real browser visual/interaction verification — blocked by the execution environment's Chromium IPC policy; escalation rejected. No visual pass claimed.
- [x] Three real sample jobs, user guide, benchmark proposal, independent review. Packaging and final verification recorded in docs/VERIFICATION.md.

## Interfaces
See docs/CONTRACTS.md for exact signatures and JSON structures. Components do not modify each other's files. Root owns schemas.py and shared app files. Use unittest (available in stdlib); runtime has no pytest installed. Agent workers must run tests after implementation and report native-versus-mocked evidence separately.
