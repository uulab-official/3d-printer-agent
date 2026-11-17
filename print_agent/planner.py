"""Constrained planning. Both rule and LLM modes propose typed template parameters only."""
import asyncio
from decimal import Decimal, localcontext
import json
import math
import os
import re
from urllib.parse import urlsplit

import httpx
from pydantic import ValidationError

from .geometry_rules import _validate_geometry
from .schemas import PALETTE, GeometryRequest


DEFAULTS = {
    'tray': {'width':120,'depth':80,'height':35,'wall':2,'bottom':2,'dividers':0},
    'cable_comb': {'width':80,'depth':18,'height':12,'wall':2,'bottom':2,'slots':5,'cable_diameter':6,'fit_clearance':0.3},
    'magnet_frame': {'width':65,'depth':65,'height':7,'wall':2,'bottom':2,'inset_diameter':52,'inset_depth':2,'fit_clearance':0.3},
    'phone_stand': {'width':70,'depth':80,'height':90,'wall':4,'bottom':4,'lean_angle':65,'device_thickness':12,'lip_height':12,'fit_clearance':1},
    'name_tag': {'text':'MINSU','text_size':12,'text_depth':2,'wall':3,'bottom':2,'hole_diameter':4},
    'wall_hook': {'width':20,'depth':35,'height':50,'wall':4,'bottom':4,'hole_diameter':4,'lip_height':10},
}
COLOR_WORDS = {
    'white': r'흰색|하얀색|하얀|하양|흰|화이트|white',
    'black': r'검정색|검은색|까만색|검정|검은|까만|블랙|black',
    'gray': r'회색|그레이|grey|gray',
    'red': r'빨간색|빨강색|빨간|빨강|레드|red',
    'orange': r'주황색|주황|오렌지|orange',
    'yellow': r'노란색|노랑색|노란|노랑|옐로우|옐로|yellow',
    'green': r'초록색|초록|녹색|그린|green',
    'blue': r'파란색|파랑색|파란|파랑|블루|blue',
    'purple': r'보라색|보라|퍼플|purple',
    'pink': r'분홍색|분홍|핑크|pink',
    'brown': r'갈색|브라운|brown',
}


def _bounded(words: str) -> str:
    # English names must be whole words ("red" is not inside "shared").
    return '|'.join(f'(?<![a-z]){word}(?![a-z])' if word.isascii() else word for word in words.split('|'))


_COLOR = '(?P<color>' + '|'.join(f'(?P<c_{key}>{_bounded(words)})' for key, words in COLOR_WORDS.items()) + ')'
_COLOR_TAIL = r'(?:\s*색(?:깔|상)?)?(?:\s*(?:으로|로))?(?:\s*(?:(?:바꿔|변경해|설정해|칠해|해|만들어)(?:\s*(?:줘|주세요))?|바꾸고|칠하고|하고))?'
_ACCENT_PART = r'(?:글자|글씨|문자|텍스트)'
_BODY_PART = r'(?:받침판|받침|바탕|배경|몸체|본체|전체|판|색깔|색상|색)'
_PARTICLE = r'\s*(?:색(?:깔|상)?)?\s*(?:은|는|을|를|이|가|:|=)?\s*'
_COLOR_PATTERNS = (
    ('accent_color', re.compile(_ACCENT_PART + _PARTICLE + _COLOR + _COLOR_TAIL, re.I)),
    ('accent_color', re.compile(_COLOR + r'(?:\s*색)?\s*(?:의\s*)?' + _ACCENT_PART + r'(?:\s*(?:으로|로))?', re.I)),
    ('color', re.compile(_BODY_PART + _PARTICLE + _COLOR + _COLOR_TAIL, re.I)),
    ('color', re.compile(_COLOR + _COLOR_TAIL, re.I)),
)


def color_label(key: str) -> str:
    return PALETTE[key][0] if key in PALETTE else key


def extract_colors(text: str) -> tuple[dict, str]:
    """Read named filament colours. Returns the fields and the text with those phrases removed.

    "글자" phrases set the letter colour; every other colour word sets the model colour.
    Two different colours for the same part raise ValueError instead of picking one."""
    found: dict = {}
    def take(field):
        def replace(match):
            key = next(name[2:] for name, value in match.groupdict().items() if name.startswith('c_') and value)
            if found.get(field, key) != key:
                raise ValueError(f'{"글자" if field == "accent_color" else "모델"} 색이 여러 개입니다({color_label(found[field])}, {color_label(key)}). 하나만 알려주세요.')
            found[field] = key
            return ' '
        return replace
    for field, pattern in _COLOR_PATTERNS:
        text = pattern.sub(take(field), text)
    return found, text


def _with_colors(result: dict, colors: dict) -> dict:
    if result.get('status') != 'ready' or not colors:
        return result
    try:
        parameters = GeometryRequest(**{**result['parameters'], **colors}).model_dump()
    except ValidationError as exc:
        message = next((str(error.get('ctx', {}).get('error', '')) for error in exc.errors() if error.get('ctx')), '')
        return _question(message or '지원하지 않는 색입니다.')
    named = ', '.join(('글자 ' if field == 'accent_color' else '모델 ') + color_label(key) for field, key in sorted(colors.items(), reverse=True))
    return {**result, 'parameters': parameters,
            'assumptions': result['assumptions'] + [f'색: {named}. 화면 색은 비슷하게 보여 줄 뿐이며 실제 필라멘트 색과 다를 수 있습니다.']}


KEYCHAIN_WORDS = ('키링','키홀더','열쇠고리','이름표','네임택','name tag','keychain','key ring')
LABELS = {'tray':'수납 트레이','cable_comb':'케이블 정리 받침','magnet_frame':'원형 인셋 프레임','phone_stand':'휴대폰 거치대','name_tag':'이름 키링','wall_hook':'벽걸이 후크'}
HOOK_WORDS = ('후크','훅','벽걸이','걸이','hook','hanger')
# Starting sizes for what is hung; the person's own numbers always win.
HOOK_RECIPES = (
    (('헤드폰','헤드셋','headphone'), {'width':30,'depth':50,'height':60,'lip_height':12}, '헤드폰 걸이는 폭 30 mm, 걸이 길이 50 mm로 시작합니다.'),
    (('가방','백팩','bag'), {'width':30,'depth':45,'height':60,'wall':5,'bottom':6,'hole_diameter':5}, '가방 걸이는 두께를 늘려(등판 5 mm, 걸이 6 mm) 시작합니다.'),
    (('수건','타월','towel'), {'width':25,'depth':45,'height':50,'lip_height':12}, '수건 걸이는 걸이 길이 45 mm로 시작합니다.'),
)
NUMBER = r'([+-]?(?:\d+(?:\.\d*)?|\.\d+))'
# Everyday names mapped to the closest supported template. Each starting size is
# announced in the plan; the user's own numbers always override it.
ITEM_RECIPES = (
    (('펜꽂이','펜 꽂이','연필꽂이','pen holder'), 'tray', {'width':80,'depth':80,'height':100,'dividers':0},
     '펜꽂이는 위가 열린 수납함(80 × 80 × 100 mm)으로 시작합니다.'),
    (('명함꽂이','명함 꽂이','명함 정리','명함'), 'tray', {'width':100,'depth':65,'height':35,'dividers':0},
     '명함 꽂이는 위가 열린 수납함(100 × 65 × 35 mm)으로 시작합니다. 실제 명함 크기를 재서 조정하세요.'),
    (('이어폰','에어팟','airpods'), 'tray', {'width':90,'depth':70,'height':30,'dividers':1},
     '이어폰 정리는 두 칸 수납함(90 × 70 × 30 mm)으로 시작합니다.'),
    (('액자','사진 프레임','포토 프레임'), 'magnet_frame', {},
     '사진 액자는 원형 사진을 넣는 인셋 프레임으로 만듭니다. 사각 액자는 아직 지원하지 않습니다.'),
    (('태블릿','아이패드','ipad','tablet'), 'phone_stand', {'width':160,'height':120,'device_thickness':10},
     '태블릿 거치대는 폭 160 mm, 높이 120 mm, 기기 두께 10 mm로 시작합니다.'),
)
STAND_WORDS = ('거치대','스탠드','stand','받침대','폰 받침','휴대폰 받침')
# "폰" alone counts as a phone, but not inside 헤드폰/이어폰/마이크폰-style words.
DEVICE_PATTERN = re.compile(r'휴대폰|핸드폰|스마트폰|아이폰|갤럭시|(?<![가-힣])폰|phone|태블릿|아이패드|ipad|tablet')
UNSUPPORTED_ITEMS = (
    (('모니터 받침','모니터 스탠드','노트북 받침','노트북 스탠드','monitor stand','laptop stand'),
     '모니터·노트북 받침대는 무게를 받치는 구조라 이 버전에서 만들지 않습니다. 휴대폰·태블릿 거치대, 수납함, 케이블 받침, 원형 인셋 프레임을 지원합니다.'),
)
HEAVY_WORDS = ('모니터','노트북','랩탑','laptop','monitor','맥북','macbook')
# A stand for some other object is not a phone stand; ask instead of guessing.
OTHER_HOLDER_WORDS = ('헤드폰','헤드셋','이어폰','카메라','게임기','컨트롤러','키보드','마우스','스피커','시계','안경','책','공구','headphone','camera')
UNIT = r'\s*(mm|cm|밀리미터|센티미터|밀리|센티)?'
MAX_LLM_RESPONSE_BYTES = 100_000
LLM_DEADLINE_SECONDS = 60


FIELD_LABELS = {
    'width':'가로','depth':'세로','height':'높이','wall':'벽 두께','bottom':'바닥 두께','dividers':'칸막이',
    'slots':'케이블 홈','cable_diameter':'케이블 지름','inset_diameter':'원판 지름','inset_depth':'포켓 깊이',
    'fit_clearance':'여유','lean_angle':'등판 각도','device_thickness':'기기 두께','lip_height':'앞턱 높이',
    'text':'글자','text_size':'글자 크기','text_depth':'글자 높이','hole_diameter':'고리 구멍 지름',
}


TEMPLATE_FIELD_LABELS = {
    'phone_stand': {'wall':'등판·앞턱 두께','fit_clearance':'홈 여유'},
    'name_tag': {'wall':'테두리 여백','bottom':'받침 두께'},
    'wall_hook': {'depth':'걸이 길이','wall':'등판·끝 턱 두께','bottom':'걸이 두께','hole_diameter':'나사 구멍 지름','lip_height':'끝 턱 높이'},
}


def _default_text(key, value, template=None):
    """One unset field as the owner sees it in the parameter panel."""
    if key == 'text':
        return f'글자 “{value}”'
    unit = '개' if key in ('slots', 'dividers') else '°' if key == 'lean_angle' else ' mm'
    label = TEMPLATE_FIELD_LABELS.get(template, {}).get(key) or FIELD_LABELS.get(key, key)
    return f'{label} {float(value):g}{unit}'


def _question(message, *, action=None, engine='template_rules'):
    result={'status':'needs_input','engine':engine,'message':message,'questions':[message],'assumptions':[]}
    if action:
        result['action']=action
    return result


def _mm(value, unit):
    # Keep user-written dimensions exact through conflict comparisons. The
    # GeometryRequest boundary converts them to public float parameters later.
    numeric_text = str(value)
    with localcontext() as context:
        context.prec = max(28, len(numeric_text) + 1)
        return Decimal(numeric_text) * (10 if unit and unit.lower() in ('cm','센티미터','센티') else 1)


def _route_existing_workflow(text: str) -> dict | None:
    """Explicit non-CAD requests navigate the same way in either planning mode."""
    lowered=text.lower()
    if any(word in lowered for word in ('필라멘트','온도','유량','profile','filament')):
        return _question('필라멘트 설정 파일과 프린터·노즐 정보를 재료 설정 화면에 넣으면, 근거와 호환 조건을 검토할 수 있습니다.',action='open_profiles')
    if any(word in lowered for word in ('가격','구매','저렴','price','buy')):
        return _question('구매 비교 화면에 상품 가격·중량·배송비를 넣어 배송비 포함 단가를 비교하세요. 실시간 가격 수집은 아직 연결되지 않았습니다.',action='open_offers')
    return None


def plan_from_text(text: str) -> dict:
    if not isinstance(text,str) or not text.strip() or len(text)>4000:
        return _question('만들 물건과 치수를 4,000자 이내로 알려주세요.')
    routed = _route_existing_workflow(text)
    if routed is not None:
        return routed
    try:
        colors, uncolored = extract_colors(text)
    except ValueError as exc:
        return _question(str(exc))
    return _with_colors(_plan_uncolored(uncolored), colors)


def _plan_uncolored(text: str) -> dict:
    lowered=text.lower()
    if any(word in lowered for word in KEYCHAIN_WORDS):
        return _plan_name_tag(text)
    hook_requested = any(word in lowered for word in HOOK_WORDS) and not any(word in lowered for word in STAND_WORDS)
    unsupported = ('뚜껑','경첩','방수','피규어','dragon','hinge','lid','손잡이','handle','곡면','둥근 모서리','rounded corner')
    if not hook_requested:
        unsupported += ('나사','screw','구멍')  # a hook has screw holes of its own
    if any(word in lowered for word in unsupported):
        return _question('이 버전은 열린 수납 트레이, 케이블 받침, 원형 인셋 프레임, 휴대폰 거치대, 이름 키링, 벽걸이 후크를 지원합니다. 지원 템플릿으로 바꿀까요?')
    for words,message in UNSUPPORTED_ITEMS:
        if any(word in lowered for word in words):
            return _question(message)
    stand_requested=any(word in lowered for word in STAND_WORDS)
    if stand_requested and any(word in lowered for word in HEAVY_WORDS):
        return _question(UNSUPPORTED_ITEMS[0][1])
    # Words that name a template win; an everyday item only supplies starting sizes
    # when it agrees with that template, or when no template word was written.
    other_template=any(word in lowered for word in ('케이블','cable','수납','트레이','정리함','프레임','액자'))
    if hook_requested and not other_template:
        template='wall_hook'
    elif stand_requested and (DEVICE_PATTERN.search(lowered) or not (other_template or any(word in lowered for word in OTHER_HOLDER_WORDS))):
        template='phone_stand'
    elif stand_requested and any(word in lowered for word in OTHER_HOLDER_WORDS):
        return _question('어떤 물건을 올릴 거치대인가요? 이 버전은 휴대폰·태블릿 거치대만 만듭니다. 헤드폰·가방처럼 거는 물건은 “헤드폰 걸이”처럼 벽걸이 후크로 만들 수 있습니다.')
    elif any(word in lowered for word in ('프레임','마그넷','magnet','frame')):
        template='magnet_frame'
    elif any(word in lowered for word in ('케이블','cable','콤','comb')):
        template='cable_comb'
    elif any(word in lowered for word in ('수납','트레이','정리함','tray','box','상자')):
        template='tray'
    else:
        template=None
    recipe=next(((recipe_template,overrides,note) for words,recipe_template,overrides,note in ITEM_RECIPES
                 if any(word in lowered for word in words) and template in (None,recipe_template)),None)
    if template=='wall_hook':
        recipe=next((('wall_hook',overrides,note) for words,overrides,note in HOOK_RECIPES if any(word in lowered for word in words)),None)
    notes=[]
    recipe_defaults={}
    if recipe:
        template,recipe_defaults,note=recipe
        notes.append(note)
    elif template is None:
        return _question('수납 트레이, 케이블 정리 받침, 원형 인셋 프레임, 휴대폰 거치대, 이름 키링, 벽걸이 후크 중 무엇을 만들까요? 가로·세로·높이는 mm 또는 cm로 적어주세요.')
    if template=='tray' and any(word in lowered for word in ('원형','동그란','원통','circular','round','cylinder')):
        return _question('수납함 템플릿은 직사각형입니다. 원형 수납함은 아직 지원하지 않습니다. 직사각형으로 만들까요?')
    if re.search(r'\b(inch|inches)\b|인치|\d\s*m\b',lowered):
        return _question('이 버전의 대화 입력은 mm 또는 cm를 지원합니다. 치수를 해당 단위로 알려주세요.')
    start={**DEFAULTS[template],**recipe_defaults}
    values={'template':template,**start}
    explicit=set()
    aliases={
        'width':r'(?:가로|너비|폭|width)', 'depth':r'(?:세로|깊이|depth)',
        'height':r'(?:높이|height)', 'wall':r'(?:벽\s*두께|등판\s*두께|앞턱\s*두께|벽|wall)',
        'bottom':r'(?:바닥\s*두께|바닥|bottom)',
        'cable_diameter':r'(?:케이블\s*지름|케이블\s*직경|cable\s*diameter)',
        'inset_diameter':r'(?:인셋\s*지름|디스크\s*지름|마그넷\s*지름|inset\s*diameter)',
        'inset_depth':r'(?:인셋\s*깊이|포켓\s*깊이|inset\s*depth)',
        'fit_clearance':r'(?:여유|공차|clearance)',
        'device_thickness':r'(?:기기|폰|휴대폰|스마트폰|케이스)\s*(?:포함\s*)?두께',
        'lip_height':r'(?:앞\s*턱(?:\s*높이)?|끝\s*턱(?:\s*높이)?|턱\s*높이)',
    }
    if template=='wall_hook':
        aliases.update({'hole_diameter':r'(?:나사\s*)?구멍\s*(?:지름|크기)?', 'depth':r'(?:걸이\s*(?:길이|깊이)|세로|깊이|depth)',
                        'bottom':r'(?:걸이\s*두께|바닥\s*두께|바닥|bottom)'})
    occupied=[]
    # Parse the qualified dimensions first so "인셋 깊이" is not also overall depth.
    for field,pattern in sorted(aliases.items(),key=lambda item:item[0] in ('width','depth','height')):
        matches=[match for match in re.finditer(pattern+r'\s*(?:는|은|을|를|:|=)?\s*'+NUMBER+UNIT,lowered)
                 if not any(match.start()<end and match.end()>start for start,end in occupied)]
        if len(matches)>1 and len({_mm(m.group(1),m.group(2)) for m in matches})>1:
            return _question(f'{field} 치수가 여러 개입니다. 사용할 치수 하나를 알려주세요.')
        if matches:
            m=matches[-1]
            values[field]=_mm(m.group(1),m.group(2)); explicit.add(field)
            occupied.extend(match.span() for match in matches)
    if template=='phone_stand' and 'device_thickness' not in explicit:
        # For a stand, a bare "두께" (not wall/base thickness) means the device with its case.
        bare=[m for m in re.finditer(r'(?<!벽)(?<!벽 )(?<!바닥)(?<!바닥 )두께\s*(?:는|은|:|=)?\s*'+NUMBER+UNIT,lowered)
              if not any(m.start()<end and m.end()>start for start,end in occupied)]
        if len({_mm(m.group(1),m.group(2)) for m in bare})>1:
            return _question('기기 두께가 여러 개입니다. 케이스를 포함한 두께 하나를 알려주세요.')
        if bare:
            values['device_thickness']=_mm(bare[-1].group(1),bare[-1].group(2));explicit.add('device_thickness')
            occupied.extend(m.span() for m in bare)
    triple_spans=[]
    triples=re.finditer(NUMBER+UNIT+r'\s*[x×*]\s*'+NUMBER+UNIT+r'\s*[x×*]\s*'+NUMBER+UNIT,lowered)
    for triple in triples:
        triple_spans.append(triple.span())
        groups=triple.groups()
        units=groups[1::2]
        normalized={_mm(1,unit) for unit in units if unit}
        if len(normalized)>1 and any(unit is None for unit in units):
            return _question('단위가 섞여 있습니다. 각 치수에 mm 또는 cm를 붙여주세요.')
        shared=next((unit for unit in reversed(units) if unit),None)
        for field,number,unit in zip(('width','depth','height'),groups[0::2],units):
            converted=_mm(number,unit or shared)
            if field in explicit and values[field]!=converted:
                return _question('표기한 가로·세로·높이가 서로 다릅니다. 사용할 치수 하나를 알려주세요.')
            values[field]=converted;explicit.add(field)
    # Two numbers ("30x20cm") give width and depth; previously they were ignored silently.
    for pair in re.finditer(NUMBER+UNIT+r'\s*[x×*]\s*'+NUMBER+UNIT+r'(?!\s*(?:칸|개|줄|가닥|[x×*]))',lowered):
        if any(pair.start()<end and pair.end()>start for start,end in triple_spans):
            continue
        units=pair.groups()[1::2]
        if not any(units):
            continue  # "2x3칸" or bare counts are not sizes; sizes need a unit.
        normalized={_mm(1,unit) for unit in units if unit}
        if len(normalized)>1 and any(unit is None for unit in units):
            return _question('단위가 섞여 있습니다. 각 치수에 mm 또는 cm를 붙여주세요.')
        shared=next((unit for unit in reversed(units) if unit),None)
        for field,number,unit in zip(('width','depth'),pair.groups()[0::2],units):
            converted=_mm(number,unit or shared)
            if field in explicit and values[field]!=converted:
                return _question('표기한 가로·세로가 서로 다릅니다. 사용할 치수 하나를 알려주세요.')
            values[field]=converted;explicit.add(field)
    if {'width','depth'}&explicit and any(word in lowered for word in ('안쪽','내부','안 치수','내경')):
        notes.append('안쪽 치수를 모델의 바깥 치수로 사용했습니다. 넣을 공간에 꼭 맞으므로 1~2 mm 줄이는 것을 권합니다.')
    if template=='phone_stand':
        angles={float(m.group(1)) for m in re.finditer(r'(?:각도|기울기)\s*(?:는|은|을|를|:|=)?\s*'+NUMBER+r'\s*(?:도|°)',lowered)}
        angles|={float(m.group(1)) for m in re.finditer(NUMBER+r'\s*(?:도|°)\s*(?:각도|기울기|로\s*기울)',lowered)}
        if len(angles)>1:
            return _question('등판 각도를 하나로 알려주세요. 50~80도 사이를 지원합니다.')
        if angles:
            values['lean_angle']=_mm(next(iter(angles)),None);explicit.add('lean_angle')
    if template=='magnet_frame' and 'inset_diameter' not in explicit:
        match=(re.search(NUMBER+r'\s*(mm|cm|밀리미터|센티미터)\s*(?:원형\s*)?(?:포토)?마그넷',lowered)
               or re.search(NUMBER+r'\s*(mm|cm|밀리미터|센티미터)\s*(?:짜리\s*)?(?:원형|동그란)',lowered)
               or re.search(r'(?:원형|동그란|지름|직경)\s*(?:사진\s*)?'+NUMBER+r'\s*(mm|cm|밀리미터|센티미터)',lowered))
        if match:
            values['inset_diameter']=_mm(match.group(1),match.group(2));explicit.add('inset_diameter')
    if template=='magnet_frame' and 'inset_diameter' in explicit and not {'width','depth'}&explicit:
        needed=float(values['inset_diameter'])+float(values['fit_clearance'])+2*float(values['wall'])
        if needed>min(float(values['width']),float(values['depth'])):
            side=math.ceil(needed)+8
            values['width']=values['depth']=side;explicit.update({'width','depth'})
            notes.append(f'지름 {values["inset_diameter"]:g} mm 포켓이 들어가도록 프레임을 {side} × {side} mm로 키웠습니다.')
    if template=='cable_comb' and not any(word in lowered for word in ('슬롯','홈','slot')):
        cables={float(m.group(1)) for m in re.finditer(r'케이블\s*'+NUMBER+r'\s*(?:개|줄|가닥)',lowered)}
        if len(cables)==1 and next(iter(cables)).is_integer() and next(iter(cables))>0:
            values['slots']=int(next(iter(cables)));explicit.add('slots')
    def count_values(patterns):
        return {float(match.group(1)) for pattern in patterns for match in re.finditer(pattern,lowered)}
    counts=count_values((NUMBER+r'\s*칸(?!막이)',r'칸\s*'+NUMBER))
    walls=count_values((r'(?:칸막이|dividers?)\s*'+NUMBER,NUMBER+r'\s*(?:개\s*)?(?:칸막이|dividers?)'))
    slots=count_values((r'(?:슬롯|홈|slots?)\s*'+NUMBER,NUMBER+r'\s*(?:개\s*)?(?:슬롯|홈)'))
    if any(len(items)>1 or any(value<=0 or not value.is_integer() for value in items) for items in (counts,slots)) or len(walls)>1 or any(value<0 or not value.is_integer() for value in walls):
        return _question('칸·홈·칸막이 개수는 각각 하나의 정수로 알려주세요. 서로 다른 개수는 함께 적용할 수 없습니다.')
    if counts:
        count=int(next(iter(counts)))
        if template=='tray':
            values['dividers']=count-1;explicit.add('dividers')
        elif template=='cable_comb':
            values['slots']=count;explicit.add('slots')
        else:
            return _question('이 프레임은 원형 포켓 하나를 지원합니다. 여러 칸은 아직 지원하지 않습니다.')
    if walls:
        count=int(next(iter(walls)))
        if template!='tray' or ('dividers' in explicit and values['dividers']!=count):
            return _question('수납함 칸 수와 칸막이 수를 확인해주세요. N칸에는 칸막이 N-1개가 필요합니다.')
        values['dividers']=count;explicit.add('dividers')
    if slots:
        count=int(next(iter(slots)))
        if template!='cable_comb' or ('slots' in explicit and values['slots']!=count):
            return _question('케이블 받침에 만들 홈 개수를 하나로 알려주세요.')
        values['slots']=count;explicit.add('slots')
    if template=='phone_stand' and not 50<=values['lean_angle']<=80:
        return _question('등판 각도는 바닥에서 50~80도 사이를 지원합니다. 사용할 각도를 알려주세요.')
    try:
        parameters=GeometryRequest(**values).model_dump()
    except ValidationError:
        return _question('치수가 지원 범위를 벗어났습니다. 가로·세로 10~500 mm, 높이 2~300 mm, 양수 두께를 사용해주세요.')
    adjusted=[]
    if template=='phone_stand' and 'depth' not in explicit:
        # Blockout rule: a default depth may grow so the leaning back stays over the
        # base. A depth the user wrote is never changed; generation reports it instead.
        lean=math.radians(90-parameters['lean_angle'])
        reach=(parameters['wall']+parameters['device_thickness']+parameters['fit_clearance']
               +(parameters['height']-parameters['bottom'])*math.tan(lean)+parameters['wall']/math.cos(lean))
        if reach>parameters['depth']:
            parameters['depth']=float(math.ceil(reach)+2)
            if parameters['depth']>500:
                return _question('높이에 비해 등판이 길어 바닥 깊이가 500 mm를 넘습니다. 높이를 줄이거나 각도를 키워 주세요.')
            explicit.add('depth')
            adjusted.append(f'등판이 바닥 안에 오도록 세로(깊이)를 {parameters["depth"]:g} mm로 늘렸습니다.')
    try:
        _validate_geometry(parameters)
    except ValueError as exc:
        return _question(str(exc))
    defaults={key:value for key,value in start.items() if key not in explicit}
    return {
        'status':'ready','engine':'template_rules','message':f'{LABELS[template]}의 제작안을 준비했습니다. 입력하지 않은 치수는 표시된 기본값을 사용합니다.',
        'parameters':parameters,'questions':[],
        'assumptions':notes+adjusted+([f'입력하지 않아 기본값을 쓴 치수: '+', '.join(_default_text(key,value,template) for key,value in defaults.items())] if defaults else []),
        'capability':'supported_template_only',
    }


def _plan_name_tag(text: str) -> dict:
    """Name keychain: the text comes from quotes or "이름/글자 …", sizes from qualified words."""
    lowered=text.lower()
    values=dict(DEFAULTS['name_tag'])
    explicit=set()
    notes=[]
    quoted=re.findall(r'[“"\'「『]([^”"\'」』]{1,20})[”"\'」』]',text)
    token=r'([0-9A-Za-z가-힣&!.\-]{1,20})'
    keychain=r'(?:키링|키홀더|열쇠고리|이름표|네임택)'
    stop={'크기','높이','두께','지름','구멍','키링','키홀더','열쇠고리','이름표','네임택','이름','글자','글씨','만들어줘','만들어','넣어줘','넣어서','고리','받침',
          '적힌','새긴','새겨진','쓴','써진','들어간'}
    def clean(word, after):
        # "민수인 키링" / "민수라고": drop a trailing particle before the keychain word.
        word=re.sub(r'(이라고|라고|으로|로)$','',word) if len(word)>2 else word
        if word.endswith('인') and len(word)>1 and re.match(r'\s*'+keychain, after):
            word=word[:-1]
        return word
    candidates=[value.strip() for value in quoted]
    for pattern in (r'(?:이름(?!표)|글자|글씨|문구|텍스트)\s*(?:은|는|이|가|을|를|:|=)?\s*'+token, token+r'(?=\s*'+keychain+')',
                    token+r'(?=\s*(?:이라고|라고)?\s*(?:적힌|새긴|새겨진|쓴|써진|들어간))'):
        for match in re.finditer(pattern,text):
            word=clean(match.group(1), text[match.end():])
            if word and word not in stop and not re.fullmatch(r'\d+(?:mm|cm)?',word):
                candidates.append(word)
    candidates=list(dict.fromkeys(candidates))
    if len(candidates)>1:
        return _question(f'키링에 넣을 글자가 여러 개입니다({", ".join(candidates)}). 하나를 따옴표로 알려주세요.')
    if candidates:
        values['text']=candidates[0];explicit.add('text')
    else:
        notes.append('넣을 글자를 찾지 못해 “MINSU”로 시작합니다. 원하는 글자를 따옴표로 적거나 글자 칸에서 바꾸세요.')
    aliases={'text_size':r'(?:글자|글씨)\s*크기','text_depth':r'(?:글자|글씨)\s*높이','hole_diameter':r'(?:고리\s*)?구멍\s*(?:지름|크기)?',
             'bottom':r'(?:받침|바닥)\s*두께','wall':r'(?:테두리|여백)'}
    for field,pattern in aliases.items():
        found={_mm(m.group(1),m.group(2)) for m in re.finditer(pattern+r'\s*(?:는|은|을|를|:|=)?\s*'+NUMBER+UNIT,lowered)}
        if len(found)>1:
            return _question(f'{FIELD_LABELS[field]} 값이 여러 개입니다. 하나만 알려주세요.')
        if found:
            values[field]=next(iter(found));explicit.add(field)
    try:
        parameters=GeometryRequest(template='name_tag',**values).model_dump()
        _validate_geometry(parameters)
    except ValidationError:
        return _question('키링 글자는 한글·영문·숫자·공백과 일부 기호로 1~20자, 글자 크기는 6~40 mm, 구멍 지름은 2~10 mm로 알려주세요.')
    except ValueError as exc:
        return _question(str(exc))
    defaults={key:value for key,value in DEFAULTS['name_tag'].items() if key not in explicit and key!='text'}
    return {
        'status':'ready','engine':'template_rules','message':'이름 키링의 제작안을 준비했습니다. 가로·세로는 글자 길이에 맞춰 정해집니다.',
        'parameters':parameters,'questions':[],
        'assumptions':notes+([f'입력하지 않아 기본값을 쓴 치수: '+', '.join(_default_text(key,value,'name_tag') for key,value in defaults.items())] if defaults else []),
        'capability':'supported_template_only',
    }


def validate_llm_plan(raw: dict) -> dict:
    if not isinstance(raw,dict) or set(raw)-{'parameters','explanation','questions'}:
        raise ValueError('LLM이 허용된 제작안 형식을 반환하지 않았습니다.')
    questions=raw.get('questions',[])
    if not isinstance(questions,list) or len(questions)>5 or any(not isinstance(q,str) or len(q)>500 for q in questions):
        raise ValueError('LLM 확인 질문 형식이 올바르지 않습니다.')
    if questions:
        message='제작안을 확정하지 못했습니다. 지원하는 물건과 가로·세로·높이를 확인해주세요.'
        return {'status':'needs_input','engine':'llm','message':message,'questions':[message],'assumptions':[]}
    params=raw.get('parameters')
    if not isinstance(params,dict) or params.get('template') not in DEFAULTS:
        raise ValueError('지원되는 템플릿의 파라미터가 필요합니다.')
    try:
        spec=GeometryRequest(**{'template':params['template'],**DEFAULTS[params['template']],**params})
    except ValidationError as exc:
        raise ValueError('LLM이 제안한 치수 또는 필드가 허용 범위를 벗어났습니다.') from exc
    message=raw.get('explanation','제작안을 준비했습니다.')
    if not isinstance(message,str) or len(message)>2000:
        raise ValueError('LLM 설명 형식이 올바르지 않습니다.')
    unset={key:value for key,value in DEFAULTS[spec.template].items() if key not in params}
    defaults=[f'입력하지 않아 기본값을 쓴 치수: '+', '.join(_default_text(key,value,spec.template) for key,value in unset.items())] if unset else []
    # Execution facts always come from the application, never provider prose.
    message='LLM이 제안한 치수를 검토할 수 있습니다. 아직 모델 생성·슬라이싱·프린터 출력은 실행하지 않았습니다.'
    return {'status':'ready','engine':'llm','message':message,'parameters':spec.model_dump(),'questions':[],'assumptions':defaults,'capability':'supported_template_only'}


def provider_config() -> dict:
    base=os.getenv('PPA_LLM_BASE_URL','').strip().rstrip('/')
    model=os.getenv('PPA_LLM_MODEL','').strip()
    if not base or not model:
        return {'configured':False,'status':'not_configured','model':model or None}
    try:
        parsed=urlsplit(base)
        port=parsed.port  # Access validates nonnumeric and out-of-range ports.
    except ValueError:
        return {'configured':False,'status':'invalid_url','model':model}
    if port == 0 or any(ord(character)<32 for character in base):
        return {'configured':False,'status':'invalid_url','model':model}
    if parsed.username or parsed.password or parsed.query or parsed.fragment or not parsed.hostname:
        return {'configured':False,'status':'invalid_url','model':model}
    if parsed.scheme!='https' and not (parsed.scheme=='http' and parsed.hostname in ('localhost','127.0.0.1','::1')):
        return {'configured':False,'status':'requires_https_or_loopback','model':model}
    return {'configured':True,'status':'configured_not_tested','model':model,'base_url':base}


async def plan_with_llm(text: str) -> dict:
    if not isinstance(text,str) or not text.strip() or len(text)>4000:
        raise ValueError('요청은 4,000자 이내여야 합니다.')
    routed = _route_existing_workflow(text)
    if routed is not None:
        return routed
    system=(
        'You plan parameterized 3D-printing models. Return only a JSON object with parameters, explanation in Korean, and questions (array). '
        'Never return code, commands, temperatures, prices or claims of printing success. '
        'Supported templates: tray (open-top, optional dividers), cable_comb (open U channels, not a clamp), magnet_frame (rectangular plate with circular blind inset, no magnet retention claim), phone_stand (base, front lip and back plate leaning at lean_angle degrees from horizontal; device_thickness plus fit_clearance sets the slot; no tipping or charging-port guarantee), name_tag (raised text of 1-20 letters on a rounded plate with a ring hole; width and depth follow the text). '
        'All dimensions in mm; convert units explicitly. If the user requests unsupported objects, moving joints, load/safety guarantees, lids or unsupported edits, ask a clarification in questions and do not generate parameters. '
        'For N tray compartments use dividers=N-1. fit_clearance adds to diameter. Missing dimensions must be described as assumptions in explanation. '
        'Allowed parameter schema: '+json.dumps(GeometryRequest.model_json_schema(),ensure_ascii=False)
    )
    return validate_llm_plan(await request_llm_json(system,text))


async def request_llm_json(system: str, text: str) -> dict:
    """Protected bounded transport shared by the typed model planners."""
    config=provider_config()
    if not config['configured']:
        raise ValueError('LLM 연결이 설정되지 않았습니다. 템플릿 모드를 이용하거나 PPA_LLM_BASE_URL과 PPA_LLM_MODEL을 설정하세요.')
    # Keep the wire budget meaningful: HTTPX decodes compressed responses before
    # yielding aiter_bytes chunks, so a small compressed body could expand first.
    headers={'Content-Type':'application/json', 'Accept-Encoding':'identity'}
    api_key=os.getenv('PPA_LLM_API_KEY','').strip()
    if api_key:
        headers['Authorization']='Bearer '+api_key
    try:
        # HTTPX's read timeout applies to each chunk. A separate deadline also
        # bounds a peer that keeps sending a small amount of data indefinitely.
        async with asyncio.timeout(LLM_DEADLINE_SECONDS):
            async with httpx.AsyncClient(timeout=60,trust_env=False,follow_redirects=False) as client:
                async with client.stream('POST',config['base_url']+'/chat/completions',headers=headers,json={
                    'model':config['model'],'temperature':0.1,'messages':[{'role':'system','content':system},{'role':'user','content':text}],
                }) as response:
                    # Error bodies may contain credentials or be arbitrarily
                    # large. Neither read nor echo them.
                    response.raise_for_status()
                    if response.headers.get('content-encoding','identity').strip().lower() not in ('','identity'):
                        raise ValueError('LLM 서버의 압축 응답은 지원하지 않습니다. 비압축 JSON 응답을 사용하도록 서버를 확인하세요.')
                    length=response.headers.get('content-length','')
                    if length.isdigit() and int(length)>MAX_LLM_RESPONSE_BYTES:
                        raise ValueError('LLM 응답이 허용 크기를 초과했습니다.')
                    body=bytearray()
                    async for chunk in response.aiter_bytes(chunk_size=16_384):
                        if len(body)+len(chunk)>MAX_LLM_RESPONSE_BYTES:
                            raise ValueError('LLM 응답이 허용 크기를 초과했습니다.')
                        body.extend(chunk)
        content=json.loads(body)['choices'][0]['message']['content']
        if not isinstance(content,str):
            raise ValueError('LLM의 텍스트 응답이 없습니다.')
        content=re.sub(r'^```(?:json)?\s*|\s*```$','',content.strip())
        raw=json.loads(content,parse_constant=lambda x: (_ for _ in ()).throw(ValueError('LLM 응답에는 유한한 JSON 값만 사용할 수 있습니다.')))
        if not isinstance(raw,dict):
            raise ValueError('LLM 응답에는 JSON 객체가 필요합니다.')
        return raw
    except TimeoutError as exc:
        raise ValueError('LLM 응답 대기 시간을 초과했습니다. 연결 상태를 확인하거나 템플릿 모드를 사용하세요.') from exc
    except httpx.HTTPStatusError as exc:
        raise ValueError(f'LLM 서버 요청 실패 (HTTP {exc.response.status_code}). 모델과 API 설정을 확인하세요.') from exc
    except (httpx.InvalidURL,httpx.RequestError,KeyError,IndexError,TypeError,json.JSONDecodeError,UnicodeDecodeError,RecursionError) as exc:
        raise ValueError('LLM 서버 연결 또는 응답 형식을 확인할 수 없습니다. 템플릿 모드는 계속 사용할 수 있습니다.') from exc
