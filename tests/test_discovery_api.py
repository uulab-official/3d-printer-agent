"""Public beginner discovery and real CAD/source round-trip contracts."""
import hashlib
import io
import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from print_agent.app import create_app


class DiscoveryAPITests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.app = create_app(self.root, test_mode=True)
        self.client = TestClient(self.app)
        self.bootstrap = self.client.get('/api/bootstrap').json()
        self.headers = {'X-Session-Token': self.bootstrap['session_token']}

    def tearDown(self):
        self.client.close()
        self.temp.cleanup()

    def project(self, project_id='desk-sorter'):
        return next(item for item in self.bootstrap['discovery']['projects']
                    if item['id'] == project_id)

    def post(self, path, payload):
        return self.client.post(path, json=payload, headers=self.headers)

    def test_bootstrap_and_recommendations_do_not_generate_or_call_providers(self):
        with patch('print_agent.app.generate_model') as generate, \
             patch('print_agent.app.plan_with_llm') as llm, \
             patch('print_agent.app.probe_environment') as native:
            data = self.client.get('/api/bootstrap').json()
            self.assertEqual(len(data['templates']), 3)
            self.assertEqual(data['discovery']['schema_version'], 1)
            self.assertEqual(len(data['discovery']['projects']), 6)
            response = self.post('/api/discovery', {})
            self.assertEqual(response.status_code, 200, response.text)
            result = response.json()
            self.assertEqual(result['total_in_purpose'], 6)
            self.assertEqual(result['excluded_count'], 0)
            self.assertEqual([item['project']['id'] for item in result['matches']],
                             [item['id'] for item in data['discovery']['projects']])
            self.assertTrue(all(item['space_fit']['status'] == 'not_checked'
                                for item in result['matches']))
            generate.assert_not_called()
            llm.assert_not_called()
            native.assert_not_called()
        self.assertEqual(self.client.get('/api/jobs').json()['jobs'], [])

    def test_purpose_space_rotation_and_empty_results_remain_explicit(self):
        response = self.post('/api/discovery', {
            'purpose': 'organization', 'available_space': {'width': 60, 'depth': 90, 'height': 18}})
        self.assertEqual(response.status_code, 200, response.text)
        result = response.json()
        self.assertEqual(result['total_in_purpose'], 3)
        self.assertEqual(result['excluded_count'], 2)
        self.assertEqual([item['project']['id'] for item in result['matches']], ['small-parts-tray'])
        fit = result['matches'][0]['space_fit']
        self.assertEqual(fit['status'], 'fits_rotated')
        self.assertEqual(fit['orientation'], 'rotated_90')
        self.assertEqual(fit['dimensions_mm'], {'width': 60, 'depth': 90, 'height': 18})
        self.assertEqual(result['matches'][0]['project']['parameters']['width'], 90)
        empty = self.post('/api/discovery', {'purpose': 'cables', 'available_space': {'height': 11}})
        self.assertEqual(empty.status_code, 200, empty.text)
        self.assertEqual(empty.json()['matches'], [])
        self.assertEqual(empty.json()['excluded_count'], 2)
        self.assertTrue(empty.json()['limits'])
        self.assertEqual(self.client.get('/api/jobs').json()['jobs'], [])

    def test_discovery_request_boundary_is_session_protected_and_strict(self):
        self.assertEqual(self.client.post('/api/discovery', json={}).status_code, 403)
        self.assertEqual(self.client.post('/api/discovery', json={}, headers={
            **self.headers, 'Origin': 'https://untrusted.example'}).status_code, 403)
        for payload in (
            {'purpose': 'external-models'}, {'available_space': {'width': True}},
            {'available_space': {'width': '90'}}, {'available_space': {'depth': 0}},
            {'available_space': {'height': -1}}, {'available_space': {'width': 10001}},
            {'available_space': {'diameter': 90}}, {'available_space': []},
            {'printer_model': 'not inferred'},
        ):
            with self.subTest(payload=payload):
                response = self.post('/api/discovery', payload)
                self.assertEqual(response.status_code, 422, response.text)
        nonfinite = self.client.post('/api/discovery', content='{"available_space":{"width":NaN}}',
                                    headers={**self.headers, 'Content-Type': 'application/json'})
        self.assertEqual(nonfinite.status_code, 400)
        oversized = self.client.post('/api/discovery', content=b'x' * (2 * 1024 * 1024 + 1),
                                    headers={**self.headers, 'Content-Type': 'application/json'})
        self.assertEqual(oversized.status_code, 413)
        self.assertEqual(self.client.get('/api/jobs').json()['jobs'], [])

    def test_customized_real_cad_keeps_recipe_in_job_manifest_bundle_and_restart(self):
        project = self.project()
        selection = {'id': project['id'], 'recipe_sha256': project['recipe_sha256']}
        response = self.post('/api/models', {
            **project['parameters'], 'width': 152, 'project_selection': selection})
        self.assertEqual(response.status_code, 200, response.text)
        job = response.json()
        self.assertEqual(job['status'], 'geometry_validated')
        self.assertEqual(job['result']['dimensions_mm'], {'x': 152, 'y': 90, 'z': 30})
        self.assertTrue(job['result']['mesh']['faces'])
        source = job['design_source']
        self.assertEqual(source['kind'], 'project_catalog')
        self.assertEqual(source['project_id'], 'desk-sorter')
        self.assertTrue(source['customized'])
        self.assertEqual(source['changed_parameters'], ['width'])
        recipe = {key: value for key, value in project.items() if key != 'recipe_sha256'}
        self.assertEqual(source['recipe'], recipe)
        canonical = json.dumps(recipe, ensure_ascii=False, sort_keys=True,
                               separators=(',', ':'), allow_nan=False).encode('utf-8')
        self.assertEqual(source['recipe_sha256'], hashlib.sha256(canonical).hexdigest())
        self.assertEqual(source['recipe']['parameters']['width'], 150)
        self.assertEqual(job['result']['parameters']['width'], 152)
        self.assertNotIn('project_selection', job['result']['parameters'])
        self.assertEqual(job['result']['print_status'], 'not_tested')
        self.assertIsNone(job['latest_slice'])

        manifest = self.client.get(job['artifacts']['manifest']).json()
        self.assertEqual(manifest['design_source'], source)
        self.assertEqual(manifest['parameters'], job['result']['parameters'])
        self.assertEqual(manifest['physical_print_status'], 'not_tested')
        self.assertEqual(manifest['slicer_status'], 'not_run')
        for kind, metadata in manifest['artifacts'].items():
            content = self.client.get(job['artifacts'][kind]).content
            self.assertEqual(len(content), metadata['bytes'])
            self.assertEqual(hashlib.sha256(content).hexdigest(), metadata['sha256'])
        with zipfile.ZipFile(io.BytesIO(self.client.get(job['bundle_url']).content)) as archive:
            self.assertIsNone(archive.testzip())
            self.assertEqual(json.loads(archive.read('manifest.json'))['design_source'], source)
            self.assertEqual(json.loads(archive.read('job.json'))['design_source'], source)
        with TestClient(create_app(self.root, test_mode=True)) as reopened:
            stored = reopened.get('/api/jobs/' + job['id']).json()
            self.assertEqual(stored['design_source'], source)
            self.assertEqual(stored['result']['parameters']['width'], 152)

    def test_bad_stale_and_spoofed_selections_fail_before_reserving_a_job(self):
        project = self.project()
        valid = {'id': project['id'], 'recipe_sha256': project['recipe_sha256']}
        cases = [
            ({**project['parameters'], 'project_selection': {**valid, 'id': 'does-not-exist'}}, 422),
            ({**project['parameters'], 'project_selection': {**valid, 'recipe_sha256': '0' * 64}}, 409),
            ({**self.project('three-cable-rest')['parameters'], 'project_selection': valid}, 422),
            ({**project['parameters'], 'project_selection': {**valid, 'source': {'license': 'spoofed'}}}, 422),
            ({**project['parameters'], 'project_selection': {'id': project['id']}}, 422),
            ({**project['parameters'], 'project_selection': []}, 422),
            ({**project['parameters'], 'project_selection': {**valid, 'recipe_sha256': 'not-a-digest'}}, 422),
            ({**project['parameters'], 'design_source': {'kind': 'verified'}}, 422),
        ]
        with patch.object(self.app.state.store, 'reserve', wraps=self.app.state.store.reserve) as reserve, \
             patch('print_agent.app.generate_model') as generate:
            for payload, expected_status in cases:
                with self.subTest(payload=payload):
                    response = self.post('/api/models', payload)
                    self.assertEqual(response.status_code, expected_status, response.text)
            reserve.assert_not_called()
            generate.assert_not_called()
        self.assertEqual(self.client.get('/api/jobs').json()['jobs'], [])

    def test_same_dimensions_without_selection_do_not_invent_origin(self):
        project = self.project('small-parts-tray')
        response = self.post('/api/models', project['parameters'])
        self.assertEqual(response.status_code, 200, response.text)
        job = response.json()
        self.assertNotIn('design_source', job)
        self.assertNotIn('design_source', self.client.get(job['artifacts']['manifest']).json())

    def test_selected_source_does_not_bypass_geometry_validation(self):
        project = self.project('small-parts-tray')
        response = self.post('/api/models', {
            **project['parameters'], 'width': 10, 'depth': 10, 'wall': 8,
            'project_selection': {'id': project['id'], 'recipe_sha256': project['recipe_sha256']}})
        self.assertEqual(response.status_code, 422, response.text)
        jobs = self.client.get('/api/jobs').json()['jobs']
        self.assertEqual(len(jobs), 1)
        failed = self.client.get('/api/jobs/' + jobs[0]['id']).json()
        self.assertEqual(failed['status'], 'failed')
        self.assertFalse(failed['artifacts'])


if __name__ == '__main__':
    unittest.main()
