"""Project-plan boundary tests; subprocess responses are synthetic, never Studio."""

import hashlib
import io
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET
import zipfile

from print_agent import slicer
from tests.studio_project_fixtures import project_bytes


PROJECT_HELP = "BambuStudio-02.09.01.70:\n--arrange --slice --export-3mf"
CORE = "http://schemas.microsoft.com/3dmanufacturing/core/2015/02"


def cube_model_xml():
    """Independent 10 x 10 x 2 mm old-source geometry; never the current CAD."""
    points = ((0, 0, 0), (10, 0, 0), (10, 10, 0), (0, 10, 0),
              (0, 0, 2), (10, 0, 2), (10, 10, 2), (0, 10, 2))
    faces = ((0, 2, 1), (0, 3, 2), (4, 5, 6), (4, 6, 7),
             (0, 1, 5), (0, 5, 4), (1, 2, 6), (1, 6, 5),
             (2, 3, 7), (2, 7, 6), (3, 0, 4), (3, 4, 7))
    vertices = "".join(f'<vertex x="{x}" y="{y}" z="{z}"/>' for x, y, z in points)
    triangles = "".join(f'<triangle v1="{a}" v2="{b}" v3="{c}"/>' for a, b, c in faces)
    return (f'<model xmlns="{CORE}" unit="millimeter"><resources><object id="1" type="model">'
            f'<mesh><vertices>{vertices}</vertices><triangles>{triangles}</triangles></mesh>'
            '</object></resources><build><item objectid="1"/></build></model>').encode()


class ProjectSlicerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.model = self.root / "현재 모델 ; $(touch sentinel).3mf"
        self.model.write_bytes((Path(__file__).resolve().parents[1] / "examples/cable_comb/model.3mf").read_bytes())
        self.source = project_bytes()
        self.source_name = "recorded-studio-project.3mf"
        self.source_id = "a" * 32
        self.executable = self.root / "synthetic executable"
        self.executable.write_bytes(b"fixture only; never launched")
        self.executable.chmod(0o700)
        slicer._PROBE_CACHE.clear()

    def prepare(self, *, directory="new-attempt", source=None, executable=None):
        prepare = getattr(slicer, "prepare_project_slice", None)
        self.assertTrue(callable(prepare), "the project path must prepare a download independently of native slicing")
        return prepare(self.model, self.root / directory, self.source_name,
                       self.source if source is None else source, source_id=self.source_id,
                       executable_path=str(self.executable if executable is None else executable))

    def write_output(self, plan, *, updates=None, omit_settings=False, gcode=b"; synthetic toolpath\nG1 X1 Y1 E1\n"):
        with zipfile.ZipFile(plan["project_path"]) as archive:
            payload = {name: archive.read(name) for name in archive.namelist()}
        if omit_settings:
            payload.pop("Metadata/project_settings.config")
        elif updates:
            settings = json.loads(payload["Metadata/project_settings.config"])
            settings.update(updates)
            payload["Metadata/project_settings.config"] = json.dumps(settings).encode()
        if gcode is not None:
            payload["Metadata/plate_1.gcode"] = gcode
        with zipfile.ZipFile(plan["output_path"], "x", compression=zipfile.ZIP_DEFLATED) as archive:
            for name, data in payload.items():
                archive.writestr(name, data)

    def run_fixture(self, plan, *, help_text=PROJECT_HELP, writer=True, updates=None,
                    omit_settings=False, gcode=b"; synthetic toolpath\nG1 X1 Y1 E1\n", returncode=0, after_write=None):
        def invoke(argv, **kwargs):
            if argv[1:] == ["--help"]:
                return subprocess.CompletedProcess(argv, 0, help_text, "")
            self.assertEqual(argv, [str(self.executable.resolve()), "--arrange", "1", "--slice", "0",
                                    "--export-3mf", Path(plan["output_path"]).name, plan["project_path"]])
            self.assertEqual(kwargs["cwd"], plan["job_dir"])
            self.assertIs(kwargs["shell"], False)
            if writer:
                self.write_output(plan, updates=updates, omit_settings=omit_settings, gcode=gcode)
            if after_write is not None:
                after_write()
            return subprocess.CompletedProcess(argv, returncode, "synthetic stdout", "synthetic stderr")
        with patch.object(slicer.subprocess, "run", side_effect=invoke):
            return slicer.execute_slice(plan)

    def test_missing_executable_still_prepares_exact_settings_and_separate_cad(self):
        original_model = self.model.read_bytes()
        with patch.object(slicer.subprocess, "run", side_effect=AssertionError("preparation must not launch any native process")):
            plan = self.prepare(executable=self.root / "missing-studio")
        self.assertTrue(plan["project_prepared"], plan["diagnostics"])
        self.assertFalse(plan["ready"])
        self.assertEqual(plan["kind"], "studio_project")
        self.assertEqual(self.model.read_bytes(), original_model)
        self.assertEqual(plan["project_source"]["source_id"], self.source_id)
        self.assertEqual(plan["project_source"]["archive_url"], f"/api/studio-projects/{self.source_id}/archive")
        self.assertNotIn("settings_text", plan["project_source"])
        self.assertNotIn("expected_settings", plan["project_source"])
        with zipfile.ZipFile(plan["project_path"]) as derived, zipfile.ZipFile(io.BytesIO(self.source)) as source:
            self.assertEqual(derived.read("Metadata/project_settings.config"), source.read("Metadata/project_settings.config"))
            self.assertNotEqual(derived.read("3D/3dmodel.model"), source.read("3D/3dmodel.model"))
            self.assertFalse(any(name.endswith(".gcode") for name in derived.namelist()))
        self.assertEqual(plan["project_sha256"], hashlib.sha256(Path(plan["project_path"]).read_bytes()).hexdigest())
        self.assertEqual(slicer.execute_slice(plan)["status"], "blocked")

    def test_supported_execution_has_fixed_direct_project_arguments_and_no_role_files(self):
        plan = self.prepare()
        self.assertTrue(plan["ready"], plan["diagnostics"])
        self.assertFalse((Path(plan["job_dir"]) / "config").exists())
        result = self.run_fixture(plan)
        self.assertEqual(result["status"], "sliced", result)
        self.assertEqual(result["bambu_version"], "02.09.01.70")
        self.assertEqual(result["printer_status"], "not_checked")
        self.assertEqual(result["print_status"], "not_started")
        self.assertTrue(result["project_settings_readback"]["all_values_equal"])
        self.assertFalse((self.root / "sentinel").exists())

    def test_wrong_runtime_and_missing_project_option_never_slice(self):
        for name, help_text in (("older", PROJECT_HELP.replace("02.09.01.70", "02.08.00.00")),
                                ("newer", PROJECT_HELP.replace("02.09.01.70", "02.10.00.00")),
                                ("unreported", "--arrange --slice --export-3mf"),
                                ("missing-arrange", PROJECT_HELP.replace("--arrange", "--arrange-unsupported"))):
            with self.subTest(name=name):
                slicer._PROBE_CACHE.clear()
                plan = self.prepare(directory=name)
                def probe_only(argv, **kwargs):
                    if argv[1:] != ["--help"]:
                        self.fail("unsupported native runtime must never receive a slice command")
                    return subprocess.CompletedProcess(argv, 0, help_text, "")
                with patch.object(slicer.subprocess, "run", side_effect=probe_only):
                    result = slicer.execute_slice(plan)
                self.assertEqual(result["status"], "blocked")
                self.assertIsNone(result["output_path"])
                self.assertFalse(Path(plan["output_path"]).exists())

    def test_changed_plan_fields_are_refused_before_native_probe(self):
        mutations = {
            "argv": lambda plan: plan["argv"].insert(1, "--arbitrary"),
            "expected": lambda plan: plan["expected_settings"].update(nozzle_temperature=["250"]),
            "project-sha": lambda plan: plan.update(project_sha256="0" * 64),
            "receipt": lambda plan: plan["project_receipt"].update(model_sha256="0" * 64),
            "public-source": lambda plan: plan["project_source"]["source"].update(sha256="0" * 64),
            "executable": lambda plan: plan.update(executable_path=str(self.model)),
            "unexpected-hash-file": lambda plan: plan["file_hashes"].update({str(self.model): "0" * 64}),
        }
        for name, mutate in mutations.items():
            with self.subTest(name=name):
                plan = self.prepare(directory=name)
                mutate(plan)
                with patch.object(slicer.subprocess, "run", side_effect=AssertionError("tampered plan must not reach native code")):
                    result = slicer.execute_slice(plan)
                self.assertEqual(result["status"], "blocked", result)

    def test_changed_staged_source_model_receipt_or_project_is_refused(self):
        for index, relative in enumerate(("input/source.3mf", "input/model.3mf", "prepared-project.3mf", "preparation-receipt.json", "preparation.json")):
            with self.subTest(relative=relative):
                plan = self.prepare(directory=f"changed-{index}")
                target = Path(plan["job_dir"]) / relative
                target.write_bytes(target.read_bytes() + b"changed")
                with patch.object(slicer.subprocess, "run", side_effect=AssertionError("changed staged bytes must not execute")):
                    result = slicer.execute_slice(plan)
                self.assertEqual(result["status"], "blocked", result)

    def test_changed_source_and_updated_hash_still_cannot_change_prepared_contract(self):
        plan = self.prepare()
        target = Path(plan["job_dir"]) / "input/source.3mf"
        target.write_bytes(project_bytes(settings_overrides={"nozzle_temperature": ["250"]}))
        plan["file_hashes"][str(target)] = hashlib.sha256(target.read_bytes()).hexdigest()
        with patch.object(slicer.subprocess, "run", side_effect=AssertionError("recomputed source must disagree with the original receipt")):
            result = slicer.execute_slice(plan)
        self.assertEqual(result["status"], "blocked", result)

    def test_existing_attempt_and_existing_output_are_never_overwritten(self):
        original = self.prepare()
        project = Path(original["project_path"]).read_bytes()
        duplicate = self.prepare()
        self.assertFalse(duplicate["project_prepared"])
        self.assertIsNone(duplicate["project_path"])
        self.assertEqual(Path(original["project_path"]).read_bytes(), project)
        Path(original["output_path"]).write_bytes(b"old output remains evidence")
        with patch.object(slicer.subprocess, "run", side_effect=AssertionError("existing output must not be overwritten")):
            result = slicer.execute_slice(original)
        self.assertEqual(result["status"], "blocked")
        self.assertEqual(Path(original["output_path"]).read_bytes(), b"old output remains evidence")

    def test_unsupported_and_malformed_sources_expose_no_prepared_artifact(self):
        for name, content in (("malformed", b"not zip"), ("unsupported", project_bytes(settings_overrides={"nozzle_diameter": ["0.4", "0.6"]}))):
            with self.subTest(name=name):
                plan = self.prepare(directory=name, source=content)
                self.assertFalse(plan["ready"])
                self.assertFalse(plan["project_prepared"])
                self.assertIsNone(plan["project_path"])
                self.assertFalse((self.root / name / "prepared-project.3mf").exists())

    def test_missing_or_changed_core_readback_is_not_reported_sliced(self):
        for name, kwargs in (("missing", {"omit_settings": True}),
                             ("changed", {"updates": {"nozzle_temperature": ["250"]}})):
            with self.subTest(name=name):
                plan = self.prepare(directory=name)
                result = self.run_fixture(plan, **kwargs)
                self.assertEqual(result["status"], "needs_review", result)
                self.assertTrue(any(check["passed"] is False for check in result["checks"]))

    def test_comment_only_gcode_cannot_be_reported_sliced(self):
        plan = self.prepare()
        result = self.run_fixture(plan, gcode=b"; no motion in this fixture\n")
        self.assertEqual(result["status"], "failed", result)
        self.assertIsNone(result["output_path"])

    def test_full_snapshot_differences_are_reported_beyond_core_fields(self):
        plan = self.prepare()
        result = self.run_fixture(plan, updates={"filament_colour": ["#112233"], "unexpected_native_setting": "observed"})
        changes = result["project_settings_readback"]
        self.assertEqual(result["status"], "needs_review")
        self.assertFalse(changes["all_values_equal"])
        self.assertGreaterEqual(changes["changed_key_count"], 1)
        self.assertEqual(changes["added_key_count"], 1)
        self.assertEqual({item["key"] for item in changes["differences"]}, {"filament_colour", "unexpected_native_setting"})

    def test_only_observed_arrange_normalization_can_keep_the_slice_verified(self):
        plan = self.prepare()
        result = self.run_fixture(plan, updates={"wipe_tower_x": ["166.25"], "wipe_tower_y": ["168.75"],
                                                "upward_compatible_machine": []})
        self.assertEqual(result["status"], "sliced", result)
        changes = result["project_settings_readback"]
        self.assertEqual(changes["difference_count"], 3)
        self.assertEqual(changes["qualified_normalization_count"], 3)
        self.assertEqual(changes["unqualified_difference_count"], 0)

    def test_native_help_cannot_change_staged_bytes_before_slice(self):
        plan = self.prepare()
        def help_changes_source(argv, **kwargs):
            if argv[1:] != ["--help"]:
                self.fail("changed staged source must be rechecked after help")
            Path(plan["source_path"]).write_bytes(b"changed during help")
            return subprocess.CompletedProcess(argv, 0, PROJECT_HELP, "")
        with patch.object(slicer.subprocess, "run", side_effect=help_changes_source):
            result = slicer.execute_slice(plan)
        self.assertEqual(result["status"], "blocked")

    def test_native_output_cannot_be_promoted_after_it_changes_prepared_input(self):
        plan = self.prepare()
        result = self.run_fixture(plan, after_write=lambda: Path(plan["source_path"]).write_bytes(b"changed during slice"))
        self.assertEqual(result["status"], "failed", result)
        self.assertIsNone(result["output_path"])

    def test_long_comment_across_read_chunks_is_not_a_motion_command(self):
        prefix = b";" + b"x" * (65536 - 65)
        command = b"G1 X1 Y1 E1"
        comment = prefix + command + b"x" * (65536 - len(prefix) - len(command)) + b"still comment\n"
        plan = self.prepare()
        result = self.run_fixture(plan, gcode=comment)
        self.assertEqual(result["status"], "failed", result)
        self.assertIsNone(result["output_path"])

    def test_failed_prepared_file_verification_exposes_no_download(self):
        original_hash = slicer._hash
        def fail_project_read(path):
            if path.name == "prepared-project.3mf":
                raise OSError("synthetic read failure after project write")
            return original_hash(path)
        with patch.object(slicer, "_hash", side_effect=fail_project_read):
            plan = self.prepare()
        self.assertFalse(plan["project_prepared"])
        self.assertFalse(plan["ready"])
        self.assertIsNone(plan["project_path"])
        self.assertFalse((self.root / "new-attempt/prepared-project.3mf").exists())

    def test_staged_symlink_cannot_reuse_matching_file_hash(self):
        plan = self.prepare()
        source = Path(plan["source_path"])
        elsewhere = self.root / "elsewhere.3mf"
        elsewhere.write_bytes(source.read_bytes())
        source.unlink()
        source.symlink_to(elsewhere)
        with patch.object(slicer.subprocess, "run", side_effect=AssertionError("staged symlink must not execute")):
            result = slicer.execute_slice(plan)
        self.assertEqual(result["status"], "blocked", result)

    def test_failed_or_timed_out_process_never_promotes_its_partial_output(self):
        failed = self.prepare(directory="failed-process")
        result = self.run_fixture(failed, returncode=3)
        self.assertEqual(result["status"], "failed")
        self.assertIsNone(result["output_path"])
        self.assertTrue(Path(failed["output_path"]).exists())
        timed_out = self.prepare(directory="timed-out-process")
        def timeout_after_partial_output(argv, **kwargs):
            if argv[1:] == ["--help"]:
                return subprocess.CompletedProcess(argv, 0, PROJECT_HELP, "")
            self.write_output(timed_out)
            raise subprocess.TimeoutExpired(argv, 180, output="synthetic partial log")
        with patch.object(slicer.subprocess, "run", side_effect=timeout_after_partial_output):
            result = slicer.execute_slice(timed_out)
        self.assertEqual(result["status"], "timed_out")
        self.assertIsNone(result["output_path"])
        self.assertTrue(Path(timed_out["output_path"]).exists())

    def test_duplicate_output_setting_cannot_hide_ambiguous_readback(self):
        plan = self.prepare()
        def duplicate_output():
            output = Path(plan["output_path"])
            with zipfile.ZipFile(output) as archive:
                payload = {name: archive.read(name) for name in archive.namelist()}
            raw = payload["Metadata/project_settings.config"].decode().rstrip()
            payload["Metadata/project_settings.config"] = (raw[:-1] + ',"nozzle_temperature":["200"]}').encode()
            with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                for name, content in payload.items():
                    archive.writestr(name, content)
        result = self.run_fixture(plan, after_write=duplicate_output)
        self.assertEqual(result["status"], "needs_review", result)
        self.assertTrue(any(item["name"] == "project_settings" and not item["passed"] for item in result["checks"]))

    def mutate_geometry_output(self, plan, kind):
        output = Path(plan["output_path"])
        with zipfile.ZipFile(output) as archive:
            payload = {name: archive.read(name) for name in archive.namelist()}
        name = "3D/3dmodel.model"
        if kind == "old-cube":
            payload[name] = cube_model_xml()
        elif kind == "missing":
            payload.pop(name)
        elif kind == "malformed":
            payload[name] = b"<model"
        else:
            root = ET.fromstring(payload[name])
            if kind == "multiple":
                resources = root.find(f"{{{CORE}}}resources")
                duplicate = ET.fromstring(ET.tostring(resources[0]))
                duplicate.set("id", "3")
                resources.append(duplicate)
            elif kind == "entity":
                payload[name] = b'<!DOCTYPE model [<!ENTITY value "bad">]>' + payload[name]
            else:
                item = root.find(f"{{{CORE}}}build/{{{CORE}}}item")
                item.set("transform", "2 0 0 0 1 0 0 0 1 0 0 0" if kind == "scaled" else
                         "6.123234e-17 1 0 -1 6.123234e-17 0 0 0 1 128 128 6")
            if kind != "entity":
                payload[name] = ET.tostring(root, encoding="utf-8", xml_declaration=True)
        with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for name, content in payload.items():
                archive.writestr(name, content)

    def test_correct_settings_and_gcode_cannot_hide_wrong_missing_or_extra_geometry(self):
        for kind in ("old-cube", "missing", "multiple", "scaled", "entity", "malformed"):
            with self.subTest(kind=kind):
                plan = self.prepare(directory=kind)
                result = self.run_fixture(plan, after_write=lambda: self.mutate_geometry_output(plan, kind))
                self.assertEqual(result["status"], "needs_review", result)
                self.assertTrue(any(item["name"] == "geometry" and not item["passed"] for item in result["checks"]))
                self.assertTrue(all(item["passed"] for item in result["checks"] if item["name"].startswith("setting:")))

    def test_qualified_native_rigid_plate_rotation_keeps_current_mesh_verified(self):
        plan = self.prepare()
        result = self.run_fixture(plan, after_write=lambda: self.mutate_geometry_output(plan, "rotated"))
        self.assertEqual(result["status"], "sliced", result)
        self.assertTrue(result["geometry_readback"]["passed"])
        self.assertEqual(result["geometry_readback"]["actual_vertices"], 1384)
        self.assertEqual(result["geometry_readback"]["actual_triangles"], 1332)


if __name__ == "__main__":
    unittest.main()
