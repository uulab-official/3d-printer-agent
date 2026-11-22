import json
import re
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from print_agent import printer_beds, printer_lan
from print_agent.app import create_app


class PrinterBedTests(unittest.TestCase):
    def test_every_known_bambu_model_code_has_a_plate_and_ids_are_unique(self):
        codes = {bed['model_code'] for bed in printer_beds.BEDS if bed['vendor'] == 'Bambu Lab'}
        self.assertEqual(codes, set(printer_lan.MODEL_NAMES))
        for bed in printer_beds.BEDS:
            if bed['model_code']:
                self.assertEqual(printer_lan.MODEL_NAMES[bed['model_code']], bed['name'])
        self.assertEqual(len({bed['id'] for bed in printer_beds.BEDS}), len(printer_beds.BEDS))

    def test_studio_values_for_the_printers_in_this_project(self):
        beds = {bed['id']: bed for bed in printer_beds.BEDS}
        x2d, u1, x1c = beds['bambu-n6'], beds['snapmaker-u1'], beds['bambu-bl-p001']
        self.assertEqual((x2d['width'], x2d['depth'], x2d['height'], x2d['shared_x']), (256, 256, 261, [20.5, 256]))
        self.assertEqual((u1['width'], u1['depth'], u1['height']), (270, 270, 270))
        self.assertIn('Snapmaker', u1['source'])
        self.assertEqual(x1c['exclude'], [[0, 0, 18, 28]])
        self.assertTrue(all(bed['source'] for bed in printer_beds.BEDS))

    def test_fit_reports_overflow_rotation_and_the_two_nozzle_region(self):
        beds = {bed['id']: bed for bed in printer_beds.BEDS}
        self.assertEqual(printer_beds.fit((120, 80, 35), beds['bambu-n1']),
                         {'fits': True, 'rotate': False, 'over': [0, 0, 0], 'shared_over': None})
        over = printer_beds.fit((200, 80, 190), beds['bambu-n1'])
        self.assertEqual((over['fits'], over['rotate'], over['over']), (False, False, [20.0, 0, 10.0]))
        turned = printer_beds.fit((340, 300, 50), beds['bambu-o1s'])  # H2S 340 × 320: fits as is
        self.assertTrue(turned['fits'])
        rotate = printer_beds.fit((300, 335, 50), beds['bambu-o1s'])
        self.assertEqual((rotate['fits'], rotate['rotate']), (False, True))
        shared = printer_beds.fit((250, 100, 20), beds['bambu-n6'])
        self.assertEqual((shared['fits'], shared['shared_over']), (True, 14.5))

    def test_bootstrap_serves_copies_with_scope(self):
        with tempfile.TemporaryDirectory() as folder:
            client = TestClient(create_app(Path(folder), test_mode=True))
            data = client.get('/api/bootstrap').json()['printer_beds']
        self.assertEqual(len(data['beds']), len(printer_beds.BEDS))
        self.assertIn('참고용', data['scope'])
        data['beds'][0]['width'] = 1
        self.assertNotEqual(printer_beds.printer_beds()['beds'][0]['width'], 1)

    def test_browser_fit_mirrors_the_server(self):
        source = (Path(__file__).resolve().parents[1] / 'print_agent' / 'static' / 'app.js').read_text(encoding='utf-8')
        self.assertIsNotNone(re.search(r'function bedFit\(size, bed\)', source))
        self.assertIn('Mirrors printer_beds.fit()', source)
        json.dumps(printer_beds.printer_beds())  # serializable


if __name__ == '__main__':
    unittest.main()
