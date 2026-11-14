"""Offline backup boundaries using actual files, ZIP streams and publication."""
from contextlib import contextmanager
import errno
import hashlib
import importlib
import io
import json
import os
from pathlib import Path
import sqlite3
import stat
import struct
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import warnings
import zipfile
import zlib

from print_agent.runtime import DataDirectoryInUse, DataDirectoryLease


def digest(content):
    return hashlib.sha256(content).hexdigest()


def fixture_manifest(files):
    return {
        'format': '3d-printer-agent-backup', 'version': 1,
        'application_version': '0.2.0', 'created_at': '2026-11-14T00:00:00+00:00',
        'file_count': len(files), 'total_bytes': sum(len(content) for content in files.values()),
        'files': [{'path': name, 'bytes': len(content), 'sha256': digest(content)}
                  for name, content in files.items()],
    }


def write_archive(path, files, *, manifest=None, manifest_text=None, extra=None,
                  compression=zipfile.ZIP_DEFLATED):
    manifest = fixture_manifest(files) if manifest is None else manifest
    with zipfile.ZipFile(path, 'w', compression=compression) as archive:
        archive.writestr('manifest.json', json.dumps(manifest) if manifest_text is None else manifest_text)
        for name, content in files.items():
            archive.writestr('data/' + name, content)
        if extra:
            for name, content in extra:
                archive.writestr(name, content)


def edit_member_headers(path, name, *, expanded=None, crc=None, flags=None):
    """Independently forge matching local/central headers, preserving payload."""
    content = bytearray(path.read_bytes())
    with zipfile.ZipFile(path) as archive:
        local = archive.getinfo(name).header_offset
        central = archive.start_dir
        while content[central:central + 4] == b'PK\x01\x02':
            name_size, extra_size, comment_size = struct.unpack_from('<3H', content, central + 28)
            if content[central + 46:central + 46 + name_size].decode('utf-8') == name:
                break
            central += 46 + name_size + extra_size + comment_size
        else:
            raise AssertionError('Fixture central entry not found')
    for value, code, local_offset, central_offset in (
        (expanded, '<L', 22, 24), (crc, '<L', 14, 16), (flags, '<H', 6, 8),
    ):
        if value is not None:
            struct.pack_into(code, content, local + local_offset, value)
            struct.pack_into(code, content, central + central_offset, value)
    path.write_bytes(content)


@contextmanager
def windows_path_and_descriptor_metadata(*, descriptor_changes=False, legacy_creation_time=False):
    """Emulate CPython 3.12's documented/source-defined Windows stat paths."""
    path_stat, descriptor_stat = Path.lstat, os.fstat
    descriptor_reads = 0

    def fields(metadata):
        result = {name: getattr(metadata, name) for name in dir(metadata) if name.startswith('st_')}
        result['st_birthtime_ns'] = 1_700_000_000_000_000_000
        return result

    def windows_lstat(path, *args, **kwargs):
        result = fields(path_stat(path, *args, **kwargs))
        result['st_ctime_ns'] = result['st_birthtime_ns']
        if legacy_creation_time:
            del result['st_birthtime_ns']
        if path.name.lower().endswith(('.exe', '.bat', '.cmd', '.com')):
            result['st_mode'] |= 0o111
        return SimpleNamespace(**result)

    def windows_fstat(descriptor):
        nonlocal descriptor_reads
        result = fields(descriptor_stat(descriptor))
        descriptor_reads += 1
        # fstat returns ChangeTime, while path stat aliases ctime to birthtime.
        result['st_ctime_ns'] = result['st_birthtime_ns'] + (0 if legacy_creation_time else 100) + (descriptor_reads if descriptor_changes else 0)
        if legacy_creation_time:
            del result['st_birthtime_ns']
        return SimpleNamespace(**result)

    with patch.object(sys, 'platform', 'win32'), patch.object(Path, 'lstat', windows_lstat), patch.object(os, 'fstat', windows_fstat):
        yield


class BackupTests(unittest.TestCase):
    def setUp(self):
        try:
            self.backup = importlib.import_module('print_agent.backup')
        except ModuleNotFoundError:
            self.fail('Verified offline backup operations have not been implemented.')
        self.temporary = tempfile.TemporaryDirectory(prefix='ppa-backup-test-')
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        self.source = self.root / '원본 작업 space'
        self.source.mkdir()
        self.archive = self.root / '보관 backup.zip'
        self.destination = self.root / '복원 작업 space'

    def canonical_workspace(self):
        database = self.source / 'profile-workspaces.sqlite3'
        with sqlite3.connect(database) as connection:
            connection.execute('''CREATE TABLE profile_workspaces (
                id TEXT PRIMARY KEY, title TEXT NOT NULL, revision INTEGER NOT NULL,
                created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
                document_count INTEGER NOT NULL, snapshot_json TEXT NOT NULL)''')
            connection.execute('INSERT INTO profile_workspaces VALUES (?,?,?,?,?,?,?)',
                               ('a' * 32, 'Keep original', 7, '2026-11-14T00:00:00+00:00',
                                '2026-11-14T00:00:00+00:00', 0,
                                '{"profile_text":"  { unfinished 한글  "}'))
        job = self.source / 'jobs' / ('b' * 32)
        job.mkdir(parents=True)
        (job / 'job.json').write_bytes(b'{"status":"generating","request":{"width":47},"_private":"preserve"}')
        (job / 'partial-model.stl').write_bytes(b'incomplete bytes; preserve, do not certify')
        (job / 'model.py').write_bytes(b'raise SystemExit("must never execute a backup source")\n')
        (job / '.printer-agent.lock').write_bytes(b'nested regular data must be preserved')
        (self.source / 'notes.txt').write_bytes(b'unknown regular file\n')

    @staticmethod
    def bytes_in(root):
        return {path.relative_to(root).as_posix(): path.read_bytes()
                for path in root.rglob('*') if path.is_file()
                and path != root / '.printer-agent.lock'}

    def assert_no_staging(self):
        self.assertEqual([p.name for p in self.root.iterdir() if p.name.startswith('.printer-agent-')], [])

    def test_backup_inspection_and_restore_preserve_all_bytes_and_private_records(self):
        self.canonical_workspace()
        before = self.bytes_in(self.source)
        created = self.backup.create_backup(self.source, self.archive)
        self.assertEqual(created['status'], 'created')
        self.assertEqual(created['file_count'], 6)
        self.assertEqual(created['total_bytes'], sum(map(len, before.values())))
        self.assertEqual(created['archive_path'], str(self.archive))
        self.assertEqual(created['archive_bytes'], self.archive.stat().st_size)
        self.assertEqual(created['archive_sha256'], digest(self.archive.read_bytes()))
        inspected = self.backup.inspect_backup(self.archive)
        self.assertEqual(inspected, {**created, 'status': 'verified'})
        self.assertEqual(self.bytes_in(self.source), before)
        with zipfile.ZipFile(self.archive) as archive:
            manifest = json.loads(archive.read('manifest.json'))
            self.assertEqual(manifest['format'], '3d-printer-agent-backup')
            self.assertEqual(manifest['version'], 1)
            self.assertEqual({item['path'] for item in manifest['files']}, set(before))
            self.assertNotIn('data/.printer-agent.lock', archive.namelist())
            for name, content in before.items():
                self.assertEqual(archive.read('data/' + name), content)
        restored = self.backup.restore_backup(self.archive, self.destination)
        self.assertEqual(restored, {**inspected, 'status': 'restored', 'data_dir': str(self.destination)})
        self.assertEqual(self.bytes_in(self.destination), before)
        self.assertFalse((self.destination / '.printer-agent.lock').exists())
        self.assertEqual(self.bytes_in(self.source), before)
        self.assert_no_staging()

    def test_cached_windows_directory_ids_do_not_reject_unchanged_source(self):
        self.canonical_workspace()
        before = self.bytes_in(self.source)
        real_scandir = os.scandir

        class WindowsDirectoryEntry:
            def __init__(self, entry):
                self.entry = entry
                self.path = entry.path

            def stat(self, *, follow_symlinks=True):
                metadata = self.entry.stat(follow_symlinks=follow_symlinks)
                fields = {name: getattr(metadata, name) for name in dir(metadata) if name.startswith('st_')}
                # Python documents these three DirEntry.stat values as zero
                # on Windows; Path.lstat still returns real file identity.
                fields.update(st_ino=0, st_dev=0, st_nlink=0)
                return SimpleNamespace(**fields)

        @contextmanager
        def windows_scandir(directory):
            with real_scandir(directory) as entries:
                yield (WindowsDirectoryEntry(entry) for entry in entries)

        with patch.object(self.backup.os, 'scandir', windows_scandir):
            created = self.backup.create_backup(self.source, self.archive)
        self.assertEqual(created['status'], 'created')
        self.backup.restore_backup(self.archive, self.destination)
        self.assertEqual(self.bytes_in(self.source), before)
        self.assertEqual(self.bytes_in(self.destination), before)
        self.assert_no_staging()

    def test_windows_opened_identity_accepts_common_birthtime_and_inferred_execute_bits(self):
        for legacy in (False, True):
            for name in ('history.sqlite3', 'saved-helper.CMD', '.CMD', '.exe'):
                with self.subTest(name=name, legacy=legacy):
                    path = self.source / name
                    path.write_bytes(b'original saved bytes')
                    with windows_path_and_descriptor_metadata(legacy_creation_time=legacy):
                        with self.backup._regular_file(path) as (source, _):
                            self.assertEqual(source.read(), b'original saved bytes')

    def test_windows_descriptor_change_time_still_detects_mutation_after_open(self):
        path = self.source / 'history.sqlite3'
        path.write_bytes(b'original saved bytes')
        observed = None
        with windows_path_and_descriptor_metadata(descriptor_changes=True):
            with self.assertRaises(self.backup.BackupError):
                with self.backup._regular_file(path) as (source, _):
                    observed = source.read()
        self.assertEqual(observed, b'original saved bytes')
        self.assertEqual(path.read_bytes(), b'original saved bytes')

    def test_live_owner_rejects_backup_before_creating_output(self):
        self.canonical_workspace()
        before = self.bytes_in(self.source)
        with DataDirectoryLease(self.source), self.assertRaises(DataDirectoryInUse):
            self.backup.create_backup(self.source, self.archive)
        self.assertFalse(self.archive.exists())
        self.assertEqual(self.bytes_in(self.source), before)
        self.assert_no_staging()

    def test_unknown_and_missing_sources_do_not_become_new_workspaces(self):
        for root in (self.source, self.root / 'missing'):
            with self.subTest(root=root), self.assertRaises(self.backup.BackupError):
                self.backup.create_backup(root, self.archive)
        self.assertFalse((self.root / 'missing').exists())
        self.assertFalse(self.archive.exists())
        self.assert_no_staging()

    def test_output_inside_source_and_existing_output_are_preserved(self):
        self.canonical_workspace()
        existing = self.root / 'existing.zip'
        existing.write_bytes(b'keep existing backup')
        for output in (self.source / 'backup.zip', existing):
            with self.subTest(output=output), self.assertRaises(self.backup.BackupError):
                self.backup.create_backup(self.source, output)
        self.assertEqual(existing.read_bytes(), b'keep existing backup')
        self.assertFalse((self.source / 'backup.zip').exists())
        self.assert_no_staging()

    def test_corrupt_canonical_database_can_be_preserved_but_not_restored_as_compatible(self):
        (self.source / 'profile-workspaces.sqlite3').write_bytes(b'corrupt canonical database')
        self.backup.create_backup(self.source, self.archive)
        self.assertEqual(self.backup.inspect_backup(self.archive)['status'], 'verified')
        with self.assertRaises(RuntimeError):
            self.backup.restore_backup(self.archive, self.destination)
        self.assertFalse(self.destination.exists())
        self.assertEqual((self.source / 'profile-workspaces.sqlite3').read_bytes(), b'corrupt canonical database')
        self.assert_no_staging()

    def test_derived_index_corruption_is_preserved_without_repair_during_restore(self):
        content = b'physically corrupt derived history index'
        (self.source / 'history.sqlite3').write_bytes(content)
        self.backup.create_backup(self.source, self.archive)
        self.backup.restore_backup(self.archive, self.destination)
        self.assertEqual((self.destination / 'history.sqlite3').read_bytes(), content)
        self.assertEqual(list(self.destination.iterdir()), [self.destination / 'history.sqlite3'])

    def test_existing_restore_destinations_remain_untouched_including_empty_directories(self):
        self.canonical_workspace()
        self.backup.create_backup(self.source, self.archive)
        for kind in ('file', 'empty', 'populated'):
            target = self.root / kind
            if kind == 'file':
                target.write_bytes(b'sentinel')
            else:
                target.mkdir()
                if kind == 'populated':
                    (target / 'sentinel').write_bytes(b'keep')
            before = target.read_bytes() if target.is_file() else self.bytes_in(target)
            with self.subTest(kind=kind), self.assertRaises(self.backup.BackupError):
                self.backup.restore_backup(self.archive, target)
            self.assertEqual(target.read_bytes() if target.is_file() else self.bytes_in(target), before)
        self.assert_no_staging()

    def test_late_destination_creation_cannot_be_overwritten_at_publication(self):
        self.canonical_workspace()
        self.backup.create_backup(self.source, self.archive)
        publish = self.backup._publish_no_replace
        def race(source, target):
            target.mkdir()
            return publish(source, target)
        with patch.object(self.backup, '_publish_no_replace', side_effect=race), self.assertRaises(self.backup.BackupError):
            self.backup.restore_backup(self.archive, self.destination)
        self.assertTrue(self.destination.is_dir())
        self.assertEqual(list(self.destination.iterdir()), [])
        self.assert_no_staging()

    def test_late_archive_creation_cannot_be_overwritten_at_publication(self):
        self.canonical_workspace()
        publish = self.backup._publish_no_replace
        def race(source, target):
            target.write_bytes(b'other writer archive')
            return publish(source, target)
        with patch.object(self.backup, '_publish_no_replace', side_effect=race), self.assertRaises(self.backup.BackupError):
            self.backup.create_backup(self.source, self.archive)
        self.assertEqual(self.archive.read_bytes(), b'other writer archive')
        self.assert_no_staging()

    def test_hash_mismatch_fails_inspection_and_leaves_no_restored_directory(self):
        files = {'history.sqlite3': b'original index'}
        manifest = fixture_manifest(files)
        write_archive(self.archive, {'history.sqlite3': b'altered index!'}, manifest=manifest)
        for operation in (lambda: self.backup.inspect_backup(self.archive),
                          lambda: self.backup.restore_backup(self.archive, self.destination)):
            with self.assertRaises(self.backup.BackupError):
                operation()
        self.assertFalse(self.destination.exists())
        self.assert_no_staging()

    def test_missing_extra_and_duplicate_members_are_rejected(self):
        files = {'history.sqlite3': b'index'}
        variants = [({}, fixture_manifest(files), None),
                    (files, fixture_manifest(files), [('unlisted', b'extra')]),
                    (files, fixture_manifest(files), [('data/extra', b'extra')]),
                    (files, fixture_manifest(files), [('data/history.sqlite3', b'index')])]
        for members, manifest, extra in variants:
            with self.subTest(extra=extra), warnings.catch_warnings():
                warnings.simplefilter('ignore', UserWarning)
                write_archive(self.archive, members, manifest=manifest, extra=extra)
                with self.assertRaises(self.backup.BackupError):
                    self.backup.inspect_backup(self.archive)

    def test_unlisted_local_file_data_cannot_hide_outside_central_inventory(self):
        write_archive(self.archive, {'history.sqlite3': b'index'})
        with zipfile.ZipFile(self.archive) as archive:
            central = archive.start_dir
        hidden = io.BytesIO()
        with zipfile.ZipFile(hidden, 'w') as archive:
            archive.writestr('unlisted-local-entry', b'undeclared bytes')
        hidden_local = hidden.getvalue()[:archive.start_dir]
        content = self.archive.read_bytes()
        changed = bytearray(content[:central] + hidden_local + content[central:])
        ending = changed.rfind(b'PK\x05\x06')
        struct.pack_into('<L', changed, ending + 16, central + len(hidden_local))
        self.archive.write_bytes(changed)
        with zipfile.ZipFile(self.archive) as archive:
            self.assertNotIn('unlisted-local-entry', archive.namelist())
        with self.assertRaises(self.backup.BackupError):
            self.backup.inspect_backup(self.archive)

    def test_data_descriptors_from_streamed_zip_writers_are_verified(self):
        class Unseekable(io.BytesIO):
            def seek(self, *args):
                raise OSError('A streamed writer cannot seek')
        files = {'history.sqlite3': b'index'}
        for zip64 in (False, True):
            with self.subTest(zip64=zip64):
                stream = Unseekable()
                with zipfile.ZipFile(stream, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
                    archive.writestr('manifest.json', json.dumps(fixture_manifest(files)))
                    with archive.open('data/history.sqlite3', 'w', force_zip64=zip64) as output:
                        output.write(b'index')
                self.archive.write_bytes(stream.getvalue())
                self.assertEqual(self.backup.inspect_backup(self.archive)['file_count'], 1)

    def test_unsafe_and_nonportable_names_never_escape_staging(self):
        names = ['../outside', '/absolute', 'C:/drive', 'a\\b', 'a//b', 'a/./b',
                 'a/../b', 'NUL', 'con.txt', 'a/COM1.data', 'LPT9', 'COM¹.txt',
                 'a/trailing.', 'a/trailing ', 'a:name', 'a\x00hidden', 'a\x1bcontrol']
        for name in names:
            with self.subTest(name=name):
                write_archive(self.archive, {name: b'x'})
                with self.assertRaises(self.backup.BackupError):
                    self.backup.restore_backup(self.archive, self.destination)
                self.assertFalse(self.destination.exists())
                self.assertFalse((self.root / 'outside').exists())
                self.assert_no_staging()

    def test_casefold_unicode_and_file_directory_collisions_are_rejected(self):
        for names in [('A/x', 'a/y'), ('é/x', 'e\u0301/y'), ('one', 'one/child'), ('file', 'FILE')]:
            with self.subTest(names=names):
                write_archive(self.archive, dict.fromkeys(names, b'value'))
                with self.assertRaises(self.backup.BackupError):
                    self.backup.inspect_backup(self.archive)

    def test_symlink_and_special_zip_entries_are_rejected(self):
        files = {'history.sqlite3': b'payload'}
        for mode in (stat.S_IFLNK | 0o777, stat.S_IFIFO | 0o600, stat.S_IFDIR | 0o700):
            with self.subTest(mode=mode), zipfile.ZipFile(self.archive, 'w') as archive:
                archive.writestr('manifest.json', json.dumps(fixture_manifest(files)))
                info = zipfile.ZipInfo('data/history.sqlite3')
                info.create_system = 3
                info.external_attr = mode << 16
                archive.writestr(info, b'payload')
            with self.assertRaises(self.backup.BackupError):
                self.backup.inspect_backup(self.archive)

    def test_unrecognized_format_and_duplicate_nonfinite_metadata_are_rejected(self):
        files = {'history.sqlite3': b'index'}
        base = fixture_manifest(files)
        variants = [json.dumps({**base, 'version': True}), json.dumps({**base, 'format': 'other'}),
                    json.dumps({**base, 'file_count': True}), json.dumps({**base, 'total_bytes': float('nan')}),
                    json.dumps(base)[:-1] + ',"version":1}', json.dumps({**base, 'created_at': 'not a timestamp'}),
                    json.dumps({**base, 'files': [{**base['files'][0], 'bytes': True}]})]
        for text in variants:
            with self.subTest(text=text[:100]):
                write_archive(self.archive, files, manifest_text=text)
                with self.assertRaises(self.backup.BackupError):
                    self.backup.inspect_backup(self.archive)

    def test_truncated_and_unsupported_compression_archives_are_rejected(self):
        write_archive(self.archive, {'history.sqlite3': b'index'})
        content = self.archive.read_bytes()
        for broken in (b'', content[:25], content[:-3]):
            self.archive.write_bytes(broken)
            with self.assertRaises(self.backup.BackupError):
                self.backup.inspect_backup(self.archive)
        write_archive(self.archive, {'history.sqlite3': b'index'}, compression=zipfile.ZIP_BZIP2)
        with self.assertRaises(self.backup.BackupError):
            self.backup.inspect_backup(self.archive)

    def test_actual_deflate_bytes_cannot_hide_behind_smaller_matching_headers(self):
        visible = b'visible index'
        write_archive(self.archive, {'history.sqlite3': visible + b'hidden bytes' * 10000},
                      manifest=fixture_manifest({'history.sqlite3': visible}))
        edit_member_headers(self.archive, 'data/history.sqlite3', expanded=len(visible), crc=zlib.crc32(visible))
        # The normal ZIP reader accepts the claimed prefix. Backup inspection
        # must count the complete DEFLATE stream instead of inheriting that gap.
        with zipfile.ZipFile(self.archive) as archive:
            self.assertEqual(archive.read('data/history.sqlite3'), visible)
        for operation in (lambda: self.backup.inspect_backup(self.archive),
                          lambda: self.backup.restore_backup(self.archive, self.destination)):
            with self.assertRaises(self.backup.BackupError):
                operation()
        self.assertFalse(self.destination.exists())
        self.assert_no_staging()

    def test_declared_limits_apply_at_boundary_without_allocating_large_fixtures(self):
        files = {'history.sqlite3': b'abcd', 'notes': b'efgh'}
        write_archive(self.archive, files)
        for setting, allowed in (('MAX_FILES', 2), ('MAX_FILE_BYTES', 4), ('MAX_TOTAL_BYTES', 8)):
            with self.subTest(setting=setting), patch.object(self.backup, setting, allowed):
                self.assertEqual(self.backup.inspect_backup(self.archive)['total_bytes'], 8)
            with patch.object(self.backup, setting, allowed - 1), self.assertRaises(self.backup.BackupError):
                self.backup.restore_backup(self.archive, self.destination)
            self.assertFalse(self.destination.exists())
            self.assert_no_staging()
        with zipfile.ZipFile(self.archive) as archive:
            manifest_bytes = archive.getinfo('manifest.json').file_size
        with patch.object(self.backup, 'MAX_MANIFEST_BYTES', manifest_bytes):
            self.assertEqual(self.backup.inspect_backup(self.archive)['file_count'], 2)
        with patch.object(self.backup, 'MAX_MANIFEST_BYTES', manifest_bytes - 1), self.assertRaises(self.backup.BackupError):
            self.backup.inspect_backup(self.archive)

    def test_creation_limit_failures_preserve_source_and_remove_temporary_files(self):
        (self.source / 'history.sqlite3').write_bytes(b'abcd')
        (self.source / 'notes').write_bytes(b'efgh')
        before = self.bytes_in(self.source)
        for setting, limit in (('MAX_FILES', 1), ('MAX_FILE_BYTES', 3),
                               ('MAX_TOTAL_BYTES', 7), ('MAX_MANIFEST_BYTES', 100)):
            with self.subTest(setting=setting), patch.object(self.backup, setting, limit):
                with self.assertRaises(self.backup.BackupError):
                    self.backup.create_backup(self.source, self.archive)
            self.assertEqual(self.bytes_in(self.source), before)
            self.assertFalse(self.archive.exists())
            self.assert_no_staging()

    def test_crc_damage_and_encryption_flags_are_rejected(self):
        for modification in ({'crc': 0}, {'flags': 1}):
            with self.subTest(modification=modification):
                write_archive(self.archive, {'history.sqlite3': b'index'})
                edit_member_headers(self.archive, 'data/history.sqlite3', **modification)
                with self.assertRaises(self.backup.BackupError):
                    self.backup.inspect_backup(self.archive)

    def test_truncated_local_zip64_sizes_raise_actionable_backup_error(self):
        files = {'history.sqlite3': b'index'}
        with zipfile.ZipFile(self.archive, 'w') as archive:
            archive.writestr('manifest.json', json.dumps(fixture_manifest(files)))
            with archive.open('data/history.sqlite3', 'w', force_zip64=True) as output:
                output.write(b'index')
        self.assertEqual(self.backup.inspect_backup(self.archive)['file_count'], 1)
        with zipfile.ZipFile(self.archive) as archive:
            info = archive.getinfo('data/history.sqlite3')
        content = bytearray(self.archive.read_bytes())
        extra = info.header_offset + 30 + len(info.filename.encode('utf-8'))
        # Keep all offsets/bytes, but turn the ZIP64 data into an empty field.
        struct.pack_into('<H', content, extra + 2, 0)
        self.archive.write_bytes(content)
        with self.assertRaises(self.backup.BackupError):
            self.backup.inspect_backup(self.archive)

    def test_source_modification_during_copy_prevents_publication(self):
        (self.source / 'history.sqlite3').write_bytes(b'original index')
        regular_file = self.backup._regular_file
        @contextmanager
        def changed_after_read(path, expected=None):
            with regular_file(path, expected) as result:
                yield result
                if path == self.source / 'history.sqlite3':
                    path.write_bytes(b'another program wrote a changed index')
        with patch.object(self.backup, '_regular_file', changed_after_read):
            with self.assertRaises(self.backup.BackupError):
                self.backup.create_backup(self.source, self.archive)
        self.assertFalse(self.archive.exists())
        self.assertEqual((self.source / 'history.sqlite3').read_bytes(), b'another program wrote a changed index')
        self.assert_no_staging()

    def test_publication_io_failure_removes_only_owned_staging(self):
        (self.source / 'history.sqlite3').write_bytes(b'opaque derived index')
        with patch.object(self.backup, '_publish_no_replace', side_effect=OSError(errno.ENOSPC, 'fixture full disk')):
            with self.assertRaises(self.backup.BackupError):
                self.backup.create_backup(self.source, self.archive)
        self.assertFalse(self.archive.exists())
        self.assert_no_staging()
        self.backup.create_backup(self.source, self.archive)
        before = self.archive.read_bytes()
        with patch.object(self.backup, '_publish_no_replace', side_effect=OSError(errno.ENOSPC, 'fixture full disk')):
            with self.assertRaises(self.backup.BackupError):
                self.backup.restore_backup(self.archive, self.destination)
        self.assertEqual(self.archive.read_bytes(), before)
        self.assertFalse(self.destination.exists())
        self.assert_no_staging()

    def test_existing_dangling_destination_symlink_survives_restore(self):
        write_archive(self.archive, {'history.sqlite3': b'index'})
        missing = self.root / 'not-created'
        try:
            self.destination.symlink_to(missing, target_is_directory=True)
        except (OSError, NotImplementedError):
            self.skipTest('This filesystem cannot create a test symlink.')
        with self.assertRaises(self.backup.BackupError):
            self.backup.restore_backup(self.archive, self.destination)
        self.assertTrue(self.destination.is_symlink())
        self.assertEqual(self.destination.readlink(), missing)
        self.assertFalse(missing.exists())
        self.assert_no_staging()

    def test_backup_creation_rejects_source_symlinks_without_reading_the_target(self):
        self.canonical_workspace()
        outside = self.root / 'outside'
        outside.write_bytes(b'outside private bytes')
        link = self.source / 'linked'
        try:
            link.symlink_to(outside)
        except (OSError, NotImplementedError):
            self.skipTest('This filesystem cannot create a test symlink.')
        with self.assertRaises(self.backup.BackupError):
            self.backup.create_backup(self.source, self.archive)
        self.assertFalse(self.archive.exists())
        self.assertEqual(outside.read_bytes(), b'outside private bytes')
        self.assert_no_staging()

    def test_inspection_and_creation_do_not_require_cad_web_or_open_databases(self):
        (self.source / 'history.sqlite3').write_bytes(b'preserve opaque corruption')
        script = '''
import builtins,json,sys
from pathlib import Path
original = builtins.__import__
def guarded(name,*args,**kwargs):
    if name.split('.')[0] in {'cadquery','fastapi','uvicorn','pydantic','httpx','sqlite3'}:
        raise AssertionError('Unexpected dependency: '+name)
    return original(name,*args,**kwargs)
builtins.__import__ = guarded
from print_agent.backup import create_backup,inspect_backup
created=create_backup(Path(sys.argv[1]),Path(sys.argv[2]))
verified=inspect_backup(Path(sys.argv[2]))
assert created['status']=='created' and verified['status']=='verified'
print(json.dumps(verified))
'''
        completed = subprocess.run([sys.executable, '-c', script, str(self.source), str(self.archive)],
                                   capture_output=True, text=True, timeout=20)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(json.loads(completed.stdout)['file_count'], 1)


if __name__ == '__main__':
    unittest.main()
