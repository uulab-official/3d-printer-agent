"""Round cup template: schema shape, real CAD, rules, requests, edits, review and titles."""
from pathlib import Path
import tempfile
import unittest

import cadquery as cq
from fastapi.testclient import TestClient
from pydantic import ValidationError

from print_agent.app import create_app
from print_agent.geometry import generate_model
from print_agent.geometry_rules import _validate_geometry
from print_agent.model_edits import plan_model_edit
from print_agent.planner import plan_from_text
from print_agent.recovery import recovery_plan
from print_agent.schemas import GeometryRequest

PLANTER = {'template': 'cup', 'width': 90, 'height': 80, 'wall': 2, 'bottom': 3, 'drain_hole': 8}


class CupGeometryTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)

    def tearDown(self):
        self.temporary.cleanup()

    def generate(self, name, **values):
        return generate_model(GeometryRequest(**values), self.root / name)

    def test_drain_hole_is_canonical_only_for_cups(self):
        self.assertEqual(GeometryRequest(**PLANTER).model_dump(mode='json')['drain_hole'], 8.0)
        self.assertNotIn('drain_hole', GeometryRequest(template='tray').model_dump(mode='json'))
        with self.assertRaises(ValidationError):
            GeometryRequest(template='tray', drain_hole=5)
        with self.assertRaises(ValidationError):
            GeometryRequest(template='cup', drain_hole=31)

    def test_planter_is_one_hollow_solid_with_a_drain_hole(self):
        result = self.generate('planter', **PLANTER)
        self.assertEqual(result['dimensions_mm'], {'x': 90.0, 'y': 90.0, 'z': 80.0})
        self.assertTrue(all(check['passed'] for check in result['checks']))
        shape = cq.importers.importStep(str(self.root / 'planter' / 'model.step')).val()
        self.assertEqual(len(shape.Solids()), 1)
        inside = {name: shape.isInside(cq.Vector(*point)) for name, point in {
            'drain hole': (0, 0, 1.5), 'cavity': (0, 0, 40), 'side wall': (44, 0, 40), 'floor': (10, 0, 1.5),
            'outside': (46, 0, 40)}.items()}
        self.assertEqual(inside, {'drain hole': False, 'cavity': False, 'side wall': True, 'floor': True, 'outside': False})
        review = {item['id']: item for item in result['printability']['items']}
        self.assertEqual(review['overhang']['status'], 'pass')
        self.assertIn('옆벽', review['min_thickness']['value'])
        self.assertTrue(any('배수 구멍' in warning or '받침 접시' in warning for warning in result['warnings']))

    def test_a_cup_without_a_hole_keeps_a_closed_floor(self):
        result = self.generate('cup', template='cup', width=70, height=100)
        shape = cq.importers.importStep(str(self.root / 'cup' / 'model.step')).val()
        self.assertTrue(shape.isInside(cq.Vector(0, 0, 1)))
        self.assertEqual(result['dimensions_mm']['z'], 100.0)

    def test_rules_explain_what_to_change(self):
        for values, words in ((dict(width=20, wall=6), '안쪽 지름'), (dict(height=5, bottom=2), '높이'),
                              (dict(drain_hole=2), '3 mm 이상'), (dict(width=30, wall=2, drain_hole=25), '이하로 줄이세요')):
            with self.subTest(values=values), self.assertRaisesRegex(ValueError, words):
                _validate_geometry(GeometryRequest(template='cup', **values).model_dump(mode='json'))


class CupRequestTests(unittest.TestCase):
    def test_everyday_round_containers_become_cups(self):
        for text, expected in (('연필꽂이 만들어줘', (70.0, 100.0, 0.0)), ('화분 지름 12cm', (120.0, 80.0, 8.0)),
                               ('원통 수납컵 지름 80mm 높이 60mm 배수 구멍 없이', (80.0, 60.0, 0.0)),
                               ('수저통 높이 150mm', (80.0, 150.0, 0.0)), ('원형 수납함 지름 60 높이 50 배수 구멍 5mm', (60.0, 50.0, 5.0))):
            with self.subTest(text=text):
                result = plan_from_text(text)
                self.assertEqual(result['status'], 'ready', result)
                p = result['parameters']
                self.assertEqual((p['template'], p['width'], p['height'], p['drain_hole']), ('cup', *expected))

    def test_lids_depth_and_coasters_are_not_guessed(self):
        self.assertIn('뚜껑', plan_from_text('뚜껑 있는 연필꽂이')['message'])
        self.assertIn('지름', plan_from_text('원통 수납컵 가로 80 세로 60')['message'])
        self.assertNotEqual(plan_from_text('컵 받침 만들어줘').get('parameters', {}).get('template'), 'cup')

    def test_edits_use_diameter_and_drain_hole_words(self):
        base = GeometryRequest(template='cup', width=70, height=100).model_dump(mode='json')
        for text, change in (('지름 10mm 늘려줘', ('width', 70.0, 80.0)), ('배수 구멍 8mm로 해줘', ('drain_hole', 0.0, 8.0)),
                             ('높이 120mm로 바꿔줘', ('height', 100.0, 120.0))):
            with self.subTest(text=text):
                review = plan_model_edit(text, base)['review']
                self.assertEqual([(c['field'], c['before'], c['after']) for c in review['changes']], [change])
        self.assertEqual(plan_model_edit('세로 10mm 늘려줘', base)['status'], 'needs_input')

    def test_weak_cup_offers_a_thicker_wall(self):
        plan = recovery_plan(GeometryRequest(template='cup', width=70, height=100).model_dump(mode='json'), ['weak'])
        self.assertEqual(plan['items'][0]['model_edit']['changes'], [{'field': 'wall', 'before': 2.0, 'after': 2.4}])


class CupApiTests(unittest.TestCase):
    def test_job_title_names_diameter_height_and_hole(self):
        with tempfile.TemporaryDirectory() as directory:
            client = TestClient(create_app(Path(directory), test_mode=True))
            token = client.get('/api/bootstrap').json()['session_token']
            job = client.post('/api/models', json=PLANTER, headers={'X-Session-Token': token}).json()
            self.assertEqual(job['title'], '원통 수납컵 · 지름 90 × 높이 80 mm · 배수 구멍')
            template = next(item for item in client.get('/api/bootstrap').json()['templates'] if item['id'] == 'cup')
            self.assertNotIn('depth', template['editable_fields'])
            client.close()


if __name__ == '__main__':
    unittest.main()
