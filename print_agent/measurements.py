"""Caliper measurements of printed samples, compared with the model's own size.

These are user-measured facts, kept apart from CAD validation and from the
printer's reported state. A comparison inside a declared tolerance is not
hardware qualification: docs/FIELD_QUALIFICATION.md requires the full record
(exact printer, firmware, profiles, at least three samples) for that.
"""
from __future__ import annotations

import math

AXES = ('x', 'y', 'z')
MAX_SAMPLES = 5
MIN_SAMPLES_FOR_REPEATABILITY = 3


def _length(value, label):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not 0 < value <= 1000:
        raise ValueError(f'{label}은(는) 0보다 크고 1000 mm 이하인 숫자여야 합니다.')
    return round(float(value), 3)


def validate_measurements(samples, tolerance):
    """Return normalized samples and tolerance; both optional, samples need all three axes."""
    if samples in (None, []):
        if tolerance is not None:
            raise ValueError('허용 오차는 실측값과 함께 기록하세요.')
        return [], None
    if not isinstance(samples, list) or len(samples) > MAX_SAMPLES:
        raise ValueError(f'실측 샘플은 최대 {MAX_SAMPLES}개까지 기록할 수 있습니다.')
    clean = []
    for index, sample in enumerate(samples, start=1):
        if not isinstance(sample, dict) or set(sample) != set(AXES):
            raise ValueError(f'샘플 {index}에는 가로(x)·세로(y)·높이(z) 세 값이 모두 필요합니다.')
        clean.append({axis: _length(sample[axis], f'샘플 {index}의 {axis}') for axis in AXES})
    if tolerance is not None:
        if isinstance(tolerance, bool) or not isinstance(tolerance, (int, float)) or not math.isfinite(tolerance) or not 0.01 <= tolerance <= 5:
            raise ValueError('허용 오차는 0.01~5 mm 사이로 정하세요.')
        tolerance = round(float(tolerance), 3)
    return clean, tolerance


def review_measurements(expected: dict | None, samples: list, tolerance: float | None) -> dict | None:
    """Per-axis deviation of each sample from the CAD size, and how it compares with the tolerance."""
    if not samples or not isinstance(expected, dict) or not all(isinstance(expected.get(axis), (int, float)) for axis in AXES):
        return None
    rows = []
    for index, sample in enumerate(samples, start=1):
        deviation = {axis: round(sample[axis] - float(expected[axis]), 3) for axis in AXES}
        rows.append({'sample': index, 'measured': dict(sample), 'deviation': deviation,
                     'within_tolerance': None if tolerance is None else all(abs(value) <= tolerance + 1e-9 for value in deviation.values())})
    axes = {}
    for axis in AXES:
        values = [row['deviation'][axis] for row in rows]
        axes[axis] = {'expected': round(float(expected[axis]), 3), 'mean_deviation': round(sum(values) / len(values), 3),
                      'max_abs_deviation': round(max(abs(value) for value in values), 3),
                      'spread': round(max(values) - min(values), 3)}
    status = 'not_judged' if tolerance is None else ('within' if all(row['within_tolerance'] for row in rows) else 'outside')
    notes = []
    if len(samples) < MIN_SAMPLES_FOR_REPEATABILITY:
        notes.append(f'반복성을 보려면 같은 조건의 샘플을 {MIN_SAMPLES_FOR_REPEATABILITY}개 이상 재세요.')
    shrink = [axis for axis in ('x', 'y') if axes[axis]['mean_deviation'] <= -(tolerance or 0.2)]
    if shrink:
        notes.append(f'{"·".join(shrink).upper()} 방향이 평균적으로 작게 나왔습니다. 끼워 맞추는 부품은 여유를 늘리거나 슬라이서의 X-Y 보정을 확인하세요.')
    return {'schema_version': 1, 'source': 'user_measured', 'samples': len(samples), 'tolerance_mm': tolerance,
            'status': status, 'rows': rows, 'axes': axes, 'notes': notes,
            'scope': '사용자가 잰 값과 CAD 치수의 차이입니다. 프린터·재료 조합의 인증이 아니며, 실물 검증 기록은 별도 점검표를 따릅니다.'}
