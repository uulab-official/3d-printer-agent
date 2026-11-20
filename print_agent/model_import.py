"""Imported mesh models (STL, 3MF): bounded parsing, mesh facts, review and orientation.

Pure functions. Nothing is repaired, simplified or re-meshed: the imported triangles
are measured as they are, and an orientation only rotates and moves them. Results are
advice from geometry alone (no slicer); they never claim a print will succeed.
"""
from __future__ import annotations

import io
import math
import re
import struct
import zipfile
import xml.etree.ElementTree as ET

from .printability import (OVERHANG_LIMIT_DEG, REFERENCE_NOZZLE_MM, bed_contact_item, line_width, material_item,
                           overhang_item, stability_item, _STATUS_RANK)

MAX_MODEL_BYTES = 32 * 1024 * 1024
MAX_TRIANGLES = 400_000
MAX_ARCHIVE_ENTRIES = 512
MAX_MODEL_PART_BYTES = 256 * 1024 * 1024
MAX_COMPONENT_DEPTH = 8
MAX_DIMENSION_MM = 2000.0
PREVIEW_TRIANGLES = 60_000
SUFFIXES = ('.stl', '.3mf')
_CORE = '{http://schemas.microsoft.com/3dmanufacturing/core/2015/02}'
_PRODUCTION_PATH = '{http://schemas.microsoft.com/3dmanufacturing/production/2015/06}path'
_UNITS = {'micron': 0.001, 'millimeter': 1.0, 'centimeter': 10.0, 'inch': 25.4, 'foot': 304.8, 'meter': 1000.0}
_IDENTITY = (1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0)
_DOWN = math.cos(math.radians(90 - OVERHANG_LIMIT_DEG))  # a face steeper than the limit has normal z below -this


class ModelImportError(ValueError):
    """The file is not a supported, bounded mesh model."""


# ---------------------------------------------------------------------------
# Parsing


def _check_count(count):
    if count > MAX_TRIANGLES:
        raise ModelImportError(f'삼각형이 {MAX_TRIANGLES:,}개를 넘는 모델은 불러오지 않습니다. 슬라이서나 CAD에서 단순화한 뒤 다시 시도하세요.')


def _parse_stl(content: bytes):
    if len(content) >= 84:
        count = struct.unpack_from('<I', content, 80)[0]
        if 84 + 50 * count == len(content):
            _check_count(count)
            triangles = []
            for index in range(count):
                values = struct.unpack_from('<12f', content, 84 + 50 * index)
                triangles.append((values[3:6], values[6:9], values[9:12]))
            return triangles
    try:
        text = content.decode('ascii')
    except UnicodeDecodeError as exc:
        raise ModelImportError('STL 파일이 올바른 바이너리·ASCII 형식이 아닙니다.') from exc
    if not text.lstrip().lower().startswith('solid'):
        raise ModelImportError('STL 파일이 올바른 바이너리·ASCII 형식이 아닙니다.')
    number = r'([-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?)'
    points = [tuple(float(value) for value in match.groups())
              for match in re.finditer(r'vertex\s+' + number + r'\s+' + number + r'\s+' + number, text)]
    if len(points) % 3:
        raise ModelImportError('ASCII STL의 삼각형 꼭짓점 수가 맞지 않습니다.')
    _check_count(len(points) // 3)
    return [tuple(points[index:index + 3]) for index in range(0, len(points), 3)]


def _transform(text):
    if text is None:
        return _IDENTITY
    values = text.split()
    try:
        numbers = tuple(float(value) for value in values)
    except ValueError as exc:
        raise ModelImportError('3MF 변환 행렬이 올바르지 않습니다.') from exc
    if len(numbers) != 12 or not all(math.isfinite(value) for value in numbers):
        raise ModelImportError('3MF 변환 행렬이 올바르지 않습니다.')
    return numbers


def _compose(inner, outer):
    """Apply `inner` then `outer` (3MF row-vector convention: p' = p · M)."""
    a, b = inner, outer
    rows = [a[0:3], a[3:6], a[6:9]]
    out = []
    for row in rows:
        out.extend(row[0] * b[0 + col] + row[1] * b[3 + col] + row[2] * b[6 + col] for col in range(3))
    translation = a[9:12]
    out.extend(translation[0] * b[0 + col] + translation[1] * b[3 + col] + translation[2] * b[6 + col] + b[9 + col]
               for col in range(3))
    return tuple(out)


def _apply(m, point):
    x, y, z = point
    return (x * m[0] + y * m[3] + z * m[6] + m[9], x * m[1] + y * m[4] + z * m[7] + m[10],
            x * m[2] + y * m[5] + z * m[8] + m[11])


def _parse_3mf(content: bytes):
    try:
        archive = zipfile.ZipFile(io.BytesIO(content))
        infos = archive.infolist()
    except (zipfile.BadZipFile, OSError) as exc:
        raise ModelImportError('3MF 파일이 올바른 ZIP이 아닙니다.') from exc
    if len(infos) > MAX_ARCHIVE_ENTRIES:
        raise ModelImportError('3MF 안의 파일이 너무 많습니다.')
    parts = {}
    for info in infos:
        name = info.filename
        if name.lower().endswith('.model') and name.startswith('3D/'):
            if info.file_size > MAX_MODEL_PART_BYTES or sum(item.file_size for item in parts.values()) > MAX_MODEL_PART_BYTES:
                raise ModelImportError('3MF 모델 데이터가 너무 큽니다.')
            parts['/' + name] = info
    root_name = '/3D/3dmodel.model'
    if root_name not in parts:
        raise ModelImportError('3MF에 3D/3dmodel.model이 없습니다.')
    documents, budget = {}, [0]

    def document(path):
        if path not in documents:
            if path not in parts:
                raise ModelImportError(f'3MF가 참조한 모델 파일({path})이 없습니다.')
            try:
                tree = ET.fromstring(archive.read(parts[path]))
            except (ET.ParseError, zipfile.BadZipFile, OSError, RuntimeError) as exc:
                raise ModelImportError('3MF 모델 XML을 읽을 수 없습니다.') from exc
            if tree.tag != _CORE + 'model':
                raise ModelImportError('3MF 모델 형식이 올바르지 않습니다.')
            scale = _UNITS.get(tree.get('unit', 'millimeter'))
            if scale is None:
                raise ModelImportError('3MF 단위를 알 수 없습니다.')
            resources = tree.find(_CORE + 'resources')
            objects = {item.get('id'): item for item in (resources.findall(_CORE + 'object') if resources is not None else [])}
            documents[path] = (tree, scale, objects)
        return documents[path]

    triangles = []

    def emit(path, object_id, matrix, depth):
        if depth > MAX_COMPONENT_DEPTH:
            raise ModelImportError('3MF 부품 중첩이 너무 깊습니다.')
        _, scale, objects = document(path)
        item = objects.get(object_id)
        if item is None:
            raise ModelImportError('3MF가 없는 개체를 참조합니다.')
        if item.get('type', 'model') not in ('model', 'solidsupport'):
            return  # support, surface and other non-model objects are not printed parts
        mesh = item.find(_CORE + 'mesh')
        if mesh is not None:
            vertices = [(float(v.get('x')) * scale, float(v.get('y')) * scale, float(v.get('z')) * scale)
                        for v in mesh.iter(_CORE + 'vertex')]
            for triangle in mesh.iter(_CORE + 'triangle'):
                budget[0] += 1
                _check_count(budget[0])
                try:
                    a, b, c = (vertices[int(triangle.get(key))] for key in ('v1', 'v2', 'v3'))
                except (TypeError, ValueError, IndexError) as exc:
                    raise ModelImportError('3MF 삼각형이 없는 꼭짓점을 가리킵니다.') from exc
                triangles.append((_apply(matrix, a), _apply(matrix, b), _apply(matrix, c)))
        components = item.find(_CORE + 'components')
        for component in (components.findall(_CORE + 'component') if components is not None else []):
            target = component.get(_PRODUCTION_PATH) or path
            emit(target, component.get('objectid'), _compose(_transform(component.get('transform')), matrix), depth + 1)

    try:
        tree, _, _ = document(root_name)
        build = tree.find(_CORE + 'build')
        items = build.findall(_CORE + 'item') if build is not None else []
        if not items:
            raise ModelImportError('3MF에 출력할 개체(build item)가 없습니다.')
        for item in items:
            if item.get('printable', '1') == '0':
                continue
            emit(item.get(_PRODUCTION_PATH) or root_name, item.get('objectid'), _transform(item.get('transform')), 0)
    except (TypeError, ValueError) as exc:
        if isinstance(exc, ModelImportError):
            raise
        raise ModelImportError('3MF 꼭짓점 값이 올바르지 않습니다.') from exc
    return triangles, len(items)


def parse_model(filename: str, content: bytes) -> dict:
    """Triangles (mm) of a supported file, rejected before measurement when unbounded."""
    name = str(filename or '')
    suffix = name[name.rfind('.'):].lower() if '.' in name else ''
    if suffix not in SUFFIXES:
        raise ModelImportError('STL 또는 3MF 파일만 불러올 수 있습니다.')
    if not isinstance(content, (bytes, bytearray)) or not content:
        raise ModelImportError('모델 파일이 비어 있습니다.')
    if len(content) > MAX_MODEL_BYTES:
        raise ModelImportError(f'모델 파일은 {MAX_MODEL_BYTES // (1024 * 1024)} MiB 이하여야 합니다.')
    if suffix == '.stl':
        triangles, items = _parse_stl(bytes(content)), 1
    else:
        triangles, items = _parse_3mf(bytes(content))
    if not triangles:
        raise ModelImportError('모델에 삼각형이 없습니다.')
    if not all(math.isfinite(value) for triangle in triangles for point in triangle for value in point):
        raise ModelImportError('모델 좌표에 숫자가 아닌 값이 있습니다.')
    return {'format': suffix[1:], 'triangles': triangles, 'build_items': items}


# ---------------------------------------------------------------------------
# Mesh facts and orientation


def _indexed(triangles):
    lookup, vertices, faces = {}, [], []
    for triangle in triangles:
        face = []
        for point in triangle:
            key = (round(point[0], 5), round(point[1], 5), round(point[2], 5))
            index = lookup.get(key)
            if index is None:
                index = lookup[key] = len(vertices)
                vertices.append(key)
            face.append(index)
        if len(set(face)) == 3:
            faces.append(tuple(face))
    return vertices, faces


def _normals(vertices, faces):
    result = []
    for a, b, c in faces:
        pa, pb, pc = vertices[a], vertices[b], vertices[c]
        u = (pb[0] - pa[0], pb[1] - pa[1], pb[2] - pa[2])
        v = (pc[0] - pa[0], pc[1] - pa[1], pc[2] - pa[2])
        n = (u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2], u[0] * v[1] - u[1] * v[0])
        length = math.sqrt(n[0] * n[0] + n[1] * n[1] + n[2] * n[2])
        result.append(((n[0] / length, n[1] / length, n[2] / length), length / 2) if length else ((0.0, 0.0, 0.0), 0.0))
    return result


def mesh_facts(vertices, faces):
    edges = {}
    for a, b, c in faces:
        for edge in ((a, b), (b, c), (c, a)):
            key = (edge[0], edge[1]) if edge[0] < edge[1] else (edge[1], edge[0])
            edges[key] = edges.get(key, 0) + 1
    open_edges = sum(1 for count in edges.values() if count == 1)
    excess_edges = sum(1 for count in edges.values() if count > 2)
    volume = 0.0
    for a, b, c in faces:
        pa, pb, pc = vertices[a], vertices[b], vertices[c]
        volume += (pa[0] * (pb[1] * pc[2] - pb[2] * pc[1]) - pa[1] * (pb[0] * pc[2] - pb[2] * pc[0])
                   + pa[2] * (pb[0] * pc[1] - pb[1] * pc[0])) / 6
    closed = open_edges == 0 and excess_edges == 0
    return {'triangles': len(faces), 'vertices': len(vertices), 'closed': closed,
            'open_edges': open_edges, 'non_manifold_edges': excess_edges,
            'volume_mm3': abs(volume) if closed else None, 'inverted': closed and volume < 0}


def _rotation_to_up(up):
    """Rotation matrix (rows) that turns `up` into +Z."""
    x, y, z = up
    if z > 1 - 1e-9:
        return ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0))
    if z < -1 + 1e-9:
        return ((1.0, 0.0, 0.0), (0.0, -1.0, 0.0), (0.0, 0.0, -1.0))
    axis = (y, -x, 0.0)  # up × Z
    s = math.sqrt(axis[0] ** 2 + axis[1] ** 2)
    k = (axis[0] / s, axis[1] / s, 0.0)
    c = z
    t = 1 - c
    return ((t * k[0] * k[0] + c, t * k[0] * k[1] - s * k[2], t * k[0] * k[2] + s * k[1]),
            (t * k[0] * k[1] + s * k[2], t * k[1] * k[1] + c, t * k[1] * k[2] - s * k[0]),
            (t * k[0] * k[2] - s * k[1], t * k[1] * k[2] + s * k[0], t * k[2] * k[2] + c))


def _rotate(matrix, point):
    return tuple(matrix[row][0] * point[0] + matrix[row][1] * point[1] + matrix[row][2] * point[2] for row in range(3))


def _candidates(normals):
    """Axis directions plus the largest flat areas, each as the face to put on the bed."""
    total = sum(area for _, area in normals) or 1.0
    groups = {}
    for normal, area in normals:
        if area:
            key = tuple(round(value, 2) for value in normal)
            groups[key] = groups.get(key, 0.0) + area
    flats = [key for key, area in sorted(groups.items(), key=lambda item: -item[1]) if area >= 0.01 * total][:6]
    found = []
    named = [((0.0, 0.0, -1.0), '원래 방향'), ((0.0, 0.0, 1.0), '위아래 뒤집기'), ((0.0, -1.0, 0.0), '앞면을 바닥으로'),
             ((0.0, 1.0, 0.0), '뒷면을 바닥으로'), ((-1.0, 0.0, 0.0), '왼쪽 면을 바닥으로'), ((1.0, 0.0, 0.0), '오른쪽 면을 바닥으로')]
    for down, label in named + [(key, None) for key in flats]:
        length = math.sqrt(sum(value * value for value in down))
        if not length:
            continue
        down = tuple(value / length for value in down)
        if any(sum(a * b for a, b in zip(down, other)) > 0.999 for other, _ in found):
            continue
        found.append((down, label or f'넓은 평면 {sum(1 for _, name in found if name.startswith("넓은")) + 1}을 바닥으로'))
    return found


def _evaluate(vertices, faces, normals, down):
    up = (-down[0], -down[1], -down[2])
    heights = [v[0] * up[0] + v[1] * up[1] + v[2] * up[2] for v in vertices]
    floor = min(heights)
    contact = overhang = 0.0
    for (a, b, c), (normal, area) in zip(faces, normals):
        if not area:
            continue
        nz = normal[0] * up[0] + normal[1] * up[1] + normal[2] * up[2]
        low = min(heights[a], heights[b], heights[c])
        if nz < -0.999 and max(heights[a], heights[b], heights[c]) - floor < 1e-3:
            contact += area
        elif nz < -_DOWN and low > floor + 0.05:
            overhang += area
    rotation = _rotation_to_up(up)
    turned = [_rotate(rotation, v) for v in vertices]
    size = [max(p[axis] for p in turned) - min(p[axis] for p in turned) for axis in range(3)]
    return {'rotation': [list(row) for row in rotation], 'contact_mm2': contact, 'overhang_mm2': overhang,
            'size_mm': {'x': size[0], 'y': size[1], 'z': size[2]}}


def orientations(vertices, faces, normals=None):
    """Ranked placements: least unsupported area first, then more bed contact, then lower height."""
    normals = normals or _normals(vertices, faces)
    ranked = []
    for down, label in _candidates(normals):
        result = _evaluate(vertices, faces, normals, down)
        ranked.append({'label': label, 'down': list(down), **result})
    ranked.sort(key=lambda item: (round(item['overhang_mm2'] / 10), -round(item['contact_mm2']), round(item['size_mm']['z'], 1)))
    for index, item in enumerate(ranked):
        item['id'] = index
        item['recommended'] = index == 0
    return ranked


def oriented_vertices(vertices, rotation):
    """Rotate, then move onto the bed (z = 0) centred on X and Y."""
    turned = [_rotate(rotation, v) for v in vertices]
    mins = [min(p[axis] for p in turned) for axis in range(3)]
    maxs = [max(p[axis] for p in turned) for axis in range(3)]
    shift = ((mins[0] + maxs[0]) / 2, (mins[1] + maxs[1]) / 2, mins[2])
    return [(p[0] - shift[0], p[1] - shift[1], p[2] - shift[2]) for p in turned]


def review(facts, placement):
    """Advisory items for one placement; thickness is not measured on an imported mesh."""
    size = placement['size_mm']
    items = [{'id': 'mesh', 'label': '메시 상태', 'status': 'pass' if facts['closed'] else 'warn',
              'value': '닫힌 메시' if facts['closed'] else f'열린 모서리 {facts["open_edges"]}개 · 겹친 모서리 {facts["non_manifold_edges"]}개',
              'detail': ('구멍 없이 닫힌 메시입니다.' if facts['closed']
                         else '구멍이나 겹친 면이 있어 슬라이서가 일부를 빠뜨리거나 다르게 채울 수 있습니다.'),
              'advice': None if facts['closed'] else '슬라이서의 모델 수리 기능이나 원본 CAD에서 다시 내보내기를 확인하세요.',
              'field': None},
             bed_contact_item(placement['contact_mm2'], size['x'] * size['y']),
             stability_item(size['x'], size['y'], size['z']),
             overhang_item(placement['overhang_mm2'])]
    if facts['volume_mm3'] is not None:
        items.append(material_item(facts['volume_mm3']))
    if max(size.values()) > MAX_DIMENSION_MM:
        items.append({'id': 'size', 'label': '크기', 'status': 'fail', 'value': f'{max(size.values()):.0f} mm',
                      'detail': '단위가 잘못 저장됐을 수 있습니다(예: m·인치).', 'advice': '원본의 단위를 확인하세요.', 'field': None})
    worst = max((item['status'] for item in items), key=_STATUS_RANK.get)
    return {'schema_version': 1, 'status': {'pass': 'ok', 'warn': 'review', 'fail': 'needs_change'}[worst],
            'basis': {'nozzle_mm': REFERENCE_NOZZLE_MM, 'line_width_mm': line_width(REFERENCE_NOZZLE_MM),
                      'overhang_limit_deg': OVERHANG_LIMIT_DEG,
                      'note': '불러온 메시의 형상만 본 조언입니다. 벽 두께는 측정하지 않았고, 슬라이서·실물 결과가 아닙니다.'},
            'items': items}


def preview_mesh(vertices, faces):
    """At most PREVIEW_TRIANGLES faces, evenly sampled, for the browser viewer only."""
    step = max(1, math.ceil(len(faces) / PREVIEW_TRIANGLES))
    chosen = faces[::step]
    used = sorted({index for face in chosen for index in face})
    remap = {old: new for new, old in enumerate(used)}
    return {'vertices': [[round(value, 4) for value in vertices[index]] for index in used],
            'faces': [[remap[index] for index in face] for face in chosen], 'sampled': step > 1}


def analyse(filename: str, content: bytes) -> dict:
    parsed = parse_model(filename, content)
    vertices, faces = _indexed(parsed['triangles'])
    if not faces:
        raise ModelImportError('면적이 있는 삼각형이 없습니다.')
    normals = _normals(vertices, faces)
    facts = mesh_facts(vertices, faces)
    ranked = orientations(vertices, faces, normals)
    for item in ranked:
        item['review'] = review(facts, item)
    original = next(item for item in ranked if item['label'] == '원래 방향')
    return {'format': parsed['format'], 'build_items': parsed['build_items'], 'facts': facts,
            'orientations': ranked, 'original_id': original['id'], 'recommended_id': ranked[0]['id'],
            '_mesh': (vertices, faces)}


def three_mf(vertices, faces, name='imported model') -> bytes:
    """A plain core-spec 3MF of one mesh object (mm)."""
    from xml.sax.saxutils import quoteattr
    points = ''.join(f'<vertex x="{x:.5f}" y="{y:.5f}" z="{z:.5f}"/>' for x, y, z in vertices)
    triangles = ''.join(f'<triangle v1="{a}" v2="{b}" v3="{c}"/>' for a, b, c in faces)
    model = ('<?xml version="1.0" encoding="UTF-8"?>\n<model unit="millimeter" xml:lang="en-US" '
             'xmlns="http://schemas.microsoft.com/3dmanufacturing/core/2015/02">'
             f'<metadata name="Application">3D Printer Agent</metadata><metadata name="Title">{quoteattr(name)[1:-1]}</metadata>'
             f'<resources><object id="1" type="model"><mesh><vertices>{points}</vertices><triangles>{triangles}</triangles></mesh></object></resources>'
             '<build><item objectid="1"/></build></model>')
    types = ('<?xml version="1.0" encoding="UTF-8"?>\n<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
             '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
             '<Default Extension="model" ContentType="application/vnd.ms-package.3dmanufacturing-3dmodel+xml"/></Types>')
    rels = ('<?xml version="1.0" encoding="UTF-8"?>\n<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Target="/3D/3dmodel.model" Id="rel0" Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel"/></Relationships>')
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
        for entry, text in (('[Content_Types].xml', types), ('_rels/.rels', rels), ('3D/3dmodel.model', model)):
            info = zipfile.ZipInfo(entry, date_time=(2026, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, text)
    return stream.getvalue()
