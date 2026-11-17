"""Caliper measurements recorded with an outcome: validation, comparison and storage."""
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from print_agent.app import create_app
from print_agent.measurements import review_measurements, validate_measurements

EXPECTED = {'x': 120.0, 'y': 80.0, 'z': 35.0}


class MeasurementTests(unittest.TestCase):
    def test_review_reports_deviation_spread_and_tolerance(self):
        samples = [{'x': 119.8, 'y': 80.1, 'z': 35.0}, {'x': 119.9, 'y': 80.0, 'z': 35.1}, {'x': 119.85, 'y': 79.95, 'z': 34.95}]
        review = review_measurements(EXPECTED, samples, 0.2)
        self.assertEqual(review['status'], 'within')
        self.assertEqual(review['source'], 'user_measured')
        self.assertEqual(review['axes']['x'], {'expected': 120.0, 'mean_deviation': -0.15, 'max_abs_deviation': 0.2, 'spread': 0.1})
        self.assertEqual(review['notes'], [])
        outside = review_measurements(EXPECTED, samples[:1], 0.1)
        self.assertEqual(outside['status'], 'outside')
        self.assertTrue(any('3개 이상' in note for note in outside['notes']))
        shrunk = review_measurements(EXPECTED, [{'x': 119.5, 'y': 79.6, 'z': 35.0}], None)
        self.assertEqual(shrunk['status'], 'not_judged')
        self.assertTrue(any('X·Y' in note for note in shrunk['notes']))
        self.assertIsNone(review_measurements(None, samples, 0.2))

    def test_validation(self):
        self.assertEqual(validate_measurements(None, None), ([], None))
        self.assertEqual(validate_measurements([{'x': 1, 'y': 2, 'z': 3}], 0.2), ([{'x': 1.0, 'y': 2.0, 'z': 3.0}], 0.2))
        for samples, tolerance in (([{'x': 1, 'y': 2}], None), ([{'x': 0, 'y': 2, 'z': 3}], None), ([{'x': True, 'y': 2, 'z': 3}], None),
                                   ([{'x': '1', 'y': 2, 'z': 3}], None), ([{'x': 1, 'y': 2, 'z': 3}] * 6, None),
                                   ([{'x': 1, 'y': 2, 'z': 3}], 9), (None, 0.2), ([{'x': float('nan'), 'y': 2, 'z': 3}], None)):
            with self.subTest(samples=str(samples)[:40], tolerance=tolerance), self.assertRaises(ValueError):
                validate_measurements(samples, tolerance)


class MeasurementAPITests(unittest.TestCase):
    def test_measurements_are_stored_with_the_outcome_and_compared_with_cad(self):
        with tempfile.TemporaryDirectory() as temp, TestClient(create_app(Path(temp), test_mode=True)) as client:
            headers = {'X-Session-Token': client.get('/api/bootstrap').json()['session_token']}
            job = client.post('/api/models', json={'template': 'tray'}, headers=headers).json()
            samples = [{'x': 119.8, 'y': 80.1, 'z': 35.0}] * 3
            saved = client.post(f"/api/jobs/{job['id']}/outcome", headers=headers,
                                json={'result': 'success', 'measurements': samples, 'tolerance_mm': 0.25}).json()
            outcome = saved['user_outcome']
            self.assertEqual(outcome['measurements'], samples)
            self.assertEqual(outcome['measurement_review']['status'], 'within')
            self.assertEqual(outcome['measurement_review']['axes']['x']['expected'], 120.0)
            self.assertEqual(outcome['source'], 'user_reported')
            refused = client.post(f"/api/jobs/{job['id']}/outcome", headers=headers,
                                  json={'result': 'not_tested', 'measurements': samples})
            self.assertEqual(refused.status_code, 422)
            self.assertEqual(client.post(f"/api/jobs/{job['id']}/outcome", headers=headers,
                                         json={'result': 'success', 'tolerance_mm': 0.2}).status_code, 422)
            plain = client.post(f"/api/jobs/{job['id']}/outcome", headers=headers, json={'result': 'success'}).json()
            self.assertNotIn('measurements', plain['user_outcome'])


if __name__ == '__main__':
    unittest.main()
