import json
import socket
import ssl
import struct
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

from print_agent import printer_lan

FIXTURES = Path(__file__).parent / 'fixtures' / 'printer_lan'
SERIAL = '01S00TEST000001'
CODE = 'abcd1234'

FULL_REPORT = {'print': {
    'command': 'push_status', 'gcode_state': 'RUNNING', 'mc_percent': 42, 'mc_remaining_time': 37,
    'layer_num': 51, 'total_layer_num': 120, 'subtask_name': 'tray_120x80', 'gcode_file': 'tray.gcode',
    'nozzle_temper': 219.6, 'nozzle_target_temper': 220, 'bed_temper': 54.9, 'bed_target_temper': 55,
    'chamber_temper': 'nan', 'print_error': 0, 'hms': [{'attr': 0x07008000, 'code': 0x00020001}],
    'nozzle_diameter': '0.4', 'nozzle_type': 'stainless_steel', 'wifi_signal': '-48dBm',
    'ams': {'ams': [{'id': '0', 'tray': [
        {'id': '0', 'tray_type': 'PLA', 'tray_sub_brands': 'PLA Basic', 'tray_color': 'FFFFFFFF', 'tray_info_idx': 'GFA00',
         'nozzle_temp_min': '190', 'nozzle_temp_max': '230'},
        {'id': '1'}]}]},
    'vt_tray': {'id': '254', 'tray_type': 'PETG', 'tray_color': 'zzz'},
}}
VERSION = {'info': {'command': 'get_version', 'sequence_id': '1', 'module': [
    {'name': 'ota', 'sw_ver': '01.08.00.00', 'hw_ver': '', 'sn': SERIAL},
    {'name': 'mc', 'sw_ver': '00.00.29.00', 'hw_ver': 'MC07', 'product_name': 'Bambu Lab P1S'}]}}


def _string(value):
    data = value.encode()
    return struct.pack('!H', len(data)) + data


class FakePrinter:
    """Loopback TLS MQTT endpoint that records what the client sent."""

    def __init__(self, *, cert='printer', code=CODE, reports=(), connack=None, suback=0, silent=False):
        self.code, self.reports, self.connack, self.suback, self.silent = code, list(reports), connack, suback, silent
        self.context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        self.context.load_cert_chain(FIXTURES / f'{cert}-cert.pem', FIXTURES / f'{cert}-key.pem')
        self.listener = socket.socket()
        self.listener.bind(('127.0.0.1', 0))
        self.listener.listen(1)
        self.port = self.listener.getsockname()[1]
        self.connect_seen = False
        self.credentials = None
        self.published = []
        self.subscribed = []
        self.thread = threading.Thread(target=self._serve, daemon=True)
        self.thread.start()

    def _read(self, conn):
        header = conn.recv(1)
        if not header:
            raise ConnectionError
        length, multiplier = 0, 1
        while True:
            byte = conn.recv(1)[0]
            length += (byte & 0x7F) * multiplier
            if not byte & 0x80:
                break
            multiplier *= 128
        body = b''
        while len(body) < length:
            chunk = conn.recv(length - len(body))
            if not chunk:
                raise ConnectionError
            body += chunk
        return header[0] >> 4, body

    def _send_publish(self, conn, topic, payload):
        body = _string(topic) + payload
        conn.sendall(bytes([0x30]) + printer_lan._remaining_length(len(body)) + body)

    def _serve(self):
        try:
            raw, _ = self.listener.accept()
            with self.context.wrap_socket(raw, server_side=True) as conn:
                conn.settimeout(5)
                kind, body = self._read(conn)
                if kind != 1:
                    return
                self.connect_seen = True
                offset = 2 + struct.unpack('!H', body[:2])[0] + 4
                fields = []
                while offset < len(body):
                    size = struct.unpack('!H', body[offset:offset + 2])[0]
                    fields.append(body[offset + 2:offset + 2 + size].decode())
                    offset += 2 + size
                self.credentials = tuple(fields[1:])
                code = self.connack if self.connack is not None else (0 if self.credentials == ('bblp', self.code) else 5)
                conn.sendall(bytes([0x20, 2, 0, code]))
                if code:
                    return
                while True:
                    kind, body = self._read(conn)
                    if kind == 8:
                        packet_id = body[:2]
                        self.subscribed.append(body[4:4 + struct.unpack('!H', body[2:4])[0]].decode())
                        conn.sendall(bytes([0x90, 3]) + packet_id + bytes([self.suback]))
                    elif kind == 3:
                        size = struct.unpack('!H', body[:2])[0]
                        self.published.append((body[2:2 + size].decode(), json.loads(body[2 + size:])))
                        if len(self.published) == 2 and not self.silent:
                            for topic, report in self.reports:
                                payload = report if isinstance(report, bytes) else json.dumps(report).encode()
                                self._send_publish(conn, topic, payload)
                    elif kind == 14:
                        return
        except (OSError, ssl.SSLError, ConnectionError, IndexError):
            pass
        finally:
            self.listener.close()

    def fingerprint(self):
        der = ssl.PEM_cert_to_DER_cert((FIXTURES / 'printer-cert.pem').read_text())
        import hashlib
        return hashlib.sha256(der).hexdigest()


class PrinterLanTests(unittest.TestCase):
    def setUp(self):
        printer_lan._LAST_STATUS.clear()

    def read(self, printer, **kwargs):
        kwargs.setdefault('timeout', 3)
        kwargs.setdefault('report_window', 0.3)
        result = printer_lan.read_status('127.0.0.1', SERIAL, CODE, port=printer.port, **kwargs)
        printer.thread.join(3)
        return result

    def test_reporting_status_separates_identity_print_and_certificate(self):
        topic = f'device/{SERIAL}/report'
        printer = FakePrinter(reports=[(f'device/OTHER0000001/report', {'print': {'gcode_state': 'FAILED'}}),
                                       (topic, b'not json'), (topic, FULL_REPORT), (topic, VERSION)])
        result = self.read(printer)
        self.assertEqual(result['connection']['state'], 'reporting')
        self.assertEqual(printer.credentials, ('bblp', CODE))
        self.assertEqual(printer.subscribed, [topic])
        commands = [(t, next(iter(p.values()))['command']) for t, p in printer.published]
        self.assertEqual(commands, [(f'device/{SERIAL}/request', 'pushall'), (f'device/{SERIAL}/request', 'get_version')])
        status = result['print']
        self.assertEqual((status['state'], status['progress_percent'], status['remaining_minutes']), ('RUNNING', 42, 37))
        self.assertEqual((status['layer'], status['total_layers']), (51, 120))
        self.assertIsNone(status['temperatures_c']['chamber'])
        self.assertEqual(status['temperatures_c']['nozzle_target'], 220.0)
        self.assertEqual(status['hms'][0]['hms_code'], '0700_8000_0002_0001')
        self.assertEqual(status['nozzle'], {'diameter_mm': 0.4, 'type': 'stainless_steel'})
        slots = status['material_slots']
        self.assertEqual(slots[0]['filament_id'], 'GFA00')
        self.assertEqual(slots[0]['color'], 'FFFFFFFF')
        self.assertTrue(slots[1]['empty'])
        self.assertEqual((slots[2]['unit'], slots[2]['material'], slots[2]['color']), ('external', 'PETG', None))
        self.assertEqual(result['identity']['firmware'], '01.08.00.00')
        self.assertEqual(result['identity']['product_name'], 'Bambu Lab P1S')
        self.assertEqual(result['certificate'], {'sha256': printer.fingerprint(), 'issuer_verified': False,
                                                 'pinned': False, 'matches_pin': None})
        self.assertNotIn(CODE, json.dumps(result))

    def test_pinned_mismatch_stops_before_access_code_is_sent(self):
        expected = FakePrinter().fingerprint()
        printer = FakePrinter(cert='other')
        result = self.read(printer, pinned_sha256=expected)
        self.assertEqual(result['connection']['state'], 'certificate_changed')
        self.assertFalse(printer.connect_seen)
        self.assertIsNone(printer.credentials)
        self.assertFalse(result['certificate']['matches_pin'])

    def test_pinned_match_continues(self):
        printer = FakePrinter(reports=[(f'device/{SERIAL}/report', FULL_REPORT), (f'device/{SERIAL}/report', VERSION)])
        result = self.read(printer, pinned_sha256=printer.fingerprint())
        self.assertEqual(result['connection']['state'], 'reporting')
        self.assertTrue(result['certificate']['matches_pin'])

    def test_rejected_access_code(self):
        printer = FakePrinter(code='different')
        result = self.read(printer)
        self.assertEqual(result['connection']['state'], 'access_rejected')
        self.assertIsNone(result['print'])

    def test_subscribed_without_report_is_not_reporting(self):
        printer = FakePrinter(silent=True)
        result = self.read(printer, timeout=1)
        self.assertEqual(result['connection']['state'], 'no_report')
        self.assertIsNone(result['print'])

    def test_rejected_subscription(self):
        printer = FakePrinter(suback=0x80)
        self.assertEqual(self.read(printer)['connection']['state'], 'subscribe_rejected')

    def test_delta_report_without_version_keeps_unknown_fields(self):
        printer = FakePrinter(reports=[(f'device/{SERIAL}/report', {'print': {'mc_percent': 5}}),
                                       (f'device/{SERIAL}/report', {'print': {'gcode_state': 'mystery'}})])
        result = self.read(printer)
        self.assertEqual(result['connection']['state'], 'reporting')
        self.assertEqual(result['print']['state_label'], '알 수 없는 상태(MYSTERY)')
        self.assertIsNone(result['print']['remaining_minutes'])
        self.assertIsNone(result['identity']['firmware'])

    def test_unreachable_and_non_tls(self):
        closed = socket.socket()
        closed.bind(('127.0.0.1', 0))
        port = closed.getsockname()[1]
        closed.close()
        result = printer_lan.read_status('127.0.0.1', SERIAL, CODE, port=port, timeout=1)
        self.assertEqual(result['connection']['state'], 'unreachable')
        printer_lan._LAST_STATUS.clear()
        plain = socket.socket()
        plain.bind(('127.0.0.1', 0))
        plain.listen(1)
        def close_after_accept():
            conn, _ = plain.accept()
            conn.sendall(b'HTTP/1.1 400 Bad Request\r\n\r\n')
            conn.close()
        thread = threading.Thread(target=close_after_accept, daemon=True)
        thread.start()
        result = printer_lan.read_status('127.0.0.1', SERIAL, CODE, port=plain.getsockname()[1], timeout=2)
        thread.join(2)
        plain.close()
        self.assertEqual(result['connection']['state'], 'tls_failed')

    def test_target_validation(self):
        for host in ('8.8.8.8', 'printer.example', '', '239.255.255.250', '0.0.0.0'):
            with self.subTest(host=host), self.assertRaises(ValueError):
                printer_lan.validate_target(host, SERIAL, CODE)
        for serial in ('short', 'BAD-SERIAL-0001', 'X' * 33, 12345678):
            with self.subTest(serial=serial), self.assertRaises(ValueError):
                printer_lan.validate_target('192.168.0.20', serial, CODE)
        for code in ('', 'has space', 'é' * 8):
            with self.subTest(code=code), self.assertRaises(ValueError):
                printer_lan.validate_target('192.168.0.20', SERIAL, code)
        with self.assertRaises(ValueError):
            printer_lan.validate_target('192.168.0.20', SERIAL, CODE, 'ABC')
        self.assertEqual(printer_lan.validate_target(' 10.0.0.5 ', ' 01s00test000001 ', CODE)[:2], ('10.0.0.5', SERIAL))

    def test_same_printer_rate_limit_and_single_reader(self):
        printer_lan._LAST_STATUS[('127.0.0.1', SERIAL)] = printer_lan.time.monotonic()
        with self.assertRaises(printer_lan.PrinterBusy):
            printer_lan.read_status('127.0.0.1', SERIAL, CODE, port=1)
        printer_lan._LAST_STATUS.clear()
        self.assertTrue(printer_lan._STATUS_LOCK.acquire(blocking=False))
        try:
            with self.assertRaises(printer_lan.PrinterBusy):
                printer_lan.read_status('127.0.0.1', SERIAL, CODE, port=1)
        finally:
            printer_lan._STATUS_LOCK.release()

    def test_only_fixed_read_requests_exist(self):
        commands = sorted(next(iter(json.loads(p).values()))['command'] for p in printer_lan.request_payloads())
        self.assertEqual(commands, ['get_version', 'pushall'])

    def test_oversized_packet_is_rejected(self):
        a, b = socket.socketpair()
        with a, b:
            b.sendall(bytes([0x30, 0xFF, 0xFF, 0xFF, 0x7F]))
            with self.assertRaises(printer_lan._Stop):
                printer_lan.read_packet(a, printer_lan.time.monotonic() + 1)

    def test_announcement_parsing(self):
        notify = ('NOTIFY * HTTP/1.1\r\nHOST: 239.255.255.250:1990\r\nServer: UPnP/1.0\r\nLocation: 192.168.1.40\r\n'
                  f'NT: {printer_lan.SSDP_TARGET}\r\nUSN: {SERIAL}\r\nCache-Control: max-age=1800\r\n'
                  'DevModel.bambu.com: C12\r\nDevName.bambu.com: Workshop P1S\r\nDevSignal.bambu.com: -52\r\n'
                  'DevConnect.bambu.com: lan\r\nDevBind.bambu.com: free\r\nDevVersion.bambu.com: 01.08.00.00\r\n\r\n').encode()
        device = printer_lan.parse_announcement(notify, '192.168.1.40')
        self.assertEqual(device['serial'], SERIAL)
        self.assertEqual((device['model_code'], device['model_name']), ('C12', 'P1S'))
        self.assertEqual(device['connection_mode'], 'lan')
        self.assertTrue(device['location_matches_sender'])
        self.assertFalse(printer_lan.parse_announcement(notify, '192.168.1.41')['location_matches_sender'])
        self.assertIsNone(printer_lan.parse_announcement(notify.replace(b'3dprinter', b'camera'), '192.168.1.40'))
        self.assertIsNone(printer_lan.parse_announcement(b'\xff' * 10, '192.168.1.40'))
        self.assertIsNone(printer_lan.parse_announcement(notify.replace(SERIAL.encode(), b'bad'), '192.168.1.40'))
        unknown = printer_lan.parse_announcement(notify.replace(b'C12', b'Z9'), '192.168.1.40')
        self.assertEqual((unknown['model_code'], unknown['model_name']), ('Z9', None))

    def test_discovery_bounds_and_unavailable_listener(self):
        for seconds in (0, 11):
            with self.subTest(seconds=seconds), self.assertRaises(ValueError):
                printer_lan.discover(seconds)
        with patch.object(printer_lan.socket, 'socket', side_effect=OSError):
            self.assertEqual(printer_lan.discover(1)['state'], 'listen_unavailable')


if __name__ == '__main__':
    unittest.main()


class SimulatorTests(unittest.TestCase):
    """The local flow simulator must stay compatible with the real client."""

    def test_fake_printer_script_serves_a_synthetic_report(self):
        import importlib.util
        import sys
        spec = importlib.util.spec_from_file_location('fake_bambu_printer', Path(__file__).resolve().parents[1] / 'scripts' / 'fake_bambu_printer.py')
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        probe = socket.socket()
        probe.bind(('127.0.0.1', 0))
        port = probe.getsockname()[1]
        probe.close()
        parser_args = ['--port', str(port), '--access-code', CODE, '--hms', '--duration', '60']
        import argparse
        namespace = argparse.Namespace(host='127.0.0.1', port=port, serial='01S00SYNTH000001', access_code=CODE, model='C12',
                                       cert='printer', state='RUNNING', duration=60.0, nozzle=0.6, hms=True, silent=False, announce=False)
        simulator = module.Simulator(namespace)
        threading.Thread(target=simulator.serve, daemon=True).start()
        printer_lan._LAST_STATUS.clear()
        for _ in range(50):
            try:
                socket.create_connection(('127.0.0.1', port), timeout=0.2).close()
                break
            except OSError:
                threading.Event().wait(0.05)
        result = printer_lan.read_status('127.0.0.1', '01S00SYNTH000001', CODE, port=port, timeout=3, report_window=0.3)
        self.assertEqual(result['connection']['state'], 'reporting', parser_args)
        self.assertEqual(result['print']['state'], 'RUNNING')
        self.assertEqual(result['identity']['product_name'], 'Synthetic Bambu-like printer')
        self.assertEqual(result['print']['hms'][0]['hms_code'], '0700_8000_0002_0001')
        self.assertEqual(result['print']['nozzle']['diameter_mm'], 0.6)
        self.assertEqual(sorted(simulator.requests[-2:]), ['get_version', 'pushall'])
