"""Filament spools the person owns: what they entered, weigh-ins and recorded use.

Every number here is entered or measured by the person (or the slicer's estimate for a
print they chose to deduct); nothing is looked up or guessed. Each spool is one JSON file
with a revision, written atomically, so a stale page cannot overwrite a newer change.
"""
from __future__ import annotations

import csv
import io
import json
import math
import re
import threading
import uuid
from pathlib import Path

from .storage import _atomic_write, _parse_json, _read_regular, now_iso

STATUSES = {'sealed': '미개봉', 'opened': '개봉', 'loaded': '프린터에 장착', 'drying': '건조 중', 'empty': '다 씀'}
LOW_STOCK_G = 150
MAX_HISTORY = 200
# Deduction identities outlive the display history so a print is never deducted twice.
MAX_DEDUCTIONS = 1000
_MAX_FILE_BYTES = 256 * 1024
_ID = re.compile(r'[a-f0-9]{32}')
_SERIAL = re.compile(r'[0-9A-Z]{8,32}')
_POSITION = re.compile(r'ams-[0-7]-[0-7]|external')
_INTEGRITY = '필라멘트 재고 기록을 읽을 수 없습니다. 원본 파일은 보존했습니다.'
_TEXT_FIELDS = ('created_at', 'updated_at', 'brand', 'material', 'color_name', 'location', 'notes')
_AMOUNT_FIELDS = ('diameter_mm', 'net_weight_g', 'empty_spool_g', 'remaining_g')


class InventoryIntegrityError(ValueError):
    """A stored spool record cannot be read as written."""


class InventoryConflict(ValueError):
    """The spool changed since the page read it."""

    def __init__(self, current):
        super().__init__('다른 화면에서 이 스풀이 먼저 바뀌었습니다. 최신 값을 불러왔으니 다시 확인해 주세요.')
        self.current = current


def _round(value):
    return round(float(value), 1)


def _number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _weight_status(spool):
    """A spool with no filament left is empty, and a sealed spool that lost filament is opened."""
    if spool['remaining_g'] == 0:
        return 'empty'
    if spool['status'] == 'sealed' and spool['remaining_g'] < spool['net_weight_g']:
        return 'opened'  # filament has left the spool, so it is no longer sealed
    return spool['status']


def _valid_job_entry(entry, grams_key):
    return (isinstance(entry, dict) and isinstance(entry.get('job_id'), str) and _ID.fullmatch(entry['job_id']) is not None
            and isinstance(entry.get('at'), str) and _number(entry.get(grams_key)))


def _valid_history(history):
    if not isinstance(history, list):
        return False
    for entry in history:
        if not isinstance(entry, dict) or not isinstance(entry.get('at'), str) or not isinstance(entry.get('kind'), str):
            return False
        if not _number(entry.get('remaining_g')):
            return False
        if 'job_id' in entry and not _valid_job_entry(entry, 'remaining_g'):
            return False
    return True


def _valid_deductions(deductions):
    return isinstance(deductions, list) and all(_valid_job_entry(entry, 'grams') for entry in deductions)


def slot_label(slot):
    """Where a spool was recorded as loaded, in words; empty when it is not linked."""
    if not slot:
        return ''
    if slot['position'] == 'external':
        return f"{slot['serial']} · 외부 스풀"
    _, unit, tray = slot['position'].split('-')
    return f"{slot['serial']} · AMS {int(unit) + 1} · {int(tray) + 1}번 칸"


class InventoryStore:
    def __init__(self, root: Path):
        self.directory = Path(root).expanduser().resolve() / 'spools'
        if self.directory.is_symlink() or (self.directory.exists() and not self.directory.is_dir()):
            raise InventoryIntegrityError(_INTEGRITY)
        self.directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        self.lock = threading.Lock()

    def _path(self, spool_id):
        if not isinstance(spool_id, str) or _ID.fullmatch(spool_id) is None:
            raise ValueError('올바른 스풀 ID가 필요합니다.')
        path = self.directory / f'{spool_id}.json'
        if path.is_symlink():
            raise InventoryIntegrityError(_INTEGRITY)
        return path

    def _read(self, spool_id):
        path = self._path(spool_id)
        if not path.exists():
            raise KeyError('스풀을 찾을 수 없습니다.')
        try:
            spool = _parse_json(_read_regular(path, _MAX_FILE_BYTES))
            self._validate(spool, spool_id)
        except (OSError, ValueError, TypeError, AttributeError, RecursionError) as exc:
            raise InventoryIntegrityError(_INTEGRITY) from exc
        # Records written before deduction identities existed derive them from their history.
        spool['deductions'] = self._deductions(spool)
        spool.setdefault('slot', None)  # records from before printer slots existed are unlinked
        return spool

    @staticmethod
    def _validate(spool, spool_id):
        """Every field the app reads must be present and of its type, or the record is damaged."""
        if not isinstance(spool, dict) or spool.get('id') != spool_id or type(spool.get('revision')) is not int:
            raise ValueError('Invalid spool record')
        if any(not isinstance(spool.get(key), str) for key in _TEXT_FIELDS):
            raise ValueError('Invalid spool record')
        if any(not _number(spool.get(key)) for key in _AMOUNT_FIELDS):
            raise ValueError('Invalid spool record')
        if spool.get('color_hex') is not None and not isinstance(spool['color_hex'], str):
            raise ValueError('Invalid spool record')
        if spool.get('price_krw') is not None and type(spool['price_krw']) is not int:
            raise ValueError('Invalid spool record')
        if spool.get('status') not in STATUSES:
            raise ValueError('Invalid spool record')
        if not _valid_history(spool.get('history')):
            raise ValueError('Invalid spool record')
        if 'deductions' in spool and not _valid_deductions(spool['deductions']):
            raise ValueError('Invalid spool record')
        slot = spool.get('slot')
        if slot is not None and not (isinstance(slot, dict) and set(slot) == {'serial', 'position'}
                                     and isinstance(slot['serial'], str) and _SERIAL.fullmatch(slot['serial'])
                                     and isinstance(slot['position'], str) and _POSITION.fullmatch(slot['position'])):
            raise ValueError('Invalid spool record')

    @staticmethod
    def _deductions(spool):
        """Job identities kept apart from the bounded history, so an evicted entry still blocks a second deduction."""
        kept = {}
        for entry in list(spool.get('deductions') or []) + list(spool.get('history') or []):
            job_id = entry.get('job_id')
            if isinstance(job_id, str):
                kept[job_id] = {'job_id': job_id, 'at': entry.get('at', ''), 'grams': entry.get('grams')}
        return list(kept.values())[-MAX_DEDUCTIONS:]

    def _write(self, spool):
        _atomic_write(self._path(spool['id']), json.dumps(spool, ensure_ascii=False, allow_nan=False).encode('utf-8'))

    @staticmethod
    def _check_revision(spool, expected):
        if expected != spool['revision']:
            raise InventoryConflict(spool)

    @staticmethod
    def _fields(values):
        fields = {key: values[key] for key in ('brand', 'material', 'color_name', 'color_hex', 'diameter_mm', 'net_weight_g',
                                               'empty_spool_g', 'remaining_g', 'status', 'location', 'price_krw', 'notes')}
        if fields['remaining_g'] > fields['net_weight_g']:
            raise ValueError('남은 양은 새 스풀의 필라멘트 무게보다 클 수 없습니다.')
        fields['material'] = fields['material'].upper()
        for key in ('net_weight_g', 'empty_spool_g', 'remaining_g'):
            fields[key] = _round(fields[key])
        return fields

    def create(self, values):
        with self.lock:
            now = now_iso()
            spool = {'id': uuid.uuid4().hex, 'revision': 1, 'created_at': now, 'updated_at': now,
                     **self._fields(values), 'slot': None, 'deductions': [],
                     'history': [{'at': now, 'kind': 'created', 'remaining_g': _round(values['remaining_g'])}]}
            spool['status'] = _weight_status(spool)
            self._write(spool)
            return spool

    def update(self, spool_id, expected_revision, values):
        with self.lock:
            spool = self._read(spool_id)
            self._check_revision(spool, expected_revision)
            before = spool['remaining_g']
            spool.update(self._fields(values))
            spool['status'] = _weight_status(spool)  # a manual edit follows the same weight rules as a weigh-in
            spool['revision'] += 1
            spool['updated_at'] = now_iso()
            if spool['remaining_g'] != before:
                spool['history'] = (spool['history'] + [{'at': spool['updated_at'], 'kind': 'edited',
                                                         'remaining_g': spool['remaining_g']}])[-MAX_HISTORY:]
            self._write(spool)
            return spool

    def weigh(self, spool_id, expected_revision, gross_g):
        """A scale reading of spool plus filament; the recorded empty-spool weight is subtracted."""
        with self.lock:
            spool = self._read(spool_id)
            self._check_revision(spool, expected_revision)
            remaining = _round(max(0.0, min(spool['net_weight_g'], gross_g - spool['empty_spool_g'])))
            return self._change(spool, remaining, {'kind': 'weighed', 'gross_g': _round(gross_g)})

    def use(self, spool_id, expected_revision, grams, job_id=None):
        """Deduct a print's filament (usually the slicer's estimate the person chose)."""
        with self.lock:
            spool = self._read(spool_id)
            self._check_revision(spool, expected_revision)
            if job_id is not None and any(entry['job_id'] == job_id for entry in spool['deductions']):
                raise ValueError('이 출력은 이미 이 스풀에서 뺐습니다.')
            remaining = _round(max(0.0, spool['remaining_g'] - grams))
            entry = {'kind': 'used', 'grams': _round(grams)}
            if job_id is not None:
                entry['job_id'] = job_id
            return self._change(spool, remaining, entry)

    def _change(self, spool, remaining, entry):
        now = now_iso()
        spool['remaining_g'] = remaining
        spool['status'] = _weight_status(spool)
        spool['revision'] += 1
        spool['updated_at'] = now
        spool['history'] = (spool['history'] + [{'at': now, **entry, 'remaining_g': remaining}])[-MAX_HISTORY:]
        if entry.get('job_id'):
            spool['deductions'] = (spool['deductions'] + [{'job_id': entry['job_id'], 'at': now, 'grams': entry.get('grams')}])[-MAX_DEDUCTIONS:]
        self._write(spool)
        return spool

    def link(self, spool_id, expected_revision, serial=None, position=None):
        """Record which printer slot holds this spool, as the person says; ``None`` removes the link.

        One spool per printer slot: a spool previously recorded in the same slot is unlinked.
        Nothing is read from the printer here; the reported slot material stays a separate fact.
        """
        if (serial is None) != (position is None):
            raise ValueError('프린터 시리얼과 칸을 함께 고르세요.')
        if serial is not None:
            serial = serial.strip().upper()
            if _SERIAL.fullmatch(serial) is None or _POSITION.fullmatch(position) is None:
                raise ValueError('프린터 시리얼이나 칸 위치가 올바르지 않습니다.')
        with self.lock:
            spool = self._read(spool_id)
            self._check_revision(spool, expected_revision)
            target = {'serial': serial, 'position': position} if serial is not None else None
            if target and spool['status'] == 'empty':
                raise ValueError('다 쓴 스풀은 프린터 칸에 연결할 수 없습니다. 남은 양을 먼저 고쳐 주세요.')
            if target == spool.get('slot'):
                return spool
            displaced = []
            if target:
                for path in sorted(self.directory.glob('*.json')):
                    if path.stem == spool_id:
                        continue
                    try:
                        other = self._read(path.stem)
                    except (InventoryIntegrityError, ValueError, KeyError):
                        continue
                    if other.get('slot') == target:
                        displaced.append(other)
            now = now_iso()
            for other in displaced:
                self._unlink(other, now, 'replaced')
            if target:
                spool['slot'] = target
                if spool['status'] in ('sealed', 'opened', 'drying'):
                    spool['status'] = 'loaded'
                entry = {'at': now, 'kind': 'linked', 'serial': serial, 'position': position, 'remaining_g': spool['remaining_g']}
                spool['revision'] += 1
                spool['updated_at'] = now
                spool['history'] = (spool['history'] + [entry])[-MAX_HISTORY:]
                self._write(spool)
                return spool
            return self._unlink(spool, now, 'removed')

    def _unlink(self, spool, now, reason):
        spool['slot'] = None
        if spool['status'] == 'loaded':
            spool['status'] = 'opened' if spool['remaining_g'] > 0 else 'empty'
        spool['revision'] += 1
        spool['updated_at'] = now
        spool['history'] = (spool['history'] + [{'at': now, 'kind': 'unlinked', 'reason': reason, 'remaining_g': spool['remaining_g']}])[-MAX_HISTORY:]
        self._write(spool)
        return spool

    def delete(self, spool_id, expected_revision):
        with self.lock:
            spool = self._read(spool_id)
            self._check_revision(spool, expected_revision)
            self._path(spool_id).unlink()

    def list(self):
        spools, unreadable = [], 0
        for path in sorted(self.directory.glob('*.json')):
            try:
                spools.append(self._read(path.stem))
            except (InventoryIntegrityError, ValueError, KeyError):
                unreadable += 1
        spools.sort(key=lambda item: (item['status'] == 'empty', item['material'], item['brand'], item['created_at']))
        active = [item for item in spools if item['status'] != 'empty']
        materials = {}
        for item in active:
            materials[item['material']] = _round(materials.get(item['material'], 0) + item['remaining_g'])
        value = sum(item['price_krw'] * item['remaining_g'] / item['net_weight_g'] for item in active
                    if item.get('price_krw') and item['net_weight_g'])
        return {'spools': spools, 'unreadable': unreadable,
                'totals': {'spools': len(active), 'remaining_g': _round(sum(item['remaining_g'] for item in active)),
                           'remaining_value_krw': int(round(value)), 'by_material': materials,
                           'low_stock_ids': [item['id'] for item in active if item['remaining_g'] < LOW_STOCK_G]},
                'low_stock_g': LOW_STOCK_G,
                'scope': '직접 입력하거나 저울로 잰 값과, 직접 고른 출력의 슬라이서 예상 사용량을 뺀 기록입니다. 실제 남은 양은 저울로 확인하세요.'}

    def csv(self):
        stream = io.StringIO()
        writer = csv.writer(stream)
        writer.writerow(['브랜드', '재료', '색', '색 코드', '지름(mm)', '새 스풀 필라멘트(g)', '빈 스풀(g)', '남은 양(g)', '상태', '보관 위치', '가격(원)', '메모', '마지막 변경', '프린터 칸'])
        for item in self.list()['spools']:
            row = [item['brand'], item['material'], item['color_name'], item['color_hex'] or '', item['diameter_mm'], item['net_weight_g'],
                   item['empty_spool_g'], item['remaining_g'], STATUSES.get(item['status'], item['status']), item['location'],
                   item['price_krw'] if item.get('price_krw') is not None else '', item['notes'], item['updated_at'], slot_label(item.get('slot'))]
            # A spreadsheet must not run a cell as a formula.
            writer.writerow([("'" + value) if isinstance(value, str) and value[:1] in '=+-@\t\r' else value for value in row])
        return '﻿' + stream.getvalue()
