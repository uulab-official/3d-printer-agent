"""Resolve a conservative subset of explicitly supplied filament preset values.

Bambu Studio also applies built-in defaults, include rules, migrations and
variant/nil merging. This module does not recreate those operations. A resolved
report is evidence about the supplied files, never a full native configuration.
"""
from copy import deepcopy
import hashlib
import json

from .profiles import evaluate_profile
from .profile_origin import copy_archive_origin


_MAX_DOCUMENTS = 64
_MAX_BYTES = 2 * 1024 * 1024
_MAX_CHAIN_DEPTH = 32
_MAX_JSON_DEPTH = 64
_POSITIVE_VALIDATION_STATUSES = {
    "measured_on_matching_setup", "verified", "validated", "reported_validated",
}

# This is an explicit identity-isolation policy, not a complete Studio schema.
# Description and filament_id are intentionally inherited as explicit values.
_TARGET_IDENTITY = {
    "name", "type", "from", "version", "setting_id", "instantiation", "url",
    "user_id", "base_id", "updated_time", "is_custom_defined", "alias",
    "renamed_from", "filament_settings_id",
}
_VARIANT_FIELDS = {
    "filament_extruder_variant", "print_extruder_id", "print_extruder_variant",
    "printer_extruder_id", "printer_extruder_variant",
}
_RESERVED_METADATA = _TARGET_IDENTITY | _VARIANT_FIELDS | {
    "inherits", "include", "description", "filament_id",
}
_WARNINGS = [
    "EXPLICIT_VALUES_ONLY: 가져온 파일의 명시값만 해석합니다. Studio 내부 기본값과 버전별 처리는 포함하지 않습니다.",
    "SOURCE_CLAIM_ONLY: 파일명·출처 표기·해시는 발행처 인증이나 실제 측정의 증거가 아닙니다.",
    "REPORT_ONLY: 이 결과는 검토 보고서입니다. 전체 슬라이서 설정이나 실물 출력 검증을 뜻하지 않습니다.",
]


def _json_bytes(value):
    """Validate JSON data without silently coercing Python-only values."""
    try:
        encoded = json.dumps(value, ensure_ascii=False, sort_keys=True,
                             separators=(",", ":"), allow_nan=False).encode("utf-8")
    except (TypeError, ValueError, OverflowError, RecursionError, UnicodeError) as exc:
        raise ValueError("유한한 숫자와 올바른 문자열로 구성된 JSON 데이터가 필요합니다.") from exc
    pending = [(value, 0)]
    while pending:
        item, depth = pending.pop()
        if depth > _MAX_JSON_DEPTH:
            raise ValueError("JSON 중첩은 최대 64단계까지 지원합니다. 더 단순한 문서로 나누어 확인하세요.")
        if isinstance(item, dict):
            if any(not isinstance(key, str) for key in item):
                raise ValueError("JSON 객체의 키는 문자열이어야 합니다.")
            pending.extend((child, depth + 1) for child in item.values())
        elif isinstance(item, list):
            pending.extend((child, depth + 1) for child in item)
        elif item is not None and not isinstance(item, (str, bool, int, float)):
            raise ValueError("JSON 객체·배열·문자열·숫자·boolean·null만 입력할 수 있습니다.")
    return encoded


def _settings(profile):
    if "settings" not in profile:
        return profile
    for field in ("settings", "scope", "source", "validation"):
        if not isinstance(profile.get(field, {}), dict):
            raise ValueError(f"{field}는 JSON 객체여야 합니다.")
    return profile["settings"]


def _issue(code, message, record=None, **context):
    result = {"code": code, "message": message, **context}
    if record is not None:
        result.update(filename=record["filename"], preset_name=record["name"])
    return result


def _unsupported_value(settings):
    pending = [(value, f"settings.{field}") for field, value in reversed(list(settings.items()))]
    while pending:
        value, path = pending.pop()
        if value is None or (isinstance(value, str) and value == "nil"):
            return path
        if isinstance(value, dict):
            pending.extend((item, f"{path}.{field}") for field, item in reversed(list(value.items())))
        elif isinstance(value, list):
            pending.extend((item, f"{path}[{index}]") for index, item in reversed(list(enumerate(value))))
    return None


def _chain_issues(record):
    settings = record["settings"]
    issues = []
    if "inherits" in settings and not isinstance(settings["inherits"], str):
        issues.append(_issue(
            "INHERITS_UNSUPPORTED",
            "inherits는 정확한 부모 이름 하나를 담은 문자열이어야 합니다.", record, field="inherits",
        ))
    if "include" in settings and settings["include"] != "" and settings["include"] != []:
        issues.append(_issue(
            "INCLUDE_UNSUPPORTED",
            "현재 상속 해석기는 비어 있지 않은 include 설정을 지원하지 않습니다. Studio에서 해당 포함 설정을 확인하세요.",
            record, field="include",
        ))
    for field in sorted(_VARIANT_FIELDS & settings.keys()):
        issues.append(_issue(
            "VARIANT_UNSUPPORTED",
            f"{field}의 압출기 변형별 병합은 현재 상속 해석기에서 지원하지 않습니다.",
            record, field=field,
        ))
    path = _unsupported_value(settings)
    if path is not None:
        issues.append(_issue(
            "SETTING_VALUE_UNSUPPORTED",
            f"{path}에 nil 또는 null이 있습니다. 부모 값 유지·변형별 적용을 추정하지 않습니다.",
            record, field=path,
        ))
    return issues


def _resolve_profile_documents(documents, target_name, setup, *, allow_empty_target=False):
    """Resolve exact single-parent references and retain per-field evidence.

    Structural non-JSON input raises ValueError. Missing references and
    unsupported/ambiguous preset graphs return an inspectable, unresolved report.
    Names and values are not normalized. Filename is a label, never a path to open.
    """
    if not isinstance(documents, list) or not 1 <= len(documents) <= _MAX_DOCUMENTS:
        raise ValueError("필라멘트 JSON 문서는 1개 이상 64개 이하로 가져오세요.")
    if not isinstance(target_name, str) or (not allow_empty_target and not target_name.strip()):
        raise ValueError("검토할 프리셋의 정확한 이름이 필요합니다.")
    if not isinstance(setup, dict):
        raise ValueError("setup은 JSON 객체여야 합니다.")
    payload = {"documents": documents, "target_name": target_name, "setup": setup}
    if len(_json_bytes(payload)) > _MAX_BYTES:
        raise ValueError("프리셋과 사용 조건을 합친 입력은 2 MiB 이하여야 합니다.")

    report = {
        "schema_version": 1,
        "status": "blocked",
        "target_name": target_name,
        "setup": deepcopy(setup),
        "documents": [],
        "chain": [],
        "field_sources": {},
        "resolved_profile": None,
        "review": None,
        "issues": [],
        "warnings": list(_WARNINGS),
        "full_config": False,
        "native_verified": False,
    }
    records = {}
    for document in documents:
        if not isinstance(document, dict) or set(document) not in (
            {"filename", "profile"}, {"filename", "profile", "origin"},
        ):
            raise ValueError("각 문서에는 filename, profile과 선택적인 origin만 필요합니다.")
        filename, profile = document["filename"], document["profile"]
        if not isinstance(filename, str) or not filename.strip() or not isinstance(profile, dict):
            raise ValueError("filename은 빈 문자열이 아니어야 하며 profile은 JSON 객체여야 합니다.")
        settings = _settings(profile)
        copied = deepcopy(profile)
        digest = hashlib.sha256(_json_bytes(profile)).hexdigest()
        supplied = {"filename": filename, "profile": copied, "sha256": digest}
        if "origin" in document:
            supplied["origin"] = copy_archive_origin(document["origin"])
        report["documents"].append(supplied)
        name = settings.get("name")
        record = {"name": name, "filename": filename, "settings": settings,
                  "profile": profile, "sha256": digest}
        for field in settings:
            if field.lower() in _RESERVED_METADATA and field != field.lower():
                report["issues"].append(_issue(
                    "NONCANONICAL_METADATA",
                    f"{field}는 소문자 표기로 확인해야 합니다. 대소문자가 다른 메타데이터를 일반 설정으로 처리하지 않습니다.",
                    record, field=field,
                ))
        if "type" in settings and settings["type"] != "filament":
            report["issues"].append(_issue(
                "PROFILE_TYPE_MISMATCH", "필라멘트(type=filament) 프리셋만 가져올 수 있습니다.", record,
            ))
        if not isinstance(name, str) or not name.strip():
            report["issues"].append(_issue(
                "PROFILE_NAME_INVALID", "각 프리셋에는 비어 있지 않은 문자열 name이 필요합니다.", record,
            ))
        elif name in records:
            report["issues"].append(_issue(
                "DUPLICATE_NAME", f"프리셋 이름 ‘{name}’이 중복되어 대상을 확정할 수 없습니다.", record,
            ))
        else:
            records[name] = record
    if report["issues"]:
        return report
    if target_name not in records:
        report["status"] = "needs_input"
        report["issues"] = [_issue(
            "TARGET_NOT_FOUND", f"대상 프리셋 ‘{target_name}’의 JSON 파일이 필요합니다.",
            target_name=target_name,
        )]
        return report

    reverse_chain, seen = [], set()
    current = target_name
    while True:
        record = records[current]
        if current in seen:
            report["issues"] = [_issue(
                "INHERITANCE_CYCLE", f"프리셋 ‘{current}’로 돌아오는 순환 상속이 있습니다.", record,
            )]
            return report
        if len(reverse_chain) >= _MAX_CHAIN_DEPTH:
            report["issues"] = [_issue(
                "INHERITANCE_DEPTH_EXCEEDED", "상속 체인은 최대 32개 문서까지 해석할 수 있습니다.", record,
            )]
            return report
        report["issues"] = _chain_issues(record)
        if report["issues"]:
            return report
        reverse_chain.append(record)
        seen.add(current)
        parent = record["settings"].get("inherits", "")
        if parent == "":
            break
        if parent not in records:
            report["status"] = "needs_input"
            report["issues"] = [_issue(
                "PARENT_NOT_FOUND", f"‘{current}’의 부모 프리셋 ‘{parent}’ JSON을 추가하세요.",
                record, parent_name=parent,
            )]
            return report
        current = parent

    effective, sources = {}, {}
    for record in reversed(reverse_chain):
        is_target = record["name"] == target_name
        report["chain"].append({
            "name": record["name"], "filename": record["filename"], "sha256": record["sha256"],
        })
        for field, value in record["settings"].items():
            if field in {"inherits", "include"} or (field in _TARGET_IDENTITY and not is_target):
                continue
            assignment = {"preset_name": record["name"], "filename": record["filename"],
                          "sha256": record["sha256"], "value": deepcopy(value)}
            history = sources[field]["history"] if field in sources else []
            history.append(assignment)
            effective[field] = deepcopy(value)
            sources[field] = {
                "preset_name": record["name"], "filename": record["filename"],
                "sha256": record["sha256"], "inherited": not is_target, "history": history,
            }

    target_profile = records[target_name]["profile"]
    resolved = deepcopy(target_profile) if "settings" in target_profile else {}
    resolved["settings"] = effective
    report.update(
        status="resolved", field_sources=sources, resolved_profile=resolved,
        review=evaluate_profile(resolved, setup),
    )
    return report


def _compare_target_evidence(report, original):
    """Compare only uniquely named target envelopes, independently of parents."""
    selected = []
    for snapshot in (original, report):
        if not snapshot["target_name"].strip():
            return
        matches = [
            document["profile"] for document in snapshot["documents"]
            if _settings(document["profile"]).get("name") == snapshot["target_name"]
        ]
        if len(matches) != 1:
            return
        profile = matches[0]
        selected.append(profile if "settings" in profile else {})

    changes = []
    for group in ("scope", "source", "validation"):
        before, after = (profile.get(group, {}) for profile in selected)
        for field in sorted(before.keys() | after.keys()):
            before_present, after_present = field in before, field in after
            if before_present and after_present and _json_bytes(before[field]) == _json_bytes(after[field]):
                continue
            change = {"path": f"{group}.{field}", "before_present": before_present,
                      "after_present": after_present}
            if before_present:
                change["before"] = deepcopy(before[field])
            if after_present:
                change["after"] = deepcopy(after[field])
            changes.append(change)
    report["edit_review"].update(evidence_status="compared", evidence_changes=changes)


def _invalidate_edited_validation(report, *, evidence_changed=False):
    """Invalidate a supplied positive claim without rewriting its source evidence."""
    edit_review = report["edit_review"]
    validation = report["resolved_profile"].get("validation", {})
    claimed_status = validation.get("status")
    if not isinstance(claimed_status, str) or claimed_status not in _POSITIVE_VALIDATION_STATUSES:
        return

    unresolved = edit_review["status"] == "baseline_unresolved"
    review = report["review"]
    review["validation_status"] = "stale"
    review["can_prepare_profile"] = False
    review["selected_profile_id"] = None
    if review["decision"] == "ready_to_prepare":
        review["decision"] = "needs_evidence"
    if evidence_changed:
        review["reasons"].append({
            "code": "VALIDATION_EVIDENCE_CHANGED",
            "message": "원본과 비교해 적용 범위 또는 검증 주장이 변경되었습니다. 기존 검증 보고의 적용 근거를 다시 확인해야 합니다.",
        })
        review["calibration_actions"].append({
            "action": "review", "reason": "validation_evidence_changed",
            "changed_evidence_fields": [
                change["path"] for change in edit_review["evidence_changes"]
                if change["path"].startswith(("scope.", "validation."))
            ],
        })
    else:
        review["reasons"].append({
            "code": "VALIDATION_BASELINE_UNRESOLVED" if unresolved else "VALIDATION_SETTINGS_CHANGED",
            "message": (
                "원본 설정의 상속을 확인할 수 없어 기존 검증 보고를 현재 설정에 적용할 수 없습니다. 원본 파일과 검증 근거를 다시 확인하세요."
                if unresolved else
                "원본과 비교해 실제 적용 설정이 변경되었습니다. 기존 검증 보고를 변경된 값에 적용할 수 없으므로 다시 확인해야 합니다."
            ),
        })
        review["calibration_actions"].append({
            "action": "review",
            "reason": "validation_baseline_unresolved" if unresolved else "validation_settings_changed",
            "changed_fields": list(edit_review["changed_fields"]),
        })
    # A positive-sounding setup-only warning no longer describes applicability.
    review["warnings"] = [
        warning for warning in review["warnings"]
        if not warning.startswith("VALIDATION_CLAIM_ONLY:")
    ]
    if evidence_changed:
        review["warnings"].append(
            "VALIDATION_EVIDENCE_STALE: 입력된 검증 주장은 원본 증거에 보존했습니다. 변경한 적용 범위나 검증 주장의 확인을 뜻하지 않습니다."
        )
    else:
        review["warnings"].append(
            "VALIDATION_SETTINGS_STALE: 입력된 검증 주장은 원본 증거에 보존했습니다. 현재 편집본의 실물 검증을 뜻하지 않습니다."
        )
    edit_review["validation_invalidated"] = True


def resolve_profile_documents(documents: list[dict], target_name: str, setup: dict,
                              *, baseline: dict | None = None) -> dict:
    """Resolve supplied values and optionally compare them with imported originals.

    Each current/original document set has the same independent size/depth bounds.
    ``baseline`` is user-supplied evidence, not an authenticated version or a
    measurement. Effective settings and the selected target's own evidence are
    compared separately. Key ordering and edits to unused or overridden ancestor
    values do not imply a configuration change.
    """
    report = _resolve_profile_documents(documents, target_name, setup)
    report["imported_documents"] = []
    report["edit_review"] = {
        "status": "untracked",
        "baseline_status": None,
        "baseline_target_name": None,
        "baseline_issues": [],
        "changed_fields": [],
        "evidence_status": "untracked",
        "evidence_changes": [],
        "validation_invalidated": False,
    }
    for source in report["field_sources"].values():
        source["edited"] = None
    if baseline is None:
        return report
    if not isinstance(baseline, dict) or set(baseline) != {"documents", "target_name"}:
        raise ValueError("원본 비교에는 documents와 target_name만 필요합니다.")

    original = _resolve_profile_documents(
        baseline["documents"], baseline["target_name"], setup, allow_empty_target=True,
    )
    report["imported_documents"] = original["documents"]
    edit_review = report["edit_review"]
    edit_review.update(
        baseline_status=original["status"],
        baseline_target_name=baseline["target_name"],
        baseline_issues=original["issues"],
    )
    _compare_target_evidence(report, original)
    report["warnings"].append(
        "BASELINE_CLAIM_ONLY: 원본 비교는 사용자가 처음 제공한 JSON을 기준으로 합니다. 발행처 인증이나 측정 이력 확인을 대신하지 않습니다."
    )
    if report["status"] != "resolved":
        return report
    if any(change["path"].startswith(("scope.", "validation."))
           for change in edit_review["evidence_changes"]):
        _invalidate_edited_validation(report, evidence_changed=True)
    if original["status"] != "resolved":
        edit_review["status"] = "baseline_unresolved"
        _invalidate_edited_validation(report)
        return report

    current_settings = report["resolved_profile"]["settings"]
    original_settings = original["resolved_profile"]["settings"]
    changed_fields = sorted(
        field for field in current_settings.keys() | original_settings.keys()
        if field not in current_settings or field not in original_settings
        or _json_bytes(current_settings[field]) != _json_bytes(original_settings[field])
    )
    edit_review["changed_fields"] = changed_fields
    edit_review["status"] = "changed" if changed_fields else "unchanged"
    changed_field_set = set(changed_fields)
    for field, source in report["field_sources"].items():
        source["edited"] = field in changed_field_set
    if changed_fields:
        report["warnings"].append(
            "EDITED_VALUES_USER_INPUT: 수정됨으로 표시된 적용값은 현재 편집본에서 달라진 값입니다. 원본의 발행처 표기가 수정값의 인증을 뜻하지 않습니다."
        )
        _invalidate_edited_validation(report)
    return report
