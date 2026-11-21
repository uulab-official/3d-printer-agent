"""Glossary and first-run guide: valid links, served with bootstrap, and wired to real page parts."""
from pathlib import Path
import re
import tempfile
import unittest
from unittest import mock

from fastapi.testclient import TestClient

from print_agent import glossary as glossary_module
from print_agent.app import create_app
from print_agent.glossary import CATEGORIES, ONBOARDING, TERMS, VIEWS, glossary

STATIC = Path(__file__).resolve().parents[1] / 'print_agent' / 'static'


class GlossaryTests(unittest.TestCase):
    def test_entries_are_complete_and_linked(self):
        data = glossary()
        self.assertEqual(len(data['terms']), len(TERMS))
        self.assertGreaterEqual(len(TERMS), 30)
        self.assertEqual(set(data['categories']), set(CATEGORIES))
        for term in data['terms']:
            with self.subTest(term=term['id']):
                for key in ('term', 'aka', 'short', 'detail'):
                    self.assertTrue(term[key].strip())
                self.assertLessEqual(len(term['short']), 80)
                self.assertTrue(term['short'].endswith('.') and term['detail'].endswith('.'))
        self.assertEqual({term['category'] for term in TERMS}, set(CATEGORIES), 'every category has entries')
        self.assertEqual([step['id'] for step in ONBOARDING], ['make', 'check', 'settings', 'slice', 'record'])

    def test_served_copy_cannot_change_the_source(self):
        served = glossary()
        served['terms'][0]['short'] = 'changed'
        served['onboarding'].clear()
        self.assertNotEqual(glossary()['terms'][0]['short'], 'changed')
        self.assertEqual(len(glossary()['onboarding']), len(ONBOARDING))

    def test_invalid_entries_are_refused(self):
        base = TERMS[0]
        for change in ({'related': ['missing']}, {'related': [base['id']]}, {'category': 'other'}, {'view': 'nowhere'}, {'id': 'Bad Id'}):
            with self.subTest(change=change), mock.patch.object(glossary_module, 'TERMS', [{**base, **change}, *TERMS[1:]]):
                with self.assertRaises(ValueError):
                    glossary()
        with mock.patch.object(glossary_module, 'TERMS', [*TERMS, TERMS[0]]), self.assertRaises(ValueError):
            glossary()
        with mock.patch.object(glossary_module, 'ONBOARDING', [{**ONBOARDING[0], 'view': 'nowhere'}]), self.assertRaises(ValueError):
            glossary()

    def test_page_names_every_view_and_marked_term(self):
        html = (STATIC / 'index.html').read_text(encoding='utf-8')
        page_views = set(re.findall(r'class="nav-item[^"]*" data-view="([a-z]+)"', html))
        self.assertEqual(page_views, {*VIEWS, 'guide'})
        marked = re.findall(r'data-term="([a-z_]+)"', html)
        self.assertGreaterEqual(len(marked), 8)
        self.assertLessEqual(set(marked), {term['id'] for term in TERMS})
        script = (STATIC / 'app.js').read_text(encoding='utf-8')
        self.assertIn('guide: "용어·안내"', script)

    def test_bootstrap_includes_the_glossary(self):
        with tempfile.TemporaryDirectory() as directory, TestClient(create_app(Path(directory), test_mode=True)) as client:
            data = client.get('/api/bootstrap').json()
        self.assertEqual(data['glossary'], glossary())


if __name__ == '__main__':
    unittest.main()
