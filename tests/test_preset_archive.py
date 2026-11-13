"""Original, source-derived ZIP fixtures; not captured GUI/native qualification.

Layouts follow BambuStudio 56a57d00a591360cf41bf21383915ee5bf357be5,
CreatePresetsDialog.cpp export methods. Values are synthetic test inputs only.
"""
from copy import deepcopy
import hashlib
import io
import json
import stat
import struct
import unittest
import warnings
import zipfile
import zlib

from print_agent.preset_archive import import_preset_archive


def preset(name='Synthetic child', **values):
    return {'name': name, 'version': '02.09.01.70', 'from': 'User',
            'filament_settings_id': [name], **values}


def raw_json(value):
    return (json.dumps(value, ensure_ascii=False, indent=2) + '\n').encode('utf-8')


def archive_bytes(entries, compression=zipfile.ZIP_DEFLATED):
    output = io.BytesIO()
    with warnings.catch_warnings():
        warnings.filterwarnings('ignore', message='Duplicate name:', category=UserWarning)
        with zipfile.ZipFile(output, 'w', compression=compression) as archive:
            for path, data in entries:
                archive.writestr(path, data if isinstance(data, bytes) else raw_json(data))
    return output.getvalue()


def filament_manifest(paths=None):
    return {'version': '', 'bundle_id': 'offline_synthetic_fixture',
            'bundle_type': 'filament config bundle', 'filament_name': 'Synthetic child',
            'filament_vendor': [{'vendor': 'Synthetic vendor', 'filament_path': paths or [
                'Synthetic vendor/Synthetic child.json']} ]}


class PresetArchiveTests(unittest.TestCase):
    def imported(self, filename, content):
        return import_preset_archive(filename, content)

    def test_filament_bundle_preserves_typeless_user_diff_and_exact_member_bytes(self):
        profile = preset(inherits='Missing system parent', nozzle_temperature=['215', 'nil'],
                         filament_extruder_variant=['Direct Drive Standard', 'Direct Drive High Flow'])
        raw = raw_json(profile)
        member = 'Synthetic vendor/Synthetic child.json'
        content = archive_bytes([(member, raw), ('bundle_structure.json', filament_manifest())])
        result = self.imported('my-filament.bbsflmt', content)
        self.assertEqual(result['schema_version'], 1)
        self.assertEqual(result['archive'], {'filename': 'my-filament.bbsflmt',
            'sha256': hashlib.sha256(content).hexdigest(), 'format': 'bbsflmt'})
        self.assertEqual(result['documents'], [{'filename': member, 'profile': profile,
            'draft_text': raw.decode('utf-8'), 'origin': {
                'type': 'bambu_preset_archive', 'archive_name': 'my-filament.bbsflmt',
                'archive_sha256': hashlib.sha256(content).hexdigest(),
                'member_path': member, 'member_sha256': hashlib.sha256(raw).hexdigest(),
            }}])
        self.assertEqual(result['ignored_members'], [])
        self.assertTrue(result['warnings'])
        self.assertNotIn('type', result['documents'][0]['profile'])
        self.assertNotIn('source', result['documents'][0]['profile'])
        self.assertNotIn('validation', result['documents'][0]['profile'])
        self.assertNotIn('bundle_id', json.dumps(result))

    def test_printer_bundle_selects_only_filament_and_reports_other_presets(self):
        manifest = {'version': 'network-library-fixture', 'bundle_id': 'account_fixture',
            'bundle_type': 'printer config bundle', 'printer_preset_name': 'Synthetic printer',
            'printer_config': ['printer/Printer.json'],
            'filament_config': ['filament/Child.json'], 'process_config': ['process/Process.json']}
        content = archive_bytes([
            ('bundle_structure.json', manifest), ('printer/Printer.json', {
                'name': 'Synthetic printer', 'printer_settings_id': 'Synthetic printer'}),
            ('filament/Child.json', preset()), ('process/Process.json', {
                'name': 'Synthetic process', 'print_settings_id': 'Synthetic process'}),
        ])
        result = self.imported('printer.bbscfg', content)
        self.assertEqual([item['filename'] for item in result['documents']], ['filament/Child.json'])
        self.assertEqual([item['path'] for item in result['ignored_members']],
                         ['printer/Printer.json', 'process/Process.json'])
        self.assertTrue(all(item['reason'] for item in result['ignored_members']))
        self.assertNotIn('account_fixture', json.dumps(result))
        self.assertNotIn('network-library-fixture', json.dumps(result))

    def test_plain_zip_accepts_explicit_and_native_filament_identity_without_manifest(self):
        content = archive_bytes([('Explicit.json', {'name': 'Explicit', 'type': 'filament'}),
            ('Native.json', preset('Native')), ('readme.txt', b'synthetic fixture'),
            ('notes.json', {'note': 'This is not a preset'})], zipfile.ZIP_STORED)
        result = self.imported('presets.ZIP', content)
        self.assertEqual([item['profile']['name'] for item in result['documents']], ['Explicit', 'Native'])
        self.assertEqual([item['path'] for item in result['ignored_members']], ['readme.txt', 'notes.json'])

    def test_conflicting_native_identity_is_not_silently_classified_as_filament(self):
        for profile in (preset(type='machine'), preset(printer_settings_id='Printer'),
                        {'name': 'Conflict', 'type': 'filament', 'print_settings_id': 'Process'}):
            with self.subTest(profile=profile), self.assertRaisesRegex(ValueError, '종류|충돌'):
                self.imported('conflict.zip', archive_bytes([('Conflict.json', profile)]))

    def test_bundle_requires_manifest_and_its_referenced_members(self):
        member = 'Synthetic vendor/Synthetic child.json'
        cases = [archive_bytes([(member, preset())]),
                 archive_bytes([('bundle_structure.json', filament_manifest())]),
                 archive_bytes([('bundle_structure.json', filament_manifest()),
                    (member, preset()), ('extra.json', preset('Unlisted'))])]
        for content in cases:
            with self.subTest(size=len(content)), self.assertRaisesRegex(ValueError, 'manifest|목록|bundle_structure|참조'):
                self.imported('incomplete.bbsflmt', content)

    def test_no_filament_is_an_actionable_error(self):
        with self.assertRaisesRegex(ValueError, '필라멘트'):
            self.imported('printer.zip', archive_bytes([('Printer.json', {
                'name': 'Printer', 'printer_settings_id': 'Printer'})]))

    def test_manifest_type_paths_and_categories_must_agree(self):
        member = 'Synthetic vendor/Synthetic child.json'
        original = filament_manifest()
        cases = []
        wrong_type = deepcopy(original)
        wrong_type['bundle_type'] = 'printer config bundle'
        cases.append((wrong_type, preset()))
        duplicate = deepcopy(original)
        duplicate['filament_vendor'][0]['filament_path'] *= 2
        cases.append((duplicate, preset()))
        wrong_vendor = deepcopy(original)
        wrong_vendor['filament_vendor'][0]['vendor'] = 'Another vendor'
        cases.append((wrong_vendor, preset()))
        cases.append((original, {'name': 'Machine', 'printer_settings_id': 'Machine'}))
        cases.append((original, {'name': 'Unknown'}))
        for manifest, profile in cases:
            with self.subTest(manifest=manifest, profile=profile), self.assertRaises(ValueError):
                self.imported('mismatch.bbsflmt', archive_bytes([
                    ('bundle_structure.json', manifest), (member, profile)]))

    def test_non_string_manifest_type_returns_a_value_error(self):
        for value in ([], {}, None, 123, True):
            manifest = filament_manifest()
            manifest['bundle_type'] = value
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.imported('bad-type.bbsflmt', archive_bytes([
                    ('bundle_structure.json', manifest),
                    ('Synthetic vendor/Synthetic child.json', preset())]))

    def test_zip_can_carry_a_recognized_bundle_manifest(self):
        content = archive_bytes([('bundle_structure.json', filament_manifest()),
            ('Synthetic vendor/Synthetic child.json', preset())])
        self.assertEqual(len(self.imported('renamed.zip', content)['documents']), 1)

    def test_safe_directory_entries_do_not_become_documents(self):
        content = archive_bytes([('Vendor/', b''), ('Vendor/Child.json', preset())])
        result = self.imported('nested.zip', content)
        self.assertEqual([item['filename'] for item in result['documents']], ['Vendor/Child.json'])
        self.assertEqual(result['ignored_members'], [])

    def test_unsafe_and_overlong_member_paths_are_rejected_even_when_ignored(self):
        for path in ('../notes.txt', '/notes.txt', 'C:/notes.txt', 'Vendor\\notes.txt',
                     './notes.txt', 'Vendor/../notes.txt', 'Vendor//notes.txt',
                     'Vendor/./notes.txt', 'bad\nname.txt', 'n' * 241):
            with self.subTest(path=path), self.assertRaisesRegex(ValueError, '경로|이름'):
                self.imported('unsafe.zip', archive_bytes([('Good.json', preset()), (path, b'ignored')]))

    def test_nul_names_and_duplicate_paths_are_rejected(self):
        nul = archive_bytes([('badXname.json', preset())]).replace(b'badXname.json', b'bad\x00name.json')
        duplicates = archive_bytes([('same.json', preset()), ('same.json', preset('Other'))])
        for content in (nul, duplicates):
            with self.subTest(size=len(content)), self.assertRaisesRegex(ValueError, '경로|이름|중복'):
                self.imported('unsafe.zip', content)

    def test_invalid_utf8_zip_filename_returns_a_value_error(self):
        content = archive_bytes([('é.json', preset())])
        damaged = content.replace('é.json'.encode('utf-8'), b'\xff\xa9.json')
        with self.assertRaises(ValueError):
            self.imported('bad-filename.zip', damaged)

    def test_links_and_nonregular_members_are_rejected(self):
        for mode in (stat.S_IFLNK, stat.S_IFIFO, stat.S_IFSOCK):
            info = zipfile.ZipInfo('link.txt')
            info.create_system = 3
            info.external_attr = (mode | 0o600) << 16
            with self.subTest(mode=mode), self.assertRaisesRegex(ValueError, '링크|일반 파일'):
                self.imported('links.zip', archive_bytes([('Good.json', preset()), (info, b'ignored')]))

    def test_encryption_and_unsupported_compression_are_rejected(self):
        encrypted = bytearray(archive_bytes([('Good.json', preset())], zipfile.ZIP_STORED))
        central = encrypted.index(b'PK\x01\x02')
        for offset in (6, central + 8):
            struct.pack_into('<H', encrypted, offset, struct.unpack_from('<H', encrypted, offset)[0] | 1)
        unsupported = archive_bytes([('Good.json', preset())], zipfile.ZIP_BZIP2)
        for content in (bytes(encrypted), unsupported):
            with self.subTest(size=len(content)), self.assertRaisesRegex(ValueError, '암호|압축'):
                self.imported('unsupported.zip', content)

    def test_crc_is_checked_for_ignored_members_too(self):
        content = archive_bytes([('Good.json', preset()), ('notes.txt', b'CRC_MARKER')], zipfile.ZIP_STORED)
        damaged = content.replace(b'CRC_MARKER', b'CRC_BROKEN')
        with self.assertRaisesRegex(ValueError, 'CRC|손상'):
            self.imported('damaged.zip', damaged)

    def test_forged_prefix_sizes_cannot_hide_expanded_bytes_or_change_member_receipts(self):
        raw = b'{"name":"Hidden bytes","type":"filament"}'
        for compression, padding in ((zipfile.ZIP_DEFLATED, 5 * 1024 * 1024),
                                     (zipfile.ZIP_DEFLATED, 100), (zipfile.ZIP_STORED, 100)):
            content = bytearray(archive_bytes([('Hidden.json', raw + b'X' * padding)], compression))
            central = content.index(b'PK\x01\x02')
            for offset in (14, central + 16):
                struct.pack_into('<I', content, offset, zlib.crc32(raw))
            for offset in (22, central + 24):
                struct.pack_into('<I', content, offset, len(raw))
            with self.subTest(compression=compression, padding=padding), self.assertRaises(ValueError):
                self.imported('forged.zip', bytes(content))

    def test_truncated_and_non_zip_input_return_value_errors(self):
        valid = archive_bytes([('Good.json', preset())])
        for content in (b'not a zip', valid[:-30], b''):
            with self.subTest(size=len(content)), self.assertRaises(ValueError):
                self.imported('bad.zip', content)

    def test_archive_name_and_input_types_are_bounded(self):
        content = archive_bytes([('Good.json', preset())])
        for filename in ('', 'x' * 237 + '.zip', '../presets.zip', 'bad\nname.zip', 'file.rar', None):
            with self.subTest(filename=filename), self.assertRaises(ValueError):
                self.imported(filename, content)
        with self.assertRaises(ValueError):
            self.imported('wrong.zip', 'not bytes')

    def test_invalid_json_values_are_rejected_before_any_documents_are_returned(self):
        bad_values = [b'[]', b'null', b'{"bad":', b'\xff',
            b'{"name":"Bad","type":"filament","value":NaN}',
            b'{"name":"Bad","type":"filament","value":Infinity}',
            b'{"name":"Bad","type":"filament","value":1e309}',
            b'{"name":"Bad","type":"filament","value":9007199254740993}',
            b'{"name":"Bad","type":"filament","value":"\\ud800"}',
            b'{"name":"First","name":"Second","type":"filament"}',
            b'{"name":"Bad","type":"filament","nested":' + b'[' * 66 + b'0' + b']' * 66 + b'}']
        for invalid in bad_values:
            with self.subTest(invalid=invalid[:90]), self.assertRaises(ValueError):
                self.imported('bad-json.zip', archive_bytes([('Good.json', preset()), ('Bad.json', invalid)]))

    def test_missing_or_unusable_preset_names_are_rejected(self):
        for name in (None, '', ' ', 123, 'n' * 257):
            profile = preset()
            if name is None:
                del profile['name']
            else:
                profile['name'] = name
            with self.subTest(name=name), self.assertRaisesRegex(ValueError, '이름|name'):
                self.imported('names.zip', archive_bytes([('Bad.json', profile)]))

    def test_compressed_archive_budget_is_applied_before_zip_parsing(self):
        with self.assertRaisesRegex(ValueError, '4 MiB'):
            self.imported('large.zip', b'0' * (4 * 1024 * 1024 + 1))

    def test_expanded_budget_includes_non_json_members(self):
        content = archive_bytes([('Good.json', preset()), ('ignored.bin', b'0' * (4 * 1024 * 1024))])
        with self.assertRaisesRegex(ValueError, '4 MiB'):
            self.imported('expanded.zip', content)

    def test_json_member_budget_applies_to_ignored_categories(self):
        content = archive_bytes([('Good.json', preset()), ('Printer.json', {
            'name': 'Printer', 'printer_settings_id': 'Printer', 'description': '0' * (2 * 1024 * 1024)})])
        with self.assertRaisesRegex(ValueError, '2 MiB'):
            self.imported('member.zip', content)

    def test_selected_document_budget_is_aggregate(self):
        content = archive_bytes([(f'{index}.json', preset(str(index), description='0' * (1100 * 1024)))
                                 for index in range(2)])
        with self.assertRaisesRegex(ValueError, '2 MiB'):
            self.imported('selected.zip', content)

    def test_filament_count_and_archive_entry_count_have_independent_limits(self):
        too_many_presets = archive_bytes([(f'{index}.json', preset(str(index))) for index in range(65)])
        with self.assertRaisesRegex(ValueError, '64'):
            self.imported('presets.zip', too_many_presets)
        too_many_entries = archive_bytes([('Good.json', preset())] + [(f'{index}.txt', b'') for index in range(256)])
        with self.assertRaisesRegex(ValueError, '256'):
            self.imported('entries.zip', too_many_entries)

    def test_maximum_filament_count_still_imports_in_archive_order(self):
        content = archive_bytes([(f'{index}.json', preset(str(index))) for index in range(64)])
        result = self.imported('many.zip', content)
        self.assertEqual([row['profile']['name'] for row in result['documents']], [str(i) for i in range(64)])


if __name__ == '__main__':
    unittest.main()
