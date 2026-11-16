"""Synthetic Bambu LAN printer for local flow checks. NOT a real printer.

Serves the bounded MQTT-over-TLS subset used by ``print_agent.printer_lan`` on a
loopback address with the test-only certificates in tests/fixtures/printer_lan, and
optionally sends SSDP NOTIFY announcements to the local discovery port. Every value
it reports is synthetic. A passing check against it is not printer qualification.

    python scripts/fake_bambu_printer.py --access-code abcd1234 --announce

Then open the app's 프린터 상태 view, enter 127.0.0.1, the serial below and the code.
"""
import argparse
import json
import socket
import ssl
import struct
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / 'tests' / 'fixtures' / 'printer_lan'
SSDP_TARGET = 'urn:bambulab-com:device:3dprinter:1'


def remaining_length(length):
    out = bytearray()
    while True:
        byte, length = length % 128, length // 128
        out.append(byte | (0x80 if length else 0))
        if not length:
            return bytes(out)


def read_packet(conn):
    header = conn.recv(1)
    if not header:
        raise ConnectionError
    length, multiplier = 0, 1
    while True:
        byte = conn.recv(1)
        if not byte:
            raise ConnectionError
        length += (byte[0] & 0x7F) * multiplier
        if not byte[0] & 0x80:
            break
        multiplier *= 128
    body = b''
    while len(body) < length:
        chunk = conn.recv(length - len(body))
        if not chunk:
            raise ConnectionError
        body += chunk
    return header[0] >> 4, body


def publish(conn, topic, message):
    data = topic.encode()
    body = struct.pack('!H', len(data)) + data + json.dumps(message).encode()
    conn.sendall(bytes([0x30]) + remaining_length(len(body)) + body)


class Simulator:
    def __init__(self, args):
        self.args = args
        self.started = time.monotonic()
        self.lock = threading.Lock()
        self.requests = []

    def report(self):
        a = self.args
        elapsed = time.monotonic() - self.started
        progress = min(100, int(elapsed / a.duration * 100)) if a.state == 'RUNNING' else (100 if a.state == 'FINISH' else 0)
        state = 'FINISH' if a.state == 'RUNNING' and progress >= 100 else a.state
        total = 120
        report = {
            'command': 'push_status', 'gcode_state': state, 'mc_percent': progress,
            'mc_remaining_time': max(0, int((a.duration - elapsed) / 60)) if state == 'RUNNING' else 0,
            'layer_num': total * progress // 100, 'total_layer_num': total,
            'subtask_name': 'synthetic_tray_120x80', 'gcode_file': 'synthetic.gcode',
            'nozzle_temper': 219.6 if state == 'RUNNING' else 26.0, 'nozzle_target_temper': 220 if state == 'RUNNING' else 0,
            'bed_temper': 54.8 if state == 'RUNNING' else 25.5, 'bed_target_temper': 55 if state == 'RUNNING' else 0,
            'print_error': 0x0300400C if state == 'FAILED' else 0,
            'hms': [{'attr': 0x07008000, 'code': 0x00020001}] if a.hms else [],
            'nozzle_diameter': '0.4', 'nozzle_type': 'stainless_steel', 'wifi_signal': '-48dBm',
            'ams': {'ams': [{'id': '0', 'tray': [
                {'id': '0', 'tray_type': 'PLA', 'tray_sub_brands': 'PLA Basic', 'tray_color': 'FFFFFFFF', 'tray_info_idx': 'GFA00',
                 'nozzle_temp_min': '190', 'nozzle_temp_max': '230'},
                {'id': '1', 'tray_type': 'PETG', 'tray_sub_brands': 'PETG HF', 'tray_color': '000000FF', 'tray_info_idx': 'GFG02'},
                {'id': '2'}, {'id': '3'}]}]},
        }
        return report

    def handle(self, raw):
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(FIXTURES / f'{self.args.cert}-cert.pem', FIXTURES / f'{self.args.cert}-key.pem')
        serial = self.args.serial
        try:
            with context.wrap_socket(raw, server_side=True) as conn:
                conn.settimeout(15)
                kind, body = read_packet(conn)
                if kind != 1:
                    return
                offset = 2 + struct.unpack('!H', body[:2])[0] + 4
                fields = []
                while offset < len(body):
                    size = struct.unpack('!H', body[offset:offset + 2])[0]
                    fields.append(body[offset + 2:offset + 2 + size].decode())
                    offset += 2 + size
                accepted = fields[1:] == ['bblp', self.args.access_code]
                conn.sendall(bytes([0x20, 2, 0, 0 if accepted else 5]))
                print(f'[fake-printer] CONNECT {"accepted" if accepted else "rejected (wrong code)"}', flush=True)
                if not accepted:
                    return
                while True:
                    kind, body = read_packet(conn)
                    if kind == 8:
                        topic = body[4:4 + struct.unpack('!H', body[2:4])[0]].decode()
                        ok = topic == f'device/{serial}/report'
                        conn.sendall(bytes([0x90, 3]) + body[:2] + bytes([0 if ok else 0x80]))
                    elif kind == 3:
                        size = struct.unpack('!H', body[:2])[0]
                        topic, payload = body[2:2 + size].decode(), json.loads(body[2 + size:])
                        command = next(iter(payload.values())).get('command')
                        with self.lock:
                            self.requests.append(command)
                        print(f'[fake-printer] request {command} on {topic}', flush=True)
                        if topic != f'device/{serial}/request' or self.args.silent:
                            continue
                        if command == 'pushall':
                            publish(conn, f'device/{serial}/report', {'print': self.report()})
                        elif command == 'get_version':
                            publish(conn, f'device/{serial}/report', {'info': {'command': 'get_version', 'module': [
                                {'name': 'ota', 'sw_ver': '01.08.00.00', 'hw_ver': '', 'sn': serial},
                                {'name': 'mc', 'sw_ver': '00.00.29.00', 'hw_ver': 'MC07', 'product_name': 'Synthetic Bambu-like printer'}]}})
                    elif kind == 14:
                        return
        except (OSError, ssl.SSLError, ConnectionError, ValueError, StopIteration):
            pass

    def announce(self):
        message = ('NOTIFY * HTTP/1.1\r\nHOST: 239.255.255.250:1990\r\nServer: UPnP/1.0\r\n'
                   f'Location: {self.args.host}\r\nNT: {SSDP_TARGET}\r\nUSN: {self.args.serial}\r\n'
                   f'DevModel.bambu.com: {self.args.model}\r\nDevName.bambu.com: Synthetic printer\r\n'
                   'DevSignal.bambu.com: -48\r\nDevConnect.bambu.com: lan\r\nDevBind.bambu.com: free\r\n'
                   'DevVersion.bambu.com: 01.08.00.00\r\n\r\n').encode()
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            while True:
                try:
                    sock.sendto(message, (self.args.host, 2021))
                except OSError:
                    pass
                time.sleep(1)

    def serve(self):
        listener = socket.socket()
        listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        listener.bind((self.args.host, self.args.port))
        listener.listen(4)
        print(f'[fake-printer] SYNTHETIC printer {self.args.serial} on {self.args.host}:{self.args.port} '
              f'(cert={self.args.cert}, state={self.args.state})', flush=True)
        if self.args.announce:
            threading.Thread(target=self.announce, daemon=True).start()
        while True:
            raw, _ = listener.accept()
            threading.Thread(target=self.handle, args=(raw,), daemon=True).start()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=8883)
    parser.add_argument('--serial', default='01S00SYNTH000001')
    parser.add_argument('--access-code', required=True)
    parser.add_argument('--model', default='C12')
    parser.add_argument('--cert', choices=('printer', 'other'), default='printer')
    parser.add_argument('--state', choices=('IDLE', 'RUNNING', 'PAUSE', 'FINISH', 'FAILED'), default='RUNNING')
    parser.add_argument('--duration', type=float, default=600, help='seconds for a synthetic RUNNING job to reach 100%%')
    parser.add_argument('--hms', action='store_true', help='include one synthetic HMS entry')
    parser.add_argument('--silent', action='store_true', help='accept and subscribe but never report')
    parser.add_argument('--announce', action='store_true', help='send SSDP NOTIFY to host:2021 every second')
    Simulator(parser.parse_args(argv)).serve()


if __name__ == '__main__':
    main()
