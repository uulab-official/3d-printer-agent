# Useful project discovery

Baseline: `ce7d0854ffa8e3ee37ed7e2e7934b2a22156a457`.

## Intent and implementation choice

Help a beginner choose something useful, understand what to measure, and reach the existing editable CAD workflow. The user previously requested beginner recommendations and has authorized continued implementation and publication to `main`. The choices below are implementation decisions for that continuing work, not a claim that the user selected every detail.

Considered approaches:

1. Add more static template cards. Small, but does not explain suitability or preserve the starting design in generated work.
2. A local, deterministic project catalog with purpose/space filtering and recorded design origin. Chosen: it works without a model server or new service and reaches actual supported CAD generation.
3. Live external model search or LLM-only recommendations. Deferred: source retrieval, model-specific reuse conditions and unsupported geometry would be separate capabilities.

## Scope

- Six original starting projects using the three existing templates, not six new geometry families.
- Purpose filtering and optional **placement-space** dimensions. This compares external bounding boxes, not printer-bed compatibility, brim clearance, functional fit or measured print dimensions.
- Selecting a card previews its explanation; an explicit action prepares editable parameters. No CAD/native action happens just from browsing.
- Generated jobs, manifests and bundles retain the server-resolved recipe alongside actual customized parameters.
- Keep existing template cards, free-text planning, jobs and all filament/native flows working.
- No new dependency, DB migration, LLM requirement, external platform API, live product price or printer action.

## Catalog and matching contract

New `print_agent/discovery.py` owns the catalog and pure matching/selection functions. `GeometryRequest` and deterministic geometry generation stay unchanged.

`project_catalog() -> dict` returns a fresh JSON-compatible object:

- `schema_version: 1`
- `purposes`: `all` (전체), `organization` (책상·서랍 정리), `cables` (케이블 정리), `display` (사진·장식), each with `id` and `title`.
- `projects`: six cards in the order below.

Each card contains `id`, `title`, `purpose`, `description`, `reason`, `measurements` (strings), `limits` (strings), `template`, complete normalized `parameters`, `source`, and `recipe_sha256`. A recipe is the card without `recipe_sha256`; its digest is SHA-256 over UTF-8 JSON with `ensure_ascii=False`, `sort_keys=True`, `separators=(',', ':')`, `allow_nan=False`. Source keys are `kind: 'repository_original'`, `repository: 'https://github.com/uulab-official/3d-printer-agent'`, `path: 'print_agent/geometry.py'`, `creator: 'uulab-official'`, and `license: 'MIT'`. It does not authenticate any third-party model.

| ID | Title | Purpose | Template | Explicit starting parameters beyond neutral GeometryRequest defaults |
|---|---|---|---|---|
| `small-parts-tray` | 작은 물건 트레이 | organization | tray | width 90, depth 60, height 18, wall 2, bottom 2, dividers 0 |
| `desk-sorter` | 세 칸 책상 정리함 | organization | tray | width 150, depth 90, height 30, wall 2, bottom 2, dividers 2 |
| `drawer-tray` | 두 칸 서랍 트레이 | organization | tray | width 180, depth 100, height 35, wall 2, bottom 2, dividers 1 |
| `three-cable-rest` | 세 줄 케이블 받침 | cables | cable_comb | width 50, depth 18, height 12, wall 2, bottom 2, slots 3, cable_diameter 6, fit_clearance 0.3 |
| `five-cable-rest` | 다섯 줄 케이블 받침 | cables | cable_comb | width 80, depth 18, height 12, wall 2, bottom 2, slots 5, cable_diameter 6, fit_clearance 0.3 |
| `round-insert-frame` | 원형 사진 인셋 프레임 | display | magnet_frame | width 65, depth 65, height 7, wall 2, bottom 2, inset_diameter 52, inset_depth 2, fit_clearance 0.3 |

The text describes use and measurement prompts, not verified retention, strength, support, material, cost, print time or success. Cable channels are open, and the frame has a pocket but no added hanger, stand or magnet-retention mechanism. Tray sizes are exterior dimensions; users need to measure usable space and contents.

`AvailableSpace` accepts optional `width`, `depth`, `height` numeric fields, each finite, strictly positive and at most 10000 mm. Missing axes are unknown. Booleans, numeric strings, unknown fields, zero and nonfinite values are rejected.

`DiscoveryRequest` has `purpose` (the four exact values, default `all`) and `available_space: AvailableSpace` (default empty). `recommend_projects(request: DiscoveryRequest) -> dict` returns:

- `schema_version: 1`, normalized `query`, `total_in_purpose`, `excluded_count`.
- `matches`: objects with `project` (catalog card), `space_fit` and `reason`.
- `space_fit`: `status` is `not_checked`, `fits`, or `fits_rotated`; `orientation` is null, `original`, or `rotated_90`; `checked_axes` lists supplied axes; `dimensions_mm` contains width/depth/height of that compared orientation.
- `limits`: concise size-comparison scope.

No axes means `not_checked`. Otherwise test the stated width/depth first, then only a 90-degree rotation in the horizontal plane; height is never swapped. Include only matches; preserve catalog order. There is no hidden scaling, geometry change, margin or score. Zero matches is a useful result that offers changing the conditions or editing a generic template. Recommendations do not become an ongoing fit guarantee after the user changes dimensions.

## API and persisted source

Bootstrap adds `discovery: project_catalog()`. `POST /api/discovery` accepts `DiscoveryRequest` through the existing local session/JSON boundary and returns `recommend_projects` without storing a job or invoking CAD.

Keep `/api/models` backward compatible with flat geometry requests. A new API-only `ModelPayload(GeometryRequest)` adds optional `project_selection: ProjectSelection | None`. `ProjectSelection` allows only `id` and a lowercase 64-hex `recipe_sha256`; extra metadata is rejected.

`resolve_project_selection(selection: ProjectSelection, spec: GeometryRequest) -> dict` validates ID, digest and matching template against the current server catalog. Unknown IDs/template mismatch raise `ValueError` (HTTP 422); a changed digest raises `StaleProjectSelection` (HTTP 409). Resolve before reserving a job. Strip selection before making a pure geometry request; never execute catalog strings or client-supplied source metadata.

The returned `design_source` snapshot contains:

- `kind: 'project_catalog'`, `schema_version: 1`, `project_id`, `recipe_sha256`.
- `recipe`: the exact server-owned recipe used for that digest.
- `customized`: comparison of normalized actual parameters against the original recipe parameters.
- `changed_parameters`: sorted names of differing parameters.

`JobStore.finish(job_id, result, *, design_source=None)` deep-copies an explicitly supplied source to the job and manifest. Requests without selection and old jobs continue without an invented source. Existing manifest parameters, artifact hashes and reproduction source describe actual generated geometry. No source claim changes `physical_print_status` or slicing state.

## UI and state contract

Add a labelled discovery section above the existing three template cards. Purpose buttons use `aria-pressed`; optional placement dimensions have visible labels and units. Use a responsive card grid, measurement prompts, starting dimensions and restrained code-native illustrations. Clearly identify these as local original starting designs. Existing templates remain directly available.

Keep filter inputs/results, browsed project, applied draft source, and generated-job source separate. Filter edits and card browsing must preserve exact live parameter input strings, request text, existing preview/downloads and selected source. Reject partial numeric input (`badInput`) instead of treating it as an omitted axis. Async recommendation results must be discarded when filter inputs or bootstrap context changed.

Applying a project requires a separate button. When the current draft has edits or a generated job, present an inline replacement choice; cancellation preserves the exact existing state. Check live DOM input values/validity, not only `state.parameters`. Applying uses `applyDraft` and existing invalidation, focuses the parameter heading, retains the chosen source reference and does not generate CAD automatically. A rotated space match only describes placement; it must not rewrite recipe geometry.

Changing dimensions retains the starting source; selecting a generic template, resetting to template defaults, or a successful new free-text plan clears it. Provide a clear-source action that keeps current dimensions/request text and invalidates any current generated result if its provenance would otherwise be relabeled. Source text is rendered with `textContent`, not HTML.

History renders the saved recipe snapshot, never one inferred from today's catalog or matching dimensions. It may restore its ID/digest for an edited regeneration; if that recipe is no longer current, show the server conflict and allow explicit source detachment or selecting a new current project without losing dimensions. Bootstrap retry must not silently relabel or replace a draft/job. Workflow locks protect preparation/application/confirmation while generation/planning is pending, with handler guards as well as disabled controls.

Use the existing real-CAD path and local file downloads. Display actual generated origin separately from the currently browsed candidate. No `verified` badge, budget, duration, material choice or printing claim is derived from this catalog.

## Evidence required

Generate all six starting recipes through actual CadQuery and re-read STEP dimensions/solid validity. Independently recompute recipe digests and exercise invalid inputs, rotation/height boundaries, no matches and copy isolation. API tests must prove customized origin across job/manifest/bundle/reopened store, fail-before-reserve behavior, unchanged legacy requests and session protection.

Controller tests cover exact draft preservation, replacement cancel, partial numbers, old async responses, source transitions and workflow locks. Real desktop/mobile browser flows filter, select, customize, generate, download and reopen history; also exercise no results and pending/failed recommendation recovery. Existing application/package/browser gates remain required; native CI is a separate regression for the unchanged synthetic slicing path.
