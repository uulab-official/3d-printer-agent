"""Keycap: Cherry MX-compatible cross stem, key sizes, engraved legend, requests and edits."""
import tempfile
import unittest
from pathlib import Path

import cadquery as cq
from fastapi.testclient import TestClient
from pydantic import ValidationError

from print_agent.app import create_app
from print_agent.geometry import _build_solid, generate_model, template_catalog
from print_agent.geometry_rules import _validate_geometry, keycap_layout
from print_agent.model_edits import normalize_parameters, plan_model_edit
from print_agent.planner import plan_from_text
from print_agent.recovery import recovery_plan
from print_agent.schemas import GeometryRequest

KEY = dict(template='keycap', key_units=1, height=8, wall=1.3, bottom=2, text='A', text_size=5, text_depth=0.8, fit_clearance=0.15)


def inside(shape, x, y, z):
    return shape.isInside(cq.Vector(x, y, z))


class KeycapGeometryTests(unittest.TestCase):
    def test_the_shell_is_sculpted_with_fuller_sides_and_a_rounded_shoulder(self):
        parameters = GeometryRequest(**{**KEY, 'text': ''}).model_dump()
        shape, k = _build_solid(parameters), keycap_layout(parameters)
        straight = (k['width'] + k['top_width']) / 4  # half-width of a straight taper at half height
        self.assertTrue(inside(shape, straight + 0.1, 0, 4.0))        # the side swells past the straight taper
        self.assertFalse(inside(shape, straight + 0.45, 0, 4.0))
        corner = (k['top_width'] / 2 - 0.15, k['top_depth'] / 2 - 0.15)
        self.assertFalse(inside(shape, *corner, 7.95))                # the top corner is rounded away
        self.assertTrue(inside(shape, 0, k['top_depth'] / 2 - 0.6, 7.4))  # the long top edge keeps material
        self.assertTrue(shape.isValid())
        self.assertEqual(len(shape.Solids()), 1)

    def test_sizes_follow_the_key_units(self):
        for units, width in ((1, 18.0), (1.5, 27.525), (2.25, 41.8125), (6.25, 118.0125)):
            with self.subTest(units=units), tempfile.TemporaryDirectory() as folder:
                result = generate_model(GeometryRequest(**{**KEY, 'key_units': units, 'text': ''}), Path(folder))
                size = result['dimensions_mm']
                self.assertAlmostEqual(size['x'], width, places=5)
                self.assertAlmostEqual(size['y'], 18.0, places=5)
                self.assertAlmostEqual(size['z'], 8.0, places=5)
                self.assertTrue(all(check['passed'] for check in result['checks']), result['checks'])

    def test_cross_stem_and_stabilizer_stems(self):
        one = _build_solid(GeometryRequest(**KEY).model_dump())
        self.assertFalse(inside(one, 0, 0, 1))        # the cross hole
        self.assertFalse(inside(one, 0, 2.0, 1))      # end of the vertical arm (4.15 mm long)
        self.assertTrue(inside(one, 0, 2.5, 1))       # stem ring beyond the arm
        self.assertTrue(inside(one, 1.0, 1.0, 1))     # between the arms
        self.assertFalse(inside(one, 6, 0, 1))        # open cavity beside the stem
        self.assertTrue(inside(one, 0, 0, 7.0))       # the top above the stem
        self.assertFalse(inside(one, 11.938, 0, 4.5))  # a 1u key has no stabilizer stem
        wide = _build_solid(GeometryRequest(**{**KEY, 'key_units': 2, 'text': 'Bk'}).model_dump())
        for x in (-11.938, 11.938):
            self.assertFalse(inside(wide, x, 0, 1))
            self.assertTrue(inside(wide, x, 2.5, 1))
        self.assertEqual(len(wide.Solids()), 1)

    def test_legend_is_engraved_and_clearance_widens_the_cross(self):
        blank = _build_solid(GeometryRequest(**{**KEY, 'text': ''}).model_dump())
        lettered = _build_solid(GeometryRequest(**KEY).model_dump())
        self.assertLess(lettered.Volume(), blank.Volume() - 1)
        loose = _build_solid(GeometryRequest(**{**KEY, 'fit_clearance': 0.4}).model_dump())
        self.assertFalse(inside(loose, 0, 2.15, 1))
        self.assertTrue(inside(lettered, 0, 2.15, 1))
        self.assertEqual(keycap_layout(GeometryRequest(**KEY).model_dump())['cross'], (4.15, 1.32))

    def test_printability_names_the_bridge_and_the_stem_fit(self):
        with tempfile.TemporaryDirectory() as folder:
            result = generate_model(GeometryRequest(**KEY), Path(folder))
            source = (Path(folder) / 'model.py').read_text(encoding='utf-8')
        items = {item['id']: item for item in result['printability']['items']}
        self.assertEqual(items['min_thickness']['status'], 'pass')
        self.assertEqual(items['overhang']['status'], 'warn')
        self.assertIn('브릿지', items['overhang']['detail'])
        self.assertEqual(items['fit_clearance']['status'], 'pass')
        self.assertIn('4.15 × 1.32', items['fit_clearance']['detail'])
        self.assertTrue(any('체리 MX' in warning for warning in result['warnings']))
        self.assertIn('def keycap_layout', source)

    def test_rules_refuse_impossible_keycaps(self):
        for change, message in (({'height': 5}, '높이'), ({'bottom': 1.2}, '글자 아래'), ({'fit_clearance': 0.6}, '십자'),
                                ({'text_size': 12}, '글자 크기'), ({'height': 6, 'bottom': 2}, '안쪽 높이')):
            with self.subTest(change=change), self.assertRaisesRegex(ValueError, message):
                _validate_geometry(GeometryRequest(**{**KEY, **change}).model_dump())
        for change, message in (({'key_units': 3}, '키 크기'), ({'text': 'Backspace'}, '6자'),
                                ({'accent_color': 'white'}, '새기므로')):
            with self.subTest(change=change), self.assertRaisesRegex(ValidationError, message):
                GeometryRequest(**{**KEY, **change})
        with self.assertRaisesRegex(ValueError, '글자가 윗면'):
            _build_solid(GeometryRequest(**{**KEY, 'text': 'WWWWWW'}).model_dump())

    def test_name_tag_keeps_its_minimum_letter_size(self):
        with self.assertRaisesRegex(ValidationError, '6 mm'):
            GeometryRequest(template='name_tag', text='MINSU', text_size=5)

    def test_catalog_and_canonical_shape(self):
        catalog = {item['id']: item for item in template_catalog()}
        self.assertEqual(catalog['keycap']['defaults']['key_units'], 1)
        self.assertNotIn('width', catalog['keycap']['editable_fields'])
        self.assertNotIn('accent_color', catalog['keycap']['editable_fields'])
        canonical = GeometryRequest(**KEY).model_dump()
        self.assertEqual(canonical['key_units'], 1.0)
        self.assertEqual(canonical['text'], 'A')
        self.assertNotIn('hole_diameter', canonical)
        self.assertNotIn('key_units', GeometryRequest(template='tray').model_dump())
        self.assertNotIn('key_units', GeometryRequest(template='name_tag', text='MINSU').model_dump())


class KeycapLanguageTests(unittest.TestCase):
    def test_requests_choose_size_and_legend(self):
        cases = {'키보드 키캡 만들어줘 1u 크기로': {'key_units': 1.0, 'text': ''},
                 '체리 MX 호환 키캡, 윗면에 A 글자': {'key_units': 1.0, 'text': 'A', 'text_size': 5.0},
                 'ESC 키캡 빨간색으로': {'text': 'ESC', 'color': 'red', 'text_size': 3.5},
                 '스페이스바 키캡': {'key_units': 6.25, 'text': ''},
                 '엔터 키캡 1.5u': {'key_units': 1.5, 'text': 'Enter'},
                 '"한" 키캡 높이 9mm 십자 여유 0.2mm': {'text': '한', 'height': 9.0, 'fit_clearance': 0.2},
                 'keycap legend Q': {'text': 'Q'}}
        for text, expected in cases.items():
            with self.subTest(text=text):
                result = plan_from_text(text)
                self.assertEqual(result['status'], 'ready', result)
                self.assertEqual(result['parameters']['template'], 'keycap')
                for key, value in expected.items():
                    self.assertEqual(result['parameters'][key], value)

    def test_unclear_requests_ask(self):
        for text, message in (('키캡 3u', '키 크기'), ('A 키캡 B 글자', '여러 개'), ('엔터 탭 키캡', '여러 개'),
                              ('검정 키캡에 흰 글자 Z', '새기므로')):
            with self.subTest(text=text):
                result = plan_from_text(text)
                self.assertEqual(result['status'], 'needs_input')
                self.assertIn(message, result['message'])
        self.assertIn('키캡', plan_from_text('뭔가 만들어줘')['message'])
        self.assertEqual(plan_from_text('민수 키링')['parameters']['template'], 'name_tag')

    def test_edits_use_keycap_words(self):
        base = normalize_parameters(GeometryRequest(**KEY).model_dump())
        for text, change in (('키 크기 1.5u로 바꿔줘', ('key_units', 1.0, 1.5)), ('글자를 "B"로 바꿔줘', ('text', 'A', 'B')),
                             ('십자 여유 0.05mm 늘려줘', ('fit_clearance', 0.15, 0.2)), ('윗면 두께 2.5mm', ('bottom', 2.0, 2.5)),
                             ('글자 깊이 1mm', ('text_depth', 0.8, 1.0)), ('옆벽 두께 1.6mm', ('wall', 1.3, 1.6))):
            with self.subTest(text=text):
                review = plan_model_edit(text, base)['review']
                self.assertEqual([(c['field'], c['before'], c['after']) for c in review['changes']], [change])
        for text in ('가로 30mm', '키 크기 3u', '키 크기 1mm'):
            with self.subTest(text=text):
                self.assertEqual(plan_model_edit(text, base)['status'], 'needs_input')

    def test_recovery_adjusts_the_cross_fit(self):
        parameters = GeometryRequest(**KEY).model_dump()
        for reason, after in (('too_tight', 0.2), ('too_loose', 0.1)):
            with self.subTest(reason=reason):
                change = recovery_plan(parameters, [reason])['items'][0]['model_edit']['changes'][0]
                self.assertEqual((change['field'], change['after']), ('fit_clearance', after))


class KeycapAPITests(unittest.TestCase):
    def test_generated_keycaps_are_stored_with_their_titles(self):
        with tempfile.TemporaryDirectory() as temp, TestClient(create_app(Path(temp), test_mode=True)) as client:
            headers = {'X-Session-Token': client.get('/api/bootstrap').json()['session_token']}
            job = client.post('/api/models', json=KEY, headers=headers).json()
            self.assertEqual(job['status'], 'geometry_validated')
            self.assertEqual(job['title'], '키캡 1u “A” · 18.0 × 18.0 × 8.0 mm')
            blank = client.post('/api/models', json={**KEY, 'key_units': 6.25, 'text': ''}, headers=headers).json()
            self.assertEqual(blank['title'], '키캡 6.25u (무지) · 118.0 × 18.0 × 8.0 mm')
            self.assertEqual(client.get('/api/jobs').json()['jobs'][0]['template'], 'keycap')
            refused = client.post('/api/models', json={**KEY, 'key_units': 3}, headers=headers)
            self.assertEqual(refused.status_code, 422)


if __name__ == '__main__':
    unittest.main()
