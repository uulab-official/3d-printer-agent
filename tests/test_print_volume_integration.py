"""Current CAD and recorded settings must agree before automatic preparation."""
import base64
import copy
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from fastapi.testclient import TestClient

from print_agent import slicer, studio_project
from print_agent.app import create_app
from tests.studio_project_fixtures import project_bytes
from tests.test_slicer import full_bundle


ROOT = Path(__file__).resolve().parents[1]
MODEL = (ROOT / 'examples/cable_comb/model.3mf').read_bytes()  # 80 × 18 × 12 mm


class PrintVolumeCompositionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.model = self.root / 'model.3mf'
        self.model.write_bytes(MODEL)
        self.executable = self.root / 'fixture-executable'
        self.executable.write_bytes(b'never launched')
        self.executable.chmod(0o700)

    def prepare(self, overrides=None, name='attempt'):
        return slicer.prepare_project_slice(self.model, self.root / name,
            'source.3mf', project_bytes(settings_overrides=overrides),
            executable_path=str(self.executable))

    def test_direct_composition_rejects_recorded_height_and_checked_xy_overflow(self):
        for changes in ({'printable_height': '11'},
                        {'printable_area': ['0x0', '70x0', '70x10', '0x10']}):
            with self.subTest(changes=changes):
                snapshot = studio_project.inspect_studio_project('source.3mf',
                    project_bytes(settings_overrides=changes))
                self.assertTrue(snapshot['supported'])  # Format support is a separate state.
                with self.assertRaises(ValueError):
                    studio_project.build_project_3mf(MODEL, snapshot)

    def test_failed_review_is_structured_and_stages_nothing(self):
        with patch.object(slicer.subprocess, 'run', side_effect=AssertionError('No native launch')):
            plan = self.prepare({'printable_height': '11'})
        self.assertFalse(plan['project_prepared'])
        self.assertFalse(plan['ready'])
        self.assertEqual(plan['print_volume']['status'], 'height_exceeded')
        self.assertEqual(plan['print_volume']['model_dimensions_mm'], [80, 18, 12])
        self.assertEqual(plan['print_volume']['recorded_volume_mm'][2], 11)
        self.assertEqual(plan['print_volume']['model_sha256'], hashlib.sha256(MODEL).hexdigest())
        self.assertFalse((self.root / 'attempt').exists())
        self.assertTrue(plan['diagnostics'])

    def test_receipt_binds_review_to_exact_model_and_effective_settings_without_changes(self):
        source = project_bytes(settings_overrides={
            'printable_area': ['-10x-20', '60x-20', '60x80', '-10x80']})
        snapshot = studio_project.inspect_studio_project('source.3mf', source)
        content, receipt = studio_project.build_project_3mf(MODEL, snapshot)
        report = receipt['print_volume']
        self.assertEqual(report['status'], 'fits')
        self.assertTrue(report['can_prepare'])
        self.assertEqual(report['rotation_degrees'], 90)
        self.assertFalse(report['placement_applied'])
        self.assertEqual(report['model_sha256'], hashlib.sha256(MODEL).hexdigest())
        self.assertEqual(report['settings_sha256'], snapshot['settings_sha256'])
        self.assertEqual(receipt['geometry']['dimensions_mm'], [80, 18, 12])
        self.assertTrue(receipt['geometry']['preserved'])
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            self.assertEqual(archive.read(studio_project.SETTINGS_PATH), snapshot['settings_text'].encode())
        self.assertEqual((content, receipt), studio_project.build_project_3mf(MODEL, snapshot))

    def test_execution_rederives_report_instead_of_trusting_ready_or_client_edits(self):
        plan = self.prepare()
        self.assertTrue(plan['ready'], plan['diagnostics'])
        slicer._validate_project_plan(plan)
        for change in ('remove', 'forge'):
            altered = copy.deepcopy(plan)
            if change == 'remove':
                altered.pop('print_volume', None)
            else:
                altered['print_volume'] = {'status': 'fits', 'can_prepare': True}
            with self.subTest(change=change), self.assertRaises(ValueError):
                slicer._validate_project_plan(altered)

    def test_full_config_execution_requires_the_saved_review_even_if_plan_field_is_removed(self):
        plan = slicer.prepare_slice(self.model, self.root / 'manual', full_bundle(),
            str(self.executable), input_bytes=MODEL, require_volume_review=True)
        self.assertTrue(plan['ready'], plan['diagnostics'])
        self.assertTrue(plan['print_volume']['can_prepare'])
        slicer._validate_plan(plan)
        altered = copy.deepcopy(plan)
        altered.pop('print_volume')
        with self.assertRaises(ValueError):
            slicer._validate_plan(altered)

    def test_competing_geometry_in_other_config_roles_never_reaches_staging(self):
        for role in ('process', 'filament'):
            bundle = full_bundle()
            target = bundle['process'] if role == 'process' else bundle['filaments'][0]
            target['printable_height'] = '999'
            folder = self.root / role
            with self.subTest(role=role):
                plan = slicer.prepare_slice(self.model, folder, bundle,
                    str(self.executable), input_bytes=MODEL, require_volume_review=True)
                self.assertFalse(plan['ready'])
                self.assertFalse(folder.exists())

    def test_nonzero_model_origin_is_translated_for_comparison_without_geometry_edit(self):
        from xml.etree import ElementTree as ET
        with zipfile.ZipFile(io.BytesIO(MODEL)) as archive:
            members = {name: archive.read(name) for name in archive.namelist()}
        root = ET.fromstring(members[studio_project.MODEL_PATH])
        for vertex in root.findall('.//{*}vertex'):
            vertex.set('x', str(float(vertex.get('x')) + 500))
            vertex.set('y', str(float(vertex.get('y')) - 300))
        members[studio_project.MODEL_PATH] = ET.tostring(root)
        stream = io.BytesIO()
        with zipfile.ZipFile(stream, 'w', zipfile.ZIP_DEFLATED) as archive:
            for name, data in members.items():
                archive.writestr(name, data)
        snapshot = studio_project.inspect_studio_project('source.3mf', project_bytes())
        _, receipt = studio_project.build_project_3mf(stream.getvalue(), snapshot)
        self.assertEqual(receipt['print_volume']['status'], 'fits')
        self.assertEqual(receipt['print_volume']['model_dimensions_mm'], [80, 18, 12])
        self.assertFalse(receipt['print_volume']['placement_applied'])
        self.assertTrue(receipt['geometry']['preserved'])


class PrintVolumeAPITests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.app = create_app(self.root, test_mode=True)
        self.client = TestClient(self.app)
        self.addCleanup(self.client.close)
        self.headers = {'X-Session-Token': self.client.get('/api/bootstrap').json()['session_token']}
        store = self.app.state.store
        job_id, folder = store.reserve()
        (folder / 'model.3mf').write_bytes(MODEL)
        self.job = store.finish(job_id, {'template': 'cable_comb',
            'parameters': {'template': 'cable_comb'},
            # Deliberately misleading cached display dimensions cannot bypass byte review.
            'dimensions_mm': {'x': 1, 'y': 1, 'z': 1}, 'volume_mm3': 1,
            'geometry_status': 'validated', 'print_status': 'not_tested',
            'files': {'three_mf': 'model.3mf'}, 'checks': [], 'warnings': []})

    def source(self, overrides=None):
        data = project_bytes(settings_overrides=overrides)
        response = self.client.post('/api/studio-projects/import', headers=self.headers,
            json={'filename': 'recorded.3mf', 'content_base64': base64.b64encode(data).decode()})
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()

    def slice(self, **values):
        response = self.client.post('/api/slice', headers=self.headers,
            json={'job_id': self.job['id'], **values})
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def test_small_source_clears_old_download_and_uses_verified_mesh_not_display_dimensions(self):
        large = self.source()
        small = self.source({'printable_height': '11'})
        first = self.slice(studio_project_id=large['source_id'])
        self.assertTrue(first['plan']['project_prepared'])
        old = self.client.get('/api/jobs/' + self.job['id']).json()
        self.assertIn('prepared_three_mf', old['artifacts'])
        with patch('print_agent.app.execute_slice', side_effect=AssertionError('Blocked work cannot execute')):
            blocked = self.slice(studio_project_id=small['source_id'], execute=True)
        self.assertFalse(blocked['plan']['project_prepared'])
        self.assertEqual(blocked['plan']['print_volume']['model_dimensions_mm'], [80, 18, 12])
        self.assertIsNone(blocked['execution'])
        saved = self.client.get('/api/jobs/' + self.job['id']).json()
        self.assertNotIn('prepared_three_mf', saved['artifacts'])
        self.assertEqual(saved['latest_slice']['plan']['print_volume']['status'], 'height_exceeded')
        self.assertEqual(self.client.get(old['artifacts']['prepared_three_mf']).status_code, 404)
        self.assertEqual(self.client.get(saved['artifacts']['three_mf']).content, MODEL)

    def test_manual_configuration_cannot_bypass_the_same_volume_check(self):
        bundle = full_bundle()
        bundle['machine']['printable_height'] = '11'
        executable = self.root / 'fixture-executable'
        executable.write_bytes(b'never launched')
        executable.chmod(0o700)
        environment = {'available': True, 'path': str(executable), 'diagnostics': []}
        with patch.object(slicer, 'detect_environment', return_value=environment), patch(
                'print_agent.app.execute_slice', side_effect=AssertionError('Blocked work cannot execute')):
            response = self.slice(config_bundle=bundle)
        self.assertFalse(response['plan']['ready'])
        self.assertEqual(response['plan']['print_volume']['status'], 'height_exceeded')
        self.assertIsNone(response['execution'])
        self.assertFalse(Path(response['plan']['job_dir']).exists())

    def test_source_summary_exposes_recorded_area_and_height_without_hardware_claim(self):
        source = self.source({'printable_height': '77',
            'printable_area': ['0x0', '70x0', '70x100', '0x100']})
        self.assertEqual(source['summary']['printable_height'], '77')
        self.assertEqual(source['summary']['printable_area'], ['0x0', '70x0', '70x100', '0x100'])


if __name__ == '__main__':
    unittest.main()
