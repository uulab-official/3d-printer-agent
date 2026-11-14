"""Backup commands stay explicit and usable without CAD/web installations."""
import contextlib
import io
import json
import os
from pathlib import Path
import subprocess
import struct
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from print_agent.__main__ import main
from print_agent.storage import JobStore
from print_agent.workspaces import ProfileWorkspaceStore


class BackupCliTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.data = self.root / '원본 data'
        self.archive = self.root / '작업 백업.zip'
        self.target = self.root / '복원 data'

    def tearDown(self):
        self.temp.cleanup()

    def call(self, *arguments):
        output, errors = io.StringIO(), io.StringIO()
        with patch('sys.argv', ['printer-agent', *map(str, arguments)]), \
             contextlib.redirect_stdout(output), contextlib.redirect_stderr(errors):
            try:
                main()
                code = 0
            except SystemExit as exc:
                code = exc.code
        return code, output.getvalue(), errors.getvalue()

    def test_missing_source_reports_json_and_does_not_create_data(self):
        code, output, errors = self.call('backup', '--data-dir', self.data, '--output', self.archive)
        self.assertEqual(code, 1)
        self.assertEqual(json.loads(output)['status'], 'error')
        self.assertFalse(self.data.exists())
        self.assertFalse(self.archive.exists())
        self.assertNotIn('Traceback', errors)

    def test_valid_commands_round_trip_exact_saved_data(self):
        store = JobStore(self.data)
        job_id, folder = store.reserve(request={'template': 'tray', 'width': 45})
        store.fail(job_id, 'synthetic CLI fixture')
        ProfileWorkspaceStore(self.data)
        original = (folder / 'job.json').read_bytes()
        code, output, errors = self.call('backup', '--data-dir', self.data, '--output', self.archive)
        self.assertEqual((code, errors), (0, ''))
        created = json.loads(output)
        self.assertEqual(created['status'], 'created')
        code, output, errors = self.call('backup-info', '--archive', self.archive)
        self.assertEqual((code, errors), (0, ''))
        verified = json.loads(output)
        self.assertEqual(verified['status'], 'verified')
        self.assertEqual(verified['archive_sha256'], created['archive_sha256'])
        code, output, errors = self.call('restore', '--archive', self.archive, '--destination', self.target)
        self.assertEqual((code, errors), (0, ''))
        self.assertEqual(json.loads(output)['data_dir'], str(self.target.resolve()))
        self.assertEqual((self.target / 'jobs' / job_id / 'job.json').read_bytes(), original)
        self.assertEqual((folder / 'job.json').read_bytes(), original)

    def test_argument_combinations_do_not_start_server_or_guess_paths(self):
        invalid = [
            ['backup'], ['backup-info'], ['restore', '--archive', str(self.archive)],
            ['backup', '--output', str(self.archive), '--port', '8765'],
            ['backup-info', '--archive', str(self.archive), '--data-dir', str(self.data)],
            ['restore', '--archive', str(self.archive), '--destination', str(self.target), '--output', str(self.archive)],
            ['serve', '--archive', str(self.archive)], ['doctor', '--output', str(self.archive)],
            ['backup', '--output', str(self.archive), '--probe-slicer'],
        ]
        with patch('uvicorn.run') as serve:
            for arguments in invalid:
                with self.subTest(arguments=arguments):
                    code, _, _ = self.call(*arguments)
                    self.assertEqual(code, 2)
            serve.assert_not_called()
        self.assertEqual(list(self.root.iterdir()), [])

    def test_backup_module_and_inspection_do_not_import_cad_or_web(self):
        JobStore(self.data)
        self.assertEqual(self.call('backup', '--data-dir', self.data, '--output', self.archive)[0], 0)
        script = """import runpy, sys
for name in ('cadquery', 'fastapi', 'uvicorn', 'httpx', 'pydantic'):
    sys.modules[name] = None
sys.argv = ['printer-agent', 'backup-info', '--archive', sys.argv[1]]
runpy.run_module('print_agent', run_name='__main__')
"""
        result = subprocess.run([sys.executable, '-c', script, str(self.archive)],
                                capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)['status'], 'verified')

    def test_inspection_and_restore_ignore_configured_original_data_path(self):
        JobStore(self.data)
        self.assertEqual(self.call('backup', '--data-dir', self.data, '--output', self.archive)[0], 0)
        sentinel = self.root / 'unrelated configured path'
        sentinel.write_bytes(b'unchanged')
        with patch.dict(os.environ, {'PPA_DATA_DIR': str(sentinel)}):
            self.assertEqual(self.call('backup-info', '--archive', self.archive)[0], 0)
            self.assertEqual(self.call('restore', '--archive', self.archive, '--destination', self.target)[0], 0)
        self.assertEqual(sentinel.read_bytes(), b'unchanged')

    def test_unsupported_zip_extraction_version_reports_json_without_traceback(self):
        JobStore(self.data)
        self.assertEqual(self.call('backup', '--data-dir', self.data, '--output', self.archive)[0], 0)
        with zipfile.ZipFile(self.archive) as archive:
            central = archive.start_dir
        changed = bytearray(self.archive.read_bytes())
        struct.pack_into('<H', changed, central + 6, 99)
        self.archive.write_bytes(changed)
        for arguments in (['backup-info', '--archive', self.archive],
                          ['restore', '--archive', self.archive, '--destination', self.target]):
            with self.subTest(command=arguments[0]):
                code, output, errors = self.call(*arguments)
                self.assertEqual(code, 1)
                self.assertEqual(json.loads(output)['status'], 'error')
                self.assertEqual(errors, '')
                self.assertFalse(self.target.exists())
                self.assertEqual(self.archive.read_bytes(), changed)
