"""Prepare and verify local Bambu Studio CLI jobs; never control a printer.

Supported validation is a minimum, not a universal Bambu full-config schema:
machine identity/FFF/bed geometry/nozzle/start/end G-code; process identity,
layer heights, shells, infill and four speeds; filament identity, material,
diameter/density/flow/MVS, nozzle temperatures and a shared bed-temperature pair.
Unresolved inheritance, nonfinite numbers and host post-processing are rejected.
Only those core settings are compared with the generated project. Other settings
and actual native/physical printing remain unverified. No numeric print presets
are supplied here. Statistics remain null until a versioned parser is validated.

CLI reference: https://github.com/bambulab/BambuStudio/wiki/Command-Line-Usage
"""

from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path, PurePosixPath
import platform
import re
import shutil
import stat
import subprocess
import threading
import time
import uuid
import zipfile


_REQUIRED_OPTIONS = ("--load-settings", "--load-filaments", "--slice", "--outputdir", "--export-3mf")
_MACHINE_FIELDS = (
    "printer_model", "printer_technology", "nozzle_diameter", "printable_area",
    "printable_height", "machine_start_gcode", "machine_end_gcode",
)
_PROCESS_FIELDS = (
    "layer_height", "initial_layer_print_height", "wall_loops", "top_shell_layers",
    "bottom_shell_layers", "sparse_infill_density", "outer_wall_speed",
    "inner_wall_speed", "sparse_infill_speed", "initial_layer_speed",
)
_FILAMENT_FIELDS = (
    "filament_type", "filament_diameter", "filament_density", "filament_flow_ratio",
    "filament_max_volumetric_speed", "nozzle_temperature", "nozzle_temperature_initial_layer",
)
_BED_PREFIXES = ("cool_plate", "eng_plate", "hot_plate", "textured_plate", "supertack_plate")
_MAX_ARCHIVE_ENTRIES = 2048
_MAX_ARCHIVE_BYTES = 512 * 1024 * 1024
_MAX_MEMBER_BYTES = 256 * 1024 * 1024
_MAX_CONFIG_BYTES = 8 * 1024 * 1024
_MAX_LOG_CHARS = 65536
_PROBE_CACHE: dict[tuple, dict] = {}
_PROBE_LOCK = threading.Lock()


def _fingerprint(path: Path) -> tuple:
    info = path.stat()
    return (str(path), info.st_size, info.st_mtime_ns, info.st_ino)


def _known_paths() -> list[Path]:
    system = platform.system()
    paths = []
    if system == "Darwin":
        paths.extend([
            Path("/Applications/BambuStudio.app/Contents/MacOS/BambuStudio"),
            Path("/Applications/Bambu Studio.app/Contents/MacOS/BambuStudio"),
            Path.home() / "Applications/BambuStudio.app/Contents/MacOS/BambuStudio",
        ])
    elif system == "Windows":
        for variable in ("ProgramFiles", "ProgramFiles(x86)", "LOCALAPPDATA"):
            base = os.environ.get(variable)
            if base:
                paths.extend([Path(base) / "Bambu Studio/bambu-studio.exe", Path(base) / "Programs/Bambu Studio/bambu-studio.exe"])
    else:
        paths.extend([Path("/usr/bin/bambu-studio"), Path("/usr/local/bin/bambu-studio"), Path("/opt/BambuStudio/bambu-studio")])
    for name in ("bambu-studio", "bambu-studio.exe", "BambuStudio"):
        located = shutil.which(name)
        if located:
            paths.append(Path(located))
    return paths


def _executable(path: Path) -> bool:
    return path.is_file() and (os.name == "nt" or os.access(path, os.X_OK))


def detect_environment() -> dict:
    """Cheap file-only discovery. Help/version probing is deferred to execution."""
    result = {"available": False, "path": None, "version": None, "capabilities": [],
              "printer_status": "not_checked", "diagnostics": []}
    override = os.environ.get("PPA_BAMBU_PATH", "").strip()
    candidates = [Path(override).expanduser()] if override else _known_paths()
    for candidate in candidates:
        try:
            path = candidate.resolve()
            if not _executable(path):
                continue
            result.update(available=True, path=str(path))
            cached = None
            # An in-flight help probe must never stall an environment/UI read.
            if _PROBE_LOCK.acquire(blocking=False):
                try:
                    cached = _PROBE_CACHE.get(_fingerprint(path))
                finally:
                    _PROBE_LOCK.release()
            if cached:
                result.update(version=cached["version"], capabilities=list(cached["capabilities"]))
                result["diagnostics"].extend(cached["diagnostics"])
            else:
                result["diagnostics"].append("실행 파일을 찾았습니다. CLI 기능은 실행 시 확인하며, 프린터 연결은 확인하지 않았습니다.")
            return result
        except (OSError, ValueError):
            continue
    result["diagnostics"].append(
        "PPA_BAMBU_PATH의 실행 파일을 찾거나 실행할 수 없습니다." if override else
        "Bambu Studio 실행 파일이 없습니다. 설치 후 PPA_BAMBU_PATH에 실행 파일의 절대 경로를 지정할 수 있습니다."
    )
    return result


def _text(value) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        value = value.decode("utf-8", errors="replace")
    value = str(value)
    return value if len(value) <= _MAX_LOG_CHARS else value[:_MAX_LOG_CHARS] + "\n[log truncated]"


def _probe_cli(path: Path, timeout_seconds: float) -> dict:
    key = _fingerprint(path)
    # Serialize the short, first probe; subsequent jobs and UI reads reuse it.
    with _PROBE_LOCK:
        cached = _PROBE_CACHE.get(key)
        if cached and (cached["supported"] or time.monotonic() - cached["checked_at"] < 30):
            return cached
        result = {"supported": False, "version": None, "capabilities": [], "diagnostics": [], "checked_at": time.monotonic()}
        try:
            completed = subprocess.run(
                [str(path), "--help"], shell=False, stdin=subprocess.DEVNULL,
                capture_output=True, text=True, encoding="utf-8", errors="replace",
                timeout=min(3, timeout_seconds), check=False,
            )
            output = _text(completed.stdout) + "\n" + _text(completed.stderr)
            result["capabilities"] = [option for option in _REQUIRED_OPTIONS if option in output]
            match = re.search(r"Bambu\s*Studio(?:\s+version)?[\s:\-]*(\d+\.\d+\.\d+(?:\.\d+)?)", output, re.I)
            result["version"] = match.group(1) if match else None
            result["supported"] = completed.returncode == 0 and len(result["capabilities"]) == len(_REQUIRED_OPTIONS)
            if not result["supported"]:
                result["diagnostics"].append("--help 응답에서 필요한 Bambu CLI 기능을 확인하지 못했습니다.")
        except subprocess.TimeoutExpired:
            result["diagnostics"].append("Bambu Studio --help 확인이 제한시간을 초과했습니다. 슬라이싱은 실행하지 않았습니다.")
        except OSError as exc:
            result["diagnostics"].append(f"Bambu Studio 실행 실패: {exc}")
        _PROBE_CACHE[key] = result
        return result


def _meaningful(value) -> bool:
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, list):
        return any(_meaningful(item) for item in value)
    return value is not None and value is not False and value != {}


def _reject_indirect_execution(value, location="config") -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            if key in ("inherits", "include") and _meaningful(item):
                raise ValueError(f"{location}.{key}: 상속을 해소한 full config가 필요합니다.")
            if key in ("post_process", "post_process_script", "post_process_scripts") and _meaningful(item):
                raise ValueError(f"{location}.{key}: 호스트 후처리 프로그램 실행은 지원하지 않습니다.")
            _reject_indirect_execution(item, f"{location}.{key}")
    elif isinstance(value, list):
        for item in value:
            _reject_indirect_execution(item, location)


def _scalar(value):
    return value[0] if isinstance(value, list) and len(value) == 1 else value


def _identity(config: dict, key: str) -> str:
    value = _scalar(config.get(key, config.get("name")))
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{key} 또는 name에 full config의 식별자가 필요합니다.")
    return value


def _numeric(value, key: str, minimum=0, inclusive=False, integer=False) -> None:
    values = value if isinstance(value, list) else [value]
    if not values or len(values) > 16:
        raise ValueError(f"{key}: 비어 있지 않은 유한 숫자 설정이 필요합니다.")
    for item in values:
        try:
            number = float(item)
        except (ValueError, TypeError):
            raise ValueError(f"{key}: 유한 숫자 설정이 필요합니다.") from None
        if isinstance(item, bool) or not math.isfinite(number) or (number < minimum if inclusive else number <= minimum) or (integer and not number.is_integer()):
            raise ValueError(f"{key}: 유효한 숫자 범위를 확인하세요.")


def _required(config: dict, fields: tuple, label: str) -> None:
    for key in fields:
        if key not in config or not _meaningful(config[key]):
            raise ValueError(f"{label}.{key}: full config의 필수 설정이 누락되었습니다.")


def _validate_bundle(bundle: dict) -> dict:
    if not isinstance(bundle, dict) or bundle.get("source") != "user_export":
        raise ValueError("source='user_export'인 사용자 full config 묶음이 필요합니다.")
    # JSON round-trip also rejects non-JSON types, cycles and numeric NaN/Infinity.
    encoded = json.dumps(bundle, ensure_ascii=False, allow_nan=False)
    if len(encoded.encode("utf-8")) > _MAX_CONFIG_BYTES:
        raise ValueError("설정 묶음이 허용 크기를 초과했습니다.")
    bundle = json.loads(encoded)
    machine, process, filaments = bundle.get("machine"), bundle.get("process"), bundle.get("filaments")
    if not isinstance(machine, dict) or not isinstance(process, dict) or not isinstance(filaments, list) or not 1 <= len(filaments) <= 16 or not all(isinstance(f, dict) for f in filaments):
        raise ValueError("machine, process와 1~16개의 filament full config가 필요합니다.")
    _reject_indirect_execution(bundle)
    _required(machine, _MACHINE_FIELDS, "machine")
    _required(process, _PROCESS_FIELDS, "process")
    expected = {"printer_settings_id": _identity(machine, "printer_settings_id"),
                "print_settings_id": _identity(process, "print_settings_id")}
    if not isinstance(machine["printer_model"], str) or machine["printer_technology"] != "FFF":
        raise ValueError("명시적인 FFF printer_model 설정이 필요합니다.")
    for key in ("machine_start_gcode", "machine_end_gcode"):
        if not isinstance(machine[key], str):
            raise ValueError(f"machine.{key}는 사용자 내보내기 문자열이어야 합니다.")
    _numeric(machine["nozzle_diameter"], "nozzle_diameter")
    _numeric(machine["printable_height"], "printable_height")
    area = machine["printable_area"]
    if not isinstance(area, list) or not 3 <= len(area) <= 128:
        raise ValueError("printable_area의 유효한 경계점이 필요합니다.")
    points = []
    for vertex in area:
        parts = re.split(r"[x,]", vertex) if isinstance(vertex, str) else []
        if len(parts) != 2:
            raise ValueError("printable_area 경계점 형식이 잘못되었습니다.")
        try:
            point = tuple(float(part) for part in parts)
        except ValueError:
            raise ValueError("printable_area 경계점은 유한 숫자여야 합니다.") from None
        if not all(math.isfinite(number) for number in point):
            raise ValueError("printable_area 경계점은 유한 숫자여야 합니다.")
        points.append(point)
    twice_area = sum(x * points[(index + 1) % len(points)][1] - y * points[(index + 1) % len(points)][0] for index, (x, y) in enumerate(points))
    if abs(twice_area) <= 0:
        raise ValueError("printable_area의 면적이 0입니다.")
    for key in _PROCESS_FIELDS:
        if key == "sparse_infill_density":
            value = str(process[key]).removesuffix("%")
            _numeric(value, key, inclusive=True)
            if float(value) > 100:
                raise ValueError("sparse_infill_density는 0~100%여야 합니다.")
        else:
            shell = key in ("wall_loops", "top_shell_layers", "bottom_shell_layers")
            _numeric(process[key], key, inclusive=shell, integer=shell)
    common_bed_fields = []
    for prefix in _BED_PREFIXES:
        pair = (prefix + "_temp", prefix + "_temp_initial_layer")
        if all(all(key in filament for key in pair) for filament in filaments):
            common_bed_fields.extend(pair)
    if not common_bed_fields:
        raise ValueError("모든 필라멘트에 공통으로 포함된 베드 온도/첫 레이어 온도 설정이 필요합니다.")
    for filament in filaments:
        _required(filament, _FILAMENT_FIELDS, "filament")
        _identity(filament, "filament_settings_id")
        material = filament["filament_type"]
        materials = material if isinstance(material, list) else [material]
        if not materials or not all(isinstance(value, str) and value.strip() for value in materials):
            raise ValueError("filament_type에 재료 정보가 필요합니다.")
        for key in _FILAMENT_FIELDS[1:]:
            _numeric(filament[key], key)
        for key in common_bed_fields:
            _numeric(filament[key], key, inclusive=True)
    expected.update({key: machine[key] for key in _MACHINE_FIELDS})
    expected.update({key: process[key] for key in _PROCESS_FIELDS})
    expected["filament_settings_id"] = [_identity(f, "filament_settings_id") for f in filaments]
    for key in (*_FILAMENT_FIELDS, *common_bed_fields):
        # Multi-variant arrays are retained; unfamiliar output mapping becomes needs_review.
        expected[key] = [_scalar(f[key]) for f in filaments]
    return {"bundle": bundle, "expected": expected}


def _hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _inspect_archive(path: Path, require_gcode: bool) -> tuple[dict | None, int]:
    with zipfile.ZipFile(path) as archive:
        entries = archive.infolist()
        if not entries or len(entries) > _MAX_ARCHIVE_ENTRIES:
            raise ValueError("3MF ZIP 항목 수가 허용 범위를 벗어났습니다.")
        total = 0
        names = set()
        gcodes = []
        for entry in entries:
            name = entry.filename.replace("\\", "/")
            pure = PurePosixPath(name)
            if "\\" in entry.filename or pure.is_absolute() or ".." in pure.parts or ":" in name or "\x00" in name or name in names or stat.S_ISLNK(entry.external_attr >> 16):
                raise ValueError("3MF에 안전하지 않거나 중복된 ZIP 경로가 있습니다.")
            names.add(name)
            total += entry.file_size
            if entry.file_size > _MAX_MEMBER_BYTES or total > _MAX_ARCHIVE_BYTES or entry.flag_bits & 1:
                raise ValueError("3MF 압축 해제 크기 또는 암호화 항목이 허용 범위를 벗어났습니다.")
            if re.fullmatch(r"Metadata/plate_[1-9][0-9]*\.gcode", name) and entry.file_size > 0:
                gcodes.append(entry)
        if "[Content_Types].xml" not in names:
            raise ValueError("3MF 컨테이너 메타데이터가 없습니다.")
        if require_gcode and not gcodes:
            raise ValueError("비어 있지 않은 Metadata/plate_*.gcode가 없습니다.")
        if archive.testzip() is not None:
            raise ValueError("3MF ZIP 무결성 검사가 실패했습니다.")
        settings = None
        config_name = "Metadata/project_settings.config"
        if config_name in names:
            info = archive.getinfo(config_name)
            if info.file_size > _MAX_CONFIG_BYTES:
                raise ValueError("프로젝트 설정이 허용 크기를 초과했습니다.")
            try:
                parsed = json.loads(archive.read(info))
                settings = parsed if isinstance(parsed, dict) else None
            except (ValueError, UnicodeError):
                settings = None
        return settings, len(gcodes)


def _build_argv(executable: str, job_dir: Path, input_path: Path, output: Path, filament_count: int) -> list[str]:
    config = job_dir / "config"
    return [executable, "--load-settings", f"{config / 'machine.json'};{config / 'process.json'}",
            "--load-filaments", ";".join(str(config / f"filament-{index + 1}.json") for index in range(filament_count)),
            "--slice", "0", "--outputdir", str(job_dir), "--export-3mf", str(output), str(input_path)]


def prepare_slice(input_path: Path, job_dir: Path, config_bundle: dict, executable_path: str | None = None) -> dict:
    """Stage immutable inputs and a fixed argv plan. Does not launch Studio."""
    plan = {"ready": False, "argv": [], "output_path": None, "job_dir": str(job_dir),
            "expected_settings": {}, "diagnostics": []}
    try:
        source = Path(input_path).expanduser().resolve(strict=True)
        job_dir = Path(job_dir).expanduser().resolve()
        plan["job_dir"] = str(job_dir)
        if ";" in str(job_dir):
            raise ValueError("작업 경로에 CLI 설정 구분자인 ';'를 사용할 수 없습니다. 다른 작업 경로를 선택하세요.")
        if source.suffix.lower() not in (".stl", ".3mf") or not source.is_file() or not 0 < source.stat().st_size <= _MAX_ARCHIVE_BYTES:
            raise ValueError("허용 크기 이내의 비어 있지 않은 STL 또는 3MF 파일이 필요합니다.")
        validated = _validate_bundle(config_bundle)
        if source.suffix.lower() == ".3mf":
            input_settings, _ = _inspect_archive(source, require_gcode=False)
            if input_settings:
                # Source projects may contain host scripts; never allow execution via import.
                for key in ("post_process", "post_process_script", "post_process_scripts"):
                    if _meaningful(input_settings.get(key)):
                        raise ValueError("입력 프로젝트의 호스트 후처리 프로그램 실행은 지원하지 않습니다.")
        environment = detect_environment() if executable_path is None else None
        supplied_path = executable_path if executable_path is not None else environment["path"]
        if not supplied_path:
            plan["diagnostics"].extend(environment["diagnostics"])
            return plan
        executable = Path(supplied_path).expanduser().resolve()
        if not _executable(executable):
            raise ValueError("Bambu Studio 실행 파일이 없거나 실행 권한이 없습니다.")
        job_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        config_dir = job_dir / "config"
        input_dir = job_dir / "input"
        if config_dir.exists() or input_dir.exists():
            raise ValueError("기존 준비 파일을 덮어쓸 수 없습니다. 새 작업 디렉터리가 필요합니다.")
        config_dir.mkdir(mode=0o700)
        input_dir.mkdir(mode=0o700)
        bundle = validated["bundle"]
        profiles = [("machine.json", bundle["machine"]), ("process.json", bundle["process"])]
        profiles.extend((f"filament-{index + 1}.json", item) for index, item in enumerate(bundle["filaments"]))
        fingerprints = {}
        for filename, profile in profiles:
            path = config_dir / filename
            with path.open("x", encoding="utf-8") as handle:
                json.dump(profile, handle, ensure_ascii=False, allow_nan=False, indent=2)
            fingerprints[str(path)] = _hash(path)
        staged_input = input_dir / ("model" + source.suffix.lower())
        with source.open("rb") as reader, staged_input.open("xb") as writer:
            shutil.copyfileobj(reader, writer)
        fingerprints[str(staged_input)] = _hash(staged_input)
        output = job_dir / f"sliced-{uuid.uuid4().hex}.gcode.3mf"
        plan.update(ready=True, executable_path=str(executable), input_path=str(staged_input),
                    filament_count=len(bundle["filaments"]), output_path=str(output),
                    expected_settings=validated["expected"], file_hashes=fingerprints,
                    argv=_build_argv(str(executable), job_dir, staged_input, output, len(bundle["filaments"])))
        plan["diagnostics"].append("최소 full-config 항목을 확인했습니다. 전체 Bambu 스키마·물리 출력 검증은 아니며 CLI 기능 확인은 실행 시 수행합니다.")
        return plan
    except (OSError, ValueError, TypeError, RecursionError, zipfile.BadZipFile, RuntimeError) as exc:
        plan["diagnostics"].append(str(exc))
        return plan


def _check(name: str, passed: bool, detail: str) -> dict:
    return {"name": name, "passed": passed, "detail": detail}


def _result(status="blocked", **values) -> dict:
    result = {"status": status, "exit_code": None, "output_path": None, "stdout": "", "stderr": "",
              "checks": [], "estimated_time_seconds": None, "filament_grams": None,
              "printer_status": "not_checked", "print_status": "not_started"}
    result.update(values)
    return result


def _validate_plan(plan: dict) -> tuple[Path, Path, Path]:
    job_dir = Path(plan["job_dir"]).resolve(strict=True)
    executable = Path(plan["executable_path"]).resolve(strict=True)
    source = Path(plan["input_path"]).resolve(strict=True)
    output = Path(plan["output_path"])
    if not output.is_absolute() or output.parent.resolve() != job_dir or output.exists() or output.is_symlink():
        raise ValueError("출력 파일은 작업 디렉터리의 새 파일이어야 합니다.")
    if not _executable(executable) or not source.is_relative_to(job_dir / "input") or not 1 <= plan["filament_count"] <= 16:
        raise ValueError("실행 계획의 경로나 필라멘트 개수가 유효하지 않습니다.")
    expected_argv = _build_argv(str(executable), job_dir, source, output, plan["filament_count"])
    if plan["argv"] != expected_argv:
        raise ValueError("실행 계획의 CLI 인자가 변경되었습니다. 다시 준비하세요.")
    required_files = [job_dir / "config/machine.json", job_dir / "config/process.json", source]
    required_files.extend(job_dir / f"config/filament-{index + 1}.json" for index in range(plan["filament_count"]))
    for path in required_files:
        if path.is_symlink() or path.resolve().parent not in (job_dir / "config", job_dir / "input") or plan["file_hashes"].get(str(path)) != _hash(path):
            raise ValueError("준비 후 입력 또는 설정 파일이 변경되었습니다. 다시 준비하세요.")
    if not isinstance(plan["expected_settings"], dict) or not plan["expected_settings"]:
        raise ValueError("검증할 설정이 없는 실행 계획입니다.")
    return job_dir, executable, output


def _equivalent(expected, actual) -> bool:
    if isinstance(expected, list):
        return isinstance(actual, list) and len(expected) == len(actual) and all(_equivalent(a, b) for a, b in zip(expected, actual))
    if isinstance(actual, list):
        return len(actual) == 1 and _equivalent(expected, actual[0])
    if isinstance(expected, bool) or isinstance(actual, bool):
        return type(expected) is type(actual) and expected == actual
    try:
        first, second = float(expected), float(actual)
        return math.isfinite(first) and math.isfinite(second) and math.isclose(first, second, rel_tol=1e-9, abs_tol=1e-9)
    except (TypeError, ValueError):
        return expected == actual


def execute_slice(plan: dict, timeout_seconds: int = 180) -> dict:
    """Execute a prepared local slice and verify its artifact. Never dispatch it."""
    if not isinstance(plan, dict) or not plan.get("ready"):
        detail = "; ".join(str(item) for item in plan.get("diagnostics", [])) if isinstance(plan, dict) else "잘못된 실행 계획입니다."
        return _result(checks=[_check("prepared", False, detail or "준비된 실행 계획이 없습니다.")])
    try:
        if isinstance(timeout_seconds, bool) or not isinstance(timeout_seconds, (int, float)) or not math.isfinite(timeout_seconds) or timeout_seconds <= 0:
            raise ValueError("timeout_seconds는 0보다 큰 유한 숫자여야 합니다.")
        job_dir, executable, output = _validate_plan(plan)
        probe = _probe_cli(executable, timeout_seconds)
        if not probe["supported"]:
            return _result(checks=[_check("cli_capabilities", False, "; ".join(probe["diagnostics"]))])
    except (OSError, ValueError, TypeError, KeyError) as exc:
        return _result(checks=[_check("prepared", False, str(exc))])
    try:
        completed = subprocess.run(
            list(plan["argv"]), cwd=str(job_dir), shell=False, stdin=subprocess.DEVNULL,
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=timeout_seconds, check=False,
        )
    except subprocess.TimeoutExpired as exc:
        return _result("timed_out", stdout=_text(exc.stdout), stderr=_text(exc.stderr),
                       checks=[_check("process", False, "슬라이싱 제한시간을 초과했습니다. 출력은 검증되지 않았습니다.")])
    except OSError as exc:
        return _result("failed", stderr=str(exc), checks=[_check("process", False, str(exc))])
    result = _result("failed", exit_code=completed.returncode, stdout=_text(completed.stdout), stderr=_text(completed.stderr))
    result["checks"].append(_check("process", completed.returncode == 0, f"CLI exit code: {completed.returncode}"))
    if completed.returncode != 0:
        return result
    try:
        if output.is_symlink() or not output.is_file() or not 0 < output.stat().st_size <= _MAX_ARCHIVE_BYTES:
            raise ValueError("이번 작업의 비어 있지 않은 출력 3MF를 확인하지 못했습니다.")
        settings, plate_count = _inspect_archive(output, require_gcode=True)
        result["checks"].append(_check("sliced_archive", True, f"ZIP 무결성과 {plate_count}개 G-code 파일을 확인했습니다."))
    except (OSError, ValueError, RuntimeError, zipfile.BadZipFile, NotImplementedError) as exc:
        result["checks"].append(_check("sliced_archive", False, str(exc)))
        return result
    result["output_path"] = str(output)
    if settings is None:
        result["checks"].append(_check("project_settings", False, "핵심 프로젝트 설정을 다시 읽을 수 없어 검토가 필요합니다."))
    else:
        for key, expected in plan["expected_settings"].items():
            present = key in settings
            equal = present and _equivalent(expected, settings[key])
            detail = "요청값과 일치합니다." if equal else ("출력 설정이 요청값과 다릅니다." if present else "출력에서 이 설정을 확인할 수 없습니다.")
            result["checks"].append(_check(f"setting:{key}", equal, detail))
    result["status"] = "sliced" if all(check["passed"] for check in result["checks"]) else "needs_review"
    return result
