"""Adapter boundary tests. Synthetic CLI responses are not native Bambu validation."""

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


HELP_TEXT = "BambuStudio 02.05.00.66\n--load-settings --load-filaments --slice --outputdir --export-3mf"


def full_bundle():
    """Hand-written test values, never supplied as production print presets."""
    return {
        "source": "user_export",
        "machine": {
            "name": "Test printer 0.4 nozzle",
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
        "printer_settings_id": "Test printer 0.4 nozzle",
        "printer_model": "Test printer",
        "printer_technology": "FFF",
        "nozzle_diameter": [0.4],
        "printable_area": ["0x0", "200x0", "200x200", "0x200"],
        "printable_height": 200,
        "machine_start_gcode": "; fixture start",
        "machine_end_gcode": "; fixture end",
        "print_settings_id": "Test process",
        "layer_height": 0.2,
        "initial_layer_print_height": 0.2,
        "wall_loops": 2,
        "top_shell_layers": 4,
        "bottom_shell_layers": 4,
        "sparse_infill_density": "15%",
        "outer_wall_speed": 50,
        "inner_wall_speed": 75,
        "sparse_infill_speed": 100,
        "initial_layer_speed": 20,
        "filament_settings_id": ["Test material"],
        "filament_type": ["PLA"],
        "filament_diameter": [1.75],
        "filament_density": [1.2],
        "filament_flow_ratio": [1.0],
        "filament_max_volumetric_speed": [10],
        "nozzle_temperature": [210],
        "nozzle_temperature_initial_layer": [215],
        "hot_plate_temp": [55],
        "hot_plate_temp_initial_layer": [55],
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
                writer(Path(argv[argv.index("--export-3mf") + 1]))
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

    def test_unresolved_inheritance_and_missing_minimum_fields_block_preparation(self):
        cases = [
            ("machine", "inherits", "base machine"),
            ("process", "include", ["base process"]),
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
        mismatch["layer_height"] = 0.4
        for index, settings in enumerate([False, mismatch]):
            with self.subTest(index=index):
                result = self.run_fixture(self.prepare(directory=f"review-{index}"), lambda p: write_output(p, settings=settings))
                self.assertEqual(result["status"], "needs_review")
                self.assertTrue(Path(result["output_path"]).exists())
                self.assertTrue(any(not check["passed"] for check in result["checks"]))

    def test_verified_fixture_is_sliced_without_invented_statistics_or_print_status(self):
        result = self.run_fixture(self.prepare(), write_output)
        self.assertEqual(result["status"], "sliced", result["checks"])
        self.assertEqual(result["exit_code"], 0)
        self.assertEqual(result["printer_status"], "not_checked")
        self.assertEqual(result["print_status"], "not_started")
        self.assertIsNone(result["estimated_time_seconds"])
        self.assertIsNone(result["filament_grams"])

    def test_nonzero_exit_does_not_promote_partial_output(self):
        result = self.run_fixture(self.prepare(), write_output, returncode=2)
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["exit_code"], 2)
        self.assertIsNone(result["output_path"])

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
