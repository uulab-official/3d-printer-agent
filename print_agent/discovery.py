"""Original local starting recipes and optional placement bounding-box comparisons.

Discovery never generates CAD, checks printer compatibility or validates a print.
The catalog is server-owned; selection hashes identify the complete starting recipe.
"""
import hashlib
import json
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from .schemas import GeometryRequest


Dimension = Annotated[float, Field(strict=True, gt=0, le=10000, allow_inf_nan=False)]
Purpose = Literal['all', 'organization', 'cables', 'display']


class AvailableSpace(BaseModel):
    model_config = ConfigDict(extra='forbid')
    width: Dimension | None = None
    depth: Dimension | None = None
    height: Dimension | None = None


class DiscoveryRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    purpose: Purpose = 'all'
    available_space: AvailableSpace = Field(default_factory=AvailableSpace)


class ProjectSelection(BaseModel):
    model_config = ConfigDict(extra='forbid')
    id: str = Field(strict=True, min_length=1, max_length=100)
    recipe_sha256: str = Field(strict=True, pattern=r'^[a-f0-9]{64}$')


class StaleProjectSelection(ValueError):
    """The selected ID exists, but its current starting recipe has changed."""


def project_catalog() -> dict:
    """Return fresh JSON data so callers cannot change future recipes or hashes."""
    common_limits = [
        '표시 치수는 모델의 바깥 치수입니다. 실제 사용할 공간과 내용물을 직접 측정하세요.',
        'CAD 시작안이며 출력 성공·강도·치수 맞춤·재료·출력 시간을 검증하지 않았습니다.',
    ]
    tray_limits = ['칸막이와 벽이 내부 공간을 차지합니다. 외부 치수로 내용물 맞춤을 판단하지 마세요.']
    cable_limits = ['위가 열린 홈입니다. 스냅 고정장치가 아니며 케이블 유지력을 보장하지 않습니다.']
    frame_limits = ['원형 포켓만 있습니다. 걸이·스탠드·자석 고정 구조는 포함하지 않습니다.',
                    '여유값은 포켓 지름 전체에 더합니다. 실제 끼워맞춤은 따로 확인하세요.']
    definitions = [
        ('small-parts-tray', '작은 물건 트레이', 'organization', 'tray',
         '책상 위의 작은 물건을 한곳에 모아 두는 얕은 트레이입니다.',
         '칸막이 없는 작은 시작안으로 사용할 공간과 물건 크기를 비교하기 쉽습니다.',
         ['놓을 공간의 가로·세로·높이와 넣을 물건의 크기를 측정하세요.'], tray_limits,
         dict(width=90, depth=60, height=18, wall=2, bottom=2, dividers=0)),
        ('desk-sorter', '세 칸 책상 정리함', 'organization', 'tray',
         '두 개의 칸막이로 세 칸을 만든 책상 정리함입니다.',
         '작은 물건을 세 구역으로 나눠 담는 시작안입니다.',
         ['책상에서 쓸 공간과 각 칸에 넣을 물건의 크기를 측정하세요.'], tray_limits,
         dict(width=150, depth=90, height=30, wall=2, bottom=2, dividers=2)),
        ('drawer-tray', '두 칸 서랍 트레이', 'organization', 'tray',
         '한 개의 칸막이로 두 칸을 만든 서랍용 트레이입니다.',
         '서랍 안에서 물건을 두 구역으로 나누어 정리하는 시작안입니다.',
         ['서랍의 실제 내부 가로·세로와 닫힐 때의 여유 높이를 측정하세요.'], tray_limits,
         dict(width=180, depth=100, height=35, wall=2, bottom=2, dividers=1)),
        ('three-cable-rest', '세 줄 케이블 받침', 'cables', 'cable_comb',
         '위가 열린 세 개의 홈에 케이블을 올려 두는 받침입니다.',
         '케이블 세 줄의 간격과 지름을 확인하며 조정하는 시작안입니다.',
         ['케이블의 실제 바깥 지름과 받침을 놓을 공간을 측정하세요.'], cable_limits,
         dict(width=50, depth=18, height=12, wall=2, bottom=2, slots=3,
              cable_diameter=6, fit_clearance=0.3)),
        ('five-cable-rest', '다섯 줄 케이블 받침', 'cables', 'cable_comb',
         '위가 열린 다섯 개의 홈에 케이블을 올려 두는 받침입니다.',
         '여러 케이블을 나란히 놓을 때 필요한 폭을 비교하는 시작안입니다.',
         ['케이블 다섯 줄의 바깥 지름과 받침을 놓을 공간을 측정하세요.'], cable_limits,
         dict(width=80, depth=18, height=12, wall=2, bottom=2, slots=5,
              cable_diameter=6, fit_clearance=0.3)),
        ('round-insert-frame', '원형 사진 인셋 프레임', 'display', 'magnet_frame',
         '원형 사진이나 얇은 원판을 놓을 포켓이 있는 프레임입니다.',
         '원형 인셋의 지름과 두께에 맞춰 포켓 치수를 조정하는 시작안입니다.',
         ['넣을 원판의 실제 지름·두께와 프레임을 놓을 공간을 측정하세요.'], frame_limits,
         dict(width=65, depth=65, height=7, wall=2, bottom=2, inset_diameter=52,
              inset_depth=2, fit_clearance=0.3)),
    ]
    projects = []
    for project_id, title, purpose, template, description, reason, measurements, limits, values in definitions:
        recipe = {
            'id': project_id, 'title': title, 'purpose': purpose, 'description': description,
            'reason': reason, 'measurements': list(measurements),
            'limits': common_limits + limits, 'template': template,
            'parameters': GeometryRequest(template=template, **values).model_dump(mode='json'),
            'source': {'kind': 'repository_original',
                       'repository': 'https://github.com/uulab-official/3d-printer-agent',
                       'path': 'print_agent/geometry.py', 'creator': 'uulab-official', 'license': 'MIT'},
        }
        canonical = json.dumps(recipe, ensure_ascii=False, sort_keys=True,
                               separators=(',', ':'), allow_nan=False).encode('utf-8')
        projects.append({**recipe, 'recipe_sha256': hashlib.sha256(canonical).hexdigest()})
    return {'schema_version': 1,
            'purposes': [{'id': 'all', 'title': '전체'},
                         {'id': 'organization', 'title': '책상·서랍 정리'},
                         {'id': 'cables', 'title': '케이블 정리'},
                         {'id': 'display', 'title': '사진·장식'}],
            'projects': projects}


def recommend_projects(request: DiscoveryRequest) -> dict:
    """Compare only supplied placement axes, trying original then horizontal rotation."""
    space = request.available_space.model_dump(mode='json')
    checked_axes = [axis for axis in ('width', 'depth', 'height') if space[axis] is not None]
    candidates = [project for project in project_catalog()['projects']
                  if request.purpose == 'all' or project['purpose'] == request.purpose]
    matches = []
    for project in candidates:
        dimensions = {axis: project['parameters'][axis] for axis in ('width', 'depth', 'height')}
        status, orientation = 'not_checked', None
        if checked_axes:
            if all(dimensions[axis] <= space[axis] for axis in checked_axes):
                status, orientation = 'fits', 'original'
            else:
                dimensions = {'width': dimensions['depth'], 'depth': dimensions['width'],
                              'height': dimensions['height']}
                if not all(dimensions[axis] <= space[axis] for axis in checked_axes):
                    continue
                status, orientation = 'fits_rotated', 'rotated_90'
        matches.append({'project': project,
                        'space_fit': {'status': status, 'orientation': orientation,
                                      'checked_axes': list(checked_axes), 'dimensions_mm': dimensions},
                        'reason': project['reason']})
    return {'schema_version': 1, 'query': request.model_dump(mode='json'),
            'total_in_purpose': len(candidates), 'excluded_count': len(candidates) - len(matches),
            'matches': matches,
            'limits': ['사용할 공간과 시작안의 바깥 치수만 비교합니다. 프린터 베드 호환성이나 실물 맞춤을 검증하지 않습니다.',
                       '가로·세로만 90도 돌려 비교하며 높이는 바꾸지 않습니다. 입력하지 않은 축은 확인하지 않습니다.',
                       '치수를 편집하면 이 비교 결과가 유지되지 않습니다. 결과가 없으면 조건을 바꾸거나 기본 템플릿을 편집하세요.']}


def resolve_project_selection(selection: ProjectSelection, spec: GeometryRequest) -> dict:
    """Resolve provenance from the current server recipe before a job is reserved."""
    card = next((project for project in project_catalog()['projects']
                 if project['id'] == selection.id), None)
    if card is None:
        raise ValueError('선택한 시작안을 찾을 수 없습니다.')
    if selection.recipe_sha256 != card['recipe_sha256']:
        raise StaleProjectSelection('시작안이 변경되었습니다. 현재 시작안을 다시 선택하거나 출처 연결을 해제하세요.')
    if spec.template != card['template']:
        raise ValueError('선택한 시작안과 모델 템플릿이 일치하지 않습니다.')
    actual = spec.model_dump(mode='json')
    changed = sorted(name for name, value in card['parameters'].items() if actual[name] != value)
    recipe = {key: value for key, value in card.items() if key != 'recipe_sha256'}
    return {'kind': 'project_catalog', 'schema_version': 1, 'project_id': card['id'],
            'recipe_sha256': card['recipe_sha256'], 'recipe': recipe,
            'customized': bool(changed), 'changed_parameters': changed}
