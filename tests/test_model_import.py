"""Imported STL/3MF models: bounded parsing, mesh facts, ranked placements and unchanged originals."""
import base64
import hashlib
import io
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch
import zipfile

import cadquery as cq
from fastapi.testclient import TestClient

from print_agent import model_import
from print_agent.app import create_app

CORE = 'http://schemas.microsoft.com/3dmanufacturing/core/2015/02'
PRODUCTION = 'http://schemas.microsoft.com/3dmanufacturing/production/2015/06'


def t_shape():
    """A thin stem on the bed under a wide cap: as stored, the cap's underside overhangs."""
    stem = cq.Workplane('XY').box(10, 10, 30, centered=(True, True, False))
    cap = cq.Workplane('XY').box(60, 40, 5, centered=(True, True, False)).translate((0, 0, 30))
    return stem.union(cap).val()


def stl_bytes(shape, ascii=False):
    vertices, triangles = shape.tessellate(0.01, 0.1)
    points = [v.toTuple() for v in vertices]
    if ascii:
        lines = ['solid test']
        for a, b, c in triangles:
            lines += ['facet normal 0 0 0', 'outer loop'] + [f'vertex {x} {y} {z}' for x, y, z in (points[a], points[b], points[c])] + ['endloop', 'endfacet']
        return ('\n'.join(lines + ['endsolid test']) + '\n').encode('ascii')
    body = b''.join(struct.pack('<12fH', 0, 0, 0, *points[a], *points[b], *points[c], 0) for a, b, c in triangles)
    return b'\0' * 80 + struct.pack('<I', len(triangles)) + body


def cube_mesh(size):
    s = size
    v = [(0, 0, 0), (s, 0, 0), (s, s, 0), (0, s, 0), (0, 0, s), (s, 0, s), (s, s, s), (0, s, s)]
    f = [(0, 2, 1), (0, 3, 2), (4, 5, 6), (4, 6, 7), (0, 1, 5), (0, 5, 4), (1, 2, 6), (1, 6, 5), (2, 3, 7), (2, 7, 6), (3, 0, 4), (3, 4, 7)]
    vertices = ''.join(f'<vertex x="{x}" y="{y}" z="{z}"/>' for x, y, z in v)
    triangles = ''.join(f'<triangle v1="{a}" v2="{b}" v3="{c}"/>' for a, b, c in f)
    return f'<mesh><vertices>{vertices}</vertices><triangles>{triangles}</triangles></mesh>'


def studio_style_3mf(unit='millimeter'):
    """Root model with a component that points into another model file, as Bambu Studio writes."""
    part = (f'<?xml version="1.0"?><model unit="{unit}" xmlns="{CORE}"><resources>'
            f'<object id="1" type="model">{cube_mesh(10)}</object></resources><build/></model>')
    root = (f'<?xml version="1.0"?><model unit="{unit}" xmlns="{CORE}" xmlns:p="{PRODUCTION}"><resources>'
            '<object id="2" type="model"><components>'
            '<component p:path="/3D/Objects/object_1.model" objectid="1" transform="1 0 0 0 1 0 0 0 1 5 0 0"/>'
            '</components></object></resources>'
            '<build><item objectid="2" transform="2 0 0 0 1 0 0 0 1 0 0 0"/></build></model>')
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, 'w') as archive:
        archive.writestr('3D/3dmodel.model', root)
        archive.writestr('3D/Objects/object_1.model', part)
    return stream.getvalue()


class ParsingTests(unittest.TestCase):
    def test_binary_and_ascii_stl_give_the_same_closed_mesh(self):
        shape = t_shape()
        for content in (stl_bytes(shape), stl_bytes(shape, ascii=True)):
            result = model_import.analyse('t.stl', content)
            self.assertTrue(result['facts']['closed'])
            self.assertAlmostEqual(result['facts']['volume_mm3'], shape.Volume(), delta=1)

    def test_studio_components_transforms_and_units_are_followed(self):
        result = model_import.analyse('part.3mf', studio_style_3mf())
        original = result['orientations'][result['original_id']]
        self.assertEqual({k: round(v, 6) for k, v in original['size_mm'].items()}, {'x': 20.0, 'y': 10.0, 'z': 10.0})
        self.assertAlmostEqual(result['facts']['volume_mm3'], 2000.0, places=3)
        in_cm = model_import.analyse('part.3mf', studio_style_3mf('centimeter'))
        self.assertAlmostEqual(in_cm['orientations'][in_cm['original_id']]['size_mm']['x'], 200.0, places=6)
        in_m = model_import.analyse('part.3mf', studio_style_3mf('meter'))
        self.assertEqual(in_m['orientations'][in_m['original_id']]['review']['status'], 'needs_change')  # likely saved in the wrong unit

    def test_bounded_inputs_are_refused_before_measurement(self):
        cases = [('model.obj', b'x', 'STL 또는 3MF'), ('model.stl', b'', '비어'), ('model.stl', b'not a mesh', 'STL'),
                 ('model.3mf', b'not a zip', 'ZIP'), ('model.3mf', zipfile_bytes({'3D/other.model': '<x/>'}), '3dmodel.model'),
                 ('model.stl', b'solid x\nvertex 1 2 nan\nvertex 1 2 3\nvertex 3 4 5\nendsolid', 'STL')]
        for filename, content, words in cases:
            with self.subTest(filename=filename, words=words), self.assertRaisesRegex(model_import.ModelImportError, words):
                model_import.analyse(filename, content)
        with patch.object(model_import, 'MAX_TRIANGLES', 10), self.assertRaisesRegex(model_import.ModelImportError, '삼각형'):
            model_import.analyse('t.stl', stl_bytes(t_shape()))
        with self.assertRaisesRegex(model_import.ModelImportError, '참조'):
            model_import.analyse('part.3mf', zipfile_rewrite(studio_style_3mf(), '3D/3dmodel.model', lambda text: text.replace('object_1', 'object_9')))


def zipfile_bytes(entries):
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, 'w') as archive:
        for name, text in entries.items():
            archive.writestr(name, text)
    return stream.getvalue()


def zipfile_rewrite(content, name, change):
    source = zipfile.ZipFile(io.BytesIO(content))
    return zipfile_bytes({item: (change(source.read(item).decode()) if item == name else source.read(item).decode())
                          for item in source.namelist()})


class OrientationTests(unittest.TestCase):
    def test_overhanging_cap_is_recommended_upside_down_and_reads_back_without_overhang(self):
        result = model_import.analyse('t.stl', stl_bytes(t_shape()))
        best, original = result['orientations'][0], result['orientations'][result['original_id']]
        self.assertEqual(best['label'], '위아래 뒤집기')
        self.assertTrue(best['recommended'])
        self.assertLess(best['overhang_mm2'], 1)
        self.assertGreater(original['overhang_mm2'], 2000)
        self.assertEqual(original['review']['status'], 'needs_change')  # 1 cm² stem on the bed
        vertices, faces = result['_mesh']
        turned = model_import.three_mf(model_import.oriented_vertices(vertices, best['rotation']), faces)
        again = model_import.analyse('again.3mf', turned)
        placed = again['orientations'][again['original_id']]
        self.assertLess(placed['overhang_mm2'], 1)
        self.assertAlmostEqual(again['facts']['volume_mm3'], result['facts']['volume_mm3'], places=2)
        self.assertAlmostEqual(placed['size_mm']['z'], 35.0, places=4)

    def test_open_meshes_are_reported_not_repaired(self):
        open_cube = zipfile_bytes({'3D/3dmodel.model': cube_mesh_model(drop_last=True)})
        result = model_import.analyse('open.3mf', open_cube)
        self.assertFalse(result['facts']['closed'])
        self.assertIsNone(result['facts']['volume_mm3'])
        mesh = next(item for item in result['orientations'][0]['review']['items'] if item['id'] == 'mesh')
        self.assertEqual(mesh['status'], 'warn')


def cube_mesh_model(drop_last=False):
    mesh = cube_mesh(10)
    if drop_last:
        mesh = mesh.replace('<triangle v1="3" v2="4" v3="7"/>', '')
    return (f'<?xml version="1.0"?><model unit="millimeter" xmlns="{CORE}"><resources>'
            f'<object id="1" type="model">{mesh}</object></resources><build><item objectid="1"/></build></model>')


class ImportApiTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.client = TestClient(create_app(self.root, test_mode=True))
        self.headers = {'X-Session-Token': self.client.get('/api/bootstrap').json()['session_token']}

    def tearDown(self):
        self.client.close()
        self.temporary.cleanup()

    def upload(self, filename, content):
        return self.client.post('/api/imports', headers=self.headers,
                                json={'filename': filename, 'content_base64': base64.b64encode(content).decode()})

    def test_import_keeps_the_original_and_downloads_a_placed_copy(self):
        content = stl_bytes(t_shape())
        response = self.upload('rocket stand.stl', content)
        self.assertEqual(response.status_code, 201, response.text)
        body = response.json()
        self.assertEqual((body['format'], body['bytes'], body['sha256']), ('stl', len(content), hashlib.sha256(content).hexdigest()))
        self.assertEqual(body['orientations'][body['recommended_id']]['label'], '위아래 뒤집기')
        self.assertTrue(body['preview']['faces'])
        self.assertNotIn('_mesh', body)
        self.assertEqual(self.client.get(body['source_url']).content, content)
        placed = self.client.get(f'/api/imports/{body["import_id"]}/oriented', params={'orientation': body['recommended_id']})
        self.assertEqual(placed.status_code, 200)
        self.assertIn("filename*=utf-8''rocket%20stand-", placed.headers['content-disposition'])
        again = model_import.analyse('placed.3mf', placed.content)
        self.assertLess(again['orientations'][again['original_id']]['overhang_mm2'], 1)
        self.assertEqual(self.client.get(f'/api/imports/{body["import_id"]}').json()['orientations'], body['orientations'])
        listed = self.client.get('/api/imports').json()['imports']
        self.assertEqual([(item['import_id'], item['filename']) for item in listed], [(body['import_id'], 'rocket stand.stl')])

    def test_changed_originals_bad_requests_and_unknown_ids_are_refused(self):
        body = self.upload('cube.3mf', zipfile_bytes({'3D/3dmodel.model': cube_mesh_model()})).json()
        source = next((self.root / 'imports' / body['import_id']).glob('source.*'))
        source.write_bytes(source.read_bytes() + b' ')
        self.assertEqual(self.client.get(f'/api/imports/{body["import_id"]}').status_code, 409)
        self.assertEqual(self.client.get(f'/api/imports/{body["import_id"]}/oriented', params={'orientation': 0}).status_code, 409)
        self.assertEqual(self.upload('bad.obj', b'x').status_code, 422)
        self.assertEqual(self.upload('../x.stl', stl_bytes(t_shape())).status_code, 422)
        self.assertEqual(self.client.get('/api/imports/' + 'f' * 32).status_code, 404)
        self.assertEqual(self.client.post('/api/imports', headers=self.headers, json={'filename': 'a.stl', 'content_base64': '***'}).status_code, 422)
        self.assertEqual(list((self.root / 'imports').iterdir()), [source.parent])  # refused uploads leave nothing

    def test_a_placement_becomes_a_sliceable_job_with_its_source_recorded(self):
        import sys
        sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
        from qualify_bambu import synthetic_fixture
        from print_agent.studio_project import _generated_model
        content = stl_bytes(t_shape())
        body = self.upload('cap.stl', content).json()
        response = self.client.post(f'/api/imports/{body["import_id"]}/jobs', headers=self.headers,
                                    json={'orientation': body['recommended_id']})
        self.assertEqual(response.status_code, 201, response.text)
        job = response.json()
        self.assertEqual((job['template'], job['status'], job['result']['geometry_status']), ('imported', 'geometry_validated', 'imported_mesh'))
        self.assertEqual(job['title'], '불러온 모델 “cap.stl” · 60.0 × 40.0 × 35.0 mm')
        source = job['design_source']
        self.assertEqual((source['kind'], source['sha256'], source['orientation']['label']),
                         ('imported_file', hashlib.sha256(content).hexdigest(), '위아래 뒤집기'))
        model = self.client.get(job['artifacts']['three_mf']).content
        _generated_model(model)  # the same layout as the app's own CAD, so Studio composition accepts it
        self.assertLess(model_import.analyse('m.3mf', model)['orientations'][0]['overhang_mm2'], 1)
        stl = self.client.get(job['artifacts']['stl']).content
        self.assertAlmostEqual(model_import.analyse('m.stl', stl)['facts']['volume_mm3'], body['facts']['volume_mm3'], places=1)
        manifest = self.client.get(job['artifacts']['manifest']).json()
        self.assertEqual((manifest['template'], manifest['design_source']['import_id']), ('imported', body['import_id']))
        bundle, _ = synthetic_fixture()
        plan = self.client.post('/api/slice', headers=self.headers, json={'job_id': job['id'], 'config_bundle': bundle}).json()['plan']
        self.assertTrue(plan['print_volume']['can_prepare'], plan)
        self.assertEqual(self.client.post(f'/api/jobs/{job["id"]}/printability', headers=self.headers,
                                          json={'nozzle_mm': 0.6}).status_code, 422)
        self.assertEqual(self.client.get(f'/api/jobs/{job["id"]}/recovery').json()['items'], [])
        self.assertEqual(self.client.get('/api/jobs/' + job['id']).json()['title'], job['title'])
        self.assertEqual(self.client.post('/api/model-edits/plan', headers=self.headers, json={
            'text': '높이 5mm 늘려줘', 'base_parameters': job['result']['parameters']}).status_code, 422)

    def test_job_needs_a_known_placement_and_an_unchanged_original(self):
        body = self.upload('cube.3mf', zipfile_bytes({'3D/3dmodel.model': cube_mesh_model()})).json()
        url = f'/api/imports/{body["import_id"]}/jobs'
        self.assertEqual(self.client.post(url, headers=self.headers, json={'orientation': 63}).status_code, 422)
        self.assertEqual(self.client.post(url, headers=self.headers, json={'orientation': '0'}).status_code, 422)
        source = next((self.root / 'imports' / body['import_id']).glob('source.*'))
        source.write_bytes(source.read_bytes() + b' ')
        self.assertEqual(self.client.post(url, headers=self.headers, json={'orientation': 0}).status_code, 409)
        self.assertEqual(self.client.get('/api/jobs').json()['jobs'], [])

    def test_oversized_request_is_refused_before_reading(self):
        from print_agent.app import MAX_MODEL_REQUEST_BYTES
        response = self.client.post('/api/imports', headers={**self.headers, 'Content-Type': 'application/json',
                                                             'Content-Length': str(MAX_MODEL_REQUEST_BYTES + 1)}, content=b'{}')
        self.assertEqual(response.status_code, 413)


if __name__ == '__main__':
    unittest.main()
