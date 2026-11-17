"""Sending a verified slice to a printer: pure checks, then the full flow against
the synthetic LAN printer (MQTT over TLS and implicit FTPS on loopback).

The synthetic printer prints nothing; passing here is not printer qualification."""
import argparse
import hashlib
import importlib.util
import io
import json
import socket
import sys
import tempfile
import threading
import time
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from print_agent import printer_lan, printer_send
from print_agent.app import create_app

ROOT = Path(__file__).resolve().parents[1]
CODE = 'abcd1234'
SERIAL = '01S00SYNTH000001'


def sliced(filaments=(('1', 'PLA', '#FFFFFF', '2.03'),), plates=(1,), md5_ok=True, gcode=b'; synthetic\nG1 X1 Y1 E1\n',
           nozzle='0.4'):
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, 'w') as archive:
        for plate in plates:
            archive.writestr(f'Metadata/plate_{plate}.gcode', gcode)
            archive.writestr(f'Metadata/plate_{plate}.gcode.md5', hashlib.md5(gcode if md5_ok else b'x').hexdigest())
        items = ''.join(f'<filament id="{i}" type="{kind}" color="{color}" used_g="{grams}"/>' for i, kind, color, grams in filaments)
        archive.writestr('Metadata/slice_info.config',
                         '<config><plate><metadata key="index" value="1"/><metadata key="printer_model_id" value="C12"/>'
                         f'<metadata key="nozzle_diameters" value="{nozzle}"/><metadata key="prediction" value="837"/>'
                         f'<metadata key="weight" value="2.69"/>{items}</plate></config>')
    return stream.getvalue()


def free_port():
    with socket.socket() as probe:
        probe.bind(('127.0.0.1', 0))
        return probe.getsockname()[1]


def fake_printer(state='IDLE', nozzle=0.4, reject=False):
    spec = importlib.util.spec_from_file_location('fake_bambu_printer', ROOT / 'scripts' / 'fake_bambu_printer.py')
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    mqtt, ftps = free_port(), free_port()
    namespace = argparse.Namespace(host='127.0.0.1', port=mqtt, serial=SERIAL, access_code=CODE, model='C12', cert='printer',
                                   state=state, duration=600.0, nozzle=nozzle, hms=False, silent=False, announce=False,
                                   ftps_port=ftps, reject_print=reject)
    simulator = module.Simulator(namespace)
    threading.Thread(target=simulator.serve, daemon=True).start()
    for port in (mqtt, ftps):
        for _ in range(100):
            try:
                socket.create_connection(('127.0.0.1', port), timeout=0.2).close()
                break
            except OSError:
                time.sleep(0.03)
    return simulator, mqtt, ftps


class SlicedFileTests(unittest.TestCase):
    def test_one_plate_with_gcode_is_described(self):
        summary = printer_send.inspect_sliced(sliced(filaments=(('1', 'PLA', '#ffffff', '2.03'), ('2', 'PLA', '#D32F2F', '0.66'))))
        self.assertEqual(summary['plate'], 1)
        self.assertEqual(summary['printer_model_id'], 'C12')
        self.assertEqual(summary['prediction_seconds'], 837)
        self.assertEqual([(item['id'], item['color'], item['used_g']) for item in summary['filaments']],
                         [(1, '#FFFFFF', 2.03), (2, '#D32F2F', 0.66)])

    def test_unsendable_files_are_refused(self):
        for content, message in ((b'not a zip', 'ZIP'), (sliced(plates=(1, 2)), '한 판'), (sliced(md5_ok=False), 'MD5'),
                                 (sliced(gcode=b'; comments only\n'), 'G-code'), (b'', '없거나')):
            with self.subTest(message=message), self.assertRaisesRegex(printer_send.SendError, message):
                printer_send.inspect_sliced(content)


class MappingTests(unittest.TestCase):
    SLOTS = [{'unit': 0, 'slot': 0, 'material': 'PLA', 'color': 'FFFFFFFF'}, {'unit': 0, 'slot': 1, 'material': 'PETG', 'color': '000000FF'},
             {'unit': 0, 'slot': 2, 'empty': True}, {'unit': 'external', 'slot': None, 'material': 'PLA'}]

    def summary(self, count):
        return {'filaments': [{'id': i + 1, 'type': 'PLA'} for i in range(count)]}

    def test_external_spool_and_ams_trays(self):
        self.assertEqual(printer_send.plan_mapping(self.summary(1), self.SLOTS, ['external'])['ams_mapping'], [-1])
        mapping = printer_send.plan_mapping(self.summary(2), self.SLOTS, [0, 1])
        self.assertEqual((mapping['use_ams'], mapping['ams_mapping']), (True, [0, 1]))
        self.assertIn('PETG', mapping['warnings'][0])

    def test_choices_must_be_complete_distinct_and_reported(self):
        for count, choice, message in ((1, None, '골라'), (2, [0], '2개'), (2, ['external', 0], '외부 스풀'), (1, [2], 'AMS 칸'),
                                       (1, [9], 'AMS 칸'), (2, [0, 0], '같은'), (1, [True], 'AMS 칸')):
            with self.subTest(choice=choice), self.assertRaisesRegex(printer_send.SendError, message):
                printer_send.plan_mapping(self.summary(count), self.SLOTS, choice)

    def test_only_the_project_file_command_is_built(self):
        body = json.loads(printer_send.print_command('pa-1.gcode.3mf', 'a' * 32, 'printer-agent 1', {'use_ams': False, 'ams_mapping': [-1]}, 1))
        self.assertEqual(list(body), ['print'])
        self.assertEqual(body['print']['command'], 'project_file')
        self.assertEqual(body['print']['param'], 'Metadata/plate_1.gcode')
        self.assertEqual(body['print']['url'], 'file:///sdcard/pa-1.gcode.3mf')
        for name in ('../x.gcode.3mf', 'x.gcode', 'a b.gcode.3mf'):
            with self.subTest(name=name), self.assertRaises(printer_send.SendError):
                printer_send.print_command(name, 'a' * 32, 's', {'use_ams': False, 'ams_mapping': [-1]}, 1)

    def test_reviews_are_single_use_and_expire(self):
        store = printer_send.ReviewStore(ttl=60)
        token = store.add({'x': 1})
        self.assertEqual(store.take(token), {'x': 1})
        with self.assertRaises(printer_send.SendError):
            store.take(token)
        expired = printer_send.ReviewStore(ttl=0)
        token = expired.add({'x': 1})
        with self.assertRaises(printer_send.SendError):
            expired.take(token)


class SendFlowTests(unittest.TestCase):
    """API review -> confirmed start against the synthetic printer, recorded on the job."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.app = create_app(Path(self.temp.name), test_mode=True)
        self.client = TestClient(self.app)
        self.headers = {'X-Session-Token': self.client.get('/api/bootstrap').json()['session_token']}
        printer_lan._LAST_STATUS.clear()

    def tearDown(self):
        self.client.close()
        self.temp.cleanup()

    def sliced_job(self, content=None):
        job = self.client.post('/api/models', json={'template': 'tray', 'width': 60, 'depth': 40, 'height': 20}, headers=self.headers).json()
        store = self.app.state.store
        output = store.directory(job['id']) / 'sliced-fixture.gcode.3mf'
        output.write_bytes(content or sliced())
        store.record_slice(job['id'], {'ready': True}, {'status': 'sliced', 'output_path': str(output)})
        return job['id']

    def review(self, job_id, mqtt, slots=None, **extra):
        with patch.object(printer_lan, 'MQTT_PORT', mqtt):
            return self.client.post('/api/printers/print/review', headers=self.headers, json={
                'job_id': job_id, 'host': '127.0.0.1', 'serial': SERIAL, 'access_code': CODE, 'slots': slots, **extra})

    def start(self, token, mqtt, ftps, **extra):
        with patch.object(printer_lan, 'MQTT_PORT', mqtt), patch.object(printer_send, '_ftps_port', lambda: ftps), \
             patch.object(printer_send, 'UPLOAD_SETTLE_SECONDS', 0), patch.object(printer_send, 'START_OBSERVE_SECONDS', 5):
            return self.client.post('/api/printers/print/start', headers=self.headers,
                                    json={'review_token': token, 'access_code': CODE, 'bed_clear_confirmed': True, **extra})

    def test_reviewed_job_is_uploaded_started_and_recorded_without_the_code(self):
        simulator, mqtt, ftps = fake_printer()
        job_id = self.sliced_job()
        options = self.review(job_id, mqtt).json()
        self.assertFalse(options['ready'])
        self.assertIn('골라', options['problems'][0])
        self.assertTrue(any(slot.get('material') == 'PLA' for slot in options['material_slots']))
        self.assertEqual(simulator.print_commands, [])
        printer_lan._LAST_STATUS.clear()
        review = self.review(job_id, mqtt, slots=[0]).json()
        self.assertTrue(review['ready'], review)
        self.assertEqual(review['mapping']['ams_mapping'], [0])
        self.assertNotIn(CODE, json.dumps(review))
        self.assertEqual(simulator.files, {})
        response = self.start(review['review_token'], mqtt, ftps)
        self.assertEqual(response.status_code, 200, response.text)
        result = response.json()
        self.assertEqual(result['status'], 'started', result)
        self.assertEqual(result['stages'], {'printer_ready': True, 'uploaded': True, 'command_sent': True, 'printer_reported_start': True})
        self.assertTrue(result['upload']['size_confirmed'])
        self.assertTrue(result['upload']['matches_mqtt_certificate'])
        stored = simulator.files[review['filename']]
        self.assertEqual(hashlib.sha256(stored).hexdigest(), hashlib.sha256(sliced()).hexdigest())
        command = simulator.print_commands[0]
        self.assertEqual((command['command'], command['use_ams'], command['ams_mapping']), ('project_file', True, [0]))
        self.assertEqual(command['md5'], hashlib.md5(stored).hexdigest())
        job = self.client.get('/api/jobs/' + job_id).json()
        event = job['events'][-1]
        self.assertEqual((event['type'], event['message']), ('printer_send', 'started'))
        self.assertNotIn(CODE, json.dumps(job))
        again = self.start(review['review_token'], mqtt, ftps)
        self.assertEqual(again.status_code, 422)
        self.assertIn('만료', again.json()['detail'])
        self.assertEqual(len(simulator.print_commands), 1)

    def test_busy_printer_and_wrong_nozzle_are_not_offered_a_token(self):
        simulator, mqtt, _ = fake_printer(state='RUNNING')
        job_id = self.sliced_job()
        busy = self.review(job_id, mqtt, slots=['external']).json()
        self.assertFalse(busy['ready'])
        self.assertNotIn('review_token', busy)
        self.assertIn('출력 중', busy['problems'][0])
        _, mqtt, _ = fake_printer(state='IDLE', nozzle=0.6)
        printer_lan._LAST_STATUS.clear()
        wrong = self.review(job_id, mqtt, slots=['external']).json()
        self.assertFalse(wrong['ready'])
        self.assertTrue(any('노즐' in problem for problem in wrong['problems']))
        self.assertEqual(simulator.print_commands, [])

    def test_printer_rejection_and_a_changed_file_are_reported(self):
        simulator, mqtt, ftps = fake_printer(reject=True)
        job_id = self.sliced_job()
        review = self.review(job_id, mqtt, slots=['external']).json()
        result = self.start(review['review_token'], mqtt, ftps).json()
        self.assertEqual(result['status'], 'rejected', result)
        self.assertTrue(result['stages']['command_sent'])
        self.assertFalse(result['stages']['printer_reported_start'])
        printer_lan._LAST_STATUS.clear()
        review = self.review(job_id, mqtt, slots=['external']).json()
        store = self.app.state.store
        uploads = dict(simulator.files)
        with patch.object(store, 'sliced_for_printing', return_value=('title', sliced(gcode=b'G1 X2\n'))):
            changed = self.start(review['review_token'], mqtt, ftps)
        # A different file is refused before anything is uploaded or sent.
        self.assertEqual(changed.status_code, 422)
        self.assertIn('바뀌었습니다', changed.json()['detail'])
        self.assertEqual(simulator.files, uploads)
        self.assertEqual(len(simulator.print_commands), 1)

    def test_ftps_port_override_is_only_an_unprivileged_number(self):
        for value, expected in (('', 990), ('2990', 2990), ('80', 990), ('abc', 990), ('70000', 990)):
            with self.subTest(value=value), patch.dict('os.environ', {'PPA_PRINTER_FTPS_PORT': value}):
                self.assertEqual(printer_send._ftps_port(), expected)

    def test_requests_need_a_slice_confirmation_and_never_echo_codes(self):
        job = self.client.post('/api/models', json={'template': 'tray'}, headers=self.headers).json()
        unsliced = self.client.post('/api/printers/print/review', headers=self.headers, json={
            'job_id': job['id'], 'host': '127.0.0.1', 'serial': SERIAL, 'access_code': CODE})
        self.assertEqual(unsliced.status_code, 422)
        self.assertIn('슬라이스', unsliced.json()['detail'])
        unconfirmed = self.client.post('/api/printers/print/start', headers=self.headers, json={
            'review_token': 'x' * 32, 'access_code': CODE, 'bed_clear_confirmed': False})
        self.assertEqual(unconfirmed.status_code, 422)
        self.assertNotIn(CODE, unconfirmed.text)
        self.assertEqual(self.client.post('/api/printers/print/start', json={
            'review_token': 'x' * 32, 'access_code': CODE, 'bed_clear_confirmed': True}).status_code, 403)


if __name__ == '__main__':
    unittest.main()
