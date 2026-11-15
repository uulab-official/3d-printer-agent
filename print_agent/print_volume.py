"""Bounded CAD-envelope comparison with recorded Studio geometry.

The caller verifies the source CAD and settings identities. This pure module
examines their supplied values without changing geometry, selecting a native
placement, or claiming that the recorded settings describe installed hardware.
"""
from __future__ import annotations

import math
import re


_TOLERANCE = 1e-6
_MAX_POINTS = 128
_MAX_VERTICES = 100_000
_NUMBER = re.compile(r"[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?")
_LIMITATIONS = (
    "가져온 설정의 출력 영역과 현재 CAD 외곽 상자를 수평 0°·90° 방향에서만 비교합니다. 대각선 회전과 기울임은 검사하지 않습니다.",
    "브림·스커트·서포트·퍼지 구조물·프린터 이동 공간은 검사하지 않았습니다. 실제 장착 프린터·노즐·플레이트의 확인 결과가 아닙니다.",
    "배치 좌표는 외곽 상자의 최소 X·Y 후보입니다. CAD를 이동·회전하지 않으며 Studio의 실제 배치를 보장하지 않습니다.",
)
_OPTIONAL_GEOMETRY = {
    "bed_exclude_area": "베드 제외 영역",
    "extruder_printable_area": "압출기별 출력 영역",
    "extruder_printable_height": "압출기별 출력 높이",
    "wrapping_exclude_area": "추가 제외 영역",
}


def _model_dimensions(coordinates):
    if not isinstance(coordinates, (list, tuple)) or not 1 <= len(coordinates) <= _MAX_VERTICES:
        raise ValueError("유한한 XYZ 꼭짓점 1~100,000개로 구성된 검증된 CAD가 필요합니다.")
    lower, upper = [math.inf] * 3, [-math.inf] * 3
    for point in coordinates:
        if not isinstance(point, (list, tuple)) or len(point) != 3:
            raise ValueError("CAD 꼭짓점에는 XYZ 숫자 세 개가 필요합니다.")
        for axis, value in enumerate(point):
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ValueError("CAD 꼭짓점에는 유한한 숫자가 필요합니다.")
            try:
                value = float(value)
            except (ValueError, OverflowError) as exc:
                raise ValueError("CAD 꼭짓점에는 유한한 숫자가 필요합니다.") from exc
            if not math.isfinite(value):
                raise ValueError("CAD 꼭짓점에는 유한한 숫자가 필요합니다.")
            lower[axis] = min(lower[axis], value)
            upper[axis] = max(upper[axis], value)
    dimensions = [high - low for low, high in zip(lower, upper)]
    if any(not math.isfinite(value) or value <= 0 for value in dimensions):
        raise ValueError("CAD 외곽 상자의 세 치수는 유한한 양수여야 합니다.")
    return dimensions


def _native_number(value):
    if not isinstance(value, str) or not 1 <= len(value) <= 128:
        raise ValueError("native 숫자 문자열이 필요합니다.")
    value = value.strip()
    if not _NUMBER.fullmatch(value):
        raise ValueError("명시적인 유한 숫자 문자열이 필요합니다.")
    number = float(value)
    if not math.isfinite(number):
        raise ValueError("유한 숫자 문자열이 필요합니다.")
    return number


def _points(value):
    if not isinstance(value, list) or not 1 <= len(value) <= _MAX_POINTS:
        raise ValueError("영역에는 최대 128개의 좌표 문자열이 필요합니다.")
    result = []
    for item in value:
        if not isinstance(item, str) or len(item) > 257:
            raise ValueError("영역 꼭짓점에는 좌표 문자열이 필요합니다.")
        parts = re.split("[x,]", item)
        if len(parts) != 2:
            raise ValueError("영역 꼭짓점에는 XY 좌표 한 쌍이 필요합니다.")
        result.append(tuple(_native_number(part) for part in parts))
    return result


def _rectangle(points, *, closed=False):
    if closed and len(points) == 5 and points[0] == points[-1]:
        points = points[:-1]
    if len(points) != 4 or len(set(points)) != 4:
        raise ValueError("서로 다른 네 꼭짓점의 사각형이 필요합니다.")
    xs, ys = sorted({point[0] for point in points}), sorted({point[1] for point in points})
    if len(xs) != 2 or len(ys) != 2 or set(points) != {(x, y) for x in xs for y in ys}:
        raise ValueError("축에 평행한 사각형만 확인할 수 있습니다.")
    for first, second in zip(points, points[1:] + points[:1]):
        if (first[0] == second[0]) == (first[1] == second[1]):
            raise ValueError("사각형 꼭짓점은 교차하지 않는 둘레 순서여야 합니다.")
    if any(not math.isfinite(high - low) or high - low <= 0 for low, high in (xs, ys)):
        raise ValueError("사각형의 치수는 유한한 양수여야 합니다.")
    return xs[0], ys[0], xs[1], ys[1]


def _exclusions(value):
    if not isinstance(value, list) or len(value) > _MAX_POINTS:
        raise ValueError("제외 영역에는 최대 128개의 좌표 문자열이 필요합니다.")
    if not value:
        return []
    points = _points(value)
    # BambuStudio 56a57d00a591360cf41bf21383915ee5bf357be5: PrintConfig.cpp
    # defaults to an origin singleton; Print.cpp consumes groups of four.
    # Other leftovers remain unsupported here.
    if points == [(0, 0)]:
        return []
    if len(points) % 4:
        raise ValueError("제외 영역은 네 꼭짓점씩 기록된 사각형이어야 합니다.")
    return [_rectangle(points[index:index + 4]) for index in range(0, len(points), 4)]


def _placement(width, depth, bed, exclusions):
    left, bottom, right, top = bed
    if width > right - left + _TOLERANCE or depth > top - bottom + _TOLERANCE:
        return None
    clipped = []
    for x0, y0, x1, y1 in exclusions:
        rectangle = max(left, x0), max(bottom, y0), min(right, x1), min(top, y1)
        if rectangle[0] < rectangle[2] and rectangle[1] < rectangle[3]:
            clipped.append(rectangle)
    # At most 32 exclusion rectangles produce 66 candidates per axis. Any
    # feasible axis-aligned rectangle can slide to these bed/obstacle boundaries.
    xs, ys = {left, right - width}, {bottom, top - depth}
    for x0, y0, x1, y1 in clipped:
        xs.update((x0 - width, x1))
        ys.update((y0 - depth, y1))
    xs = sorted({max(left, x) for x in xs if math.isfinite(x)
                 and x >= left - _TOLERANCE and x + width <= right + _TOLERANCE})
    ys = sorted({max(bottom, y) for y in ys if math.isfinite(y)
                 and y >= bottom - _TOLERANCE and y + depth <= top + _TOLERANCE})
    for y in ys:
        for x in xs:
            if not any(min(x + width, x1) - max(x, x0) > _TOLERANCE
                       and min(y + depth, y1) - max(y, y0) > _TOLERANCE
                       for x0, y0, x1, y1 in clipped):
                return [x, y, 0]
    return None


def review_print_volume(coordinates, settings) -> dict:
    """Review upright CAD bounds against supported recorded bed constraints.

    Invalid CAD coordinates raise ValueError. Unknown or unsupported settings
    produce an inspectable needs_review report. A known height overrun remains
    definitive even when other recorded constraints cannot be interpreted.
    """
    dimensions = _model_dimensions(coordinates)
    result = {
        "schema_version": 1, "status": "needs_review", "can_prepare": False,
        "scope": "upright_bounding_box_0_90", "model_dimensions_mm": dimensions,
        "recorded_volume_mm": [None, None, None],
        "orientations": [{"rotation_degrees": angle, "fits": False} for angle in (0, 90)],
        "placement_mm": None, "rotation_degrees": None, "placement_applied": False,
        "issues": [], "limitations": list(_LIMITATIONS), "tolerance_mm": _TOLERANCE,
    }

    def issue(code, message, field=None):
        item = {"code": code, "message": message}
        if field is not None:
            item["field"] = field
        result["issues"].append(item)

    if not isinstance(settings, dict):
        issue("invalid_settings", "기록된 출력 영역과 높이를 담은 설정 객체가 필요합니다.")
        return result
    missing = [label for key, label in _OPTIONAL_GEOMETRY.items() if key not in settings]
    if missing:
        result["limitations"].append("원본에 " + ", ".join(missing)
                                     + " 항목이 없습니다. 해당 추가 제한이 없는 것으로 확정하지 않습니다.")

    bed, height, exclusions = None, None, []
    try:
        bed = _rectangle(_points(settings.get("printable_area")), closed=True)
        result["recorded_volume_mm"][:2] = [bed[2] - bed[0], bed[3] - bed[1]]
    except ValueError:
        issue("unsupported_printable_area", "기록된 출력 영역은 둘레 순서의 축 정렬 사각형만 확인할 수 있습니다. 원본 영역을 Studio에서 확인하세요.", "printable_area")
    try:
        value = settings.get("printable_height")
        if isinstance(value, list) and len(value) == 1:
            value = value[0]
        height = _native_number(value)
        if height <= 0:
            raise ValueError()
        result["recorded_volume_mm"][2] = height
    except ValueError:
        height = None
        issue("invalid_printable_height", "기록된 출력 높이에 유한한 양수 문자열이 필요합니다.", "printable_height")
    if "bed_exclude_area" in settings:
        try:
            exclusions = _exclusions(settings["bed_exclude_area"])
        except ValueError:
            issue("unsupported_bed_exclusions", "베드 제외 영역의 사각형 묶음이 없거나 모호합니다. 해당 제외 영역을 Studio에서 확인하세요.", "bed_exclude_area")
    for key in ("extruder_printable_area", "wrapping_exclude_area"):
        if key in settings and settings[key] != []:
            issue("unsupported_" + key, "추가 영역 설정은 이 비교에서 해석하지 않습니다. 원본의 적용 범위를 Studio에서 확인하세요.", key)
    if "extruder_printable_height" in settings:
        value = settings["extruder_printable_height"]
        try:
            if value != [] and (not isinstance(value, list) or len(value) != 1
                                or _native_number(value[0]) != 0):
                raise ValueError()
        except ValueError:
            issue("unsupported_extruder_printable_height", "압출기별 추가 높이 제한을 이 비교에서 확정할 수 없습니다. 원본 설정을 Studio에서 확인하세요.", "extruder_printable_height")
    if height is not None and dimensions[2] > height + _TOLERANCE:
        result["status"] = "height_exceeded"
        issue("height_exceeded", "현재 CAD의 높이가 기록된 출력 높이를 초과합니다. 치수 또는 선택한 프린터 설정을 확인하세요.", "printable_height")
        return result
    if result["issues"]:
        return result

    width, depth, _ = dimensions
    for orientation, size in zip(result["orientations"], ((width, depth), (depth, width))):
        placement = _placement(*size, bed, exclusions)
        orientation["fits"] = placement is not None
        if placement is not None and result["placement_mm"] is None:
            result.update(status="fits", can_prepare=True, placement_mm=placement,
                          rotation_degrees=orientation["rotation_degrees"])
    if not result["can_prepare"]:
        issue("checked_orientations_do_not_fit", "0°·90° 방향에서 CAD 외곽 상자의 배치를 확인하지 못했습니다. 대각선 회전은 검사하지 않았으므로 Studio에서 추가 검토하세요.", "printable_area")
    return result
