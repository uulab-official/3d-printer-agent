"""Side-by-side slices of one model with a few process settings changed.

Only the process (print) settings change, and only the keys named here. Machine and
filament settings, the plate and the model stay exactly as supplied. Each variant goes
through the normal preparation (including the print-volume review) and execution; only a
small summary of the verified output is kept. Figures are the slicer's own estimates for
these settings, not measured prints.
"""
from __future__ import annotations

import copy
import io
import re
import zipfile

from .printer_send import inspect_sliced

VARIANT_KEYS = ('layer_height', 'sparse_infill_density', 'wall_loops', 'top_shell_layers', 'bottom_shell_layers')
VARIANTS = (
    ('original', '지금 설정', '넣은 설정 그대로'),
    ('fine', '곱게', '레이어를 얇게(노즐의 30%) 쌓아 표면이 매끈하지만 오래 걸립니다'),
    ('fast', '빠르게', '레이어를 두껍게(노즐의 70%), 채움 10%로 빨리 뽑습니다'),
    ('strong', '튼튼하게', '벽 2줄·위아래 껍질 1층을 더하고 채움 40%로 단단하게 만듭니다'),
)


def _first(value):
    return value[0] if isinstance(value, list) and value else value


def _number(value):
    try:
        return float(str(_first(value)).strip().removesuffix('%'))
    except (TypeError, ValueError):
        return None


def _text(number):
    return f'{number:.2f}'.rstrip('0').rstrip('.')


def overrides(bundle, variant_id):
    """The process keys this variant changes, as the strings Studio profiles use."""
    if variant_id == 'original':
        return {}
    process = bundle.get('process') or {}
    nozzle = _number((bundle.get('machine') or {}).get('nozzle_diameter'))
    if not nozzle or not 0.1 <= nozzle <= 1.2:
        raise ValueError('machine.nozzle_diameter를 읽을 수 없어 비교 설정을 만들 수 없습니다.')
    if variant_id == 'fine':
        return {'layer_height': _text(max(0.06, round(nozzle * 0.3, 2)))}
    if variant_id == 'fast':
        return {'layer_height': _text(round(nozzle * 0.7, 2)), 'sparse_infill_density': '10%'}
    if variant_id == 'strong':
        changes = {'sparse_infill_density': '40%'}
        for key, extra in (('wall_loops', 2), ('top_shell_layers', 1), ('bottom_shell_layers', 1)):
            current = _number(process.get(key))
            if current is None:
                raise ValueError(f'process.{key}를 읽을 수 없어 비교 설정을 만들 수 없습니다.')
            changes[key] = str(int(current) + extra)
        return changes
    raise ValueError('지원하지 않는 비교 설정입니다.')


def variant_bundle(bundle, variant_id):
    changed = copy.deepcopy(bundle)
    for key, value in overrides(bundle, variant_id).items():
        current = changed['process'].get(key)
        changed['process'][key] = [value] * len(current) if isinstance(current, list) and current else value
    return changed


def summarize(content: bytes) -> dict:
    """Estimates read from a verified sliced 3MF; nothing is printed."""
    summary = inspect_sliced(content)
    with zipfile.ZipFile(io.BytesIO(content)) as archive:
        gcode = archive.read(summary['gcode_path']).decode('utf-8', 'ignore')
    layers = len(re.findall(r'^;\s*(?:CHANGE_LAYER|LAYER_CHANGE)\b', gcode, re.M))
    return {'minutes': None if summary['prediction_seconds'] is None else round(summary['prediction_seconds'] / 60, 1),
            'grams': summary['weight_g'], 'layers': layers or None,
            'support': bool(re.search(r'^;\s*FEATURE:\s*Support', gcode, re.M))}
