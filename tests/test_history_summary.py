import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from print_agent.app import create_app


class HistorySummaryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.client = TestClient(create_app(Path(self.temp.name), test_mode=True))
        self.headers = {'X-Session-Token': self.client.get('/api/bootstrap').json()['session_token']}

    def tearDown(self):
        self.client.close()
        self.temp.cleanup()

    def make(self, **values):
        response = self.client.post('/api/models', json=values, headers=self.headers)
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def test_list_items_carry_only_distinguishing_display_facts(self):
        thin = self.make(template='tray', width=120, depth=80, height=35, wall=0.8)
        stand = self.make(template='phone_stand', width=70, depth=80, height=90, wall=4, bottom=4,
                          lean_angle=70, device_thickness=10, lip_height=12, fit_clearance=1)
        self.client.post(f"/api/jobs/{stand['id']}/outcome", json={'result': 'success', 'notes': '잘 섬'}, headers=self.headers)
        jobs = {job['id']: job for job in self.client.get('/api/jobs?limit=10').json()['jobs']}
        self.assertEqual(jobs[thin['id']]['summary'], {'parameters': {'wall': 0.8, 'bottom': 2.0, 'dividers': 0},
                                                       'printability': 'review'})
        self.assertEqual(jobs[stand['id']]['summary']['parameters'],
                         {'wall': 4.0, 'bottom': 4.0, 'device_thickness': 10.0, 'fit_clearance': 1.0,
                          'lean_angle': 70.0, 'lip_height': 12.0})
        self.assertEqual(jobs[stand['id']]['user_outcome']['notes'], '잘 섬')
        for job in jobs.values():
            self.assertNotIn('mesh', job['summary'])
            self.assertNotIn('artifacts', job)


if __name__ == '__main__':
    unittest.main()
