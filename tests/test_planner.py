import unittest
from print_agent.planner import plan_from_text, validate_llm_plan


class PlannerTests(unittest.TestCase):
    def test_unsupported_shapes_are_not_silently_simplified(self):
        for text in ('원형 수납함 가로 100mm 높이 30mm 만들어줘','손잡이 달린 수납함 만들어줘'):
            self.assertEqual(plan_from_text(text)['status'],'needs_input')

    def test_leading_decimal_and_channel_count(self):
        parameters=plan_from_text('케이블 받침 3칸으로 만들어줘 벽 .8mm')['parameters']
        self.assertEqual(parameters['slots'],3)
        self.assertEqual(parameters['wall'],0.8)

    def test_conflicting_compartment_counts_need_clarification(self):
        self.assertEqual(plan_from_text('수납함 3칸 4칸으로 만들어줘')['status'],'needs_input')

    def test_irrelevant_template_parameters_are_rejected(self):
        with self.assertRaises(ValueError):
            validate_llm_plan({'parameters':{'template':'tray','slots':10}})

    def test_llm_cannot_supply_execution_status_prose(self):
        result=validate_llm_plan({'parameters':{'template':'tray'},'explanation':'프린터 연결 및 출력이 완료되었습니다.'})
        self.assertNotIn('출력이 완료',str(result))
        self.assertEqual(result['status'],'ready')
    def test_material_or_shopping_intent_takes_priority_over_object_noun(self):
        material=plan_from_text('이 마그넷 프레임에 쓸 필라멘트 온도는 어떻게 설정해?')
        shopping=plan_from_text('수납함 살 건데 가장 저렴한 가격 비교해줘')
        self.assertEqual(material['action'],'open_profiles')
        self.assertEqual(shopping['action'],'open_offers')
        self.assertNotIn('parameters',material)
        self.assertNotIn('parameters',shopping)
    def test_per_dimension_units_are_all_converted(self):
        result = plan_from_text('14cm x 9cm x 4cm 수납함')
        self.assertEqual(result['status'], 'ready')
        self.assertEqual([result['parameters'][k] for k in ('width','depth','height')], [140,90,40])

    def test_inset_depth_does_not_change_overall_depth(self):
        result = plan_from_text('원형 인셋 프레임 인셋 깊이 3mm')
        self.assertEqual(result['status'], 'ready')
        self.assertEqual(result['parameters']['depth'],65)
        self.assertEqual(result['parameters']['inset_depth'],3)
    def test_korean_dimensions_convert_cm_and_compartments(self):
        result = plan_from_text('가로 12cm 세로 8cm 높이 3.5cm 수납함을 3칸으로 만들어줘')
        self.assertEqual(result['status'], 'ready')
        self.assertEqual(result['parameters']['width'], 120)
        self.assertEqual(result['parameters']['depth'], 80)
        self.assertEqual(result['parameters']['height'], 35)
        self.assertEqual(result['parameters']['dividers'], 2)
        self.assertEqual(result['engine'], 'template_rules')

    def test_requested_unsupported_lid_is_not_silently_ignored(self):
        result = plan_from_text('경첩 달린 방수 뚜껑 수납함 만들어줘')
        self.assertEqual(result['status'], 'needs_input')
        self.assertTrue(result['questions'])

    def test_reference_model_defaults_are_explicit(self):
        result = plan_from_text('52mm 포토마그넷 프레임 만들어줘')
        self.assertEqual(result['parameters']['template'], 'magnet_frame')
        self.assertEqual(result['parameters']['inset_diameter'], 52)
        self.assertTrue(result['assumptions'])

    def test_negative_size_is_rejected(self):
        result = plan_from_text('가로 -5mm 세로 60mm 높이 30mm 수납함')
        self.assertEqual(result['status'], 'needs_input')

    def test_three_numbers_with_units(self):
        result = plan_from_text('수납함 120x80x35 mm')
        self.assertEqual([result['parameters'][k] for k in ('width','depth','height')], [120,80,35])

    def test_unknown_request_does_not_generate_arbitrary_model(self):
        result = plan_from_text('용 모양 피규어를 만들어줘')
        self.assertEqual(result['status'], 'needs_input')

    def test_llm_code_and_extra_fields_are_not_executable(self):
        with self.assertRaises(ValueError):
            validate_llm_plan({'parameters': {'template':'tray','python':'import os'}, 'explanation':'run'})

    def test_nonfinite_llm_dimension_is_rejected(self):
        with self.assertRaises(ValueError):
            validate_llm_plan({'parameters': {'template':'tray','width':float('inf')}, 'explanation':'test'})

    def test_filament_question_routes_to_profile_review(self):
        result=plan_from_text('이 필라멘트 온도를 어떻게 설정해?')
        self.assertEqual(result['action'], 'open_profiles')
        self.assertNotIn('nozzle_temperature', result)


if __name__ == '__main__':
    unittest.main()
