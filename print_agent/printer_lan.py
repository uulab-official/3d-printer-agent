"""Read-only Bambu LAN-mode identification and status.

The local network interface used by Bambu printers in LAN mode (SSDP announcements
and an MQTT-over-TLS report topic) is community-documented, not a supported public
API. This module therefore reports exactly what was observed and keeps every stage
separate: reachability, TLS certificate, access, report delivery and the printer's
own reported state. A reported "finish" is never a measured physical result.

Only two fixed requests are constructible here: ``pushall`` (ask the printer to send
its current state) and ``get_version`` (module and firmware list). No print, motion,
temperature, file or G-code command can be built through this module. Starting a
reviewed print lives only in ``printer_send``.
"""
from datetime import datetime, timezone
import hashlib
import ipaddress
import json
import math
import re
import secrets
import socket
import ssl
import struct
import threading
import time

MQTT_PORT = 8883
SSDP_LISTEN_PORT = 2021
SSDP_SEARCH_PORT = 1990
SSDP_GROUP = '239.255.255.250'
SSDP_TARGET = 'urn:bambulab-com:device:3dprinter:1'
MQTT_USERNAME = 'bblp'
MAX_PACKET_BYTES = 1024 * 1024
MAX_DEVICES = 32
MIN_STATUS_INTERVAL_SECONDS = 5.0
STATUS_TIMEOUT_SECONDS = 8.0
REPORT_WINDOW_SECONDS = 1.5

_SERIAL = re.compile(r'[0-9A-Z]{8,32}')
_ACCESS_CODE = re.compile(r'[!-~]{4,64}')
_SHA256 = re.compile(r'[a-f0-9]{64}')
# Codes observed in printer announcements. Names are a lookup for display only;
# the raw reported code is always returned alongside.
MODEL_NAMES = {
    'BL-P001': 'X1 Carbon', 'BL-P002': 'X1', 'C13': 'X1E', 'C11': 'P1P', 'C12': 'P1S',
    'N1': 'A1 mini', 'N2S': 'A1', 'O1D': 'H2D',
}
PRINT_STATES = {
    'IDLE': '대기 중', 'PREPARE': '출력 준비 중', 'SLICING': '프린터에서 슬라이싱 중',
    'RUNNING': '출력 중', 'PAUSE': '일시 정지', 'FINISH': '프린터가 완료를 보고함',
    'FAILED': '프린터가 실패를 보고함',
}
CONNECTION_STATES = {
    'reporting': '프린터가 현재 상태를 보고했습니다.',
    'unreachable': '이 주소의 8883 포트에 연결하지 못했습니다. 주소·같은 네트워크 여부·프린터 전원을 확인하세요.',
    'tls_failed': '보안 연결(TLS)을 시작하지 못했습니다. 이 주소가 Bambu 프린터인지 확인하세요.',
    'certificate_changed': '이전에 확인한 인증서와 다릅니다. 액세스 코드를 보내지 않고 중단했습니다.',
    'access_rejected': '프린터가 연결을 거부했습니다. 프린터 화면의 LAN 액세스 코드를 다시 확인하세요.',
    'subscribe_rejected': '연결은 됐지만 이 시리얼의 상태 주제 구독이 거부됐습니다.',
    'no_report': '연결은 됐지만 제한 시간 안에 이 시리얼의 상태 보고를 받지 못했습니다. 시리얼 번호를 확인하세요.',
    'protocol_error': '프린터 응답을 해석할 수 없어 중단했습니다.',
}

_STATUS_LOCK = threading.Lock()
_LAST_STATUS = {}


class PrinterBusy(RuntimeError):
    """Another LAN read is in progress or the same printer was asked too recently."""


class _Stop(Exception):
    def __init__(self, state):
        super().__init__(state)
        self.state = state


def _now():
    return datetime.now(timezone.utc).isoformat()


def validate_target(host, serial, access_code, pinned_sha256=None):
    """Return normalized (host, serial, pin). Only private-network literals are accepted."""
    if not isinstance(host, str) or not host.strip():
        raise ValueError('프린터의 IP 주소를 입력하세요.')
    try:
        address = ipaddress.ip_address(host.strip())
    except ValueError as exc:
        raise ValueError('프린터 주소는 192.168.0.20 같은 IP 주소로 입력하세요.') from exc
    if not (address.is_private or address.is_link_local or address.is_loopback) or address.is_multicast or address.is_unspecified:
        raise ValueError('같은 로컬 네트워크의 사설 IP 주소만 확인할 수 있습니다.')
    if not isinstance(serial, str) or not _SERIAL.fullmatch(serial.strip().upper()):
        raise ValueError('시리얼 번호는 영문 대문자와 숫자 8~32자로 입력하세요.')
    if not isinstance(access_code, str) or not _ACCESS_CODE.fullmatch(access_code):
        raise ValueError('프린터 화면의 LAN 액세스 코드를 공백 없이 입력하세요.')
    if pinned_sha256 is not None and (not isinstance(pinned_sha256, str) or not _SHA256.fullmatch(pinned_sha256)):
        raise ValueError('고정할 인증서 SHA-256은 소문자 16진수 64자여야 합니다.')
    return str(address), serial.strip().upper(), pinned_sha256


# ---------------------------------------------------------------------------
# Minimal MQTT 3.1.1 codec (CONNECT, SUBSCRIBE, QoS 0 PUBLISH, DISCONNECT).

def _mqtt_string(value):
    data = value.encode('utf-8')
    return struct.pack('!H', len(data)) + data


def _remaining_length(length):
    out = bytearray()
    while True:
        byte, length = length % 128, length // 128
        out.append(byte | (0x80 if length else 0))
        if not length:
            return bytes(out)


def _packet(kind, flags, body):
    return bytes([(kind << 4) | flags]) + _remaining_length(len(body)) + body


def _connect_packet(client_id, username, password):
    # Protocol "MQTT" level 4, flags: username + password + clean session.
    variable = _mqtt_string('MQTT') + bytes([4, 0xC2]) + struct.pack('!H', 60)
    return _packet(1, 0, variable + _mqtt_string(client_id) + _mqtt_string(username) + _mqtt_string(password))


def _subscribe_packet(packet_id, topic):
    return _packet(8, 2, struct.pack('!H', packet_id) + _mqtt_string(topic) + b'\x00')


def _publish_packet(topic, payload):
    return _packet(3, 0, _mqtt_string(topic) + payload)


def request_payloads():
    """The only two request bodies this module can publish."""
    sequence = str(secrets.randbelow(10 ** 6))
    return (
        json.dumps({'pushing': {'sequence_id': sequence, 'command': 'pushall', 'version': 1, 'push_target': 1}},
                   separators=(',', ':')).encode(),
        json.dumps({'info': {'sequence_id': sequence, 'command': 'get_version'}}, separators=(',', ':')).encode(),
    )


def _recv_exact(sock, count, deadline):
    data = bytearray()
    while len(data) < count:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise socket.timeout()
        sock.settimeout(remaining)
        chunk = sock.recv(min(65536, count - len(data)))
        if not chunk:
            raise ConnectionError('closed')
        data.extend(chunk)
    return bytes(data)


def read_packet(sock, deadline, max_bytes=MAX_PACKET_BYTES):
    header = _recv_exact(sock, 1, deadline)[0]
    multiplier, length = 1, 0
    for _ in range(4):
        byte = _recv_exact(sock, 1, deadline)[0]
        length += (byte & 0x7F) * multiplier
        if not byte & 0x80:
            break
        multiplier *= 128
    else:
        raise _Stop('protocol_error')
    if length > max_bytes:
        raise _Stop('protocol_error')
    return header >> 4, header & 0x0F, _recv_exact(sock, length, deadline)


def _publish_message(flags, body):
    if len(body) < 2:
        raise _Stop('protocol_error')
    topic_length = struct.unpack('!H', body[:2])[0]
    offset = 2 + topic_length
    if offset > len(body):
        raise _Stop('protocol_error')
    try:
        topic = body[2:offset].decode('utf-8')
    except UnicodeDecodeError as exc:
        raise _Stop('protocol_error') from exc
    if (flags >> 1) & 0x03:
        offset += 2  # packet identifier for QoS 1/2
    return topic, body[offset:]


# ---------------------------------------------------------------------------
# Report normalization (pure).

def _finite(value):
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)) and math.isfinite(value):
        return round(float(value), 1)
    if isinstance(value, str):
        try:
            number = float(value)
        except ValueError:
            return None
        return round(number, 1) if math.isfinite(number) else None
    return None


def _integer(value, low=None, high=None):
    if isinstance(value, bool):
        return None
    if isinstance(value, str) and re.fullmatch(r'-?\d{1,12}', value):
        value = int(value)
    if not isinstance(value, int):
        return None
    if (low is not None and value < low) or (high is not None and value > high):
        return None
    return value


def _text(value, limit=200):
    if not isinstance(value, str):
        return None
    value = ''.join(ch for ch in value if ch.isprintable()).strip()
    return value[:limit] or None


def _hms(entries):
    codes = []
    if not isinstance(entries, list):
        return codes
    for entry in entries[:32]:
        if not isinstance(entry, dict):
            continue
        attr, code = _integer(entry.get('attr'), 0, 0xFFFFFFFF), _integer(entry.get('code'), 0, 0xFFFFFFFF)
        if attr is None or code is None:
            continue
        codes.append({'attr': attr, 'code': code,
                      'hms_code': f'{attr >> 16:04X}_{attr & 0xFFFF:04X}_{code >> 16:04X}_{code & 0xFFFF:04X}'})
    return codes


def _color(value):
    return value.upper() if isinstance(value, str) and re.fullmatch(r'[0-9A-Fa-f]{6}([0-9A-Fa-f]{2})?', value) else None


def _tray(unit_id, tray):
    if not isinstance(tray, dict):
        return None
    slot = {
        'unit': unit_id, 'slot': _integer(tray.get('id'), 0, 255),
        'material': _text(tray.get('tray_type'), 32), 'product': _text(tray.get('tray_sub_brands'), 80),
        'color': _color(tray.get('tray_color')), 'filament_id': _text(tray.get('tray_info_idx'), 32),
        'nozzle_min_c': _finite(tray.get('nozzle_temp_min')), 'nozzle_max_c': _finite(tray.get('nozzle_temp_max')),
    }
    return slot if any(slot[key] is not None for key in ('material', 'product', 'color', 'filament_id')) else {**slot, 'empty': True}


def _material_slots(report):
    slots = []
    ams = report.get('ams')
    units = ams.get('ams') if isinstance(ams, dict) else None
    if isinstance(units, list):
        for unit in units[:8]:
            if not isinstance(unit, dict):
                continue
            unit_id = _integer(unit.get('id'), 0, 255)
            for tray in (unit.get('tray') if isinstance(unit.get('tray'), list) else [])[:8]:
                slot = _tray(unit_id, tray)
                if slot:
                    slots.append(slot)
    external = _tray('external', report.get('vt_tray'))
    if external:
        slots.append(external)
    return slots


def normalize_report(report, info=None):
    """Convert merged raw printer report fields into bounded, display-safe values.

    Missing fields stay ``None`` (unknown). Nothing is defaulted from other models.
    """
    report = report if isinstance(report, dict) else {}
    raw_state = _text(report.get('gcode_state'), 32)
    state = raw_state.upper() if raw_state else None
    error = _integer(report.get('print_error'), 0, 0xFFFFFFFF)
    printing = {
        'state': state,
        'state_label': PRINT_STATES.get(state, f'알 수 없는 상태({state})' if state else '보고되지 않음'),
        'progress_percent': _integer(report.get('mc_percent'), 0, 100),
        'remaining_minutes': _integer(report.get('mc_remaining_time'), 0, 100000),
        'layer': _integer(report.get('layer_num'), 0, 1000000),
        'total_layers': _integer(report.get('total_layer_num'), 0, 1000000),
        'job_name': _text(report.get('subtask_name')),
        'file_name': _text(report.get('gcode_file')),
        'error_code': error,
        'error_code_hex': f'{error:08X}' if error else None,
        'hms': _hms(report.get('hms')),
        'temperatures_c': {
            'nozzle': _finite(report.get('nozzle_temper')), 'nozzle_target': _finite(report.get('nozzle_target_temper')),
            'bed': _finite(report.get('bed_temper')), 'bed_target': _finite(report.get('bed_target_temper')),
            'chamber': _finite(report.get('chamber_temper')),
        },
        'nozzle': {'diameter_mm': _finite(report.get('nozzle_diameter')), 'type': _text(report.get('nozzle_type'), 40)},
        'wifi_signal': _text(report.get('wifi_signal'), 16),
        'material_slots': _material_slots(report),
    }
    modules = []
    raw_modules = info.get('module') if isinstance(info, dict) else None
    if isinstance(raw_modules, list):
        for module in raw_modules[:24]:
            if isinstance(module, dict) and _text(module.get('name'), 40):
                modules.append({'name': _text(module.get('name'), 40), 'software': _text(module.get('sw_ver'), 40),
                                'hardware': _text(module.get('hw_ver'), 40), 'product': _text(module.get('product_name'), 80),
                                'project': _text(module.get('project_name'), 40)})
    firmware = next((m['software'] for m in modules if m['name'] == 'ota'), None)
    product = next((m['product'] for m in modules if m['product']), None)
    return printing, {'modules': modules, 'firmware': firmware, 'product_name': product}


# ---------------------------------------------------------------------------
# Status read.

def _result(host, serial, state, *, certificate=None, printing=None, identity=None):
    return {
        'schema_version': 1, 'observed_at': _now(),
        'target': {'host': host, 'serial': serial, 'port': MQTT_PORT},
        'connection': {'state': state, 'detail': CONNECTION_STATES[state]},
        'certificate': certificate,
        'identity': identity,
        'print': printing,
        'scope': ('읽기 전용 LAN 상태 확인입니다. 출력 시작·정지·온도 변경 같은 명령은 보내지 않습니다. '
                  '프린터가 보고한 상태는 실물 치수나 품질의 측정 결과가 아닙니다.'),
    }


def _reserve(host, serial):
    if not _STATUS_LOCK.acquire(blocking=False):
        raise PrinterBusy('다른 프린터 상태 확인이 진행 중입니다. 잠시 뒤 다시 시도하세요.')
    key = (host, serial)
    elapsed = time.monotonic() - _LAST_STATUS.get(key, -math.inf)
    if elapsed < MIN_STATUS_INTERVAL_SECONDS:
        _STATUS_LOCK.release()
        raise PrinterBusy(f'같은 프린터는 {MIN_STATUS_INTERVAL_SECONDS:.0f}초 간격으로 확인할 수 있습니다.')
    _LAST_STATUS[key] = time.monotonic()


def read_status(host, serial, access_code, *, pinned_sha256=None, timeout=STATUS_TIMEOUT_SECONDS,
                report_window=REPORT_WINDOW_SECONDS, port=None, include_version=True):
    """Connect once, ask for the current state, and disconnect. Never raises for network outcomes.

    ``include_version=False`` skips the module/firmware query for repeated progress reads."""
    host, serial, pinned_sha256 = validate_target(host, serial, access_code, pinned_sha256)
    _reserve(host, serial)
    try:
        return _read_status(host, serial, access_code, pinned_sha256, timeout, report_window, port or MQTT_PORT,
                            include_version)
    finally:
        _STATUS_LOCK.release()


def _read_status(host, serial, access_code, pinned, timeout, report_window, port, include_version=True):
    deadline = time.monotonic() + timeout
    certificate = None
    try:
        raw = socket.create_connection((host, port), timeout=min(timeout, 4.0))
    except OSError:
        return _result(host, serial, 'unreachable')
    # The printer presents a device certificate that ordinary trust stores do not
    # contain. Its issuer is therefore not verified; the fingerprint is reported and
    # can be pinned so that a later different endpoint never receives the code.
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE
    try:
        with raw:
            try:
                sock = context.wrap_socket(raw, server_hostname=None)
                sock.settimeout(max(0.1, deadline - time.monotonic()))
                sock.do_handshake()
            except (OSError, ssl.SSLError):
                return _result(host, serial, 'tls_failed')
            with sock:
                der = sock.getpeercert(binary_form=True) or b''
                fingerprint = hashlib.sha256(der).hexdigest() if der else None
                certificate = {'sha256': fingerprint, 'issuer_verified': False, 'pinned': pinned is not None,
                               'matches_pin': None if pinned is None else fingerprint == pinned}
                if not fingerprint:
                    return _result(host, serial, 'tls_failed', certificate=certificate)
                if pinned is not None and fingerprint != pinned:
                    return _result(host, serial, 'certificate_changed', certificate=certificate)
                return _session(sock, host, serial, access_code, certificate, deadline, report_window, include_version)
    except _Stop as stop:
        return _result(host, serial, stop.state, certificate=certificate)
    except (OSError, ssl.SSLError):
        return _result(host, serial, 'protocol_error' if certificate else 'tls_failed', certificate=certificate)


def _session(sock, host, serial, access_code, certificate, deadline, report_window, include_version=True):
    client_id = 'print-agent-' + secrets.token_hex(6)
    sock.sendall(_connect_packet(client_id, MQTT_USERNAME, access_code))
    try:
        kind, _flags, body = read_packet(sock, deadline, 16)
    except (socket.timeout, ConnectionError):
        raise _Stop('access_rejected')
    if kind != 2 or len(body) != 2:
        raise _Stop('protocol_error')
    if body[1] != 0:
        raise _Stop('access_rejected')
    report_topic = f'device/{serial}/report'
    sock.sendall(_subscribe_packet(1, report_topic))
    payloads = request_payloads()
    for payload in payloads if include_version else payloads[:1]:
        sock.sendall(_publish_packet(f'device/{serial}/request', payload))
    subscribed, merged, info, received = False, {}, None, False
    window_end = None
    while True:
        now = time.monotonic()
        limit = deadline if window_end is None else min(deadline, window_end)
        if now >= limit:
            break
        try:
            kind, flags, body = read_packet(sock, limit)
        except socket.timeout:
            break
        except ConnectionError:
            break
        if kind == 9:  # SUBACK
            if len(body) < 3 or body[2] == 0x80:
                raise _Stop('subscribe_rejected')
            subscribed = True
        elif kind == 3:
            topic, payload = _publish_message(flags, body)
            if topic != report_topic:
                continue
            try:
                message = json.loads(payload, parse_constant=lambda _value: None)
            except (ValueError, UnicodeDecodeError, RecursionError):
                continue
            if not isinstance(message, dict):
                continue
            if isinstance(message.get('print'), dict):
                merged.update(message['print'])
                received = True
            if isinstance(message.get('info'), dict) and message['info'].get('command') == 'get_version':
                info = message['info']
                received = True
            if received and window_end is None:
                # Collect follow-up deltas/version reply for a short bounded window.
                window_end = time.monotonic() + report_window
            if 'gcode_state' in merged and (info is not None or not include_version):
                break
    try:
        sock.sendall(_packet(14, 0, b''))
    except OSError:
        pass
    if not received:
        return _result(host, serial, 'no_report' if subscribed else 'protocol_error', certificate=certificate)
    printing, identity = normalize_report(merged, info)
    identity['report_topic_serial'] = serial
    return _result(host, serial, 'reporting', certificate=certificate, printing=printing, identity=identity)


# ---------------------------------------------------------------------------
# SSDP discovery.

def parse_announcement(datagram, sender):
    """Parse one Bambu SSDP NOTIFY or search response. Return None for anything else."""
    if not isinstance(datagram, (bytes, bytearray)) or len(datagram) > 4096:
        return None
    try:
        text = bytes(datagram).decode('utf-8')
    except UnicodeDecodeError:
        return None
    lines = text.replace('\r\n', '\n').split('\n')
    if not lines or not (lines[0].startswith('NOTIFY ') or lines[0].startswith('HTTP/1.1 200')):
        return None
    headers = {}
    for line in lines[1:40]:
        name, sep, value = line.partition(':')
        if sep:
            headers[name.strip().lower()] = value.strip()
    if SSDP_TARGET not in (headers.get('nt'), headers.get('st')):
        return None
    serial = (headers.get('usn') or '').upper()
    if not _SERIAL.fullmatch(serial):
        return None
    try:
        address = ipaddress.ip_address(sender)
    except ValueError:
        return None
    location = headers.get('location')
    model = _text(headers.get('devmodel.bambu.com'), 40)
    return {
        'host': str(address), 'serial': serial,
        'location_matches_sender': location == str(address) if location else None,
        'model_code': model, 'model_name': MODEL_NAMES.get(model or ''),
        'name': _text(headers.get('devname.bambu.com'), 80),
        'connection_mode': _text(headers.get('devconnect.bambu.com'), 20),
        'bind_state': _text(headers.get('devbind.bambu.com'), 20),
        'firmware': _text(headers.get('devversion.bambu.com'), 40),
        'signal': _text(headers.get('devsignal.bambu.com'), 16),
    }


def discover(seconds=4.0):
    """Listen for printer announcements on this computer's local network."""
    seconds = float(seconds)
    if not 1 <= seconds <= 10:
        raise ValueError('찾기 시간은 1~10초여야 합니다.')
    started = _now()
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    except OSError:
        return {'state': 'listen_unavailable', 'observed_at': started, 'devices': [], 'seconds': seconds}
    with sock:
        try:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            if hasattr(socket, 'SO_REUSEPORT'):
                try:
                    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
                except OSError:
                    pass
            sock.bind(('', SSDP_LISTEN_PORT))
        except OSError:
            return {'state': 'listen_unavailable', 'observed_at': started, 'devices': [], 'seconds': seconds}
        try:
            membership = socket.inet_aton(SSDP_GROUP) + socket.inet_aton('0.0.0.0')
            sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, membership)
        except OSError:
            pass
        search = ('M-SEARCH * HTTP/1.1\r\nHOST: 239.255.255.250:1990\r\nMAN: "ssdp:discover"\r\n'
                  f'MX: 1\r\nST: {SSDP_TARGET}\r\n\r\n').encode()
        try:
            sock.sendto(search, (SSDP_GROUP, SSDP_SEARCH_PORT))
        except OSError:
            pass
        devices = {}
        end = time.monotonic() + seconds
        while len(devices) < MAX_DEVICES:
            remaining = end - time.monotonic()
            if remaining <= 0:
                break
            sock.settimeout(remaining)
            try:
                datagram, (sender, _port) = sock.recvfrom(4096)
            except socket.timeout:
                break
            except OSError:
                break
            device = parse_announcement(datagram, sender)
            if device:
                devices[(device['host'], device['serial'])] = device
    return {'state': 'listened', 'observed_at': started, 'seconds': seconds,
            'devices': sorted(devices.values(), key=lambda d: (d['serial'], d['host']))}
