"""Wall hook: one solid printed as modelled, teardrop screw holes, requests and edits."""
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from print_agent.app import create_app
from print_agent.geometry import generate_model, template_catalog
from print_agent.geometry_rules import _validate_geometry
from print_agent.model_edits import normalize_parameters, plan_model_edit
from print_agent.planner import plan_from_text
from print_agent.recovery import recovery_plan
from print_agent.schemas import GeometryRequest

HOOK = dict(template='wall_hook', width=20, depth=35, height=50, wall=4, bottom=4, hole_diameter=4, lip_height=10)


class WallHookGeometryTests(unittest.TestCase):
    def test_one_solid_at_the_requested_size_without_supports(self):
        with tempfile.TemporaryDirectory() as folder:
            result = generate_model(GeometryRequest(**HOOK), Path(folder))
        self.assertEqual(result['dimensions_mm'], {'x': 20.0, 'y': 35.0, 'z': 50.0})
        self.assertTrue(all(check['passed'] for check in result['checks']))
        items = {item['id']: item for item in result['printability']['items']}
        self.assertEqual(items['overhang']['status'], 'pass')  # teardrop holes need no support
        self.assertEqual(items['bed_contact']['status'], 'pass')
        # Two holes really cut: less than the solid L+tip volume.
        solid = 20 * 35 * 4 + 20 * 4 * (50 - 4) + 20 * 4 * 10
        self.assertLess(result['volume_mm3'], solid - 100)
        self.assertTrue(any('나사' in warning for warning in result['warnings']))

    def test_rules_refuse_impossible_hooks(self):
        for change, message in (({'lip_height': 50}, '끝 턱'), ({'depth': 12}, '걸이 길이'), ({'width': 10, 'hole_diameter': 8}, '가로'),
                                ({'height': 15}, '높이')):
            with self.subTest(change=change), self.assertRaisesRegex(ValueError, message):
                _validate_geometry(GeometryRequest(**{**HOOK, **change}).model_dump())

    def test_catalog_and_canonical_shape(self):
        catalog = {item['id']: item for item in template_catalog()}
        self.assertIn('wall_hook', catalog)
        self.assertEqual(catalog['wall_hook']['defaults']['depth'], 35)
        canonical = GeometryRequest(**HOOK).model_dump()
        self.assertIn('lip_height', canonical)
        self.assertNotIn('text', canonical)
        self.assertNotIn('lean_angle', canonical)


class WallHookLanguageTests(unittest.TestCase):
    def test_requests_choose_the_hook_with_item_sizes(self):
        cases = {'헤드폰 걸이 만들어줘': {'width': 30, 'depth': 50}, '열쇠 걸 후크 폭 30mm': {'width': 30, 'depth': 35},
                 '가방 걸이 나사 구멍 5mm': {'hole_diameter': 5, 'bottom': 6},
                 '벽걸이 후크 걸이 길이 40mm 끝 턱 12mm 파란색': {'depth': 40, 'lip_height': 12, 'color': 'blue'}}
        for text, expected in cases.items():
            with self.subTest(text=text):
                result = plan_from_text(text)
                self.assertEqual(result['status'], 'ready', result)
                self.assertEqual(result['parameters']['template'], 'wall_hook')
                for key, value in expected.items():
                    self.assertEqual(result['parameters'][key], value)

    def test_other_requests_are_unchanged(self):
        self.assertEqual(plan_from_text('휴대폰 거치대')['parameters']['template'], 'phone_stand')
        self.assertEqual(plan_from_text('나사 구멍 있는 수납함')['status'], 'needs_input')
        self.assertIn('벽걸이 후크', plan_from_text('헤드폰 거치대')['questions'][0])

    def test_edits_use_hook_words(self):
        base = normalize_parameters(GeometryRequest(**HOOK).model_dump())
        for text, change in (('걸이 길이 10mm 늘려줘', ('depth', 35.0, 45.0)), ('끝 턱 15mm로', ('lip_height', 10.0, 15.0)),
                             ('나사 구멍 5mm로 바꿔줘', ('hole_diameter', 4.0, 5.0)), ('걸이 두께 6mm', ('bottom', 4.0, 6.0))):
            with self.subTest(text=text):
                review = plan_model_edit(text, base)['review']
                self.assertEqual([(c['field'], c['before'], c['after']) for c in review['changes']], [change])
        self.assertEqual(plan_model_edit('가로 6mm로', base)['status'], 'needs_input')

    def test_recovery_strengthens_a_weak_hook(self):
        item = recovery_plan(GeometryRequest(**HOOK).model_dump(), ['weak'])['items'][0]
        self.assertEqual(item['model_edit']['changes'][0]['field'], 'wall')


class WallHookAPITests(unittest.TestCase):
    def test_generated_hook_is_stored_with_its_title(self):
        with tempfile.TemporaryDirectory() as temp, TestClient(create_app(Path(temp), test_mode=True)) as client:
            headers = {'X-Session-Token': client.get('/api/bootstrap').json()['session_token']}
            job = client.post('/api/models', json=HOOK, headers=headers).json()
            self.assertEqual(job['status'], 'geometry_validated')
            self.assertEqual(job['title'], '벽걸이 후크 · 20 × 35 × 50 mm')
            self.assertEqual(client.get('/api/jobs').json()['jobs'][0]['template'], 'wall_hook')


if __name__ == '__main__':
    unittest.main()
