# Bambu Studio configuration and native execution

The local app prepares and checks Bambu Studio CLI jobs. A discovered executable, a supported CLI, a verified sliced archive, a printer connection and a successful physical print are separate observations. The current app never sends a job to a printer.

## Check the installed program

Set `PPA_BAMBU_PATH` to the executable you installed, if normal installation-path/PATH discovery does not find it. Open the model's slicing panel and choose **설치된 슬라이서 확인**, or run:

```bash
python -m print_agent doctor --probe-slicer
```

Ordinary `doctor` and page bootstrap only discover files. The explicit check invokes that configured program with `--help`, bounds its runtime, and reports its observed version and required CLI options. It accepts no executable path or command from browser input. A found executable with missing runtime libraries can have `available: true` and `cli_supported: false`; review its diagnostics before preparing a job. A successful help check does not test slicing or printer connectivity.

`POST /api/slicer/probe` accepts only `{}` under the existing session-token/origin boundary and returns the environment object directly. Fields include `available`, `cli_supported`, `path`, `version`, `capabilities`, `diagnostics`, and `printer_status: "not_checked"`.

## Bring settings from a Studio project

The primary model-page flow imports one supported `.3mf`, shows its recorded setup, and prepares the current generated CAD with its exact global settings. Composition/download works without an installed slicer. Native execution requires the qualified version and a separate explicit action. [STUDIO_PROJECTS.md](STUDIO_PROJECTS.md) describes the one-filament/nozzle/extruder scope, provenance, excluded object/plate data, original storage and full-setting comparison.

The sections below describe the retained advanced machine/process/filament JSON path. Its role configuration rules do not apply by relabeling project JSON.

## Assemble the supplied configuration files

1. Generate a model and open its full configuration panel.
2. Import one machine JSON, one process JSON, and one to sixteen filament JSON files. Their list order becomes the CLI filament order.
3. Select the build plate explicitly and assemble the input bundle.
4. Review the assembled JSON, prepare the job, and then explicitly execute the local slice.

The helper preserves the JSON objects and their value representations. It does not remove `inherits`, flatten `include`, fill native defaults, select extruder variants, or propose temperatures. Files and plate choices stay staged until assembly. A failed import retains the existing manual JSON and previously accepted files. Pending staged changes invalidate previous preparation and block preparation/execution until assembled or cancelled. Manual bundle JSON remains supported.

The entire slice API request is limited to 8 MiB. This includes `job_id`, the bundle and request encoding; a bundle at the absolute limit can therefore leave insufficient space for its enclosing request. The helper checks the complete request budget before accepting assembly.

The input shape is:

```json
{
  "source": "user_export",
  "plate_type": "Textured PEI Plate",
  "machine": {},
  "process": {},
  "filaments": [{}]
}
```

This is a structural illustration, not an executable profile or hardware recommendation. The objects must contain the user's actual resolved full configurations. Individual exported presets may contain only overrides; the separate filament inheritance report does not fill Studio's internal defaults or provide the machine/process configurations.

## Supported validation

Each configuration needs a nonempty string `name`, the appropriate `type` (`machine`, `process`, `filament`), and a native `from` value (`system`, `User`, or `user`). Bambu's native JSON setting representation uses strings and string arrays. Bare JSON numeric settings are rejected because the inspected native loader can skip them. Values are preserved rather than silently converted. Unresolved `inherits`, `include`, or `includes`, host post-processing programs and browser-supplied CLI options are blocked.

The currently supported machine path is a resolved native root configuration with `from: "system"`. Native Studio uses an inherited system name for `from: "user"`/`"User"` machines; this adapter does not yet resolve that lineage, so it blocks those machines with a specific explanation. The process needs an explicit `compatible_printers` string array containing the exact machine `name`. Process and filament `from: "user"`/`"User"` remain accepted within the other validation requirements. The helper never changes `from` or invents a compatibility entry to make a file pass. Native `from` is a configuration classification, not a manufacturer-authenticity claim.

The CLI assigns `printer_settings_id`, `print_settings_id`, and `filament_settings_id` from the corresponding configuration `name`. Missing/blank settings IDs are therefore accepted; a supplied nonempty conflicting ID must be corrected in the source configuration. This is a native naming rule, not evidence that the named product is authentic or compatible.

The adapter checks a documented minimum of machine identity, FFF technology, nozzle and bed geometry, start/end G-code; layer/shell/infill and selected process speeds; material type, diameter, density, flow, volumetric limit and nozzle/bed temperatures. It does not validate every Bambu setting or establish physical suitability.

| `plate_type` native value | Required temperature fields on every filament |
|---|---|
| `Cool Plate` | `cool_plate_temp`, `cool_plate_temp_initial_layer` |
| `Engineering Plate` | `eng_plate_temp`, `eng_plate_temp_initial_layer` |
| `High Temp Plate` | `hot_plate_temp`, `hot_plate_temp_initial_layer` |
| `Textured PEI Plate` | `textured_plate_temp`, `textured_plate_temp_initial_layer` |
| `Supertack Plate` | `supertack_plate_temp`, `supertack_plate_temp_initial_layer` |

These are the inspected CLI enum values, including `Supertack Plate`. The separate filament-review UI also recognizes human-facing plate labels; those aliases do not replace the explicit native value in this bundle. No plate is silently selected.

Both selected-plate temperatures must be positive: native validation treats a zero temperature as an unsupported material/plate combination. Zero values for unselected plates are retained. This prevents a known incompatibility from reaching native execution without inventing a replacement temperature.

## Execution and read-back

Preparation copies the model and configuration files into a new job directory and records their hashes. The selected source/plate are staged in `config/selection.json`. Immediately before execution, the adapter checks the staged files again and derives expected settings from those files, rejecting a modified plan or mismatched command arguments.

The command uses an argument array with `shell=False`. It supplies the explicit `--curr-bed-type`, an absolute `--outputdir`, and a basename for `--export-3mf`; the inspected native program joins the directory and filename itself. Input files are not overwritten.

After a successful process exit, the adapter requires a fresh bounded 3MF ZIP, valid archive entries/CRC, nonempty `Metadata/plate_*.gcode`, and core settings read from `Metadata/project_settings.config`. Missing or mismatched read-back values produce `needs_review`, not `sliced`. The result records `bambu_version` from the help probe and `output_sha256` only after archive validation. A failed new attempt removes the preceding slice as the current download.

Project-setting JSON nesting is bounded at 32 containers before recursive comparisons. Unreadable, non-object or excessively nested input project settings block preparation; geometry-only 3MF without a settings entry remains accepted. The corresponding malformed output is marked `needs_review` instead of crashing the request or treating deeply wrapped values as verified settings.

`estimated_time_seconds` and `filament_grams` remain `null`: no native statistics parser has been qualified. `printer_status` remains `not_checked` and `print_status` remains `not_started`.

## Native qualification and upstream references

The source audit is pinned to [Bambu Studio v02.09.01.70](https://github.com/bambulab/BambuStudio/releases/tag/v02.09.01.70), commit `56a57d00a591360cf41bf21383915ee5bf357be5`:

- [Official CLI usage](https://github.com/bambulab/BambuStudio/wiki/Command-Line-Usage): machine/process/filament inputs, export flags and configuration precedence.
- [BambuStudio.cpp](https://github.com/bambulab/BambuStudio/blob/56a57d00a591360cf41bf21383915ee5bf357be5/src/BambuStudio.cpp): native metadata/identities, selected plate and export path behavior.
- [Config.cpp](https://github.com/bambulab/BambuStudio/blob/56a57d00a591360cf41bf21383915ee5bf357be5/src/libslic3r/Config.cpp): native JSON string representations and project settings export.
- [PrintConfig.cpp](https://github.com/bambulab/BambuStudio/blob/56a57d00a591360cf41bf21383915ee5bf357be5/src/libslic3r/PrintConfig.cpp): supported plate enum and configuration definitions.
- [Print.cpp](https://github.com/bambulab/BambuStudio/blob/56a57d00a591360cf41bf21383915ee5bf357be5/src/libslic3r/Print.cpp): selected-plate zero-temperature incompatibility validation.

The native workflow fetches the exact Ubuntu release and checks its SHA-256 before execution. Official CLI example configurations are fetched separately with pinned hashes and kept unchanged for investigation; they are not project-authored presets or included under this repository's MIT license. Their remaining inheritance/include/variant metadata must not be deleted to force the app's validator to accept them.

A separate adapter smoke phase uses handwritten synthetic settings, an original cube STL and the project's original CadQuery cable-comb 3MF. Its synthetic machine is explicitly classified as a native root configuration and its process names that machine exactly. The fixture is not a user export or manufacturer profile, depends on native defaults for unspecified fields, and must not be offered as a printing recommendation. The qualification inspects output ZIP/G-code and independently declared core setting expectations rather than accepting the adapter's own success label alone.

Observed native results, exact workflow runs and limitations are recorded in [VERIFICATION.md](VERIFICATION.md). Subprocess fixtures verify adapter boundaries; only a successful actual native run qualifies the tested native path. Windows/macOS and physical printer/material setups require separate evidence.
