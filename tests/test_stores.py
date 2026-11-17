"""The curated where-to-buy directory: shape, honesty rules and delivery to the browser."""
import tempfile
import unittest
from pathlib import Path
from urllib.parse import urlsplit

from fastapi.testclient import TestClient

from print_agent.app import create_app
from print_agent.stores import EXCLUDED, KINDS, MATERIALS, STORES, UNCONFIRMED, store_guide


class StoreGuideTests(unittest.TestCase):
    def test_every_store_is_dated_categorised_and_linked_safely(self):
        guide = store_guide()
        self.assertRegex(guide['checked_on'], r'^\d{4}-\d{2}-\d{2}$')
        ids = [store['id'] for store in guide['stores'] + guide['unconfirmed']]
        self.assertEqual(len(ids), len(set(ids)))
        for store in guide['stores']:
            with self.subTest(store=store['id']):
                self.assertEqual(store['status'], 'active')
                self.assertTrue(store['materials'] and set(store['materials']) <= set(MATERIALS))
                self.assertTrue(store['kinds'] and set(store['kinds']) <= set(KINDS))
                self.assertTrue(store['sells'] and store['evidence'])
                self.assertIsInstance(store['bambu'], bool)
                for link in store['urls']:
                    parts = urlsplit(link['url'])
                    self.assertIn(parts.scheme, ('http', 'https'))
                    self.assertTrue(parts.netloc and link['label'])

    def test_closed_stores_are_excluded_and_unconfirmed_kept_apart(self):
        names = {store['name'] for store in STORES}
        for closed in EXCLUDED:
            self.assertTrue(closed['reason'])
            self.assertFalse(any(closed['name'] in name for name in names))
        self.assertTrue(all(store['status'] == 'unconfirmed' and store['reason'] for store in UNCONFIRMED))
        self.assertFalse({store['id'] for store in UNCONFIRMED} & {store['id'] for store in STORES})

    def test_no_prices_or_stock_are_stored(self):
        import re
        text = repr(store_guide()).lower()
        self.assertIsNone(re.search(r'\d[\d,]*\s*원|₩|\bprice\b|\bstock\b', text))

    def test_bambu_filter_matches_the_official_sources(self):
        bambu = {store['id'] for store in STORES if store['bambu']}
        self.assertIn('bambu-kr', bambu)
        self.assertTrue({'dyair', 'printboard'} <= bambu)

    def test_bootstrap_delivers_a_copy(self):
        with tempfile.TemporaryDirectory() as temp, TestClient(create_app(Path(temp), test_mode=True)) as client:
            guide = client.get('/api/bootstrap').json()['store_guide']
            self.assertEqual(len(guide['stores']), len(STORES))
            self.assertEqual(guide['excluded'][0]['name'], '퓨어필라')
        guide['stores'][0]['name'] = 'changed'
        self.assertNotEqual(store_guide()['stores'][0]['name'], 'changed')


if __name__ == '__main__':
    unittest.main()
