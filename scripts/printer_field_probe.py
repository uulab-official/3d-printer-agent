#!/usr/bin/env python3
"""Read one real Bambu printer's status once and record its field layout, redacted.

Run this yourself on the computer that shares the printer's network. The LAN access
code is typed at a hidden prompt (or read from ``PPA_PRINTER_ACCESS_CODE``); it is
never written anywhere. Only the application's two fixed read requests are sent
(``pushall`` and ``get_version``); nothing is started, moved, heated or uploaded.

The report keeps the *shape* of the printer's raw report (every key and its value
type, list lengths) so parsers can be checked against real firmware. Values are kept
only for an allow-list of non-identifying fields (state, temperatures, nozzle,
filament types and colours, module names and versions). Serial numbers, addresses,
network names, file names and anything not allow-listed become type tags.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import getpass
import json
import os
from pathlib import Path
import platform
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from print_agent import __version__, printer_lan  # noqa: E402

# Raw keys whose values are kept. Everything else is reduced to its type.
KEEP_VALUES = frozenset({
    # print report
    'gcode_state', 'mc_percent', 'mc_remaining_time', 'layer_num', 'total_layer_num', 'print_error',
    'nozzle_temper', 'nozzle_target_temper', 'bed_temper', 'bed_target_temper', 'chamber_temper',
    'nozzle_diameter', 'nozzle_type', 'wifi_signal', 'command', 'sequence_id', 'msg', 'print_type',
    'spd_lvl', 'spd_mag', 'stg_cur', 'home_flag', 'hw_switch_state', 'lifecycle', 'fan_gear',
    'cooling_fan_speed', 'heatbreak_fan_speed', 'big_fan1_speed', 'big_fan2_speed', 'mc_print_stage',
    'mc_print_sub_stage', 'print_gcode_action', 'ams_status', 'ams_rfid_status', 'queue_number',
    # HMS entries
    'attr', 'code',
    # AMS units and trays
    'id', 'humidity', 'humidity_raw', 'temp', 'tray_type', 'tray_sub_brands', 'tray_color', 'tray_info_idx',
    'nozzle_temp_min', 'nozzle_temp_max', 'tray_now', 'tray_pre', 'tray_tar', 'tray_exist_bits', 'tray_is_bbl_bits',
    'tray_read_done_bits', 'tray_reading_bits', 'insert_flag', 'power_on_flag', 'version', 'remain', 'k', 'n',
    'cols', 'ctype', 'tray_diameter', 'tray_weight', 'bed_temp', 'bed_temp_type', 'drying_temp', 'drying_time',
    'info', 'dry_time', 'check',
    # extruders/nozzles on multi-nozzle models
    'diameter', 'type', 'state', 'stat', 'snow', 'spre', 'star', 'hnow', 'htar', 'hpre', 'cur_temp', 'tar_temp',
    # get_version modules
    'name', 'sw_ver', 'hw_ver', 'product_name', 'project_name', 'loader_ver', 'ota_ver', 'new_ver',
})
# Never kept even if a key name above matches inside them.
DROP_SUBTREES = frozenset({'net', 'ipcam', 'xcam', 'upload', 'upgrade_state', 'online', 'sdcard'})
IDENTIFYING = ('sn', 'serial', 'ip', 'mac', 'ssid', 'url', 'token', 'user', 'pass', 'code_', 'gcode_file',
               'subtask_name', 'file', 'task_id', 'job_id', 'project_id', 'profile_id', 'subtask_id', 'model_id')
MAX_LIST_ITEMS = 8


def _identifying(key: str) -> bool:
    lowered = key.lower()
    return any(lowered == word or lowered.endswith('_' + word) or lowered.startswith(word + '_') for word in IDENTIFYING)


def shape(value, key=None, serial=None, depth=0):
    """Return the redacted layout of a raw report value."""
    if depth > 12:
        return '<too deep>'
    if isinstance(value, dict):
        out = {}
        for name in sorted(value)[:200]:
            if name in DROP_SUBTREES:
                out[name] = f'<{type(value[name]).__name__}, not recorded>'
            else:
                out[name] = shape(value[name], name, serial, depth + 1)
        return out
    if isinstance(value, list):
        items = [shape(item, key, serial, depth + 1) for item in value[:MAX_LIST_ITEMS]]
        if len(value) > MAX_LIST_ITEMS:
            items.append(f'<{len(value) - MAX_LIST_ITEMS} more>')
        return items
    keep = key in KEEP_VALUES and not _identifying(str(key))
    if isinstance(value, str) and serial and serial.casefold() in value.casefold():
        keep = False
    if keep and isinstance(value, (bool, int, float)) or keep and isinstance(value, str) and len(value) <= 64:
        return value
    if value is None:
        return None
    return f'<{type(value).__name__}>'


def build_report(result, serial):
    raw = result.pop('raw', None) or {}
    connection = result.get('connection') or {}
    understood = {
        'print': result.get('print'),
        'identity': {k: v for k, v in (result.get('identity') or {}).items() if k != 'report_topic_serial'},
    }
    return {
        'schema_version': 1,
        'kind': 'printer-field-probe',
        'recorded_at': datetime.now(timezone.utc).isoformat(timespec='seconds'),
        'app_version': __version__,
        'computer': {'system': platform.system(), 'release': platform.release(), 'python': platform.python_version()},
        'requests_sent': ['pushall', 'get_version'],
        'connection_state': connection.get('state'),
        'connection_detail': connection.get('detail'),
        'certificate_sha256_prefix': ((result.get('certificate') or {}).get('sha256') or '')[:12] or None,
        'understood_by_app': understood if connection.get('state') == 'reporting' else None,
        'raw_layout': {'print': shape(raw.get('print'), serial=serial), 'info': shape(raw.get('info'), serial=serial)}
        if raw else None,
        'not_recorded': 'serial, IP address, access code, network names, file and job names, camera and storage details',
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--host', required=True, help='printer IP address on the local network')
    parser.add_argument('--serial', required=True, help='printer serial (used for the report topic, not recorded)')
    parser.add_argument('--out-dir', type=Path, default=ROOT / 'qa-output' / 'printer-probe')
    args = parser.parse_args(argv)
    code = os.environ.get('PPA_PRINTER_ACCESS_CODE') or getpass.getpass('프린터 화면의 LAN 액세스 코드(입력은 보이지 않음): ')
    serial = args.serial.strip().upper()
    try:
        result = printer_lan.read_status(args.host.strip(), serial, code.strip(), keep_raw=True)
    except (ValueError, printer_lan.PrinterBusy) as error:
        print(f'시작하지 못했습니다: {error}', file=sys.stderr)
        return 2
    finally:
        code = None
    report = build_report(result, serial)
    args.out_dir.mkdir(parents=True, exist_ok=True)
    path = args.out_dir / f"probe-{datetime.now().strftime('%Y%m%d-%H%M%S')}.json"
    text = json.dumps(report, ensure_ascii=False, indent=2)
    if serial.casefold() in text.casefold() or args.host.strip() in text:
        print('보고서에 식별 정보가 남아 저장하지 않았습니다.', file=sys.stderr)
        return 3
    path.write_text(text + '\n', encoding='utf-8')
    print(f"연결 결과: {report['connection_state']} — {report['connection_detail']}")
    understood = report['understood_by_app'] or {}
    identity = understood.get('identity') or {}
    printing = understood.get('print') or {}
    if understood:
        print(f"제품 이름 보고: {identity.get('product_name')} · 펌웨어 보고: {identity.get('firmware')}")
        print(f"상태: {printing.get('state_label')} · 노즐: {printing.get('nozzle')} · 재료 칸 {len(printing.get('material_slots') or [])}개")
    print(f'기록 파일: {path}')
    return 0 if report['connection_state'] == 'reporting' else 1


if __name__ == '__main__':
    sys.exit(main())
