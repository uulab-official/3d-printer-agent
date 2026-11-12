# First release component contracts

Repository: https://github.com/uulab-official/3d-printer-agent (paths below are relative to the repository root).
Runtime: Python 3.12.14; cadquery 2.7.0; fastapi 0.141.1; uvicorn 0.52.1; pydantic 2.13.4; httpx 0.28.1.
The ownership notes below record the initial parallel implementation only. Current contribution guidance is in CONTRIBUTING.md and AGENTS.md. Shared input schemas live in print_agent/schemas.py.

## Geometry worker
Implement `generate_model(spec: GeometryRequest, output_dir: Path) -> dict` and `template_catalog() -> list[dict]`.
GeometryRequest fields: template enum tray|cable_comb|magnet_frame; width=120, depth=80, height=35, wall=2, bottom=2, dividers=0, slots=5, cable_diameter=6, inset_diameter=52, inset_depth=2, fit_clearance=0.3. All lengths mm. GeometryRequest generic finite/range validation exists; geometry worker validates actual cross-field/geometry constraints per template. The default object is an open-top tray; dividers add internal partitions along width. Cable comb is an open-top cable cradle with rounded channels across depth (not a snapping clamp). Magnet frame has a circular inset pocket for a disc; fit_clearance is extra diameter, not per-side; no claim of magnet-retention or strength.
Output: {template, parameters, dimensions_mm:{x,y,z}, volume_mm3, geometry_status:'validated', print_status:'not_tested', checks: list[{name,passed,detail}], files:{stl:'model.stl',step:'model.step',three_mf:'model.3mf',source:'model.py'}, mesh:{vertices:[[x,y,z]...],faces:[[a,b,c]...]}, warnings:list[str]}.
Generate real CadQuery solid, save all outputs to output_dir. Source must reproduce this exact template without arbitrary user code. Manifest/hash can be written by root. Verify shape validity, number of solids=1, positive volume, dimensions. Reimport STEP in tests; verify numeric tray volume for no/with divider. Invalid dimensions raise ValueError in Korean or clear English. Do not implement HTTP, persistence, or LLM.

## Profiles worker
Implement `evaluate_profile(profile: dict, setup: dict) -> dict`, `review_calibrations(records:list[dict], changes:dict) -> list[dict]`.
Setup dictionary: {printer_model,printer_preset,nozzle_diameter,plate_type,extruder,feed_mode,material_id,material_identity_status}. Unknown string values can be empty; material_identity_status exact|ambiguous|unknown.
Input supports a plain Bambu filament JSON or an envelope {id,settings:<Bambu JSON>,scope:{printer_model,printer_preset,nozzle_diameter,plate_type,extruder,feed_mode,material_id},source:{authority,url,publisher,retrieved_at},validation:{status,setup_fingerprint}}. Treat supplied source as claimed metadata, not externally verified provenance. Do not provide default numeric filament parameters. Read Bambu compatible_printers without fuzzy matching; raw profile lacks exact product metadata unless provided. List effective fields available and missing evidence; unresolved inherits/include => needs_evidence, no auto prepare.
Output: {decision:blocked|needs_input|needs_evidence|ready_to_prepare,compatibility:supported|unsupported|unknown,can_prepare_profile:bool,selected_profile_id:string|null,effective_settings:dict,missing_fields:list[str],reasons:list[{code,message}],source_authority,validation_status,calibration_actions:list,warnings:list[str]}. Do not label ready_to_prepare as print ready. Machine/process full configuration remains slicer module responsibility.
Do not hardcode unverifiable numeric temperatures or broad AMS rules. Validate empty/nonfinite settings; direct mismatch blocks. Temperature/MVS changes make K stale; nozzle/hotend/material changes recheck relevant calibrations; plate changes should not invalidate K by themselves.

## Slicer worker
Implement `detect_environment() -> dict`, `prepare_slice(input_path:Path,job_dir:Path,config_bundle:dict,executable_path:str|None=None) -> dict`, `execute_slice(plan:dict,timeout_seconds:int=180) -> dict`.
Environment from PPA_BAMBU_PATH only or known OS paths/PATH. No browser supplied executable overrides at API layer. Env output {available,path,version,capabilities,printer_status:'not_checked',diagnostics:list[str]}.
Config bundle uses {machine:<full JSON>,process:<full JSON>,filaments:[<full JSON>],source:'user_export'}; write normalized machine.json/process.json/filament-1.json names in private job_dir/config. Reject unresolved inherits/include, missing full-config identity and necessary settings. Do not claim a universal complete-schema check; supported validation requirements documented. CLI argv arrays only, shell=False. Never overwrite input; fresh output path; no arbitrary CLI flags. Plan output includes {ready,argv,output_path,job_dir,expected_settings,diagnostics}. Missing executable produces ready=false and useful diagnostics, not fabricated results.
Execution output {status:blocked|failed|timed_out|sliced|needs_review,exit_code,output_path|null,stdout,stderr,checks:list,estimated_time_seconds:null|number,filament_grams:null|number,printer_status:'not_checked',print_status:'not_started'}. Treat unsupported statistics as null. Validate fresh nonempty 3MF ZIP, no zip traversal, bounded entries/uncompressed size, nonempty Metadata/plate_*.gcode, and compared core project settings when available. If values cannot be verified use needs_review. Do not call network printer protocols, launch physical operations or invent Connect URI.

## Ownership
Geometry: geometry.py and tests/test_geometry.py only.
Profiles: profiles.py and tests/test_profiles.py only.
Slicer: slicer.py and tests/test_slicer.py only.
Root: all other files. No worker git commits or edits outside owned files. Root coordinates final commit/package.
