#!/usr/bin/env python3
"""A synthetic Moonraker server for demos and tests. It is not a real printer.

It answers only the four read requests the app makes, with labelled synthetic
values shaped like a four-toolhead Klipper printer. Nothing is printed.

    python scripts/fake_moonraker.py --port 7125 [--api-key KEY] [--state printing|standby|paused|complete|error]
                                     [--klippy ready|startup|shutdown]
"""
from __future__ import annotations

import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import sys
import threading
from urllib.parse import parse_qs, urlsplit

TOOLS = 4


def objects():
    return (['webhooks', 'configfile', 'print_stats', 'virtual_sdcard', 'display_status', 'toolhead', 'heater_bed',
             'gcode_move', 'fan'] + ['extruder'] + [f'extruder{i}' for i in range(1, TOOLS)])


def status(state):
    printing = state in ('printing', 'paused')
    data = {
        'print_stats': {'state': state, 'filename': 'synthetic-cube.gcode' if state != 'standby' else '',
                        'print_duration': 1200.0 if printing else 0.0, 'total_duration': 1260.0 if printing else 0.0,
                        'message': 'Synthetic MCU shutdown' if state == 'error' else '',
                        'info': {'current_layer': 42 if printing else None, 'total_layer': 120 if printing else None}},
        'virtual_sdcard': {'progress': 0.4 if printing else (1.0 if state == 'complete' else 0.0), 'is_active': state == 'printing'},
        'display_status': {'progress': 0.4 if printing else 0.0, 'message': None},
        'toolhead': {'extruder': 'extruder1', 'homed_axes': 'xyz' if printing else ''},
        'heater_bed': {'temperature': 59.8 if printing else 24.1, 'target': 60.0 if printing else 0.0},
    }
    for index in range(TOOLS):
        name = 'extruder' if index == 0 else f'extruder{index}'
        active = index == 1 and printing
        data[name] = {'temperature': 219.6 if active else 140.0 if printing else 24.5, 'target': 220.0 if active else 140.0 if printing else 0.0}
    return data


def make_handler(options):
    class Handler(BaseHTTPRequestHandler):
        server_version = 'SyntheticMoonraker/1.0'

        def log_message(self, fmt, *args):  # noqa: N802 - quiet unless asked
            if options.verbose:
                sys.stderr.write('[fake-moonraker] ' + fmt % args + '\n')

        def reply(self, code, payload):
            body = json.dumps(payload).encode()
            self.send_response(code)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):  # noqa: N802
            if options.api_key and self.headers.get('X-Api-Key') != options.api_key:
                return self.reply(401, {'error': {'code': 401, 'message': 'Unauthorized'}})
            url = urlsplit(self.path)
            if url.path == '/server/info':
                return self.reply(200, {'result': {'klippy_connected': True, 'klippy_state': options.klippy,
                                                   'moonraker_version': 'v0.9.3-synthetic', 'api_version_string': '1.5.0'}})
            if url.path == '/printer/info':
                return self.reply(200, {'result': {'state': options.klippy, 'state_message': f'Synthetic printer is {options.klippy}',
                                                   'hostname': 'synthetic-klipper', 'software_version': 'v0.13.0-synthetic',
                                                   'cpu_info': 'synthetic'}})
            if options.klippy != 'ready':
                return self.reply(503, {'error': {'code': 503, 'message': 'Klippy Host not connected'}})
            if url.path == '/printer/objects/list':
                return self.reply(200, {'result': {'objects': objects()}})
            if url.path == '/printer/objects/query':
                names = list(parse_qs(url.query, keep_blank_values=True))
                full = status(options.state)
                return self.reply(200, {'result': {'eventtime': 1234.5, 'status': {n: full[n] for n in names if n in full}}})
            return self.reply(404, {'error': {'code': 404, 'message': 'Not Found'}})

    return Handler


def serve(options, ready=None):
    server = ThreadingHTTPServer((options.host, options.port), make_handler(options))
    if ready is not None:
        ready(server)
    try:
        server.serve_forever(poll_interval=0.1)
    finally:
        server.server_close()


def start_in_thread(**overrides):
    """Start on an ephemeral loopback port for tests; returns (server, port)."""
    options = parse([])
    options.port = 0
    for key, value in overrides.items():
        setattr(options, key, value)
    holder = {}
    started = threading.Event()

    def ready(server):
        holder['server'] = server
        started.set()

    threading.Thread(target=serve, args=(options, ready), daemon=True).start()
    started.wait(5)
    server = holder['server']
    return server, server.server_address[1]


def parse(argv):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=7125)
    parser.add_argument('--api-key', default=None)
    parser.add_argument('--state', default='printing', choices=['standby', 'printing', 'paused', 'complete', 'cancelled', 'error'])
    parser.add_argument('--klippy', default='ready', choices=['ready', 'startup', 'shutdown', 'error'])
    parser.add_argument('--verbose', action='store_true')
    return parser.parse_args(argv)


if __name__ == '__main__':
    opts = parse(sys.argv[1:])
    print(f'[fake-moonraker] synthetic Moonraker on http://{opts.host}:{opts.port} (state {opts.state}, klippy {opts.klippy}); nothing is printed', flush=True)
    serve(opts)
