"""Regressions for the independent production-readiness review of v0.9-0.10."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from print_agent import geometry
from print_agent.planner import plan_from_text
from print_agent.printability import _normal, _wall_item
from print_agent.schemas import GeometryRequest
from print_agent.storage import _history_summary


def plan(text):
    result = plan_from_text(text)
    return result, result.get('parameters') or {}


class PlannerReviewTests(unittest.TestCase):
    def test_load_bearing_and_unknown_stands_are_not_phone_stands(self):
        for text in ('노트북 거치대', '모니터 거치대 만들어줘', '맥북 스탠드'):
            with self.subTest(text=text):
                result, _ = plan(text)
                self.assertEqual(result['status'], 'needs_input')
                self.assertIn('무게를 받치는', result['message'])
        for text in ('헤드폰 거치대', '카메라 스탠드', '이어폰 거치대'):
            with self.subTest(text=text):
                result, _ = plan(text)
                self.assertEqual(result['status'], 'needs_input')
                self.assertIn('휴대폰·태블릿 거치대만', result['message'])
        for text in ('폰 거치대', '아이폰 거치대', 'smartphone stand', '갤럭시 탭 거치대'):
            with self.subTest(text=text):
                self.assertEqual(plan(text)[1]['template'], 'phone_stand')

    def test_counts_after_x_are_not_sizes_and_template_words_beat_item_names(self):
        result, tray = plan('수납함 2x3칸')
        self.assertEqual((result['status'], tray['width'], tray['dividers']), ('ready', 120.0, 2))
        self.assertEqual(plan('케이블 받침 6mm x 5개')[1]['template'], 'cable_comb')
        _, cable = plan('이어폰 케이블 정리 받침 5칸')
        self.assertEqual((cable['template'], cable['slots']), ('cable_comb', 5))
        self.assertEqual(plan('명함 크기 휴대폰 거치대')[1]['template'], 'phone_stand')
        self.assertEqual(plan('명함 수납함')[1]['width'], 100.0)

    def test_back_plate_thickness_is_the_wall_not_the_device(self):
        _, stand = plan('휴대폰 거치대 등판 두께 5mm')
        self.assertEqual((stand['wall'], stand['device_thickness']), (5.0, 12.0))


class PrintabilityReviewTests(unittest.TestCase):
    def test_constraint_only_wall_is_not_reported_for_comb_and_frame(self):
        comb = _wall_item({'template': 'cable_comb', 'width': 80, 'depth': 18, 'height': 12, 'wall': 0.8, 'bottom': 2,
                           'slots': 5, 'cable_diameter': 6, 'fit_clearance': 0.3}, line=0.84)
        self.assertEqual(comb['status'], 'pass')
        self.assertNotIn('바깥 벽', comb['value'])
        frame = _wall_item({'template': 'magnet_frame', 'width': 65, 'depth': 65, 'height': 7, 'wall': 0.8, 'bottom': 2,
                            'inset_diameter': 52, 'inset_depth': 2, 'fit_clearance': 0.3})
        self.assertEqual(frame['status'], 'pass')
        self.assertIn('포켓', frame['value'])

    def test_degenerate_triangle_has_no_area(self):
        self.assertEqual(_normal([0, 0, 0], [1, 1, 1], [2, 2, 2]), ([0.0, 0.0, 0.0], 0.0))

    def test_review_failure_never_blocks_a_valid_model(self):
        with tempfile.TemporaryDirectory() as folder, \
                patch.object(geometry, 'assess_printability', side_effect=RuntimeError('boom')):
            result = geometry.generate_model(GeometryRequest(template='tray'), Path(folder))
        self.assertEqual(result['geometry_status'], 'validated')
        self.assertIsNone(result['printability'])


class HistorySliceSummaryTests(unittest.TestCase):
    def summary(self, latest):
        job = {'result': {'parameters': GeometryRequest(template='tray').model_dump()}, 'latest_slice': latest}
        return _history_summary(job).get('slice')

    def test_slice_states_match_the_record(self):
        self.assertEqual(self.summary({'phase': 'finished', 'plan': {'ready': False}, 'execution': None}), 'blocked')
        self.assertEqual(self.summary({'phase': 'finished', 'plan': {'ready': False}, 'execution': {'status': 'failed'}}), 'failed')
        self.assertEqual(self.summary({'phase': 'finished', 'plan': {'ready': True}, 'execution': None}), 'planned')
        self.assertEqual(self.summary({'phase': 'finished', 'plan': {'ready': True, 'project_prepared': True}, 'execution': None}), 'prepared')
        self.assertEqual(self.summary({'phase': 'finished', 'plan': {'ready': True}, 'execution': {'status': 'sliced'}}), 'sliced')
        self.assertEqual(self.summary({'phase': 'running', 'plan': None, 'execution': None}), 'running')
        self.assertIsNone(self.summary(None))


if __name__ == '__main__':
    unittest.main()
