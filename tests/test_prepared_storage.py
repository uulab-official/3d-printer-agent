"""Prepared projects have independent, verified download receipts."""
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from print_agent import slicer
from print_agent.storage import ArtifactIntegrityError, JobStore
from tests.studio_project_fixtures import project_bytes


class PreparedStorageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = JobStore(Path(self.temp.name))
        self.job_id, self.folder = self.store.reserve()
        (self.folder / 'model.3mf').write_bytes(b'original generated CAD fixture')
        self.store.finish(self.job_id, {'template': 'tray', 'parameters': {'width': 120},
            'dimensions_mm': {'x': 120, 'y': 80, 'z': 35}, 'volume_mm3': 100,
            'geometry_status': 'validated', 'print_status': 'not_tested',
            'files': {'three_mf': 'model.3mf'}, 'checks': [], 'warnings': []})
        self.path = self.folder / 'slices' / 'attempt' / 'prepared-project.3mf'
        self.path.parent.mkdir(parents=True)
        self.content = b'prepared archive receipt fixture'
        self.path.write_bytes(self.content)
        self.plan = {'kind': 'studio_project', 'ready': False, 'project_prepared': True,
            'project_path': str(self.path), 'project_sha256': hashlib.sha256(self.content).hexdigest(),
            'project_receipt': {'project_sha256': hashlib.sha256(self.content).hexdigest(), 'project_bytes': len(self.content),
                                'model_sha256': hashlib.sha256(b'original generated CAD fixture').hexdigest()},
            'project_source': {'source_id': 'a' * 32, 'summary': {'printer_model': 'synthetic'}}}

    def tearDown(self):
        self.temp.cleanup()

    def test_prepared_without_native_can_download_and_bundle(self):
        job = self.store.record_slice(self.job_id, self.plan, None)
        self.assertIn('prepared_three_mf', job['artifacts'])
        self.assertNotIn('sliced_three_mf', job['artifacts'])
        self.assertEqual(job['latest_slice']['plan']['project_source'], self.plan['project_source'])
        reopened = JobStore(Path(self.temp.name))
        self.assertEqual(reopened.read_artifact(self.job_id, 'prepared_three_mf')[1], self.content)
        with zipfile.ZipFile(io.BytesIO(reopened.bundle(self.job_id))) as archive:
            self.assertEqual(archive.read('prepared-project.3mf'), self.content)
            self.assertEqual(archive.read('model.3mf'), b'original generated CAD fixture')

    def test_changed_prepared_bytes_refuse_download_and_bundle(self):
        self.store.record_slice(self.job_id, self.plan, None)
        self.path.write_bytes(b'changed!')
        with self.assertRaises(ArtifactIntegrityError):
            self.store.read_artifact(self.job_id, 'prepared_three_mf')
        with self.assertRaises(ArtifactIntegrityError):
            self.store.bundle(self.job_id)

    def test_invalid_preparation_receipt_or_external_path_cannot_publish(self):
        for change in ({'project_sha256': '0' * 64}, {'project_sha256': None},
                       {'project_receipt': {'project_bytes': 1}},
                       {'project_path': str(Path(self.temp.name) / 'outside.3mf')}):
            with self.subTest(change=change):
                with self.assertRaises(ArtifactIntegrityError):
                    self.store.record_slice(self.job_id, {**self.plan, **change}, None)
                self.assertNotIn('prepared_three_mf', self.store.get(self.job_id)['artifacts'])

    def test_verified_cable_comb_path_replaced_by_tray_cannot_publish_under_original_receipt(self):
        examples = Path(__file__).resolve().parents[1] / 'examples'
        original = (examples / 'cable_comb/model.3mf').read_bytes()
        replacement = (examples / 'tray/model.3mf').read_bytes()
        job_id, folder = self.store.reserve()
        (folder / 'model.3mf').write_bytes(original)
        self.store.finish(job_id, {'template': 'cable_comb', 'parameters': {},
            'dimensions_mm': {'x': 1, 'y': 1, 'z': 1}, 'volume_mm3': 100,
            'geometry_status': 'validated', 'print_status': 'not_tested',
            'files': {'three_mf': 'model.3mf'}, 'checks': [], 'warnings': []})
        model, verified = self.store.read_artifact(job_id, 'three_mf')
        self.assertEqual(verified, original)
        model.write_bytes(replacement)
        with patch.object(slicer.subprocess, 'run', side_effect=AssertionError('preparation cannot launch native code')):
            plan = slicer.prepare_project_slice(model, folder / 'slices/replaced', 'source.3mf', project_bytes(),
                                                executable_path=str(folder / 'missing'))
        self.assertTrue(plan['project_prepared'], plan['diagnostics'])
        self.assertEqual(plan['project_receipt']['model_sha256'], hashlib.sha256(replacement).hexdigest())
        with self.assertRaises(ArtifactIntegrityError):
            self.store.record_slice(job_id, plan, None)
        job = self.store.get(job_id)
        self.assertNotIn('prepared_three_mf', job['artifacts'])
        self.assertEqual(job['latest_slice']['execution']['status'], 'failed')
        with patch.object(slicer.subprocess, 'run', side_effect=AssertionError('preparation cannot launch native code')):
            verified_plan = slicer.prepare_project_slice(model, folder / 'slices/verified', 'source.3mf', project_bytes(),
                executable_path=str(folder / 'missing'), input_bytes=verified)
        self.assertTrue(verified_plan['project_prepared'], verified_plan['diagnostics'])
        self.assertEqual(Path(verified_plan['input_path']).read_bytes(), original)
        job = self.store.record_slice(job_id, verified_plan, None)
        self.assertIn('prepared_three_mf', job['artifacts'])
        published = self.store.read_artifact(job_id, 'prepared_three_mf')[1]
        with zipfile.ZipFile(io.BytesIO(published)) as archive:
            model_xml = archive.read('3D/3dmodel.model').decode()
            self.assertIn(hashlib.sha256(original).hexdigest(), model_xml)
            self.assertNotIn(hashlib.sha256(replacement).hexdigest(), model_xml)

    def test_missing_or_different_original_model_hash_cannot_publish(self):
        for legacy in (False, True):
            if legacy:
                record = self.folder / 'job.json'
                data = json.loads(record.read_text())
                data.pop('_artifact_receipts')
                record.write_text(json.dumps(data), encoding='utf-8')
            for model_hash in (None, '0' * 64):
                with self.subTest(legacy=legacy, model_hash=model_hash):
                    plan = {**self.plan, 'project_receipt': {**self.plan['project_receipt'], 'model_sha256': model_hash}}
                    with self.assertRaises(ArtifactIntegrityError):
                        self.store.record_slice(self.job_id, plan, None)
                    self.assertNotIn('prepared_three_mf', self.store.get(self.job_id)['artifacts'])

    def test_new_attempt_and_interruption_detach_both_downloads(self):
        sliced = self.path.parent / 'sliced.gcode.3mf'
        sliced.write_bytes(b'native output fixture')
        self.store.record_slice(self.job_id, self.plan, {'status': 'sliced', 'output_path': str(sliced)})
        job = self.store.begin_slice(self.job_id)
        self.assertNotIn('prepared_three_mf', job['artifacts'])
        self.assertNotIn('sliced_three_mf', job['artifacts'])
        self.store.recover()
        job = self.store.get(self.job_id)
        self.assertEqual(job['latest_slice']['phase'], 'interrupted')
        self.assertNotIn('prepared_three_mf', job['artifacts'])
        self.assertTrue(self.path.is_file())

    def test_legacy_job_gets_new_prepared_receipt_without_inventing_original_hash(self):
        record = self.folder / 'job.json'
        data = json.loads(record.read_text())
        data.pop('_artifact_receipts')
        record.write_text(json.dumps(data), encoding='utf-8')
        self.store.record_slice(self.job_id, self.plan, None)
        data = json.loads(record.read_text())
        self.assertNotIn('_artifact_receipts', data)
        self.assertIn('_prepared_artifact_receipt', data)
        self.assertEqual(self.store.read_artifact(self.job_id, 'prepared_three_mf')[1], self.content)
        self.store.bundle(self.job_id)
        data.pop('_prepared_artifact_receipt')
        record.write_text(json.dumps(data), encoding='utf-8')
        with self.assertRaises(ArtifactIntegrityError):
            self.store.read_artifact(self.job_id, 'prepared_three_mf')

    def test_native_failure_keeps_verified_prepared_file_separate(self):
        job = self.store.record_slice(self.job_id, self.plan,
            {'status': 'failed', 'output_path': None, 'print_status': 'not_started'})
        self.assertIn('prepared_three_mf', job['artifacts'])
        self.assertNotIn('sliced_three_mf', job['artifacts'])
        self.assertEqual(job['latest_slice']['execution']['status'], 'failed')
