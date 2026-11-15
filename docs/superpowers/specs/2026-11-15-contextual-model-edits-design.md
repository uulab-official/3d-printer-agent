# Contextual model edits — v0.7

## Outcome and scope

Let a person change the current tray, cable comb or magnet frame with a short request while preserving every unspecified parameter and the original beginner-project identity. Show the actual before/after values, require explicit application, then generate a new reproducible model. The latest accepted edit is recorded in the job and exported manifest. The application remains a local, single-user tool. This release does not add arbitrary CAD, imported-mesh editing, physical printer control, live shopping or a MakerWorld API.

The user has already authorized continued implementation, commits, main pushes and releases. Architecture choices here are implementation decisions under that instruction; no additional approval checkpoint is needed. Existing protected storage, local-session boundaries and same-source release gates remain in force. No local browser/Chromium or native Bambu/AppImage installation, execution, retry or escalation is permitted in this work session; browser/native evidence must come from GitHub CI.

## User flow

The model panel gains a distinct **현재 제작안 수정** section. A user chooses rules or the existing optional LLM, writes a request, and asks for a proposal. A proposal displays changed fields and their before/after values; it does not alter inputs, a generated preview, downloads, slicing state or notes. Apply changes only after the user presses its apply button. Cancel preserves the exact current draft and job. Applying invalidates the old generated result and slice, preserves project source, and carries an accepted selection into the next generation. Subsequent manual dimension changes detach that selection. No CAD generation or slicing starts automatically.

Examples: current tray 150 × 90 × 30 mm, wall 2, bottom 2, dividers 2; “높이를 5mm 늘려줘” changes only height to 35. “가로 160mm, 4칸” changes only width to 160 and dividers to 3. “벽 두께를 0.2mm 줄여줘” changes only wall to 1.8. Cable diameter applies only to a cable comb. Ambiguous size requests, global scaling, template switches, unsupported features, contradictory edits, invalid resulting geometry, mixed understood/unsupported clauses and zero-effect edits return clarification without a partial proposal.

The current new-model planner has two confirmed defects to fix with this work: it silently replaces a dirty draft and can lose unsaved print-outcome notes; its first XYZ match ignores a later conflicting triple. Successful new-model plans must use the existing replacement-confirmation UI when there is pending work. Every path that replaces or invalidates a job, including regeneration of unchanged dimensions, must retain unsaved outcome drafts with their original job and storage location. Retained notes never attach to the new model. Failed, canceled or stale operations leave current inputs and notes intact.

## Pure edit contract

New module `print_agent/model_edits.py` exposes:

```python
normalize_parameters(base: dict) -> dict
review_model_edit(selection: dict) -> dict
model_edit_record(selection: dict, parameters: dict) -> dict
validate_model_edit_record(record: dict, parameters: dict) -> dict
plan_model_edit(text: str, base: dict, *, parent: dict | None = None) -> dict
async def plan_model_edit_with_llm(text: str, base: dict, *, parent: dict | None = None) -> dict
```

`normalize_parameters` requires an explicit supported template and all fields editable for that template. It accepts the other fields only at the existing neutral defaults. It rejects unknown fields, booleans, strings, nonfinite numbers and missing applicable fields; count fields are strict integers. It returns the full normalized `GeometryRequest.model_dump()` (12 keys including template). It also checks cross-field geometry constraints. Existing schemas and neutral defaults remain authoritative.

Move the exact `_validate_geometry` function from `geometry.py` into pure `geometry_rules.py`, retaining its name and behavior. Import it in both geometry and model_edits. The standalone reproduction-source generator uses `inspect.getsource` and must still embed a function named `_validate_geometry`; its output must remain independently executable.

An operation is exactly `{field, op, value}`. `field` is an editable field for the selected template; `op` is `set` or `add`; `value` is a finite JSON number. Count fields `dividers` and `slots` allow only `set` with a strict integer. No duplicate fields, extra keys, empty operations, or more than 12 operations. Calculate additions with decimal arithmetic from numeric strings, then normalize and validate the entire result. Unchanged fields must remain identical. A selection with no actual changed value is invalid.

Before hashing, canonical length operation values and every non-count geometry field are Python floats with zero normalized to positive `0.0`; counts stay strict integers. This makes a browser JSON round trip (`5.0` → `5`, `-0.0` → `0`) rederive the exact same selection, parent parameter hash and review hash. Raw numeric validation still precedes normalization. Stored records must match the canonical rederivation exactly.

Canonical selection (exact keys):

```json
{"schema_version":1,"request_text":"높이를 5mm 늘려줘","base_parameters":{"template":"tray","width":150.0,"depth":90.0,"height":30.0,"wall":2.0,"bottom":2.0,"dividers":2,"slots":5,"cable_diameter":6.0,"inset_diameter":52.0,"inset_depth":2.0,"fit_clearance":0.3},"operations":[{"field":"height","op":"add","value":5.0}],"parent":null}
```

`schema_version` is strictly integer 1, not boolean or float. `request_text` is the original nonblank string, at most 4000 characters. Canonical selection retains exact request text and normalized numeric parameters. An optional parent is exactly `{job_id, parameters_sha256, model_sha256, manifest_sha256}`, lowercase hex lengths 32/64/64/64. Its parameters hash must match the base. Canonical JSON for hashes uses UTF-8, `ensure_ascii=False`, sorted keys, compact separators and `allow_nan=False`.

`review_model_edit` returns exactly `{schema_version:1, selection, base_sha256, parameters, parameters_sha256, changes, review_sha256}`. `changes` is a deterministic list in schema field order, each exactly `{field,before,after}`, containing all and only changed fields. `review_sha256` hashes `{schema_version,selection,base_sha256,parameters_sha256,changes}`. It describes the parameters the user can review, not an authenticated provider response.

`model_edit_record` rederives the review and requires the supplied generated parameters to equal its normalized result; it returns the review plus `provenance: "user_confirmed_parameters"`. `validate_model_edit_record` requires exact record keys and exact canonical agreement with rederivation. Records are bounded by the existing JSON/request limits. They contain no provider keys, URLs, output prose or print-success claim. This is the latest selected edit, not a complete conversational audit trail.

## Planning and provider boundary

`POST /api/model-edits/plan` accepts exactly `text`, `mode` (`templates` or `llm`), `base_parameters`, and optional `parent_job_id` (32 lowercase hex). Normalize and validate the base and resolve the optional parent before requesting a provider. Ready responses have `status: ready`, `engine: template_rules|llm`, `capability: current_template_parameters_only`, fixed application message, empty questions/assumptions, and `review`. Clarification responses have `status: needs_input`, the same capability and engine, a fixed application message/questions, and **no review or parameters**. Other-workflow routing may return the existing action contract without an edit. HTTP validation or provider failures must not expose secrets or response bodies.

Rules handle Korean common field aliases, absolute sizes, increase/decrease amounts, mm/cm conversion and absolute counts. Explicitly reject requests whose meaningful editing clauses cannot be fully understood. Ambiguity may be resolved by requesting a more specific request, never by guessing or applying a supported subset. Grammar details beyond the examples are the builder's choice, but tests must demonstrate mixed unsupported clauses and conflicting same-field operations fail closed.

Optional LLM uses a typed operation response (operations plus bounded clarification questions), never replacement geometry or executable code. It receives only the request and validated current numeric parameters. Extract the existing protected HTTP transport into `planner.request_llm_json(system: str, text: str) -> dict` and reuse it for both planners. Preserve the 60-second total deadline, bounded streamed body, local/HTTPS provider validation, disabled redirects, `trust_env=False`, no error-body echo and fixed application-generated user messages. The new system prompt lists applicable fields and instructs clarification for unsupported or mixed requests. Validate returned operations with the same pure engine. Synthetic provider tests must be clearly labeled; no live-provider qualification claim.

For the existing new-model planner, inspect **all** XYZ triples, convert mm/cm before comparison, reject conflicting triples or conflicts with named dimensions, and accept equivalent repeated triples. Preserve other existing behavior.

## Persistence and parent identity

`JobStore.model_edit_parent(job_id, base_parameters)` returns the verified parent identity above. Require a geometry-validated job whose actual normalized parameters equal the supplied base, verified manifest bytes identifying the same job/parameters, and verified original model.3mf bytes matching the manifest receipt. Integrity failures must not silently produce a parentless proposal. A parent is provenance of observed model bytes, not printability evidence.

`ModelPayload` adds optional `model_edit` selection, alongside existing `project_selection`. Before reserving a job or starting CAD, derive its record against the submitted geometry and recheck the parent identity if supplied. Missing, changed, mismatched or unreadable parent at generation returns HTTP 409 with code `model_edit_parent_changed` and performs no reservation/generation. Initial planning may retain existing invalid/not-found/integrity error semantics. No background CAD or partial application follows a failed check.

`JobStore.reserve(..., model_edit=None)` accepts the full canonical record (not the selection), validates it against the original uncoerced request with `validate_model_edit_record`, and stores an immutable copy before creating a job folder. `finish` validates it against actual result parameters and includes it in manifest and public job. `_read` validates optional saved records structurally and by rederivation, rejecting corruption. Existing jobs without a record retain their current behavior. Validating an old child record does not recursively open its parent; parent revalidation occurs when using that parent for a new edit. Existing bundles and backups preserve the record through manifest/job files with no new database schema. Source recipe identity and edit identity coexist. Repeated pre-generation edits record only the latest selection; a generated matching current job supplies a parent, otherwise parent is null.

Paginated job summaries expose an optional `model_edit` record so the history list can show its request and changes. Read and validate only the displayed page's canonical jobs under the store lock; preserve existing SQL ordering/cursors and legacy summary fields. A missing or corrupt canonical job is represented as unreadable with the fixed diagnostic, without exposing unverified edits or internal fields. Listing does not mutate the index, scan additional job pages, open parent/artifact files or require a database schema migration.

## UI correctness

Proposal scope captures exact raw input strings and bad-input state, template, project source, current job identity, connection/storage epoch, edit text/mode and request ownership. Changed or reconnected scope invalidates candidates and ignores late responses. Request completion releases only its own busy state even if the response is stale. Validate complete responses before displaying: supported template, full base/result fields, numeric values, unchanged-field identity, complete before/after changes, expected engine, parent context and hash syntax. Generation is authoritative and rederives the applied selection server-side.

The new-model replacement confirmation must run after its request releases workflow-busy state. Applying a contextual edit is itself explicit confirmation; retain dirty outcome notes before invalidation, with original job/storage association and readable copyable text. Expose recorded edits in generated-job/history views. Do not silently carry a current edit selection into a restored unrelated history job. Retained notes continue to participate in pending-work protection.

## Evidence and release acceptance

Behavior tests must prove unchanged dimensions, strict/invalid operations and geometry, provider bounds, confirmed application, stale/failure/cancel preservation, note retention, source identity, record tamper rejection and parent changes before CAD. Real generated CAD must round-trip through job, manifest, bundle, restart and backup/restore. Installed qualification must exercise an edited beginner recipe and prepare its current model for Studio without claiming native/physical output. Browser CI must exercise the contextual flow and dirty new-plan protection on desktop and mobile and save structured evidence plus screenshots. Preserve existing scenarios. Native CI remains regression coverage of the four existing synthetic paths.

Release v0.7.0 only from one exact source commit whose CI, three-OS installed-wheel qualification and native workflow all pass. Independently read back evidence; promote the already-qualified identical wheel and verify the published assets. Record concrete limits and residual native diagnostics. Never substitute fixture checks for real provider, physical printer or hardware qualification.
