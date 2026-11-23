"""Studio live preview: the generated solid as a mesh, nothing written or stored."""
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from print_agent.app import CAD_LOCK, create_app
from print_agent.geometry import generate_model, preview_model
from print_agent.schemas import GeometryRequest

KEY = dict(template='keycap', key_units=1, height=8, wall=1.3, bottom=2, text='A', text_size=5, text_depth=0.8, fit_clearance=0.15)


class PreviewModelTests(unittest.TestCase):
    def test_preview_matches_generation_without_files(self):
        spec = GeometryRequest(**KEY)
        preview = preview_model(spec)
        self.assertTrue(preview['preview_only'])
        self.assertNotIn('files', preview)
        with tempfile.TemporaryDirectory() as folder:
            generated = generate_model(spec, Path(folder))
        self.assertEqual(preview['parameters'], generated['parameters'])
        self.assertEqual(preview['dimensions_mm'], generated['dimensions_mm'])
        self.assertAlmostEqual(preview['volume_mm3'], generated['volume_mm3'], places=6)
        self.assertEqual(len(preview['mesh']['faces']), len(generated['mesh']['faces']))

    def test_colour_parts_are_previewed(self):
        preview = preview_model(GeometryRequest(template='name_tag', text='MINSU', color='white', accent_color='red'))
        self.assertEqual([part['key'] for part in preview['mesh']['parts']], ['base', 'letters'])
        self.assertEqual(len(preview['mesh']['face_parts']), len(preview['mesh']['faces']))

    def test_rules_still_refuse(self):
        with self.assertRaises(ValueError):
            preview_model(GeometryRequest(**{**KEY, 'height': 5}))


class PreviewApiTests(unittest.TestCase):
    def test_preview_route_stores_nothing_and_respects_the_cad_lock(self):
        with tempfile.TemporaryDirectory() as temp, TestClient(create_app(Path(temp), test_mode=True)) as client:
            headers = {'X-Session-Token': client.get('/api/bootstrap').json()['session_token']}
            before = client.get('/api/jobs', headers=headers).json()['jobs']
            response = client.post('/api/models/preview', json={'template': 'tray', 'width': 60, 'depth': 40, 'height': 20}, headers=headers)
            self.assertEqual(response.status_code, 200)
            body = response.json()
            self.assertTrue(body['preview_only'])
            self.assertEqual(body['dimensions_mm'], {'x': 60.0, 'y': 40.0, 'z': 20.0})
            self.assertEqual(client.get('/api/jobs', headers=headers).json()['jobs'], before)
            refused = client.post('/api/models/preview', json={**KEY, 'height': 5}, headers=headers)
            self.assertGreaterEqual(refused.status_code, 400)
            self.assertLess(refused.status_code, 500)
            self.assertTrue(CAD_LOCK.acquire(blocking=False))
            try:
                busy = client.post('/api/models/preview', json={'template': 'tray'}, headers=headers)
            finally:
                CAD_LOCK.release()
            self.assertEqual(busy.status_code, 409)
            self.assertEqual(busy.json()['code'], 'resource_busy')
            unauthenticated = client.post('/api/models/preview', json={'template': 'tray'})
            self.assertEqual(unauthenticated.status_code, 403)


if __name__ == '__main__':
    unittest.main()
