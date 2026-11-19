"""Print attempt history: a model and the earlier models it was edited from, as recorded."""
import json
from pathlib import Path
import tempfile
import unittest

from fastapi.testclient import TestClient

from print_agent.app import create_app

BASE = {'template': 'cable_comb', 'width': 80, 'depth': 18, 'height': 12, 'wall': 2, 'bottom': 2,
        'slots': 5, 'cable_diameter': 6, 'fit_clearance': 0.2}


class AttemptHistoryTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.client = TestClient(create_app(self.root, test_mode=True))
        token = self.client.get('/api/bootstrap').json()['session_token']
        self.headers = {'X-Session-Token': token}

    def tearDown(self):
        self.client.close()
        self.temporary.cleanup()

    def post(self, path, payload):
        response = self.client.post(path, json=payload, headers=self.headers)
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def edited(self, parent, text):
        plan = self.post('/api/model-edits/plan', {'text': text, 'base_parameters': parent['result']['parameters'],
                                                  'parent_job_id': parent['id']})
        self.assertEqual(plan['status'], 'ready', plan)
        review = plan['review']
        return self.post('/api/models', {**review['parameters'], 'model_edit': review['selection']})

    def history(self, job_id):
        return self.client.get(f'/api/jobs/{job_id}/attempts')

    def test_chain_keeps_each_attempts_outcome_and_the_changes_between_them(self):
        first = self.post('/api/models', BASE)
        self.post(f'/api/jobs/{first["id"]}/outcome', {'result': 'failure', 'notes': '안 들어감', 'reasons': ['too_tight']})
        second = self.edited(first, '여유 0.2mm 늘려줘')
        self.post(f'/api/jobs/{second["id"]}/outcome', {'result': 'failure', 'notes': '', 'reasons': ['weak']})
        third = self.edited(second, '벽 두께 0.4mm 늘려줘')

        body = self.history(third['id']).json()
        self.assertEqual(body['stopped'], None)
        self.assertEqual([item['job_id'] for item in body['attempts']], [third['id'], second['id'], first['id']])
        newest, middle, oldest = body['attempts']
        self.assertIsNone(newest['user_outcome'])
        self.assertEqual(middle['user_outcome']['reasons'], ['weak'])
        self.assertEqual((oldest['user_outcome']['result'], oldest['user_outcome']['source']), ('failure', 'user_reported'))
        self.assertIsNone(oldest['changes_from_parent'])
        self.assertEqual(middle['changes_from_parent']['changes'], [{'field': 'fit_clearance', 'before': 0.2, 'after': 0.4}])
        self.assertEqual(newest['changes_from_parent']['request_text'], '벽 두께 0.4mm 늘려줘')
        self.assertFalse(any(item['sent_to_printer'] or item['sliced'] for item in body['attempts']))
        self.assertNotIn('notes', json.dumps(body))  # history repeats recorded facts, not free text

        # Reading history changes nothing.
        before = (self.root / 'jobs' / first['id'] / 'job.json').read_bytes()
        self.history(third['id'])
        self.assertEqual((self.root / 'jobs' / first['id'] / 'job.json').read_bytes(), before)

        alone = self.history(first['id']).json()
        self.assertEqual([item['job_id'] for item in alone['attempts']], [first['id']])

    def test_unknown_job_is_404_and_a_lost_parent_stops_the_walk(self):
        self.assertEqual(self.history('f' * 32).status_code, 404)
        self.assertNotEqual(self.history('../x').status_code, 200)
        first = self.post('/api/models', BASE)
        second = self.edited(first, '여유 0.2mm 늘려줘')
        (self.root / 'jobs' / first['id'] / 'job.json').write_text('{broken', encoding='utf-8')
        body = self.history(second['id']).json()
        self.assertEqual(([item['job_id'] for item in body['attempts']], body['stopped']), ([second['id']], 'unreadable'))


if __name__ == '__main__':
    unittest.main()
