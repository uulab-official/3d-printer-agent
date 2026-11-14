#!/usr/bin/env python3
"""Qualify an installed wheel through real local HTTP/CAD and restart behavior.

Run outside the checkout, after installing the exact wheel and its dependencies.
All fault injection targets a fresh synthetic directory created by this script.
No browser, native slicer, provider, account, or physical printer is used.
"""
import argparse
from datetime import datetime, timezone
from email.parser import BytesParser
import hashlib
import importlib.metadata
import io
import json
import os
from pathlib import Path
import platform
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import traceback
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
import zipfile


def sha256(content):
    return hashlib.sha256(content).hexdigest()


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')


def available_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as reservation:
        reservation.bind(('127.0.0.1', 0))
        return reservation.getsockname()[1]


def request(base, path, *, method='GET', payload=None, token=None, timeout=90):
    body = None if payload is None else json.dumps(payload, ensure_ascii=False, allow_nan=False).encode('utf-8')
    headers = {'Origin': base}
    if body is not None:
        headers['Content-Type'] = 'application/json'
    if token is not None:
        headers['X-Session-Token'] = token
    message = urllib.request.Request(base + path, data=body, method=method, headers=headers)
    try:
        response = urllib.request.build_opener(urllib.request.ProxyHandler({})).open(message, timeout=timeout)
    except urllib.error.HTTPError as exc:
        response = exc
    with response:
        return response.status, response.read(), dict(response.headers)


class Server:
    def __init__(self, data_dir, working_dir, report_dir, name, environment):
        self.port = available_port()
        self.base = f'http://127.0.0.1:{self.port}'
        self.log_path = report_dir / f'{name}.log'
        self.log = self.log_path.open('wb')
        try:
            self.process = subprocess.Popen(
                [sys.executable, '-m', 'print_agent', '--data-dir', str(data_dir), '--port', str(self.port)],
                cwd=working_dir, env=environment, stdout=self.log, stderr=subprocess.STDOUT,
            )
        except Exception:
            self.log.close()
            raise

    def wait_ready(self):
        deadline = time.monotonic() + 70
        while time.monotonic() < deadline:
            if self.process.poll() is not None:
                raise RuntimeError(f'Installed server exited ({self.process.returncode}); see {self.log_path.name}')
            try:
                status, body, _ = request(self.base, '/api/bootstrap', timeout=1)
                if status == 200:
                    return json.loads(body)
            except (OSError, ValueError):
                pass
            time.sleep(0.1)
        raise TimeoutError(f'Installed server did not start; see {self.log_path.name}')

    def stop(self):
        try:
            if self.process.poll() is None:
                self.process.terminate()
                try:
                    self.process.wait(timeout=12)
                except subprocess.TimeoutExpired:
                    self.process.kill()
                    self.process.wait(timeout=8)
        finally:
            self.log.close()


def qualify(args, report):
    checks = report['checks']

    def check(name, condition, detail=''):
        checks.append({'id': name, 'passed': bool(condition), 'detail': detail})
        if not condition:
            raise AssertionError(f'{name}: {detail}')

    def get_json(server, path, *, method='GET', payload=None, token=None, expected=200):
        status, content, _ = request(server.base, path, method=method, payload=payload, token=token)
        check(f'http_{method.lower()}_{path.split("?")[0]}', status == expected, f'HTTP {status}; expected {expected}')
        return json.loads(content)

    source = Path(__file__).resolve().parents[1]
    check('working_directory_outside_checkout', not Path.cwd().resolve().is_relative_to(source))
    receipt_bytes = args.receipt.read_bytes()
    receipt = json.loads(receipt_bytes)
    wheel_bytes = args.wheel.read_bytes()
    report['wheel'] = {'filename': args.wheel.name, 'bytes': len(wheel_bytes), 'sha256': sha256(wheel_bytes),
                       'receipt_sha256': sha256(receipt_bytes)}
    report['source_commit'] = receipt['source_commit']
    check('wheel_filename_matches_receipt', args.wheel.name == receipt['filename'])
    check('wheel_byte_size_matches_receipt', len(wheel_bytes) == receipt['bytes'])
    check('wheel_sha256_matches_receipt', sha256(wheel_bytes) == receipt['sha256'])
    check('source_commit_is_exact_sha', isinstance(receipt['source_commit'], str)
          and len(receipt['source_commit']) == 40 and all(c in '0123456789abcdef' for c in receipt['source_commit']))
    shutil.copyfile(args.receipt, args.report_dir / 'wheel-receipt.json')
    (args.report_dir / 'wheel.sha256').write_text(f'{sha256(wheel_bytes)}  {args.wheel.name}\n', encoding='utf-8')

    import print_agent
    import cadquery as cq
    from print_agent.runtime import DataDirectoryLease
    from print_agent.storage import JobStore

    package_dir = Path(print_agent.__file__).resolve().parent
    report['installed_package'] = str(package_dir)
    report['versions'] = {'application': print_agent.__version__, 'cadquery': cq.__version__,
                          'distribution': importlib.metadata.version('3d-printer-agent-local')}
    check('imported_package_outside_checkout', not package_dir.is_relative_to(source))
    with zipfile.ZipFile(io.BytesIO(wheel_bytes)) as wheel:
        check('wheel_crc', wheel.testzip() is None)
        metadata_names = [name for name in wheel.namelist() if name.endswith('.dist-info/METADATA')]
        check('single_wheel_metadata', len(metadata_names) == 1)
        metadata = BytesParser().parsebytes(wheel.read(metadata_names[0]))
        check('installed_version_matches_wheel', metadata['Version'] == print_agent.__version__
              == report['versions']['distribution'])
        files = [name for name in wheel.namelist() if name.startswith('print_agent/') and not name.endswith('/')]
        for name in files:
            installed = package_dir.parent / name
            check('installed_bytes_' + name, installed.is_file() and installed.read_bytes() == wheel.read(name))
        report['packaged_application_files'] = len(files)

    work = Path(tempfile.mkdtemp(prefix='installed-work-', dir=args.report_dir))
    data = work / '한국어 data space'
    downloads = args.report_dir / 'downloads'
    downloads.mkdir()
    environment = {key: value for key, value in os.environ.items() if key not in {'PYTHONPATH', 'PPA_DATA_DIR'}}
    environment.update(PPA_LLM_BASE_URL='', PPA_LLM_MODEL='', PPA_LLM_API_KEY='',
                       PPA_BAMBU_PATH=str(work / 'missing-bambu-studio'), PYTHONUTF8='1', PYTHONIOENCODING='utf-8')
    entrypoint = shutil.which('printer-agent')
    check('installed_console_entrypoint', entrypoint is not None)
    doctor = subprocess.run([entrypoint, 'doctor', '--data-dir', str(data)], cwd=work, env=environment,
                            capture_output=True, text=True, encoding='utf-8', timeout=45)
    (args.report_dir / 'doctor-stdout.json').write_text(doctor.stdout, encoding='utf-8')
    (args.report_dir / 'doctor-stderr.log').write_text(doctor.stderr, encoding='utf-8')
    check('installed_doctor_success', doctor.returncode == 0, f'exit {doctor.returncode}')
    diagnostic = json.loads(doctor.stdout)
    check('console_version_matches_installed_distribution', diagnostic['version'] == print_agent.__version__)
    check('doctor_reports_required_readiness', diagnostic['ready'] is True)
    check('doctor_reports_selected_unicode_path', diagnostic['storage']['path'] == str(data.resolve())
          and diagnostic['storage']['source'] == 'argument')
    check('doctor_does_not_initialize_data', not data.exists())
    check('optional_services_remain_unconfigured', not diagnostic['provider']['configured']
          and not diagnostic['slicer']['available'])

    servers = []
    try:
        server = Server(data, work, args.report_dir, 'server-first', environment)
        servers.append(server)
        bootstrap = server.wait_ready()
        token = bootstrap['session_token']
        check('bootstrap_storage_identity', bootstrap['storage']['path'] == str(data.resolve())
              and bootstrap['storage']['source'] == 'argument')
        for path in ('/', '/static/app.js', '/static/style.css'):
            status, content, _ = request(server.base, path)
            check('installed_http_asset_' + path, status == 200 and bool(content))

        selected = next(project for project in bootstrap['discovery']['projects'] if project['id'] == 'small-parts-tray')
        check('known_original_recipe_dimensions', selected['parameters']['width'] == 90
              and selected['parameters']['depth'] == 60 and selected['parameters']['height'] == 18)
        requests = [
            ({**selected['parameters'], 'width': 92,
              'project_selection': {'id': selected['id'], 'recipe_sha256': selected['recipe_sha256']}}, (92, 60, 18)),
            ({'template': 'cable_comb', 'width': 80, 'depth': 18, 'height': 12, 'slots': 5}, (80, 18, 12)),
            ({'template': 'magnet_frame', 'width': 65, 'depth': 65, 'height': 7}, (65, 65, 7)),
        ]
        models = []
        for payload, dimensions in requests:
            job = get_json(server, '/api/models', method='POST', payload=payload, token=token)
            kind = payload['template']
            check('cad_validated_' + kind, job['status'] == 'geometry_validated'
                  and job['result']['geometry_status'] == 'validated')
            check('physical_print_stays_unverified_' + kind, job['result']['print_status'] == 'not_tested'
                  and job['latest_slice'] is None)
            manifest = get_json(server, job['artifacts']['manifest'])
            write_json(downloads / f'{kind}-manifest.json', manifest)
            for artifact_kind, metadata in manifest['artifacts'].items():
                status, content, _ = request(server.base, job['artifacts'][artifact_kind])
                check('download_receipt_' + kind + '_' + artifact_kind,
                      status == 200 and len(content) == metadata['bytes'] and sha256(content) == metadata['sha256'])
                filename = {'stl': 'model.stl', 'step': 'model.step', 'three_mf': 'model.3mf', 'source': 'model.py'}[artifact_kind]
                (downloads / f'{kind}-{filename}').write_bytes(content)
            shape = cq.importers.importStep(str(downloads / f'{kind}-model.step')).val()
            check('step_valid_solid_' + kind, shape.isValid() and len(shape.Solids()) == 1 and shape.Volume() > 0)
            bounds = shape.BoundingBox()
            check('step_dimensions_' + kind, all(abs(getattr(bounds, axis + 'len') - expected) < 1e-5
                                                for axis, expected in zip('xyz', dimensions)))
            with zipfile.ZipFile(downloads / f'{kind}-model.3mf') as archive:
                check('3mf_crc_' + kind, archive.testzip() is None)
                model = ET.fromstring(archive.read('3D/3dmodel.model'))
                vertices = model.findall('.//{*}vertex')
                check('3mf_mm_geometry_' + kind, model.attrib.get('unit') == 'millimeter' and len(vertices) >= 8)
                mesh_bounds = {axis: max(float(v.attrib[axis]) for v in vertices) - min(float(v.attrib[axis]) for v in vertices)
                               for axis in 'xyz'}
                check('3mf_dimensions_' + kind, all(abs(mesh_bounds[axis] - expected) < 1e-5
                                                  for axis, expected in zip('xyz', dimensions)))
            models.append({'template': kind, 'id': job['id'], 'expected_dimensions_mm': dict(zip('xyz', dimensions)),
                           'mesh_vertices': len(vertices), 'artifacts': manifest['artifacts'],
                           'source': job.get('design_source')})
        report['models'] = models
        source_record = models[0]['source']
        check('customized_original_is_recorded', source_record['recipe']['parameters']['width'] == 90
              and source_record['changed_parameters'] == ['width'] and source_record['customized'] is True)
        recipe_digest = sha256(json.dumps(source_record['recipe'], sort_keys=True, separators=(',', ':'),
                                         ensure_ascii=False, allow_nan=False).encode('utf-8'))
        check('recorded_recipe_hash', recipe_digest == selected['recipe_sha256'] == source_record['recipe_sha256'])

        snapshot = {'schema_version': 1, 'documents': [{'filename': '합성 filament.json',
                    'profile': {'name': 'Synthetic installation profile', 'inherits': 'Missing synthetic parent'},
                    'draft_text': '{"unfinished":  '}], 'target_index': 0, 'profile_text': '',
                    'setup': {name: '' for name in ('printer_model', 'printer_preset', 'nozzle_diameter', 'plate_type',
                                                   'extruder', 'feed_mode', 'material_id', 'material_identity_status')}}
        snapshot['setup']['material_identity_status'] = 'unknown'
        workspace = get_json(server, '/api/profile-workspaces', method='POST', token=token, expected=201,
                             payload={'title': '설치 검증 작업', 'snapshot': snapshot})
        check('unfinished_workspace_saved_exactly', workspace['snapshot'] == snapshot)

        def data_hashes():
            # Windows denies reads of another handle's locked byte. The stable
            # lock marker is deliberately excluded; all actual user data remains.
            return {str(path.relative_to(data)): sha256(path.read_bytes()) for path in data.rglob('*')
                    if path.is_file() and path.name != '.printer-agent.lock'}

        before_competitor = data_hashes()
        competitor = Server(data, work, args.report_dir, 'server-conflicting-owner', environment)
        servers.append(competitor)
        try:
            competitor.process.wait(timeout=20)
        except subprocess.TimeoutExpired:
            check('second_live_server_is_rejected', False, 'second server remained alive with the same data directory')
        check('second_live_server_is_rejected', competitor.process.returncode != 0)
        competitor.stop()
        check('rejected_owner_does_not_modify_user_data', before_competitor == data_hashes())
        get_json(server, '/api/jobs?limit=2')
        server.stop()

        # Deliberate offline faults only in this script's fresh synthetic store.
        request_before_crash = {**selected['parameters'], 'width': 47}
        with DataDirectoryLease(data):
            store = JobStore(data)
            interrupted_id, partial_folder = store.reserve(request=request_before_crash, design_source=source_record)
            saved_request = store.get(interrupted_id)['request']
            partial = partial_folder / 'partial-model.stl'
            partial.write_bytes(b'synthetic incomplete export; preserve these bytes')
            partial_sha = sha256(partial.read_bytes())
        del store
        for suffix in ('', '-wal', '-shm', '-journal'):
            (data / ('history.sqlite3' + suffix)).unlink(missing_ok=True)

        restarted = Server(data, work, args.report_dir, 'server-restarted', environment)
        servers.append(restarted)
        refreshed = restarted.wait_ready()
        recovery = refreshed['storage']['recovery']
        check('restart_reconciles_index_and_interrupted_job', recovery['indexed'] == 4
              and recovery['interrupted'] == 1 and recovery['unreadable'] == 0, json.dumps(recovery))
        check('restart_rotates_session', refreshed['session_token'] != token)
        old_session = get_json(restarted, '/api/discovery', method='POST', payload={}, token=token, expected=403)
        check('expired_session_has_explicit_code', old_session.get('code') == 'session_expired')
        get_json(restarted, '/api/discovery', method='POST', payload={}, token=refreshed['session_token'])
        restored = get_json(restarted, '/api/profile-workspaces/' + workspace['id'])
        check('workspace_survives_real_restart', restored == workspace and restored['snapshot'] == snapshot)
        retained_job = get_json(restarted, '/api/jobs/' + models[0]['id'])
        check('generation_source_survives_restart', retained_job['design_source'] == source_record
              and retained_job['result']['parameters']['width'] == 92)
        abandoned = get_json(restarted, '/api/jobs/' + interrupted_id)
        check('interrupted_job_preserves_inputs_without_verified_outputs', abandoned['status'] == 'interrupted'
              and abandoned['request'] == saved_request and abandoned['design_source'] == source_record
              and not abandoned['artifacts'] and abandoned['bundle_url'] is None and abandoned['result'] is None)
        check('partial_file_bytes_preserved', sha256(partial.read_bytes()) == partial_sha)
        events = [event for event in abandoned['events'] if event['type'] == 'generation_interrupted']
        check('interruption_recorded_once', len(events) == 1)

        paged_ids, cursor = [], None
        for _ in range(4):
            query = urllib.parse.urlencode({'limit': 2, **({'before': cursor} if cursor else {})})
            page = get_json(restarted, '/api/jobs?' + query)
            paged_ids.extend(item['id'] for item in page['jobs'])
            cursor = page['next_cursor']
            if cursor is None:
                break
        check('history_cursor_reaches_all_recovered_jobs', cursor is None and len(paged_ids) == 4
              and set(paged_ids) == {model['id'] for model in models} | {interrupted_id})

        tampered = data / 'jobs' / models[0]['id'] / 'model.3mf'
        tampered.write_bytes(b'synthetic altered artifact; do not rewrite')
        damaged_bytes = tampered.read_bytes()
        bad_download = get_json(restarted, retained_job['artifacts']['three_mf'], expected=409)
        check('altered_artifact_is_not_downloaded', bad_download.get('code') == 'artifact_integrity')
        bad_bundle = get_json(restarted, retained_job['bundle_url'], expected=409)
        check('altered_artifact_blocks_bundle', bad_bundle.get('code') == 'artifact_integrity')
        check('damaged_artifact_bytes_preserved', tampered.read_bytes() == damaged_bytes)
        healthy_job = get_json(restarted, '/api/jobs/' + models[1]['id'])
        status, healthy_bytes, _ = request(restarted.base, healthy_job['artifacts']['three_mf'])
        check('unrelated_verified_download_remains_available', status == 200
              and sha256(healthy_bytes) == models[1]['artifacts']['three_mf']['sha256'])
        report['recovery'] = {'counts': recovery, 'interrupted_id': interrupted_id,
                              'request': saved_request, 'partial_sha256': partial_sha,
                              'workspace_id': workspace['id'], 'paged_job_ids': paged_ids}
    finally:
        for server in reversed(servers):
            server.stop()
    with DataDirectoryLease(data):
        check('stopped_server_releases_data_directory', True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--wheel', type=Path, required=True)
    parser.add_argument('--receipt', type=Path, required=True)
    parser.add_argument('--report-dir', type=Path, required=True)
    args = parser.parse_args()
    args.wheel = args.wheel.resolve()
    args.receipt = args.receipt.resolve()
    args.report_dir = args.report_dir.resolve()
    args.report_dir.mkdir(parents=True, exist_ok=True)
    report = {'schema_version': 1, 'status': 'running',
              'started_at': datetime.now(timezone.utc).isoformat(),
              'platform': {'system': platform.system(), 'release': platform.release(), 'machine': platform.machine()},
              'python': platform.python_version(), 'checks': [],
              'script_sha256': sha256(Path(__file__).read_bytes()),
              'limits': {'synthetic_data': True, 'native_slicer_executed': False, 'browser_executed': False,
                         'live_provider_executed': False, 'physical_print_verified': False}}
    exit_code = 0
    try:
        qualify(args, report)
        report['status'] = 'passed'
    except Exception as exc:
        report['status'] = 'failed'
        report['error'] = {'type': type(exc).__name__, 'message': str(exc)}
        (args.report_dir / 'failure.log').write_text(traceback.format_exc(), encoding='utf-8')
        exit_code = 1
    finally:
        report['completed_at'] = datetime.now(timezone.utc).isoformat()
        report['checks_passed'] = sum(check['passed'] for check in report['checks'])
        report['checks_total'] = len(report['checks'])
        write_json(args.report_dir / 'report.json', report)
        print(json.dumps({'status': report['status'], 'checks_passed': report['checks_passed'],
                          'checks_total': report['checks_total'], 'report': str(args.report_dir / 'report.json')}, ensure_ascii=False))
    return exit_code


if __name__ == '__main__':
    raise SystemExit(main())
