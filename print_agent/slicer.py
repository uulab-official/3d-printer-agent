"""Prepare and verify local Bambu Studio CLI jobs; never control a printer.

Supported validation is a minimum, not a universal Bambu full-config schema:
machine identity/FFF/bed geometry/nozzle/start/end G-code; process identity,
layer heights, shells, infill and four speeds; filament identity, material,
diameter/density/flow/MVS, nozzle temperatures and the selected plate's temperatures.
Native profile metadata and JSON string representations are required; the explicit
plate selection and read-back expectations are bound to the staged configuration.
The lineage-free path requires a system root machine and a process with that exact
machine name in compatible_printers; user machine lineage is not resolved here.
Unresolved inheritance, nonfinite numbers and host post-processing are rejected.
The role-bundle path compares those core settings. A separate Studio-project
path copies exact recorded snapshot bytes into current generated CAD and reports
every native roundtrip difference. Only observed arrange-coordinate changes and
an added empty compatibility list are accepted normalization; other differences
require review. Native qualification is version/fixture-specific, and physical
printing remains unqualified. No numeric print presets are supplied here.
Statistics remain null until a versioned parser is validated.

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
import xml.etree.ElementTree as ET
import zipfile

from . import studio_project


_REQUIRED_OPTIONS = ("--load-settings", "--load-filaments", "--slice", "--outputdir", "--export-3mf")
_PROJECT_REQUIRED_OPTIONS = ("--arrange", "--slice", "--export-3mf")
_CORE_3MF = "http://schemas.microsoft.com/3dmanufacturing/core/2015/02"
_PRODUCTION_3MF = "http://schemas.microsoft.com/3dmanufacturing/production/2015/06"
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
_PLATE_BED_PREFIXES = {
    "Cool Plate": "cool_plate",
    "Engineering Plate": "eng_plate",
    "High Temp Plate": "hot_plate",
    "Textured PEI Plate": "textured_plate",
    "Supertack Plate": "supertack_plate",
}
_NATIVE_METADATA_FIELDS = frozenset({
    "version", "name", "url", "type", "setting_id", "filament_id", "from",
    "description", "instantiation", "is_custom",
})
_MAX_ARCHIVE_ENTRIES = 2048
_MAX_ARCHIVE_BYTES = 512 * 1024 * 1024
_MAX_MEMBER_BYTES = 256 * 1024 * 1024
_MAX_CONFIG_BYTES = 8 * 1024 * 1024
_MAX_SETTINGS_DEPTH = 32
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


def _probe_cli(path: Path, timeout_seconds: float, required_options: tuple = _REQUIRED_OPTIONS) -> dict:
    key = _fingerprint(path)
    if required_options != _REQUIRED_OPTIONS:
        key += (required_options,)
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
            result["capabilities"] = [option for option in required_options
                                      if re.search(r"(?<![\w-])" + re.escape(option) + r"(?![\w-])", output)]
            match = re.search(r"Bambu\s*Studio(?:\s+version)?[\s:\-]*(\d+\.\d+\.\d+(?:\.\d+)?)", output, re.I)
            result["version"] = match.group(1) if match else None
            result["supported"] = completed.returncode == 0 and len(result["capabilities"]) == len(required_options)
            if not result["supported"]:
                result["diagnostics"].append("--help 응답에서 필요한 Bambu CLI 기능을 확인하지 못했습니다.")
            if completed.returncode != 0:
                stderr = _text(completed.stderr).strip()
                if len(stderr) > 2000:
                    stderr = stderr[:2000] + "\n[stderr truncated]"
                result["diagnostics"].append(f"--help 종료 코드: {completed.returncode}" + (f"\n{stderr}" if stderr else ""))
        except subprocess.TimeoutExpired:
            result["diagnostics"].append("Bambu Studio --help 확인이 제한시간을 초과했습니다. 슬라이싱은 실행하지 않았습니다.")
        except OSError as exc:
            result["diagnostics"].append(f"Bambu Studio 실행 실패: {exc}")
        _PROBE_CACHE[key] = result
        return result


def probe_environment(timeout: int = 3) -> dict:
    """Explicitly probe an installed CLI; ordinary discovery remains file-only."""
    environment = detect_environment()
    environment["cli_supported"] = False
    if not environment["available"]:
        return environment
    try:
        probe = _probe_cli(Path(environment["path"]), timeout)
        environment.update(cli_supported=probe["supported"], version=probe["version"],
                           capabilities=list(probe["capabilities"]), diagnostics=list(probe["diagnostics"]))
        if probe["supported"]:
            environment["diagnostics"].append("--help에서 필요한 CLI 기능을 확인했습니다. 슬라이싱과 프린터 연결은 별도로 확인해야 합니다.")
    except (OSError, ValueError, TypeError) as exc:
        environment["diagnostics"].append(f"Bambu Studio CLI 확인 실패: {exc}")
    return environment


def _meaningful(value) -> bool:
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, list):
        return any(_meaningful(item) for item in value)
    return value is not None and value is not False and value != {}


def _reject_indirect_execution(value, location="config") -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            if key in ("inherits", "include", "includes") and _meaningful(item):
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
    name = config.get("name")
    if not isinstance(name, str) or not name.strip():
        raise ValueError(f"name에 비어 있지 않은 native full config 이름이 필요합니다 ({key}).")
    supplied = _scalar(config.get(key))
    if _meaningful(supplied) and supplied != name:
        raise ValueError(f"{key}가 name과 다릅니다. Bambu CLI는 name으로 식별자를 설정하므로 원본 full config의 두 값을 확인하세요.")
    return name


def _native_profile(config: dict, role: str, label: str) -> None:
    """Check native JSON representation without filling defaults or variants."""
    for key, value in config.items():
        if key.casefold() in _NATIVE_METADATA_FIELDS:
            valid = isinstance(value, str)
        else:
            # Native ConfigBase accepts strings or uniform arrays of strings,
            # including two-dimensional string arrays. Preserve those as supplied.
            valid = isinstance(value, str) or (isinstance(value, list) and (
                all(isinstance(item, str) for item in value) or
                all(isinstance(item, list) and all(isinstance(part, str) for part in item) for item in value)
            ))
        if not valid:
            raise ValueError(f"{label}.{key}: native 설정은 문자열 또는 문자열 배열이어야 하며 메타데이터는 문자열이어야 합니다. 원본 내보내기 형식을 확인하세요.")
    if not isinstance(config.get("name"), str) or not config["name"].strip():
        raise ValueError(f"{label}.name: 비어 있지 않은 native full config 이름이 필요합니다.")
    if config.get("type") != role:
        raise ValueError(f"{label}.type: native 설정의 type은 '{role}'이어야 합니다.")
    if config.get("from") not in ("system", "User", "user"):
        raise ValueError(f"{label}.from: native 설정의 from은 system, User 또는 user여야 합니다.")


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
    plate_type = bundle.get("plate_type")
    if not isinstance(plate_type, str) or plate_type not in _PLATE_BED_PREFIXES:
        raise ValueError("plate_type에 사용할 플레이트를 명시하세요: " + ", ".join(_PLATE_BED_PREFIXES))
    _reject_indirect_execution(bundle)
    _native_profile(machine, "machine", "machine")
    if machine["from"] != "system":
        raise ValueError("machine.from: 현재는 from='system'인 상속 없는 루트 machine 전체 설정만 지원합니다. User/user 프린터는 inherits의 시스템 계보 해석이 필요하지만 아직 지원하지 않습니다. 원본 from을 변경하지 말고 해당 장비의 루트 전체 설정을 제공하세요.")
    _native_profile(process, "process", "process")
    compatible_printers = process.get("compatible_printers")
    if not isinstance(compatible_printers, list) or not compatible_printers or not all(isinstance(name, str) and name.strip() for name in compatible_printers):
        raise ValueError("process.compatible_printers: 비어 있지 않은 프린터 이름의 문자열 배열이 필요합니다. 원본 전체 설정의 호환 목록을 확인하세요.")
    if machine["name"] not in compatible_printers:
        raise ValueError(f"process.compatible_printers에 machine.name '{machine['name']}'과 정확히 같은 이름이 필요합니다. 해당 프린터와 호환되는 원본 process 전체 설정을 제공하세요.")
    for index, filament in enumerate(filaments):
        _native_profile(filament, "filament", f"filaments[{index}]")
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
    selected_prefix = _PLATE_BED_PREFIXES[plate_type]
    selected_bed_fields = (selected_prefix + "_temp", selected_prefix + "_temp_initial_layer")
    for index, filament in enumerate(filaments):
        _required(filament, selected_bed_fields, f"filaments[{index}]")
    common_bed_fields = []
    for prefix in _PLATE_BED_PREFIXES.values():
        pair = (prefix + "_temp", prefix + "_temp_initial_layer")
        if all(all(key in filament for key in pair) for filament in filaments):
            common_bed_fields.extend(pair)
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
            # Native Print::validate treats zero for the selected bed as an
            # unsupported filament/plate combination. Other plates may retain it.
            _numeric(filament[key], key, inclusive=key not in selected_bed_fields)
    expected.update({key: machine[key] for key in _MACHINE_FIELDS})
    expected.update({key: process[key] for key in _PROCESS_FIELDS})
    expected["curr_bed_type"] = plate_type
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


def _validate_settings_depth(settings: dict) -> None:
    """Bound decoded project metadata before any recursive value inspection."""
    pending = [(settings, 1)]
    while pending:
        value, depth = pending.pop()
        if depth > _MAX_SETTINGS_DEPTH:
            raise ValueError(f"프로젝트 설정 JSON의 중첩 깊이는 {_MAX_SETTINGS_DEPTH} 이하여야 합니다.")
        children = value.values() if isinstance(value, dict) else value
        pending.extend((child, depth + 1) for child in children if isinstance(child, (dict, list)))


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
                if not isinstance(parsed, dict):
                    raise ValueError("프로젝트 설정은 JSON 객체여야 합니다.")
                _validate_settings_depth(parsed)
                settings = parsed
            except (ValueError, UnicodeError, RecursionError) as exc:
                if not require_gcode:
                    raise ValueError(f"입력 3MF의 {config_name}을 검사할 수 없습니다. 읽을 수 있는 프로젝트 설정으로 다시 내보내세요: {exc}") from None
                settings = None
        return settings, len(gcodes)


def _build_argv(executable: str, job_dir: Path, input_path: Path, output: Path, filament_count: int, plate_type: str) -> list[str]:
    config = job_dir / "config"
    return [executable, "--load-settings", f"{config / 'machine.json'};{config / 'process.json'}",
            "--load-filaments", ";".join(str(config / f"filament-{index + 1}.json") for index in range(filament_count)),
            "--curr-bed-type", plate_type, "--slice", "0", "--outputdir", str(job_dir),
            "--export-3mf", output.name, str(input_path)]


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
        profiles.append(("selection.json", {"source": bundle["source"], "plate_type": bundle["plate_type"]}))
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
                    plate_type=bundle["plate_type"], expected_settings=validated["expected"], file_hashes=fingerprints,
                    argv=_build_argv(str(executable), job_dir, staged_input, output, len(bundle["filaments"]), bundle["plate_type"]))
        plan["diagnostics"].append("최소 full-config 항목을 확인했습니다. 전체 Bambu 스키마·물리 출력 검증은 아니며 CLI 기능 확인은 실행 시 수행합니다.")
        return plan
    except (OSError, ValueError, TypeError, RecursionError, zipfile.BadZipFile, RuntimeError) as exc:
        plan["diagnostics"].append(str(exc))
        return plan


def _project_argv(executable: str, project: Path, output: Path) -> list[str]:
    return [executable, "--arrange", "1", "--slice", "0", "--export-3mf", output.name, str(project)]


def _project_public_source(snapshot: dict, source_id: str | None) -> dict:
    public = studio_project.public_snapshot(snapshot)
    if source_id is not None:
        if not isinstance(source_id, str) or not re.fullmatch(r"[0-9a-f]{32}", source_id):
            raise ValueError("서버가 저장한 Studio 원본 ID가 필요합니다.")
        public.update(source_id=source_id, archive_url=f"/api/studio-projects/{source_id}/archive")
    return public


def _project_read_file(path: Path, maximum: int) -> bytes:
    if path.is_symlink() or not path.is_file() or not 0 < path.stat().st_size <= maximum:
        raise ValueError("준비 파일이 없거나 링크·빈 파일·허용 크기 밖의 파일입니다.")
    with path.open("rb") as handle:
        content = handle.read(maximum + 1)
    if not 0 < len(content) <= maximum:
        raise ValueError("준비 파일의 실제 바이트가 허용 크기를 벗어났습니다.")
    return content


def prepare_project_slice(input_path: Path, job_dir: Path, source_filename: str, source_content: bytes, *,
                          source_id: str | None = None, executable_path: str | None = None) -> dict:
    """Compose current generated CAD with an immutable recorded Studio snapshot.

    Composition requires no executable. The separate ready flag only permits a
    later native attempt; the exact runtime/options are checked at execution.
    Source bytes are inspected here, never accepted as a client-derived snapshot.
    """
    plan = {"kind": "studio_project", "ready": False, "project_prepared": False,
            "project_path": None, "project_sha256": None, "project_receipt": None,
            "project_source": None, "argv": [], "output_path": None,
            "job_dir": str(job_dir), "expected_settings": {}, "diagnostics": []}
    created_project = None
    try:
        snapshot = studio_project.inspect_studio_project(source_filename, source_content)
        public_source = _project_public_source(snapshot, source_id)
        plan["project_source"] = public_source
        if not snapshot["supported"]:
            plan["diagnostics"].extend(issue["message"] for issue in snapshot["issues"])
            return plan
        original_model = Path(input_path).expanduser()
        if original_model.is_symlink() or original_model.suffix.lower() != ".3mf":
            raise ValueError("앱에서 생성한 원본 3MF 파일이 필요합니다.")
        model = original_model.resolve(strict=True)
        model_bytes = _project_read_file(model, studio_project.MAX_ARCHIVE_BYTES)
        derived, receipt = studio_project.build_project_3mf(model_bytes, snapshot)
        requested_job = Path(job_dir).expanduser()
        if requested_job.is_symlink():
            raise ValueError("준비 작업 폴더는 링크일 수 없습니다.")
        job_dir = requested_job.resolve()
        plan["job_dir"] = str(job_dir)
        # A caller supplies a new server-owned attempt directory. Existing
        # destinations are never reused, even if a previous attempt was partial.
        job_dir.mkdir(parents=True, exist_ok=False, mode=0o700)
        input_dir = job_dir / "input"
        input_dir.mkdir(mode=0o700)
        staged_source, staged_model = input_dir / "source.3mf", input_dir / "model.3mf"
        project = job_dir / "prepared-project.3mf"
        receipt_path, preparation_path = job_dir / "preparation-receipt.json", job_dir / "preparation.json"
        output = job_dir / f"sliced-{uuid.uuid4().hex}.gcode.3mf"
        environment = detect_environment() if executable_path is None else None
        supplied = executable_path if executable_path is not None else environment["path"]
        executable = Path(supplied).expanduser().resolve() if supplied else None
        executable_available = executable is not None and _executable(executable)
        preparation = {"schema_version": 1, "kind": "studio_project", "source_filename": source_filename,
                       "source_id": source_id, "source_sha256": snapshot["source"]["sha256"],
                       "model_sha256": receipt["model_sha256"], "project_sha256": receipt["project_sha256"],
                       "output_name": output.name, "native_version": studio_project.QUALIFIED_VERSION,
                       "executable_path": str(executable) if executable_available else None,
                       "executable_sha256": _hash(executable) if executable_available else None}
        payload = {staged_source: source_content, staged_model: model_bytes,
                   receipt_path: (json.dumps(receipt, ensure_ascii=False, allow_nan=False, sort_keys=True, indent=2) + "\n").encode(),
                   preparation_path: (json.dumps(preparation, ensure_ascii=False, allow_nan=False, sort_keys=True, indent=2) + "\n").encode()}
        fingerprints = {}
        for path, content in payload.items():
            with path.open("xb") as handle:
                handle.write(content)
            fingerprints[str(path)] = _hash(path)
        # Publish the complete project only after its source/receipt records.
        # An interrupted write is not returned as a prepared artifact.
        with project.open("xb") as handle:
            created_project = project
            handle.write(derived)
        if _hash(project) != receipt["project_sha256"] or project.stat().st_size != receipt["project_bytes"]:
            raise ValueError("준비 프로젝트의 기록과 저장 바이트가 다릅니다.")
        fingerprints[str(project)] = receipt["project_sha256"]
        plan.update(project_prepared=True, project_path=str(project), project_sha256=receipt["project_sha256"],
                    project_receipt=receipt, expected_settings=snapshot["expected_settings"], file_hashes=fingerprints,
                    input_path=str(staged_model), source_path=str(staged_source), output_path=str(output),
                    plate_type=snapshot["summary"]["plate_type"], filament_count=1)
        plan["diagnostics"].extend(snapshot["warnings"])
        if executable_available:
            plan.update(ready=True, executable_path=str(executable), argv=_project_argv(str(executable), project, output))
            plan["diagnostics"].append(f"프로젝트 파일을 준비했습니다. 실행 시 Studio {studio_project.QUALIFIED_VERSION}과 CLI 기능을 확인합니다.")
        else:
            plan["diagnostics"].extend(environment["diagnostics"] if environment is not None else ["Bambu Studio 실행 파일이 없거나 실행 권한이 없습니다."])
            plan["diagnostics"].append("준비한 프로젝트는 다운로드할 수 있습니다. native 슬라이싱은 실행하지 않았습니다.")
        return plan
    except (OSError, ValueError, TypeError, KeyError, RecursionError, RuntimeError, zipfile.BadZipFile) as exc:
        if created_project is not None and not plan["project_prepared"]:
            try:
                created_project.unlink()
            except OSError:
                pass
        plan["diagnostics"].append(str(exc))
        return plan


def _validate_project_plan(plan: dict) -> tuple[Path, Path, Path, dict, list[str], dict]:
    if plan.get("kind") != "studio_project" or plan.get("project_prepared") is not True or plan.get("ready") is not True:
        raise ValueError("완전히 준비한 Studio 프로젝트 실행 계획이 필요합니다.")
    job_dir = Path(plan["job_dir"])
    if not job_dir.is_absolute() or job_dir.is_symlink() or job_dir.resolve(strict=True) != job_dir:
        raise ValueError("준비 작업 폴더의 경로가 변경되었습니다.")
    project = job_dir / "prepared-project.3mf"
    source, model = job_dir / "input/source.3mf", job_dir / "input/model.3mf"
    receipt_path, preparation_path = job_dir / "preparation-receipt.json", job_dir / "preparation.json"
    paths = (source, model, receipt_path, preparation_path, project)
    if (Path(plan["project_path"]) != project or Path(plan["source_path"]) != source or Path(plan["input_path"]) != model
            or (job_dir / "input").is_symlink() or not isinstance(plan.get("file_hashes"), dict)
            or set(plan["file_hashes"]) != {str(path) for path in paths}):
        raise ValueError("준비 파일 목록이나 경로가 변경되었습니다.")
    payload = {}
    for path in paths:
        if path.resolve(strict=True) != path:
            raise ValueError("준비 파일 경로에 링크가 있습니다.")
        limit = studio_project.MAX_ARCHIVE_BYTES if path.suffix == ".3mf" else studio_project.MAX_SETTINGS_BYTES
        payload[path] = _project_read_file(path, limit)
        if hashlib.sha256(payload[path]).hexdigest() != plan["file_hashes"][str(path)]:
            raise ValueError("준비 후 입력 또는 프로젝트 파일이 변경되었습니다. 다시 준비하세요.")
    preparation = json.loads(payload[preparation_path])
    if (not isinstance(preparation, dict) or preparation.get("schema_version") != 1
            or preparation.get("kind") != "studio_project" or preparation.get("native_version") != studio_project.QUALIFIED_VERSION):
        raise ValueError("원본 준비 기록이 유효하지 않습니다.")
    snapshot = studio_project.inspect_studio_project(preparation["source_filename"], payload[source])
    if not snapshot["supported"]:
        raise ValueError("준비된 원본 프로젝트가 현재 지원 범위와 다릅니다.")
    derived, receipt = studio_project.build_project_3mf(payload[model], snapshot)
    if (payload[project] != derived or json.loads(payload[receipt_path]) != receipt or plan["project_receipt"] != receipt
            or plan["project_sha256"] != receipt["project_sha256"]
            or plan["expected_settings"] != snapshot["expected_settings"]
            or plan["project_source"] != _project_public_source(snapshot, preparation["source_id"])
            or preparation["source_sha256"] != snapshot["source"]["sha256"]
            or preparation["model_sha256"] != receipt["model_sha256"]
            or preparation["project_sha256"] != receipt["project_sha256"]
            or plan.get("plate_type") != snapshot["summary"]["plate_type"] or plan.get("filament_count") != 1):
        raise ValueError("원본·현재 CAD·설정·파생 프로젝트 기록이 실행 계획과 다릅니다. 다시 준비하세요.")
    executable = Path(plan["executable_path"])
    if (not executable.is_absolute() or executable.resolve(strict=True) != executable or not _executable(executable)
            or str(executable) != preparation["executable_path"] or _hash(executable) != preparation["executable_sha256"]):
        raise ValueError("준비한 Bambu Studio 실행 파일이 변경되었습니다.")
    output = Path(plan["output_path"])
    if (not re.fullmatch(r"sliced-[0-9a-f]{32}\.gcode\.3mf", preparation["output_name"])
            or output != job_dir / preparation["output_name"] or output.exists() or output.is_symlink()):
        raise ValueError("출력 파일은 준비한 작업 디렉터리의 새 파일이어야 합니다.")
    argv = _project_argv(str(executable), project, output)
    if plan["argv"] != argv:
        raise ValueError("실행 계획의 CLI 인자가 변경되었습니다. 다시 준비하세요.")
    return job_dir, executable, output, snapshot["expected_settings"], argv, snapshot


def _snapshot_readback(before_text: str, after: dict, after_bytes: bytes) -> dict:
    before = json.loads(before_text)
    added, removed = sorted(after.keys() - before.keys()), sorted(before.keys() - after.keys())
    changed = sorted(key for key in before.keys() & after.keys() if before[key] != after[key])

    def preview(value):
        text = json.dumps(value, ensure_ascii=False)
        return {"type": type(value).__name__, "json": text[:512], "truncated": len(text) > 512}

    differences = []
    for kind, keys in (("added", added), ("removed", removed), ("changed", changed)):
        for key in keys:
            qualified = kind == "added" and key == "upward_compatible_machine" and after[key] == []
            if kind == "changed" and key in ("wipe_tower_x", "wipe_tower_y"):
                old, new = before[key], after[key]
                qualified = (isinstance(old, list) and isinstance(new, list) and len(old) == len(new) == 1
                             and all(isinstance(item, str) for item in old + new))
                if qualified:
                    try:
                        qualified = all(math.isfinite(float(item)) for item in old + new)
                    except (ValueError, OverflowError):
                        qualified = False
            differences.append({"key": key, "kind": kind, "qualified_native_normalization": qualified,
                                "before": preview(before[key]) if key in before else None,
                                "after": preview(after[key]) if key in after else None})
    qualified_count = sum(item["qualified_native_normalization"] for item in differences)
    return {"before_key_count": len(before), "after_key_count": len(after),
            "unchanged_key_count": len(before.keys() & after.keys()) - len(changed),
            "added_key_count": len(added), "removed_key_count": len(removed), "changed_key_count": len(changed),
            "all_values_equal": before == after, "exact_bytes_equal": before_text.encode("utf-8") == after_bytes,
            "before_sha256": hashlib.sha256(before_text.encode("utf-8")).hexdigest(),
            "after_sha256": hashlib.sha256(after_bytes).hexdigest(), "difference_count": len(differences),
            "qualified_normalization_count": qualified_count, "unqualified_difference_count": len(differences) - qualified_count,
            "differences": differences[:100], "differences_truncated": len(differences) > 100}


def _project_output_settings(output: Path) -> tuple[dict | None, bytes | None]:
    """Require real movement and unambiguous finite JSON for this native path."""
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("출력 설정 JSON에 중복 키가 있습니다.")
            result[key] = value
        return result

    def constant(value):
        raise ValueError("출력 설정 JSON의 비유한 숫자를 허용하지 않습니다.")

    with zipfile.ZipFile(output) as archive:
        for info in archive.infolist():
            if re.fullmatch(r"Metadata/plate_[1-9][0-9]*\.gcode", info.filename):
                motion, tail, first_chunk = False, b"", True
                with archive.open(info) as stream:
                    while chunk := stream.read(65536):
                        # A retained tail can begin in the middle of a comment.
                        # Only the real file start or a newline starts a command.
                        sample = (b"" if first_chunk else b"x") + tail + chunk
                        motion = motion or re.search(rb"(?m)^\s*G[0123](?:\s|$)", sample) is not None
                        tail = sample[-64:]
                        first_chunk = False
                if not motion:
                    raise ValueError("출력 G-code에서 실제 이동 명령을 확인하지 못했습니다.")
        name = "Metadata/project_settings.config"
        if name not in archive.namelist():
            return None, None
        with archive.open(name) as stream:
            raw = stream.read(studio_project.MAX_SETTINGS_BYTES + 1)
        if len(raw) > studio_project.MAX_SETTINGS_BYTES:
            raise ValueError("출력 프로젝트 설정이 허용 크기를 초과했습니다.")
        try:
            settings = json.loads(raw.decode("utf-8"), object_pairs_hook=pairs, parse_constant=constant)
            if not isinstance(settings, dict):
                return None, raw
            _validate_settings_depth(settings)
            return settings, raw
        except (ValueError, UnicodeError, RecursionError):
            return None, raw


def _project_mesh(path: Path) -> tuple[list, list, list]:
    """Read one active mesh through bounded inline/native component references.

    The generated input has an inline wrapper; native exports put the part in
    another model member. Validate that the sole build instance reaches the sole
    mesh, rather than accepting an unused matching mesh elsewhere in the ZIP.
    Native arrange may translate and rotate the build on the XY plate, but it
    must not scale, shear, mirror, or tilt the geometry.
    """
    q = lambda name: f"{{{_CORE_3MF}}}{name}"
    documents, objects, mesh_keys = {}, {}, []
    with zipfile.ZipFile(path) as archive:
        members = [entry for entry in archive.infolist() if entry.filename.endswith(".model")]
        if not 1 <= len(members) <= 8:
            raise ValueError("출력 형상 검토는 제한된 단일 메시 프로젝트만 지원합니다.")
        for entry in members:
            if entry.file_size > studio_project.MAX_MODEL_XML_BYTES:
                raise ValueError("형상 XML 크기가 검토 한도를 초과했습니다.")
            with archive.open(entry) as stream:
                raw = stream.read(studio_project.MAX_MODEL_XML_BYTES + 1)
            if len(raw) > studio_project.MAX_MODEL_XML_BYTES:
                raise ValueError("형상 XML의 실제 바이트가 검토 한도를 초과했습니다.")
            text = raw.decode("utf-8")
            if re.search(r"<!\s*(?:DOCTYPE|ENTITY)\b", text, re.I):
                raise ValueError("형상 XML의 DTD·entity 선언은 지원하지 않습니다.")
            root = ET.fromstring(text)
            if root.tag != q("model") or root.get("unit", "millimeter") != "millimeter" or entry.filename in documents:
                raise ValueError("중복되지 않은 mm 단위 3MF 형상 XML이 필요합니다.")
            documents[entry.filename] = root
            for item in root.findall(q("resources") + "/" + q("object")):
                key = entry.filename, item.get("id")
                if not key[1] or key in objects or item.get("type", "model") != "model":
                    raise ValueError("형상 객체 식별자 또는 종류가 유효하지 않습니다.")
                objects[key] = item
                meshes = item.findall(q("mesh"))
                if len(meshes) > 1:
                    raise ValueError("출력에 여러 메시가 있어 현재 CAD 형상을 확인할 수 없습니다.")
                if meshes:
                    mesh_keys.append(key)
    if len(mesh_keys) != 1 or "3D/3dmodel.model" not in documents:
        raise ValueError("출력에서 정확히 하나의 현재 CAD 메시를 확인해야 합니다.")
    root = documents["3D/3dmodel.model"]
    builds = root.findall(q("build"))
    instances = builds[0].findall(q("item")) if len(builds) == 1 else []
    if len(instances) != 1 or instances[0].get("printable", "1") != "1":
        raise ValueError("출력에 출력 가능한 단일 build instance가 필요합니다.")
    placements = []

    def placement(element, *, build=False):
        values = [float(value) for value in element.get("transform", "1 0 0 0 1 0 0 0 1 0 0 0").split()]
        if len(values) != 12 or not all(math.isfinite(value) for value in values):
            raise ValueError("형상 배치 변환을 읽을 수 없습니다.")
        if build:
            a, b, c, d, e, f, g, h, i = values[:9]
            valid = (all(abs(value) <= 1e-6 for value in (c, f, g, h)) and abs(i - 1) <= 1e-6
                     and abs(a * a + b * b - 1) <= 1e-6 and abs(d * d + e * e - 1) <= 1e-6
                     and abs(a * d + b * e) <= 1e-6 and abs(a * e - b * d - 1) <= 1e-6)
        else:
            valid = all(abs(value - expected) <= 1e-6 for value, expected in zip(values[:9], (1, 0, 0, 0, 1, 0, 0, 0, 1)))
        if not valid:
            raise ValueError("형상 배치에 크기 변경·기울임·반전 또는 지원하지 않는 part 회전이 있습니다.")
        placements.append({"kind": "build" if build else "component", "transform": values})

    placement(instances[0], build=True)
    current = "3D/3dmodel.model", instances[0].get("objectid")
    visited = set()
    while True:
        if current not in objects or current in visited or len(visited) >= 8:
            raise ValueError("build instance의 형상 참조가 없거나 순환합니다.")
        visited.add(current)
        item = objects[current]
        mesh = item.find(q("mesh"))
        components = item.findall(q("components") + "/" + q("component"))
        if mesh is not None:
            if components or current != mesh_keys[0]:
                raise ValueError("출력의 실제 build 형상이 단일 현재 CAD 메시와 다릅니다.")
            break
        if len(components) != 1:
            raise ValueError("출력은 하나의 part를 가리키는 형상이어야 합니다.")
        component = components[0]
        placement(component)
        target = component.get(f"{{{_PRODUCTION_3MF}}}path")
        member = current[0] if not target else (target[1:] if target.startswith("/") else str(PurePosixPath(current[0]).parent / target))
        current = member, component.get("objectid")
    points = [tuple(float(vertex.attrib[key]) for key in ("x", "y", "z"))
              for vertex in mesh.findall(q("vertices") + "/" + q("vertex"))]
    faces = [tuple(int(face.attrib[key]) for key in ("v1", "v2", "v3"))
             for face in mesh.findall(q("triangles") + "/" + q("triangle"))]
    if (not points or not faces or any(not math.isfinite(value) for point in points for value in point)
            or any(index < 0 or index >= len(points) for face in faces for index in face)):
        raise ValueError("형상 메시의 꼭짓점 또는 삼각형 연결 정보가 유효하지 않습니다.")
    return points, faces, placements


def _project_geometry_readback(model: Path, output: Path) -> dict:
    expected_points, expected_faces, _ = _project_mesh(model)
    actual_points, actual_faces, placements = _project_mesh(output)
    expected_bounds = [[min(point[axis] for point in expected_points), max(point[axis] for point in expected_points)] for axis in range(3)]
    actual_bounds = [[min(point[axis] for point in actual_points), max(point[axis] for point in actual_points)] for axis in range(3)]
    same_counts = len(expected_points) == len(actual_points) and len(expected_faces) == len(actual_faces)
    maximum_error = max(abs((expected[axis] - expected_bounds[axis][0]) - (actual[axis] - actual_bounds[axis][0]))
                        for expected, actual in zip(expected_points, actual_points) for axis in range(3)) if same_counts else None
    topology = sorted(tuple(sorted(face)) for face in expected_faces) == sorted(tuple(sorted(face)) for face in actual_faces)
    return {"passed": same_counts and topology and maximum_error is not None and maximum_error <= 0.0001,
            "expected_vertices": len(expected_points), "actual_vertices": len(actual_points),
            "expected_triangles": len(expected_faces), "actual_triangles": len(actual_faces),
            "expected_dimensions_mm": [hi - lo for lo, hi in expected_bounds],
            "actual_dimensions_mm": [hi - lo for lo, hi in actual_bounds],
            "maximum_translated_vertex_error_mm": maximum_error, "triangle_connectivity_matches": topology,
            "placement_policy": "single active mesh; part translations; rigid XY plate rotation and translation",
            "placements": placements}


def _execute_project_slice(plan: dict, timeout_seconds: int) -> dict:
    try:
        if isinstance(timeout_seconds, bool) or not isinstance(timeout_seconds, (int, float)) or not math.isfinite(timeout_seconds) or timeout_seconds <= 0:
            raise ValueError("timeout_seconds는 0보다 큰 유한 숫자여야 합니다.")
        job_dir, executable, output, expected, argv, snapshot = _validate_project_plan(plan)
        probe = _probe_cli(executable, timeout_seconds, _PROJECT_REQUIRED_OPTIONS)
        if not probe["supported"]:
            return _result(bambu_version=probe["version"], checks=[_check("cli_capabilities", False, "; ".join(probe["diagnostics"]))])
        if probe["version"] != studio_project.QUALIFIED_VERSION:
            return _result(bambu_version=probe["version"], checks=[_check("qualified_version", False,
                f"이 프로젝트 경로는 Studio {studio_project.QUALIFIED_VERSION}에서 검증했습니다. 설치 버전: {probe['version'] or '확인 불가'}")])
        # A first help probe can take time; re-check the staged files and binary
        # before launching the actual slice rather than trusting an earlier hash.
        job_dir, executable, output, expected, argv, snapshot = _validate_project_plan(plan)
    except (OSError, ValueError, TypeError, KeyError, RecursionError, RuntimeError, zipfile.BadZipFile) as exc:
        return _result(checks=[_check("prepared", False, str(exc))])
    try:
        completed = subprocess.run(argv, cwd=str(job_dir), shell=False, stdin=subprocess.DEVNULL,
                                   capture_output=True, text=True, encoding="utf-8", errors="replace",
                                   timeout=timeout_seconds, check=False)
    except subprocess.TimeoutExpired as exc:
        return _result("timed_out", bambu_version=probe["version"], stdout=_text(exc.stdout), stderr=_text(exc.stderr),
                       checks=[_check("process", False, "슬라이싱 제한시간을 초과했습니다. 출력은 검증되지 않았습니다.")])
    except OSError as exc:
        return _result("failed", bambu_version=probe["version"], stderr=str(exc), checks=[_check("process", False, str(exc))])
    result = _result("failed", bambu_version=probe["version"], exit_code=completed.returncode,
                     stdout=_text(completed.stdout), stderr=_text(completed.stderr))
    result["checks"].append(_check("process", completed.returncode == 0, f"CLI exit code: {completed.returncode}"))
    if completed.returncode != 0:
        return result
    try:
        for filename, digest in plan["file_hashes"].items():
            path = Path(filename)
            limit = studio_project.MAX_ARCHIVE_BYTES if path.suffix == ".3mf" else studio_project.MAX_SETTINGS_BYTES
            if (path.is_symlink() or path.resolve(strict=True) != path
                    or hashlib.sha256(_project_read_file(path, limit)).hexdigest() != digest):
                raise ValueError("native 실행 중 준비한 원본 또는 프로젝트가 변경되었습니다. 결과를 검증된 출력으로 사용할 수 없습니다.")
        if output.is_symlink() or not output.is_file() or not 0 < output.stat().st_size <= _MAX_ARCHIVE_BYTES:
            raise ValueError("이번 작업의 비어 있지 않은 출력 3MF를 확인하지 못했습니다.")
        _, plate_count = _inspect_archive(output, require_gcode=True)
        settings, settings_bytes = _project_output_settings(output)
        result["checks"].append(_check("sliced_archive", True, f"ZIP 무결성과 {plate_count}개 G-code 이동 명령을 확인했습니다."))
        result.update(output_path=str(output), output_sha256=_hash(output))
    except (OSError, ValueError, RuntimeError, zipfile.BadZipFile, NotImplementedError) as exc:
        result["checks"].append(_check("sliced_archive", False, str(exc)))
        return result
    try:
        geometry = _project_geometry_readback(Path(plan["input_path"]), output)
        result["geometry_readback"] = geometry
        result["checks"].append(_check("geometry", geometry["passed"],
            "현재 CAD의 전체 꼭짓점·삼각형과 단일 build 배치를 확인했습니다." if geometry["passed"] else "출력 형상이 현재 CAD 메시와 다릅니다."))
    except (OSError, ValueError, TypeError, KeyError, OverflowError, RuntimeError, zipfile.BadZipFile, NotImplementedError, ET.ParseError) as exc:
        result["geometry_readback"] = {"passed": False, "error": str(exc)}
        result["checks"].append(_check("geometry", False, str(exc)))
    if settings is None:
        result["checks"].append(_check("project_settings", False, "출력 프로젝트 설정을 다시 읽을 수 없어 검토가 필요합니다."))
    else:
        for key, value in expected.items():
            matches = key in settings and _equivalent(value, settings[key])
            result["checks"].append(_check(f"setting:{key}", matches, "기록한 설정과 일치합니다." if matches else "출력 설정이 누락되었거나 기록과 다릅니다."))
        readback = _snapshot_readback(snapshot["settings_text"], settings, settings_bytes)
        result["project_settings_readback"] = readback
        result["checks"].append(_check("project_settings_snapshot", readback["unqualified_difference_count"] == 0,
            f"전체 설정 비교: 동일 {readback['unchanged_key_count']}개, 확인한 native 정규화 {readback['qualified_normalization_count']}개, 추가 검토 {readback['unqualified_difference_count']}개."))
    result["status"] = "sliced" if all(check["passed"] for check in result["checks"]) else "needs_review"
    return result


def _check(name: str, passed: bool, detail: str) -> dict:
    return {"name": name, "passed": passed, "detail": detail}


def _result(status="blocked", **values) -> dict:
    result = {"status": status, "exit_code": None, "output_path": None, "stdout": "", "stderr": "",
              "bambu_version": None, "output_sha256": None,
              "checks": [], "estimated_time_seconds": None, "filament_grams": None,
              "printer_status": "not_checked", "print_status": "not_started"}
    result.update(values)
    return result


def _validate_plan(plan: dict) -> tuple[Path, Path, Path, dict, list[str]]:
    job_dir = Path(plan["job_dir"]).resolve(strict=True)
    executable = Path(plan["executable_path"]).resolve(strict=True)
    source = Path(plan["input_path"]).resolve(strict=True)
    output = Path(plan["output_path"])
    if not output.is_absolute() or output.parent.resolve() != job_dir or output.exists() or output.is_symlink():
        raise ValueError("출력 파일은 작업 디렉터리의 새 파일이어야 합니다.")
    if not _executable(executable) or not source.is_relative_to(job_dir / "input") or not 1 <= plan["filament_count"] <= 16:
        raise ValueError("실행 계획의 경로나 필라멘트 개수가 유효하지 않습니다.")
    selection_path = job_dir / "config/selection.json"
    required_files = [job_dir / "config/machine.json", job_dir / "config/process.json", selection_path, source]
    required_files.extend(job_dir / f"config/filament-{index + 1}.json" for index in range(plan["filament_count"]))
    for path in required_files:
        if path.is_symlink() or path.resolve().parent not in (job_dir / "config", job_dir / "input") or plan["file_hashes"].get(str(path)) != _hash(path):
            raise ValueError("준비 후 입력 또는 설정 파일이 변경되었습니다. 다시 준비하세요.")
    if not isinstance(plan["expected_settings"], dict) or not plan["expected_settings"]:
        raise ValueError("검증할 설정이 없는 실행 계획입니다.")
    selection = json.loads(selection_path.read_text(encoding="utf-8"))
    if not isinstance(selection, dict) or set(selection) != {"source", "plate_type"}:
        raise ValueError("준비한 플레이트 선택 정보가 유효하지 않습니다. 다시 준비하세요.")
    bundle = {
        **selection,
        "machine": json.loads((job_dir / "config/machine.json").read_text(encoding="utf-8")),
        "process": json.loads((job_dir / "config/process.json").read_text(encoding="utf-8")),
        "filaments": [json.loads((job_dir / f"config/filament-{index + 1}.json").read_text(encoding="utf-8"))
                      for index in range(plan["filament_count"])],
    }
    validated = _validate_bundle(bundle)
    if plan.get("plate_type") != selection["plate_type"]:
        raise ValueError("실행 계획의 plate_type이 준비한 선택과 다릅니다. 다시 준비하세요.")
    if plan["expected_settings"] != validated["expected"]:
        raise ValueError("실행 계획의 검증 대상 설정이 준비한 설정 파일과 다릅니다. 다시 준비하세요.")
    expected_argv = _build_argv(str(executable), job_dir, source, output, plan["filament_count"], selection["plate_type"])
    if plan["argv"] != expected_argv:
        raise ValueError("실행 계획의 CLI 인자가 변경되었습니다. 다시 준비하세요.")
    return job_dir, executable, output, validated["expected"], expected_argv


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
    except OverflowError:
        return False
    except (TypeError, ValueError):
        return expected == actual


def execute_slice(plan: dict, timeout_seconds: int = 180) -> dict:
    """Execute a prepared local slice and verify its artifact. Never dispatch it."""
    if not isinstance(plan, dict) or not plan.get("ready"):
        detail = "; ".join(str(item) for item in plan.get("diagnostics", [])) if isinstance(plan, dict) else "잘못된 실행 계획입니다."
        return _result(checks=[_check("prepared", False, detail or "준비된 실행 계획이 없습니다.")])
    if plan.get("kind") == "studio_project":
        return _execute_project_slice(plan, timeout_seconds)
    try:
        if isinstance(timeout_seconds, bool) or not isinstance(timeout_seconds, (int, float)) or not math.isfinite(timeout_seconds) or timeout_seconds <= 0:
            raise ValueError("timeout_seconds는 0보다 큰 유한 숫자여야 합니다.")
        job_dir, executable, output, expected_settings, argv = _validate_plan(plan)
        probe = _probe_cli(executable, timeout_seconds)
        if not probe["supported"]:
            return _result(bambu_version=probe["version"], checks=[_check("cli_capabilities", False, "; ".join(probe["diagnostics"]))])
    except (OSError, ValueError, TypeError, KeyError, RecursionError) as exc:
        return _result(checks=[_check("prepared", False, str(exc))])
    try:
        completed = subprocess.run(
            argv, cwd=str(job_dir), shell=False, stdin=subprocess.DEVNULL,
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=timeout_seconds, check=False,
        )
    except subprocess.TimeoutExpired as exc:
        return _result("timed_out", bambu_version=probe["version"], stdout=_text(exc.stdout), stderr=_text(exc.stderr),
                       checks=[_check("process", False, "슬라이싱 제한시간을 초과했습니다. 출력은 검증되지 않았습니다.")])
    except OSError as exc:
        return _result("failed", bambu_version=probe["version"], stderr=str(exc), checks=[_check("process", False, str(exc))])
    result = _result("failed", bambu_version=probe["version"], exit_code=completed.returncode, stdout=_text(completed.stdout), stderr=_text(completed.stderr))
    result["checks"].append(_check("process", completed.returncode == 0, f"CLI exit code: {completed.returncode}"))
    if completed.returncode != 0:
        return result
    try:
        if output.is_symlink() or not output.is_file() or not 0 < output.stat().st_size <= _MAX_ARCHIVE_BYTES:
            raise ValueError("이번 작업의 비어 있지 않은 출력 3MF를 확인하지 못했습니다.")
        settings, plate_count = _inspect_archive(output, require_gcode=True)
        output_sha256 = _hash(output)
        result["checks"].append(_check("sliced_archive", True, f"ZIP 무결성과 {plate_count}개 G-code 파일을 확인했습니다."))
    except (OSError, ValueError, RuntimeError, zipfile.BadZipFile, NotImplementedError) as exc:
        result["checks"].append(_check("sliced_archive", False, str(exc)))
        return result
    result["output_path"] = str(output)
    result["output_sha256"] = output_sha256
    if settings is None:
        result["checks"].append(_check("project_settings", False, "핵심 프로젝트 설정을 다시 읽을 수 없어 검토가 필요합니다."))
    else:
        for key, expected in expected_settings.items():
            present = key in settings
            equal = present and _equivalent(expected, settings[key])
            detail = "요청값과 일치합니다." if equal else ("출력 설정이 요청값과 다릅니다." if present else "출력에서 이 설정을 확인할 수 없습니다.")
            result["checks"].append(_check(f"setting:{key}", equal, detail))
    result["status"] = "sliced" if all(check["passed"] for check in result["checks"]) else "needs_review"
    return result
