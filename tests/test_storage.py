import json
import tempfile
import unittest
from pathlib import Path

from print_agent.storage import JobStore


class StorageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = JobStore(Path(self.temp.name))

    def tearDown(self):
        self.temp.cleanup()

    def result(self, folder):
        (folder / 'model.stl').write_bytes(b'verified test fixture')
        return {'template':'tray','parameters':{'width':120},'dimensions_mm':{'x':120,'y':80,'z':35},
                'geometry_status':'validated','print_status':'not_tested','files':{'stl':'model.stl'},
                'mesh':{'vertices':[],'faces':[]},'checks':[],'warnings':[],'volume_mm3':100}

    def test_job_manifest_hash_and_readback(self):
        job_id, folder = self.store.reserve()
        job = self.store.finish(job_id, self.result(folder))
        self.assertEqual(self.store.get(job_id)['id'], job_id)
        self.assertEqual(self.store.list_jobs()[0]['status'], 'geometry_validated')
        manifest = json.loads(self.store.artifact_path(job_id, 'manifest').read_text())
        self.assertEqual(len(manifest['artifacts']['stl']['sha256']), 64)
        self.assertEqual(manifest['physical_print_status'], 'not_tested')
        self.assertIn('/files/stl', job['artifacts']['stl'])

    def test_unknown_id_and_paths_cannot_escape(self):
        with self.assertRaises(ValueError):
            self.store.get('../outside')
        job_id, folder = self.store.reserve()
        self.store.finish(job_id, self.result(folder))
        with self.assertRaises(KeyError):
            self.store.artifact_path(job_id, '../../etc/passwd')

    def test_result_reports_do_not_change_geometry_or_assert_print_verified(self):
        job_id, folder = self.store.reserve()
        self.store.finish(job_id, self.result(folder))
        job = self.store.record_outcome(job_id, 'success', '실제 출력 후 사용자 입력')
        self.assertEqual(job['user_outcome']['source'], 'user_reported')
        self.assertEqual(job['result']['print_status'], 'not_tested')
        self.assertEqual(job['status'], 'geometry_validated')
        self.assertEqual(len(job['events']), 2)

    def test_failed_reservation_is_visible_without_bogus_artifacts(self):
        job_id, folder = self.store.reserve()
        self.store.fail(job_id, '치수 충돌')
        job = self.store.get(job_id)
        self.assertEqual(job['status'], 'failed')
        self.assertFalse(job['artifacts'])
        self.assertIn('치수 충돌', job['events'][-1]['message'])

    def test_api_cannot_register_arbitrary_generated_file(self):
        job_id, folder = self.store.reserve()
        payload = self.result(folder)
        payload['files']['stl'] = '../secret'
        with self.assertRaises(ValueError):
            self.store.finish(job_id, payload)

    def test_failed_new_slice_does_not_leave_previous_slice_as_current_download(self):
        job_id,folder=self.store.reserve()
        self.store.finish(job_id,self.result(folder))
        previous=folder/'first.gcode.3mf'
        previous.write_bytes(b'previous result fixture')
        self.store.record_slice(job_id,{'ready':True},{'status':'sliced','output_path':str(previous)})
        self.assertIn('sliced_three_mf',self.store.get(job_id)['artifacts'])
        current=self.store.record_slice(job_id,{'ready':False,'expected_settings':{'layer_height':0.4}},None)
        self.assertNotIn('sliced_three_mf',current['artifacts'])
        with self.assertRaises(KeyError):
            self.store.artifact_path(job_id,'sliced_three_mf')
