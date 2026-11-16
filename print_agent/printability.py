"""Advisory printability review of generated CAD (pure geometry, no slicer).

The review is computed from the validated solid, its preview mesh and the template
parameters. It uses a stated reference extrusion (0.4 mm nozzle, 0.42 mm line) because
the user's real nozzle is not known at generation time. Results are advice with a
suggested parameter to change; they never block generation and never claim that a
print will succeed.
"""
import math

REFERENCE_NOZZLE_MM = 0.4
REFERENCE_LINE_MM = 0.42
SUPPORTED_NOZZLES_MM = (0.2, 0.4, 0.6, 0.8)
PLA_DENSITY_G_CM3 = 1.24
OVERHANG_LIMIT_DEG = 45.0
_STATUS_RANK = {'pass': 0, 'warn': 1, 'fail': 2}


def _item(item_id, label, status, value, detail, advice=None, field=None):
    return {'id': item_id, 'label': label, 'status': status, 'value': value, 'detail': detail,
            'advice': advice, 'field': field}


def _thin_features(p):
    """Minimum printed thicknesses that the template parameters define exactly."""
    # Only thicknesses the built solid actually has. For the cable comb and frame,
    # `wall` is a minimum constraint, not a printed wall, so it is not reported.
    w, d, h, wall, bottom = (p[key] for key in ('width', 'depth', 'height', 'wall', 'bottom'))
    if p['template'] == 'cable_comb':
        diameter = p['cable_diameter'] + p['fit_clearance']
        gap = (w - p['slots'] * diameter) / (p['slots'] + 1)
        return [('bottom', '홈 아래 바닥', bottom), ('slots', '케이블 홈 사이 벽', gap)]
    if p['template'] == 'magnet_frame':
        diameter = p['inset_diameter'] + p['fit_clearance']
        return [('inset_diameter', '포켓 둘레 벽', (min(w, d) - diameter) / 2),
                ('inset_depth', '포켓 아래 바닥', h - p['inset_depth'])]
    if p['template'] == 'phone_stand':
        return [('wall', '등판·앞턱', wall), ('bottom', '바닥', bottom)]
    if p['template'] == 'name_tag':
        # Letter strokes depend on the font; about a tenth of the letter height for bold sans.
        return [('bottom', '받침판', bottom), ('hole_diameter', '고리 둘레', wall),
                ('text_size', '글자 획(추정)', p['text_size'] * 0.1)]
    features = [('wall', '바깥 벽', wall), ('bottom', '바닥', bottom)]
    if p['dividers']:
        features.append(('wall', '칸막이', wall))
    return features


def line_width(nozzle_mm):
    # Common default extrusion width is about 105% of the nozzle diameter.
    return round(nozzle_mm * 1.05, 3)


def _wall_item(p, line=REFERENCE_LINE_MM):
    features = _thin_features(p)
    field, name, thinnest = min(features, key=lambda feature: feature[2])
    lines = thinnest / line
    value = f'{thinnest:.2f} mm ({name})'
    if thinnest < line:
        return _item('min_thickness', '가장 얇은 부분', 'fail', value,
                     f'압출 폭 {line:.2f} mm보다 얇아 이 부분이 출력되지 않을 수 있습니다.',
                     f'{name} 두께를 {2 * line:.2f} mm 이상으로 늘리세요.', field)
    if lines < 2:
        return _item('min_thickness', '가장 얇은 부분', 'warn', value,
                     f'압출 선 {lines:.1f}줄 두께라 약하거나 틈이 생길 수 있습니다.',
                     f'{name} 두께를 {2 * line:.2f} mm 이상(2줄)으로 늘리면 더 튼튼합니다.', field)
    return _item('min_thickness', '가장 얇은 부분', 'pass', value,
                 f'이 노즐로 약 {math.floor(lines)}줄 이상 출력되는 두께입니다.')


def _normal(a, b, c):
    u = [b[i] - a[i] for i in range(3)]
    v = [c[i] - a[i] for i in range(3)]
    n = [u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2], u[0] * v[1] - u[1] * v[0]]
    length = math.hypot(*n)
    if not length:
        return [0.0, 0.0, 0.0], 0.0  # degenerate triangle: no area, no direction
    return [value / length for value in n], length / 2


def _mesh_review(mesh, floor_z, footprint_area):
    vertices, faces = mesh['vertices'], mesh['faces']
    contact = overhang = 0.0
    limit = -math.cos(math.radians(90 - OVERHANG_LIMIT_DEG))  # normal z below -0.707
    for face in faces:
        a, b, c = (vertices[index] for index in face)
        normal, area = _normal(a, b, c)
        if not area:
            continue
        lowest = min(a[2], b[2], c[2])
        if all(abs(point[2] - floor_z) < 1e-6 for point in (a, b, c)) and normal[2] < -0.999:
            contact += area
        elif normal[2] < limit and lowest > floor_z + 1e-6:
            overhang += area
    return contact, overhang


def assess_printability(shape, parameters, mesh):
    return review_mesh(parameters, mesh, shape.Volume())


def review_mesh(parameters, mesh, volume_mm3, nozzle_mm=REFERENCE_NOZZLE_MM):
    """Review from stored values only, so a saved job can be rechecked for another nozzle."""
    if nozzle_mm not in SUPPORTED_NOZZLES_MM:
        raise ValueError('점검 노즐은 0.2, 0.4, 0.6, 0.8 mm 중에서 고르세요.')
    vertices = mesh['vertices']
    mins = [min(point[axis] for point in vertices) for axis in range(3)]
    maxs = [max(point[axis] for point in vertices) for axis in range(3)]
    xlen, ylen, zlen = (maxs[axis] - mins[axis] for axis in range(3))
    line = line_width(nozzle_mm)
    footprint = xlen * ylen
    contact, overhang = _mesh_review(mesh, mins[2], footprint)
    ratio = contact / footprint if footprint else 0
    items = [_wall_item(parameters, line)]

    if ratio >= 0.5:
        items.append(_item('bed_contact', '바닥 접촉면', 'pass', f'{contact / 100:.1f} cm² ({ratio:.0%})',
                           '평평한 아랫면이 넓게 베드에 닿습니다.'))
    elif ratio >= 0.15:
        items.append(_item('bed_contact', '바닥 접촉면', 'warn', f'{contact / 100:.1f} cm² ({ratio:.0%})',
                           '베드에 닿는 면이 좁아 출력 중 떨어질 수 있습니다.',
                           '브림(brim)을 켜거나 바닥 면적을 넓히세요.'))
    else:
        items.append(_item('bed_contact', '바닥 접촉면', 'fail', f'{contact / 100:.1f} cm² ({ratio:.0%})',
                           '평평하게 베드에 닿는 면이 거의 없습니다.',
                           '모델을 눕히거나 평평한 바닥을 추가하세요.'))

    short_side = min(xlen, ylen)
    slenderness = zlen / short_side if short_side else math.inf
    if slenderness > 3:
        items.append(_item('stability', '세운 비율', 'warn', f'높이/짧은 변 {slenderness:.1f}',
                           '가늘고 높아 출력 중 흔들리거나 넘어질 수 있습니다.',
                           '높이를 줄이거나 짧은 변을 넓히세요.', 'height'))
    else:
        items.append(_item('stability', '세운 비율', 'pass', f'높이/짧은 변 {slenderness:.1f}',
                           '넘어질 위험이 낮은 비율입니다.'))

    if overhang > 1.0:
        items.append(_item('overhang', f'{OVERHANG_LIMIT_DEG:.0f}° 넘는 돌출부', 'warn', f'{overhang / 100:.2f} cm²',
                           '아래가 비어 있는 면이 있어 처지거나 지지대가 필요할 수 있습니다.',
                           '슬라이서에서 지지대를 확인하세요.'))
    else:
        items.append(_item('overhang', f'{OVERHANG_LIMIT_DEG:.0f}° 넘는 돌출부', 'pass', '없음',
                           '지지대 없이 쌓을 수 있는 형상입니다.'))

    # Only templates with a fitted insert or cable use the clearance parameter.
    clearance = parameters.get('fit_clearance') if parameters['template'] in ('cable_comb', 'magnet_frame', 'phone_stand') else None
    if clearance is not None:
        if clearance < 0.2:
            items.append(_item('fit_clearance', '끼움 여유', 'warn', f'{clearance:.2f} mm',
                               '여유가 작아 실물이 빡빡하게 끼거나 들어가지 않을 수 있습니다.',
                               '처음에는 0.2~0.4 mm로 시험해 보세요.', 'fit_clearance'))
        else:
            items.append(_item('fit_clearance', '끼움 여유', 'pass', f'{clearance:.2f} mm',
                               '일반적인 시작 범위의 여유입니다. 실제 맞춤은 시험 출력으로 확인하세요.'))

    volume_cm3 = volume_mm3 / 1000
    estimate = _item('material', '재료 사용 상한', 'pass', f'약 {volume_cm3 * PLA_DENSITY_G_CM3:.0f} g',
                     f'속을 100% 채운 PLA({PLA_DENSITY_G_CM3} g/cm³) 기준 상한입니다. 실제 사용량은 슬라이서 결과를 보세요.')
    estimate['grams'] = round(volume_cm3 * PLA_DENSITY_G_CM3, 1)
    items.append(estimate)

    worst = max((item['status'] for item in items), key=_STATUS_RANK.get)
    return {
        'schema_version': 1,
        'status': {'pass': 'ok', 'warn': 'review', 'fail': 'needs_change'}[worst],
        'basis': {'nozzle_mm': nozzle_mm, 'line_width_mm': line,
                  'overhang_limit_deg': OVERHANG_LIMIT_DEG,
                  'note': f'{nozzle_mm} mm 노즐(압출 폭 {line:.2f} mm) 기준으로 형상만 검토한 조언입니다. 실제 장비·설정·슬라이싱 결과가 아닙니다.'},
        'items': items,
    }
