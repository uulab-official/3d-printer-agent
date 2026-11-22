"""Plain-language explanations of 3D-printing words the app uses, and a first-run guide.

The glossary explains words; it does not give settings, temperatures or product claims.
Where a value depends on the printer, filament or model, the entry says so and points to
the place in the app where the person's own value is reviewed. Every entry is written for
this project and states how the app uses the word.
"""
from __future__ import annotations

import copy
import re

CATEGORIES = {
    'material': '재료',
    'model': '모델·형상',
    'slice': '슬라이스',
    'printer': '프린터',
    'file': '파일',
}

# Views a term or step may open; must match the page's data-view names.
VIEWS = ('models', 'imports', 'profiles', 'inventory', 'offers', 'printers', 'history')

TERMS = [
    # --- Material ---------------------------------------------------------------------
    {'id': 'pla', 'term': 'PLA', 'aka': 'Polylactic acid', 'category': 'material',
     'short': '가장 흔히 쓰는 출력하기 쉬운 필라멘트입니다.',
     'detail': '휘어짐이 적어 처음 출력하기 좋지만, 뜨거운 차 안처럼 열을 받는 곳에서는 변형될 수 있습니다. 이 앱의 형상 점검은 재료와 상관없이 같은 기준을 씁니다.',
     'related': ['petg', 'filament_profile'], 'view': 'profiles'},
    {'id': 'petg', 'term': 'PETG', 'aka': 'Polyethylene terephthalate glycol', 'category': 'material',
     'short': 'PLA보다 질기고 열과 물에 강한 필라멘트입니다.',
     'detail': '실처럼 늘어지는 줄(스트링)이 생기기 쉬워 온도·리트랙션 설정이 중요합니다. 설정값은 재료 설정 화면에서 내 필라멘트 파일로 확인합니다.',
     'related': ['pla', 'filament_profile'], 'view': 'profiles'},
    {'id': 'abs_asa', 'term': 'ABS · ASA', 'aka': 'ABS, ASA', 'category': 'material',
     'short': '열에 강하지만 식으면서 수축해 뒤틀리기 쉬운 필라멘트입니다.',
     'detail': '닫힌 프린터에서 출력하는 편이 안정적이고, 출력 중 냄새가 나므로 환기가 필요합니다. ASA는 햇빛에 더 강합니다.',
     'related': ['warping', 'brim'], 'view': 'profiles'},
    {'id': 'tpu', 'term': 'TPU', 'aka': 'Thermoplastic polyurethane', 'category': 'material',
     'short': '고무처럼 휘어지는 유연한 필라멘트입니다.',
     'detail': '천천히 출력해야 하고, 장치에 따라 AMS로 공급하지 못할 수 있습니다. 사용 가능 여부는 프린터와 필라멘트 제조사 안내를 확인하세요.',
     'related': ['ams'], 'view': 'profiles'},
    {'id': 'fiber_filled', 'term': '섬유 강화 필라멘트', 'aka': '-CF, -GF', 'category': 'material',
     'short': '탄소섬유(CF)나 유리섬유(GF)를 섞어 단단하게 만든 필라멘트입니다.',
     'detail': '섬유가 노즐을 빨리 닳게 하므로 경화강 노즐을 권합니다. 이 앱은 프린터가 스테인리스·황동 노즐을 보고하면 전송 전에 경고합니다.',
     'related': ['nozzle'], 'view': 'printers'},
    {'id': 'drying', 'term': '필라멘트 건조', 'aka': 'Drying', 'category': 'material',
     'short': '공기 중 습기를 먹은 필라멘트를 말리는 일입니다.',
     'detail': '습기를 먹으면 출력 중 거품·탁탁 소리·거친 표면이 생길 수 있습니다. 재고 화면에서 스풀 상태를 “건조 중”으로 기록할 수 있습니다.',
     'related': ['spool'], 'view': 'inventory'},
    {'id': 'spool', 'term': '스풀', 'aka': 'Spool', 'category': 'material',
     'short': '필라멘트가 감겨 있는 릴입니다.',
     'detail': '“1 kg 스풀”은 보통 필라멘트 무게이고 빈 릴 무게는 따로입니다. 재고 화면은 저울로 잰 전체 무게에서 빈 스풀 무게를 빼 남은 양을 계산합니다.',
     'related': ['drying', 'estimate'], 'view': 'inventory'},

    # --- Model and geometry ---------------------------------------------------------------
    {'id': 'wall_thickness', 'term': '벽 두께', 'aka': 'Wall thickness', 'category': 'model',
     'short': '모델 벽이 실제로 얼마나 두꺼운지입니다.',
     'detail': '노즐이 한 번 지나가며 만드는 선(압출 폭)보다 얇으면 제대로 출력되지 않습니다. 이 앱은 0.4 mm 노즐 기준으로 가장 얇은 부분이 몇 줄인지 점검합니다.',
     'related': ['extrusion_width', 'nozzle'], 'view': 'models'},
    {'id': 'overhang', 'term': '돌출부', 'aka': 'Overhang', 'category': 'model',
     'short': '아래에 받칠 것 없이 공중으로 튀어나온 부분입니다.',
     'detail': '바닥에서 많이 기울어질수록 처지기 쉬워 서포트가 필요할 수 있습니다. 가진 모델 점검은 돌출부 면적이 작은 출력 방향을 먼저 추천합니다.',
     'related': ['support', 'bridge', 'orientation'], 'view': 'imports'},
    {'id': 'bridge', 'term': '브리지', 'aka': 'Bridge', 'category': 'model',
     'short': '양쪽 기둥 사이를 공중으로 가로지르는 부분입니다.',
     'detail': '짧은 브리지는 서포트 없이도 출력되지만 길어질수록 처집니다.',
     'related': ['overhang', 'support'], 'view': 'models'},
    {'id': 'clearance', 'term': '끼움 여유', 'aka': 'Clearance, tolerance', 'category': 'model',
     'short': '서로 끼우는 두 부품 사이에 일부러 두는 틈입니다.',
     'detail': '출력물은 설계보다 조금 커지거나 작아지므로 꽉 맞는 치수로 만들면 끼워지지 않을 수 있습니다. 원판 받침의 “지름 여유”가 이 값입니다.',
     'related': ['shrinkage'], 'view': 'models'},
    {'id': 'shrinkage', 'term': '수축', 'aka': 'Shrinkage', 'category': 'model',
     'short': '녹은 플라스틱이 식으면서 조금 줄어드는 현상입니다.',
     'detail': '재료마다 정도가 달라 정확한 치수가 필요한 부품은 시험 출력으로 확인하는 편이 안전합니다.',
     'related': ['warping', 'clearance'], 'view': None},
    {'id': 'warping', 'term': '뒤틀림', 'aka': 'Warping', 'category': 'model',
     'short': '출력물 모서리가 식으면서 바닥에서 들뜨는 현상입니다.',
     'detail': '넓고 평평한 모델과 ABS 같은 재료에서 흔합니다. 바닥 접촉면을 넓히는 브림이 도움이 될 수 있습니다.',
     'related': ['brim', 'abs_asa', 'first_layer'], 'view': 'history'},
    {'id': 'orientation', 'term': '출력 방향', 'aka': 'Orientation', 'category': 'model',
     'short': '모델을 어느 면이 바닥에 오도록 놓고 출력할지입니다.',
     'detail': '방향에 따라 서포트 양, 강도, 표면이 달라집니다. 가진 모델 점검 화면이 여러 방향을 비교해 보여 줍니다.',
     'related': ['overhang', 'first_layer'], 'view': 'imports'},
    {'id': 'first_layer', 'term': '바닥 접촉면', 'aka': 'Bed contact', 'category': 'model',
     'short': '첫 층이 출력판에 닿는 면입니다.',
     'detail': '넓을수록 출력 중 떨어지지 않고 안정적입니다. 첫 층이 잘 붙지 않으면 출력 실패로 이어지기 쉽습니다.',
     'related': ['brim', 'warping', 'plate'], 'view': 'imports'},

    # --- Slicing ----------------------------------------------------------------------
    {'id': 'slice', 'term': '슬라이스', 'aka': 'Slicing', 'category': 'slice',
     'short': '3D 모델을 얇은 층으로 잘라 프린터가 따라갈 경로로 바꾸는 일입니다.',
     'detail': '이 앱은 이 PC에 설치한 Bambu Studio로 슬라이스하고, 결과 파일을 확인한 뒤에만 “슬라이스됨”으로 표시합니다. 슬라이스 성공은 실제 출력 성공과 다릅니다.',
     'related': ['gcode_3mf', 'process_profile', 'estimate'], 'view': 'models'},
    {'id': 'layer_height', 'term': '레이어 높이', 'aka': 'Layer height', 'category': 'slice',
     'short': '한 층의 두께입니다.',
     'detail': '얇을수록 표면이 매끈하지만 출력 시간이 길어집니다. 슬라이스 비교의 “곱게”는 레이어를 얇게, “빠르게”는 두껍게 바꿉니다.',
     'related': ['slice', 'process_profile'], 'view': 'models'},
    {'id': 'infill', 'term': '내부 채움', 'aka': 'Infill', 'category': 'slice',
     'short': '출력물 안쪽을 얼마나 채울지입니다.',
     'detail': '속을 꽉 채우지 않고 격자 같은 무늬로 일부만 채웁니다. 높이면 튼튼해지지만 재료와 시간이 늘어납니다.',
     'related': ['wall_loops', 'process_profile'], 'view': 'models'},
    {'id': 'wall_loops', 'term': '벽 줄 수', 'aka': 'Wall loops, perimeters', 'category': 'slice',
     'short': '바깥 벽을 몇 줄로 두를지 정하는 슬라이스 설정입니다.',
     'detail': '모델의 벽 두께와 다릅니다. 줄 수를 늘리면 측면이 튼튼해집니다. 슬라이스 비교의 “튼튼하게”가 이 값과 내부 채움을 올립니다.',
     'related': ['infill', 'wall_thickness'], 'view': 'models'},
    {'id': 'support', 'term': '서포트', 'aka': 'Support', 'category': 'slice',
     'short': '돌출부가 처지지 않도록 아래에 임시로 세우는 받침입니다.',
     'detail': '출력 뒤 떼어내야 하고 닿은 면이 거칠어집니다. 출력 방향을 바꿔 서포트를 줄일 수 있는지 먼저 보는 편이 좋습니다.',
     'related': ['overhang', 'orientation'], 'view': 'imports'},
    {'id': 'brim', 'term': '브림', 'aka': 'Brim', 'category': 'slice',
     'short': '첫 층 둘레에 얇게 덧대어 바닥 접촉면을 넓히는 테두리입니다.',
     'detail': '모서리 들뜸을 줄이는 데 쓰고, 출력 뒤 떼어냅니다.',
     'related': ['warping', 'first_layer'], 'view': 'models'},
    {'id': 'plate', 'term': '플레이트', 'aka': 'Build plate', 'category': 'slice',
     'short': '모델을 올려 출력하는 판입니다. 슬라이서에서는 판 종류 설정이기도 합니다.',
     'detail': '판 표면(쿨 플레이트·텍스처 PEI 등)에 따라 바닥 온도와 접착이 달라집니다. 슬라이스할 때 실제 장착한 판을 골라야 합니다.',
     'related': ['first_layer', 'build_volume'], 'view': 'models'},
    {'id': 'process_profile', 'term': '공정 설정', 'aka': 'Process preset', 'category': 'slice',
     'short': '레이어 높이·벽·내부 채움·속도처럼 출력 방식을 정한 슬라이서 설정입니다.',
     'detail': '프린터 설정, 필라멘트 설정과 함께 세 가지가 한 묶음으로 슬라이스에 쓰입니다. 이 앱은 Studio에서 내보낸 파일 값을 그대로 묶고, 없는 값을 추측해 채우지 않습니다.',
     'related': ['filament_profile', 'machine_profile', 'slice'], 'view': 'models'},
    {'id': 'filament_profile', 'term': '필라멘트 설정', 'aka': 'Filament preset', 'category': 'slice',
     'short': '노즐 온도·바닥 온도·흐름 비율처럼 재료에 맞춘 슬라이서 설정입니다.',
     'detail': '같은 PLA라도 제품마다 값이 다를 수 있습니다. 재료 설정 화면에서 내 파일의 값을 검토하고 보정 결과를 기록할 수 있습니다.',
     'related': ['process_profile', 'pla', 'petg'], 'view': 'profiles'},
    {'id': 'machine_profile', 'term': '프린터 설정', 'aka': 'Machine preset', 'category': 'slice',
     'short': '프린터 기종·노즐 지름·출력 공간을 정한 슬라이서 설정입니다.',
     'detail': '다른 기종용으로 슬라이스한 파일은 이 앱이 프린터로 보내지 않습니다.',
     'related': ['nozzle', 'build_volume'], 'view': 'models'},
    {'id': 'estimate', 'term': '슬라이서 예상치', 'aka': 'Estimate', 'category': 'slice',
     'short': '슬라이서가 계산한 예상 출력 시간과 필라멘트 사용량입니다.',
     'detail': '실제 값과 다를 수 있습니다. 재고에서 뺄 때도 이 값을 기본으로 채우지만 직접 고칠 수 있습니다.',
     'related': ['slice', 'spool'], 'view': 'inventory'},

    # --- Printer ----------------------------------------------------------------------
    {'id': 'nozzle', 'term': '노즐', 'aka': 'Nozzle', 'category': 'printer',
     'short': '녹은 필라멘트가 나오는 끝부분입니다. 지름은 보통 0.4 mm입니다.',
     'detail': '지름이 크면 빠르지만 거칠고, 작으면 섬세하지만 느립니다. 프린터 상태 화면은 프린터가 보고한 노즐 지름과 재질을 보여 줍니다.',
     'related': ['extrusion_width', 'fiber_filled'], 'view': 'printers'},
    {'id': 'extrusion_width', 'term': '압출 폭', 'aka': 'Line width', 'category': 'printer',
     'short': '노즐이 한 번 지나가며 그리는 선의 폭입니다.',
     'detail': '보통 노즐 지름보다 조금 넓습니다. 이 앱의 형상 점검은 0.4 mm 노즐에서 약 0.42 mm로 계산합니다.',
     'related': ['nozzle', 'wall_thickness'], 'view': 'models'},
    {'id': 'ams', 'term': 'AMS', 'aka': 'Automatic Material System', 'category': 'printer',
     'short': '여러 스풀을 넣어 두고 자동으로 바꿔 쓰는 Bambu Lab 장치입니다.',
     'detail': '칸(슬롯)마다 다른 색이나 재료를 넣을 수 있습니다. 프린터 상태 화면은 프린터가 보고한 칸별 재료를 읽기만 하며, 재고 스풀과 자동으로 연결하지는 않습니다.',
     'related': ['spool', 'tpu'], 'view': 'printers'},
    {'id': 'build_volume', 'term': '출력 공간', 'aka': 'Build volume', 'category': 'printer',
     'short': '프린터가 한 번에 출력할 수 있는 가로·세로·높이 한계입니다.',
     'detail': '이 앱은 슬라이서 설정 파일에 기록된 출력 공간과 모델 크기를 비교합니다. 실제 장비 확인은 아닙니다.',
     'related': ['machine_profile', 'plate'], 'view': 'models'},
    {'id': 'lan_mode', 'term': 'LAN 연결', 'aka': 'LAN, access code', 'category': 'printer',
     'short': '같은 공유기에 연결된 프린터와 클라우드를 거치지 않고 직접 주고받는 방식입니다.',
     'detail': '프린터 화면에 표시된 IP 주소와 액세스 코드가 필요합니다. 이 앱은 액세스 코드를 저장하지 않고, 상태를 읽거나 사람이 확인한 파일만 보냅니다.',
     'related': ['ams', 'klipper'], 'view': 'printers'},
    {'id': 'klipper', 'term': 'Klipper·Moonraker', 'aka': 'Klipper, Moonraker, Fluidd, Mainsail', 'category': 'printer',
     'short': 'Snapmaker U1·Voron 등 많은 프린터가 쓰는 펌웨어(Klipper)와 그 상태를 알려 주는 웹 API(Moonraker)입니다.',
     'detail': '같은 네트워크에서 프린터 IP와 포트(보통 7125)로 연결합니다. 인증을 켠 프린터는 API 키가 필요합니다. 이 앱은 상태만 읽고 API 키를 저장하지 않습니다.',
     'related': ['lan_mode'], 'view': 'printers'},

    # --- Files ------------------------------------------------------------------------
    {'id': 'stl', 'term': 'STL', 'aka': 'STL file', 'category': 'file',
     'short': '삼각형 면만 담은 가장 흔한 3D 모델 파일입니다.',
     'detail': '색·단위·출력 설정은 담지 않습니다. 가진 모델 점검 화면에서 불러올 수 있으며 원본은 바꾸지 않습니다.',
     'related': ['three_mf', 'watertight'], 'view': 'imports'},
    {'id': 'three_mf', 'term': '3MF', 'aka': '3D Manufacturing Format', 'category': 'file',
     'short': '모델과 함께 단위·색·배치 정보를 담는 3D 파일입니다.',
     'detail': 'Bambu Studio 프로젝트도 3MF 형식입니다. 이 앱이 만든 모델은 3MF로 내려받아 Studio에서 바로 열 수 있습니다.',
     'related': ['stl', 'gcode_3mf'], 'view': 'models'},
    {'id': 'gcode_3mf', 'term': '.gcode.3mf', 'aka': 'Sliced 3MF', 'category': 'file',
     'short': '슬라이스가 끝나 프린터가 바로 출력할 수 있는 파일입니다.',
     'detail': '안에 프린터 명령(G-code)과 예상 시간·사용량이 들어 있습니다. 이 앱은 이 파일만 프린터로 보냅니다.',
     'related': ['slice', 'three_mf', 'estimate'], 'view': 'models'},
    {'id': 'watertight', 'term': '닫힌 메시', 'aka': 'Watertight, manifold', 'category': 'file',
     'short': '구멍이나 끊긴 면 없이 안팎이 분명히 나뉜 모델입니다.',
     'detail': '닫히지 않은 모델은 슬라이서가 잘못 채우거나 일부를 빼먹을 수 있습니다. 가진 모델 점검은 열린 모서리를 세어 알려 줍니다.',
     'related': ['stl'], 'view': 'imports'},
]

ONBOARDING = [
    {'id': 'make', 'title': '만들 것 고르기', 'view': 'models',
     'text': '용도에서 시작점을 고르거나 원하는 것을 문장으로 적고, 놓을 곳을 실측한 치수로 모델을 만듭니다. 가진 STL·3MF가 있다면 “가진 모델 점검”에서 불러옵니다.'},
    {'id': 'check', 'title': '형상 점검 보기', 'view': 'models',
     'text': '너무 얇은 벽이나 처지기 쉬운 돌출부가 있는지 미리 봅니다. 점검은 참고용이고 생성을 막지 않습니다.'},
    {'id': 'settings', 'title': '내 설정 넣기', 'view': 'profiles',
     'text': 'Bambu Studio에서 내보낸 프린터·필라멘트·공정 설정을 넣습니다. 앱은 값을 추측해 채우지 않고 파일 그대로 씁니다.'},
    {'id': 'slice', 'title': '슬라이스하고 보내기', 'view': 'models',
     'text': '이 PC의 Bambu Studio로 슬라이스해 예상 시간·사용량을 확인하고, 원하면 같은 공유기의 프린터로 보냅니다.'},
    {'id': 'record', 'title': '결과 기록하기', 'view': 'history',
     'text': '실제로 출력한 결과와 실패 이유를 남기면 다음 수정에 쓰입니다. 쓴 필라멘트는 재고에서 뺄 수 있습니다.'},
]

_ID = re.compile(r'[a-z][a-z0-9_]{1,30}')


def glossary() -> dict:
    """The glossary and first-run guide as sent to the browser: validated and copied."""
    ids = [term['id'] for term in TERMS]
    if len(ids) != len(set(ids)):
        raise ValueError('용어 ID가 중복됐습니다.')
    for term in TERMS:
        if _ID.fullmatch(term['id']) is None or term['category'] not in CATEGORIES:
            raise ValueError(f'잘못된 용어 항목: {term["id"]}')
        if set(term['related']) - set(ids) or term['id'] in term['related']:
            raise ValueError(f'잘못된 관련 용어: {term["id"]}')
        if term['view'] is not None and term['view'] not in VIEWS:
            raise ValueError(f'알 수 없는 화면: {term["id"]}')
    for step in ONBOARDING:
        if step['view'] not in VIEWS:
            raise ValueError(f'알 수 없는 화면: {step["id"]}')
    return {'schema_version': 1, 'categories': dict(CATEGORIES), 'terms': copy.deepcopy(TERMS),
            'onboarding': copy.deepcopy(ONBOARDING),
            'scope': '이 앱에서 쓰는 말을 쉽게 풀어 쓴 설명입니다. 권장 온도나 설정값은 프린터·필라멘트·모델마다 다르니 내 설정 파일과 제조사 안내를 확인하세요.'}
