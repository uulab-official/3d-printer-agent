"""Send one verified, already-sliced 3MF to a Bambu printer on the LAN and start it.

This is the only module that can start a print. It is deliberately narrow:

* The file must be a sliced 3MF the app itself produced and verified for a job
  (exactly one plate with G-code). Nothing typed by a person or returned by an LLM
  becomes a command; the only command body is ``project_file`` built below.
* Starting is two-step. ``review_print`` reads the printer once and returns what
  would happen; ``start_print`` runs only with that single-use, short-lived review
  and re-checks the file bytes, certificate and printer state before acting.
* The printer must report an idle/finished state. A running, paused or unknown
  printer is never sent a job.
* Stages stay separate in the result: uploaded, command sent, and the printer's own
  report that it began. A reported start is not a physical print result.
* Once a print runs, only three fixed control commands exist here: pause, resume and
  stop. Each requires the previously pinned certificate and a printer state in which
  that command makes sense; stop also needs an explicit confirmation at the API.

The LAN protocol (implicit FTPS on 990 for the file, MQTT over TLS on 8883 for the
command) is community-documented, not a supported public API. Current Bambu
firmware accepts it only in LAN-only mode with Developer Mode switched on.
Access codes are used for one operation and are never stored or returned.
"""
from __future__ import annotations

from datetime import datetime, timezone
import ftplib
import hashlib
import io
import json
import os
import re
import secrets
import socket
import ssl
import threading
import time
import xml.etree.ElementTree as ET
import zipfile

from . import printer_lan
from .printer_lan import (MQTT_USERNAME, _connect_packet, _packet, _publish_message, _publish_packet,
                          _subscribe_packet, normalize_report, read_packet, validate_target)

FTPS_PORT = 990
MAX_SLICED_BYTES = 64 * 1024 * 1024
REVIEW_TTL_SECONDS = 180
START_OBSERVE_SECONDS = 30.0
UPLOAD_SETTLE_SECONDS = 2.0
READY_STATES = {'IDLE', 'FINISH', 'FAILED'}
STARTED_STATES = {'PREPARE', 'SLICING', 'RUNNING'}
_PLATE_GCODE = re.compile(r'Metadata/plate_(\d{1,3})\.gcode')
_SEND_LOCK = threading.Lock()
# Pause/resume serialize with each other; a stop never waits for them.
_CONTROL_LOCK = threading.Lock()


class SendError(ValueError):
    """The request cannot be sent; nothing was uploaded or started."""


def _now():
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Sliced file inspection (pure).

def inspect_sliced(content: bytes) -> dict:
    """Describe a sliced 3MF; raise SendError unless it has exactly one plate of G-code."""
    if not isinstance(content, (bytes, bytearray)) or not 0 < len(content) <= MAX_SLICED_BYTES:
        raise SendError('보낼 슬라이스 파일이 없거나 64 MiB를 넘습니다.')
    try:
        archive = zipfile.ZipFile(io.BytesIO(content))
        names = archive.namelist()
        if archive.testzip() is not None:
            raise SendError('슬라이스 파일(ZIP)이 손상됐습니다.')
    except (zipfile.BadZipFile, OSError, RuntimeError) as exc:
        raise SendError('슬라이스 파일이 올바른 3MF(ZIP)가 아닙니다.') from exc
    plates = sorted(int(match.group(1)) for name in names if (match := _PLATE_GCODE.fullmatch(name)))
    if len(plates) != 1:
        raise SendError('한 판(plate)의 G-code가 든 슬라이스 파일만 보낼 수 있습니다.')
    plate = plates[0]
    gcode_name = f'Metadata/plate_{plate}.gcode'
    gcode = archive.read(gcode_name)
    if not re.search(rb'^G[01]\s', gcode, re.M):
        raise SendError('슬라이스 파일에 이동 G-code가 없습니다.')
    md5_name = gcode_name + '.md5'
    if md5_name in names:
        recorded = archive.read(md5_name).decode('ascii', 'replace').strip().lower()
        if recorded != hashlib.md5(gcode).hexdigest():
            raise SendError('슬라이스 파일의 G-code 검사값(MD5)이 맞지 않습니다.')
    summary = {'plate': plate, 'gcode_path': gcode_name, 'printer_model_id': None, 'nozzle_diameters': None,
               'prediction_seconds': None, 'weight_g': None, 'filaments': []}
    if 'Metadata/slice_info.config' in names:
        try:
            root = ET.fromstring(archive.read('Metadata/slice_info.config'))
        except ET.ParseError as exc:
            raise SendError('슬라이스 정보(slice_info)를 읽을 수 없습니다.') from exc
        node = root.find('plate')
        if node is not None:
            meta = {item.get('key'): item.get('value') for item in node.findall('metadata')}
            summary['printer_model_id'] = (meta.get('printer_model_id') or '').strip()[:32] or None
            summary['nozzle_diameters'] = (meta.get('nozzle_diameters') or '').strip()[:32] or None
            for key, field, cast in (('prediction', 'prediction_seconds', int), ('weight', 'weight_g', float)):
                try:
                    summary[field] = cast(float(meta[key])) if key in meta else None
                except (TypeError, ValueError):
                    summary[field] = None
            for item in node.findall('filament')[:16]:
                try:
                    number = int(item.get('id', ''))
                    used = round(float(item.get('used_g', '0')), 2)
                except ValueError:
                    continue
                color = item.get('color', '')
                summary['filaments'].append({
                    'id': number, 'type': (item.get('type') or '')[:32] or None,
                    'color': color.upper() if re.fullmatch(r'#[0-9A-Fa-f]{6}', color) else None, 'used_g': used})
    if not summary['filaments']:
        summary['filaments'] = [{'id': 1, 'type': None, 'color': None, 'used_g': None}]
    return summary


def model_check(sliced_code: str | None, product_name: str | None) -> tuple[str | None, str | None]:
    """Compare the slice's printer model with the product name the printer reports.

    Returns ``(problem, warning)``. A send is refused only when the reported name is
    exactly another known model; any name this app cannot place stays a warning.
    """
    from .printer_lan import MODEL_NAMES
    if not sliced_code:
        return None, '슬라이스 파일에 프린터 기종 정보가 없어 프린터와 비교하지 못했습니다.'
    expected = MODEL_NAMES.get(sliced_code)
    if expected is None:
        return None, f'슬라이스한 기종 코드({sliced_code})를 이 앱이 알지 못해 프린터와 비교하지 못했습니다.'
    if not product_name:
        return None, f'프린터가 제품 이름을 보고하지 않아 기종을 비교하지 못했습니다. 이 파일은 {expected}용입니다.'
    reported = ' '.join(re.sub(r'^\s*bambu\s*lab\s*', '', product_name, flags=re.I).split()).casefold()
    known = {name.casefold(): name for name in MODEL_NAMES.values()}
    if reported == expected.casefold():
        return None, None
    if reported in known:
        return (f'이 파일은 {expected}용으로 슬라이스했지만 프린터는 {known[reported]}입니다. '
                '출력판 크기와 시작 동작이 달라 보내지 않습니다. 이 프린터 기종의 설정으로 다시 슬라이스하세요.'), None
    return None, f'프린터가 보고한 제품 이름({product_name})으로는 기종을 확인하지 못했습니다. 이 파일은 {expected}용입니다.'


def ams_index(slot: dict) -> int | None:
    """Global AMS tray number used by the print command (unit * 4 + slot)."""
    if not isinstance(slot, dict) or slot.get('unit') == 'external':
        return None
    unit, tray = slot.get('unit'), slot.get('slot')
    if isinstance(unit, int) and isinstance(tray, int) and 0 <= unit < 8 and 0 <= tray < 4:
        return unit * 4 + tray
    return None


def plan_mapping(summary: dict, slots: list, choice: list | None) -> dict:
    """Validate the person's filament-to-slot choice against reported slots.

    ``choice`` lists, per sliced filament in order, an AMS tray number or ``'external'``."""
    filaments = summary['filaments']
    trays = {ams_index(slot): slot for slot in slots if ams_index(slot) is not None and not slot.get('empty')}
    if choice is None:
        raise SendError('필라멘트마다 꽂힌 위치(AMS 칸 또는 외부 스풀)를 골라 주세요.')
    if not isinstance(choice, list) or len(choice) != len(filaments):
        raise SendError(f'슬라이스한 필라멘트 {len(filaments)}개마다 위치를 하나씩 골라 주세요.')
    if any(value == 'external' for value in choice):
        if len(filaments) != 1:
            raise SendError('여러 색은 AMS 칸으로만 보낼 수 있습니다. 외부 스풀은 한 색일 때만 고를 수 있습니다.')
        return {'use_ams': False, 'ams_mapping': [-1], 'slots': [{'filament': filaments[0]['id'], 'location': '외부 스풀'}]}
    if any(isinstance(value, bool) or not isinstance(value, int) or value not in trays for value in choice):
        raise SendError('프린터가 보고한 AMS 칸 중에서 골라 주세요.')
    if len(set(choice)) != len(choice):
        raise SendError('서로 다른 필라멘트에 같은 AMS 칸을 고를 수 없습니다.')
    rows = []
    warnings = []
    for filament, value in zip(filaments, choice):
        slot = trays[value]
        rows.append({'filament': filament['id'], 'location': f'AMS {value // 4 + 1} · {value % 4 + 1}번 칸',
                     'tray': value, 'material': slot.get('material'), 'color': slot.get('color')})
        if filament.get('type') and slot.get('material') and filament['type'].upper() != slot['material'].upper():
            warnings.append(f'필라멘트 {filament["id"]}은 {filament["type"]}로 슬라이스했지만 고른 칸은 {slot["material"]}입니다.')
    return {'use_ams': True, 'ams_mapping': list(choice), 'slots': rows, 'warnings': warnings}


def print_command(filename: str, md5: str, subtask: str, mapping: dict, plate: int) -> bytes:
    """The single command body this module can publish."""
    if not re.fullmatch(r'[A-Za-z0-9._-]{1,80}\.gcode\.3mf', filename) or not re.fullmatch(r'[a-f0-9]{32}', md5):
        raise SendError('보낼 파일 이름 또는 검사값이 올바르지 않습니다.')
    return json.dumps({'print': {
        'sequence_id': str(secrets.randbelow(10 ** 6)), 'command': 'project_file',
        'param': f'Metadata/plate_{int(plate)}.gcode', 'project_id': '0', 'profile_id': '0', 'task_id': '0',
        'subtask_id': '0', 'subtask_name': subtask[:80], 'file': '', 'url': f'file:///sdcard/{filename}', 'md5': md5,
        'timelapse': False, 'bed_type': 'auto', 'bed_levelling': True, 'flow_cali': False, 'vibration_cali': False,
        'layer_inspect': False, 'use_ams': bool(mapping['use_ams']), 'ams_mapping': list(mapping['ams_mapping']),
    }}, separators=(',', ':')).encode()


# ---------------------------------------------------------------------------
# Network stages.

class _ImplicitFTPS(ftplib.FTP_TLS):
    """FTPS where TLS starts immediately (port 990) and data connections reuse the session."""

    def connect(self, host='', port=0, timeout=-999, source_address=None):
        self.host, self.port = host, port
        if timeout != -999:
            self.timeout = timeout
        raw = socket.create_connection((host, port), self.timeout)
        self.sock = self.context.wrap_socket(raw, server_hostname=None)
        self.af = self.sock.family
        self.file = self.sock.makefile('r', encoding=self.encoding)
        self.welcome = self.getresp()
        return self.welcome

    def ntransfercmd(self, cmd, rest=None):
        conn, size = ftplib.FTP.ntransfercmd(self, cmd, rest)
        if self._prot_p:
            conn = self.context.wrap_socket(conn, server_hostname=None, session=self.sock.session)
        return conn, size


def _ftps_port() -> int:
    """990 on real printers. PPA_PRINTER_FTPS_PORT exists only for local synthetic-printer checks,
    because an unprivileged process cannot listen on 990 at a loopback address on some systems."""
    value = os.environ.get('PPA_PRINTER_FTPS_PORT', '')
    if value.isdigit() and 1024 <= int(value) <= 65535:
        return int(value)
    return FTPS_PORT


def _tls_context():
    # Same device-certificate handling as the status read: the issuer is not in a
    # public trust store, so the fingerprint is compared with the reviewed one instead.
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE
    return context


def upload(host, access_code, filename, content, *, port=FTPS_PORT, timeout=60.0):
    """Store the file at the printer's storage root and confirm its size. Returns the FTPS certificate hash."""
    ftps = _ImplicitFTPS(context=_tls_context(), timeout=timeout)
    try:
        ftps.connect(host, port)
        der = ftps.sock.getpeercert(binary_form=True) or b''
        ftps.login(MQTT_USERNAME, access_code)
        ftps.prot_p()
        ftps.voidcmd('TYPE I')
        ftps.storbinary(f'STOR {filename}', io.BytesIO(content))
        try:
            stored = ftps.size(filename)
        except ftplib.error_perm:
            stored = None
        if stored is not None and stored != len(content):
            raise SendError(f'프린터에 저장된 크기({stored}바이트)가 보낸 파일({len(content)}바이트)과 다릅니다.')
        return {'certificate_sha256': hashlib.sha256(der).hexdigest() if der else None, 'size_confirmed': stored is not None}
    finally:
        try:
            ftps.quit()
        except (OSError, EOFError, ftplib.Error):
            ftps.close()


def _mqtt(host, serial, access_code, pinned, port, deadline):
    raw = socket.create_connection((host, port), timeout=4.0)
    try:
        sock = _tls_context().wrap_socket(raw, server_hostname=None)
        sock.settimeout(max(0.1, deadline - time.monotonic()))
        sock.do_handshake()
    except (OSError, ssl.SSLError):
        raw.close()
        raise SendError('프린터와 보안 연결(TLS)을 시작하지 못했습니다.')
    der = sock.getpeercert(binary_form=True) or b''
    if not der or hashlib.sha256(der).hexdigest() != pinned:
        sock.close()
        raise SendError('검토할 때 확인한 프린터 인증서와 다릅니다. 액세스 코드를 보내지 않고 중단했습니다.')
    sock.sendall(_connect_packet('print-agent-send-' + secrets.token_hex(6), MQTT_USERNAME, access_code))
    kind, _flags, body = read_packet(sock, deadline, 16)
    if kind != 2 or len(body) != 2 or body[1] != 0:
        sock.close()
        raise SendError('프린터가 연결을 거부했습니다. LAN 액세스 코드를 확인하세요.')
    sock.sendall(_subscribe_packet(1, f'device/{serial}/report'))
    return sock


def _reports(sock, serial, deadline, merged):
    """Yield merged print reports until the deadline."""
    topic = f'device/{serial}/report'
    while time.monotonic() < deadline:
        try:
            kind, flags, body = read_packet(sock, deadline)
        except (socket.timeout, ConnectionError):
            return
        if kind != 3:
            continue
        name, payload = _publish_message(flags, body)
        if name != topic:
            continue
        try:
            message = json.loads(payload, parse_constant=lambda _value: None)
        except (ValueError, UnicodeDecodeError, RecursionError):
            continue
        if isinstance(message, dict) and isinstance(message.get('print'), dict):
            merged.update(message['print'])
            yield merged


def _current_state(sock, serial, timeout=6.0):
    sock.sendall(_publish_packet(f'device/{serial}/request', printer_lan.request_payloads()[0]))
    merged = {}
    for report in _reports(sock, serial, time.monotonic() + timeout, merged):
        if 'gcode_state' in report:
            break
    printing, _ = normalize_report(merged)
    return printing


def start(review: dict, access_code: str, content: bytes, *, mqtt_port=None, ftps_port=None,
          observe_seconds=None, settle_seconds=None) -> dict:
    """Upload and start one reviewed job. Returns the separate stage results; never stores the code."""
    observe_seconds = START_OBSERVE_SECONDS if observe_seconds is None else observe_seconds
    settle_seconds = UPLOAD_SETTLE_SECONDS if settle_seconds is None else settle_seconds
    host, serial, pinned = validate_target(review['host'], review['serial'], access_code, review['certificate_sha256'])
    if hashlib.sha256(content).hexdigest() != review['file_sha256']:
        raise SendError('검토한 뒤 슬라이스 파일이 바뀌었습니다. 다시 검토해 주세요.')
    if not _SEND_LOCK.acquire(blocking=False):
        raise SendError('다른 출력 보내기가 진행 중입니다.')
    stages = {'printer_ready': None, 'uploaded': False, 'command_sent': False, 'printer_reported_start': False}
    result = {'schema_version': 1, 'started_at': _now(), 'target': {'host': host, 'serial': serial},
              'file': {'name': review['filename'], 'sha256': review['file_sha256'], 'bytes': len(content)},
              'mapping': review['mapping'], 'stages': stages, 'status': 'blocked', 'detail': '', 'printer': None,
              'scope': '프린터가 출력 시작을 보고했는지까지 확인합니다. 실제 출력 품질·치수는 측정하지 않습니다.'}
    try:
        port = mqtt_port or printer_lan.MQTT_PORT
        deadline = time.monotonic() + 15
        with _mqtt(host, serial, access_code, pinned, port, deadline) as sock:
            state = _current_state(sock, serial)
            stages['printer_ready'] = state['state'] in READY_STATES
            result['printer'] = state
            if not stages['printer_ready']:
                result['detail'] = f'프린터가 “{state["state_label"]}” 상태라 보내지 않았습니다.'
                return result
        result['status'] = 'failed'
        try:
            receipt = upload(host, access_code, review['filename'], content, port=ftps_port or _ftps_port())
        except (OSError, EOFError, ftplib.Error, ssl.SSLError) as exc:
            result['detail'] = f'프린터에 파일을 올리지 못했습니다({type(exc).__name__}). 개발자 모드와 LAN 전용 모드가 켜져 있는지 확인하세요.'
            return result
        stages['uploaded'] = True
        result['upload'] = {**receipt, 'matches_mqtt_certificate': receipt['certificate_sha256'] == pinned}
        time.sleep(settle_seconds)  # some firmware ignores a start sent right after the upload
        deadline = time.monotonic() + 15 + observe_seconds
        with _mqtt(host, serial, access_code, pinned, port, deadline) as sock:
            state = _current_state(sock, serial)
            if state['state'] not in READY_STATES:
                result['printer'] = state
                result['detail'] = f'올린 뒤 프린터가 “{state["state_label"]}” 상태가 되어 시작 명령을 보내지 않았습니다.'
                return result
            md5 = hashlib.md5(content).hexdigest()
            sock.sendall(_publish_packet(f'device/{serial}/request',
                                         print_command(review['filename'], md5, review['subtask'], review['mapping'], review['plate'])))
            stages['command_sent'] = True
            merged = {}
            observed = None
            for report in _reports(sock, serial, time.monotonic() + observe_seconds, merged):
                printing, _ = normalize_report(report)
                observed = printing
                if printing['state'] in STARTED_STATES and printing['job_name'] == review['subtask']:
                    stages['printer_reported_start'] = True
                    break
                if printing['state'] == 'FAILED' and printing['error_code']:
                    break
            try:
                sock.sendall(_packet(14, 0, b''))
            except OSError:
                pass
        result['printer'] = observed
        if stages['printer_reported_start']:
            result['status'] = 'started'
            result['detail'] = '프린터가 이 작업의 출력 시작을 보고했습니다. 첫 레이어가 잘 붙는지 직접 확인하세요.'
        elif observed and observed['error_code']:
            result['status'] = 'rejected'
            result['detail'] = f'프린터가 오류 {observed["error_code_hex"]}를 보고했습니다. 프린터 화면을 확인하세요.'
        else:
            result['status'] = 'unconfirmed'
            result['detail'] = '시작 명령은 보냈지만 제한 시간 안에 출력 시작 보고를 받지 못했습니다. 프린터 화면을 확인하세요.'
        return result
    except SendError as exc:
        result['detail'] = str(exc)
        return result
    except (OSError, ssl.SSLError, printer_lan._Stop) as exc:
        result['detail'] = f'프린터 연결 중 문제가 생겼습니다({type(exc).__name__}).'
        return result
    finally:
        result['finished_at'] = _now()
        _SEND_LOCK.release()


# ---------------------------------------------------------------------------
# Controlling a running print: pause, resume, stop. Nothing else.

CONTROL_FROM = {'pause': {'RUNNING'}, 'resume': {'PAUSE'}, 'stop': {'PREPARE', 'SLICING', 'RUNNING', 'PAUSE'}}
CONTROL_TO = {'pause': {'PAUSE'}, 'resume': {'RUNNING'}, 'stop': {'IDLE', 'FAILED', 'FINISH'}}
CONTROL_LABELS = {'pause': '일시정지', 'resume': '재개', 'stop': '정지'}
CONTROL_OBSERVE_SECONDS = 15.0


def control_command(action: str) -> bytes:
    if action not in CONTROL_FROM:
        raise SendError('지원하는 출력 제어는 일시정지·재개·정지뿐입니다.')
    return json.dumps({'print': {'sequence_id': str(secrets.randbelow(10 ** 6)), 'command': action, 'param': ''}},
                      separators=(',', ':')).encode()


def control(host, serial, access_code, pinned_sha256, action, *, mqtt_port=None, observe_seconds=None) -> dict:
    """Send one control command to a printer whose certificate was pinned earlier, then watch its report."""
    if action not in CONTROL_FROM:
        raise SendError('지원하는 출력 제어는 일시정지·재개·정지뿐입니다.')
    if pinned_sha256 is None:
        raise SendError('먼저 프린터 상태를 읽어 인증서를 확인한 뒤에 제어할 수 있습니다.')
    host, serial, pinned = validate_target(host, serial, access_code, pinned_sha256)
    observe_seconds = CONTROL_OBSERVE_SECONDS if observe_seconds is None else observe_seconds
    lock = None if action == 'stop' else _CONTROL_LOCK
    if lock is not None and not lock.acquire(blocking=False):
        raise SendError('다른 일시정지·재개 명령이 진행 중입니다. 정지는 언제든 보낼 수 있습니다.')
    label = CONTROL_LABELS[action]
    result = {'schema_version': 1, 'action': action, 'target': {'host': host, 'serial': serial}, 'status': 'blocked',
              'command_sent': False, 'state_before': None, 'printer': None, 'detail': '', 'requested_at': _now()}
    try:
        deadline = time.monotonic() + 15 + observe_seconds
        with _mqtt(host, serial, access_code, pinned, mqtt_port or printer_lan.MQTT_PORT, deadline) as sock:
            before = _current_state(sock, serial)
            result['state_before'] = before['state']
            result['printer'] = before
            if before['state'] not in CONTROL_FROM[action]:
                result['detail'] = f'프린터가 “{before["state_label"]}” 상태라 {label} 명령을 보내지 않았습니다.'
                return result
            sock.sendall(_publish_packet(f'device/{serial}/request', control_command(action)))
            result['command_sent'] = True
            merged = {}
            for report in _reports(sock, serial, time.monotonic() + observe_seconds, merged):
                printing, _ = normalize_report(report)
                result['printer'] = printing
                if printing['state'] in CONTROL_TO[action]:
                    result['status'] = 'applied'
                    break
            try:
                sock.sendall(_packet(14, 0, b''))
            except OSError:
                pass
        if result['status'] == 'applied':
            result['detail'] = f'프린터가 {label} 뒤 “{result["printer"]["state_label"]}” 상태를 보고했습니다.'
            if action == 'stop':
                result['detail'] += ' 사용자가 정지한 작업도 프린터는 실패로 보고할 수 있습니다.'
        else:
            result['status'] = 'unconfirmed'
            result['detail'] = f'{label} 명령은 보냈지만 제한 시간 안에 바뀐 상태를 받지 못했습니다. 프린터 화면을 확인하세요.'
        return result
    except SendError as exc:
        result['detail'] = str(exc)
        return result
    except (OSError, ssl.SSLError, printer_lan._Stop) as exc:
        result['status'] = 'failed'
        result['detail'] = f'프린터 연결 중 문제가 생겼습니다({type(exc).__name__}).'
        return result
    finally:
        result['finished_at'] = _now()
        if lock is not None:
            lock.release()


# ---------------------------------------------------------------------------
# Single-use reviews held in memory by the app.

class ReviewStore:
    def __init__(self, ttl=REVIEW_TTL_SECONDS):
        self.ttl = ttl
        self._items = {}
        self._lock = threading.Lock()

    def add(self, review: dict) -> str:
        token = secrets.token_urlsafe(24)
        with self._lock:
            now = time.monotonic()
            self._items = {key: value for key, value in self._items.items() if value[0] > now}
            self._items[token] = (now + self.ttl, review)
        return token

    def take(self, token: str) -> dict:
        with self._lock:
            entry = self._items.pop(token, None) if isinstance(token, str) else None
        if entry is None or entry[0] <= time.monotonic():
            raise SendError('출력 검토가 만료됐거나 이미 사용됐습니다. 다시 검토해 주세요.')
        return entry[1]
