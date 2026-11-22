"""Read-only status of Klipper printers through their Moonraker web API.

Moonraker is the HTTP API in front of Klipper used by Mainsail, Fluidd and many
vendor firmwares (Snapmaker U1, Voron, Sovol, Elegoo Neptune 4, Qidi and others).
This module only issues four fixed ``GET`` requests (``/server/info``,
``/printer/info``, ``/printer/objects/list`` and ``/printer/objects/query``). It
cannot build a print, motion, temperature, file or G-code request.

Every stage is reported separately: reachability, authorization, whether the
service is Moonraker, Klipper's own state and the printer-reported print state. A
reported "complete" is never a measured physical result. An optional API key is
used for one read and is never stored or returned.
"""
from __future__ import annotations

from datetime import datetime, timezone
import http.client
import ipaddress
import json
import math
import re
import threading
import time
from urllib.parse import quote

DEFAULT_PORT = 7125
MAX_RESPONSE_BYTES = 2 * 1024 * 1024
REQUEST_TIMEOUT_SECONDS = 4.0
MIN_STATUS_INTERVAL_SECONDS = 2.0
MAX_TOOLS = 8
_API_KEY = re.compile(r'[!-~]{8,128}')
_EXTRUDER = re.compile(r'extruder\d{0,2}')

PRINT_STATES = {
    # Moonraker print_stats.state → shared print-state vocabulary of this app
    'standby': ('IDLE', '대기 중'),
    'printing': ('RUNNING', '출력 중'),
    'paused': ('PAUSE', '일시 정지'),
    'complete': ('FINISH', '프린터가 완료를 보고함'),
    'cancelled': ('CANCELLED', '출력이 취소됨'),
    'error': ('FAILED', '프린터가 오류를 보고함'),
}
KLIPPY_STATES = {
    'ready': '준비됨', 'startup': '시작 중', 'shutdown': '정지됨(재시작 필요)', 'error': '오류',
    'disconnected': 'Klipper와 연결되지 않음',
}
CONNECTION_STATES = {
    'reporting': '프린터가 현재 상태를 보고했습니다.',
    'klippy_not_ready': 'Moonraker에는 연결됐지만 Klipper가 준비되지 않아 출력 상태를 읽지 못했습니다.',
    'unreachable': '이 주소와 포트에 연결하지 못했습니다. 주소·포트(기본 7125)·같은 네트워크 여부·프린터 전원을 확인하세요.',
    'access_rejected': '프린터가 요청을 거부했습니다(인증 필요). 프린터의 Moonraker API 키를 입력하거나 이 PC를 신뢰 목록에 추가하세요.',
    'not_moonraker': '이 주소의 서비스가 Moonraker 응답을 보내지 않았습니다. 주소와 포트를 확인하세요.',
    'protocol_error': '프린터 응답을 해석할 수 없어 중단했습니다.',
}

_STATUS_LOCK = threading.Lock()
_LAST_STATUS: dict = {}


class PrinterBusy(RuntimeError):
    """Another Moonraker read is in progress or the same printer was asked too recently."""


class _Stop(Exception):
    def __init__(self, state):
        super().__init__(state)
        self.state = state


def _now():
    return datetime.now(timezone.utc).isoformat()


def validate_target(host, port=DEFAULT_PORT, api_key=None):
    """Return normalized (host, port, api_key). Only private-network IP literals are accepted."""
    if not isinstance(host, str) or not host.strip():
        raise ValueError('프린터의 IP 주소를 입력하세요.')
    try:
        address = ipaddress.ip_address(host.strip())
    except ValueError as exc:
        raise ValueError('프린터 주소는 192.168.0.30 같은 IP 주소로 입력하세요.') from exc
    if not (address.is_private or address.is_link_local or address.is_loopback) or address.is_multicast or address.is_unspecified:
        raise ValueError('같은 로컬 네트워크의 사설 IP 주소만 확인할 수 있습니다.')
    if isinstance(port, bool) or not isinstance(port, int) or not 1 <= port <= 65535:
        raise ValueError('포트는 1~65535 사이의 숫자여야 합니다(Moonraker 기본값 7125).')
    if api_key is not None:
        if not isinstance(api_key, str):
            raise ValueError('API 키 형식이 올바르지 않습니다.')
        api_key = api_key.strip() or None
        if api_key is not None and not _API_KEY.fullmatch(api_key):
            raise ValueError('API 키는 공백 없이 8~128자로 입력하세요.')
    return str(address), port, api_key


# ---------------------------------------------------------------------------
# Bounded value helpers.

def _finite(value, low=-1e6, high=1e6):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    number = float(value)
    return round(number, 2) if math.isfinite(number) and low <= number <= high else None


def _integer(value, low=0, high=10**7):
    number = _finite(value, low, high)
    return int(number) if number is not None else None


def _text(value, limit=200):
    if not isinstance(value, str):
        return None
    cleaned = ' '.join(value.split())[:limit]
    return cleaned or None


# ---------------------------------------------------------------------------
# HTTP.

def _get(host, port, path, api_key, deadline):
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise _Stop('unreachable')
    connection = http.client.HTTPConnection(host, port, timeout=min(REQUEST_TIMEOUT_SECONDS, remaining))
    headers = {'Accept': 'application/json', 'User-Agent': '3d-printer-agent'}
    if api_key:
        headers['X-Api-Key'] = api_key
    try:
        try:
            connection.request('GET', path, headers=headers)
            response = connection.getresponse()
        except (OSError, http.client.HTTPException) as exc:
            raise _Stop('unreachable') from exc
        if response.status in (401, 403):
            raise _Stop('access_rejected')
        try:
            body = response.read(MAX_RESPONSE_BYTES + 1)
        except (OSError, http.client.HTTPException) as exc:
            raise _Stop('protocol_error') from exc
        if len(body) > MAX_RESPONSE_BYTES:
            raise _Stop('protocol_error')
        status = response.status
    finally:
        connection.close()
    try:
        message = json.loads(body, parse_constant=lambda _value: None)
    except (ValueError, UnicodeDecodeError, RecursionError):
        message = None
    result = message.get('result') if isinstance(message, dict) else None
    return status, result


def _require(status, result):
    if status != 200 or not isinstance(result, dict):
        raise _Stop('not_moonraker')
    return result


# ---------------------------------------------------------------------------
# Normalization.

def _tools(status, active):
    tools = []
    names = sorted((name for name in status if _EXTRUDER.fullmatch(name)),
                   key=lambda name: int(name[8:] or 0))[:MAX_TOOLS]
    for index, name in enumerate(names):
        values = status.get(name) if isinstance(status.get(name), dict) else {}
        tools.append({'name': name, 'index': index, 'active': name == active,
                      'temperature_c': _finite(values.get('temperature')), 'target_c': _finite(values.get('target'))})
    return tools


def normalize_status(status, info=None):
    """Turn a Moonraker object query into this app's shared print-status shape.

    Missing fields stay ``None`` (unknown). Material slots are not reported by
    Klipper itself and therefore stay an empty list.
    """
    status = status if isinstance(status, dict) else {}
    stats = status.get('print_stats') if isinstance(status.get('print_stats'), dict) else {}
    sdcard = status.get('virtual_sdcard') if isinstance(status.get('virtual_sdcard'), dict) else {}
    display = status.get('display_status') if isinstance(status.get('display_status'), dict) else {}
    toolhead = status.get('toolhead') if isinstance(status.get('toolhead'), dict) else {}
    bed = status.get('heater_bed') if isinstance(status.get('heater_bed'), dict) else {}
    raw_state = _text(stats.get('state'), 32)
    state, label = PRINT_STATES.get(raw_state or '', (None, None))
    if raw_state and state is None:
        state, label = raw_state.upper(), f'알 수 없는 상태({raw_state})'
    progress = _finite(sdcard.get('progress'), 0, 1)
    if progress is None:
        progress = _finite(display.get('progress'), 0, 1)
    duration = _finite(stats.get('print_duration'), 0, 10**7)
    remaining = None
    if state == 'RUNNING' and progress and progress >= 0.02 and duration:
        remaining = max(0, round((duration / progress - duration) / 60))
    layer_info = stats.get('info') if isinstance(stats.get('info'), dict) else {}
    active = _text(toolhead.get('extruder'), 16)
    tools = _tools(status, active)
    active_tool = next((tool for tool in tools if tool['active']), tools[0] if tools else None)
    message = _text(stats.get('message'), 300)
    printing = {
        'state': state,
        'state_label': label or '보고되지 않음',
        'progress_percent': round(progress * 100) if progress is not None else None,
        'remaining_minutes': remaining,
        'remaining_is_estimate': remaining is not None,
        'elapsed_minutes': round(duration / 60) if duration is not None else None,
        'layer': _integer(layer_info.get('current_layer')),
        'total_layers': _integer(layer_info.get('total_layer')),
        'job_name': None,
        'file_name': _text(stats.get('filename'), 200),
        'error_code': None,
        'error_code_hex': None,
        'error_message': message if state == 'FAILED' else None,
        'hms': [],
        'temperatures_c': {
            'nozzle': active_tool['temperature_c'] if active_tool else None,
            'nozzle_target': active_tool['target_c'] if active_tool else None,
            'bed': _finite(bed.get('temperature')), 'bed_target': _finite(bed.get('target')),
            'chamber': None,
        },
        'tools': tools,
        'active_tool': active_tool['name'] if active_tool else None,
        'nozzle': {'diameter_mm': None, 'type': None},
        'wifi_signal': None,
        'material_slots': [],
        'homed_axes': _text(toolhead.get('homed_axes'), 8),
    }
    return printing


def _result(host, port, state, *, printing=None, identity=None):
    return {
        'schema_version': 1, 'kind': 'moonraker', 'observed_at': _now(),
        'target': {'host': host, 'port': port},
        'connection': {'state': state, 'detail': CONNECTION_STATES[state]},
        'identity': identity,
        'print': printing,
        'scope': ('읽기 전용 Moonraker 상태 확인입니다. 출력 시작·정지·온도 변경·파일 전송 요청은 보내지 않습니다. '
                  '프린터가 보고한 상태는 실물 치수나 품질의 측정 결과가 아닙니다.'),
    }


# ---------------------------------------------------------------------------
# Status read.

def _reserve(host, port):
    if not _STATUS_LOCK.acquire(blocking=False):
        raise PrinterBusy('다른 프린터 상태 확인이 진행 중입니다. 잠시 뒤 다시 시도하세요.')
    key = (host, port)
    if time.monotonic() - _LAST_STATUS.get(key, -math.inf) < MIN_STATUS_INTERVAL_SECONDS:
        _STATUS_LOCK.release()
        raise PrinterBusy(f'같은 프린터는 {MIN_STATUS_INTERVAL_SECONDS:.0f}초 간격으로 확인할 수 있습니다.')
    _LAST_STATUS[key] = time.monotonic()


def read_status(host, port=DEFAULT_PORT, api_key=None, *, timeout=8.0):
    """Read once. Never raises for network outcomes; invalid input raises ``ValueError``."""
    host, port, api_key = validate_target(host, port, api_key)
    _reserve(host, port)
    try:
        try:
            result = _read(host, port, api_key, time.monotonic() + timeout)
        except _Stop as stop:
            result = _result(host, port, stop.state)
        if result['connection']['state'] in ('unreachable', 'access_rejected', 'not_moonraker'):
            # Klipper did not answer, so a corrected address or key may be tried at once.
            _LAST_STATUS.pop((host, port), None)
        return result
    finally:
        _STATUS_LOCK.release()


def _read(host, port, api_key, deadline):
    server = _require(*_get(host, port, '/server/info', api_key, deadline))
    if 'klippy_state' not in server and 'moonraker_version' not in server:
        raise _Stop('not_moonraker')
    identity = {
        'moonraker_version': _text(server.get('moonraker_version'), 80),
        'klippy_connected': server.get('klippy_connected') if isinstance(server.get('klippy_connected'), bool) else None,
        'klippy_state': _text(server.get('klippy_state'), 32),
        'hostname': None, 'klipper_version': None, 'cpu': None, 'state_message': None,
    }
    status, info = _get(host, port, '/printer/info', api_key, deadline)
    if status == 200 and isinstance(info, dict):
        identity.update({'hostname': _text(info.get('hostname'), 80), 'klipper_version': _text(info.get('software_version'), 80),
                         'cpu': _text(info.get('cpu_info'), 120), 'klippy_state': _text(info.get('state'), 32) or identity['klippy_state'],
                         'state_message': _text(info.get('state_message'), 300)})
    identity['klippy_state_label'] = KLIPPY_STATES.get(identity['klippy_state'] or '', identity['klippy_state'] or '보고되지 않음')
    if identity['klippy_state'] != 'ready':
        return _result(host, port, 'klippy_not_ready', identity=identity)
    objects = _require(*_get(host, port, '/printer/objects/list', api_key, deadline)).get('objects')
    available = {name for name in objects if isinstance(name, str)} if isinstance(objects, list) else set()
    wanted = ['print_stats', 'virtual_sdcard', 'display_status', 'toolhead', 'heater_bed']
    wanted += sorted(name for name in available if _EXTRUDER.fullmatch(name))[:MAX_TOOLS]
    query = '&'.join(quote(name, safe='') for name in wanted if name in available)
    if not query:
        raise _Stop('protocol_error')
    result = _require(*_get(host, port, f'/printer/objects/query?{query}', api_key, deadline))
    status_objects = result.get('status')
    if not isinstance(status_objects, dict):
        raise _Stop('protocol_error')
    identity['objects_queried'] = [name for name in wanted if name in available]
    return _result(host, port, 'reporting', printing=normalize_status(status_objects), identity=identity)

