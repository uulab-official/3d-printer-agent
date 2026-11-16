import tempfile
import unittest
from pathlib import Path

import cadquery as cq

from print_agent.geometry import generate_model
from print_agent.model_edits import normalize_parameters, plan_model_edit
from print_agent.planner import plan_from_text
from print_agent.schemas import GeometryRequest

LEGACY_KEYS = {'template', 'width', 'depth', 'height', 'wall', 'bottom', 'dividers', 'slots',
               'cable_diameter', 'inset_diameter', 'inset_depth', 'fit_clearance'}
STAND = dict(template='phone_stand', width=70, depth=80, height=90, wall=4, bottom=4,
             lean_angle=65, device_thickness=12, lip_height=12, fit_clearance=1)


def build(**overrides):
    with tempfile.TemporaryDirectory() as folder:
        result = generate_model(GeometryRequest(**{**STAND, **overrides}), Path(folder))
        shape = cq.importers.importStep(str(Path(folder) / 'model.step')).val()
        return result, shape


class PhoneStandTests(unittest.TestCase):
    def test_existing_templates_keep_their_exact_parameter_shape(self):
        for template in ('tray', 'cable_comb', 'magnet_frame'):
            with self.subTest(template=template):
                self.assertEqual(set(GeometryRequest(template=template).model_dump()), LEGACY_KEYS)
                self.assertEqual(set(normalize_parameters(GeometryRequest(template=template).model_dump())), LEGACY_KEYS)
        stand = GeometryRequest(**STAND).model_dump()
        self.assertEqual(set(stand) - LEGACY_KEYS, {'lean_angle', 'device_thickness', 'lip_height'})
        with self.assertRaises(ValueError):
            GeometryRequest(template='tray', lean_angle=70)

    def test_stand_is_one_valid_solid_with_open_slot_and_passing_review(self):
        result, shape = build()
        self.assertEqual(result['dimensions_mm'], {'x': 70.0, 'y': 80.0, 'z': 90.0})
        self.assertTrue(shape.isValid())
        self.assertEqual(len(shape.Solids()), 1)
        self.assertEqual(result['printability']['status'], 'ok')
        # The slot between lip and back is empty above the base.
        slot_center = cq.Vector(35, 4 + 6.5, 4 + 6)
        self.assertFalse(shape.isInside(slot_center))
        # The lip and the back plate are solid.
        self.assertTrue(shape.isInside(cq.Vector(35, 2, 10)))
        self.assertTrue(shape.isInside(cq.Vector(35, 17 + 2, 8)))
        self.assertIn('기기 두께', ' '.join(result['warnings']))

    def test_steeper_angle_moves_the_back_toward_the_front(self):
        import math
        _, upright = build(lean_angle=80, depth=100)
        _, leaning = build(lean_angle=55, depth=100)
        # Middle of the back plate at z=85: slot front 17 mm plus the horizontal run.
        def back_point(angle):
            return cq.Vector(35, 17 + (85 - 4) * math.tan(math.radians(90 - angle)) + 2, 85)
        self.assertTrue(upright.isInside(back_point(80)))
        self.assertTrue(leaning.isInside(back_point(55)))
        self.assertFalse(upright.isInside(back_point(55)))
        self.assertFalse(leaning.isInside(back_point(80)))

    def test_rules_reject_a_back_outside_the_base_and_a_lip_above_the_top(self):
        with self.assertRaisesRegex(ValueError, '세로\\(깊이\\)를 \\d+ mm 이상'):
            build(height=200)
        with self.assertRaisesRegex(ValueError, '앞턱'):
            build(lip_height=60, height=60)

    def test_planner_detects_stand_parses_angle_and_grows_default_depth(self):
        ready = plan_from_text('폭 80mm 휴대폰 거치대, 각도 70도, 폰 두께 10mm, 앞턱 높이 15mm')
        self.assertEqual(ready['status'], 'ready')
        p = ready['parameters']
        self.assertEqual((p['template'], p['width'], p['lean_angle'], p['device_thickness'], p['lip_height']),
                         ('phone_stand', 80.0, 70.0, 10.0, 15.0))
        grown = plan_from_text('거치대 높이 160mm')
        self.assertEqual(grown['parameters']['depth'], 97.0)
        self.assertIn('97 mm로 늘렸습니다', grown['assumptions'][0])
        kept = plan_from_text('거치대 높이 160mm 세로 80mm')
        self.assertEqual(kept['status'], 'needs_input')
        self.assertIn('95 mm 이상', kept['message'])
        self.assertIn('50~80도', plan_from_text('스탠드 각도 40도')['message'])
        self.assertEqual(plan_from_text('거치대 각도 60도, 기울기 70도')['status'], 'needs_input')

    def test_contextual_edits_use_degrees_for_angle_and_lengths_elsewhere(self):
        base = GeometryRequest(**STAND).model_dump()
        changes = plan_model_edit('각도를 70도로 바꿔줘', base)['review']['changes']
        self.assertEqual(changes, [{'field': 'lean_angle', 'before': 65.0, 'after': 70.0}])
        thicker = plan_model_edit('폰 두께 2mm 늘려줘', base)['review']['changes']
        self.assertEqual(thicker, [{'field': 'device_thickness', 'before': 12.0, 'after': 14.0}])
        for text in ('각도 70mm', '높이 5도'):
            with self.subTest(text=text):
                self.assertEqual(plan_model_edit(text, base)['status'], 'needs_input')


if __name__ == '__main__':
    unittest.main()
