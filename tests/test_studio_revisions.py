"""Immutable recipe publication and verified reads, using real bounded files."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from print_agent.studio_revisions import StudioSettingsRevisionStore, StudioRevisionIntegrityError
from print_agent.studio_settings import derive_settings
from print_agent.studio_sources import StudioProjectStore, StudioSourceIntegrityError
from tests.studio_project_fixtures import project_bytes


class StudioRevisionStoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.sources = StudioProjectStore(self.root)
        self.original = project_bytes()
        self.source = self.sources.import_project('원본.3mf', self.original)
        self.store = StudioSettingsRevisionStore(self.root, self.sources)
        self.proposal = {'source_sha256': self.source['source']['sha256'],
                         'settings_sha256': self.source['settings_sha256'],
                         'values': {'nozzle_temperature': '225', 'filament_flow_ratio': '0.98'}}
        snapshot, _ = self.sources.read(self.source['source_id'])
        _, review = derive_settings(snapshot, self.proposal)
        self.review_hash = review['review_sha256']

    def tearDown(self):
        self.temp.cleanup()

    def create(self):
        return self.store.create(self.source['source_id'], self.proposal, self.review_hash)

    def test_reopen_validates_recipe_original_and_independent_returned_values(self):
        saved = self.create()
        record = saved['revision']
        rid = record['revision_id']
        expected = copy.deepcopy(saved)
        self.assertEqual(set(saved), {'revision', 'review', 'source'})
        self.assertEqual(saved['source'], self.source)
        self.assertEqual(record['provenance'], 'user_selected')
        self.assertEqual(record['proposal']['values'], {'nozzle_temperature': '225', 'filament_flow_ratio': '0.98'})
        saved['revision']['proposal']['values']['nozzle_temperature'] = '100'
        saved['review']['changes'].clear()
        reopened = StudioSettingsRevisionStore(self.root, StudioProjectStore(self.root))
        self.assertEqual(reopened.get(rid), expected)
        snapshot, original, receipt = reopened.read(rid)
        self.assertEqual(original, self.original)
        self.assertEqual(snapshot['settings_sha256'], self.source['settings_sha256'])
        self.assertEqual(receipt, expected['revision'])
        self.assertEqual(self.sources.archive(self.source['source_id'])[1], self.original)

    def test_existing_empty_and_populated_directories_are_never_overwritten(self):
        rid = 'a' * 32
        folder = self.root / 'studio-settings-revisions' / rid
        folder.mkdir()
        for populated in (False, True):
            with self.subTest(populated=populated):
                if populated:
                    (folder / 'keep.txt').write_bytes(b'original data')
                before = {p.name: p.read_bytes() for p in folder.iterdir()}
                with patch('print_agent.studio_revisions.uuid.uuid4') as new_id:
                    new_id.return_value.hex = rid
                    with self.assertRaises(FileExistsError):
                        self.create()
                self.assertEqual({p.name: p.read_bytes() for p in folder.iterdir()}, before)

    def test_failed_publication_removes_only_its_owned_partial_directory(self):
        rid = 'b' * 32
        keep = self.root / 'studio-settings-revisions' / ('c' * 32)
        keep.mkdir()
        (keep / 'keep.txt').write_bytes(b'untouched')
        with patch('print_agent.studio_revisions.uuid.uuid4') as new_id, \
                patch('print_agent.studio_revisions._publish_revision', side_effect=OSError('simulated full disk')):
            new_id.return_value.hex = rid
            with self.assertRaises(OSError):
                self.create()
        self.assertFalse((keep.parent / rid).exists())
        self.assertEqual((keep / 'keep.txt').read_bytes(), b'untouched')
        with self.assertRaises(KeyError):
            self.store.read(rid)

    def test_incomplete_publication_is_not_readable(self):
        from print_agent import studio_revisions
        publish = studio_revisions._publish_revision
        observed = []
        def before_publish(path, record):
            with self.assertRaises(KeyError):
                self.store.get(record['revision_id'])
            observed.append(record['revision_id'])
            publish(path, record)
        with patch('print_agent.studio_revisions._publish_revision', side_effect=before_publish):
            saved = self.create()
        self.assertEqual(observed, [saved['revision']['revision_id']])
        self.assertEqual(self.store.get(observed[0]), saved)

    def test_invalid_review_or_values_publish_nothing(self):
        for proposal, review_hash in ((self.proposal, '0' * 64),
                ({**self.proposal, 'values': {'nozzle_temperature': '225', 'filament_flow_ratio': 'bad'}}, self.review_hash),
                ({**self.proposal, 'source_sha256': '0' * 64}, self.review_hash)):
            with self.assertRaises(ValueError):
                self.store.create(self.source['source_id'], proposal, review_hash)
        self.assertEqual(list((self.root / 'studio-settings-revisions').iterdir()), [])
        self.assertEqual(self.sources.archive(self.source['source_id'])[1], self.original)

    def test_corrupt_record_fields_are_rejected_on_every_read(self):
        saved = self.create()
        record = saved['revision']
        rid = record['revision_id']
        path = self.root / 'studio-settings-revisions' / rid / 'revision.json'
        mutations = (
            {'schema_version': True}, {'revision_id': 'f' * 32}, {'created_at': '2026-11-15T00:00:00'},
            {'source_id': '../escape'}, {'effective_settings_sha256': '0' * 64},
            {'review_sha256': '0' * 64}, {'changes': []}, {'provenance': 'manufacturer_verified'},
            {'unexpected': True},
            {'proposal': {**record['proposal'], 'values': {'nozzle_temperature': '226', 'filament_flow_ratio': '0.98'}}},
        )
        for mutation in mutations:
            with self.subTest(mutation=mutation):
                path.write_text(json.dumps({**record, **mutation}), encoding='utf-8')
                for read in (self.store.read, self.store.get):
                    with self.assertRaises(StudioRevisionIntegrityError):
                        read(rid)

    def test_oversized_duplicate_and_malformed_json_are_integrity_failures(self):
        saved = self.create()
        rid = saved['revision']['revision_id']
        path = self.root / 'studio-settings-revisions' / rid / 'revision.json'
        valid = path.read_bytes()
        for raw in (b' ' * 65537, b'{', b'{"schema_version":1,' + valid.lstrip()[1:]):
            path.write_bytes(raw)
            with self.assertRaises(StudioRevisionIntegrityError):
                self.store.get(rid)

    def test_record_and_parent_symlinks_are_rejected(self):
        saved = self.create()
        rid = saved['revision']['revision_id']
        path = self.root / 'studio-settings-revisions' / rid / 'revision.json'
        target = path.with_name('kept.json')
        path.rename(target)
        path.symlink_to(target)
        with self.assertRaises(StudioRevisionIntegrityError):
            self.store.get(rid)
        path.unlink()
        target.rename(path)
        folder = path.parent
        other = folder.with_name('kept-folder')
        folder.rename(other)
        folder.symlink_to(other, target_is_directory=True)
        with self.assertRaises(StudioRevisionIntegrityError):
            self.store.get(rid)

    def test_missing_and_changed_sources_keep_distinct_failure_meaning(self):
        saved = self.create()
        rid = saved['revision']['revision_id']
        source_dir = self.root / 'studio-projects' / self.source['source_id']
        (source_dir / 'source.3mf').write_bytes(b'corrupted')
        with self.assertRaises(StudioSourceIntegrityError):
            self.store.get(rid)
        (source_dir / 'source.3mf').write_bytes(self.original)
        (source_dir / 'receipt.json').unlink()
        with self.assertRaises(KeyError):
            self.store.get(rid)

    def test_invalid_ids_cannot_read_outside_the_store(self):
        for rid in ('../outside', 'a' * 31, 'A' * 32, '', None):
            with self.assertRaises(ValueError):
                self.store.read(rid)
        with self.assertRaises(KeyError):
            self.store.read('d' * 32)


if __name__ == '__main__':
    unittest.main()
