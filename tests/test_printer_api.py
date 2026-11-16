import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from print_agent import printer_lan
from print_agent.app import create_app
from tests.test_printer_lan import CODE, FULL_REPORT, SERIAL, VERSION, FakePrinter


class PrinterAPITests(unittest.TestCase):
    def setUp(self):
        printer_lan._LAST_STATUS.clear()
        self.temp = tempfile.TemporaryDirectory()
        self.client = TestClient(create_app(Path(self.temp.name), test_mode=True))
        self.headers = {'X-Session-Token': self.client.get('/api/bootstrap').json()['session_token']}

    def tearDown(self):
        self.client.close()
        self.temp.cleanup()

    def status(self, **values):
        payload = {'host': '127.0.0.1', 'serial': SERIAL, 'access_code': CODE, **values}
        return self.client.post('/api/printers/status', json=payload, headers=self.headers)

    def test_status_reads_fake_printer_without_returning_access_code(self):
        printer = FakePrinter(reports=[(f'device/{SERIAL}/report', FULL_REPORT), (f'device/{SERIAL}/report', VERSION)])
        with patch.object(printer_lan, 'MQTT_PORT', printer.port):
            response = self.status()
        printer.thread.join(3)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['connection']['state'], 'reporting')
        self.assertEqual(data['target'], {'host': '127.0.0.1', 'serial': SERIAL, 'port': printer.port})
        self.assertEqual(data['print']['state'], 'RUNNING')
        self.assertNotIn(CODE, response.text)
        self.assertEqual(response.headers['cache-control'], 'no-store')

    def test_status_requires_session_and_strict_payload(self):
        payload = {'host': '127.0.0.1', 'serial': SERIAL, 'access_code': CODE}
        self.assertEqual(self.client.post('/api/printers/status', json=payload).status_code, 403)
        self.assertEqual(self.status(command='print').status_code, 422)
        rejected = self.status(access_code=['SECRET-CODE-9'])
        self.assertEqual(rejected.status_code, 422)
        self.assertNotIn('SECRET-CODE-9', rejected.text)
        too_long = self.status(access_code='S' * 65)
        self.assertNotIn('S' * 65, too_long.text)

    def test_public_or_named_hosts_are_rejected_before_network(self):
        with patch.object(printer_lan.socket, 'create_connection') as connect:
            for host in ('8.8.8.8', 'printer.local'):
                response = self.status(host=host)
                self.assertEqual(response.status_code, 422)
                self.assertNotIn(CODE, response.text)
        connect.assert_not_called()

    def test_busy_printer_returns_retry(self):
        printer_lan._LAST_STATUS[('127.0.0.1', SERIAL)] = printer_lan.time.monotonic()
        response = self.status()
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()['code'], 'printer_busy')
        self.assertEqual(response.headers['retry-after'], '5')

    def test_discovery_is_bounded(self):
        self.assertEqual(self.client.post('/api/printers/discover', json={'seconds': 30}, headers=self.headers).status_code, 422)
        result = {'state': 'listened', 'observed_at': 'x', 'seconds': 2.0, 'devices': []}
        with patch.object(printer_lan, 'discover', return_value=result) as discover:
            response = self.client.post('/api/printers/discover', json={'seconds': 2}, headers=self.headers)
        self.assertEqual(response.json(), result)
        discover.assert_called_once_with(2)


if __name__ == '__main__':
    unittest.main()
