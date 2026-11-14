"""Verify storage receipts with explicitly synthetic file contents."""
import copy
import hashlib
import io
import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from print_agent import storage
from tests.test_storage_recovery import result_fixture


class ArtifactIntegrityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.store = storage.JobStore(self.root)
        self.job_id, self.folder = self.store.reserve()
        result = result_fixture(self.folder)
        for kind, filename in (('step', 'model.step'), ('three_mf', 'model.3mf'), ('source', 'model.py')):
            (self.folder / filename).write_bytes(('synthetic storage fixture: ' + kind).encode())
            result['files'][kind] = filename
        self.job = self.store.finish(self.job_id, result)

    def tearDown(self):
        self.temp.cleanup()

    def legacy(self):
        path = self.folder / 'job.json'
        job = json.loads(path.read_text())
        job.pop('_artifact_receipts', None)
        path.write_text(json.dumps(job, ensure_ascii=False))
        return path.read_bytes()

    def test_healthy_download_is_exact_verified_byte_snapshot(self):
        original = (self.folder / 'model.3mf').read_bytes()
        path, content = self.store.read_artifact(self.job_id, 'three_mf')
        self.assertEqual(path, self.folder / 'model.3mf')
        self.assertEqual(content, original)
        path.write_bytes(b'changed after the snapshot')
        self.assertEqual(content, original)

    def test_same_length_change_cannot_download_by_path_or_bundle(self):
        path = self.folder / 'model.3mf'
        original = path.read_bytes()
        record = (self.folder / 'job.json').read_bytes()
        path.write_bytes(b'!' * len(original))
        for operation in (lambda: self.store.artifact_path(self.job_id, 'three_mf'),
                          lambda: self.store.read_artifact(self.job_id, 'three_mf'),
                          lambda: self.store.bundle(self.job_id)):
            with self.assertRaises(storage.ArtifactIntegrityError):
                operation()
        self.assertEqual((self.folder / 'job.json').read_bytes(), record)
        path.write_bytes(original)
        self.assertEqual(self.store.read_artifact(self.job_id, 'three_mf')[1], original)

    def test_truncated_or_missing_registered_artifact_has_integrity_error(self):
        path = self.folder / 'model.stl'
        path.write_bytes(b'truncated')
        with self.assertRaises(storage.ArtifactIntegrityError):
            self.store.read_artifact(self.job_id, 'stl')
        path.unlink()
        with self.assertRaises(storage.ArtifactIntegrityError):
            self.store.read_artifact(self.job_id, 'stl')
        with self.assertRaises(KeyError):
            self.store.read_artifact(self.job_id, 'unregistered')

    def test_new_manifest_has_its_own_original_byte_receipt(self):
        manifest = self.folder / 'manifest.json'
        data = json.loads(manifest.read_text())
        data['volume_mm3'] += 1
        manifest.write_text(json.dumps(data, ensure_ascii=False))
        with self.assertRaises(storage.ArtifactIntegrityError):
            self.store.read_artifact(self.job_id, 'manifest')
        with self.assertRaises(storage.ArtifactIntegrityError):
            self.store.bundle(self.job_id)

    def test_bundle_uses_verified_snapshots_when_disk_changes_during_serialization(self):
        expected = {path.name: path.read_bytes() for path in self.folder.iterdir() if path.name != 'job.json'}
        original_write = zipfile.ZipFile.writestr
        changed = []
        def write(archive, name, content, *args, **kwargs):
            if not changed:
                changed.append(True)
                for filename in expected:
                    (self.folder / filename).write_bytes(b'changed after complete snapshot')
            return original_write(archive, name, content, *args, **kwargs)
        with patch.object(zipfile.ZipFile, 'writestr', write):
            content = self.store.bundle(self.job_id)
        self.assertTrue(changed)
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            for filename, data in expected.items():
                self.assertEqual(archive.read(filename), data)
            self.assertEqual(json.loads(archive.read('job.json'))['id'], self.job_id)

    def test_legacy_downloads_use_existing_manifest_without_inventing_receipts(self):
        original_record = self.legacy()
        manifest_bytes = (self.folder / 'manifest.json').read_bytes()
        self.assertEqual(self.store.read_artifact(self.job_id, 'manifest')[1], manifest_bytes)
        self.assertEqual(self.store.read_artifact(self.job_id, 'stl')[1], (self.folder / 'model.stl').read_bytes())
        with zipfile.ZipFile(io.BytesIO(self.store.bundle(self.job_id))) as archive:
            self.assertEqual(archive.read('manifest.json'), manifest_bytes)
        self.assertEqual((self.folder / 'job.json').read_bytes(), original_record)
        (self.folder / 'model.stl').write_bytes(b'bad legacy STL')
        with self.assertRaises(storage.ArtifactIntegrityError):
            self.store.read_artifact(self.job_id, 'stl')
        with self.assertRaises(storage.ArtifactIntegrityError):
            self.store.read_artifact(self.job_id, 'manifest')

    def test_legacy_manifest_must_match_saved_job_identity_and_parameters(self):
        self.legacy()
        original = json.loads((self.folder / 'manifest.json').read_text())
        mutations = ({'job_id': 'a' * 32}, {'parameters': {'width': 999}}, {'schema_version': True},
                     {'design_source': {'kind': 'forged'}}, {'physical_print_status': 'verified'})
        for mutation in mutations:
            altered = {**original, **mutation}
            (self.folder / 'manifest.json').write_text(json.dumps(altered, ensure_ascii=False))
            with self.subTest(mutation=mutation), self.assertRaises(storage.ArtifactIntegrityError):
                self.store.read_artifact(self.job_id, 'manifest')

    def test_partial_receipt_map_cannot_fall_back_to_legacy_trust(self):
        record = self.folder / 'job.json'
        data = json.loads(record.read_text())
        data['_artifact_receipts'] = {}
        record.write_text(json.dumps(data, ensure_ascii=False))
        with self.assertRaises(storage.ArtifactIntegrityError):
            self.store.read_artifact(self.job_id, 'stl')

    def test_sliced_output_receipt_is_checked_and_removed_after_blocked_attempt(self):
        path = self.folder / 'new.gcode.3mf'
        original = b'synthetic sliced bytes'
        path.write_bytes(original)
        execution = {'status': 'sliced', 'output_path': str(path),
                     'output_sha256': hashlib.sha256(original).hexdigest()}
        self.store.record_slice(self.job_id, {'ready': True}, execution)
        self.assertEqual(self.store.read_artifact(self.job_id, 'sliced_three_mf')[1], original)
        path.write_bytes(b'!' * len(original))
        with self.assertRaises(storage.ArtifactIntegrityError):
            self.store.read_artifact(self.job_id, 'sliced_three_mf')
        self.store.record_slice(self.job_id, {'ready': False}, None)
        with self.assertRaises(KeyError):
            self.store.read_artifact(self.job_id, 'sliced_three_mf')

    def test_mismatched_executor_receipt_never_registers_new_output(self):
        path = self.folder / 'changed.gcode.3mf'
        path.write_bytes(b'changed after execution read-back')
        for digest in ('0' * 64, None):
            with self.subTest(digest=digest), self.assertRaises(storage.ArtifactIntegrityError):
                self.store.record_slice(self.job_id, {'ready': True}, {
                    'status': 'sliced', 'output_path': str(path), 'output_sha256': digest})
            self.assertNotIn('sliced_three_mf', self.store.get(self.job_id)['artifacts'])

    def test_legacy_slice_without_original_hash_is_not_recertified(self):
        path = self.folder / 'old.gcode.3mf'
        path.write_bytes(b'old synthetic slice')
        self.store.record_slice(self.job_id, {'ready': True}, {'status': 'sliced', 'output_path': str(path)})
        self.legacy()
        with self.assertRaises(storage.ArtifactIntegrityError):
            self.store.read_artifact(self.job_id, 'sliced_three_mf')

    def test_legacy_slice_with_executor_hash_remains_verifiable(self):
        path = self.folder / 'old.gcode.3mf'
        content = b'old synthetic slice with recorded hash'
        path.write_bytes(content)
        self.store.record_slice(self.job_id, {'ready': True}, {
            'status': 'sliced', 'output_path': str(path), 'output_sha256': hashlib.sha256(content).hexdigest()})
        self.legacy()
        self.assertEqual(self.store.read_artifact(self.job_id, 'sliced_three_mf')[1], content)

    def test_missing_new_output_cannot_leave_previous_slice_current(self):
        path = self.folder / 'previous.gcode.3mf'
        path.write_bytes(b'previous synthetic result')
        self.store.record_slice(self.job_id, {'ready': True}, {'status': 'sliced', 'output_path': str(path)})
        with self.assertRaises(storage.ArtifactIntegrityError):
            self.store.record_slice(self.job_id, {'ready': True}, {'status': 'sliced'})
        job = self.store.get(self.job_id)
        self.assertNotIn('sliced_three_mf', job['artifacts'])
        self.assertEqual(job['latest_slice']['execution']['status'], 'failed')
        self.assertEqual(path.read_bytes(), b'previous synthetic result')

    def test_legacy_windows_slice_separators_keep_the_original_hash(self):
        path = self.folder / 'slices' / 'synthetic' / 'old.gcode.3mf'
        path.parent.mkdir(parents=True)
        content = b'legacy Windows path fixture'
        path.write_bytes(content)
        self.store.record_slice(self.job_id, {'ready': True}, {
            'status': 'sliced', 'output_path': str(path), 'output_sha256': hashlib.sha256(content).hexdigest()})
        self.legacy()
        record = self.folder / 'job.json'
        job = json.loads(record.read_text())
        job['_files']['sliced_three_mf'] = 'slices\\synthetic\\old.gcode.3mf'
        record.write_text(json.dumps(job))
        self.assertEqual(self.store.read_artifact(self.job_id, 'sliced_three_mf')[1], content)
