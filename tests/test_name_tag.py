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
                self.assertIn('글꼴', ' '.join(result['warnings']))
        longer, _ = build(text='MINSU KIM')
        self.assertGreater(longer['dimensions_mm']['x'], build()[0]['dimensions_mm']['x'])

    def test_printability_names_estimated_stroke(self):
        # Checked on the rule itself so the result does not depend on the platform font.
        from print_agent.printability import _wall_item
        item = _wall_item(GeometryRequest(**{**TAG, 'text_size': 6}).model_dump())
        self.assertIn('글자 획', item['value'])
        self.assertEqual((item['status'], item['field']), ('warn', 'text_size'))
        self.assertEqual(_wall_item(GeometryRequest(**TAG).model_dump())['status'], 'pass')

    @unittest.skipUnless(Path('/System/Library/Fonts/Supplemental/Bradley Hand Bold.ttf').is_file(), 'needs a known self-overlapping font')
    def test_invalid_font_outlines_fail_with_a_clear_reason(self):
        from unittest.mock import patch
        from print_agent import geometry
        bad = {'fontPath': '/System/Library/Fonts/Supplemental/Bradley Hand Bold.ttf', 'label': 'Bradley Hand Bold.ttf'}
        with patch.object(geometry, '_name_tag_font', return_value=bad), self.assertRaisesRegex(ValueError, '글자 형상이 올바르지 않습니다'):
            build()

    def test_font_is_pinned_and_reported(self):
        from print_agent.geometry import _name_tag_font
        font = _name_tag_font()
        self.assertTrue(font['label'])
        result, _ = build()
        self.assertIn(font['label'], ' '.join(result['warnings']))

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

    def test_default_note_uses_the_panel_labels_of_each_template(self):
        tag = ' '.join(plan_from_text('"지우" 이름 키링 만들어줘')['assumptions'])
        self.assertIn('테두리 여백 3 mm', tag)
        self.assertIn('받침 두께 2 mm', tag)
        self.assertNotIn('벽 두께', tag)
        self.assertNotIn('바닥 두께', tag)
        stand = ' '.join(plan_from_text('휴대폰 거치대 만들어줘')['assumptions'])
        self.assertIn('등판·앞턱 두께', stand)
        self.assertIn('홈 여유', stand)
        tray = ' '.join(plan_from_text('가로 12cm 세로 8cm 수납함')['assumptions'])
        self.assertIn('벽 두께', tray)

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
