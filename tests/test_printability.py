import tempfile
import unittest
from pathlib import Path

import cadquery as cq

from print_agent.geometry import _preview_mesh, generate_model
from print_agent.printability import assess_printability
from print_agent.schemas import GeometryRequest


def review(**values):
    with tempfile.TemporaryDirectory() as folder:
        return generate_model(GeometryRequest(**values), Path(folder))['printability']


def by_id(result):
    return {item['id']: item for item in result['items']}


class PrintabilityTests(unittest.TestCase):
    def test_nozzle_choice_changes_only_the_thickness_basis(self):
        from print_agent.printability import review_mesh
        with tempfile.TemporaryDirectory() as folder:
            result = generate_model(GeometryRequest(template='tray', width=120, depth=80, height=35, wall=1.2,
                                                    bottom=2, dividers=0), Path(folder))
        base = result['printability']
        self.assertEqual(base, review_mesh(result['parameters'], result['mesh'], result['volume_mm3']))
        small = by_id(review_mesh(result['parameters'], result['mesh'], result['volume_mm3'], 0.2))
        large = review_mesh(result['parameters'], result['mesh'], result['volume_mm3'], 0.8)
        self.assertEqual(small['min_thickness']['status'], 'pass')
        self.assertEqual(by_id(large)['min_thickness']['status'], 'warn')
        self.assertEqual((large['basis']['nozzle_mm'], large['basis']['line_width_mm']), (0.8, 0.84))
        self.assertEqual(by_id(large)['bed_contact'], by_id(base)['bed_contact'])
        with self.assertRaises(ValueError):
            review_mesh(result['parameters'], result['mesh'], result['volume_mm3'], 0.5)

    def test_default_tray_is_ok_with_full_bed_contact_and_no_overhang(self):
        result = review(template='tray', width=120, depth=80, height=35, wall=2, bottom=2, dividers=2)
        items = by_id(result)
        self.assertEqual(result['status'], 'ok')
        self.assertEqual(items['bed_contact']['value'], '96.0 cm² (100%)')
        self.assertEqual(items['overhang']['status'], 'pass')
        self.assertEqual(items['min_thickness']['status'], 'pass')
        self.assertEqual(result['basis']['nozzle_mm'], 0.4)
        self.assertIn('상한', items['material']['detail'])
        self.assertNotIn('fit_clearance', items)

    def test_one_line_wall_warns_with_target_field(self):
        result = review(template='tray', width=60, depth=40, height=20, wall=0.8, bottom=2, dividers=0)
        item = by_id(result)['min_thickness']
        self.assertEqual((item['status'], item['field']), ('warn', 'wall'))
        self.assertEqual(result['status'], 'review')

    def test_frame_pocket_floor_is_measured_from_parameters(self):
        result = review(template='magnet_frame', width=65, depth=65, height=4, wall=2, bottom=0.8,
                        inset_diameter=52, inset_depth=3, fit_clearance=0.1)
        items = by_id(result)
        self.assertEqual(items['min_thickness']['status'], 'warn')
        self.assertEqual(items['min_thickness']['value'], '0.80 mm (바닥)')
        self.assertEqual(items['fit_clearance']['status'], 'warn')
        self.assertEqual(items['fit_clearance']['field'], 'fit_clearance')
        self.assertEqual(result['status'], 'review')

    def test_thickness_below_one_line_fails(self):
        from print_agent.printability import _wall_item
        item = _wall_item({'template': 'tray', 'width': 50, 'depth': 50, 'height': 10, 'wall': 0.3, 'bottom': 2, 'dividers': 0})
        self.assertEqual((item['status'], item['field']), ('fail', 'wall'))

    def test_cable_comb_slot_gap_and_slender_part(self):
        result = review(template='cable_comb', width=80, depth=10, height=40, wall=2, bottom=2,
                        slots=5, cable_diameter=6, fit_clearance=0.3)
        items = by_id(result)
        self.assertEqual(items['stability']['status'], 'warn')
        self.assertEqual(items['stability']['field'], 'height')

    def test_overhang_and_small_contact_are_detected_on_a_t_shape(self):
        stem = cq.Workplane('XY').box(10, 10, 20, centered=False)
        top = cq.Workplane('XY').box(40, 10, 4, centered=False).translate((-15, 0, 20))
        shape = stem.union(top).clean().val()
        params = {'template': 'tray', 'width': 40, 'depth': 10, 'height': 24, 'wall': 2, 'bottom': 2, 'dividers': 0}
        items = by_id(assess_printability(shape, params, _preview_mesh(shape)))
        self.assertEqual(items['overhang']['status'], 'warn')
        self.assertEqual(items['overhang']['value'], '3.00 cm²')
        self.assertEqual(items['bed_contact']['status'], 'warn')


if __name__ == '__main__':
    unittest.main()
