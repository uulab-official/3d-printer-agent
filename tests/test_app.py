import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient
from print_agent.app import create_app
from tests.test_profiles import fixture_profile, fixture_setup


class APITests(unittest.TestCase):
    def test_bad_optional_llm_url_does_not_break_template_bootstrap(self):
        for url in ('http://[::1','http://127.0.0.1:abc/v1','https://example.com:999999/v1'):
            with self.subTest(url=url), patch.dict('os.environ',{'PPA_LLM_BASE_URL':url,'PPA_LLM_MODEL':'test-model'}):
                response=self.client.get('/api/bootstrap')
                self.assertEqual(response.status_code,200)
                data=response.json()
                self.assertFalse(data['provider']['configured'])
                self.assertEqual(data['provider']['status'],'invalid_url')
                self.assertEqual(len(data['templates']),3)

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.app = create_app(Path(self.temp.name), test_mode=True)
        self.client = TestClient(self.app)
        bootstrap = self.client.get('/api/bootstrap')
        self.assertEqual(bootstrap.status_code, 200)
        self.headers = {'X-Session-Token':bootstrap.json()['session_token']}

    def tearDown(self):
        self.client.close()
        self.temp.cleanup()

    def test_bootstrap_has_real_capabilities_and_no_secrets(self):
        with patch.dict('os.environ', {'PPA_LLM_API_KEY':'SECRET_TOKEN'}):
            response = self.client.get('/api/bootstrap')
        data = response.json()
        self.assertEqual(len(data['templates']), 3)
        self.assertEqual(data['environment']['printer_status'], 'not_checked')
        self.assertNotIn('SECRET_TOKEN', response.text)
        self.assertIn("frame-ancestors 'none'", response.headers['content-security-policy'])
        self.assertEqual(response.headers['cache-control'], 'no-store')

    def test_cross_origin_or_missing_token_cannot_mutate(self):
        payload = {'text':'수납함 120x80x35 mm'}
        self.assertEqual(self.client.post('/api/plan', json=payload).status_code, 403)
        self.assertEqual(self.client.post('/api/plan', json=payload, headers={**self.headers,'Origin':'https://untrusted.example'}).status_code, 403)
        self.assertEqual(self.client.post('/api/plan', json=payload, headers={**self.headers,'Origin':'http://testserver'}).status_code, 200)

    def test_strict_bounded_json(self):
        for body in ('{"template":"tray","width":NaN}', '{"width":Infinity}'):
            result = self.client.post('/api/models',content=body,headers={**self.headers,'Content-Type':'application/json'})
            self.assertEqual(result.status_code, 400)
        response = self.client.post('/api/plan', content=b'x'*(2*1024*1024+1),headers={**self.headers,'Content-Type':'application/json'})
        self.assertEqual(response.status_code, 413)

    def test_slicer_probe_is_explicit_authenticated_and_accepts_no_command(self):
        environment = {'available': True, 'path': '/configured/bambu-studio',
                       'version': '02.09.01.70', 'cli_supported': True,
                       'capabilities': ['slice'], 'diagnostics': [], 'printer_status': 'not_checked'}
        with patch('print_agent.app.probe_environment', return_value=environment, create=True) as probe:
            self.assertEqual(self.client.get('/api/bootstrap').status_code, 200)
            probe.assert_not_called()
            self.assertEqual(self.client.post('/api/slicer/probe', json={}).status_code, 403)
            self.assertEqual(self.client.post('/api/slicer/probe', json={},
                headers={**self.headers, 'Origin': 'https://untrusted.example'}).status_code, 403)
            self.assertEqual(self.client.post('/api/slicer/probe', json={'path': '/some/other/program'},
                headers=self.headers).status_code, 422)
            probe.assert_not_called()
            response = self.client.post('/api/slicer/probe', json={}, headers=self.headers)
            self.assertEqual(response.status_code, 200, response.text)
            self.assertEqual(response.json(), environment)
            probe.assert_called_once_with()

    def test_slice_request_allows_full_config_budget_but_remains_bounded(self):
        store = self.app.state.store
        bundle = {'large_native_field': 'x' * (2 * 1024 * 1024)}
        plan = {'ready': False, 'diagnostics': ['Synthetic API boundary fixture']}
        with patch.object(store, 'get', return_value={'status': 'geometry_validated'}), \
             patch.object(store, 'artifact_path', return_value=Path(self.temp.name) / 'model.3mf'), \
             patch.object(store, 'directory', return_value=Path(self.temp.name)), \
             patch.object(store, 'record_slice'), \
             patch('print_agent.app.prepare_slice', return_value=plan) as prepare, \
             patch('print_agent.app.execute_slice') as execute:
            response = self.client.post('/api/slice', json={'job_id': 'synthetic-job',
                'config_bundle': bundle, 'execute': False}, headers=self.headers)
            self.assertEqual(response.status_code, 200, response.text)
            self.assertEqual(response.json(), {'plan': plan, 'execution': None})
            self.assertEqual(prepare.call_args.args[2], bundle)
            execute.assert_not_called()
            response = self.client.post('/api/slice', content=b'x' * (8 * 1024 * 1024 + 1),
                headers={**self.headers, 'Content-Type': 'application/json'})
            self.assertEqual(response.status_code, 413)
            self.assertIn('8 MiB', response.json()['detail'])
            prepare.assert_called_once()

    def test_invalid_host_rejected(self):
        self.assertEqual(self.client.get('/api/bootstrap',headers={'Host':'untrusted.example'}).status_code, 400)

    def test_generation_files_bundle_and_outcome(self):
        response = self.client.post('/api/models', json={'template':'tray','width':60,'depth':40,'height':15}, headers=self.headers)
        self.assertEqual(response.status_code, 200, response.text)
        job = response.json()
        self.assertEqual(job['status'], 'geometry_validated')
        self.assertTrue(job['result']['mesh']['faces'])
        for kind in ('stl','step','three_mf','source','manifest'):
            artifact = self.client.get(job['artifacts'][kind])
            self.assertEqual(artifact.status_code, 200)
            self.assertTrue(artifact.content)
        bundle = self.client.get(job['bundle_url'])
        self.assertEqual(bundle.headers['content-type'], 'application/zip')
        import io, zipfile
        with zipfile.ZipFile(io.BytesIO(bundle.content)) as archive:
            self.assertIn('manifest.json', archive.namelist())
            self.assertIn('model.step', archive.namelist())
        report = self.client.post('/api/jobs/'+job['id']+'/outcome',json={'result':'success','notes':'user result'},headers=self.headers).json()
        self.assertEqual(report['user_outcome']['source'], 'user_reported')
        self.assertEqual(report['result']['print_status'], 'not_tested')

    def test_invalid_geometry_does_not_create_downloads(self):
        response=self.client.post('/api/models',json={'width':10,'depth':10,'height':2,'wall':8},headers=self.headers)
        self.assertEqual(response.status_code, 422)
        jobs=self.client.get('/api/jobs').json()['jobs']
        self.assertEqual(jobs[0]['status'],'failed')
        self.assertFalse(self.client.get('/api/jobs/'+jobs[0]['id']).json()['artifacts'])

    def test_nonapplicable_parameters_are_not_ignored(self):
        response=self.client.post('/api/models',json={'template':'tray','slots':10},headers=self.headers)
        self.assertEqual(response.status_code,422)

    def test_llm_not_configured_is_not_fake_template_fallback(self):
        with patch.dict('os.environ',{},clear=True):
            response=self.client.post('/api/plan',json={'text':'수납함','mode':'llm'},headers=self.headers)
        self.assertEqual(response.status_code,422)

    def test_price_comparison_and_profile_missing_evidence(self):
        result=self.client.post('/api/offers/compare',json={'offers':[{'name':'A','price':10000,'grams':1000,'shipping':None,'currency':'KRW'}]},headers=self.headers).json()
        self.assertFalse(result['live_prices'])
        profile=self.client.post('/api/profiles/review',json={'profile':{},'setup':{}},headers=self.headers)
        self.assertEqual(profile.status_code,200)
        self.assertFalse(profile.json()['can_prepare_profile'])

    def test_imported_presets_resolve_values_and_keep_original_evidence(self):
        parent = fixture_profile()['settings']
        parent['name'] = 'Synthetic parent; not a recommendation'
        child = fixture_profile()
        child['settings'] = {
            'type': 'filament', 'name': 'Synthetic child; not a recommendation',
            'inherits': parent['name'], 'nozzle_temperature': ['215'],
        }
        documents = [
            {'filename': 'parent.json', 'profile': parent},
            {'filename': 'child.json', 'profile': child},
        ]
        response = self.client.post('/api/profiles/resolve', json={
            'documents': documents, 'target_name': child['settings']['name'],
            'setup': fixture_setup(),
        }, headers=self.headers)
        self.assertEqual(response.status_code, 200, response.text)
        report = response.json()
        self.assertEqual(report['status'], 'resolved')
        self.assertFalse(report['full_config'])
        self.assertFalse(report['native_verified'])
        self.assertEqual(report['setup'], fixture_setup())
        self.assertEqual(report['resolved_profile']['settings']['nozzle_temperature'], ['215'])
        self.assertEqual(report['resolved_profile']['settings']['filament_flow_ratio'], ['0.98'])
        self.assertNotIn('inherits', report['resolved_profile']['settings'])
        self.assertEqual(report['field_sources']['filament_flow_ratio']['filename'], 'parent.json')
        self.assertEqual(report['field_sources']['nozzle_temperature']['filename'], 'child.json')
        self.assertEqual(report['review']['decision'], 'ready_to_prepare')
        self.assertEqual(report['review']['validation_status'], 'unverified')
        for original, retained in zip(documents, report['documents']):
            self.assertEqual(retained['profile'], original['profile'])
            self.assertEqual(len(retained['sha256']), 64)

    def test_missing_imported_parent_returns_actionable_report(self):
        payload = {'documents': [{'filename': 'child.json', 'profile': {
            'name': 'Child', 'type': 'filament', 'inherits': 'Missing parent',
        }}], 'target_name': 'Child', 'setup': {}}
        response = self.client.post('/api/profiles/resolve', json=payload, headers=self.headers)
        self.assertEqual(response.status_code, 200, response.text)
        report = response.json()
        self.assertEqual(report['status'], 'needs_input')
        self.assertIsNone(report['resolved_profile'])
        self.assertIsNone(report['review'])
        self.assertFalse(report['full_config'])
        self.assertIn('Missing parent', str(report['issues']))
        self.assertEqual(report['documents'][0]['profile']['inherits'], 'Missing parent')

    def test_preset_import_shape_and_document_limits_are_enforced(self):
        document = {'filename': 'profile.json', 'profile': {'name': 'Profile'}}
        for payload in (
            {'documents': [], 'target_name': 'Profile'},
            {'documents': [document] * 65, 'target_name': 'Profile'},
            {'documents': [{'filename': 'profile.json', 'profile': []}], 'target_name': 'Profile'},
            {'documents': [{**document, 'open_path': '/tmp/preset.json'}], 'target_name': 'Profile'},
            {'documents': [document], 'target_name': ''},
            {'documents': [document], 'target_name': 'Profile', 'execute': True},
        ):
            with self.subTest(payload_keys=list(payload)):
                response = self.client.post('/api/profiles/resolve', json=payload, headers=self.headers)
                self.assertEqual(response.status_code, 422, response.text)

    def test_preset_import_uses_existing_local_request_boundary(self):
        payload = {'documents': [{'filename': 'p.json', 'profile': {'name': 'Profile'}}], 'target_name': 'Profile'}
        self.assertEqual(self.client.post('/api/profiles/resolve', json=payload).status_code, 403)
        self.assertEqual(self.client.post('/api/profiles/resolve', json=payload,
            headers={**self.headers, 'Origin': 'https://untrusted.example'}).status_code, 403)
        response = self.client.post('/api/profiles/resolve', content=b'x' * (8 * 1024 * 1024 + 1),
            headers={**self.headers, 'Content-Type': 'application/json'})
        self.assertEqual(response.status_code, 413)

    def test_deeply_nested_import_is_an_actionable_input_error(self):
        nested = 'synthetic leaf'
        for _ in range(500):
            nested = [nested]
        for location in ('profile', 'setup'):
            with self.subTest(location=location):
                profile = {'name': 'Deep synthetic preset'}
                setup = {}
                (profile if location == 'profile' else setup)['vendor_notes'] = nested
                payload = {'documents': [{'filename': 'deep.json', 'profile': profile}],
                           'target_name': profile['name'], 'setup': setup}
                with TestClient(self.app, raise_server_exceptions=False) as client:
                    response = client.post('/api/profiles/resolve', json=payload, headers=self.headers)
                self.assertEqual(response.status_code, 422, response.text)
                self.assertIn('중첩', response.json()['detail'])
