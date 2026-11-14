import contextlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from print_agent.__main__ import main


class DoctorTests(unittest.TestCase):
    def test_version_does_not_require_cad_import_or_a_data_directory(self):
        with patch.dict(sys.modules, {'cadquery': None}), \
             patch('sys.argv', ['printer-agent', '--version']), \
             contextlib.redirect_stdout(io.StringIO()) as output, self.assertRaises(SystemExit) as result:
            main()
        self.assertEqual(result.exception.code, 0)
        self.assertTrue(output.getvalue().startswith('3D Printer Agent '))

    def test_serve_reports_storage_and_passes_original_selection_to_the_app(self):
        with tempfile.TemporaryDirectory() as temp:
            selected = str(Path(temp) / '선택한 data')
            with patch.dict('os.environ', {'PPA_DATA_DIR': selected}), \
                 patch('sys.argv', ['printer-agent', 'serve', '--port', '8766']), \
                 patch('print_agent.app.create_app', return_value=object()) as create, \
                 patch('uvicorn.run') as serve, contextlib.redirect_stdout(io.StringIO()) as output:
                main()
            create.assert_called_once_with(None)
            self.assertEqual(serve.call_args.kwargs['host'], '127.0.0.1')
            self.assertEqual(serve.call_args.kwargs['port'], 8766)
            self.assertIn(f'Data directory (environment): {selected}', output.getvalue())
            self.assertFalse(Path(selected).exists())

    def test_doctor_rejects_a_regular_file_data_path_with_a_structured_report(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'sentinel'
            path.write_bytes(b'keep')
            with patch('sys.argv', ['printer-agent', 'doctor', '--data-dir', str(path)]), \
                 contextlib.redirect_stdout(io.StringIO()) as output, self.assertRaises(SystemExit) as result:
                main()
            self.assertEqual(result.exception.code, 1)
            report = json.loads(output.getvalue())
            self.assertFalse(report['ready'])
            self.assertEqual(report['storage']['path'], str(path))
            self.assertEqual(path.read_bytes(), b'keep')

    def test_doctor_emits_a_report_when_cad_cannot_import(self):
        with tempfile.TemporaryDirectory() as temp, patch.dict(sys.modules, {'cadquery': None}), \
             patch('sys.argv', ['printer-agent', 'doctor', '--data-dir', temp]), \
             contextlib.redirect_stdout(io.StringIO()) as output, self.assertRaises(SystemExit) as result:
            main()
        self.assertEqual(result.exception.code, 1)
        report = json.loads(output.getvalue())
        self.assertFalse(report['ready'])
        self.assertIn('storage', report)
        self.assertTrue(any(check['id'] == 'cadquery' and not check['passed'] for check in report['checks']))

    def test_doctor_keeps_native_execution_explicit(self):
        discovered = {'available': True, 'version': None}
        qualified = {'available': True, 'version': '02.09.01.70', 'cli_supported': True}
        for probe_requested in (False, True):
            with self.subTest(probe_requested=probe_requested), \
                 patch('sys.argv', ['printer-agent', 'doctor'] + (['--probe-slicer'] if probe_requested else [])), \
                 patch('print_agent.slicer.detect_environment', return_value=discovered) as detect, \
                 patch('print_agent.slicer.probe_environment', return_value=qualified, create=True) as probe, \
                 contextlib.redirect_stdout(io.StringIO()) as output:
                main()
                self.assertEqual(json.loads(output.getvalue())['slicer'], qualified if probe_requested else discovered)
                self.assertEqual(probe.call_count, int(probe_requested))
                self.assertEqual(detect.call_count, int(not probe_requested))

    def test_probe_flag_cannot_silently_start_server(self):
        with patch('sys.argv', ['printer-agent', '--probe-slicer']), \
             patch('uvicorn.run') as serve, contextlib.redirect_stderr(io.StringIO()), \
             self.assertRaises(SystemExit) as exit_result:
            main()
        self.assertEqual(exit_result.exception.code, 2)
        serve.assert_not_called()
