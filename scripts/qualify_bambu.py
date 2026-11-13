#!/usr/bin/env python3
"""Run pinned, local Bambu CLI and application adapter smoke checks.

The bootstrap uses unchanged official example configs. Adapter checks use an
explicitly synthetic minimum config, an original cube and an original example
3MF. Native defaults fill unspecified settings; this is not a manufacturer preset
or a physical print qualification. No job is sent to a printer. Downloads require
network access; native execution is local, not network-isolated. Only the standard
library is required. Evidence excludes the large downloaded runtime image.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import platform
import re
import signal
import stat
import subprocess
import sys
import threading
import time
import urllib.request
import zipfile


VERSION = "02.09.01.70"
RELEASE_COMMIT = "56a57d00a591360cf41bf21383915ee5bf357be5"
WIKI_URL = "https://github.com/bambulab/BambuStudio/wiki/Command-Line-Usage"
APPIMAGE = {
    "filename": "BambuStudio_ubu24-v02.09.01.70-20261103183404.AppImage",
    "url": "https://github.com/bambulab/BambuStudio/releases/download/v02.09.01.70/BambuStudio_ubu24-v02.09.01.70-20261103183404.AppImage",
    "sha256": "668dabb1be53c758189ed6bc89935285dea5e0af46216546b1bafd6882e9aff0",
    "bytes": 255822328,
}
CONFIGS = (
    {"filename": "machine.json", "url": "https://github.com/user-attachments/files/26363641/machine.json",
     "sha256": "e7b2e9dab30cb053ef7e81f5bab9ed100c461a6217b82b4710e7f723ca964ab8", "bytes": 28051},
    {"filename": "process.json", "url": "https://github.com/user-attachments/files/26363644/process.json",
     "sha256": "3313337e9c87e599995f2bd4a3b55f04153111e9437a253e79e0e0542ceba2d1", "bytes": 8207},
    {"filename": "filament.json", "url": "https://github.com/user-attachments/files/26363647/filament.json",
     "sha256": "eac8cc4f2a5fa5676679ebd24f9956513818c97bf657917fea1f464702751626", "bytes": 8042},
)
MAX_LOG_BYTES = 2 * 1024 * 1024
MAX_OUTPUT_BYTES = 64 * 1024 * 1024
MAX_UNPACKED_BYTES = 256 * 1024 * 1024
REPO_ROOT = Path(__file__).resolve().parents[1]


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def download(source, folder):
    """Fetch an exact known file; a changed upstream attachment is a failure."""
    path = folder / source["filename"]
    started = time.monotonic()
    request = urllib.request.Request(source["url"], headers={"User-Agent": "3D-Printer-Agent-native-qualification"})
    with urllib.request.urlopen(request, timeout=30) as response, path.open("xb") as output:
        size = 0
        while chunk := response.read(1024 * 1024):
            size += len(chunk)
            if size > source["bytes"] or time.monotonic() - started > 180:
                raise ValueError(f"Download exceeded pinned size or time budget: {source['filename']}")
            output.write(chunk)
    if size != source["bytes"] or sha256(path) != source["sha256"]:
        raise ValueError(f"Downloaded bytes do not match pinned evidence: {source['filename']}")
    return {**source, "verified": True, "path": str(path)}


def run_command(argv, cwd, env, log_dir, label, timeout):
    """Drain both native pipes continuously while bounding the saved logs."""
    result = {"argv": argv, "cwd": str(cwd), "timeout_seconds": timeout,
              "returncode": None, "timed_out": False, "logs": {}}
    started = time.monotonic()
    process = subprocess.Popen(argv, cwd=cwd, env=env, stdin=subprocess.DEVNULL,
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                               start_new_session=True)

    def drain(pipe, stream):
        path = log_dir / f"{label}.{stream}.log"
        total = 0
        with path.open("wb") as output:
            while chunk := pipe.read(65536):
                kept = max(0, MAX_LOG_BYTES - total)
                if kept:
                    output.write(chunk[:kept])
                total += len(chunk)
            if total > MAX_LOG_BYTES:
                output.write(b"\n[remaining native log omitted by size bound]\n")
        pipe.close()
        result["logs"][stream] = {"path": str(path), "observed_bytes": total,
                                  "truncated": total > MAX_LOG_BYTES}

    readers = [threading.Thread(target=drain, args=(pipe, stream), daemon=True)
               for pipe, stream in ((process.stdout, "stdout"), (process.stderr, "stderr"))]
    for reader in readers:
        reader.start()
    try:
        result["returncode"] = process.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        result["timed_out"] = True
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        result["returncode"] = process.wait(timeout=10)
    for reader in readers:
        reader.join(timeout=10)
    if any(reader.is_alive() for reader in readers):
        # A descendant must not keep a pipe and stall evidence finalization.
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        for reader in readers:
            reader.join(timeout=2)
    result["duration_seconds"] = round(time.monotonic() - started, 3)
    result["logs_complete"] = not any(reader.is_alive() for reader in readers)
    return result


def command_text(record):
    return "\n".join(Path(log["path"]).read_text(encoding="utf-8", errors="replace")
                     for log in record["logs"].values())


def cube_stl(path):
    """Original deterministic 10 x 10 x 2 mm closed cube, twelve triangles."""
    vertices = ((0, 0, 0), (10, 0, 0), (10, 10, 0), (0, 10, 0),
                (0, 0, 2), (10, 0, 2), (10, 10, 2), (0, 10, 2))
    faces = ((0, 2, 1), (0, 3, 2), (4, 5, 6), (4, 6, 7),
             (0, 1, 5), (0, 5, 4), (1, 2, 6), (1, 6, 5),
             (2, 3, 7), (2, 7, 6), (3, 0, 4), (3, 4, 7))
    lines = ["solid original_cube_10x10x2"]
    for face in faces:
        a, b, c = (vertices[index] for index in face)
        u, v = [b[i] - a[i] for i in range(3)], [c[i] - a[i] for i in range(3)]
        normal = (u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2], u[0] * v[1] - u[1] * v[0])
        length = sum(value * value for value in normal) ** 0.5
        lines.append("  facet normal " + " ".join(f"{value / length:g}" for value in normal))
        lines.append("    outer loop")
        lines.extend("      vertex " + " ".join(str(value) for value in vertex) for vertex in (a, b, c))
        lines.extend(("    endloop", "  endfacet"))
    lines.extend(("endsolid original_cube_10x10x2", ""))
    path.write_text("\n".join(lines), encoding="ascii")
    return {"path": str(path), "sha256": sha256(path), "bytes": path.stat().st_size,
            "source": "original geometry generated by this script", "dimensions_mm": [10, 10, 2], "triangles": 12}


def read_config(path):
    if not path.is_file() or not 0 < path.stat().st_size <= 8 * 1024 * 1024:
        raise ValueError(f"Missing or oversized native JSON export: {path.name}")
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Native JSON export is not an object: {path.name}")
    return value


def inspect_output(archive_path, exported_path=None, expected_settings=None):
    if not archive_path.is_file() or not 0 < archive_path.stat().st_size <= MAX_OUTPUT_BYTES:
        raise ValueError("Native sliced 3MF is missing, empty or too large.")
    exported = read_config(exported_path) if exported_path is not None else None
    with zipfile.ZipFile(archive_path) as archive:
        entries = archive.infolist()
        if not entries or len(entries) > 2048 or sum(i.file_size for i in entries) > MAX_UNPACKED_BYTES:
            raise ValueError("Native 3MF exceeds archive inspection limits.")
        names = set()
        for entry in entries:
            path = PurePosixPath(entry.filename)
            if (path.is_absolute() or ".." in path.parts or "\\" in entry.filename or ":" in entry.filename
                    or entry.filename in names or entry.flag_bits & 1 or stat.S_ISLNK(entry.external_attr >> 16)
                    or entry.file_size > MAX_OUTPUT_BYTES):
                raise ValueError("Native 3MF contains an unsupported archive entry.")
            names.add(entry.filename)
        if "[Content_Types].xml" not in names or archive.testzip() is not None:
            raise ValueError("Native 3MF container or ZIP integrity is invalid.")
        gcodes = []
        for entry in entries:
            if re.fullmatch(r"Metadata/plate_[1-9][0-9]*\.gcode", entry.filename):
                data = archive.read(entry)
                text = data.decode("utf-8")
                moves = len(re.findall(r"^\s*G[0123](?:\s|$)", text, re.MULTILINE))
                if not data or not moves:
                    raise ValueError("Native G-code contains no readable movement commands.")
                gcodes.append({"name": entry.filename, "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest(), "motion_lines": moves})
        if not gcodes:
            raise ValueError("Native 3MF contains no readable plate G-code.")
        settings = json.loads(archive.read("Metadata/project_settings.config"))
        if not isinstance(settings, dict):
            raise ValueError("Native 3MF project settings are not a JSON object.")
    keys = ("printer_model", "printer_settings_id", "print_settings_id", "filament_settings_id",
            "nozzle_diameter", "curr_bed_type", "filament_extruder_variant", "printer_extruder_variant",
            "layer_height", "nozzle_temperature", "filament_flow_ratio", "filament_max_volumetric_speed")
    inspection = {"archive": {"path": str(archive_path), "bytes": archive_path.stat().st_size, "sha256": sha256(archive_path)},
                  "gcode": gcodes, "project_settings_key_count": len(settings),
                  "project_settings": {key: settings[key] for key in keys if key in settings}}
    if exported is not None:
        inspection.update(exported_config={"path": str(exported_path), "sha256": sha256(exported_path), "key_count": len(exported)},
                          exported_settings={key: exported[key] for key in keys if key in exported})
    if expected_settings is not None:
        # The oracle is a separate handwritten fixture contract, never the
        # adapter's plan/expected_settings or one of its test helpers.
        inspection["independent_core_checks"] = [
            {"name": key, "expected": expected, "actual": settings.get(key),
             "passed": key in settings and settings[key] == expected}
            for key, expected in expected_settings.items()
        ]
        (archive_path.parent / "native-project-settings.json").write_text(
            json.dumps(settings, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return inspection


def synthetic_fixture():
    """Handwritten CI inputs, deliberately not a claimed user/vendor export.

    source=user_export exercises the application's accepted bundle contract;
    this fixture's actual provenance is synthetic and recorded separately.
    These minimum settings depend on native defaults and must not be offered
    to users as printer/material recommendations.
    """
    bundle = {
        "source": "user_export", "plate_type": "High Temp Plate",
        "machine": {
            "from": "user", "type": "machine", "name": "PPA Synthetic Machine CI Only",
            "printer_settings_id": "PPA Synthetic Machine CI Only",
            "printer_model": "PPA Synthetic FFF CI Only", "printer_technology": "FFF",
            "nozzle_diameter": ["0.4"],
            "printable_area": ["0x0", "256x0", "256x256", "0x256"], "printable_height": "256",
            "machine_start_gcode": "; SYNTHETIC CI ONLY - not a hardware preset\nG90\nM83",
            "machine_end_gcode": "; SYNTHETIC CI ONLY\nM400",
        },
        "process": {
            "from": "user", "type": "process", "name": "PPA Synthetic Process CI Only",
            "print_settings_id": "PPA Synthetic Process CI Only",
            "layer_height": "0.2", "initial_layer_print_height": "0.2",
            "wall_loops": "2", "top_shell_layers": "3", "bottom_shell_layers": "3",
            "sparse_infill_density": "15%", "outer_wall_speed": "40", "inner_wall_speed": "60",
            "sparse_infill_speed": "80", "initial_layer_speed": "20",
        },
        "filaments": [{
            "from": "user", "type": "filament", "name": "PPA Synthetic PLA CI Only",
            "filament_settings_id": ["PPA Synthetic PLA CI Only"],
            "filament_type": ["PLA"], "filament_diameter": ["1.75"], "filament_density": ["1.24"],
            "filament_flow_ratio": ["1"], "filament_max_volumetric_speed": ["10"],
            "nozzle_temperature": ["200"], "nozzle_temperature_initial_layer": ["205"],
            "hot_plate_temp": ["50"], "hot_plate_temp_initial_layer": ["55"],
        }],
    }
    # Intentionally written independently of prepare_slice's computed plan.
    expected = {
        "printer_settings_id": "PPA Synthetic Machine CI Only",
        "print_settings_id": "PPA Synthetic Process CI Only",
        "filament_settings_id": ["PPA Synthetic PLA CI Only"],
        "printer_model": "PPA Synthetic FFF CI Only", "printer_technology": "FFF",
        "nozzle_diameter": ["0.4"], "printable_area": ["0x0", "256x0", "256x256", "0x256"],
        "printable_height": "256",
        "machine_start_gcode": "; SYNTHETIC CI ONLY - not a hardware preset\nG90\nM83",
        "machine_end_gcode": "; SYNTHETIC CI ONLY\nM400",
        "layer_height": "0.2", "initial_layer_print_height": "0.2", "wall_loops": "2",
        "top_shell_layers": "3", "bottom_shell_layers": "3", "sparse_infill_density": "15%",
        "outer_wall_speed": "40", "inner_wall_speed": "60", "sparse_infill_speed": "80", "initial_layer_speed": "20",
        "curr_bed_type": "High Temp Plate", "filament_type": ["PLA"], "filament_diameter": ["1.75"],
        "filament_density": ["1.24"], "filament_flow_ratio": ["1"], "filament_max_volumetric_speed": ["10"],
        "nozzle_temperature": ["200"], "nozzle_temperature_initial_layer": ["205"],
        "hot_plate_temp": ["50"], "hot_plate_temp_initial_layer": ["55"],
    }
    return bundle, expected


def adapter_smoke(executable, cube, evidence, env, report):
    """Exercise the real public application functions against the native CLI."""
    sys.path.insert(0, str(REPO_ROOT))
    from print_agent.slicer import execute_slice, prepare_slice

    report.update(status="running", synthetic_fixture=True, source="handwritten_ci_fixture",
                  contract_source_field="user_export", uses_native_defaults=True,
                  manufacturer_preset=False, hardware_qualified=False, cases=[])
    adapter_dir = evidence / "native-adapter"
    adapter_dir.mkdir()
    bundle, expected = synthetic_fixture()
    (adapter_dir / "synthetic-bundle.json").write_text(json.dumps(bundle, indent=2) + "\n", encoding="utf-8")
    (adapter_dir / "independent-core-expectations.json").write_text(json.dumps(expected, indent=2) + "\n", encoding="utf-8")
    example_dir = REPO_ROOT / "examples" / "cable_comb"
    example_manifest_path = example_dir / "manifest.json"
    example_manifest = read_config(example_manifest_path)
    example = example_dir / "model.3mf"
    expected_artifact = example_manifest["artifacts"]["three_mf"]
    if (expected_artifact["filename"] != example.name or example.stat().st_size != expected_artifact["bytes"]
            or sha256(example) != expected_artifact["sha256"]):
        raise ValueError("Original example 3MF does not match its checked-in manifest.")
    (adapter_dir / "original-example-manifest.json").write_bytes(example_manifest_path.read_bytes())
    report["example_source"] = {"path": "examples/cable_comb/model.3mf", **expected_artifact,
                                "manifest_sha256": sha256(example_manifest_path), "verified": True}
    report["adapter_source_sha256"] = sha256(REPO_ROOT / "print_agent" / "slicer.py")
    # execute_slice inherits the process environment. Reuse the isolated XDG
    # directories used by bootstrap without changing HOME or any credentials.
    old_xdg = {key: os.environ.get(key) for key in ("XDG_CONFIG_HOME", "XDG_CACHE_HOME", "XDG_DATA_HOME")}
    os.environ.update({key: env[key] for key in old_xdg})
    try:
        for label, source in (("original-cube-stl", cube), ("original-cable-comb-3mf", example)):
            case_dir = adapter_dir / label
            case_dir.mkdir()
            case = {"name": label, "status": "running", "source_sha256": sha256(source)}
            report["cases"].append(case)
            plan = prepare_slice(source, case_dir / "job", bundle, executable_path=str(executable))
            (case_dir / "plan.json").write_text(json.dumps(plan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            if not plan.get("ready"):
                case.update(status="failed", diagnostics=plan.get("diagnostics"))
                continue
            started = time.monotonic()
            result = execute_slice(plan, timeout_seconds=180)
            case["duration_seconds"] = round(time.monotonic() - started, 3)
            (case_dir / "result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            for stream in ("stdout", "stderr"):
                (case_dir / f"adapter.{stream}.log").write_text(result.get(stream, ""), encoding="utf-8")
            case.update(adapter_status=result.get("status"), bambu_version=result.get("bambu_version"),
                        exit_code=result.get("exit_code"), argv=plan["argv"],
                        adapter_checks=result.get("checks", []), output_sha256=result.get("output_sha256"))
            output_path = Path(plan["output_path"])
            try:
                inspection = inspect_output(output_path, expected_settings=expected)
                case["independent_output_inspection"] = inspection
                checks = {
                    "adapter_reports_sliced": result.get("status") == "sliced",
                    "exact_native_version": result.get("bambu_version") == VERSION,
                    "zero_exit_code": result.get("exit_code") == 0,
                    "all_adapter_checks_pass": bool(result.get("checks")) and all(item.get("passed") is True for item in result["checks"]),
                    "correct_output_path": result.get("output_path") == str(output_path),
                    "correct_output_digest": result.get("output_sha256") == inspection["archive"]["sha256"],
                    "independent_core_settings_match": all(item["passed"] for item in inspection["independent_core_checks"]),
                    "printer_not_checked": result.get("printer_status") == "not_checked",
                    "print_not_started": result.get("print_status") == "not_started",
                }
                case["qualification_checks"] = checks
                case["status"] = "passed" if all(checks.values()) else "failed"
            except Exception as exc:
                case.update(status="failed", error=f"{type(exc).__name__}: {exc}")
            print(f"Application adapter {label}: {case['status']} (native status {result.get('status')}).", flush=True)
    finally:
        for key, previous in old_xdg.items():
            if previous is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = previous
    report["status"] = "passed" if len(report["cases"]) == 2 and all(case["status"] == "passed" for case in report["cases"]) else "failed"
    if report["status"] != "passed":
        raise RuntimeError("Application adapter native smoke did not pass both original input cases; inspect plan/result/native evidence.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--work-dir", type=Path, default=Path("qa-output/native-bambu"))
    args = parser.parse_args()
    root = args.work_dir.expanduser().resolve()
    if root.exists() and any(root.iterdir()):
        parser.error("Use a new empty work directory; prior qualification evidence is never overwritten.")
    evidence, runtime = root / "evidence", root / "runtime"
    inputs, output, logs = evidence / "inputs", evidence / "output", evidence / "logs"
    for folder in (inputs, output, logs, runtime):
        folder.mkdir(parents=True, exist_ok=True)
    manifest = {
        "schema_version": 2, "started_at": datetime.now(timezone.utc).isoformat(),
        "scope": "native_bootstrap_and_synthetic_adapter_smoke", "status": "running",
        "native_bootstrap": {"status": "not_run"}, "native_adapter_smoke": {"status": "not_run"},
        "adapter_qualified": False,
        "raw_preset_resolution_qualified": False, "printer_connected": False, "physical_print_verified": False,
        "declared_release_version": VERSION, "release_commit": RELEASE_COMMIT, "reported_version": None,
        "platform": platform.platform(), "python": platform.python_version(),
        "repository_commit": os.environ.get("GITHUB_SHA"), "qualification_script_sha256": sha256(Path(__file__)),
        "wiki_url": WIKI_URL, "sources": [], "commands": [],
        "source_notes": "Official CLI examples remain unchanged. Separate adapter inputs are handwritten synthetic fixtures using native defaults, not user exports or manufacturer recommendations.",
        "license_notes": "Bambu Studio repository declares AGPL v3. External wiki attachments are attributed inputs, not relicensed as this project's MIT code; no attachment-specific license was observed.",
    }
    env = dict(os.environ)
    env.update({"XDG_CONFIG_HOME": str(runtime / "user-config"), "XDG_CACHE_HOME": str(runtime / "user-cache"),
                "XDG_DATA_HOME": str(runtime / "user-data")})
    try:
        manifest["native_bootstrap"]["status"] = "running"
        print("Downloading and verifying the pinned official runtime and CLI examples.", flush=True)
        runtime_source = download(APPIMAGE, runtime)
        manifest["sources"].append(runtime_source)
        for source in CONFIGS:
            manifest["sources"].append(download(source, inputs))
            read_config(inputs / source["filename"])
        model = inputs / "original-cube-10x10x2.stl"
        manifest["model"] = cube_stl(model)
        image = runtime / APPIMAGE["filename"]
        image.chmod(0o755)
        extraction = run_command([str(image), "--appimage-extract"], runtime, env, logs, "extract", 120)
        manifest["commands"].append(extraction)
        if extraction["returncode"] != 0 or extraction["timed_out"]:
            raise RuntimeError("AppImage extraction failed; inspect extract logs.")
        executable = runtime / "squashfs-root" / "AppRun"
        if not executable.is_file():
            raise RuntimeError("Extracted runtime has no AppRun launcher.")
        print("Probing the actual extracted Studio launcher without a virtual display.", flush=True)
        help_run = run_command([str(executable), "--help"], output, env, logs, "help", 30)
        manifest["commands"].append(help_run)
        help_text = command_text(help_run)
        match = re.search(r"Bambu\s*Studio[^\r\n]{0,60}?(\d+\.\d+\.\d+(?:\.\d+)?)", help_text, re.I)
        manifest["reported_version"] = match.group(1) if match else None
        if help_run["returncode"] != 0 or help_run["timed_out"]:
            raise RuntimeError("Native --help failed; inspect help logs before changing the runtime environment.")
        required = ("--load-settings", "--load-filaments", "--slice", "--outputdir", "--export-3mf", "--export-settings")
        manifest["observed_cli_options"] = [option for option in required if option in help_text]
        if len(manifest["observed_cli_options"]) != len(required):
            raise RuntimeError("Native --help did not advertise every required bootstrap option.")
        argv = [str(executable), "--load-settings", f"{inputs / 'machine.json'};{inputs / 'process.json'}",
                "--load-filaments", str(inputs / "filament.json"), "--curr-bed-type", "Textured PEI Plate",
                "--arrange", "1", "--slice", "0", "--debug", "2", "--outputdir", str(output),
                "--export-settings", str(output / "resolved-project.json"),
                "--export-3mf", "qualification.gcode.3mf", str(model)]
        print("Running the unchanged official examples with an original 10 x 10 x 2 mm cube.", flush=True)
        sliced = run_command(argv, output, env, logs, "slice", 180)
        manifest["commands"].append(sliced)
        if sliced["returncode"] != 0 or sliced["timed_out"]:
            raise RuntimeError("Native slicing failed; inspect slice logs and retain the unchanged inputs.")
        manifest["output_inspection"] = inspect_output(output / "qualification.gcode.3mf", output / "resolved-project.json")
        for source in CONFIGS:
            if sha256(inputs / source["filename"]) != source["sha256"]:
                raise RuntimeError("An original input changed during native execution.")
        manifest["native_bootstrap"]["status"] = "passed"
        print("Native bootstrap passed. Running separate synthetic application adapter checks.", flush=True)
        adapter_smoke(executable, model, evidence, env, manifest["native_adapter_smoke"])
        manifest["adapter_qualified"] = True
        manifest["adapter_qualification_scope"] = "Pinned native version; synthetic single-filament core settings; original STL and 3MF only. Unspecified native defaults and physical printing remain unqualified."
        manifest["status"] = "passed"
        print("Native bootstrap and both application adapter smoke cases passed. No manufacturer preset or physical printing was qualified.", flush=True)
    except Exception as exc:
        manifest["status"] = "failed"
        manifest["adapter_qualified"] = False
        for stage in ("native_bootstrap", "native_adapter_smoke"):
            if manifest[stage]["status"] == "running":
                manifest[stage]["status"] = "failed"
        for case in manifest["native_adapter_smoke"].get("cases", []):
            if case["status"] == "running":
                case.update(status="failed", error=f"{type(exc).__name__}: {exc}")
        manifest["error"] = f"{type(exc).__name__}: {exc}"
        print(manifest["error"], flush=True)
    finally:
        manifest["completed_at"] = datetime.now(timezone.utc).isoformat()
        (evidence / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0 if manifest["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
