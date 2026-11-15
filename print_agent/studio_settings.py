"""Pure, bounded edits rooted in an immutable supported Studio snapshot.

Input bounds describe the pinned native schema, not physical print validation.
Only explicitly submitted numeric differences receive user-selected provenance.
"""
from __future__ import annotations

import copy
from datetime import datetime
from decimal import Decimal
import hashlib
import json
import re

from .studio_project import MAX_SETTINGS_BYTES, PLATE_BED_PREFIXES, _assess, _settings, _summary

_FIELDS = (
    ('nozzle_temperature', '노즐 온도', '°C', 'integer', 1, 360),
    ('nozzle_temperature_initial_layer', '첫 레이어 노즐 온도', '°C', 'integer', 1, 360),
    ('filament_flow_ratio', '필라멘트 유량 비율', '', 'decimal', 0, 2),
    ('filament_max_volumetric_speed', '최대 체적 속도', 'mm³/s', 'decimal', 0, 200),
    ('bed_temperature', '베드 온도', '°C', 'integer', 1, 120),
    ('bed_temperature_initial_layer', '첫 레이어 베드 온도', '°C', 'integer', 1, 120),
)
_PROPOSAL_KEYS = {'source_sha256', 'settings_sha256', 'values'}
_REVIEW_IDENTITY = ('schema_version', 'source_sha256', 'settings_sha256', 'effective_settings_sha256', 'values', 'changes', 'provenance')
_RECORD_KEYS = {'schema_version', 'revision_id', 'created_at', 'source_id', 'proposal', 'review_sha256', 'effective_settings_sha256', 'changes', 'provenance'}
_WARNINGS = [
    '변경값은 사용자가 선택한 값이며 제조사 권장값이나 실물 출력 검증을 뜻하지 않습니다.',
    '입력 범위는 지원하는 Studio 설정 형식의 범위입니다. 프린터·재료의 안전한 동작 범위는 별도로 확인하세요.',
]


def _serialize(value):
    return json.dumps(value, ensure_ascii=False, allow_nan=False, sort_keys=True, separators=(',', ':')).encode('utf-8')


def _hash(content):
    return hashlib.sha256(content).hexdigest()


def _same_json(actual, expected):
    if type(actual) is not type(expected):
        return False
    if isinstance(expected, dict):
        return actual.keys() == expected.keys() and all(_same_json(actual[key], value) for key, value in expected.items())
    if isinstance(expected, list):
        return len(actual) == len(expected) and all(_same_json(a, b) for a, b in zip(actual, expected))
    return actual == expected


def _sha(value):
    return isinstance(value, str) and re.fullmatch('[0-9a-f]{64}', value) is not None


def _id(value):
    if not isinstance(value, str) or not re.fullmatch('[0-9a-f]{32}', value):
        raise ValueError('서버 UUID hex 식별자가 필요합니다.')


def _timestamp(value):
    try:
        if not isinstance(value, str) or len(value) > 64 or 'T' not in value:
            raise ValueError()
        parsed = datetime.fromisoformat(value)
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            raise ValueError()
    except (ValueError, TypeError, OverflowError) as exc:
        raise ValueError('시간대가 있는 ISO 생성 시각이 필요합니다.') from exc


def _number(value, kind, minimum, maximum):
    if not isinstance(value, str) or len(value) > 32:
        raise ValueError('설정값은 32자 이하 숫자 문자열이어야 합니다.')
    value = value.strip()
    pattern = r'[0-9]+' if kind == 'integer' else r'[0-9]+(?:\.[0-9]{1,6})?'
    if not re.fullmatch(pattern, value):
        raise ValueError('완성된 십진수 숫자 문자열이 필요합니다. 부호·지수 표기는 지원하지 않습니다.')
    number = Decimal(value)
    if number < minimum or number > maximum or (minimum == 0 and number == 0):
        raise ValueError('지원하는 설정 입력 범위를 벗어났습니다.')
    canonical = format(number, 'f')
    if '.' in canonical:
        canonical = canonical.rstrip('0').rstrip('.')
    # Decimal formatting retains leading zeros only in the original, never here.
    return number, canonical


def _validated(snapshot):
    try:
        if (not isinstance(snapshot, dict) or type(snapshot.get('schema_version')) is not int
                or snapshot['schema_version'] != 1 or snapshot.get('supported') is not True
                or not isinstance(snapshot['settings_text'], str)
                or not _sha(snapshot['settings_sha256']) or not _sha(snapshot['source']['sha256'])
                or not isinstance(snapshot['producer'], dict)):
            raise ValueError()
        raw = snapshot['settings_text'].encode('utf-8')
        if len(raw) > MAX_SETTINGS_BYTES or _hash(raw) != snapshot['settings_sha256']:
            raise ValueError()
        settings, _ = _settings(raw)
        issues, expected, beds = _assess(settings, snapshot['producer'])
        if (issues or expected != snapshot['expected_settings'] or snapshot.get('issues') != []
                or snapshot['summary'] != _summary(settings, beds)):
            raise ValueError()
        prefix = PLATE_BED_PREFIXES[settings['curr_bed_type']]
        fields = []
        for key, label, unit, kind, minimum, maximum in _FIELDS:
            native = (prefix + '_temp' + ('_initial_layer' if key.endswith('_initial_layer') else '')) if key.startswith('bed_temperature') else key
            value = settings.get(native)
            if not isinstance(value, list) or len(value) != 1 or not isinstance(value[0], str):
                raise ValueError('편집 가능한 원본 값은 한 문자열 배열이어야 합니다.')
            number, canonical = _number(value[0], kind, minimum, maximum)
            fields.append({'key': key, 'native_key': native, 'label': label, 'unit': unit, 'kind': kind,
                           'original': value[0], 'value': canonical, 'minimum': minimum, 'maximum': maximum,
                           'exclusive_minimum': minimum == 0})
        return settings, fields
    except (KeyError, TypeError, UnicodeError) as exc:
        raise ValueError('지원하는 검증된 원본 설정 snapshot이 필요합니다.') from exc


def settings_editor(snapshot: dict) -> dict:
    _, fields = _validated(snapshot)
    return {'schema_version': 1, 'source_sha256': snapshot['source']['sha256'],
            'settings_sha256': snapshot['settings_sha256'], 'fields': fields,
            'source_summary': copy.deepcopy(snapshot['summary']),
            'warnings': copy.deepcopy(snapshot['warnings']) + list(_WARNINGS)}


def derive_settings(snapshot: dict, proposal: dict) -> tuple[dict, dict]:
    settings, fields = _validated(snapshot)
    if (not isinstance(proposal, dict) or set(proposal) != _PROPOSAL_KEYS
            or proposal['source_sha256'] != snapshot['source']['sha256']
            or proposal['settings_sha256'] != snapshot['settings_sha256']
            or not isinstance(proposal['values'], dict)
            or not set(proposal['values']).issubset(field['key'] for field in fields)):
        raise ValueError('원본 해시와 여섯 편집 항목의 제안만 사용할 수 있습니다.')
    values, changes = {}, []
    # Validate the whole proposal before producing any effective snapshot.
    for field in fields:
        key = field['key']
        if key not in proposal['values']:
            continue
        number, canonical = _number(proposal['values'][key], field['kind'], field['minimum'], field['maximum'])
        if number == Decimal(field['original'].strip()):
            continue
        values[key] = canonical
        changes.append({'field': key, 'native_key': field['native_key'],
                        'before': copy.deepcopy(settings[field['native_key']]), 'after': [canonical]})
    effective = copy.deepcopy(snapshot)
    if changes:
        effective_settings = copy.deepcopy(settings)
        for change in changes:
            effective_settings[change['native_key']] = copy.deepcopy(change['after'])
        raw = _serialize(effective_settings)
        if len(raw) > MAX_SETTINGS_BYTES:
            raise ValueError('변경 설정 크기 제한을 초과했습니다.')
        issues, expected, beds = _assess(effective_settings, snapshot['producer'])
        if issues:
            raise ValueError('변경 후 전체 Studio 설정이 지원 범위를 벗어났습니다.')
        effective.update(settings_text=raw.decode('utf-8'), settings_sha256=_hash(raw),
                         summary=_summary(effective_settings, beds), expected_settings=expected)
    review = {'schema_version': 1, 'source_sha256': snapshot['source']['sha256'],
              'settings_sha256': snapshot['settings_sha256'], 'effective_settings_sha256': effective['settings_sha256'],
              'values': values, 'changes': changes, 'changed_count': len(changes), 'provenance': 'user_selected',
              'effective_summary': copy.deepcopy(effective['summary']), 'warnings': list(_WARNINGS)}
    review['review_sha256'] = _hash(_serialize({key: review[key] for key in _REVIEW_IDENTITY}))
    return effective, review


def make_revision(snapshot, proposal, *, source_id, revision_id, created_at, review_sha256) -> dict:
    _id(source_id)
    _id(revision_id)
    _timestamp(created_at)
    _, review = derive_settings(snapshot, proposal)
    if not review['changed_count'] or not _sha(review_sha256) or review_sha256 != review['review_sha256']:
        raise ValueError('실제 변경과 일치하는 검토 해시가 필요합니다.')
    return {'schema_version': 1, 'revision_id': revision_id, 'created_at': created_at, 'source_id': source_id,
            'proposal': {'source_sha256': review['source_sha256'], 'settings_sha256': review['settings_sha256'],
                         'values': copy.deepcopy(review['values'])},
            'review_sha256': review['review_sha256'], 'effective_settings_sha256': review['effective_settings_sha256'],
            'changes': copy.deepcopy(review['changes']), 'provenance': 'user_selected'}


def verify_revision(snapshot, revision, *, source_id) -> tuple[dict, dict]:
    _id(source_id)
    if (not isinstance(revision, dict) or set(revision) != _RECORD_KEYS
            or type(revision['schema_version']) is not int or revision['schema_version'] != 1
            or revision['source_id'] != source_id):
        raise ValueError('정확한 원본 설정 revision 기록이 필요합니다.')
    expected = make_revision(snapshot, revision['proposal'], source_id=source_id,
                             revision_id=revision['revision_id'], created_at=revision['created_at'],
                             review_sha256=revision['review_sha256'])
    # Neither Python bool/int equality nor JSON tuple/list coercion may weaken
    # the exact record contract. The trusted expected recipe bounds recursion.
    if not _same_json(revision, expected):
        raise ValueError('설정 revision 기록과 원본에서 재구성한 변경이 다릅니다.')
    return derive_settings(snapshot, expected['proposal'])
