"""After a failed print: recorded reasons and reviewable next steps."""
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from print_agent.app import create_app
from print_agent.recovery import REASONS, recovery_plan, validate_reasons
from print_agent.schemas import GeometryRequest


class RecoveryPlanTests(unittest.TestCase):
    def changes(self, template, reason, **parameters):
        plan = recovery_plan(GeometryRequest(template=template, **parameters).model_dump(), [reason])
        edit = plan['items'][0]['model_edit']
        return edit and [(c['field'], c['before'], c['after']) for c in edit['changes']]

    def test_geometry_steps_are_valid_edits_of_the_current_model(self):
        self.assertEqual(self.changes('cable_comb', 'too_tight'), [('fit_clearance', 0.3, 0.5)])
        self.assertEqual(self.changes('magnet_frame', 'too_loose'), [('fit_clearance', 0.3, 0.2)])
        self.assertEqual(self.changes('name_tag', 'text_blurry', text='A'), [('text_size', 12.0, 14.0)])
        self.assertEqual(self.changes('name_tag', 'too_tight', text='A'), [('hole_diameter', 4.0, 4.3)])
        self.assertEqual(self.changes('name_tag', 'weak', text='A'), [('bottom', 2.0, 2.5)])
        self.assertEqual(self.changes('tray', 'too_tight'), [('width', 120.0, 122.0), ('depth', 80.0, 82.0)])
        self.assertEqual(self.changes('tray', 'weak'), [('wall', 2.0, 2.4)])

    def test_no_edit_when_none_applies_or_it_would_leave_the_range(self):
        self.assertIsNone(self.changes('tray', 'too_loose'))
        self.assertIsNone(self.changes('magnet_frame', 'too_loose', fit_clearance=0))
        self.assertIsNone(self.changes('name_tag', 'text_blurry', text='A', text_size=40))
        self.assertIsNone(self.changes('cable_comb', 'first_layer'))

    def test_every_reason_has_advice_and_unknown_reasons_are_skipped(self):
        plan = recovery_plan(GeometryRequest().model_dump(), [*REASONS, 'nonsense'])
        self.assertEqual([item['reason'] for item in plan['items']], list(REASONS))
        self.assertTrue(all(item['actions'] for item in plan['items']))
        self.assertEqual(recovery_plan(None, ['too_tight'])['items'][0]['model_edit'], None)

    def test_reason_validation(self):
        self.assertEqual(validate_reasons('failure', ['warping', 'warping']), ['warping'])
        self.assertEqual(validate_reasons('success', []), [])
        for result, reasons in (('success', ['warping']), ('failure', ['unknown']), ('failure', list(REASONS)), ('failure', 'warping')):
            with self.subTest(reasons=reasons), self.assertRaises(ValueError):
                validate_reasons(result, reasons)


class RecoveryAPITests(unittest.TestCase):
    def test_reasons_are_stored_with_the_failure_and_drive_the_plan(self):
        with tempfile.TemporaryDirectory() as temp, TestClient(create_app(Path(temp), test_mode=True)) as client:
            headers = {'X-Session-Token': client.get('/api/bootstrap').json()['session_token']}
            self.assertEqual(client.get('/api/bootstrap').json()['failure_reasons']['too_tight'], REASONS['too_tight'])
            job = client.post('/api/models', json={'template': 'cable_comb'}, headers=headers).json()
            self.assertEqual(client.get(f"/api/jobs/{job['id']}/recovery").json()['items'], [])
            saved = client.post(f"/api/jobs/{job['id']}/outcome", headers=headers,
                                json={'result': 'failure', 'notes': '케이블이 안 들어감', 'reasons': ['too_tight', 'stringing']}).json()
            self.assertEqual(saved['user_outcome']['reasons'], ['too_tight', 'stringing'])
            plan = client.get(f"/api/jobs/{job['id']}/recovery").json()
            self.assertEqual([item['reason'] for item in plan['items']], ['too_tight', 'stringing'])
            self.assertEqual(plan['items'][0]['model_edit']['text'], '여유 0.2mm 늘려줘')
            refused = client.post(f"/api/jobs/{job['id']}/outcome", headers=headers, json={'result': 'success', 'reasons': ['warping']})
            self.assertEqual(refused.status_code, 422)
            ok = client.post(f"/api/jobs/{job['id']}/outcome", headers=headers, json={'result': 'success'}).json()
            self.assertNotIn('reasons', ok['user_outcome'])
            self.assertEqual(client.get(f"/api/jobs/{job['id']}/recovery").json()['items'], [])


if __name__ == '__main__':
    unittest.main()
