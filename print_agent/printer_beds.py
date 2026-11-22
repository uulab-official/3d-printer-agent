"""Build-plate sizes for the preview's "on the plate" view.

This is a visual reference only. The slicer settings used for an actual slice stay
the authority (``print_volume`` compares against those). Every entry names its
source. Coordinates are millimetres with the origin at the plate's front-left
corner, as in the source definitions.

Bambu Lab values are the ``printable_area``, ``printable_height``,
``bed_exclude_area`` and ``extruder_printable_area`` of the 0.4 mm nozzle machine
definitions shipped with Bambu Studio 02.09.01.70 (``profiles/BBL/machine``), with
``inherits`` resolved. For two-nozzle models the region both nozzles reach is the
intersection of their ``extruder_printable_area`` rectangles.
"""
from __future__ import annotations

import copy

BAMBU_SOURCE = 'Bambu Studio 02.09.01.70 기종 정의(0.4 mm 노즐)'
SNAPMAKER_SOURCE = 'Snapmaker U1 공식 사양 페이지(snapmaker.com/snapmaker-u1/specs)'

_EXCLUDE_X1_P1 = [[0, 0, 18, 28]]  # x0, y0, x1, y1 — the purge chute corner


def _bambu(model_id, name, width, depth, height, *, exclude=None, shared=None):
    entry = {'id': f'bambu-{model_id.lower()}', 'vendor': 'Bambu Lab', 'name': name, 'model_code': model_id,
             'width': width, 'depth': depth, 'height': height, 'exclude': exclude or [], 'shared_x': shared,
             'source': BAMBU_SOURCE}
    return entry


BEDS = [
    _bambu('N1', 'A1 mini', 180, 180, 180),
    _bambu('N2S', 'A1', 256, 256, 256),
    _bambu('C11', 'P1P', 256, 256, 250, exclude=_EXCLUDE_X1_P1),
    _bambu('C12', 'P1S', 256, 256, 250, exclude=_EXCLUDE_X1_P1),
    _bambu('N7', 'P2S', 256, 256, 256),
    _bambu('BL-P002', 'X1', 256, 256, 250, exclude=_EXCLUDE_X1_P1),
    _bambu('BL-P001', 'X1 Carbon', 256, 256, 250, exclude=_EXCLUDE_X1_P1),
    _bambu('C13', 'X1E', 256, 256, 250, exclude=_EXCLUDE_X1_P1),
    _bambu('N6', 'X2D', 256, 256, 261, shared=[20.5, 256]),
    _bambu('N9', 'A2L', 330, 320, 325),
    _bambu('O1C2', 'H2C', 330, 320, 325, shared=[25, 325]),
    _bambu('O1D', 'H2D', 350, 320, 325, shared=[25, 325]),
    _bambu('O1E', 'H2D Pro', 350, 320, 325, shared=[25, 325]),
    _bambu('O1S', 'H2S', 340, 320, 340),
    _bambu('N10', 'H3C', 330, 320, 325),
    {'id': 'snapmaker-u1', 'vendor': 'Snapmaker', 'name': 'U1', 'model_code': None,
     'width': 270, 'depth': 270, 'height': 270, 'exclude': [], 'shared_x': None, 'source': SNAPMAKER_SOURCE},
]


def _validate():
    seen = set()
    for bed in BEDS:
        assert bed['id'] not in seen, bed['id']
        seen.add(bed['id'])
        assert all(0 < bed[key] <= 1000 for key in ('width', 'depth', 'height')), bed['id']
        for x0, y0, x1, y1 in bed['exclude']:
            assert 0 <= x0 < x1 <= bed['width'] and 0 <= y0 < y1 <= bed['depth'], bed['id']
        if bed['shared_x'] is not None:
            low, high = bed['shared_x']
            assert 0 <= low < high <= bed['width'], bed['id']


_validate()


def printer_beds():
    """Copies of the plate table for the browser, with the scope note."""
    return {
        'beds': copy.deepcopy(BEDS),
        'scope': ('출력판 크기는 참고용입니다. 실제로 들어가는지는 슬라이스할 때 쓰는 프린터 설정이 최종 기준이며, '
                  '브림·서포트·퍼지 영역은 이 표시에 들어 있지 않습니다.'),
    }


def fit(size, bed):
    """Compare a model's X/Y/Z size (mm) with a plate. Pure; used by tests and mirrors the browser.

    Returns ``{'fits', 'rotate', 'over': [dx, dy, dz], 'shared_over'}`` where ``rotate`` is
    true when only a 90° turn on the plate makes it fit, and ``shared_over`` is how far the
    width exceeds the region both nozzles of a two-nozzle printer reach (``None`` if n/a).
    """
    width, depth, height = (max(0.0, float(value)) for value in size)
    over = [round(max(0.0, width - bed['width']), 1), round(max(0.0, depth - bed['depth']), 1),
            round(max(0.0, height - bed['height']), 1)]
    fits = not any(over)
    turned = width <= bed['depth'] and depth <= bed['width'] and height <= bed['height']
    shared = None
    if bed.get('shared_x'):
        shared_width = bed['shared_x'][1] - bed['shared_x'][0]
        footprint = min(width, depth) if not fits and turned else width
        shared = round(max(0.0, footprint - shared_width), 1)
    return {'fits': fits, 'rotate': not fits and turned, 'over': over, 'shared_over': shared}
