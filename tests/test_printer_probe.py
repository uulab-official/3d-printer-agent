import importlib.util
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('printer_field_probe', ROOT / 'scripts' / 'printer_field_probe.py')
probe = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = probe
spec.loader.exec_module(probe)

SERIAL = '0948AB000001895'


def raw_report():
    return {
        'print': {
            'gcode_state': 'IDLE', 'nozzle_diameter': '0.4', 'nozzle_type': 'hardened_steel', 'sn': SERIAL,
            'gcode_file': '/sdcard/secret-part.gcode.3mf', 'subtask_name': 'secret-part', 'wifi_signal': '-50dBm',
            'net': {'info': [{'ip': 3232235726, 'mask': 16777215}]}, 'ipcam': {'rtsp_url': 'rtsps://192.168.0.206/streaming'},
            'device': {'extruder': {'info': [{'id': 0, 'diameter': 0.4, 'type': 'HS'}]}},
            'ams': {'ams': [{'id': '0', 'sn': SERIAL[:-1] + '9', 'tray': [{'id': '0', 'tray_type': 'PLA', 'tray_uuid': 'ABC'}]}],
                    'tray_now': '0'},
            'hms': [{'attr': 0x0300_0100, 'code': 0x0001_0001}],
            'note': 'printer ' + SERIAL,
        },
        'info': {'command': 'get_version', 'module': [{'name': 'ota', 'sn': SERIAL, 'sw_ver': '01.02.00.00'},
                                                      {'name': 'mc', 'product_name': 'Bambu Lab X2D', 'sw_ver': '00.01'}]},
    }


class PrinterProbeTests(unittest.TestCase):
    def test_layout_keeps_allow_listed_values_and_reduces_everything_else_to_types(self):
        layout = probe.shape(raw_report()['print'], serial=SERIAL)
        self.assertEqual((layout['gcode_state'], layout['nozzle_type'], layout['nozzle_diameter']), ('IDLE', 'hardened_steel', '0.4'))
        self.assertEqual(layout['sn'], '<str>')
        self.assertEqual((layout['gcode_file'], layout['subtask_name']), ('<str>', '<str>'))
        self.assertEqual(layout['net'], '<dict, not recorded>')
        self.assertEqual(layout['ipcam'], '<dict, not recorded>')
        self.assertEqual(layout['ams']['ams'][0]['tray'][0], {'id': '0', 'tray_type': 'PLA', 'tray_uuid': '<str>'})
        self.assertEqual(layout['ams']['ams'][0]['sn'], '<str>')
        self.assertEqual(layout['device']['extruder']['info'][0], {'diameter': 0.4, 'id': 0, 'type': 'HS'})
        self.assertEqual(layout['hms'][0]['code'], 0x0001_0001)
        self.assertEqual(layout['note'], '<str>')

    def test_report_never_contains_the_serial_address_or_names(self):
        result = {'connection': {'state': 'reporting', 'detail': 'ok'}, 'certificate': {'sha256': 'f' * 64},
                  'identity': {'product_name': 'Bambu Lab X2D', 'firmware': '01.02.00.00', 'report_topic_serial': SERIAL},
                  'print': {'state': 'IDLE'}, 'target': {'host': '192.168.0.206', 'serial': SERIAL}, 'raw': raw_report()}
        report = probe.build_report(result, SERIAL)
        text = json.dumps(report)
        for secret in (SERIAL, '192.168.0.206', 'secret-part', 'rtsps'):
            self.assertNotIn(secret, text)
        self.assertEqual(report['understood_by_app']['identity']['product_name'], 'Bambu Lab X2D')
        self.assertEqual(report['raw_layout']['info']['module'][1]['product_name'], 'Bambu Lab X2D')
        self.assertEqual(report['certificate_sha256_prefix'], 'f' * 12)
        self.assertEqual(report['requests_sent'], ['pushall', 'get_version'])

    def test_a_failed_connection_records_only_the_outcome(self):
        report = probe.build_report({'connection': {'state': 'access_rejected', 'detail': 'rejected'}}, SERIAL)
        self.assertEqual(report['connection_state'], 'access_rejected')
        self.assertIsNone(report['understood_by_app'])
        self.assertIsNone(report['raw_layout'])

    def test_lists_are_bounded(self):
        layout = probe.shape({'hms': [{'attr': i, 'code': i} for i in range(20)]})
        self.assertEqual(len(layout['hms']), probe.MAX_LIST_ITEMS + 1)
        self.assertEqual(layout['hms'][-1], '<12 more>')


if __name__ == '__main__':
    unittest.main()
