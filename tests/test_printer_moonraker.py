import importlib.util
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import socket
import sys
import threading
import unittest

from fastapi.testclient import TestClient

from print_agent import printer_moonraker

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('fake_moonraker', ROOT / 'scripts' / 'fake_moonraker.py')
fake = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = fake
spec.loader.exec_module(fake)


def read(port, **kwargs):
    printer_moonraker._LAST_STATUS.clear()
    return printer_moonraker.read_status('127.0.0.1', port, **kwargs)


class MoonrakerValidationTests(unittest.TestCase):
    def test_only_private_literals_ports_and_bounded_keys_are_accepted(self):
        for host in ('', 'printer.local', '8.8.8.8', '224.0.0.1', '0.0.0.0'):
            with self.subTest(host=host), self.assertRaises(ValueError):
                printer_moonraker.validate_target(host)
        for port in (0, 70000, True, '7125'):
            with self.subTest(port=port), self.assertRaises(ValueError):
                printer_moonraker.validate_target('192.168.0.30', port)
        with self.assertRaises(ValueError):
            printer_moonraker.validate_target('192.168.0.30', 7125, 'short')
        with self.assertRaises(ValueError):
            printer_moonraker.validate_target('192.168.0.30', 7125, 'has a space in it')
        self.assertEqual(printer_moonraker.validate_target(' 192.168.0.30 ', 7125, '  '), ('192.168.0.30', 7125, None))


class MoonrakerStatusTests(unittest.TestCase):
    def serve(self, **options):
        server, port = fake.start_in_thread(**options)
        self.addCleanup(server.shutdown)
        return port

    def test_a_printing_four_tool_printer_is_reported_in_the_shared_shape(self):
        result = read(self.serve())
        self.assertEqual(result['kind'], 'moonraker')
        self.assertEqual(result['connection']['state'], 'reporting')
        printing = result['print']
        self.assertEqual((printing['state'], printing['state_label']), ('RUNNING', '출력 중'))
        self.assertEqual((printing['progress_percent'], printing['layer'], printing['total_layers']), (40, 42, 120))
        self.assertEqual(printing['remaining_minutes'], 30)  # 1200 s at 40 % → 1800 s left
        self.assertTrue(printing['remaining_is_estimate'])
        self.assertEqual([tool['name'] for tool in printing['tools']], ['extruder', 'extruder1', 'extruder2', 'extruder3'])
        self.assertEqual(printing['active_tool'], 'extruder1')
        self.assertEqual(printing['temperatures_c']['nozzle'], 219.6)
        self.assertEqual(printing['temperatures_c']['bed'], 59.8)
        self.assertEqual(printing['material_slots'], [])
        self.assertEqual(result['identity']['klipper_version'], 'v0.13.0-synthetic')
        self.assertEqual(result['identity']['klippy_state_label'], '준비됨')
        self.assertNotIn('api_key', json.dumps(result))

    def test_states_map_to_the_shared_vocabulary(self):
        for raw, expected in (('standby', 'IDLE'), ('paused', 'PAUSE'), ('complete', 'FINISH'),
                              ('cancelled', 'CANCELLED'), ('error', 'FAILED')):
            with self.subTest(state=raw):
                result = read(self.serve(state=raw))
                self.assertEqual(result['print']['state'], expected)
                self.assertIsNone(result['print']['remaining_minutes'])
        failed = read(self.serve(state='error'))
        self.assertEqual(failed['print']['error_message'], 'Synthetic MCU shutdown')

    def test_api_key_is_sent_and_a_wrong_or_missing_key_is_a_rejection(self):
        port = self.serve(api_key='synthetic-key-1234')
        self.assertEqual(read(port)['connection']['state'], 'access_rejected')
        # A rejected read does not reach Klipper, so the corrected key may be tried at once.
        self.assertEqual(printer_moonraker.read_status('127.0.0.1', port, 'synthetic-key-1234')['connection']['state'], 'reporting')
        self.assertEqual(read(port, api_key='wrong-key-12345')['connection']['state'], 'access_rejected')
        self.assertEqual(read(port, api_key='synthetic-key-1234')['connection']['state'], 'reporting')

    def test_klipper_not_ready_reports_identity_without_print_state(self):
        result = read(self.serve(klippy='shutdown'))
        self.assertEqual(result['connection']['state'], 'klippy_not_ready')
        self.assertIsNone(result['print'])
        self.assertEqual(result['identity']['klippy_state_label'], '정지됨(재시작 필요)')

    def test_unreachable_and_non_moonraker_services(self):
        with socket.socket() as probe:
            probe.bind(('127.0.0.1', 0))
            closed = probe.getsockname()[1]
        self.assertEqual(read(closed)['connection']['state'], 'unreachable')

        class Other(BaseHTTPRequestHandler):
            def do_GET(self):  # noqa: N802
                body = b'<html>router</html>'
                self.send_response(200)
                self.send_header('Content-Length', str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *args):
                pass

        server = ThreadingHTTPServer(('127.0.0.1', 0), Other)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        self.assertEqual(read(server.server_address[1])['connection']['state'], 'not_moonraker')

    def test_repeated_reads_of_one_printer_are_spaced(self):
        port = self.serve()
        read(port)
        with self.assertRaises(printer_moonraker.PrinterBusy):
            printer_moonraker.read_status('127.0.0.1', port)

    def test_normalize_keeps_missing_values_unknown(self):
        printing = printer_moonraker.normalize_status({'print_stats': {'state': 'weird'}, 'extruder': {'temperature': float('nan')}})
        self.assertEqual((printing['state'], printing['state_label']), ('WEIRD', '알 수 없는 상태(weird)'))
        self.assertIsNone(printing['temperatures_c']['nozzle'])
        self.assertIsNone(printing['progress_percent'])
        self.assertEqual(printer_moonraker.normalize_status(None)['tools'], [])


class MoonrakerApiTests(unittest.TestCase):
    def setUp(self):
        import tempfile
        from print_agent.app import create_app
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.client = TestClient(create_app(Path(self.tmp.name), test_mode=True))
        self.headers = {'X-Session-Token': self.client.get('/api/bootstrap').json()['session_token']}

    def test_status_route_reads_once_and_never_echoes_the_key(self):
        server, port = fake.start_in_thread(api_key='synthetic-key-1234')
        self.addCleanup(server.shutdown)
        printer_moonraker._LAST_STATUS.clear()
        response = self.client.post('/api/printers/moonraker/status', headers=self.headers,
                                    json={'host': '127.0.0.1', 'port': port, 'api_key': 'synthetic-key-1234'})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()['connection']['state'], 'reporting')
        self.assertNotIn('synthetic-key-1234', response.text)
        bad = self.client.post('/api/printers/moonraker/status', headers=self.headers,
                               json={'host': '127.0.0.1', 'port': 0, 'api_key': 'synthetic-key-1234'})
        self.assertEqual(bad.status_code, 422)
        self.assertNotIn('synthetic-key-1234', bad.text)
        public = self.client.post('/api/printers/moonraker/status', headers=self.headers, json={'host': '8.8.8.8'})
        self.assertIn(public.status_code, (400, 422))


if __name__ == '__main__':
    unittest.main()
