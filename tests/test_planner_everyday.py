import unittest

from print_agent.planner import plan_from_text


def plan(text):
    result = plan_from_text(text)
    return result, result.get('parameters') or {}


class EverydayRequestTests(unittest.TestCase):
    def test_two_number_dimensions_are_used_and_inner_size_is_flagged(self):
        result, p = plan('서랍 정리함 3칸, 서랍 안쪽이 30x20cm 높이 6cm')
        self.assertEqual((p['width'], p['depth'], p['height'], p['dividers']), (300.0, 200.0, 60.0, 2))
        self.assertTrue(any('안쪽 치수' in note for note in result['assumptions']))
        _, p = plan('리모컨 수납함 20x10cm 높이 5cm')
        self.assertEqual((p['width'], p['depth'], p['height']), (200.0, 100.0, 50.0))
        _, mixed = plan('수납함 20cm x 100mm')
        self.assertEqual((mixed['width'], mixed['depth']), (200.0, 100.0))
        self.assertEqual(plan('수납함 가로 120mm 150x90mm')[0]['status'], 'needs_input')
        self.assertEqual(plan('수납함 가로 150mm 150x90mm')[1]['depth'], 90.0)

    def test_everyday_names_start_from_announced_sizes(self):
        for text, template, size in (('명함 꽂이', 'tray', (100.0, 65.0, 35.0)),
                                     ('이어폰 정리', 'tray', (90.0, 70.0, 30.0)),
                                     ('태블릿 받침대 만들어줘', 'phone_stand', (160.0, 80.0, 120.0))):
            with self.subTest(text=text):
                result, p = plan(text)
                self.assertEqual(result['status'], 'ready')
                self.assertEqual((p['template'], p['width'], p['depth'], p['height']), (template, *size))
                self.assertIn('시작합니다', result['assumptions'][0])
        result, pen = plan('책상 위에 둘 펜꽂이 만들어줘')
        self.assertEqual((pen['template'], pen['width'], pen['height'], pen['drain_hole']), ('cup', 70.0, 100.0, 0.0))
        self.assertIn('지름 70 mm', result['assumptions'][0])
        _, pen = plan('펜꽂이 높이 120mm')
        self.assertEqual(pen['height'], 120.0)

    def test_round_photo_frame_grows_to_fit_the_photo(self):
        result, p = plan('사진 넣는 액자 10cm 원형')
        self.assertEqual((p['template'], p['inset_diameter'], p['width'], p['depth']), ('magnet_frame', 100.0, 113.0, 113.0))
        self.assertTrue(any('113 × 113 mm로 키웠습니다' in note for note in result['assumptions']))
        _, kept = plan('액자 지름 50mm 가로 80mm 세로 80mm')
        self.assertEqual((kept['inset_diameter'], kept['width']), (50.0, 80.0))

    def test_cable_count_and_bare_stand_thickness(self):
        self.assertEqual(plan('USB 케이블 3개 받침')[1]['slots'], 3)
        self.assertEqual(plan('케이블 받침 홈 4개')[1]['slots'], 4)
        _, stand = plan('휴대폰 거치대 두께 9mm 케이스 포함')
        self.assertEqual((stand['device_thickness'], stand['wall']), (9.0, 4.0))
        _, walled = plan('휴대폰 거치대 벽 두께 3mm')
        self.assertEqual((walled['device_thickness'], walled['wall']), (12.0, 3.0))

    def test_load_bearing_stands_are_declined_honestly(self):
        for text in ('모니터 받침대', '모니터 스탠드', '노트북 받침'):
            with self.subTest(text=text):
                result, _ = plan(text)
                self.assertEqual(result['status'], 'needs_input')
                self.assertIn('무게를 받치는 구조', result['message'])

    def test_default_notes_use_korean_field_names(self):
        result, _ = plan('휴대폰 거치대')
        self.assertEqual(len(result['assumptions']), 1)
        self.assertIn('등판 각도 65°', result['assumptions'][0])
        self.assertNotIn('width', result['assumptions'][0])


if __name__ == '__main__':
    unittest.main()
