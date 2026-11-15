"""Edit provenance and original-byte identity using synthetic CAD file contents."""
import copy
import hashlib
import inspect
import io
import json
import tempfile
import unittest
import zipfile
from pathlib import Path

from print_agent import storage
from print_agent.model_edits import model_edit_record
from print_agent.schemas import GeometryRequest


def canonical_hash(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                    separators=(',', ':'), allow_nan=False).encode()).hexdigest()


class ModelEditRecordTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / 'data'
        self.store = storage.JobStore(self.root)
        self.base = GeometryRequest(template='tray', width=150, depth=90, height=30,
                                    wall=2, bottom=2, dividers=2).model_dump(mode='json')
        self.parameters = {**self.base, 'height': 35.0}
        self.selection = {'schema_version': 1, 'request_text': '높이를 5mm 늘려줘',
                          'base_parameters': copy.deepcopy(self.base),
                          'operations': [{'field': 'height', 'op': 'add', 'value': 5}], 'parent': None}

    def tearDown(self):
        self.temp.cleanup()

    def result(self, folder, parameters=None):
        parameters = copy.deepcopy(self.base if parameters is None else parameters)
        files = {'stl': 'model.stl', 'three_mf': 'model.3mf', 'source': 'model.py'}
        for kind, name in files.items():
            (folder / name).write_bytes(('synthetic model-edit fixture: ' + kind).encode())
        return {'template': parameters['template'], 'parameters': parameters,
                'dimensions_mm': {'x': parameters['width'], 'y': parameters['depth'], 'z': parameters['height']},
                'geometry_status': 'validated', 'print_status': 'not_tested', 'files': files,
                'mesh': {'vertices': [], 'faces': []}, 'checks': [], 'warnings': [], 'volume_mm3': 100}

    def parent_job(self):
        job_id, folder = self.store.reserve(request=self.base)
        self.store.finish(job_id, self.result(folder))
        return job_id, folder

    def parent(self, job_id, parameters=None):
        self.assertTrue(callable(getattr(self.store, 'model_edit_parent', None)),
                        'JobStore must verify parent model bytes before edits')
        return self.store.model_edit_parent(job_id, self.base if parameters is None else parameters)

    def reserve_edit(self, selection=None):
        self.assertIn('model_edit', inspect.signature(self.store.reserve).parameters,
                      'reserve must accept an immutable model-edit record')
        record = model_edit_record(self.selection if selection is None else selection, self.parameters)
        return self.store.reserve(request=self.parameters, model_edit=record)

    def rewrite(self, folder, mutate):
        path = folder / 'job.json'
        job = json.loads(path.read_bytes())
        mutate(job)
        path.write_text(json.dumps(job, ensure_ascii=False), encoding='utf-8')

    def test_reserve_validates_record_before_creating_any_job(self):
        record = model_edit_record(self.selection, self.parameters)
        invalid = [{}, self.selection, {**record, 'schema_version': True},
                   {**record, 'changes': []}, {**record, 'parameters': self.base}]
        self.assertIn('model_edit', inspect.signature(self.store.reserve).parameters)
        for selection in invalid:
            with self.subTest(selection=selection), self.assertRaises(ValueError):
                self.store.reserve(request=self.parameters, model_edit=selection)
            self.assertEqual(list(self.store.jobs_dir.iterdir()), [])
            self.assertEqual(self.store.list_jobs(), [])
        with self.assertRaises(ValueError):
            self.store.reserve(model_edit=record)
        self.assertEqual(list(self.store.jobs_dir.iterdir()), [])

    def test_edit_reservation_does_not_coerce_string_dimensions(self):
        with self.assertRaises(ValueError):
            self.store.reserve(request={**self.parameters, 'height': '35'},
                               model_edit=model_edit_record(self.selection, self.parameters))
        self.assertEqual(list(self.store.jobs_dir.iterdir()), [])

    def test_selection_and_recipe_are_immutable_and_exported_with_receipts(self):
        expected = model_edit_record(self.selection, self.parameters)
        submitted = copy.deepcopy(expected)
        source = {'kind': 'project_catalog', 'recipe_sha256': 'a' * 64,
                  'recipe': {'source': {'license': 'MIT'}, 'parameters': copy.deepcopy(self.base)}}
        expected_source = copy.deepcopy(source)
        job_id, folder = self.store.reserve(request=self.parameters, design_source=source,
                                           model_edit=submitted)
        self.selection['base_parameters']['width'] = 999
        self.selection['operations'][0]['value'] = 999
        submitted['selection']['base_parameters']['width'] = 999
        submitted['selection']['operations'][0]['value'] = 999
        source['recipe']['source']['license'] = 'changed'
        self.assertEqual(self.store.get(job_id)['model_edit'], expected)
        job = self.store.finish(job_id, self.result(folder, self.parameters))
        job['model_edit']['selection']['request_text'] = 'mutated returned view'
        reopened = storage.JobStore(self.root)
        self.assertEqual(reopened.get(job_id)['model_edit'], expected)
        self.assertEqual(reopened.get(job_id)['design_source'], expected_source)
        manifest_bytes = reopened.read_artifact(job_id, 'manifest')[1]
        manifest = json.loads(manifest_bytes)
        self.assertEqual(manifest['model_edit'], expected)
        self.assertEqual(manifest['design_source'], expected_source)
        disk_job = json.loads((folder / 'job.json').read_bytes())
        for kind, receipt in disk_job['_artifact_receipts'].items():
            content = (folder / receipt['filename']).read_bytes()
            self.assertEqual(receipt['bytes'], len(content), kind)
            self.assertEqual(receipt['sha256'], hashlib.sha256(content).hexdigest(), kind)
        with zipfile.ZipFile(io.BytesIO(reopened.bundle(job_id))) as bundle:
            self.assertEqual(bundle.read('manifest.json'), manifest_bytes)
            self.assertEqual(json.loads(bundle.read('job.json'))['model_edit'], expected)
            self.assertEqual(bundle.read('model.3mf'), (folder / 'model.3mf').read_bytes())

    def test_finish_rechecks_edit_against_actual_result_before_manifest(self):
        job_id, folder = self.reserve_edit()
        with self.assertRaises(ValueError):
            self.store.finish(job_id, self.result(folder, self.base))
        self.assertEqual(self.store.get(job_id)['status'], 'generating')
        self.assertFalse((folder / 'manifest.json').exists())

    def test_saved_edit_record_tampering_is_unreadable(self):
        job_id, folder = self.reserve_edit()
        self.store.finish(job_id, self.result(folder, self.parameters))
        original = (folder / 'job.json').read_bytes()
        mutations = [lambda j: j['model_edit'].__setitem__('provenance', 'printed'),
                     lambda j: j['model_edit'].__setitem__('review_sha256', 'a' * 64),
                     lambda j: j['model_edit']['selection']['operations'][0].__setitem__('value', 6),
                     lambda j: j['model_edit']['changes'].clear(),
                     lambda j: j['model_edit'].__setitem__('extra', 'untrusted'),
                     lambda j: j['model_edit'].__setitem__('schema_version', True),
                     lambda j: j['result']['parameters'].__setitem__('height', 36),
                     lambda j: j['request'].__setitem__('height', 36),
                     lambda j: (j.__setitem__('status', 'failed'), j.__setitem__('result', {})),
                     lambda j: j.__setitem__('model_edit', None)]
        for mutate in mutations:
            (folder / 'job.json').write_bytes(original)
            self.rewrite(folder, mutate)
            with self.subTest(mutation=mutate), self.assertRaises(storage.JobRecordError):
                storage.JobStore(self.root).get(job_id)

    def test_parent_identity_hashes_verified_original_and_manifest_bytes(self):
        job_id, folder = self.parent_job()
        before = (folder / 'job.json').read_bytes()
        expected = {'job_id': job_id, 'parameters_sha256': canonical_hash(self.base),
                    'model_sha256': hashlib.sha256((folder / 'model.3mf').read_bytes()).hexdigest(),
                    'manifest_sha256': hashlib.sha256((folder / 'manifest.json').read_bytes()).hexdigest()}
        parent = self.parent(job_id)
        self.assertEqual(parent, expected)
        parent['model_sha256'] = 'f' * 64
        self.assertEqual(self.parent(job_id), expected)
        self.assertEqual((folder / 'job.json').read_bytes(), before)

    def test_parent_requires_matching_validated_job_and_complete_parameters(self):
        job_id, folder = self.parent_job()
        for parameters in ({**self.base, 'height': 31}, {'template': 'tray'},
                           {**self.base, 'wall': 80}):
            with self.subTest(parameters=parameters), self.assertRaises(ValueError):
                self.parent(job_id, parameters)
        with self.assertRaises(KeyError):
            self.parent('f' * 32)
        unfinished, _ = self.store.reserve(request=self.base)
        with self.assertRaises(ValueError):
            self.parent(unfinished)
        self.store.fail(unfinished, 'synthetic failure')
        with self.assertRaises(ValueError):
            self.parent(unfinished)

    def test_parent_rejects_missing_changed_unreadable_and_unregistered_model(self):
        job_id, folder = self.parent_job()
        path = folder / 'model.3mf'
        original = path.read_bytes()
        path.write_bytes(b'!' * len(original))
        with self.assertRaises(storage.ArtifactIntegrityError):
            self.parent(job_id)
        path.unlink()
        with self.assertRaises(storage.ArtifactIntegrityError):
            self.parent(job_id)
        path.mkdir()
        with self.assertRaises(storage.ArtifactIntegrityError):
            self.parent(job_id)
        path.rmdir()
        path.write_bytes(original)
        self.rewrite(folder, lambda j: (j['_files'].pop('three_mf'), j['artifacts'].pop('three_mf'),
                                       j['_artifact_receipts'].pop('three_mf')))
        with self.assertRaises(storage.ArtifactIntegrityError):
            self.parent(job_id)

    def test_parent_rejects_manifest_identity_and_receipt_conflicts(self):
        job_id, folder = self.parent_job()
        path = folder / 'manifest.json'
        original = path.read_bytes()
        for mutation in ({'job_id': 'f' * 32}, {'parameters': {**self.base, 'height': 31}},
                         {'geometry_status': 'invalid'}, {'artifacts': {}}):
            manifest = {**json.loads(original), **mutation}
            path.write_text(json.dumps(manifest, ensure_ascii=False), encoding='utf-8')
            # Even if a saved manifest byte receipt is updated, its semantics
            # must still bind to this job and its original-model receipt.
            content = path.read_bytes()
            self.rewrite(folder, lambda j: j['_artifact_receipts'].__setitem__(
                'manifest', storage._receipt('manifest.json', content)))
            with self.subTest(mutation=mutation), self.assertRaises(storage.ArtifactIntegrityError):
                self.parent(job_id)

    def test_legacy_parent_uses_manifest_receipts_without_inventing_saved_receipts(self):
        job_id, folder = self.parent_job()
        self.rewrite(folder, lambda j: j.pop('_artifact_receipts'))
        before = (folder / 'job.json').read_bytes()
        identity = self.parent(job_id)
        self.assertEqual(identity['manifest_sha256'], hashlib.sha256((folder / 'manifest.json').read_bytes()).hexdigest())
        self.assertEqual((folder / 'job.json').read_bytes(), before)

    def test_child_read_does_not_open_historical_parent(self):
        parent_id, folder = self.parent_job()
        self.selection['parent'] = self.parent(parent_id)
        child_id, child_folder = self.reserve_edit()
        self.store.finish(child_id, self.result(child_folder, self.parameters))
        (folder / 'job.json').write_bytes(b'corrupt historical parent')
        self.assertEqual(storage.JobStore(self.root).get(child_id)['model_edit']['selection']['parent']['job_id'], parent_id)
        self.assertEqual(self.parent(child_id, self.parameters)['job_id'], child_id)
        with self.assertRaises(storage.JobRecordError):
            self.parent(parent_id)

    def test_backup_restore_preserves_canonical_edit_record_and_receipts(self):
        from print_agent.backup import create_backup, restore_backup
        job_id, folder = self.reserve_edit()
        self.store.finish(job_id, self.result(folder, self.parameters))
        expected = {path.name: path.read_bytes() for path in folder.iterdir()}
        archive, destination = Path(self.temp.name) / 'backup.zip', Path(self.temp.name) / 'restored'
        create_backup(self.root, archive)
        restore_backup(archive, destination)
        restored = storage.JobStore(destination)
        self.assertEqual(restored.get(job_id)['model_edit'], self.store.get(job_id)['model_edit'])
        for name, content in expected.items():
            self.assertEqual((destination / 'jobs' / job_id / name).read_bytes(), content, name)
        self.assertEqual(restored.read_artifact(job_id, 'manifest')[1], expected['manifest.json'])

    def test_legacy_jobs_have_no_invented_edit_record(self):
        job_id, _ = self.parent_job()
        self.assertNotIn('model_edit', self.store.get(job_id))
        self.assertNotIn('model_edit', json.loads(self.store.read_artifact(job_id, 'manifest')[1]))


if __name__ == '__main__':
    unittest.main()
