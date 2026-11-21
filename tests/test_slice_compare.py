"""Side-by-side slices: only listed process keys change, estimates are kept, the current slice is not."""
import copy
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from print_agent import slice_compare
from print_agent.app import create_app
from tests.test_printer_send import sliced

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from qualify_bambu import synthetic_fixture  # noqa: E402


def bundle(nozzle=('0.4',)):
    value, _ = synthetic_fixture()
    value = copy.deepcopy(value)
    value['machine']['nozzle_diameter'] = list(nozzle)
    return value


class VariantTests(unittest.TestCase):
    def test_variants_follow_the_nozzle_and_the_supplied_process(self):
        b = bundle()
        self.assertEqual(slice_compare.overrides(b, 'original'), {})
        self.assertEqual(slice_compare.overrides(b, 'fine'), {'layer_height': '0.12'})
        self.assertEqual(slice_compare.overrides(b, 'fast'), {'layer_height': '0.28', 'sparse_infill_density': '10%'})
        strong = slice_compare.overrides(b, 'strong')
        self.assertEqual(strong['sparse_infill_density'], '40%')
        self.assertEqual(int(strong['wall_loops']), int(b['process']['wall_loops']) + 2)
        self.assertEqual(slice_compare.overrides(bundle(('0.6',)), 'fast')['layer_height'], '0.42')
        self.assertEqual(slice_compare.overrides(bundle(('0.2',)), 'fine')['layer_height'], '0.06')

    def test_only_listed_process_keys_change(self):
        b = bundle()
        changed = slice_compare.variant_bundle(b, 'strong')
        self.assertEqual((changed['machine'], changed['filaments'], changed['plate_type']), (b['machine'], b['filaments'], b['plate_type']))
        differing = {key for key in set(b['process']) | set(changed['process']) if b['process'].get(key) != changed['process'].get(key)}
        self.assertTrue(differing <= set(slice_compare.VARIANT_KEYS))
        self.assertEqual(b, bundle())  # the supplied bundle is not modified

    def test_unreadable_values_are_refused(self):
        b = bundle()
        b['machine']['nozzle_diameter'] = ['x']
        with self.assertRaisesRegex(ValueError, 'nozzle_diameter'):
            slice_compare.overrides(b, 'fine')
        b = bundle()
        b['process']['wall_loops'] = 'many'
        with self.assertRaisesRegex(ValueError, 'wall_loops'):
            slice_compare.overrides(b, 'strong')

    def test_summary_reads_estimates_layers_and_supports(self):
        gcode = b'; synthetic\n; CHANGE_LAYER\nG1 X1 Y1 E1\n; CHANGE_LAYER\n; FEATURE: Support\nG1 X2 Y2 E1\n'
        summary = slice_compare.summarize(sliced(gcode=gcode))
        self.assertEqual(summary, {'minutes': 13.9, 'grams': 2.69, 'layers': 2, 'support': True})  # 837 s


class CompareApiTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.app = create_app(self.root, test_mode=True)
        self.client = TestClient(self.app)
        self.headers = {'X-Session-Token': self.client.get('/api/bootstrap').json()['session_token']}
        self.job = self.client.post('/api/models', headers=self.headers, json={'template': 'cup', 'width': 70, 'height': 100}).json()

    def tearDown(self):
        self.client.close()
        self.temporary.cleanup()

    def compare(self, **extra):
        return self.client.post('/api/slice/compare', headers=self.headers,
                                json={'job_id': self.job['id'], 'config_bundle': bundle(), **extra})

    def test_each_variant_is_prepared_and_run_and_only_estimates_are_kept(self):
        seen = []

        def prepare(input_path, work, config, **kwargs):
            seen.append((Path(work).name, config['process']['layer_height'], kwargs['require_volume_review']))
            output = Path(work) / 'out.gcode.3mf'
            output.parent.mkdir(parents=True)
            layers = {'0.12': 3, '0.28': 1}.get(config['process']['layer_height'], 2)
            output.write_bytes(sliced(gcode=b'; synthetic\n' + b'; CHANGE_LAYER\nG1 X1 Y1 E1\n' * layers))
            return {'ready': True, 'output_path': str(output), 'diagnostics': []}

        with patch('print_agent.app.prepare_slice', side_effect=prepare), \
             patch('print_agent.app.execute_slice', return_value={'status': 'sliced', 'checks': []}):
            response = self.compare()
        self.assertEqual(response.status_code, 200, response.text)
        record = response.json()['slice_comparison']
        self.assertEqual([row['id'] for row in record['variants']], ['original', 'fine', 'fast', 'strong'])
        self.assertEqual([row['layers'] for row in record['variants']], [2, 3, 1, 2])
        self.assertEqual(seen[1], ('fine', '0.12', True))
        self.assertIsNone(response.json()['latest_slice'])  # the current slice is untouched
        self.assertNotIn('sliced_three_mf', response.json()['artifacts'])
        self.assertEqual(list((self.root / 'jobs' / self.job['id'] / 'slices').iterdir()), [])
        stored = self.client.get('/api/jobs/' + self.job['id']).json()
        self.assertEqual(stored['slice_comparison'], record)
        self.assertEqual([e['type'] for e in stored['events']].count('slice_comparison'), 1)

    def test_not_ready_and_failed_variants_say_why(self):
        def prepare(input_path, work, config, **kwargs):
            if Path(work).name == 'fast':
                return {'ready': False, 'diagnostics': ['출력 영역을 넘습니다(합성).']}
            return {'ready': True, 'output_path': str(Path(work) / 'missing.3mf'), 'diagnostics': []}

        with patch('print_agent.app.prepare_slice', side_effect=prepare), \
             patch('print_agent.app.execute_slice', return_value={'status': 'failed', 'checks': [{'passed': False, 'detail': 'CLI exit code: 1'}]}):
            rows = {row['id']: row for row in self.compare(variants=['original', 'fast']).json()['slice_comparison']['variants']}
        self.assertEqual((rows['fast']['status'], rows['fast']['diagnostics']), ('not_ready', ['출력 영역을 넘습니다(합성).']))
        self.assertEqual((rows['original']['status'], rows['original']['diagnostics']), ('failed', ['CLI exit code: 1']))

    def test_requests_are_checked_before_the_slicer_is_reserved(self):
        with patch('print_agent.app.prepare_slice', side_effect=AssertionError('must not run')):
            self.assertEqual(self.compare(variants=['turbo']).status_code, 422)
            self.assertEqual(self.compare(variants=[]).status_code, 422)
            broken = bundle()
            broken['machine']['nozzle_diameter'] = ['?']
            response = self.client.post('/api/slice/compare', headers=self.headers,
                                        json={'job_id': self.job['id'], 'config_bundle': broken})
            self.assertEqual(response.status_code, 422)
            self.assertEqual(self.client.post('/api/slice/compare', headers=self.headers,
                                              json={'job_id': 'f' * 32, 'config_bundle': bundle()}).status_code, 404)


if __name__ == '__main__':
    unittest.main()
