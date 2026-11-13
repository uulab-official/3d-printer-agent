"""Catalog, placement comparisons, server-owned source and real recipe CAD checks."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

import cadquery as cq
from pydantic import ValidationError

from print_agent.geometry import generate_model
from print_agent.schemas import GeometryRequest

try:
    from print_agent.discovery import (
        AvailableSpace, DiscoveryRequest, ProjectSelection, StaleProjectSelection,
        project_catalog, recommend_projects, resolve_project_selection,
    )
except ModuleNotFoundError as exc:
    if exc.name != 'print_agent.discovery':
        raise
    project_catalog = None


RECIPES = [
    ('small-parts-tray', 'organization', 'tray', 90, 60, 18, {'dividers': 0}),
    ('desk-sorter', 'organization', 'tray', 150, 90, 30, {'dividers': 2}),
    ('drawer-tray', 'organization', 'tray', 180, 100, 35, {'dividers': 1}),
    ('three-cable-rest', 'cables', 'cable_comb', 50, 18, 12, {'slots': 3}),
    ('five-cable-rest', 'cables', 'cable_comb', 80, 18, 12, {'slots': 5}),
    ('round-insert-frame', 'display', 'magnet_frame', 65, 65, 7, {}),
]


class DiscoveryTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(project_catalog, 'The project discovery implementation is missing')

    def matches(self, **query):
        return recommend_projects(DiscoveryRequest(**query))

    def test_six_recipes_have_complete_supported_starting_parameters(self):
        catalog = project_catalog()
        self.assertEqual(catalog['schema_version'], 1)
        self.assertEqual([p['id'] for p in catalog['purposes']],
                         ['all', 'organization', 'cables', 'display'])
        self.assertEqual(len(catalog['projects']), 6)
        for card, (project_id, purpose, template, width, depth, height, extras) in zip(catalog['projects'], RECIPES):
            with self.subTest(project=project_id):
                self.assertEqual((card['id'], card['purpose'], card['template']),
                                 (project_id, purpose, template))
                expected = GeometryRequest(template=template, width=width, depth=depth,
                                           height=height, wall=2, bottom=2, **extras)
                self.assertEqual(card['parameters'], expected.model_dump(mode='json'))
                for name in ('title', 'description', 'reason', 'measurements', 'limits'):
                    self.assertTrue(card[name])
                for name in ('measurements', 'limits'):
                    self.assertTrue(all(isinstance(text, str) for text in card[name]))
                self.assertEqual(card['source']['repository'],
                                 'https://github.com/uulab-official/3d-printer-agent')
                self.assertEqual(card['source']['path'], 'print_agent/geometry.py')
                self.assertEqual(card['source']['creator'], 'uulab-official')
                self.assertEqual(card['source']['license'], 'MIT')

    def test_digests_cover_exact_canonical_recipe_without_digest_field(self):
        for card in project_catalog()['projects']:
            with self.subTest(project=card['id']):
                recipe = {key: value for key, value in card.items() if key != 'recipe_sha256'}
                wire = json.dumps(recipe, ensure_ascii=False, sort_keys=True,
                                  separators=(',', ':'), allow_nan=False).encode('utf-8')
                self.assertEqual(card['recipe_sha256'], hashlib.sha256(wire).hexdigest())

    def test_catalog_and_recommendations_are_fresh_nested_copies(self):
        catalog = project_catalog()
        catalog['projects'][0]['parameters']['width'] = 999
        catalog['projects'][0]['source']['license'] = 'changed'
        catalog['projects'][0]['measurements'].clear()
        catalog['purposes'][0]['title'] = 'changed'
        matches = self.matches()
        self.assertEqual(matches['matches'][0]['project']['parameters']['width'], 90)
        self.assertEqual(matches['matches'][0]['project']['source']['license'], 'MIT')
        matches['matches'][0]['project']['limits'].clear()
        self.assertTrue(project_catalog()['projects'][0]['limits'])
        self.assertTrue(project_catalog()['projects'][0]['measurements'])
        self.assertEqual(project_catalog()['purposes'][0]['title'], '전체')

    def test_no_space_returns_all_in_order_without_claiming_a_fit(self):
        result = self.matches()
        self.assertEqual(result['schema_version'], 1)
        self.assertEqual(result['total_in_purpose'], 6)
        self.assertEqual(result['excluded_count'], 0)
        self.assertEqual(result['query'], {'purpose': 'all', 'available_space':
                                        {'width': None, 'depth': None, 'height': None}})
        self.assertEqual([m['project']['id'] for m in result['matches']], [r[0] for r in RECIPES])
        first = result['matches'][0]
        self.assertEqual(first['space_fit'], {'status': 'not_checked', 'orientation': None,
                                            'checked_axes': [], 'dimensions_mm':
                                            {'width': 90.0, 'depth': 60.0, 'height': 18.0}})
        self.assertTrue(first['reason'])
        self.assertTrue(result['limits'])

    def test_purpose_filter_is_exact_and_preserves_order(self):
        result = self.matches(purpose='cables')
        self.assertEqual([m['project']['id'] for m in result['matches']],
                         ['three-cable-rest', 'five-cable-rest'])
        self.assertEqual(result['total_in_purpose'], 2)
        self.assertEqual(result['excluded_count'], 0)

    def test_exact_boundary_prefers_original_orientation(self):
        result = self.matches(purpose='organization', available_space={'width': 90, 'depth': 60, 'height': 18})
        self.assertEqual(len(result['matches']), 1)
        self.assertEqual(result['excluded_count'], 2)
        fit = result['matches'][0]['space_fit']
        self.assertEqual((fit['status'], fit['orientation']), ('fits', 'original'))
        self.assertEqual(fit['checked_axes'], ['width', 'depth', 'height'])

    def test_width_depth_rotation_reports_compared_dimensions_without_changing_recipe(self):
        result = self.matches(purpose='organization', available_space={'width': 60, 'depth': 90, 'height': 18})
        self.assertEqual(len(result['matches']), 1)
        match = result['matches'][0]
        self.assertEqual(match['space_fit'], {'status': 'fits_rotated', 'orientation': 'rotated_90',
                                            'checked_axes': ['width', 'depth', 'height'],
                                            'dimensions_mm': {'width': 60.0, 'depth': 90.0, 'height': 18.0}})
        self.assertEqual(match['project']['parameters']['width'], 90)
        self.assertEqual(match['project']['parameters']['depth'], 60)

    def test_single_supplied_horizontal_axis_can_use_rotation_without_inventing_other_constraints(self):
        for space, axes, width, depth in (({'width': 60}, ['width'], 60, 90),
                                         ({'depth': 60}, ['depth'], 90, 60)):
            with self.subTest(space=space):
                result = self.matches(purpose='organization', available_space=space)
                self.assertEqual([m['project']['id'] for m in result['matches']], ['small-parts-tray'])
                fit = result['matches'][0]['space_fit']
                self.assertEqual(fit['checked_axes'], axes)
                self.assertEqual(fit['dimensions_mm'], {'width': width, 'depth': depth, 'height': 18})

    def test_height_only_excludes_tall_models_and_cannot_be_rotated(self):
        result = self.matches(available_space={'height': 12})
        self.assertEqual([m['project']['id'] for m in result['matches']],
                         ['three-cable-rest', 'five-cable-rest', 'round-insert-frame'])
        for match in result['matches']:
            self.assertEqual(match['space_fit']['status'], 'fits')
            self.assertEqual(match['space_fit']['checked_axes'], ['height'])
        result = self.matches(purpose='organization', available_space={'width': 1000, 'depth': 1000, 'height': 17.99})
        self.assertEqual(result['matches'], [])
        self.assertEqual(result['excluded_count'], 3)

    def test_zero_matches_is_a_successful_comparison(self):
        result = self.matches(available_space={'width': 1})
        self.assertEqual(result['matches'], [])
        self.assertEqual(result['total_in_purpose'], 6)
        self.assertEqual(result['excluded_count'], 6)
        self.assertTrue(result['limits'])

    def test_space_rejects_coercion_nonfinite_zero_and_unknown_fields(self):
        for value in (True, False, '90', '', 0, -1, float('nan'), float('inf'), -float('inf'), 10000.01):
            for axis in ('width', 'depth', 'height'):
                with self.subTest(axis=axis, value=value), self.assertRaises(ValidationError):
                    AvailableSpace(**{axis: value})
        with self.assertRaises(ValidationError):
            AvailableSpace(length=90)
        self.assertEqual(AvailableSpace(width=10000, depth=0.001).width, 10000)

    def test_request_rejects_unknown_purpose_and_extra_metadata(self):
        for query in ({'purpose': 'unknown'}, {'purpose': 'All'}, {'purpose': None},
                      {'available_space': None}, {'source': {'license': 'MIT'}},
                      {'available_space': {'printer_bed': 300}}):
            with self.subTest(query=query), self.assertRaises(ValidationError):
                DiscoveryRequest(**query)

    def test_project_selection_rejects_malformed_hash_ids_and_client_metadata(self):
        base = {'id': 'small-parts-tray', 'recipe_sha256': 'a' * 64}
        for patch in ({'recipe_sha256': 'A' * 64}, {'recipe_sha256': 'a' * 63},
                      {'recipe_sha256': 'g' * 64}, {'recipe_sha256': None},
                      {'id': ''}, {'id': 1}, {'source': {}}, {'customized': False}):
            with self.subTest(patch=patch), self.assertRaises(ValidationError):
                ProjectSelection(**{**base, **patch})
        for payload in ({}, {'id': 'small-parts-tray'}):
            with self.subTest(payload=payload), self.assertRaises(ValidationError):
                ProjectSelection(**payload)

    def selection(self, card):
        return ProjectSelection(id=card['id'], recipe_sha256=card['recipe_sha256'])

    def test_server_resolution_records_exact_recipe_and_normalized_parameter_changes(self):
        card = project_catalog()['projects'][0]
        source = resolve_project_selection(self.selection(card), GeometryRequest(**card['parameters']))
        self.assertEqual(source['kind'], 'project_catalog')
        self.assertEqual(source['schema_version'], 1)
        self.assertEqual(source['project_id'], 'small-parts-tray')
        self.assertEqual(source['recipe_sha256'], card['recipe_sha256'])
        self.assertEqual(source['recipe'], {k: v for k, v in card.items() if k != 'recipe_sha256'})
        self.assertFalse(source['customized'])
        self.assertEqual(source['changed_parameters'], [])
        changed = {**card['parameters'], 'width': 100, 'height': 22}
        customized = resolve_project_selection(self.selection(card), GeometryRequest(**changed))
        self.assertTrue(customized['customized'])
        self.assertEqual(customized['changed_parameters'], ['height', 'width'])
        self.assertEqual(customized['recipe']['parameters']['width'], 90)

    def test_unknown_stale_and_wrong_template_selections_are_rejected(self):
        card = project_catalog()['projects'][0]
        with self.assertRaises(ValueError):
            resolve_project_selection(ProjectSelection(id='missing', recipe_sha256='a' * 64), GeometryRequest())
        with self.assertRaises(StaleProjectSelection):
            resolve_project_selection(ProjectSelection(id=card['id'], recipe_sha256='0' * 64), GeometryRequest())
        with self.assertRaises(ValueError):
            resolve_project_selection(self.selection(card), GeometryRequest(template='cable_comb'))

    def test_resolved_source_is_independent_from_catalog_and_other_resolutions(self):
        card = project_catalog()['projects'][0]
        selection = self.selection(card)
        spec = GeometryRequest(**card['parameters'])
        source = resolve_project_selection(selection, spec)
        source['recipe']['parameters']['width'] = 123
        source['recipe']['source']['creator'] = 'changed'
        other = resolve_project_selection(selection, spec)
        self.assertEqual(other['recipe']['parameters']['width'], 90)
        self.assertEqual(other['recipe']['source']['creator'], 'uulab-official')

    def test_all_six_recipes_generate_real_cad_and_reimport_one_valid_solid(self):
        with tempfile.TemporaryDirectory() as directory:
            for card, (_, _, _, width, depth, height, _) in zip(project_catalog()['projects'], RECIPES):
                with self.subTest(project=card['id']):
                    folder = Path(directory) / card['id']
                    result = generate_model(GeometryRequest(**card['parameters']), folder)
                    self.assertEqual(result['geometry_status'], 'validated')
                    self.assertEqual(result['print_status'], 'not_tested')
                    self.assertTrue(all(check['passed'] for check in result['checks']))
                    solid = cq.importers.importStep(str(folder / result['files']['step'])).val()
                    self.assertTrue(solid.isValid())
                    self.assertEqual(len(solid.Solids()), 1)
                    self.assertGreater(solid.Volume(), 0)
                    bounds = solid.BoundingBox()
                    for axis, expected in zip('xyz', (width, depth, height)):
                        self.assertAlmostEqual(getattr(bounds, axis + 'len'), expected, places=5)
                    self.assertAlmostEqual(solid.Volume(), result['volume_mm3'], places=5)


if __name__ == '__main__':
    unittest.main()
