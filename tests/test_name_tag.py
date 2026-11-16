import tempfile
import unittest
from pathlib import Path

import cadquery as cq

from print_agent.geometry import generate_model
from print_agent.model_edits import normalize_parameters, review_model_edit
from print_agent.planner import plan_from_text
from print_agent.schemas import GeometryRequest

TAG = dict(template='name_tag', text='MINSU', text_size=12, text_depth=2, wall=3, bottom=2, hole_diameter=4)


def build(**overrides):
    with tempfile.TemporaryDirectory() as folder:
        result = generate_model(GeometryRequest(**{**TAG, **overrides}), Path(folder))
        shape = cq.importers.importStep(str(Path(folder) / 'model.step')).val()
        return result, shape


class NameTagTests(unittest.TestCase):
    def test_existing_templates_do_not_gain_text_fields(self):
        for template in ('tray', 'cable_comb', 'magnet_frame', 'phone_stand'):
            self.assertNotIn('text', GeometryRequest(template=template).model_dump())
        tag = GeometryRequest(**TAG).model_dump()
        self.assertEqual(tag['text'], 'MINSU')
        with self.assertRaises(ValueError):
            GeometryRequest(template='tray', text='A')

    def test_text_is_validated(self):
        for bad in ('', '   ', 'x' * 21, 'a\nb', '<b>', 'emoji 😀'):
            with self.subTest(text=bad), self.assertRaises(ValueError):
                GeometryRequest(**{**TAG, 'text': bad})
        for good in ('민수', 'Samantha', 'I ♥ NY', "Tom's", 'A-1'):
            GeometryRequest(**{**TAG, 'text': good})
        with self.assertRaisesRegex(ValueError, '고리 구멍'):
            build(text_size=6, hole_diameter=8)

    def test_one_solid_with_ring_hole_and_letters_on_the_plate(self):
        for text in ('MINSU', '민수', 'Hi! 2026'):
            with self.subTest(text=text):
                result, shape = build(text=text)
                self.assertEqual(result['geometry_status'], 'validated')
                self.assertTrue(shape.isValid())
                self.assertEqual(len(shape.Solids()), 1)
                self.assertAlmostEqual(result['dimensions_mm']['z'], 4.0, places=5)
                hole_center = cq.Vector(3 + 2, result['dimensions_mm']['y'] / 2, 1)
                self.assertFalse(shape.isInside(hole_center))
                dims = result['dimensions_mm']
                self.assertTrue(shape.isInside(cq.Vector(dims['x'] / 2, dims['y'] / 2, 1)))  # plate under the letters
                self.assertIn('시스템 글꼴', ' '.join(result['warnings']))
        longer, _ = build(text='MINSU KIM')
        self.assertGreater(longer['dimensions_mm']['x'], build()[0]['dimensions_mm']['x'])

    def test_printability_names_estimated_stroke(self):
        result, _ = build(text_size=6)
        items = {item['id']: item for item in result['printability']['items']}
        self.assertIn('글자 획', items['min_thickness']['value'])
        self.assertEqual(items['min_thickness']['status'], 'warn')

    def test_planner_reads_text_and_sizes(self):
        cases = {
            '"Samantha" 키링': 'Samantha', '이름이 민수인 키링': '민수', '민수 이름표 글자 크기 15mm': '민수',
            '키링 글자는 지우 구멍 지름 5mm': '지우', '서연이라고 적힌 키링': '서연', '지민 키링': '지민',
        }
        for text, expected in cases.items():
            with self.subTest(text=text):
                result = plan_from_text(text)
                self.assertEqual(result['status'], 'ready')
                self.assertEqual(result['parameters']['text'], expected)
        self.assertEqual(plan_from_text('민수 이름표 글자 크기 15mm')['parameters']['text_size'], 15.0)
        default = plan_from_text('이름 키링 만들어줘')
        self.assertEqual(default['parameters']['text'], 'MINSU')
        self.assertIn('따옴표', default['assumptions'][0])
        self.assertEqual(plan_from_text('“Mia”랑 “Lily” 키링')['status'], 'needs_input')
        self.assertEqual(plan_from_text('키링 글자 크기 50mm')['status'], 'needs_input')

    def test_contextual_edit_sets_new_text_without_touching_numbers(self):
        base = normalize_parameters(GeometryRequest(**TAG).model_dump())
        self.assertEqual(base['text'], 'MINSU')
        review = review_model_edit({'schema_version': 1, 'request_text': '글자 바꿔줘', 'base_parameters': base,
                                    'operations': [{'field': 'text', 'op': 'set', 'value': '지우'}], 'parent': None})
        self.assertEqual(review['changes'], [{'field': 'text', 'before': 'MINSU', 'after': '지우'}])
        self.assertEqual(review['parameters']['text_size'], 12.0)
        with self.assertRaises(ValueError):
            review_model_edit({'schema_version': 1, 'request_text': 'x', 'base_parameters': base,
                               'operations': [{'field': 'text', 'op': 'add', 'value': '1'}], 'parent': None})


if __name__ == '__main__':
    unittest.main()
