"""Pure revision policy tests with synthetic sources, not hardware validation."""
import copy
import hashlib
import json
import unittest

from print_agent.studio_project import inspect_studio_project
from print_agent.studio_settings import settings_editor, derive_settings, make_revision, verify_revision
from tests.studio_project_fixtures import project_bytes


class StudioSettingsTests(unittest.TestCase):
    source_id = '1' * 32
    revision_id = '2' * 32

    def snapshot(self, **overrides):
        return inspect_studio_project('source.3mf', project_bytes(settings_overrides=overrides))

    def proposal(self, snapshot, values=None):
        return {'source_sha256': snapshot['source']['sha256'], 'settings_sha256': snapshot['settings_sha256'], 'values': values or {}}

    def revision(self, snapshot, values=None):
        proposal = self.proposal(snapshot, values or {'nozzle_temperature': '230'})
        _, review = derive_settings(snapshot, proposal)
        return make_revision(snapshot, proposal, source_id=self.source_id, revision_id=self.revision_id,
                             created_at='2026-11-15T09:00:00+00:00', review_sha256=review['review_sha256'])

    def test_six_literal_edits_preserve_every_untouched_value_and_input(self):
        snapshot = self.snapshot(unknown_custom_setting=[['original', '값']], machine_start_gcode='M104 S200')
        original = copy.deepcopy(snapshot)
        values = {'nozzle_temperature': '230', 'nozzle_temperature_initial_layer': '235',
                  'filament_flow_ratio': '0.980000', 'filament_max_volumetric_speed': '12.500000',
                  'bed_temperature': '60', 'bed_temperature_initial_layer': '65'}
        proposal = self.proposal(snapshot, values)
        proposal_before = copy.deepcopy(proposal)
        effective, review = derive_settings(snapshot, proposal)
        before, after = json.loads(snapshot['settings_text']), json.loads(effective['settings_text'])
        changes = {'nozzle_temperature': ['230'], 'nozzle_temperature_initial_layer': ['235'],
                   'filament_flow_ratio': ['0.98'], 'filament_max_volumetric_speed': ['12.5'],
                   'hot_plate_temp': ['60'], 'hot_plate_temp_initial_layer': ['65']}
        self.assertEqual({k: after[k] for k in changes}, changes)
        self.assertEqual({k: v for k, v in before.items() if k not in changes},
                         {k: v for k, v in after.items() if k not in changes})
        self.assertEqual(set(before), set(after))
        self.assertEqual(review['changed_count'], 6)
        self.assertEqual([x['field'] for x in review['changes']], list(values))
        self.assertEqual(review['changes'][0], {'field': 'nozzle_temperature', 'native_key': 'nozzle_temperature', 'before': ['200'], 'after': ['230']})
        self.assertEqual(review['values']['filament_flow_ratio'], '0.98')
        self.assertEqual(effective['summary']['bed_temperature'], '60')
        self.assertEqual(effective['expected_settings']['hot_plate_temp'], ['60'])
        self.assertEqual(effective['source'], original['source'])
        self.assertEqual(effective['producer'], original['producer'])
        self.assertEqual(snapshot, original)
        self.assertEqual(proposal, proposal_before)
        identity = {k: review[k] for k in ('schema_version', 'source_sha256', 'settings_sha256', 'effective_settings_sha256', 'values', 'changes', 'provenance')}
        raw = json.dumps(identity, ensure_ascii=False, allow_nan=False, sort_keys=True, separators=(',', ':')).encode()
        self.assertEqual(review['review_sha256'], hashlib.sha256(raw).hexdigest())

    def test_partial_proposal_and_numeric_noop_preserve_exact_original_bytes(self):
        snapshot = self.snapshot(filament_flow_ratio=['01.000000'], unknown_custom_setting=['keep'])
        for values in ({}, {'filament_flow_ratio': ' 1.0 ', 'nozzle_temperature': '0200'}):
            effective, review = derive_settings(snapshot, self.proposal(snapshot, values))
            self.assertEqual(effective, snapshot)
            self.assertEqual(review['values'], {})
            self.assertEqual(review['changes'], [])
            self.assertEqual(review['changed_count'], 0)
            self.assertEqual(review['effective_settings_sha256'], snapshot['settings_sha256'])
        effective, review = derive_settings(snapshot, self.proposal(snapshot, {'nozzle_temperature': '0230', 'filament_flow_ratio': '1'}))
        after = json.loads(effective['settings_text'])
        self.assertEqual(after['filament_flow_ratio'], ['01.000000'])
        self.assertEqual(review['values'], {'nozzle_temperature': '230'})

    def test_editor_exposes_six_bounded_fields_and_selected_plate_only(self):
        for plate, prefix in (('Cool Plate', 'cool_plate'), ('Engineering Plate', 'eng_plate'), ('High Temp Plate', 'hot_plate'), ('Textured PEI Plate', 'textured_plate'), ('Supertack Plate', 'supertack_plate')):
            with self.subTest(plate=plate):
                snapshot = self.snapshot(curr_bed_type=plate, **{prefix + '_temp': ['40'], prefix + '_temp_initial_layer': ['45']})
                editor = settings_editor(snapshot)
                self.assertEqual(set(editor), {'schema_version', 'source_sha256', 'settings_sha256', 'fields', 'source_summary', 'warnings'})
                self.assertEqual(len(editor['fields']), 6)
                bed = editor['fields'][4]
                self.assertEqual(bed['native_key'], prefix + '_temp')
                self.assertEqual((bed['original'], bed['value'], bed['minimum'], bed['maximum'], bed['exclusive_minimum']), ('40', '40', 1, 120, False))
                flow = editor['fields'][2]
                self.assertEqual((flow['kind'], flow['minimum'], flow['maximum'], flow['exclusive_minimum']), ('decimal', 0, 2, True))
                effective, _ = derive_settings(snapshot, self.proposal(snapshot, {'bed_temperature': '60', 'bed_temperature_initial_layer': '65'}))
                self.assertEqual(json.loads(effective['settings_text'])[prefix + '_temp'], ['60'])
                self.assertEqual(effective['summary']['plate_type'], plate)

    def test_unknown_identity_gcode_process_and_other_plate_keys_are_refused_atomically(self):
        snapshot = self.snapshot()
        before = copy.deepcopy(snapshot)
        for field in ('unknown', 'curr_bed_type', 'printer_model', 'filament_settings_id', 'nozzle_diameter', 'machine_start_gcode', 'layer_height', 'hot_plate_temp', 'cool_plate_temp'):
            with self.subTest(field=field), self.assertRaises(ValueError):
                derive_settings(snapshot, self.proposal(snapshot, {'nozzle_temperature': '230', field: '60'}))
            self.assertEqual(snapshot, before)

    def test_invalid_text_types_bounds_and_atomic_proposals(self):
        snapshot = self.snapshot()
        before = copy.deepcopy(snapshot)
        invalid_common = [None, True, 230, 0.98, [], {}, '', ' ', '+1', '-1', '1e2', 'NaN', 'Infinity', '.5', '1.', '1.0000000', '1' * 33, '０１']
        for field in ('nozzle_temperature', 'filament_flow_ratio'):
            for value in invalid_common:
                with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                    derive_settings(snapshot, self.proposal(snapshot, {'bed_temperature': '60', field: value}))
                self.assertEqual(snapshot, before)
        for field, value in (('nozzle_temperature', '360.0'), ('nozzle_temperature', '0'), ('nozzle_temperature', '361'), ('bed_temperature', '121'), ('bed_temperature_initial_layer', '0'), ('filament_flow_ratio', '0'), ('filament_flow_ratio', '2.000001'), ('filament_max_volumetric_speed', '200.000001')):
            with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                derive_settings(snapshot, self.proposal(snapshot, {field: value}))
        _, review = derive_settings(snapshot, self.proposal(snapshot, {'nozzle_temperature': '360', 'nozzle_temperature_initial_layer': '1', 'bed_temperature': '120', 'bed_temperature_initial_layer': '1', 'filament_flow_ratio': '0.000001', 'filament_max_volumetric_speed': '200'}))
        self.assertEqual(review['changed_count'], 6)

    def test_proposal_schema_source_identity_and_snapshot_integrity(self):
        snapshot = self.snapshot()
        base = self.proposal(snapshot, {'nozzle_temperature': '230'})
        invalid = [None, [], {**base, 'extra': 1}, {k:v for k,v in base.items() if k != 'values'}, {**base, 'values': []}, {**base, 'source_sha256': '0'*64}, {**base, 'settings_sha256': '0'*64}]
        for proposal in invalid:
            with self.subTest(proposal=proposal), self.assertRaises(ValueError): derive_settings(snapshot, proposal)
        for key, value in (('settings_text', snapshot['settings_text']+' '), ('expected_settings', {}), ('supported', False), ('source', {'sha256': 'bad'}), ('summary', {**snapshot['summary'], 'plate_type': 'Cool Plate'})):
            altered = copy.deepcopy(snapshot); altered[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError): derive_settings(altered, base)

    def test_unsupported_original_editable_representations_cannot_be_repaired(self):
        for key, value in (('nozzle_temperature', ['200.5']), ('nozzle_temperature', ['361']), ('filament_flow_ratio', ['2.1']), ('filament_max_volumetric_speed', ['201']), ('hot_plate_temp', ['121']), ('hot_plate_temp', '50'), ('nozzle_temperature', ['2e2'])):
            snapshot = self.snapshot(**{key: value})
            for operation in (lambda: settings_editor(snapshot), lambda: derive_settings(snapshot, self.proposal(snapshot, {'nozzle_temperature': '230'}))):
                with self.subTest(key=key, value=value), self.assertRaises(ValueError): operation()

    def test_revision_roundtrip_uses_canonical_changed_only_proposal(self):
        snapshot = self.snapshot()
        proposal = self.proposal(snapshot, {'nozzle_temperature': ' 0230 ', 'filament_flow_ratio': '1.000000'})
        _, review = derive_settings(snapshot, proposal)
        revision = make_revision(snapshot, proposal, source_id=self.source_id, revision_id=self.revision_id, created_at='2026-11-15T09:00:00Z', review_sha256=review['review_sha256'])
        self.assertEqual(set(revision), {'schema_version', 'revision_id', 'created_at', 'source_id', 'proposal', 'review_sha256', 'effective_settings_sha256', 'changes', 'provenance'})
        self.assertEqual(revision['proposal'], self.proposal(snapshot, {'nozzle_temperature': '230'}))
        effective, verified = verify_revision(snapshot, revision, source_id=self.source_id)
        self.assertEqual(verified, review)
        self.assertEqual(json.loads(effective['settings_text'])['nozzle_temperature'], ['230'])

    def test_revision_rejects_mismatch_zero_changes_bad_ids_and_naive_time(self):
        snapshot = self.snapshot()
        proposal = self.proposal(snapshot, {'nozzle_temperature': '230'})
        _, review = derive_settings(snapshot, proposal)
        kwargs = dict(source_id=self.source_id, revision_id=self.revision_id, created_at='2026-11-15T09:00:00+00:00', review_sha256=review['review_sha256'])
        for key, value in (('source_id', '../escape'), ('source_id', 'a'*31), ('revision_id', True), ('revision_id', 'A'*32), ('created_at', '2026-11-15T09:00:00'), ('created_at', 1), ('review_sha256', '0'*64)):
            with self.subTest(key=key), self.assertRaises(ValueError): make_revision(snapshot, proposal, **{**kwargs, key:value})
        _, noop = derive_settings(snapshot, self.proposal(snapshot))
        with self.assertRaises(ValueError): make_revision(snapshot, self.proposal(snapshot), **{**kwargs, 'review_sha256':noop['review_sha256']})

    def test_revision_exact_schema_and_all_recorded_identity_fields_are_verified(self):
        snapshot = self.snapshot()
        revision = self.revision(snapshot)
        bad = [('schema_version', True), ('schema_version', 2), ('source_id', '3'*32), ('revision_id', '../bad'), ('created_at', 'yesterday'), ('provenance', 'manufacturer'), ('review_sha256', '0'*64), ('effective_settings_sha256', '0'*64), ('changes', []), ('changes', [{'field': 'nozzle_temperature', 'native_key': 'nozzle_temperature', 'before': ['201'], 'after': ['230']}]), ('extra', 1), ('proposal', self.proposal(snapshot, {'nozzle_temperature': '0230'}))]
        for key, value in bad:
            altered = copy.deepcopy(revision); altered[key] = value
            with self.subTest(key=key, value=value), self.assertRaises(ValueError): verify_revision(snapshot, altered, source_id=self.source_id)
        for key in revision:
            altered = copy.deepcopy(revision); del altered[key]
            with self.subTest(missing=key), self.assertRaises(ValueError): verify_revision(snapshot, altered, source_id=self.source_id)
        other_plate = self.snapshot(curr_bed_type='Cool Plate')
        with self.assertRaises(ValueError): verify_revision(other_plate, revision, source_id=self.source_id)

    def test_revision_types_are_exact_even_when_python_or_json_coerces_them(self):
        snapshot = self.snapshot()
        revision = self.revision(snapshot)
        for change in (tuple(revision['changes']),
                       [{'field': 'nozzle_temperature', 'native_key': 'nozzle_temperature', 'before': ('200',), 'after': ['230']}],
                       [{'field': 'nozzle_temperature', 'native_key': 'nozzle_temperature', 'before': ['200'], 'after': ('230',)}]):
            altered = copy.deepcopy(revision)
            altered['changes'] = change
            with self.subTest(change=change), self.assertRaises(ValueError):
                verify_revision(snapshot, altered, source_id=self.source_id)
