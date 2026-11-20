"""Pure, reproducible edits to the current supported template parameters."""

from decimal import Decimal
import hashlib
import json
import math
import re

from .geometry_rules import _validate_geometry
from .schemas import COLOR_FIELDS, PALETTE, TEXT_FIELDS, GeometryRequest, TEMPLATE_SPECIFIC_FIELDS

_STRINGS = TEXT_FIELDS | COLOR_FIELDS
from . import planner

_COMMON = {'width', 'depth', 'height', 'wall', 'bottom'}
_COUNTS = {'dividers', 'slots'}
_CAPABILITY = 'current_template_parameters_only'
_READY = '현재 제작안의 변경 치수를 검토하세요. 적용 후 모델을 생성할 수 있습니다.'
_QUESTION = '변경할 항목과 mm 또는 cm 치수·개수를 구체적으로 알려주세요. 지원하지 않거나 서로 다른 변경은 함께 적용할 수 없습니다.'
_SELECTION_KEYS = {'schema_version', 'request_text', 'base_parameters', 'operations', 'parent'}
_REVIEW_KEYS = {'schema_version', 'selection', 'base_sha256', 'parameters', 'parameters_sha256', 'changes', 'review_sha256'}


def _canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('utf-8')


def _hash(value):
    return hashlib.sha256(_canonical(value)).hexdigest()


def _number(value):
    if type(value) not in (int, float):
        raise ValueError('치수는 유한한 JSON 숫자여야 합니다.')
    try:
        valid = math.isfinite(value)
    except OverflowError:
        valid = False
    if not valid:
        raise ValueError('치수는 유한한 JSON 숫자여야 합니다.')


def _length_number(value):
    # JavaScript serializes integral floats as integers and signed zero as 0.
    # Restore one representation at every pure boundary before deriving hashes.
    return 0.0 if value == 0 else float(value)


def _required(template):
    # A name tag's outline follows its text; a keycap's follows its key size.
    # A round cup is sized by its diameter (width); depth is not used.
    common = (_COMMON - {'width', 'depth', 'height'} if template == 'name_tag'
              else _COMMON - {'width', 'depth'} if template == 'keycap'
              else _COMMON - {'depth'} if template == 'cup' else _COMMON)
    return common | TEMPLATE_SPECIFIC_FIELDS[template]


def _editable(template):
    # Colours are optional: an unchosen colour is absent from canonical parameters.
    return _required(template) | {'color'} | ({'accent_color'} if template == 'name_tag' else set())


def normalize_parameters(base: dict) -> dict:
    """Require explicit current dimensions; never invent applicable defaults."""
    if not isinstance(base, dict) or not isinstance(base.get('template'), str) or base['template'] not in TEMPLATE_SPECIFIC_FIELDS:
        raise ValueError('지원하는 현재 템플릿이 필요합니다.')
    fields = GeometryRequest.model_fields
    editable = _editable(base['template'])
    if set(base) - set(fields) or not _required(base['template']) <= set(base):
        raise ValueError('현재 제작안의 모든 적용 치수가 필요합니다.')
    for name, value in base.items():
        if name == 'template':
            continue
        if name in TEXT_FIELDS:
            if not isinstance(value, str):
                raise ValueError('글자 항목은 문자열이어야 합니다.')
            continue
        if name in COLOR_FIELDS:
            if not isinstance(value, str) or (value and name not in editable):
                raise ValueError('색 항목이 올바르지 않습니다.')
            continue
        _number(value)
        if name in _COUNTS and type(value) is not int:
            raise ValueError('개수는 정수여야 합니다.')
        if name not in editable and value != fields[name].default:
            raise ValueError('현재 템플릿에 적용되지 않는 치수입니다.')
    parameters = GeometryRequest(**{**{name:field.default for name,field in fields.items()}, **base}).model_dump()
    for name in parameters.keys() - _COUNTS - _STRINGS - {'template'}:
        parameters[name] = _length_number(parameters[name])
    _validate_geometry(parameters)
    return parameters


def _selection(selection):
    if not isinstance(selection, dict) or set(selection) != _SELECTION_KEYS:
        raise ValueError('변경 선택 형식이 올바르지 않습니다.')
    if type(selection['schema_version']) is not int or selection['schema_version'] != 1:
        raise ValueError('변경 선택 버전이 올바르지 않습니다.')
    text = selection['request_text']
    if not isinstance(text, str) or not text.strip() or len(text) > 4000:
        raise ValueError('변경 요청은 4,000자 이내여야 합니다.')
    base = normalize_parameters(selection['base_parameters'])
    parent = selection['parent']
    if parent is not None:
        lengths = {'job_id':32, 'parameters_sha256':64, 'model_sha256':64, 'manifest_sha256':64}
        if not isinstance(parent, dict) or set(parent) != set(lengths):
            raise ValueError('부모 모델 식별 형식이 올바르지 않습니다.')
        for key, length in lengths.items():
            if not isinstance(parent[key], str) or re.fullmatch('[0-9a-f]{'+str(length)+'}', parent[key]) is None:
                raise ValueError('부모 모델 식별 형식이 올바르지 않습니다.')
        if parent['parameters_sha256'] != _hash(base):
            raise ValueError('부모 모델과 현재 치수가 다릅니다.')
        parent = dict(parent)
    operations = selection['operations']
    if not isinstance(operations, list) or not 1 <= len(operations) <= 12:
        raise ValueError('변경 작업은 1~12개여야 합니다.')
    seen = set()
    result = []
    for operation in operations:
        if not isinstance(operation, dict) or set(operation) != {'field', 'op', 'value'}:
            raise ValueError('변경 작업 형식이 올바르지 않습니다.')
        field, op, value = (operation[key] for key in ('field', 'op', 'value'))
        if not isinstance(field, str) or field not in _editable(base['template']) or field in seen:
            raise ValueError('중복되거나 적용되지 않는 변경 항목입니다.')
        if op not in ('set', 'add'):
            raise ValueError('지원하지 않는 변경 연산입니다.')
        if field in COLOR_FIELDS:
            if op != 'set' or not isinstance(value, str) or (value and value not in PALETTE):
                raise ValueError('색은 지원하는 색 이름으로 직접 지정해야 합니다.')
            seen.add(field)
            result.append({'field':field, 'op':op, 'value':value})
            continue
        if field in TEXT_FIELDS:
            if op != 'set' or not isinstance(value, str):
                raise ValueError('글자는 새 문자열로 직접 지정해야 합니다.')
            seen.add(field)
            result.append({'field':field, 'op':op, 'value':value})
            continue
        _number(value)
        if field in _COUNTS and (op != 'set' or type(value) is not int):
            raise ValueError('개수 변경은 정수를 직접 지정해야 합니다.')
        if field not in _COUNTS:
            value = _length_number(value)
        seen.add(field)
        result.append({'field':field, 'op':op, 'value':value})
    return {'schema_version':1, 'request_text':text, 'base_parameters':base, 'operations':result, 'parent':parent}


def review_model_edit(selection: dict) -> dict:
    selection = _selection(selection)
    base = selection['base_parameters']
    proposed = dict(base)
    for operation in selection['operations']:
        field, value = operation['field'], operation['value']
        if operation['op'] == 'add':
            value = float(Decimal(str(base[field])) + Decimal(str(value)))
        proposed[field] = value
    parameters = normalize_parameters(proposed)
    changes = [{'field':field, 'before':base.get(field, ''), 'after':parameters.get(field, '')}
               for field in GeometryRequest.model_fields
               if (field in parameters or field in base) and base.get(field, '') != parameters.get(field, '')]
    if not changes:
        raise ValueError('실제로 달라지는 치수가 없습니다.')
    hashed = {'schema_version':1, 'selection':selection, 'base_sha256':_hash(base),
              'parameters_sha256':_hash(parameters), 'changes':changes}
    return {**hashed, 'parameters':parameters, 'review_sha256':_hash(hashed)}


def model_edit_record(selection: dict, parameters: dict) -> dict:
    review = review_model_edit(selection)
    if normalize_parameters(parameters) != review['parameters']:
        raise ValueError('생성 치수가 검토한 변경과 다릅니다.')
    return {**review, 'provenance':'user_confirmed_parameters'}


def validate_model_edit_record(record: dict, parameters: dict) -> dict:
    if not isinstance(record, dict) or set(record) != _REVIEW_KEYS | {'provenance'}:
        raise ValueError('저장된 변경 기록 형식이 올바르지 않습니다.')
    derived = model_edit_record(record['selection'], parameters)
    try:
        matches = _canonical(record) == _canonical(derived)
    except (TypeError, ValueError, OverflowError, RecursionError) as exc:
        raise ValueError('저장된 변경 기록 형식이 올바르지 않습니다.') from exc
    if not matches:
        raise ValueError('저장된 변경 기록이 재현 결과와 다릅니다.')
    return derived


def _response(engine, review=None):
    result = {'status':'ready' if review is not None else 'needs_input', 'engine':engine,
              'capability':_CAPABILITY, 'message':_READY if review is not None else _QUESTION,
              'questions':[] if review is not None else [_QUESTION], 'assumptions':[]}
    if review is not None:
        result['review'] = review
    return result


_ALIASES = {
    'width':r'가로|너비|폭|width', 'depth':r'걸이\s*길이|세로|깊이|depth', 'height':r'키캡\s*높이|높이|height',
    'wall':r'옆\s*벽(?:\s*두께)?|벽\s*두께|등판\s*두께|앞턱\s*두께|테두리(?:\s*여백)?|여백|벽|wall', 'bottom':r'윗면\s*두께|바닥\s*두께|받침\s*두께|걸이\s*두께|바닥|bottom',
    'text_size':r'(?:글자|글씨)\s*크기|text\s*size', 'text_depth':r'(?:글자|글씨|각인)\s*(?:높이|깊이)|text\s*depth',
    'hole_diameter':r'(?:고리\s*|나사\s*)?구멍(?:\s*(?:지름|크기))?|hole\s*diameter',
    'cable_diameter':r'케이블\s*(?:지름|직경)|cable\s*diameter',
    'inset_diameter':r'(?:인셋|디스크|마그넷)\s*지름|inset\s*diameter',
    'inset_depth':r'(?:인셋|포켓)\s*깊이|inset\s*depth',
    'fit_clearance':r'(?:십자\s*|스템\s*)?(?:여유|공차)|clearance', 'key_units':r'키\s*크기|key\s*units?', 'dividers':r'칸막이|dividers?', 'slots':r'슬롯|홈|slots?',
    'lean_angle':r'(?:등판\s*)?(?:각도|기울기)|lean\s*angle',
    'device_thickness':r'(?:기기|폰|휴대폰|스마트폰|케이스)\s*(?:포함\s*)?두께|device\s*thickness',
    'lip_height':r'앞\s*턱(?:\s*높이)?|끝\s*턱(?:\s*높이)?|턱\s*높이|lip\s*height',
}
_ANGLES = {'lean_angle'}
_NUMBER = r'[+-]?(?:\d+(?:\.\d*)?|\.\d+)'
_UNIT = r'mm|cm|밀리미터|센티미터|밀리|센티|도|°|u(?![a-z])'
_ACTION = r'늘려(?:줘|주세요)?|늘려|증가(?:시켜)?(?:줘|주세요)?|줄여(?:줘|주세요)?|감소(?:시켜)?(?:줘|주세요)?|더해(?:줘|주세요)?|빼(?:줘|주세요)?'
_TAIL = r'(?:(?:으)?로\s*)?(?:바꿔(?:줘|주세요)?|변경해(?:줘|주세요)?|설정해(?:줘|주세요)?|해(?:줘|주세요)?)?'


_TEXT_EDIT = re.compile(
    r'(?:글자|글씨|이름|문구|텍스트)\s*(?:를|을|은|는|:|=)?\s*'
    r'(?:["“”\'‘’](?P<quoted>[^"“”\'‘’]{1,20})["“”\'‘’]|(?P<word>[0-9A-Za-z가-힣&!.\-]{1,20}?))\s*'
    r'(?:으로|로|라고)(?=\s|$|[,，.])\s*(?:(?:바꿔|변경해|고쳐|수정해|해|써)(?:\s*(?:줘|주세요))?|바꾸고|하고|변경하고)?')


def _rule_operations(text, template):
    # Consume every meaningful token. Unknown clauses cannot disappear beside a valid edit.
    aliases = dict(_ALIASES)
    if template == 'cup':
        # “지름” is the cup's outer diameter and any “구멍” is its drain hole.
        aliases['width'] = r'(?:바깥\s*|컵\s*)?(?:지름|직경)|' + _ALIASES['width']
        aliases.pop('hole_diameter')
        aliases['drain_hole'] = r'(?:배수\s*)?구멍(?:\s*(?:지름|크기))?|drain\s*hole'
    alias = '|'.join('(?P<'+field+'>'+pattern+')' for field,pattern in sorted(aliases.items(),key=lambda item:-len(item[1])))
    pattern = re.compile(r'(?P<label>'+alias+r')\s*(?:는|은|을|를|만|:|=)?\s*(?P<value>'+_NUMBER+r')\s*(?P<unit>'+_UNIT+r')?\s*(?P<count_unit>개)?\s*(?P<action>'+_ACTION+r')?\s*'+_TAIL, re.I)
    operations = []
    colors, text = planner.extract_colors(text)
    for field, key in colors.items():
        if field not in _editable(template):
            raise ValueError('글자 색은 이름 키링에만 지정할 수 있습니다.')
        operations.append({'field':field, 'op':'set', 'value':key})
    if template in ('name_tag', 'keycap'):
        def text_edit(match):
            operations.append({'field':'text', 'op':'set', 'value':(match.group('quoted') or match.group('word')).strip()})
            return ' '
        text = _TEXT_EDIT.sub(text_edit, text)
    def field_edit(match):
        field = next(field for field in aliases if match.group(field) is not None)
        value = Decimal(match.group('value'))
        unit = match.group('unit')
        if field in _COUNTS:
            if unit or match.group('action') or value != value.to_integral_value():
                raise ValueError('개수는 절대 정수로 지정하세요.')
            value = int(value)
        elif field == 'key_units':
            if match.group('count_unit') or (unit and unit.lower() != 'u') or match.group('action'):
                raise ValueError('키 크기는 1u, 1.5u처럼 u 단위로 지정하세요.')
            value = float(value)
        elif field in _ANGLES:
            if match.group('count_unit') or (unit and unit not in ('도', '°')):
                raise ValueError('각도는 도(°) 단위로 지정하세요.')
            value = float(value)
        else:
            if match.group('count_unit') or unit in ('도', '°') or (unit and unit.lower() == 'u'):
                raise ValueError('길이에는 mm 또는 cm 단위를 사용하세요.')
            if unit and unit.lower() in ('cm','센티미터','센티'):
                value *= 10
            value = float(value)
        action = match.group('action')
        if action and value < 0:
            raise ValueError('변경량은 양수로 지정하세요.')
        if action and action.startswith(('줄','감소','빼')):
            value = -value
        operations.append({'field':field, 'op':'add' if action else 'set', 'value':value})
        return ' '
    residue = pattern.sub(field_edit, text.lower())
    count_pattern = re.compile(r'(?P<value>'+_NUMBER+r')\s*(?P<label>칸(?!막이)|(?:개\s*)?(?:슬롯|홈|칸막이))\s*'+_TAIL)
    def count_edit(match):
        value = Decimal(match.group('value'))
        if value != value.to_integral_value():
            raise ValueError('개수는 정수로 지정하세요.')
        label = match.group('label')
        if label == '칸':
            field = 'dividers' if template == 'tray' else 'slots' if template == 'cable_comb' else None
            value = int(value) - (1 if template == 'tray' else 0)
        else:
            field = 'dividers' if '칸막이' in label else 'slots'
            value = int(value)
        operations.append({'field':field, 'op':'set', 'value':value})
        return ' '
    residue = count_pattern.sub(count_edit, residue)
    residue = re.sub(r'그리고|및|바꾸고|변경하고|하고|[,，.\s]+', '', residue)
    if residue or not operations:
        raise ValueError('전체 변경 요청을 해석할 수 없습니다.')
    return operations


def plan_model_edit(text: str, base: dict, *, parent: dict | None = None) -> dict:
    base = normalize_parameters(base)
    if not isinstance(text, str) or not text.strip() or len(text) > 4000:
        return _response('template_rules')
    routed = planner._route_existing_workflow(text)
    if routed is not None:
        return routed
    try:
        operations = _rule_operations(text, base['template'])
        review = review_model_edit({'schema_version':1, 'request_text':text, 'base_parameters':base,
                                    'operations':operations, 'parent':parent})
    except ValueError:
        return _response('template_rules')
    return _response('template_rules', review)


async def plan_model_edit_with_llm(text: str, base: dict, *, parent: dict | None = None) -> dict:
    base = normalize_parameters(base)
    if not isinstance(text, str) or not text.strip() or len(text) > 4000:
        raise ValueError('변경 요청은 4,000자 이내여야 합니다.')
    # Validate parent and request before sending anything to a provider.
    _selection({'schema_version':1, 'request_text':text, 'base_parameters':base,
                'operations':[{'field':'height', 'op':'add', 'value':1}], 'parent':parent})
    routed = planner._route_existing_workflow(text)
    if routed is not None:
        return routed
    system = (
        'Propose edits to the current parameters only. Return JSON with exactly operations and questions. '
        'operations is an array of {field,op,value}; op is set or add, value is a finite number in mm. '
        'key_units is a keycap size in units (set only: 1, 1.25, 1.5, 1.75, 2, 2.25, 2.75, 6.25 or 7). '
        'Exceptions use op set with a string: text is the new name-tag text or keycap legend; color (whole model) and accent_color '
        '(name-tag letters only) are one of: ' + ', '.join(PALETTE) + ', or an empty string to clear. '
        'Counts dividers and slots require set with an integer. N tray compartments means dividers=N-1. '
        'Never replace geometry, switch template, return code, prose, URLs or execution claims. '
        'Preserve every unspecified field. For ambiguous, conflicting, unsupported or mixed requests return '
        'no operations and ask clarification in questions (at most 5 strings of at most 500 characters). '
        'Allowed editable fields: '+', '.join(field for field in GeometryRequest.model_fields if field in _editable(base['template']))
    )
    raw = await planner.request_llm_json(system, json.dumps({'request_text':text, 'base_parameters':base},ensure_ascii=False,allow_nan=False))
    if not isinstance(raw, dict) or set(raw) != {'operations', 'questions'}:
        raise ValueError('LLM 변경 응답 형식이 올바르지 않습니다.')
    questions = raw['questions']
    if not isinstance(questions, list) or len(questions)>5 or any(not isinstance(q,str) or not q.strip() or len(q)>500 for q in questions):
        raise ValueError('LLM 확인 질문 형식이 올바르지 않습니다.')
    if questions:
        if raw['operations'] != []:
            raise ValueError('LLM 변경과 확인 질문을 함께 적용할 수 없습니다.')
        return _response('llm')
    selection = _selection({'schema_version':1, 'request_text':text, 'base_parameters':base,
                            'operations':raw['operations'], 'parent':parent})
    try:
        review = review_model_edit(selection)
    except ValueError:
        return _response('llm')
    return _response('llm', review)
