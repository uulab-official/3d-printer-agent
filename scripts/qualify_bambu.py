#!/usr/bin/env python3
"""Run one pinned, offline Bambu CLI bootstrap; never send a job to a printer.

This experiment uses the official CLI documentation's unchanged example configs
and an original small cube. Success qualifies this native invocation only, not
the application's adapter, arbitrary raw presets, or physical print quality.
Only the standard library is required. Downloads and native output stay beneath
the selected ignored work directory; evidence excludes the large runtime image.
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
        os.killpg(process.pid, signal.SIGKILL)
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


def inspect_output(archive_path, exported_path):
    if not archive_path.is_file() or not 0 < archive_path.stat().st_size <= MAX_OUTPUT_BYTES:
        raise ValueError("Native sliced 3MF is missing, empty or too large.")
    exported = read_config(exported_path)
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
    return {"archive": {"path": str(archive_path), "bytes": archive_path.stat().st_size, "sha256": sha256(archive_path)},
            "exported_config": {"path": str(exported_path), "sha256": sha256(exported_path), "key_count": len(exported)},
            "gcode": gcodes, "project_settings": {key: settings[key] for key in keys if key in settings},
            "exported_settings": {key: exported[key] for key in keys if key in exported}}


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
        "schema_version": 1, "started_at": datetime.now(timezone.utc).isoformat(),
        "scope": "native_cli_bootstrap_only", "status": "running", "adapter_qualified": False,
        "raw_preset_resolution_qualified": False, "printer_connected": False, "physical_print_verified": False,
        "declared_release_version": VERSION, "release_commit": RELEASE_COMMIT, "reported_version": None,
        "platform": platform.platform(), "python": platform.python_version(),
        "wiki_url": WIKI_URL, "sources": [], "commands": [],
        "source_notes": "Official CLI examples remain unchanged, including inherits/include/variant/nil metadata. No automatic preset recommendation is made.",
        "license_notes": "Bambu Studio repository declares AGPL v3. External wiki attachments are attributed inputs, not relicensed as this project's MIT code; no attachment-specific license was observed.",
    }
    env = dict(os.environ)
    env.update({"XDG_CONFIG_HOME": str(runtime / "user-config"), "XDG_CACHE_HOME": str(runtime / "user-cache"),
                "XDG_DATA_HOME": str(runtime / "user-data")})
    try:
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
        manifest["status"] = "passed"
        print("Native bootstrap passed: readable plate G-code and project JSON are present. The application adapter and physical printing remain unqualified.", flush=True)
    except Exception as exc:
        manifest["status"] = "failed"
        manifest["error"] = f"{type(exc).__name__}: {exc}"
        print(manifest["error"], flush=True)
    finally:
        manifest["completed_at"] = datetime.now(timezone.utc).isoformat()
        (evidence / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0 if manifest["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
