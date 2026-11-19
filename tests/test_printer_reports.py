"""A printer's finish/failure report, linked to the job this app sent, against the synthetic printer.

The synthetic printer prints nothing; these tests do not qualify a real printer."""
import json
import unittest
from unittest.mock import patch

from print_agent import printer_lan
from print_agent.printer_reports import HMS_SEARCH_URL, codes_of, recovery_item, subtask_for, terminal_record
from print_agent.recovery import recovery_plan
from tests import test_printer_send as send
from tests.test_printer_send import CODE, SERIAL, fake_printer

JOB = 'a' * 32


class PrinterReportRuleTests(unittest.TestCase):
    def failed(self, **extra):
        return {'state': 'FAILED', 'state_label': '실패', 'job_name': subtask_for(JOB), 'progress_percent': 37, 'layer': 44,
                'total_layers': 120, 'error_code': 0x0300400C, 'error_code_hex': '0300400C',
                'hms': [{'hms_code': '0700_8000_0002_0001'}, {'hms_code': 'bad'}], **extra}

    def test_codes_are_shown_in_search_form_and_never_interpreted(self):
        self.assertEqual(codes_of(self.failed()), [{'kind': 'print_error', 'code': '0300-400C'},
                                                   {'kind': 'hms', 'code': '0700-8000-0002-0001'}])
        self.assertEqual(codes_of({'error_code': 0, 'error_code_hex': None, 'hms': []}), [])
        item = recovery_item(terminal_record(JOB, SERIAL, self.failed(), '2026-11-19T00:00:00Z')[0])
        self.assertEqual(item['codes'], ['0300-400C', '0700-8000-0002-0001'])
        self.assertEqual(item['lookup_url'], HMS_SEARCH_URL)
        self.assertIn('44/120 레이어', item['actions'][0])
        self.assertIn('해석하지 않습니다', item['actions'][-1])

    def test_only_this_jobs_terminal_report_is_kept(self):
        self.assertIsNone(terminal_record(JOB, SERIAL, self.failed(state='RUNNING'), 'x')[0])
        record, why = terminal_record(JOB, SERIAL, self.failed(job_name='someone else'), 'x')
        self.assertIsNone(record)
        self.assertIn('작업 이름', why)
        finished = terminal_record(JOB, SERIAL, self.failed(state='FINISH', error_code=0, error_code_hex=None, hms=[]), 'x')[0]
        self.assertEqual((finished['source'], finished['codes']), ('printer_reported', []))
        self.assertIsNone(recovery_item(finished))

    def test_recovery_puts_the_printer_report_first_and_still_works_without_reasons(self):
        record = terminal_record(JOB, SERIAL, self.failed(error_code=0, error_code_hex=None, hms=[]), 'x')[0]
        plan = recovery_plan({'template': 'tray'}, ['warping'], printer_report=record)
        self.assertEqual([item['reason'] for item in plan['items']], ['printer_reported', 'warping'])
        self.assertIsNone(plan['items'][0]['lookup_url'])
        self.assertIn('오류 코드를 함께 보고하지', plan['items'][0]['actions'][1])
        self.assertEqual([item['reason'] for item in recovery_plan(None, [], printer_report=record)['items']], ['printer_reported'])


class PrinterReportFlowTests(send.SendFlowTests):
    """Send to the synthetic printer, let it fail, and read its status with the job id."""

    def started_job(self):
        self.simulator, self.mqtt, ftps = fake_printer()
        job_id = self.sliced_job()
        review = self.review(job_id, self.mqtt, slots=[0]).json()
        printer_lan._LAST_STATUS.clear()
        result = self.start(review['review_token'], self.mqtt, ftps).json()
        self.assertEqual(result['status'], 'started', result)
        return job_id

    def status(self, job_id):
        printer_lan._LAST_STATUS.clear()
        with patch.object(printer_lan, 'MQTT_PORT', self.mqtt):
            return self.client.post('/api/printers/status', headers=self.headers, json={
                'host': '127.0.0.1', 'serial': SERIAL, 'access_code': CODE, 'include_version': False, 'job_id': job_id})

    def test_failure_report_is_kept_once_and_offered_as_the_first_recovery_step(self):
        job_id = self.started_job()
        running = self.status(job_id).json()
        self.assertEqual(running['print']['job_name'], subtask_for(job_id))
        self.assertNotIn('job_link', running)
        self.simulator.state, self.simulator.error, self.simulator.args.hms = 'FAILED', 0x0300400C, True
        failed = self.status(job_id).json()
        self.assertTrue(failed['job_link']['recorded'], failed['job_link'])
        self.assertEqual([c['code'] for c in failed['job_link']['report']['codes']], ['0300-400C', '0700-8000-0002-0001'])
        self.assertTrue(self.status(job_id).json()['job_link']['recorded'])  # the same report again
        job = self.client.get('/api/jobs/' + job_id).json()
        self.assertEqual([e['type'] for e in job['events']].count('printer_report'), 1)
        self.assertEqual((job['printer_report']['state'], job['printer_report']['source']), ('FAILED', 'printer_reported'))
        self.assertIsNone(job['user_outcome'])  # the printer's report is not the person's outcome
        self.assertNotIn(CODE, json.dumps(job))
        plan = self.client.get(f'/api/jobs/{job_id}/recovery').json()
        self.assertEqual(plan['items'][0]['reason'], 'printer_reported')
        self.assertEqual(plan['items'][0]['lookup_url'], HMS_SEARCH_URL)
        attempt = self.client.get(f'/api/jobs/{job_id}/attempts').json()['attempts'][0]
        self.assertTrue(attempt['sent_to_printer'] and attempt['sliced'])
        self.assertEqual((attempt['printer_report']['state'], attempt['printer_report']['codes']),
                         ('FAILED', ['0300-400C', '0700-8000-0002-0001']))
        self.assertIsNone(attempt['user_outcome'])

    def test_reports_for_other_jobs_or_unsent_jobs_are_not_linked(self):
        sent = self.started_job()
        self.simulator.state = 'FINISH'
        other = self.client.post('/api/models', json={'template': 'tray'}, headers=self.headers).json()['id']
        refused = self.status(other).json()['job_link']
        self.assertFalse(refused['recorded'])
        self.assertIn('작업 이름', refused['detail'])
        self.assertNotIn('printer_report', self.client.get('/api/jobs/' + other).json())
        self.simulator.subtask = subtask_for(other)  # a matching name alone is not enough
        self.assertIn('보낸 기록', self.status(other).json()['job_link']['detail'])
        self.simulator.subtask = subtask_for(sent)
        self.assertEqual(self.status(sent).json()['job_link']['report']['state'], 'FINISH')
        before = len(self.simulator.requests)
        self.assertEqual(self.status('f' * 32).status_code, 404)
        self.assertEqual(len(self.simulator.requests), before)


# Only this class's own tests run here; the inherited send tests run in tests.test_printer_send.
for _name in [n for n in vars(send.SendFlowTests) if n.startswith('test_')]:
    setattr(PrinterReportFlowTests, _name, None)


if __name__ == '__main__':
    unittest.main()
