import contextlib
import io
import json
import unittest
from unittest.mock import patch

from print_agent.__main__ import main


class DoctorTests(unittest.TestCase):
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
