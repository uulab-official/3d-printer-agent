# 3D Printer Agent: first working release

Status: implementation proposal based on this conversation, project name provisional.

## Intent
A Korean-first website and local companion helps beginners choose a useful object, customize dimensions, understand filament settings, compare purchase inputs, and prepare a real print. Local/cloud LLMs share constrained tools. Quality means measured geometry and honest execution state, not a claim to be the best available product.

## First release
A local web application runs at loopback only. It generates tray, cable-comb and circular-inset frame models using CadQuery, exports STL/STEP/3MF plus source and a reproducibility manifest, inspects user-provided filament profiles with provenance and three-state compatibility, prepares/executes Bambu CLI when available and complete configurations are supplied, offers deterministic natural-language planning with optional OpenAI-compatible LLM JSON planning, and compares user-entered filament offers without claiming live prices. Output history stores generation, geometry validation, slicing and user-reported physical outcomes separately.

## Constraints
- Millimetres are explicit. All dimensions must be finite and physically meaningful.
- No generated arbitrary Python, shell, G-code or printer controls from an LLM.
- CAD generation is real; geometry validity does not imply physical printability.
- No invented manufacturer temperatures, device specifications, live prices, print duration, filament mass, printer connection or print success.
- All model outputs are fresh job files, never overwriting source files.
- Model names and supported templates are explicit; unsupported wishes require clarification.
- Manufacturer source authority and validation-on-this-setup are separate.
- Missing evidence is unknown, not success. Unresolved profile inheritance blocks direct full-config slicing.
- Website/companion use same-origin session-protected mutation endpoints; provider API keys remain environment variables and are never sent to the browser.
- Existing Bambu Studio and printer hardware are not present in this executor; native/hardware integration stays unverified unless actually exercised.
- All work is local and reviewable. No external repository, public deployment, shopping, printer movement, heating or print initiation is performed.

## Architecture
Python 3.12, FastAPI/uvicorn, CadQuery 2.7, httpx; static HTML/CSS/JS with a Canvas mesh viewer. Geometry, profiles and slicer are separate modules. CLI and API call the same implementations. Jobs have immutable output artifacts plus atomic JSON records. A small SQLite job index supports history.

## Approaches considered
1. Content-only portal: easier discovery but cannot complete printing preparation.
2. Desktop-only agent: powerful but installation precedes discovery.
3. Website plus optional local companion: recommended; this first release implements the local companion as a local web application and preserves a future hosted portal boundary.
These are implementation recommendations, not a claim the user approved a particular stack or final brand.

## Quality evidence
Real model dimensions, positive volume, CAD validity, export reimport, invalid-input rejection, absent-slicer handling, no false-success artifacts, profile matching, stale-calibration dependencies, natural-language units, price normalization, API origin and token checks, and a visible end-to-end browser path.

Implementation record: CAD/API/contract checks were executed. The browser path remains unverified because Chromium IPC was blocked and permission escalation rejected by the configured environment policy. See docs/VERIFICATION.md for observed evidence rather than treating this target as a completed gate.

## Future product work
Hosted discovery catalog, official data feeds and live shopping provenance, broader templates/import customization, image diagnosis, native installers and updates, signed companion pairing, authenticated printer dispatch, multi-device integrations and field print benchmarks remain explicitly outside this initial release.
