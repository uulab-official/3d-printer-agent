"""Contextual edits cross the real API/CAD boundary without replacing unknown work."""
import copy
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import AsyncMock, patch
import zipfile

from fastapi.testclient import TestClient

from print_agent.app import create_app
from tests.test_model_edits import javascript_json_roundtrip


BASE = {'template': 'tray', 'width': 150, 'depth': 90, 'height': 30,
        'wall': 2, 'bottom': 2, 'dividers': 2}


class ModelEditsAPITests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.app = create_app(self.root, test_mode=True)
        self.client = TestClient(self.app)
        self.bootstrap = self.client.get('/api/bootstrap').json()
        self.headers = {'X-Session-Token': self.bootstrap['session_token']}

    def tearDown(self):
        self.client.close()
        self.temporary.cleanup()

    def post(self, path, payload):
        return self.client.post(path, json=payload, headers=self.headers)

    def ready(self, base=None, **extra):
        response = self.post('/api/model-edits/plan', {
            'text': '높이를 5mm 늘려줘', 'base_parameters': base or BASE, **extra})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()['status'], 'ready', response.text)
        return response.json()

    def generate(self, payload=None):
        response = self.post('/api/models', payload or BASE)
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def test_plan_preserves_every_unmentioned_dimension_without_generating(self):
        plan = self.ready()
        review = plan['review']
        self.assertEqual(plan['engine'], 'template_rules')
        self.assertEqual(plan['capability'], 'current_template_parameters_only')
        self.assertEqual(review['changes'], [{'field': 'height', 'before': 30.0, 'after': 35.0}])
        expected = {**BASE, 'height': 35, 'slots': 5, 'cable_diameter': 6,
                    'inset_diameter': 52, 'inset_depth': 2, 'fit_clearance': 0.3}
        self.assertEqual(review['parameters'], expected)
        self.assertIsNone(review['selection']['parent'])
        self.assertEqual(self.client.get('/api/jobs').json()['jobs'], [])
        self.assertEqual(list((self.root / 'jobs').iterdir()), [])

    def test_browser_json_roundtrip_keeps_proposal_hash_on_generated_parented_record(self):
        base={'template':'cable_comb','width':80,'depth':18,'height':12,'wall':2,'bottom':2,
              'slots':5,'cable_diameter':6,'fit_clearance':-0.0}
        parent=self.generate(base)
        for text in ('높이를 5mm 늘려줘', '벽 두께를 0.2mm 줄여줘',
                     '높이를 5mm 늘려줘, 여유 0mm'):
            with self.subTest(text=text):
                response=self.post('/api/model-edits/plan',javascript_json_roundtrip({
                    'text':text,'base_parameters':base,'parent_job_id':parent['id']}))
                self.assertEqual(response.status_code,200,response.text)
                original=response.json()['review']
                wire=javascript_json_roundtrip(original)
                job=self.generate({**wire['parameters'],'model_edit':wire['selection']})
                self.assertEqual(job['model_edit']['review_sha256'],original['review_sha256'])
                self.assertEqual(job['model_edit']['selection']['parent'],original['selection']['parent'])
                self.assertEqual(job['model_edit']['base_sha256'],original['base_sha256'])
                self.assertEqual(job['model_edit']['parameters_sha256'],original['parameters_sha256'])
                manifest=self.client.get(job['artifacts']['manifest']).json()
                self.assertEqual(manifest['model_edit'],job['model_edit'])

    def test_route_is_session_protected_and_rejects_incomplete_or_coerced_context(self):
        payload = {'text': '높이를 5mm 늘려줘', 'base_parameters': BASE}
        self.assertEqual(self.client.post('/api/model-edits/plan', json=payload).status_code, 403)
        self.assertEqual(self.client.post('/api/model-edits/plan', json=payload, headers={
            **self.headers, 'Origin': 'https://untrusted.example'}).status_code, 403)
        cases = [
            {**payload, 'mode': 'execute'}, {**payload, 'command': 'run'},
            {**payload, 'parent_job_id': '../outside'}, {**payload, 'text': 'x' * 4001},
            {**payload, 'base_parameters': {'template': 'tray', 'height': 30}},
            {**payload, 'base_parameters': {**BASE, 'height': True}},
            {**payload, 'base_parameters': {**BASE, 'width': '150'}},
            {**payload, 'base_parameters': {**BASE, 'dividers': 2.0}},
            {**payload, 'base_parameters': {**BASE, 'width': 10, 'wall': 8}},
        ]
        with patch('print_agent.app.plan_model_edit_with_llm', new_callable=AsyncMock, create=True) as provider:
            for invalid in cases:
                with self.subTest(invalid=invalid):
                    response = self.post('/api/model-edits/plan', {**invalid, **({'mode': 'llm'} if invalid.get('mode') != 'execute' else {})})
                    self.assertEqual(response.status_code, 422, response.text)
            provider.assert_not_called()
        self.assertEqual(self.client.get('/api/jobs').json()['jobs'], [])

    def test_clarification_does_not_return_partial_changes(self):
        for text in ('조금 더 크게 해줘', '높이 40mm, 뚜껑도 추가해줘', '높이 40mm, 높이 50mm', '높이 2mm'):
            with self.subTest(text=text):
                response = self.post('/api/model-edits/plan', {'text': text, 'base_parameters': BASE})
                self.assertEqual(response.status_code, 200, response.text)
                self.assertEqual(response.json()['status'], 'needs_input')
                self.assertNotIn('review', response.json())
                self.assertNotIn('parameters', response.json())

    def test_parent_is_bound_to_verified_original_artifacts_and_base(self):
        parent = self.generate()
        manifest = self.client.get(parent['artifacts']['manifest'])
        model = self.client.get(parent['artifacts']['three_mf'])
        plan = self.ready(parent_job_id=parent['id'])
        identity = plan['review']['selection']['parent']
        self.assertEqual(identity['job_id'], parent['id'])
        self.assertEqual(identity['model_sha256'], hashlib.sha256(model.content).hexdigest())
        self.assertEqual(identity['manifest_sha256'], hashlib.sha256(manifest.content).hexdigest())
        normalized_base = json.dumps(parent['result']['parameters'], sort_keys=True, separators=(',', ':'),
                                     ensure_ascii=False, allow_nan=False).encode('utf-8')
        self.assertEqual(identity['parameters_sha256'], hashlib.sha256(normalized_base).hexdigest())
        with patch('print_agent.app.plan_model_edit_with_llm', new_callable=AsyncMock, create=True) as provider:
            response = self.post('/api/model-edits/plan', {'text': '높이 40mm', 'mode': 'llm',
                'base_parameters': {**BASE, 'height': 31}, 'parent_job_id': parent['id']})
            self.assertIn(response.status_code, (409, 422), response.text)
            missing = self.post('/api/model-edits/plan', {'text': '높이 40mm', 'mode': 'llm',
                'base_parameters': BASE, 'parent_job_id': 'a' * 32})
            self.assertEqual(missing.status_code, 404, missing.text)
            provider.assert_not_called()

    def test_accepted_edit_and_recipe_survive_cad_manifest_bundle_and_reopen(self):
        project = next(item for item in self.bootstrap['discovery']['projects'] if item['id'] == 'desk-sorter')
        source = {'id': project['id'], 'recipe_sha256': project['recipe_sha256']}
        parent = self.generate({**project['parameters'], 'project_selection': source})
        plan = self.ready(project['parameters'], parent_job_id=parent['id'])
        selection = plan['review']['selection']
        job = self.generate({**plan['review']['parameters'], 'project_selection': source, 'model_edit': selection})
        self.assertNotEqual(job['id'], parent['id'])
        record = job['model_edit']
        self.assertEqual(record, {**plan['review'], 'provenance': 'user_confirmed_parameters'})
        self.assertEqual(job['result']['dimensions_mm'], {'x': 150.0, 'y': 90.0, 'z': 35.0})
        self.assertEqual(job['result']['print_status'], 'not_tested')
        self.assertEqual(job['design_source']['project_id'], project['id'])
        self.assertEqual(job['design_source']['changed_parameters'], ['height'])
        manifest = self.client.get(job['artifacts']['manifest']).json()
        self.assertEqual(manifest['model_edit'], record)
        self.assertEqual(manifest['parameters'], plan['review']['parameters'])
        bundled = self.client.get(job['bundle_url'])
        self.assertEqual(bundled.status_code, 200, bundled.text[:100] if bundled.status_code != 200 else '')
        with zipfile.ZipFile(io.BytesIO(bundled.content)) as archive:
            self.assertIsNone(archive.testzip())
            self.assertEqual(json.loads(archive.read('manifest.json'))['model_edit'], record)
        self.client.close()
        with TestClient(create_app(self.root, test_mode=True)) as reopened:
            restored = reopened.get('/api/jobs/' + job['id']).json()
            self.assertEqual(restored['model_edit'], record)
            self.assertEqual(restored['design_source'], job['design_source'])
            self.assertEqual(reopened.get('/api/jobs/' + parent['id']).json()['result']['parameters']['height'], 30)

    def test_mismatched_result_or_changed_parent_never_reserves_or_generates(self):
        parent = self.generate()
        plan = self.ready(parent_job_id=parent['id'])
        valid = {**plan['review']['parameters'], 'model_edit': plan['review']['selection']}
        before = self.client.get('/api/jobs').json()['jobs']
        with patch.object(self.app.state.store, 'reserve', wraps=self.app.state.store.reserve) as reserve, \
             patch('print_agent.app.generate_model') as generate:
            mismatch = self.post('/api/models', {**valid, 'width': 151})
            self.assertEqual(mismatch.status_code, 422, mismatch.text)
            model_path = self.root / 'jobs' / parent['id'] / 'model.3mf'
            model_path.write_bytes(model_path.read_bytes() + b'altered')
            changed = self.post('/api/models', valid)
            self.assertEqual(changed.status_code, 409, changed.text)
            self.assertEqual(changed.json()['code'], 'model_edit_parent_changed')
            reserve.assert_not_called()
            generate.assert_not_called()
        self.assertEqual(self.client.get('/api/jobs').json()['jobs'], before)

    def test_deleted_parent_is_a_conflict_without_an_orphan_generation(self):
        parent = self.generate()
        plan = self.ready(parent_job_id=parent['id'])
        path = self.root / 'jobs' / parent['id'] / 'job.json'
        path.unlink()
        with patch.object(self.app.state.store, 'reserve', wraps=self.app.state.store.reserve) as reserve, \
             patch('print_agent.app.generate_model') as generate:
            response = self.post('/api/models', {**plan['review']['parameters'], 'model_edit': plan['review']['selection']})
            self.assertEqual(response.status_code, 409, response.text)
            self.assertEqual(response.json()['code'], 'model_edit_parent_changed')
            reserve.assert_not_called()
            generate.assert_not_called()

    def test_parentless_selection_can_generate_but_cannot_claim_a_different_result(self):
        plan = self.ready()
        altered = copy.deepcopy(plan['review']['selection'])
        altered['operations'][0]['value'] = 6
        response = self.post('/api/models', {**plan['review']['parameters'], 'model_edit': altered})
        self.assertEqual(response.status_code, 422, response.text)
        self.assertEqual(self.client.get('/api/jobs').json()['jobs'], [])
        job = self.generate({**plan['review']['parameters'], 'model_edit': plan['review']['selection']})
        self.assertIsNone(job['model_edit']['selection']['parent'])
        self.assertNotIn('design_source', job)

    def test_generation_does_not_coerce_or_default_approved_edit_geometry(self):
        plan = self.ready({**BASE, 'bottom': 1})
        payload = {**plan['review']['parameters'], 'model_edit': plan['review']['selection']}
        # Legacy GeometryRequest would turn each into the approved numeric
        # geometry, hiding what the caller actually supplied at this boundary.
        cases = [{**payload, 'height': '35'}, {**payload, 'bottom': True},
                 {key: value for key, value in payload.items() if key != 'wall'}]
        for invalid in cases:
            with self.subTest(invalid=invalid):
                response = self.post('/api/models', invalid)
                self.assertEqual(response.status_code, 422, response.text)
                self.assertEqual(self.client.get('/api/jobs').json()['jobs'], [])
                self.assertEqual(list((self.root / 'jobs').iterdir()), [])

    def test_paginated_history_returns_generated_edit_record_and_legacy_summary(self):
        parent = self.generate()
        plan = self.ready(parent_job_id=parent['id'])
        edited = self.generate({**plan['review']['parameters'], 'model_edit': plan['review']['selection']})
        record = edited['model_edit']
        summaries = {}
        url = '/api/jobs?limit=1'
        while url:
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200, response.text)
            page = response.json()
            self.assertEqual(len(page['jobs']), 1)
            item = page['jobs'][0]
            summaries[item['id']] = item
            url = '/api/jobs?limit=1&before=' + page['next_cursor'] if page['next_cursor'] else None
        self.assertEqual(set(summaries), {parent['id'], edited['id']})
        self.assertEqual(summaries[edited['id']].get('model_edit'), record)
        self.assertEqual(summaries[edited['id']]['model_edit']['selection']['request_text'], '높이를 5mm 늘려줘')
        # 'summary' carries display-only distinguishing facts (v0.10).
        summary_keys = {'id', 'created_at', 'title', 'template', 'status', 'user_outcome', 'summary'}
        self.assertEqual(set(summaries[parent['id']]), summary_keys)
        self.assertEqual(set(summaries[edited['id']]), summary_keys | {'model_edit'})
        self.assertNotIn(str(self.root), json.dumps(summaries, ensure_ascii=False))
        self.client.close()
        with TestClient(create_app(self.root, test_mode=True)) as reopened:
            page = reopened.get('/api/jobs?limit=20').json()
            restored = next(j for j in page['jobs'] if j['id'] == edited['id'])
            self.assertEqual(restored['model_edit'], record)

    def test_history_does_not_publish_tampered_or_missing_edit_record(self):
        plan = self.ready()
        edited = self.generate({**plan['review']['parameters'], 'model_edit': plan['review']['selection']})
        path = self.root / 'jobs' / edited['id'] / 'job.json'
        job = json.loads(path.read_bytes())
        job['model_edit']['selection']['request_text'] = 'tampered request without matching review hash'
        path.write_text(json.dumps(job, ensure_ascii=False), encoding='utf-8')
        original = path.read_bytes()
        for missing in (False, True):
            if missing:
                path.unlink()
            response = self.client.get('/api/jobs?limit=1')
            self.assertEqual(response.status_code, 200, response.text)
            summary = response.json()['jobs'][0]
            self.assertEqual(summary['id'], edited['id'])
            self.assertEqual(summary['status'], 'unreadable')
            self.assertNotIn('model_edit', summary)
            self.assertNotIn(str(self.root), response.text)
            if not missing:
                self.assertEqual(path.read_bytes(), original)


if __name__ == '__main__':
    unittest.main()
