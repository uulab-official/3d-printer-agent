"""Immutable source publication and readback, using synthetic Studio fixtures."""
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from print_agent.studio_sources import StudioProjectStore, StudioSourceIntegrityError
from tests.studio_project_fixtures import project_bytes


class StudioSourceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.store = StudioProjectStore(self.root)
        self.content = project_bytes()

    def tearDown(self):
        self.temp.cleanup()

    def test_exact_original_and_public_inspection_survive_reopening(self):
        source = self.store.import_project('설정 원본.3mf', self.content)
        self.assertTrue(source['supported'], source)
        self.assertNotIn('settings_text', source)
        self.assertNotIn('expected_settings', source)
        source_id = source['source_id']
        self.assertRegex(source_id, r'^[a-f0-9]{32}$')
        self.assertEqual(source['source']['sha256'], hashlib.sha256(self.content).hexdigest())
        self.assertEqual(source['archive_url'], f'/api/studio-projects/{source_id}/archive')
        saved = copy.deepcopy(source)
        source['summary']['printer_model'] = 'caller changed this'
        reopened = StudioProjectStore(self.root)
        self.assertEqual(reopened.get(source_id), saved)
        self.assertEqual(reopened.archive(source_id), ('설정 원본.3mf', self.content))
        snapshot, raw = reopened.read(source_id)
        self.assertIn('settings_text', snapshot)
        self.assertEqual(raw, self.content)

    def test_unsupported_source_can_be_inspected_and_downloaded(self):
        raw = project_bytes(application='BambuStudio-99.00.00.00', settings_overrides={'version': '99.00.00.00'})
        source = self.store.import_project('future.3mf', raw)
        self.assertFalse(source['supported'])
        self.assertTrue(source['issues'])
        self.assertEqual(self.store.archive(source['source_id'])[1], raw)

    def test_malformed_input_publishes_nothing(self):
        with self.assertRaises(ValueError):
            self.store.import_project('broken.3mf', b'broken archive')
        self.assertEqual(list((self.root / 'studio-projects').iterdir()), [])

    def test_existing_empty_or_populated_destination_never_replaced(self):
        chosen = 'a' * 32
        folder = self.root / 'studio-projects' / chosen
        folder.mkdir()
        for populated in (False, True):
            with self.subTest(populated=populated):
                if populated:
                    (folder / 'keep').write_bytes(b'original bytes')
                before = {p.name: p.read_bytes() for p in folder.iterdir()}
                with patch('print_agent.studio_sources.uuid.uuid4') as make_id:
                    make_id.return_value.hex = chosen
                    with self.assertRaises(FileExistsError):
                        self.store.import_project('source.3mf', self.content)
                self.assertEqual({p.name: p.read_bytes() for p in folder.iterdir()}, before)

    def test_failed_publication_does_not_leave_readable_source(self):
        chosen = 'b' * 32
        with patch('print_agent.studio_sources.uuid.uuid4') as make_id, \
             patch('print_agent.studio_sources._publish_receipt', side_effect=OSError('simulated full disk')):
            make_id.return_value.hex = chosen
            with self.assertRaises(OSError):
                self.store.import_project('source.3mf', self.content)
        self.assertFalse((self.root / 'studio-projects' / chosen).exists())
        self.assertEqual(list((self.root / 'studio-projects').iterdir()), [])

    def test_changed_archive_or_receipt_is_never_returned(self):
        for changed in ('archive', 'receipt'):
            with self.subTest(changed=changed):
                source = self.store.import_project('source.3mf', self.content)
                folder = self.root / 'studio-projects' / source['source_id']
                if changed == 'archive':
                    path = folder / 'source.3mf'
                    raw = path.read_bytes()
                    path.write_bytes(raw[:-1] + bytes([raw[-1] ^ 1]))
                else:
                    path = folder / 'receipt.json'
                    receipt = json.loads(path.read_bytes())
                    receipt['inspection']['summary']['nozzle_diameter'] = '99'
                    path.write_text(json.dumps(receipt), encoding='utf-8')
                for read in (self.store.get, self.store.read, self.store.archive):
                    with self.assertRaises(StudioSourceIntegrityError):
                        read(source['source_id'])

    def test_invalid_unknown_and_partial_ids_have_no_source(self):
        for source_id in ('../escape', 'x' * 32, '', 'a/b'):
            with self.assertRaises(ValueError):
                self.store.get(source_id)
        with self.assertRaises(KeyError):
            self.store.get('c' * 32)
        partial = self.root / 'studio-projects' / ('d' * 32)
        partial.mkdir()
        (partial / 'source.3mf').write_bytes(self.content)
        with self.assertRaises(KeyError):
            self.store.get(partial.name)

    def test_symlink_source_record_and_parent_are_refused(self):
        source = self.store.import_project('source.3mf', self.content)
        folder = self.root / 'studio-projects' / source['source_id']
        original = folder / 'source.3mf'
        outside = self.root / 'outside.3mf'
        outside.write_bytes(original.read_bytes())
        original.unlink()
        try:
            original.symlink_to(outside)
        except OSError:
            self.skipTest('OS does not permit creating symlinks')
        with self.assertRaises(StudioSourceIntegrityError):
            self.store.get(source['source_id'])
        original.unlink()
        original.write_bytes(self.content)
        saved_parent = self.root / 'saved-projects'
        (self.root / 'studio-projects').rename(saved_parent)
        (self.root / 'studio-projects').symlink_to(saved_parent, target_is_directory=True)
        with self.assertRaises(StudioSourceIntegrityError):
            self.store.get(source['source_id'])
        with self.assertRaises(StudioSourceIntegrityError):
            StudioProjectStore(self.root)
