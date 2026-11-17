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


class LaunchTests(unittest.TestCase):
    def run_main(self, argv, **patches):
        out, err = io.StringIO(), io.StringIO()
        with patch('sys.argv', ['printer-agent', *argv]), contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            try:
                main()
                code = 0
            except SystemExit as exit:
                code = exit.code
        return code, out.getvalue(), err.getvalue()

    def test_second_launch_points_to_the_running_app_instead_of_failing(self):
        with patch('print_agent.__main__._port_free', return_value=False), \
             patch('print_agent.__main__._agent_answers', return_value=True), \
             patch('print_agent.__main__._should_open_browser', return_value=True), \
             patch('print_agent.__main__.webbrowser.open') as opened, patch('uvicorn.run') as serve:
            code, out, _ = self.run_main(['serve', '--port', '8770'])
        self.assertEqual(code, 0)
        self.assertIn('이미 실행 중', out)
        opened.assert_called_once_with('http://127.0.0.1:8770')
        serve.assert_not_called()

    def test_port_used_by_another_program_suggests_the_next_port(self):
        with patch('print_agent.__main__._port_free', return_value=False), \
             patch('print_agent.__main__._agent_answers', return_value=False), \
             patch('print_agent.__main__.webbrowser.open') as opened, patch('uvicorn.run') as serve:
            code, _, err = self.run_main(['serve', '--port', '8770'])
        self.assertEqual(code, 1)
        self.assertIn('--port 8771', err)
        opened.assert_not_called()
        serve.assert_not_called()

    def test_data_folder_in_use_fails_before_the_server_with_a_message(self):
        from print_agent.runtime import DataDirectoryLease
        with tempfile.TemporaryDirectory() as temp, DataDirectoryLease(Path(temp)):
            with patch('print_agent.__main__._port_free', return_value=True), patch('uvicorn.run') as serve:
                code, _, err = self.run_main(['serve', '--port', '8770', '--data-dir', temp])
        self.assertEqual(code, 1)
        self.assertIn('다른 3D Printer Agent가 사용 중', err)
        self.assertNotIn('Traceback', err)
        serve.assert_not_called()

    def test_browser_opens_only_for_a_person_at_a_terminal(self):
        from print_agent.__main__ import _should_open_browser
        class Args:
            no_browser = False
        tty = type('TTY', (), {'isatty': lambda self: True})()
        pipe = type('Pipe', (), {'isatty': lambda self: False})()
        with patch.dict('os.environ', {}, clear=False), patch('sys.stdout', tty):
            os_env = __import__('os').environ
            os_env.pop('PPA_NO_BROWSER', None)
            self.assertTrue(_should_open_browser(Args()))
            Args.no_browser = True
            self.assertFalse(_should_open_browser(Args()))
            Args.no_browser = False
            with patch.dict('os.environ', {'PPA_NO_BROWSER': '1'}):
                self.assertFalse(_should_open_browser(Args()))
        with patch('sys.stdout', pipe):
            self.assertFalse(_should_open_browser(Args()))

    def test_port_check_ignores_time_wait_but_sees_a_listener(self):
        import socket
        from print_agent.__main__ import _port_free
        server = socket.socket(); server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind(('127.0.0.1', 0)); server.listen(); port = server.getsockname()[1]
        self.assertFalse(_port_free(port))
        client = socket.create_connection(('127.0.0.1', port)); accepted, _ = server.accept()
        accepted.close(); client.close(); server.close()  # the server side closes first -> TIME_WAIT
        self.assertTrue(_port_free(port))

    def test_no_browser_is_only_for_serve(self):
        code, _, err = self.run_main(['doctor', '--no-browser'])
        self.assertEqual(code, 2)
        self.assertIn('only available with serve', err)

    def test_free_port_starts_the_server_once(self):
        with patch('print_agent.__main__._port_free', return_value=True), \
             patch('print_agent.app.create_app', return_value=object()), \
             patch('print_agent.__main__._should_open_browser', return_value=False), \
             patch('uvicorn.run') as serve, tempfile.TemporaryDirectory() as temp:
            code, out, _ = self.run_main(['serve', '--port', '8770', '--data-dir', temp])
        self.assertEqual(code, 0)
        serve.assert_called_once()
        self.assertIn('Starting 3D Printer Agent: http://127.0.0.1:8770', out)
