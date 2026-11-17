"""Filament colours: optional parameters, natural-language requests and edits,
two-part name tags and the Studio part/filament 3MF."""
import json
import re
import tempfile
import unittest
import zipfile
from pathlib import Path
import xml.etree.ElementTree as ET

from fastapi.testclient import TestClient
from pydantic import ValidationError

from print_agent.app import create_app
from print_agent.geometry import color_parts, generate_model, template_catalog
from print_agent.model_edits import normalize_parameters, plan_model_edit
from print_agent.planner import extract_colors, plan_from_text
from print_agent.schemas import PALETTE, GeometryRequest

ROOT = Path(__file__).resolve().parents[1]
CORE = '{http://schemas.microsoft.com/3dmanufacturing/core/2015/02}'


def changes(result):
    return [(item['field'], item['before'], item['after']) for item in result.get('review', {}).get('changes', [])]


class ColorParameterTests(unittest.TestCase):
    def test_unchosen_colours_keep_the_earlier_canonical_shape(self):
        plain = GeometryRequest().model_dump()
        self.assertNotIn('color', plain)
        self.assertNotIn('accent_color', plain)
        tag = GeometryRequest(template='name_tag', text='A').model_dump()
        self.assertNotIn('color', tag)
        colored = GeometryRequest(template='name_tag', text='A', color='white', accent_color='red').model_dump()
        self.assertEqual((colored['color'], colored['accent_color']), ('white', 'red'))

    def test_only_palette_names_and_letter_colour_only_on_name_tags(self):
        for bad in ({'color': 'teal'}, {'color': '#FF0000'}, {'accent_color': 'red'},
                    {'template': 'name_tag', 'text': 'A', 'accent_color': 'navy'}):
            with self.subTest(bad=bad), self.assertRaises(ValidationError):
                GeometryRequest(**bad)

    def test_palette_matches_the_browser_copy(self):
        source = (ROOT / 'print_agent' / 'static' / 'app.js').read_text(encoding='utf-8')
        block = re.search(r'const PALETTE = \{(.*?)\};', source, re.S).group(1)
        browser = {key: (name, hexa) for key, name, hexa in re.findall(r'(\w+): \["([^"]+)", "(#[0-9A-F]{6})"\]', block)}
        self.assertEqual(browser, PALETTE)

    def test_catalog_offers_colour_fields_with_empty_defaults(self):
        for item in template_catalog():
            with self.subTest(template=item['id']):
                self.assertIn('color', item['editable_fields'])
                self.assertEqual(item['defaults']['color'], '')
                self.assertEqual('accent_color' in item['editable_fields'], item['id'] == 'name_tag')


class ColorLanguageTests(unittest.TestCase):
    def test_requests_read_model_and_letter_colours(self):
        cases = {
            '빨간 글자로 "지우" 키링, 판은 흰색': ('name_tag', '지우', 'white', 'red'),
            '글자는 검정, 받침은 분홍 "Mia" 키링': ('name_tag', 'Mia', 'pink', 'black'),
            '노란 키링 이름 민수': ('name_tag', '민수', 'yellow', None),
            '파란색 수납함 가로 12cm 세로 8cm': ('tray', None, 'blue', None),
            '하얀 케이블 받침 5칸': ('cable_comb', None, 'white', None),
        }
        for text, (template, name, body, accent) in cases.items():
            with self.subTest(text=text):
                result = plan_from_text(text)
                self.assertEqual(result['status'], 'ready', result)
                parameters = result['parameters']
                self.assertEqual(parameters['template'], template)
                if name:
                    self.assertEqual(parameters['text'], name)
                self.assertEqual(parameters.get('color'), body)
                self.assertEqual(parameters.get('accent_color'), accent)
                self.assertTrue(any('색:' in note for note in result['assumptions']))

    def test_conflicting_or_inapplicable_colours_ask_instead_of_guessing(self):
        self.assertEqual(plan_from_text('빨간 파란 수납함')['status'], 'needs_input')
        self.assertIn('글자 색은 이름 키링에만', plan_from_text('빨간 글자 수납함 가로 10cm')['questions'][0])

    def test_english_colour_names_are_whole_words(self):
        self.assertEqual(extract_colors('shared tired box')[0], {})
        self.assertEqual(extract_colors('Red keychain')[0], {'color': 'red'})

    def test_edits_change_colours_text_and_sizes_together(self):
        tag = normalize_parameters(GeometryRequest(template='name_tag', text='MINSU').model_dump())
        tray = normalize_parameters(GeometryRequest().model_dump())
        cases = [
            (tag, '글자를 빨간색으로 바꿔줘', [('accent_color', '', 'red')]),
            (tag, '판은 흰색, 글자는 검정으로 해줘', [('color', '', 'white'), ('accent_color', '', 'black')]),
            (tag, '이름을 지우로 바꿔줘', [('text', 'MINSU', '지우')]),
            (tag, '글자를 "Mia"로 바꾸고 글자 크기 15mm', [('text', 'MINSU', 'Mia'), ('text_size', 12.0, 15.0)]),
            (tag, '구멍 지름 5mm로 바꿔줘', [('hole_diameter', 4.0, 5.0)]),
            (tag, '테두리 4mm, 받침 두께 3mm', [('wall', 2.0, 4.0), ('bottom', 2.0, 3.0)]),
            (tray, '파란색으로 하고 높이를 5mm 늘려줘', [('height', 35.0, 40.0), ('color', '', 'blue')]),
            (tray, '색을 초록으로 바꿔줘', [('color', '', 'green')]),
        ]
        for base, text, expected in cases:
            with self.subTest(text=text):
                result = plan_model_edit(text, base)
                self.assertEqual(result['status'], 'ready', result)
                self.assertEqual(changes(result), expected)

    def test_colour_edit_from_a_coloured_model_and_back_to_unchosen(self):
        base = normalize_parameters(GeometryRequest(template='name_tag', text='A', color='white', accent_color='red').model_dump())
        result = plan_model_edit('글자를 파랑으로', base)
        self.assertEqual(changes(result), [('accent_color', 'red', 'blue')])
        self.assertEqual(result['review']['parameters']['color'], 'white')

    def test_letter_colour_edit_on_other_templates_fails_closed(self):
        tray = normalize_parameters(GeometryRequest().model_dump())
        self.assertEqual(plan_model_edit('글자를 빨간색으로', tray)['status'], 'needs_input')


class ColoredModelTests(unittest.TestCase):
    def build(self, **parameters):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        return generate_model(GeometryRequest(**parameters), Path(folder.name)), Path(folder.name)

    def test_letters_in_their_own_colour_make_two_filament_parts(self):
        result, folder = self.build(template='name_tag', text='JIWOO', color='white', accent_color='red')
        parts = result['color_parts']
        self.assertEqual([(part['key'], part['color'], part['filament']) for part in parts],
                         [('base', 'white', 1), ('letters', 'red', 2)])
        self.assertAlmostEqual(sum(part['volume_mm3'] for part in parts), result['volume_mm3'], places=3)
        self.assertEqual(result['files']['color_three_mf'], 'model-colors.3mf')
        faces = result['mesh']['face_parts']
        self.assertEqual(len(faces), len(result['mesh']['faces']))
        self.assertEqual(set(faces), {0, 1})
        self.assertEqual([part['hex'] for part in result['mesh']['parts']], [PALETTE['white'][1], PALETTE['red'][1]])
        with zipfile.ZipFile(folder / 'model-colors.3mf') as archive:
            self.assertIsNone(archive.testzip())
            model = ET.fromstring(archive.read('3D/3dmodel.model'))
            config = ET.fromstring(archive.read('Metadata/model_settings.config'))
        meshes = model.findall(f'{CORE}resources/{CORE}object/{CORE}mesh')
        self.assertEqual(len(meshes), 2)
        components = model.findall(f'{CORE}resources/{CORE}object/{CORE}components/{CORE}component')
        self.assertEqual([item.get('objectid') for item in components], ['1', '2'])
        extruders = [part.find("metadata[@key='extruder']").get('value') for part in config.iter('part')]
        self.assertEqual(extruders, ['1', '2'])
        # The single-colour evidence files stay exactly as before.
        self.assertTrue((folder / 'model.3mf').is_file())
        self.assertNotIn('color', json.loads(json.dumps(GeometryRequest(template='name_tag', text='A').model_dump())))

    def test_single_colour_needs_no_extra_file(self):
        result, folder = self.build(color='blue')
        self.assertEqual([(part['key'], part['color']) for part in result['color_parts']], [('body', 'blue')])
        self.assertNotIn('color_three_mf', result['files'])
        self.assertNotIn('face_parts', result['mesh'])
        self.assertFalse((folder / 'model-colors.3mf').exists())
        same, _ = self.build(template='name_tag', text='A', color='red', accent_color='red')
        self.assertEqual(len(same['color_parts']), 1)

    def test_no_colour_leaves_results_unchanged(self):
        result, _ = self.build()
        self.assertEqual(result['color_parts'], [])
        self.assertNotIn('parts', result['mesh'])
        self.assertEqual(color_parts(GeometryRequest().model_dump()), [])


class ColoredJobAPITests(unittest.TestCase):
    def test_coloured_job_serves_and_bundles_the_colour_3mf_after_restart(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            with TestClient(create_app(root, test_mode=True)) as client:
                headers = {'X-Session-Token': client.get('/api/bootstrap').json()['session_token']}
                response = client.post('/api/models', json={'template': 'name_tag', 'text': 'JIWOO', 'color': 'white',
                                                            'accent_color': 'red'}, headers=headers)
                self.assertEqual(response.status_code, 200, response.text)
                job = response.json()
                url = job['artifacts']['color_three_mf']
                content = client.get(url).content
                manifest = client.get(job['artifacts']['manifest']).json()
                self.assertEqual(manifest['artifacts']['color_three_mf']['bytes'], len(content))
                self.assertEqual(manifest['parameters']['accent_color'], 'red')
                plain = client.post('/api/models', json={'template': 'tray'}, headers=headers).json()
                self.assertNotIn('color_three_mf', plain['artifacts'])
            with TestClient(create_app(root, test_mode=True)) as reopened:
                stored = reopened.get('/api/jobs/' + job['id']).json()
                self.assertEqual(reopened.get(stored['artifacts']['color_three_mf']).content, content)
                self.assertEqual(stored['result']['color_parts'][1]['name'], '빨강')


class EditedNameTagRegenerationTests(unittest.TestCase):
    def test_an_edited_name_tag_regenerates_without_width_depth_or_height(self):
        # The browser sends only a name tag's own fields; an applied edit must still generate.
        with tempfile.TemporaryDirectory() as temp, TestClient(create_app(Path(temp), test_mode=True)) as client:
            headers = {'X-Session-Token': client.get('/api/bootstrap').json()['session_token']}
            fields = {'template': 'name_tag', 'text': '지우', 'text_size': 12, 'text_depth': 2, 'wall': 3, 'bottom': 2,
                      'hole_diameter': 4, 'color': 'white', 'accent_color': 'red'}
            first = client.post('/api/models', json=fields, headers=headers).json()
            plan = client.post('/api/model-edits/plan', json={'text': '글자를 파란색으로 바꾸고 이름을 Mia로', 'base_parameters': fields,
                                                            'parent_job_id': first['id']}, headers=headers)
            self.assertEqual(plan.status_code, 200, plan.text)
            review = plan.json()['review']
            self.assertEqual([change['field'] for change in review['changes']], ['text', 'accent_color'])
            edited = {**fields, 'text': 'Mia', 'accent_color': 'blue', 'model_edit': review['selection']}
            response = client.post('/api/models', json=edited, headers=headers)
            self.assertEqual(response.status_code, 200, response.text)
            self.assertEqual(response.json()['result']['parameters']['accent_color'], 'blue')
            self.assertEqual(response.json()['model_edit']['changes'], review['changes'])

    def test_outline_sizes_are_not_editable_on_a_name_tag(self):
        base = normalize_parameters({'template': 'name_tag', 'text': 'A', 'text_size': 12, 'text_depth': 2, 'wall': 3,
                                     'bottom': 2, 'hole_diameter': 4})
        self.assertEqual(plan_model_edit('가로 50mm로', base)['status'], 'needs_input')


if __name__ == '__main__':
    unittest.main()
