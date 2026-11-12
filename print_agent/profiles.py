"""Inspect supplied filament settings without inventing printing parameters.

This module never resolves Bambu inheritance, verifies a publisher, or applies a
profile to hardware. ``ready_to_prepare`` describes this limited inspection, not
full slicer-schema validation or a successful physical print. Unknown fields are
retained; unfamiliar execution settings require further evidence.
"""

from copy import deepcopy
import math


_SCOPE_FIELDS = (
    "printer_model", "printer_preset", "nozzle_diameter", "plate_type",
    "extruder", "feed_mode", "material_id",
)
_PLATE_FIELDS = {
    "Textured PEI Plate": "textured_plate_temp",
    "Smooth PEI Plate": "hot_plate_temp",
    "High Temp Plate": "hot_plate_temp",
    "Smooth PEI Plate / High Temp Plate": "hot_plate_temp",
    "Engineering Plate": "eng_plate_temp",
    "Cool Plate": "cool_plate_temp",
    "Bambu Cool Plate SuperTack": "supertack_plate_temp",
}
_METADATA_FIELDS = {
    "type", "name", "from", "version", "description", "setting_id",
    "filament_id", "filament_settings_id", "filament_vendor", "filament_type",
    "instantiation", "is_custom_defined", "compatible_printers", "inherits",
    "include", "compatible_printers_condition", "compatible_prints_condition",
}
_NUMERIC_FIELDS = {
    "nozzle_temperature", "nozzle_temperature_initial_layer",
    "nozzle_temperature_range_low", "nozzle_temperature_range_high",
    "filament_flow_ratio", "filament_max_volumetric_speed", "filament_diameter",
    "pressure_advance_k", "fan_min_speed", "fan_max_speed", "overhang_fan_speed",
    "slow_down_layer_time", "slow_down_min_speed", "fan_cooling_layer_time",
    "close_fan_the_first_x_layers",
} | set(_PLATE_FIELDS.values()) | {
    f"{field}_initial_layer" for field in _PLATE_FIELDS.values()
}
_EXECUTION_WORDS = (
    "temp", "flow", "volumetric", "nozzle", "extruder", "plate", "pressure",
    "compatib", "feed", "retract", "gcode", "speed", "cooling", "fan",
)


def _present(value):
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip()) and value.strip().lower() != "unknown"
    if isinstance(value, (list, dict)):
        return bool(value)
    return True


def _numeric_values(value):
    """Return parsed numbers for checking only; preserve original source values."""
    values = value if isinstance(value, list) else [value]
    if not values or any(item is None or item == "" for item in values):
        return [], "empty"
    numbers = []
    for item in values:
        if isinstance(item, bool):
            return [], "invalid"
        if not isinstance(item, (int, float, str)):
            return [], "unresolved"
        try:
            number = float(item)
        except (ValueError, TypeError):
            return [], "unresolved"
        except OverflowError:
            return [], "invalid"
        if not math.isfinite(number):
            return [], "invalid"
        numbers.append(number)
    return numbers, None


def _same(field, first, second):
    if field == "nozzle_diameter":
        left, left_error = _numeric_values(first)
        right, right_error = _numeric_values(second)
        return not left_error and not right_error and left == right
    return type(first) is type(second) and first == second


def _copy_json_values(value, path="settings"):
    """Retain invalid nonfinite numbers as text in a blocked, JSON-safe report."""
    invalid = []
    if isinstance(value, dict):
        result = {}
        for key, item in value.items():
            result[key], problems = _copy_json_values(item, f"{path}.{key}")
            invalid.extend(problems)
        return result, invalid
    if isinstance(value, list):
        result = []
        for index, item in enumerate(value):
            copied, problems = _copy_json_values(item, f"{path}[{index}]")
            result.append(copied)
            invalid.extend(problems)
        return result, invalid
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        try:
            finite = math.isfinite(value)
        except OverflowError:
            finite = False
        if not finite:
            if isinstance(value, float):
                label = "NaN" if math.isnan(value) else "Infinity" if value > 0 else "-Infinity"
            else:
                label = str(value)
            return label, [path]
    return deepcopy(value), invalid


def evaluate_profile(profile: dict, setup: dict) -> dict:
    """Evaluate a raw Bambu filament JSON or a scoped metadata envelope.

    Scope comparisons use exact identifiers; compatible_printers can supply the
    printer-preset evidence. Other scope evidence must be supplied explicitly.
    Supplied validation claims are only ``reported_validated`` when their full
    setup dictionary matches. Opaque hashes are not independently verifiable.
    """
    if not isinstance(profile, dict) or not isinstance(setup, dict):
        raise ValueError("profile and setup must be JSON objects")
    envelope = "settings" in profile
    settings = profile["settings"] if envelope else profile
    scope = profile.get("scope", {}) if envelope else {}
    source = profile.get("source", {}) if envelope else {}
    validation = profile.get("validation", {}) if envelope else {}
    if not all(isinstance(value, dict) for value in (settings, scope, source, validation)):
        raise ValueError("settings, scope, source, and validation must be objects")

    effective, invalid_paths = _copy_json_values(settings)
    reasons, missing, warnings, actions = [], [], [], []
    level = 0  # ready < evidence < input < blocked
    scope_unknown = False
    mismatch = False

    def issue(code, message, severity=1, field=None):
        nonlocal level
        level = max(level, severity)
        reasons.append({"code": code, "message": message})
        if field and field not in missing:
            missing.append(field)

    authority = source.get("authority", "unknown")
    if not isinstance(authority, str) or not authority.strip():
        authority = "unknown"
    warnings.append("SOURCE_CLAIM_ONLY: 출처 정보는 입력된 주장입니다. 발행처나 원문을 외부 검증하지 않았습니다.")
    warnings.append("PREPARATION_ONLY: 준비 가능은 전체 슬라이서 구성 검증이나 실제 출력 검증을 의미하지 않습니다.")

    identity_exact = setup.get("material_identity_status") == "exact"
    if not identity_exact:
        scope_unknown = True
        issue("MATERIAL_IDENTITY_UNCONFIRMED", "정확한 필라멘트 제품 식별이 필요합니다.", 2, "material_identity_status")
    for field in _SCOPE_FIELDS:
        actual = setup.get(field)
        if actual is not None and field != "nozzle_diameter" and not isinstance(actual, str):
            scope_unknown = True
            issue("INVALID_SETUP_VALUE", f"{field}는 정확한 식별 문자열이어야 합니다.", 3, field)
        elif not _present(actual):
            scope_unknown = True
            issue("SETUP_FIELD_MISSING", f"현재 장비의 {field} 정보를 확인하세요.", 2, field)
        elif field == "nozzle_diameter":
            numbers, error = _numeric_values(actual)
            if error or len(numbers) != 1 or numbers[0] <= 0:
                scope_unknown = True
                issue("INVALID_SETUP_VALUE", "노즐 지름은 유한한 양수 하나여야 합니다.", 3, field)

    compatible = settings.get("compatible_printers")
    compatible_match = False
    if _present(compatible):
        if not isinstance(compatible, list) or not all(isinstance(name, str) and name.strip() for name in compatible):
            scope_unknown = True
            issue("COMPATIBILITY_UNRESOLVED", "compatible_printers를 정확한 프리셋 이름 목록으로 확인해야 합니다.", field="settings.compatible_printers")
        elif _present(setup.get("printer_preset")):
            compatible_match = setup["printer_preset"] in compatible
            if not compatible_match:
                mismatch = True
                issue("PRINTER_PRESET_MISMATCH", "현재 프린터 프리셋이 compatible_printers에 정확히 일치하지 않습니다.", 3)

    for field in _SCOPE_FIELDS:
        expected, actual = scope.get(field), setup.get(field)
        if not _present(expected):
            if field == "printer_preset" and compatible_match:
                continue
            scope_unknown = True
            issue("PROFILE_SCOPE_MISSING", f"프로필의 {field} 적용 범위 근거가 필요합니다.", field=f"scope.{field}")
        elif _present(actual) and (field != "material_id" or identity_exact):
            if not _same(field, expected, actual):
                mismatch = True
                issue("PROFILE_SCOPE_MISMATCH", f"프로필과 현재 설정의 {field} 값이 일치하지 않습니다.", 3)

    for path in invalid_paths:
        issue("NONFINITE_SETTING", f"{path}에 비유한 숫자가 있습니다. 보고서에서는 원래 표기를 문자열로 보존했습니다.", 3, path)
        warnings.append(f"NONFINITE_SETTING: {path}의 비유한 숫자를 JSON 보고서에서만 문자열로 표시했습니다. 실행에 사용할 수 없습니다.")
    if "type" in settings and settings["type"] != "filament":
        issue("PROFILE_TYPE_MISMATCH", "필라멘트 프로필만 검사할 수 있습니다.", 3)

    for field in ("inherits", "include"):
        if _present(settings.get(field)):
            issue("UNRESOLVED_INHERITANCE", f"{field}를 먼저 해결한 전체 설정이 필요합니다.", field=f"settings.{field}")
    for field in ("compatible_printers_condition", "compatible_prints_condition"):
        if _present(settings.get(field)):
            scope_unknown = True
            issue("COMPATIBILITY_CONDITION_UNRESOLVED", f"{field} 표현식은 이 검사기에서 평가하지 않습니다.", field=f"settings.{field}")

    required = [
        "nozzle_temperature", "nozzle_temperature_initial_layer",
        "filament_flow_ratio", "filament_max_volumetric_speed",
    ]
    plate_name = setup.get("plate_type")
    plate_field = _PLATE_FIELDS.get(plate_name) if isinstance(plate_name, str) else None
    if plate_field:
        required.extend((plate_field, f"{plate_field}_initial_layer"))
    elif _present(setup.get("plate_type")):
        issue("PLATE_TEMPERATURE_UNRESOLVED", "이 플레이트와 Bambu 온도 필드의 대응을 확인해야 합니다.", field="settings.plate_temperature")
    for field in required:
        if field not in settings:
            issue("SETTING_MISSING", f"{field} 값이 없습니다. 임의값으로 채우지 않습니다.", field=f"settings.{field}")

    for field, value in settings.items():
        if field in _NUMERIC_FIELDS:
            numbers, error = _numeric_values(value)
            if error:
                issue("INVALID_SETTING" if error == "invalid" else "SETTING_UNRESOLVED", f"{field}의 유한한 수치를 확인해야 합니다.", 3 if error == "invalid" else 1, f"settings.{field}")
            elif field in ("filament_flow_ratio", "filament_diameter", "nozzle_temperature", "nozzle_temperature_initial_layer") and any(number <= 0 for number in numbers):
                issue("INVALID_SETTING", f"{field}는 양수여야 합니다.", 3, f"settings.{field}")
            elif any(number < 0 for number in numbers):
                issue("INVALID_SETTING", f"{field}의 음수 값은 지원되지 않습니다.", 3, f"settings.{field}")
            elif field == "filament_max_volumetric_speed" and any(number <= 0 for number in numbers):
                issue("VOLUMETRIC_LIMIT_UNRESOLVED", "양의 체적 속도 상한을 확인해야 합니다.", field=f"settings.{field}")
            elif plate_field and field in {plate_field, f"{plate_field}_initial_layer"} and all(number == 0 for number in numbers):
                mismatch = True
                issue("PLATE_UNSUPPORTED", "선택한 플레이트 온도 0은 Bambu 필라멘트 설정에서 지원되지 않는 플레이트를 뜻합니다.", 3)
            if not error and len(set(numbers)) > 1:
                scope_unknown = True
                issue("SETTING_VARIANT_UNRESOLVED", f"{field}에 서로 다른 옵션 값이 있습니다. 현재 압출기와 배열 인덱스의 대응을 확인해야 합니다.", field=f"settings.{field}")
            if field == "pressure_advance_k":
                issue("CALIBRATION_TARGET_UNRESOLVED", "K 값의 장비 교정 저장 위치와 적용은 별도로 확인해야 합니다.", field=f"settings.{field}")
        elif field not in _METADATA_FIELDS:
            warnings.append(f"FIELD_NOT_VALIDATED: {field}는 원문을 보존하며 이 검사기에서 해석하지 않습니다.")
            if any(word in field.lower() for word in _EXECUTION_WORDS) and _present(value):
                issue("EXECUTION_FIELD_UNRESOLVED", f"실행 관련 필드 {field}를 추가 검증해야 합니다.", field=f"settings.{field}")

    validation_status = "unverified"
    reported_status = validation.get("status")
    if reported_status == "stale":
        validation_status = "stale"
    elif isinstance(reported_status, str) and reported_status in {"measured_on_matching_setup", "verified", "validated", "reported_validated"}:
        fingerprint = validation.get("setup_fingerprint")
        if isinstance(fingerprint, dict) and all(_present(fingerprint.get(field)) for field in _SCOPE_FIELDS):
            if all(_same(field, fingerprint[field], setup.get(field)) for field in _SCOPE_FIELDS) and identity_exact:
                validation_status = "reported_validated"
                warnings.append("VALIDATION_CLAIM_ONLY: 같은 장비 조건의 검증 보고가 입력되었으며 실제 측정 여부는 확인하지 않았습니다.")
            else:
                validation_status = "stale"
        else:
            warnings.append("VALIDATION_SCOPE_UNVERIFIED: 검증 보고의 전체 장비 조건을 비교할 수 없습니다.")
    if validation_status == "stale":
        issue("VALIDATION_STALE", "기존 검증 조건과 현재 조건을 다시 확인해야 합니다.", field="validation.setup_fingerprint")
        actions.append({"action": "review", "reason": "validation_setup_changed"})

    identifier = profile.get("id") if envelope else None
    identifier = identifier or settings.get("setting_id") or settings.get("name")
    if not isinstance(identifier, str) or not identifier.strip():
        identifier = None
        issue("PROFILE_ID_MISSING", "프로필 식별자가 필요합니다.", field="profile.id")
    decision = ("ready_to_prepare", "needs_evidence", "needs_input", "blocked")[level]
    return {
        "decision": decision,
        "compatibility": "unsupported" if mismatch else "unknown" if scope_unknown else "supported",
        "can_prepare_profile": level == 0,
        "selected_profile_id": identifier if level == 0 else None,
        "effective_settings": effective,
        "missing_fields": missing,
        "reasons": reasons,
        "source_authority": authority,
        "validation_status": validation_status,
        "calibration_actions": actions,
        "warnings": warnings,
    }


_HARDWARE_CHANGES = {
    "printer_model", "extruder", "nozzle", "nozzle_diameter", "nozzle_material",
    "nozzle_type", "hotend", "hotend_id", "material", "material_id",
}
_TEMPERATURE_CHANGES = {"temperature", "nozzle_temperature", "nozzle_temperature_initial_layer"}
_VOLUMETRIC_CHANGES = {"max_volumetric_speed", "filament_max_volumetric_speed"}
_CALIBRATION_DEPENDENCIES = {
    "flow_dynamics": _HARDWARE_CHANGES | _TEMPERATURE_CHANGES | _VOLUMETRIC_CHANGES | {"flow_ratio", "filament_flow_ratio"},
    "flow_ratio": _HARDWARE_CHANGES,
    "max_volumetric_speed": _HARDWARE_CHANGES | _TEMPERATURE_CHANGES,
}


def review_calibrations(records: list[dict], changes: dict) -> list[dict]:
    """Preserve distinct measurements and mark affected records for review.

    Records use kind=flow_dynamics|flow_ratio|max_volumetric_speed, value, and
    validity=valid|stale|unknown. Optional dependencies add named fields. Changes
    accept either {field: new_value} or {field: {before: ..., after: ...}}.
    This dependency policy requests review; it never fabricates new measurements.
    """
    if not isinstance(records, list) or not all(isinstance(record, dict) for record in records) or not isinstance(changes, dict):
        raise ValueError("records must be a list of objects and changes an object")
    changed = set()
    for field, change in changes.items():
        if isinstance(change, dict) and "before" in change and "after" in change and change["before"] == change["after"]:
            continue
        changed.add(field)
    output = []
    for record in records:
        reviewed, invalid_paths = _copy_json_values(record, "record")
        kind = record.get("kind")
        validity = record.get("validity", "unknown")
        validity = validity if isinstance(validity, str) and validity in {"valid", "stale", "unknown"} else "unknown"
        reasons = list(record.get("review_reasons", [])) if isinstance(record.get("review_reasons", []), list) else []
        values, error = _numeric_values(record.get("value"))
        if not isinstance(kind, str) or kind not in _CALIBRATION_DEPENDENCIES:
            validity = "unknown"
            reasons.append("UNKNOWN_CALIBRATION_KIND")
        elif invalid_paths or error or len(values) != 1 or values[0] < 0 or (kind != "flow_dynamics" and values[0] == 0):
            validity = "unknown"
            reasons.append("INVALID_CALIBRATION_VALUE")
        else:
            dependencies = set(_CALIBRATION_DEPENDENCIES[kind])
            supplied = record.get("dependencies", [])
            if isinstance(supplied, list) and all(isinstance(field, str) for field in supplied):
                dependencies.update(supplied)
            affected = sorted(dependencies & changed)
            if affected:
                if validity != "unknown":
                    validity = "stale"
                reasons.extend(f"CHANGED:{field}" for field in affected)
        reviewed["validity"] = validity
        reviewed["review_reasons"] = list(dict.fromkeys(reasons))
        output.append(reviewed)
    return output
