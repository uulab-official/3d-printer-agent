import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient
from print_agent.app import create_app


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
