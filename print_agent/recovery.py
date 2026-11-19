"""What to try after a failed print: reasons the person reports, and next steps.

Pure and advisory. Slicer and equipment steps are general guidance, not measured
diagnoses. Geometry steps are written as the same sentences the contextual edit
parser accepts, and a step is offered only when that sentence yields a valid,
in-range edit of the current model; it is then reviewed and applied by the person
through the existing edit flow, never changed automatically.
"""
from __future__ import annotations

from .model_edits import plan_model_edit
from .printer_reports import recovery_item

REASONS = {
    'first_layer': '첫 레이어가 안 붙음',
    'warping': '모서리가 들뜨거나 휨',
    'stringing': '거미줄·실 날림',
    'too_tight': '끼울 물건이 안 들어감(너무 꽉)',
    'too_loose': '헐거움',
    'weak': '약하거나 부러짐',
    'text_blurry': '글자 획이 뭉개짐',
    'under_extrusion': '압출 부족·구멍 난 벽',
    'mid_failure': '출력 중간에 떨어지거나 엉킴',
}
MAX_REASONS = 6

_ADVICE = {
    'first_layer': ['출력판을 IPA(이소프로필 알코올)로 닦아 기름·지문을 없애세요.',
                    '슬라이스 설정의 플레이트 종류가 실제 출력판과 같은지 확인하세요.',
                    '첫 레이어 속도를 낮추거나, 재료 권장 범위 안에서 베드 온도를 5°C 올려 보세요.',
                    '바닥 면적이 작으면 슬라이서에서 브림(brim)을 추가하세요.'],
    'warping': ['슬라이서에서 브림을 추가하세요.', '에어컨·창문 바람을 막고, ABS·ASA는 인클로저를 닫고 출력하세요.',
                '출력판 청소와 베드 온도(재료 권장 범위)를 확인하세요.'],
    'stringing': ['노즐 온도를 재료 권장 범위 안에서 5~10°C 낮춰 보세요.', '필라멘트를 건조하세요(습기를 먹으면 실이 많이 납니다).',
                  '슬라이서의 리트랙션 설정을 확인하세요.'],
    'too_tight': ['프린터와 재료에 따라 실제 치수가 조금 작게 나올 수 있습니다. 여유를 늘린 모델로 다시 출력해 보세요.'],
    'too_loose': ['여유를 조금 줄인 모델로 다시 출력해 보세요. 한 번에 0.1 mm씩 바꾸는 것이 안전합니다.'],
    'weak': ['벽 루프(wall loops)와 내부 채움(infill)을 늘리면 같은 모델도 튼튼해집니다.',
             '힘을 받는 방향이 레이어 방향과 나란하면 약합니다. 놓는 방향을 바꿔 보세요.'],
    'text_blurry': ['글자를 키우면 획이 굵어져 또렷하게 나옵니다. 0.2 mm 노즐을 쓰면 작은 글자에 유리합니다.'],
    'under_extrusion': ['필라멘트를 건조하고, 노즐 막힘이 없는지 확인하세요.',
                        '슬라이서의 최대 체적 속도(max volumetric speed)를 낮춰 보세요.',
                        '필라멘트가 엉키거나 스풀이 걸리지 않았는지 확인하세요.'],
    'mid_failure': ['출력물이 출력판에서 떨어졌다면 “첫 레이어가 안 붙음” 조치를 먼저 해 보세요.',
                    '형상 점검의 오버행 항목을 확인하고, 필요하면 서포트를 켜세요.',
                    '노즐이 출력물에 부딪혔다면 휨(들뜸)이 없는지 확인하세요.'],
}


def _edit_sentences(reason: str, parameters: dict) -> list[str]:
    template = parameters.get('template')
    has_clearance = template in ('cable_comb', 'magnet_frame', 'phone_stand')
    if template == 'keycap':
        # The cross hole is the fitted feature; the top is the thinnest printed area.
        return {'too_tight': ['십자 여유 0.05mm 늘려줘'], 'too_loose': ['십자 여유 0.05mm 줄여줘'],
                'weak': ['옆벽 두께 0.3mm 늘려줘'], 'text_blurry': ['글자 크기 1mm 늘려줘']}.get(reason, [])
    if reason == 'too_tight':
        if has_clearance:
            return ['여유 0.2mm 늘려줘']
        if template == 'name_tag':
            return ['구멍 지름 0.3mm 늘려줘']
        if template == 'tray':
            return ['가로 2mm 늘려줘, 세로 2mm 늘려줘']
    if reason == 'too_loose' and has_clearance:
        return ['여유 0.1mm 줄여줘']
    if reason == 'weak':
        return ['받침 두께 0.5mm 늘려줘'] if template == 'name_tag' else ['벽 두께 0.4mm 늘려줘']
    if reason == 'text_blurry' and template == 'name_tag':
        return ['글자 크기 2mm 늘려줘']
    return []


def _model_edit(reason: str, parameters: dict) -> dict | None:
    for sentence in _edit_sentences(reason, parameters):
        try:
            planned = plan_model_edit(sentence, parameters)
        except ValueError:
            continue
        if planned.get('status') == 'ready':
            return {'text': sentence, 'changes': planned['review']['changes']}
    return None


def validate_reasons(result: str, reasons) -> list[str]:
    if reasons is None:
        return []
    if not isinstance(reasons, list) or len(reasons) > MAX_REASONS or any(reason not in REASONS for reason in reasons):
        raise ValueError(f'실패 원인은 정해진 항목에서 최대 {MAX_REASONS}개까지 고를 수 있습니다.')
    if reasons and result != 'failure':
        raise ValueError('실패 원인은 “출력 실패”를 기록할 때만 고를 수 있습니다.')
    return list(dict.fromkeys(reasons))


def recovery_plan(parameters: dict | None, reasons: list[str], printer_report: dict | None = None) -> dict:
    """Next steps for each reported reason, with a reviewable model edit when one applies.

    A failure the printer itself reported for this job comes first, with its codes as reported.
    """
    reported = recovery_item(printer_report)
    items = [reported] if reported else []
    for reason in reasons:
        if reason not in REASONS:
            continue
        edit = _model_edit(reason, parameters) if isinstance(parameters, dict) else None
        items.append({'reason': reason, 'label': REASONS[reason], 'actions': list(_ADVICE[reason]), 'model_edit': edit})
    return {'schema_version': 1, 'items': items,
            'scope': '사용자가 고른 원인에 맞춘 일반적인 다음 조치입니다. 측정한 진단이 아니며, 모델 수정은 검토한 뒤 직접 적용합니다.'}
