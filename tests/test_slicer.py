"""Adapter boundary tests. Synthetic CLI responses are not native Bambu validation."""

import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
import zipfile

from print_agent import slicer


HELP_TEXT = "BambuStudio-02.09.01.70:\n--load-settings --load-filaments --slice --outputdir --export-3mf"


def full_bundle():
    """Hand-written test values, never supplied as production print presets."""
    return {
        "source": "user_export",
        "plate_type": "High Temp Plate",
        "machine": {
            "name": "Test printer 0.4 nozzle",
            "type": "machine",
            "from": "system",
            "printer_model": "Test printer",
            "printer_technology": "FFF",
            "nozzle_diameter": ["0.4"],
            "printable_area": ["0x0", "200x0", "200x200", "0x200"],
            "printable_height": "200",
            "machine_start_gcode": "; fixture start",
            "machine_end_gcode": "; fixture end",
        },
        "process": {
            "name": "Test process",
            "type": "process",
            "from": "user",
            "compatible_printers": ["Test printer 0.4 nozzle"],
            "layer_height": "0.2",
            "initial_layer_print_height": "0.2",
            "wall_loops": "2",
            "top_shell_layers": "4",
            "bottom_shell_layers": "4",
            "sparse_infill_density": "15%",
            "outer_wall_speed": "50",
            "inner_wall_speed": "75",
            "sparse_infill_speed": "100",
            "initial_layer_speed": "20",
        },
        "filaments": [{
            "name": "Test material",
            "type": "filament",
            "from": "user",
            "filament_type": ["PLA"],
            "filament_diameter": ["1.75"],
            "filament_density": ["1.2"],
            "filament_flow_ratio": ["1"],
            "filament_max_volumetric_speed": ["10"],
            "nozzle_temperature": ["210"],
            "nozzle_temperature_initial_layer": ["215"],
            "hot_plate_temp": ["55"],
            "hot_plate_temp_initial_layer": ["55"],
        }],
    }


def exported_settings():
    """Independently specified read-back fixture; do not derive from adapter plans."""
    return {
        "name": "project_settings",
        "from": "project",
        "version": "02.09.01.70",
        "curr_bed_type": "High Temp Plate",
        "printer_settings_id": "Test printer 0.4 nozzle",
        "printer_model": "Test printer",
        "printer_technology": "FFF",
        "nozzle_diameter": ["0.4"],
        "printable_area": ["0x0", "200x0", "200x200", "0x200"],
        "printable_height": "200",
        "machine_start_gcode": "; fixture start",
        "machine_end_gcode": "; fixture end",
        "print_settings_id": "Test process",
        "layer_height": "0.2",
        "initial_layer_print_height": "0.2",
        "wall_loops": "2",
        "top_shell_layers": "4",
        "bottom_shell_layers": "4",
        "sparse_infill_density": "15%",
        "outer_wall_speed": "50",
        "inner_wall_speed": "75",
        "sparse_infill_speed": "100",
        "initial_layer_speed": "20",
        "filament_settings_id": ["Test material"],
        "filament_type": ["PLA"],
        "filament_diameter": ["1.75"],
        "filament_density": ["1.2"],
        "filament_flow_ratio": ["1"],
        "filament_max_volumetric_speed": ["10"],
        "nozzle_temperature": ["210"],
        "nozzle_temperature_initial_layer": ["215"],
        "hot_plate_temp": ["55"],
        "hot_plate_temp_initial_layer": ["55"],
    }


def write_output(path, settings=True, extra=None, gcode=True):
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"/>')
        if gcode:
            archive.writestr("Metadata/plate_1.gcode", "; synthetic test toolpath\nG1 X1 Y1 E1\n")
        if settings is not False:
            archive.writestr("Metadata/project_settings.config", json.dumps(exported_settings() if settings is True else settings))
        for name, value in (extra or {}).items():
            archive.writestr(name, value)


class SlicerTests(unittest.TestCase):
    def setUp(self):
        self.slicer = slicer
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.executable = self.root / "Bambu Studio executable"
        self.executable.write_bytes(b"synthetic test executable")
        self.executable.chmod(0o700)
        self.model = self.root / "부품 ; $(touch sentinel) space.stl"
        self.model.write_text("solid fixture\nendsolid fixture\n")

    def prepare(self, bundle=None, directory="job with spaces"):
        return self.slicer.prepare_slice(self.model, self.root / directory, bundle or full_bundle(), str(self.executable))

    def run_fixture(self, plan, writer=None, returncode=0):
        def invoke(argv, **kwargs):
            self.assertIsInstance(argv, list)
            self.assertIs(kwargs.get("shell"), False)
            self.assertTrue(all(isinstance(arg, str) for arg in argv))
            if argv[1:] == ["--help"]:
                return subprocess.CompletedProcess(argv, 0, HELP_TEXT, "")
            self.assertEqual(argv[0], str(self.executable.resolve()))
            self.assertEqual(argv[argv.index("--slice") + 1], "0")
            if writer:
                export_name = argv[argv.index("--export-3mf") + 1]
                self.assertEqual(Path(export_name).name, export_name)
                # Studio concatenates outputdir + '/' + export filename, including
                # when the filename is absolute. Path / absolute would hide that bug.
                output_dir = argv[argv.index("--outputdir") + 1]
                writer(Path(f"{output_dir}/{export_name}"))
            return subprocess.CompletedProcess(argv, returncode, "synthetic stdout", "synthetic stderr")
        with patch.object(self.slicer.subprocess, "run", side_effect=invoke):
            return self.slicer.execute_slice(plan)

    def test_environment_detection_is_lazy_and_missing_override_is_honest(self):
        with patch.dict(os.environ, {"PPA_BAMBU_PATH": str(self.root / "absent")}), patch.object(self.slicer.subprocess, "run", side_effect=AssertionError("detection must not launch CLI")):
            result = self.slicer.detect_environment()
        self.assertFalse(result["available"])
        self.assertIsNone(result["version"])
        self.assertEqual(result["printer_status"], "not_checked")
        self.assertTrue(result["diagnostics"])

    def test_environment_override_does_not_imply_printer_connection_or_capabilities(self):
        with patch.dict(os.environ, {"PPA_BAMBU_PATH": str(self.executable)}), patch.object(self.slicer.subprocess, "run", side_effect=AssertionError("must be lazy")):
            result = self.slicer.detect_environment()
        self.assertTrue(result["available"])
        self.assertEqual(result["path"], str(self.executable.resolve()))
        self.assertEqual(result["capabilities"], [])
        self.assertEqual(result["printer_status"], "not_checked")

    def test_explicit_environment_probe_reports_cli_version_and_capabilities(self):
        probe = getattr(self.slicer, "probe_environment", None)
        self.assertTrue(callable(probe), "an explicit CLI probe must be available without changing lazy discovery")
        calls = []
        def invoke(argv, **kwargs):
            calls.append(argv)
            self.assertEqual(argv, [str(self.executable.resolve()), "--help"])
            self.assertLessEqual(kwargs["timeout"], 3)
            return subprocess.CompletedProcess(argv, 0, HELP_TEXT, "")
        with patch.dict(os.environ, {"PPA_BAMBU_PATH": str(self.executable)}), patch.object(self.slicer.subprocess, "run", side_effect=invoke):
            result = probe()
        self.assertTrue(result["available"])
        self.assertTrue(result["cli_supported"])
        self.assertEqual(result["version"], "02.09.01.70")
        self.assertIn("--slice", result["capabilities"])
        self.assertEqual(result["printer_status"], "not_checked")
        self.assertEqual(len(calls), 1)

    def test_explicit_environment_probe_does_not_launch_a_missing_executable(self):
        probe = getattr(self.slicer, "probe_environment", None)
        self.assertTrue(callable(probe))
        with patch.dict(os.environ, {"PPA_BAMBU_PATH": str(self.root / "absent")}), patch.object(self.slicer.subprocess, "run", side_effect=AssertionError("missing executable must not be launched")):
            result = probe()
        self.assertFalse(result["available"])
        self.assertFalse(result["cli_supported"])
        self.assertIsNone(result["version"])
        self.assertTrue(result["diagnostics"])

    def test_failed_explicit_probe_keeps_file_discovery_separate(self):
        probe = getattr(self.slicer, "probe_environment", None)
        self.assertTrue(callable(probe))
        with patch.dict(os.environ, {"PPA_BAMBU_PATH": str(self.executable)}), patch.object(self.slicer.subprocess, "run", return_value=subprocess.CompletedProcess([], 1, HELP_TEXT, "help failed")):
            result = probe()
        self.assertTrue(result["available"])
        self.assertFalse(result["cli_supported"])
        self.assertEqual(result["version"], "02.09.01.70")
        self.assertTrue(result["diagnostics"])
        self.assertEqual(result["printer_status"], "not_checked")

    def test_failed_help_reports_observed_exit_code_and_bounded_installation_cause(self):
        stderr = "error while loading shared libraries: libwebkit2gtk-4.1.so.0: cannot open shared object file\n" + "x" * 5000
        with patch.dict(os.environ, {"PPA_BAMBU_PATH": str(self.executable)}), patch.object(self.slicer.subprocess, "run", return_value=subprocess.CompletedProcess([], 127, HELP_TEXT, stderr)):
            result = self.slicer.probe_environment()
        self.assertTrue(result["available"])
        self.assertFalse(result["cli_supported"])
        self.assertEqual(result["version"], "02.09.01.70")
        diagnostics = "\n".join(result["diagnostics"])
        self.assertIn("127", diagnostics)
        self.assertIn("libwebkit2gtk-4.1.so.0", diagnostics)
        self.assertLess(len(diagnostics), 2300)
        self.assertNotIn(stderr, diagnostics)

    def test_missing_executable_blocks_without_fabricating_output(self):
        plan = self.slicer.prepare_slice(self.model, self.root / "job", full_bundle(), str(self.root / "absent"))
        self.assertFalse(plan["ready"])
        self.assertTrue(plan["diagnostics"])
        result = self.slicer.execute_slice(plan)
        self.assertEqual(result["status"], "blocked")
        self.assertIsNone(result["output_path"])
        self.assertIsNone(result["estimated_time_seconds"])

    def test_prepare_stages_normalized_names_without_touching_source(self):
        source = self.model.read_bytes()
        plan = self.prepare()
        self.assertTrue(plan["ready"], plan["diagnostics"])
        args = plan["argv"]
        configs = args[args.index("--load-settings") + 1].split(";")
        self.assertEqual([Path(p).name for p in configs], ["machine.json", "process.json"])
        self.assertEqual(Path(args[args.index("--load-filaments") + 1]).name, "filament-1.json")
        self.assertEqual(Path(args[-1]).read_bytes(), source)
        self.assertNotEqual(Path(args[-1]), self.model)
        self.assertEqual(self.model.read_bytes(), source)
        self.assertFalse(Path(plan["output_path"]).exists())
        self.assertFalse((self.root / "sentinel").exists())

    def test_export_filename_is_relative_to_native_output_directory(self):
        plan = self.prepare()
        self.assertTrue(plan["ready"], plan["diagnostics"])
        args = plan["argv"]
        export_name = args[args.index("--export-3mf") + 1]
        self.assertFalse(Path(export_name).is_absolute())
        native_output = Path(args[args.index("--outputdir") + 1] + "/" + export_name)
        self.assertEqual(native_output, Path(plan["output_path"]))
        self.assertEqual(self.run_fixture(plan, write_output)["status"], "sliced")

    def test_native_profile_metadata_is_required_before_launch(self):
        cases = [
            ("name", None), ("name", ""), ("name", " "), ("name", 2),
            ("name", ["Test name"]), ("type", None), ("type", "wrong"),
            ("type", ["machine"]), ("from", None), ("from", "project"),
            ("from", 1), ("from", ["user"]), ("version", 2),
            ("version", ["02.09.01.70"]),
        ]
        for kind in ("machine", "process", "filament"):
            for index, (key, value) in enumerate(cases):
                with self.subTest(kind=kind, key=key, value=value):
                    bundle = full_bundle()
                    target = bundle["filaments"][0] if kind == "filament" else bundle[kind]
                    target[key] = value
                    plan = self.prepare(bundle, f"metadata-{kind}-{index}")
                    self.assertFalse(plan["ready"])
                    self.assertIn(key, " ".join(plan["diagnostics"]))

    def test_native_profile_type_must_match_its_bundle_role(self):
        for kind, wrong_type in (("machine", "process"), ("process", "filament"), ("filament", "machine")):
            with self.subTest(kind=kind):
                bundle = full_bundle()
                target = bundle["filaments"][0] if kind == "filament" else bundle[kind]
                target["type"] = wrong_type
                plan = self.prepare(bundle, f"wrong-role-{kind}")
                self.assertFalse(plan["ready"])
                self.assertIn("type", " ".join(plan["diagnostics"]))

    def test_native_process_and_filament_origins_are_preserved_with_root_machine(self):
        for index, origin in enumerate(("system", "User", "user")):
            with self.subTest(origin=origin):
                bundle = full_bundle()
                for profile in (bundle["process"], *bundle["filaments"]):
                    profile["from"] = origin
                plan = self.prepare(bundle, f"origin-{index}")
                self.assertTrue(plan["ready"], plan["diagnostics"])
                config = Path(plan["job_dir"]) / "config"
                self.assertEqual(json.loads((config / "machine.json").read_text())["from"], "system")
                self.assertEqual(json.loads((config / "process.json").read_text())["from"], origin)
                self.assertEqual(json.loads((config / "filament-1.json").read_text())["from"], origin)

    def test_user_machine_requires_unsupported_system_lineage_without_rewriting_origin(self):
        for index, origin in enumerate(("User", "user")):
            with self.subTest(origin=origin):
                bundle = full_bundle()
                bundle["machine"]["from"] = origin
                before = json.dumps(bundle)
                plan = self.prepare(bundle, f"user-machine-{index}")
                self.assertFalse(plan["ready"])
                diagnostics = " ".join(plan["diagnostics"])
                self.assertIn("machine.from", diagnostics)
                self.assertIn("inherits", diagnostics)
                self.assertIn("변경하지", diagnostics)
                self.assertEqual(json.dumps(bundle), before)
                self.assertFalse((Path(plan["job_dir"]) / "config").exists())

    def test_process_compatibility_requires_exact_root_machine_name(self):
        cases = (
            None, "Test printer 0.4 nozzle", [], [""], ["   "],
            ["Different printer"], ["test printer 0.4 nozzle"],
            ["Test printer 0.4 nozzle "], [["Test printer 0.4 nozzle"]],
            ["Test printer 0.4 nozzle", ""], ["Test printer 0.4 nozzle", 1],
        )
        for index, compatible in enumerate(cases):
            with self.subTest(compatible=compatible):
                bundle = full_bundle()
                bundle["process"]["compatible_printers"] = compatible
                plan = self.prepare(bundle, f"process-compatibility-{index}")
                self.assertFalse(plan["ready"])
                self.assertIn("compatible_printers", " ".join(plan["diagnostics"]))
        bundle = full_bundle()
        del bundle["process"]["compatible_printers"]
        plan = self.prepare(bundle, "process-compatibility-missing")
        self.assertFalse(plan["ready"])
        self.assertIn("compatible_printers", " ".join(plan["diagnostics"]))

    def test_matching_process_compatibility_list_is_preserved_verbatim(self):
        bundle = full_bundle()
        compatible = ["Another printer 0.6 nozzle", "Test printer 0.4 nozzle"]
        bundle["process"]["compatible_printers"] = compatible
        plan = self.prepare(bundle)
        self.assertTrue(plan["ready"], plan["diagnostics"])
        staged = json.loads((Path(plan["job_dir"]) / "config/process.json").read_text())
        self.assertEqual(staged["compatible_printers"], compatible)
        self.assertEqual(bundle["process"]["compatible_printers"], compatible)

    def test_native_configuration_shapes_reject_silently_skipped_values(self):
        cases = [
            ("machine", "printable_height", 200),
            ("process", "layer_height", 0.2),
            ("process", "wall_loops", [2]),
            ("filament", "filament_flow_ratio", [1.0]),
            ("filament", "filament_flow_ratio", ["1", 1.0]),
            ("machine", "optional_setting", False),
            ("machine", "optional_setting", None),
            ("machine", "optional_setting", {"value": "1"}),
        ]
        for index, (kind, key, value) in enumerate(cases):
            with self.subTest(kind=kind, key=key, value=value):
                bundle = full_bundle()
                target = bundle["filaments"][0] if kind == "filament" else bundle[kind]
                target[key] = value
                plan = self.prepare(bundle, f"shape-{index}")
                self.assertFalse(plan["ready"])
                self.assertIn(key, " ".join(plan["diagnostics"]))

    def test_native_settings_ids_follow_name_when_blank_or_matching(self):
        for index, blank in enumerate(("", [""], [])):
            with self.subTest(blank=blank):
                bundle = full_bundle()
                bundle["machine"]["printer_settings_id"] = blank
                bundle["process"]["print_settings_id"] = blank
                bundle["filaments"][0]["filament_settings_id"] = blank
                plan = self.prepare(bundle, f"blank-ids-{index}")
                self.assertTrue(plan["ready"], plan["diagnostics"])
                self.assertEqual(plan["expected_settings"]["printer_settings_id"], "Test printer 0.4 nozzle")
                self.assertEqual(plan["expected_settings"]["print_settings_id"], "Test process")
                self.assertEqual(plan["expected_settings"]["filament_settings_id"], ["Test material"])
                self.assertEqual(self.run_fixture(plan, write_output)["status"], "sliced")
        bundle = full_bundle()
        bundle["machine"]["printer_settings_id"] = "Test printer 0.4 nozzle"
        bundle["process"]["print_settings_id"] = "Test process"
        bundle["filaments"][0]["filament_settings_id"] = ["Test material"]
        self.assertTrue(self.prepare(bundle, "matching-ids")["ready"])

    def test_conflicting_internal_ids_are_actionable_preparation_errors(self):
        for kind, key, value in (
            ("machine", "printer_settings_id", "Different printer"),
            ("process", "print_settings_id", "Different process"),
            ("filament", "filament_settings_id", ["Different material"]),
        ):
            with self.subTest(kind=kind):
                bundle = full_bundle()
                target = bundle["filaments"][0] if kind == "filament" else bundle[kind]
                target[key] = value
                plan = self.prepare(bundle, f"conflict-{kind}")
                self.assertFalse(plan["ready"])
                self.assertIn(key, " ".join(plan["diagnostics"]))
                self.assertIn("name", " ".join(plan["diagnostics"]))

    def test_explicit_supported_plate_type_is_required(self):
        for index, value in enumerate((None, "", "Default", "Smooth PEI Plate", "High Temp Plate; --outputdir /tmp", ["High Temp Plate"])):
            with self.subTest(value=value):
                bundle = full_bundle()
                bundle["plate_type"] = value
                plan = self.prepare(bundle, f"plate-{index}")
                self.assertFalse(plan["ready"])
                self.assertIn("plate_type", " ".join(plan["diagnostics"]))
        bundle = full_bundle()
        del bundle["plate_type"]
        self.assertFalse(self.prepare(bundle, "plate-missing")["ready"])

    def test_selected_plate_binds_cli_readback_and_staged_selection(self):
        cases = (
            ("Cool Plate", "cool_plate"),
            ("Engineering Plate", "eng_plate"),
            ("High Temp Plate", "hot_plate"),
            ("Textured PEI Plate", "textured_plate"),
            ("Supertack Plate", "supertack_plate"),
        )
        for index, (plate_type, prefix) in enumerate(cases):
            with self.subTest(plate_type=plate_type):
                bundle = full_bundle()
                bundle["plate_type"] = plate_type
                filament = bundle["filaments"][0]
                filament[prefix + "_temp"] = ["55"]
                filament[prefix + "_temp_initial_layer"] = ["55"]
                plan = self.prepare(bundle, f"selected-plate-{index}")
                self.assertTrue(plan["ready"], plan["diagnostics"])
                self.assertEqual(plan.get("plate_type"), plate_type)
                self.assertIn("--curr-bed-type", plan["argv"])
                self.assertEqual(plan["argv"][plan["argv"].index("--curr-bed-type") + 1], plate_type)
                self.assertEqual(plan["expected_settings"].get("curr_bed_type"), plate_type)
                selection = Path(plan["job_dir"]) / "config/selection.json"
                self.assertTrue(selection.exists())
                self.assertEqual(json.loads(selection.read_text()), {"source": "user_export", "plate_type": plate_type})
                self.assertEqual(plan["file_hashes"].get(str(selection)), hashlib.sha256(selection.read_bytes()).hexdigest())

    def test_an_unselected_temperature_pair_does_not_satisfy_selected_plate(self):
        bundle = full_bundle()
        bundle["plate_type"] = "Textured PEI Plate"
        plan = self.prepare(bundle)
        self.assertFalse(plan["ready"])
        self.assertIn("textured_plate_temp", " ".join(plan["diagnostics"]))

    def test_each_filament_requires_the_selected_bed_temperature_pair(self):
        bundle = full_bundle()
        bundle["filaments"].append(dict(bundle["filaments"][0], name="Second material"))
        del bundle["filaments"][1]["hot_plate_temp_initial_layer"]
        plan = self.prepare(bundle)
        self.assertFalse(plan["ready"])
        self.assertIn("filaments[1].hot_plate_temp_initial_layer", " ".join(plan["diagnostics"]))

    def test_zero_temperature_marks_the_selected_plate_as_unsupported(self):
        for index, (plate_type, prefix) in enumerate((
            ("Cool Plate", "cool_plate"), ("Engineering Plate", "eng_plate"),
            ("High Temp Plate", "hot_plate"), ("Textured PEI Plate", "textured_plate"),
            ("Supertack Plate", "supertack_plate"),
        )):
            for suffix in ("_temp", "_temp_initial_layer"):
                with self.subTest(plate_type=plate_type, field=prefix + suffix):
                    bundle = full_bundle()
                    bundle["plate_type"] = plate_type
                    bundle["filaments"][0][prefix + "_temp"] = ["55"]
                    bundle["filaments"][0][prefix + "_temp_initial_layer"] = ["55"]
                    bundle["filaments"][0][prefix + suffix] = ["0"]
                    plan = self.prepare(bundle, f"zero-bed-{index}-{suffix}")
                    self.assertFalse(plan["ready"])
                    self.assertIn(prefix + suffix, " ".join(plan["diagnostics"]))

    def test_zero_unselected_plate_temperatures_are_preserved(self):
        bundle = full_bundle()
        bundle["filaments"][0]["cool_plate_temp"] = ["0"]
        bundle["filaments"][0]["cool_plate_temp_initial_layer"] = ["0"]
        plan = self.prepare(bundle)
        self.assertTrue(plan["ready"], plan["diagnostics"])
        staged = json.loads((Path(plan["job_dir"]) / "config/filament-1.json").read_text())
        self.assertEqual(staged["cool_plate_temp"], ["0"])
        self.assertEqual(staged["cool_plate_temp_initial_layer"], ["0"])
        settings = exported_settings()
        settings.update(cool_plate_temp=["0"], cool_plate_temp_initial_layer=["0"])
        self.assertEqual(self.run_fixture(plan, lambda path: write_output(path, settings=settings))["status"], "sliced")

    def test_unresolved_inheritance_and_missing_minimum_fields_block_preparation(self):
        cases = [
            ("machine", "inherits", "base machine"),
            ("process", "include", ["base process"]),
            ("process", "includes", ["base process"]),
            ("filament", "inherits", "Generic PLA"),
            ("machine", "printable_height", None),
            ("process", "layer_height", "nan"),
            ("filament", "nozzle_temperature", []),
        ]
        for index, (kind, key, value) in enumerate(cases):
            with self.subTest(kind=kind, key=key):
                bundle = full_bundle()
                target = bundle["filaments"][0] if kind == "filament" else bundle[kind]
                target[key] = value
                plan = self.prepare(bundle, f"invalid-{index}")
                self.assertFalse(plan["ready"])
                self.assertTrue(plan["diagnostics"])

    def test_host_postprocessing_commands_are_rejected(self):
        bundle = full_bundle()
        bundle["process"]["post_process"] = ["touch unexpected"]
        plan = self.prepare(bundle)
        self.assertFalse(plan["ready"])

    def test_semicolon_in_job_path_cannot_split_config_arguments(self):
        plan = self.prepare(directory="bad;job")
        self.assertFalse(plan["ready"])
        self.assertTrue(plan["diagnostics"])

    def test_zero_exit_without_output_is_failure(self):
        result = self.run_fixture(self.prepare())
        self.assertEqual(result["status"], "failed")
        self.assertIsNone(result["output_path"])
        self.assertIsNone(result["filament_grams"])
        self.assertEqual(result["print_status"], "not_started")

    def test_project_without_sliced_gcode_is_not_success(self):
        result = self.run_fixture(self.prepare(), lambda p: write_output(p, gcode=False))
        self.assertEqual(result["status"], "failed")

    def test_deep_project_settings_output_requires_review_without_recursion_crash(self):
        for depth in (64, 1200, 20000):
            with self.subTest(depth=depth):
                # At depth64 this parses, and the previous recursive comparison
                # unwrapped every singleton array and incorrectly verified it.
                settings = json.dumps(exported_settings()).replace(
                    '"nozzle_diameter": ["0.4"]',
                    '"nozzle_diameter": ' + '[' * depth + '"0.4"' + ']' * depth,
                )
                try:
                    result = self.run_fixture(self.prepare(directory=f"deep-output-{depth}"),
                        lambda path: write_output(path, settings=False, extra={"Metadata/project_settings.config": settings}))
                except RecursionError:
                    self.fail("unreadable output settings must return a result, not raise RecursionError")
                self.assertEqual(result["status"], "needs_review")
                self.assertTrue(Path(result["output_path"]).is_file())
                self.assertTrue(any(check["name"] == "project_settings" and not check["passed"] for check in result["checks"]))

    def test_unreadable_input_project_settings_block_before_staging(self):
        cases = [b"{broken", b"\xff", b"[]"]
        cases.extend(('{"opaque":' + '[' * depth + '"value"' + ']' * depth + '}').encode() for depth in (64, 1200, 20000))
        for index, raw_settings in enumerate(cases):
            with self.subTest(index=index):
                source = self.root / f"invalid-input-{index}.3mf"
                write_output(source, settings=False, gcode=False, extra={"Metadata/project_settings.config": raw_settings})
                directory = self.root / f"blocked-input-{index}"
                plan = self.slicer.prepare_slice(source, directory, full_bundle(), str(self.executable))
                self.assertFalse(plan["ready"])
                self.assertIn("Metadata/project_settings.config", " ".join(plan["diagnostics"]))
                self.assertFalse((directory / "input").exists())

    def test_geometry_only_input_archive_does_not_require_project_settings(self):
        source = self.root / "geometry-only.3mf"
        write_output(source, settings=False, gcode=False, extra={"3D/3dmodel.model": '<model xmlns="http://schemas.microsoft.com/3dmanufacturing/core/2015/02"/>'})
        plan = self.slicer.prepare_slice(source, self.root / "geometry-input", full_bundle(), str(self.executable))
        self.assertTrue(plan["ready"], plan["diagnostics"])
        self.assertEqual(Path(plan["input_path"]).read_bytes(), source.read_bytes())

    def test_readable_input_project_host_scripts_remain_blocked(self):
        source = self.root / "host-script.3mf"
        write_output(source, settings={"post_process": ["touch unexpected"]}, gcode=False)
        plan = self.slicer.prepare_slice(source, self.root / "host-script-input", full_bundle(), str(self.executable))
        self.assertFalse(plan["ready"])
        self.assertFalse((self.root / "host-script-input/input").exists())

    def test_corrupt_or_traversing_archives_are_rejected(self):
        writers = [lambda p: p.write_bytes(b"not a zip"), lambda p: write_output(p, extra={"../outside.txt": "escape"})]
        for index, writer in enumerate(writers):
            with self.subTest(index=index):
                result = self.run_fixture(self.prepare(directory=f"bad-output-{index}"), writer)
                self.assertEqual(result["status"], "failed")
                self.assertIsNone(result["output_path"])

    def test_archive_entry_limits_prevent_unbounded_output_inspection(self):
        def too_many(path):
            write_output(path, extra={f"extras/{n}": "x" for n in range(2100)})
        result = self.run_fixture(self.prepare(), too_many)
        self.assertEqual(result["status"], "failed")

    def test_missing_or_mismatched_project_settings_need_review(self):
        mismatch = exported_settings()
        mismatch["layer_height"] = "0.4"
        for index, settings in enumerate([False, mismatch]):
            with self.subTest(index=index):
                result = self.run_fixture(self.prepare(directory=f"review-{index}"), lambda p: write_output(p, settings=settings))
                self.assertEqual(result["status"], "needs_review")
                self.assertTrue(Path(result["output_path"]).exists())
                self.assertTrue(any(not check["passed"] for check in result["checks"]))
                self.assertEqual(result.get("output_sha256"), hashlib.sha256(Path(result["output_path"]).read_bytes()).hexdigest())

    def test_different_selected_plate_in_output_needs_review(self):
        settings = exported_settings()
        settings["curr_bed_type"] = "Cool Plate"
        result = self.run_fixture(self.prepare(), lambda path: write_output(path, settings=settings))
        self.assertEqual(result["status"], "needs_review")
        self.assertIn("setting:curr_bed_type", [check["name"] for check in result["checks"] if not check["passed"]])

    def test_oversized_integer_in_native_readback_requires_review(self):
        settings = exported_settings()
        settings["nozzle_diameter"] = [10 ** 400]
        result = self.run_fixture(self.prepare(), lambda path: write_output(path, settings=settings))
        self.assertEqual(result["status"], "needs_review")
        self.assertTrue(Path(result["output_path"]).is_file())
        self.assertIn("setting:nozzle_diameter", [check["name"] for check in result["checks"] if not check["passed"]])

    def test_verified_fixture_is_sliced_without_invented_statistics_or_print_status(self):
        result = self.run_fixture(self.prepare(), write_output)
        self.assertEqual(result["status"], "sliced", result["checks"])
        self.assertEqual(result["exit_code"], 0)
        self.assertEqual(result["printer_status"], "not_checked")
        self.assertEqual(result["print_status"], "not_started")
        self.assertIsNone(result["estimated_time_seconds"])
        self.assertIsNone(result["filament_grams"])
        self.assertEqual(result.get("bambu_version"), "02.09.01.70")
        self.assertEqual(result.get("output_sha256"), hashlib.sha256(Path(result["output_path"]).read_bytes()).hexdigest())

    def test_nonzero_exit_does_not_promote_partial_output(self):
        result = self.run_fixture(self.prepare(), write_output, returncode=2)
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["exit_code"], 2)
        self.assertIsNone(result["output_path"])
        self.assertEqual(result.get("bambu_version"), "02.09.01.70")
        self.assertIsNone(result.get("output_sha256"))

    def test_timeout_is_reported_without_success_artifact(self):
        plan = self.prepare()
        def invoke(argv, **kwargs):
            if argv[1:] == ["--help"]:
                return subprocess.CompletedProcess(argv, 0, HELP_TEXT, "")
            raise subprocess.TimeoutExpired(argv, kwargs["timeout"], output=b"partial output", stderr=b"still slicing")
        with patch.object(self.slicer.subprocess, "run", side_effect=invoke):
            result = self.slicer.execute_slice(plan, timeout_seconds=1)
        self.assertEqual(result["status"], "timed_out")
        self.assertIsNone(result["output_path"])
        self.assertIn("partial output", result["stdout"])
        self.assertEqual(result.get("bambu_version"), "02.09.01.70")
        self.assertIsNone(result.get("output_sha256"))

    def test_preexisting_output_is_not_accepted_or_overwritten(self):
        plan = self.prepare()
        Path(plan["output_path"]).write_bytes(b"existing file")
        with patch.object(self.slicer.subprocess, "run", side_effect=AssertionError("stale plan must not execute")):
            result = self.slicer.execute_slice(plan)
        self.assertEqual(result["status"], "blocked")
        self.assertEqual(Path(plan["output_path"]).read_bytes(), b"existing file")

    def test_modified_config_or_injected_cli_flag_blocks_execution(self):
        plan = self.prepare()
        plan["argv"].insert(1, "--arbitrary-flag")
        with patch.object(self.slicer.subprocess, "run", side_effect=AssertionError("tampered plan must not execute")):
            self.assertEqual(self.slicer.execute_slice(plan)["status"], "blocked")
        plan = self.prepare(directory="changed-config")
        (Path(plan["job_dir"]) / "config" / "process.json").write_text("{}")
        with patch.object(self.slicer.subprocess, "run", side_effect=AssertionError("changed config must not execute")):
            self.assertEqual(self.slicer.execute_slice(plan)["status"], "blocked")

    def test_modified_readback_expectations_block_before_launch(self):
        for index, change in enumerate(("replace", "delete", "add")):
            with self.subTest(change=change):
                plan = self.prepare(directory=f"expectations-{index}")
                if change == "replace":
                    plan["expected_settings"]["layer_height"] = "0.4"
                elif change == "delete":
                    del plan["expected_settings"]["layer_height"]
                else:
                    plan["expected_settings"]["invented_setting"] = "approved"
                with patch.object(self.slicer.subprocess, "run", side_effect=AssertionError("altered expectations must block before CLI probing")):
                    result = self.slicer.execute_slice(plan)
                self.assertEqual(result["status"], "blocked")

    def test_modified_plate_selection_blocks_before_launch(self):
        for index, change in enumerate(("plan", "selection")):
            with self.subTest(change=change):
                plan = self.prepare(directory=f"selection-{index}")
                if change == "plan":
                    plan["plate_type"] = "Cool Plate"
                else:
                    selection = Path(plan["job_dir"]) / "config/selection.json"
                    self.assertTrue(selection.exists())
                    selection.write_text(json.dumps({"source": "user_export", "plate_type": "Cool Plate"}))
                with patch.object(self.slicer.subprocess, "run", side_effect=AssertionError("altered plate selection must block before CLI probing")):
                    result = self.slicer.execute_slice(plan)
                self.assertEqual(result["status"], "blocked")

    def test_help_capability_failure_blocks_slicing_and_result_is_cached(self):
        calls = []
        def invoke(argv, **kwargs):
            calls.append(argv)
            self.assertEqual(argv[1:], ["--help"])
            self.assertLessEqual(kwargs["timeout"], 3)
            return subprocess.CompletedProcess(argv, 0, "unrecognized application", "")
        with patch.object(self.slicer.subprocess, "run", side_effect=invoke):
            first = self.slicer.execute_slice(self.prepare(directory="probe-1"))
            second = self.slicer.execute_slice(self.prepare(directory="probe-2"))
        self.assertEqual(first["status"], "blocked")
        self.assertEqual(second["status"], "blocked")
        self.assertEqual(len(calls), 1)

    def test_environment_detection_does_not_wait_for_an_inflight_help_probe(self):
        plan = self.prepare()
        started, release = threading.Event(), threading.Event()
        def invoke(argv, **kwargs):
            started.set()
            release.wait(2)
            return subprocess.CompletedProcess(argv, 0, "unsupported CLI", "")
        with patch.dict(os.environ, {"PPA_BAMBU_PATH": str(self.executable)}), patch.object(self.slicer.subprocess, "run", side_effect=invoke):
            worker = threading.Thread(target=self.slicer.execute_slice, args=(plan,))
            worker.start()
            try:
                self.assertTrue(started.wait(1), "execution did not reach the external probe")
                before = time.monotonic()
                environment = self.slicer.detect_environment()
                elapsed = time.monotonic() - before
                self.assertTrue(environment["available"])
                self.assertLess(elapsed, 0.5, "UI detection waited for an external CLI process")
            finally:
                release.set()
                worker.join(3)

    def test_nonstandard_zip_separator_fails_cleanly_instead_of_crashing(self):
        def malformed(path):
            write_output(path, settings=False, extra={"Metadata\\project_settings.config": json.dumps(exported_settings())})
        try:
            result = self.run_fixture(self.prepare(), malformed)
        except KeyError:
            self.fail("malformed ZIP paths must be a failed result, not an uncaught KeyError")
        self.assertEqual(result["status"], "failed")


if __name__ == "__main__":
    unittest.main()
