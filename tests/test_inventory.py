"""Filament inventory: entered spools, weigh-ins, recorded use, conflicts, CSV and slicer estimates."""
import csv
import io
import json
from pathlib import Path
import tempfile
import unittest
import zipfile

from fastapi.testclient import TestClient

from print_agent.app import create_app
from print_agent.slicer import _slice_estimates

SPOOL = {'brand': 'Bambu Lab', 'material': 'pla', 'color_name': '검정', 'color_hex': '#232323', 'net_weight_g': 1000,
         'empty_spool_g': 250, 'remaining_g': 1000, 'status': 'sealed', 'location': '책상 서랍', 'price_krw': 25000}


class InventoryApiTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.client = TestClient(create_app(self.root, test_mode=True))
        self.headers = {'X-Session-Token': self.client.get('/api/bootstrap').json()['session_token']}

    def tearDown(self):
        self.client.close()
        self.temporary.cleanup()

    def post(self, path, payload, expected=200):
        response = self.client.post(path, headers=self.headers, json=payload)
        self.assertEqual(response.status_code, expected, response.text)
        return response.json()

    def test_spool_lifecycle_weigh_in_use_and_totals(self):
        spool = self.post('/api/spools', SPOOL, 201)
        self.assertEqual((spool['material'], spool['revision'], spool['remaining_g']), ('PLA', 1, 1000.0))
        weighed = self.post(f'/api/spools/{spool["id"]}/weigh', {'expected_revision': 1, 'gross_g': 1080})
        self.assertEqual((weighed['remaining_g'], weighed['revision'], weighed['status']), (830.0, 2, 'opened'))
        self.assertEqual(weighed['history'][-1]['kind'], 'weighed')
        job = self.post('/api/models', {'template': 'tray', 'width': 60, 'depth': 40, 'height': 15})
        used = self.post(f'/api/spools/{spool["id"]}/use', {'expected_revision': 2, 'grams': 30.5, 'job_id': job['id']})
        self.assertEqual(used['remaining_g'], 799.5)
        self.assertEqual(used['history'][-1]['job_id'], job['id'])
        # The same print is not deducted twice, and an unknown job changes nothing.
        self.assertEqual(self.client.post(f'/api/spools/{spool["id"]}/use', headers=self.headers,
                                          json={'expected_revision': 3, 'grams': 30.5, 'job_id': job['id']}).status_code, 422)
        self.assertEqual(self.client.post(f'/api/spools/{spool["id"]}/use', headers=self.headers,
                                          json={'expected_revision': 3, 'grams': 5, 'job_id': 'f' * 32}).status_code, 404)
        second = self.post('/api/spools', {**SPOOL, 'material': 'PETG', 'color_name': '흰색', 'remaining_g': 100, 'price_krw': None}, 201)
        listed = self.client.get('/api/spools').json()
        self.assertEqual(listed['totals']['spools'], 2)
        self.assertEqual(listed['totals']['by_material'], {'PETG': 100.0, 'PLA': 799.5})
        self.assertEqual(listed['totals']['low_stock_ids'], [second['id']])
        self.assertEqual(listed['totals']['remaining_value_krw'], round(25000 * 799.5 / 1000))
        emptied = self.post(f'/api/spools/{second["id"]}/use', {'expected_revision': 1, 'grams': 500})
        self.assertEqual((emptied['remaining_g'], emptied['status']), (0.0, 'empty'))
        self.assertEqual(self.client.get('/api/spools').json()['totals']['spools'], 1)

    def test_stale_pages_conflict_and_invalid_values_are_refused(self):
        spool = self.post('/api/spools', SPOOL, 201)
        edited = self.client.put(f'/api/spools/{spool["id"]}', headers=self.headers,
                                 json={**SPOOL, 'location': '선반 2', 'expected_revision': 1})
        self.assertEqual(edited.status_code, 200, edited.text)
        stale = self.client.put(f'/api/spools/{spool["id"]}', headers=self.headers,
                                json={**SPOOL, 'location': '선반 9', 'expected_revision': 1})
        self.assertEqual(stale.status_code, 409)
        self.assertEqual((stale.json()['code'], stale.json()['current']['location']), ('inventory_conflict', '선반 2'))
        for change in ({'remaining_g': 1200}, {'color_hex': 'red'}, {'material': 'PLA;rm'}, {'net_weight_g': 0},
                       {'status': 'lost'}, {'price_krw': 1.5}, {'diameter_mm': 3.0}):
            with self.subTest(change=change):
                self.assertEqual(self.client.post('/api/spools', headers=self.headers, json={**SPOOL, **change}).status_code, 422)
        deleted = self.client.request('DELETE', f'/api/spools/{spool["id"]}', headers=self.headers, json={'expected_revision': 1})
        self.assertEqual(deleted.status_code, 409)
        deleted = self.client.request('DELETE', f'/api/spools/{spool["id"]}', headers=self.headers, json={'expected_revision': 2})
        self.assertEqual(deleted.status_code, 204)
        self.assertEqual(self.client.get('/api/spools').json()['spools'], [])

    def test_csv_export_is_spreadsheet_safe_and_records_stay_readable(self):
        self.post('/api/spools', {**SPOOL, 'notes': '=HYPERLINK("x")', 'location': '+선반'}, 201)
        broken = self.root / 'spools' / ('a' * 32 + '.json')
        broken.write_text('{broken', encoding='utf-8')
        listed = self.client.get('/api/spools').json()
        self.assertEqual((len(listed['spools']), listed['unreadable']), (1, 1))
        response = self.client.get('/api/spools.csv')
        self.assertEqual(response.status_code, 200)
        rows = list(csv.reader(io.StringIO(response.content.decode('utf-8-sig'))))
        self.assertEqual(rows[0][0], '브랜드')
        self.assertEqual(rows[1][9], "'+선반")
        self.assertEqual(rows[1][11], "'=HYPERLINK(\"x\")")
        self.assertEqual(broken.read_text(encoding='utf-8'), '{broken')  # preserved, not repaired

    def test_manual_edits_apply_the_same_weight_rules_as_weigh_ins(self):
        spool = self.post('/api/spools', SPOOL, 201)
        path = f'/api/spools/{spool["id"]}'
        opened = self.client.put(path, headers=self.headers, json={**SPOOL, 'remaining_g': 700, 'expected_revision': 1})
        self.assertEqual(opened.status_code, 200, opened.text)
        self.assertEqual((opened.json()['status'], opened.json()['remaining_g']), ('opened', 700.0))
        # A status the person picked is kept when the amount does not contradict it.
        drying = self.client.put(path, headers=self.headers, json={**SPOOL, 'remaining_g': 600, 'status': 'drying', 'expected_revision': 2})
        self.assertEqual((drying.json()['status'], drying.json()['revision']), ('drying', 3))
        # Zero grams is empty whatever status the form still carried.
        emptied = self.client.put(path, headers=self.headers, json={**SPOOL, 'remaining_g': 0, 'status': 'loaded', 'expected_revision': 3})
        self.assertEqual(emptied.json()['status'], 'empty')
        self.assertEqual(self.client.get('/api/spools').json()['totals']['spools'], 0)
        # Refilled to the new-spool weight it may be sealed again.
        resealed = self.client.put(path, headers=self.headers, json={**SPOOL, 'status': 'sealed', 'expected_revision': 4})
        self.assertEqual((resealed.json()['status'], resealed.json()['remaining_g']), ('sealed', 1000.0))
        # A spool entered as sealed with less filament than a full spool is opened.
        partial = self.post('/api/spools', {**SPOOL, 'remaining_g': 500}, 201)
        self.assertEqual(partial['status'], 'opened')

    def test_damaged_records_are_preserved_skipped_and_counted(self):
        spool = self.post('/api/spools', SPOOL, 201)
        path = self.root / 'spools' / f'{spool["id"]}.json'
        only_identity = {key: spool[key] for key in ('id', 'revision')}
        path.write_text(json.dumps(only_identity), encoding='utf-8')
        listed = self.client.get('/api/spools')
        self.assertEqual(listed.status_code, 200, listed.text)
        self.assertEqual((listed.json()['spools'], listed.json()['unreadable']), ([], 1))
        exported = self.client.get('/api/spools.csv')
        self.assertEqual(len(list(csv.reader(io.StringIO(exported.content.decode('utf-8-sig'))))), 1)
        self.assertEqual(path.read_text(encoding='utf-8'), json.dumps(only_identity))  # preserved, not repaired
        for damaged in ({**only_identity, 'status': 'opened'}, {**spool, 'remaining_g': '800'}, {**spool, 'diameter_mm': True},
                        {**spool, 'status': 'lost'}, {**spool, 'history': [{'kind': 'created'}]},
                        {**spool, 'deductions': [{'job_id': 'not-a-job'}]}):
            with self.subTest(damaged=damaged):
                path.write_text(json.dumps(damaged), encoding='utf-8')
                self.assertEqual(self.client.get('/api/spools').json()['unreadable'], 1)
        self.assertEqual(self.client.put(f'/api/spools/{spool["id"]}', headers=self.headers,
                                         json={**SPOOL, 'expected_revision': 1}).status_code, 409)
        path.write_text(json.dumps(spool), encoding='utf-8')
        self.assertEqual(len(self.client.get('/api/spools').json()['spools']), 1)

    def test_deduction_identities_outlive_the_bounded_history(self):
        spool = self.post('/api/spools', SPOOL, 201)
        job = self.post('/api/models', {'template': 'tray', 'width': 60, 'depth': 40, 'height': 15})
        used = self.post(f'/api/spools/{spool["id"]}/use', {'expected_revision': 1, 'grams': 10, 'job_id': job['id']})
        self.assertEqual(used['deductions'], [{'job_id': job['id'], 'at': used['updated_at'], 'grams': 10.0}])
        weighed = used
        for _ in range(200):  # the display history keeps only its latest 200 entries
            weighed = self.post(f'/api/spools/{spool["id"]}/weigh', {'expected_revision': weighed['revision'], 'gross_g': weighed['remaining_g'] + 250})
        self.assertEqual(len(weighed['history']), 200)
        self.assertNotIn(job['id'], [entry.get('job_id') for entry in weighed['history']])
        self.assertEqual([entry['job_id'] for entry in weighed['deductions']], [job['id']])
        again = self.client.post(f'/api/spools/{spool["id"]}/use', headers=self.headers,
                                 json={'expected_revision': weighed['revision'], 'grams': 10, 'job_id': job['id']})
        self.assertEqual(again.status_code, 422)
        self.assertEqual(self.client.get('/api/spools').json()['spools'][0]['remaining_g'], weighed['remaining_g'])

    def test_records_without_deduction_identities_stay_readable_and_migrate(self):
        spool = self.post('/api/spools', SPOOL, 201)
        job = self.post('/api/models', {'template': 'tray', 'width': 60, 'depth': 40, 'height': 15})
        path = self.root / 'spools' / f'{spool["id"]}.json'
        stored = json.loads(path.read_text(encoding='utf-8'))
        del stored['deductions']  # a file written before deduction identities existed
        stored['history'].append({'at': stored['updated_at'], 'kind': 'used', 'grams': 20.0, 'job_id': job['id'], 'remaining_g': 980.0})
        stored.update({'remaining_g': 980.0, 'status': 'opened', 'revision': 2})
        path.write_text(json.dumps(stored), encoding='utf-8')
        listed = self.client.get('/api/spools').json()
        self.assertEqual((listed['unreadable'], listed['spools'][0]['remaining_g']), (0, 980.0))
        self.assertEqual([entry['job_id'] for entry in listed['spools'][0]['deductions']], [job['id']])
        self.assertEqual(self.client.post(f'/api/spools/{spool["id"]}/use', headers=self.headers,
                                          json={'expected_revision': 2, 'grams': 20, 'job_id': job['id']}).status_code, 422)
        weighed = self.post(f'/api/spools/{spool["id"]}/weigh', {'expected_revision': 2, 'gross_g': 1200})
        self.assertEqual([entry['job_id'] for entry in weighed['deductions']], [job['id']])
        self.assertEqual([entry['job_id'] for entry in json.loads(path.read_text(encoding='utf-8'))['deductions']], [job['id']])


class SliceEstimateTests(unittest.TestCase):
    def test_slicer_estimates_are_read_from_the_output(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'out.gcode.3mf'
            with zipfile.ZipFile(path, 'w') as archive:
                archive.writestr('Metadata/slice_info.config', '<config><plate><metadata key="prediction" value="837"/>'
                                                              '<metadata key="weight" value="2.694"/></plate></config>')
            self.assertEqual(_slice_estimates(path), {'estimated_time_seconds': 837, 'filament_grams': 2.69})
            with zipfile.ZipFile(path, 'w') as archive:
                archive.writestr('Metadata/slice_info.config', '<config><plate><metadata key="weight" value="nan"/></plate></config>')
            self.assertEqual(_slice_estimates(path), {})
            self.assertEqual(_slice_estimates(Path(directory) / 'missing.3mf'), {})


if __name__ == '__main__':
    unittest.main()
