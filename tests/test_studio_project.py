import hashlib
import io
import json
from pathlib import Path
import struct
import stat
import unittest
import zipfile
from unittest.mock import patch
from xml.etree import ElementTree as ET

from tests.studio_project_fixtures import project_bytes
from print_agent.studio_project import inspect_studio_project, build_project_3mf, public_snapshot


class StudioProjectTests(unittest.TestCase):
    def inspect(self, **kwargs):
        return inspect_studio_project('source.3mf', project_bytes(**kwargs))

    def test_inspection_preserves_exact_settings_and_public_boundary(self):
        source = project_bytes(settings_overrides={'unknown_custom_setting': [['original', '값']]})
        snapshot = inspect_studio_project('source.3mf', source)
        self.assertTrue(snapshot['supported'], snapshot['issues'])
        self.assertEqual(snapshot['source']['sha256'], hashlib.sha256(source).hexdigest())
        with zipfile.ZipFile(io.BytesIO(source)) as archive:
            self.assertEqual(snapshot['settings_text'].encode(), archive.read('Metadata/project_settings.config'))
        self.assertGreaterEqual(len(snapshot['expected_settings']), 30)
        self.assertNotIn('settings_text', public_snapshot(snapshot))
        self.assertNotIn('expected_settings', public_snapshot(snapshot))

    def test_unsupported_valid_projects(self):
        for changes in ({'version':'02.10.00.00'}, {'filament_settings_id':['a','b']},
                        {'nozzle_diameter':['0.4','0.6']}, {'printer_extruder_id':['1','2']},
                        {'hot_plate_temp':['0']}, {'printer_technology':'SLA'}):
            with self.subTest(changes=changes):
                snapshot = self.inspect(settings_overrides=changes)
                self.assertFalse(snapshot['supported'])
                self.assertTrue(snapshot['issues'])

    def test_invalid_json_and_xml(self):
        for text in ('{"a":1,"a":2}', '{"a":NaN}', '{"a":1e999}', '{"a":'+ '['*40+'0'+']'*40+'}', '[]'):
            with self.subTest(text=text), self.assertRaises(ValueError):
                self.inspect(settings_text=text)
        for xml in (b'<model', b'<!DOCTYPE model [<!ENTITY x "bad">]><model/>', b'<model/>'):
            with self.subTest(xml=xml), self.assertRaises(ValueError):
                self.inspect(root_xml=xml)

    def test_host_program_is_not_supported(self):
        self.assertFalse(self.inspect(settings_overrides={'post_process':['touch bad']})['supported'])

    def test_native_loader_cannot_silently_skip_numeric_object_or_mixed_array_settings(self):
        for field, value in (('layer_height', 0.31), ('nozzle_temperature', [231]),
                             ('unknown_custom_setting', {'original': 'value'}),
                             ('unknown_custom_setting', ['value', ['nested']]),
                             ('unknown_custom_setting', True), ('unknown_custom_setting', [[['too deep']]])):
            with self.subTest(field=field, value=value):
                snapshot = self.inspect(settings_overrides={field: value})
                self.assertFalse(snapshot['supported'])
                self.assertTrue(any(item['code'] == 'invalid_native_representation' and item['field'] == field
                                    for item in snapshot['issues']))
                self.assertEqual(json.loads(snapshot['settings_text'])[field], value)

    def test_project_specific_native_identity_is_required(self):
        snapshot = self.inspect(settings_overrides={'name': 'filament preset'})
        self.assertFalse(snapshot['supported'])
        self.assertTrue(any(item['code'] == 'unsupported_project' for item in snapshot['issues']))

    def test_archive_boundaries_and_ignored_member_crc(self):
        original = project_bytes(extra_members={'ignored.bin':b'ignored'})
        for content in (original+b'hidden', b'hidden'+original,
                        project_bytes(extra_members={'../escape':b'x'}),
                        project_bytes(extra_members={'folder/':b'not empty'})):
            with self.assertRaises(ValueError):
                inspect_studio_project('source.3mf', content)
        corrupt = bytearray(original)
        with zipfile.ZipFile(io.BytesIO(original)) as archive:
            info = archive.getinfo('ignored.bin')
            offset = info.header_offset
            start = offset + 30 + len(info.filename.encode())
            corrupt[start] ^= 1
        with self.assertRaises(ValueError):
            inspect_studio_project('source.3mf', bytes(corrupt))

    def test_forged_short_member_cannot_hide_expanded_bytes(self):
        import zlib
        original = project_bytes(extra_members={'ignored.bin':b'A'*10000})
        forged = bytearray(original)
        with zipfile.ZipFile(io.BytesIO(original)) as archive:
            info = archive.getinfo('ignored.bin')
        struct.pack_into('<I', forged, info.header_offset+14, zlib.crc32(b'A'))
        struct.pack_into('<I', forged, info.header_offset+22, 1)
        cursor=forged.find(b'PK\x01\x02')
        while cursor >= 0:
            name_len, extra_len, comment_len = struct.unpack_from('<3H', forged, cursor+28)
            if forged[cursor+46:cursor+46+name_len] == b'ignored.bin':
                struct.pack_into('<I', forged, cursor+16, zlib.crc32(b'A'))
                struct.pack_into('<I', forged, cursor+24, 1)
                break
            cursor=forged.find(b'PK\x01\x02',cursor+46+name_len+extra_len+comment_len)
        with self.assertRaises(ValueError):
            inspect_studio_project('source.3mf',bytes(forged))

    def test_composition_is_deterministic_and_preserves_only_current_geometry(self):
        model = (Path(__file__).parents[1]/'examples/cable_comb/model.3mf').read_bytes()
        snapshot = self.inspect(extra_members={'Metadata/custom_gcode_per_layer.xml':b'NEVER COPY', 'plate_1.gcode':b'OLD'})
        derived, receipt = build_project_3mf(model,snapshot)
        self.assertEqual((derived,receipt), build_project_3mf(model,snapshot))
        self.assertEqual(receipt['project_sha256'],hashlib.sha256(derived).hexdigest())
        self.assertTrue(receipt['geometry']['preserved'])
        with zipfile.ZipFile(io.BytesIO(derived)) as archive:
            self.assertEqual(archive.read('Metadata/project_settings.config'),snapshot['settings_text'].encode())
            self.assertNotIn('plate_1.gcode',archive.namelist())
            self.assertNotIn('Metadata/custom_gcode_per_layer.xml',archive.namelist())
            self.assertIn(snapshot['source']['sha256'].encode(),archive.read('3D/3dmodel.model'))

    def test_changed_internal_settings_cannot_compose(self):
        snapshot=self.inspect()
        snapshot['settings_text'] += ' '
        model=(Path(__file__).parents[1]/'examples/cable_comb/model.3mf').read_bytes()
        with self.assertRaises(ValueError):
            build_project_3mf(model,snapshot)

    def test_composition_independent_of_process_namespace_registration(self):
        from tests.studio_project_fixtures import CORE
        model=(Path(__file__).parents[1]/'examples/cable_comb/model.3mf').read_bytes()
        snapshot=self.inspect()
        previous=dict(ET._namespace_map)
        try:
            ET.register_namespace('one',CORE)
            first=build_project_3mf(model,snapshot)
            ET.register_namespace('two',CORE)
            second=build_project_3mf(model,snapshot)
        finally:
            ET._namespace_map.clear(); ET._namespace_map.update(previous)
        self.assertEqual(hashlib.sha256(first[0]).hexdigest(),hashlib.sha256(second[0]).hexdigest())
        self.assertEqual(first[1],second[1])

    def test_explicit_size_and_inventory_budgets(self):
        source=project_bytes(extra_members={'ignored':b'X'*100})
        for constant,limit in (('MAX_ARCHIVE_BYTES',len(source)-1),('MAX_EXPANDED_BYTES',100),
                               ('MAX_ENTRIES',2),('MAX_SETTINGS_BYTES',10),('MAX_MODEL_XML_BYTES',10)):
            with self.subTest(constant=constant), patch('print_agent.studio_project.'+constant,limit), self.assertRaises(ValueError):
                inspect_studio_project('source.3mf',source)

    def test_duplicate_names_unsafe_types_and_unsupported_compression(self):
        for kind in ('duplicate','symlink','fifo','unsupported','encrypted'):
            stream=io.BytesIO(project_bytes())
            with zipfile.ZipFile(stream,'a') as archive:
                info=zipfile.ZipInfo('other.bin')
                info.compress_type=zipfile.ZIP_BZIP2 if kind=='unsupported' else zipfile.ZIP_STORED
                info.external_attr=((stat.S_IFLNK if kind=='symlink' else stat.S_IFIFO if kind=='fifo' else stat.S_IFREG)|0o600)<<16
                archive.writestr(info,b'content')
                if kind=='duplicate':
                    import warnings
                    with warnings.catch_warnings():
                        warnings.simplefilter('ignore'); archive.writestr('other.bin',b'duplicate')
            raw=bytearray(stream.getvalue())
            if kind=='encrypted':
                with zipfile.ZipFile(io.BytesIO(raw)) as archive: offset=archive.getinfo('other.bin').header_offset
                struct.pack_into('<H',raw,offset+6,1)
                index=raw.rfind(b'PK\x01\x02'); struct.pack_into('<H',raw,index+8,1)
            with self.subTest(kind=kind),self.assertRaises(ValueError):
                inspect_studio_project('source.3mf',bytes(raw))

    def test_missing_duplicate_and_foreign_producer(self):
        from tests.studio_project_fixtures import CORE
        for metadata in ('', '<metadata name="Application">Bambu</metadata>',
                         '<metadata name="Application">a</metadata><metadata name="Application">b</metadata><metadata name="BambuStudio:3mfVersion">1</metadata>'):
            with self.assertRaises(ValueError):
                self.inspect(root_xml=f'<model xmlns="{CORE}">{metadata}</model>'.encode())
        snapshot=self.inspect(application='Unrelated Application')
        self.assertFalse(snapshot['supported'])
        model=(Path(__file__).parents[1]/'examples/cable_comb/model.3mf').read_bytes()
        with self.assertRaises(ValueError): build_project_3mf(model,snapshot)

    def test_hidden_local_member_is_rejected(self):
        source=bytearray(project_bytes(extra_members={'ignored.bin':b'payload'}))
        start=source.rfind(b'PK\x01\x02'); end=source.rfind(b'PK\x05\x06')
        length=end-start
        del source[start:end]
        end=start
        struct.pack_into('<H',source,end+8,2); struct.pack_into('<H',source,end+10,2)
        size=struct.unpack_from('<I',source,end+12)[0]
        struct.pack_into('<I',source,end+12,size-length)
        with self.assertRaises(ValueError): inspect_studio_project('source.3mf',bytes(source))

    def test_extra_or_transformed_geometry_is_not_supported_generated_cad(self):
        from tests.studio_project_fixtures import CORE
        model=(Path(__file__).parents[1]/'examples/cable_comb/model.3mf').read_bytes()
        for change in ('extra_mesh','extra_build','wrapper_transform','extra_resources','external_relationship'):
            with zipfile.ZipFile(io.BytesIO(model)) as archive: payload={name:archive.read(name) for name in archive.namelist()}
            root=ET.fromstring(payload['3D/3dmodel.model']); q=lambda n:'{'+CORE+'}'+n
            objects=root.findall(q('resources')+'/'+q('object'))
            if change=='extra_mesh': objects[1].append(ET.fromstring(ET.tostring(objects[0].find(q('mesh')))))
            if change=='extra_build': root.find(q('build')).append(ET.Element(q('item'),{'objectid':'1'}))
            if change=='wrapper_transform': objects[1].find(q('components')+'/'+q('component')).set('transform','1 0 0 0 1 0 0 0 1 10 0 0')
            if change=='extra_resources': root.append(ET.fromstring(ET.tostring(root.find(q('resources')))))
            if change=='external_relationship': payload['_rels/.rels']=b'<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="r1" Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel" Target="https://example.com/model" TargetMode="External"/></Relationships>'
            payload['3D/3dmodel.model']=ET.tostring(root)
            stream=io.BytesIO()
            with zipfile.ZipFile(stream,'w') as archive:
                for name,content in payload.items(): archive.writestr(name,content)
            with self.subTest(change=change), self.assertRaises(ValueError):
                build_project_3mf(stream.getvalue(),self.inspect())
