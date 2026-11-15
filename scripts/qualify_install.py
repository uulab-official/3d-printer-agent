#!/usr/bin/env python3
"""Qualify an installed wheel through real local HTTP/CAD and restart behavior.

Run outside the checkout, after installing the exact wheel and its dependencies.
All fault injection targets a fresh synthetic directory created by this script.
No browser, native slicer, provider, account, or physical printer is used.
"""
import argparse
import base64
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

        # This is a labeled synthetic source container, not an authenticated
        # user's GUI export. Its complete settings came from the separately
        # retained native CI fixture. The installed app supplies all behavior.
        settings_path = source / 'tests/fixtures/studio_project_synthetic_settings.json'
        settings_bytes = settings_path.read_bytes()
        core = 'http://schemas.microsoft.com/3dmanufacturing/core/2015/02'
        fixture_xml = (f'<model xmlns="{core}" unit="millimeter">'
                       '<metadata name="Application">BambuStudio-02.09.01.70</metadata>'
                       '<metadata name="BambuStudio:3mfVersion">1</metadata>'
                       '<resources/><build/></model>').encode('utf-8')
        stream = io.BytesIO()
        with zipfile.ZipFile(stream, 'w', compression=zipfile.ZIP_DEFLATED) as fixture:
            fixture.writestr('Metadata/project_settings.config', settings_bytes)
            fixture.writestr('3D/3dmodel.model', fixture_xml)
        source_bytes = stream.getvalue()
        (downloads / 'synthetic-source-project.3mf').write_bytes(source_bytes)
        imported = get_json(server, '/api/studio-projects/import', method='POST', token=token, expected=201,
                            payload={'filename': '합성 설정 원본.3mf',
                                     'content_base64': base64.b64encode(source_bytes).decode('ascii')})
        check('studio_source_identity_and_public_scope', imported['supported'] is True
              and imported['source']['sha256'] == sha256(source_bytes)
              and imported['settings_sha256'] == sha256(settings_bytes)
              and 'settings_text' not in imported and 'expected_settings' not in imported)
        inspected = get_json(server, '/api/studio-projects/' + imported['source_id'])
        check('studio_source_reinspection_matches', inspected == imported)
        code, original, _ = request(server.base, imported['archive_url'])
        check('studio_original_download_exact', code == 200 and original == source_bytes)

        # Exercise all six user-selected fields through the installed HTTP API.
        # These literal synthetic values are independent of the derivation engine.
        editor_path = '/api/studio-projects/' + imported['source_id'] + '/settings'
        editor = get_json(server, editor_path)
        values = {'nozzle_temperature': '225', 'nozzle_temperature_initial_layer': '230',
                  'filament_flow_ratio': '0.98', 'filament_max_volumetric_speed': '7.5',
                  'bed_temperature': '60', 'bed_temperature_initial_layer': '65'}
        native_values = {'nozzle_temperature': ['225'], 'nozzle_temperature_initial_layer': ['230'],
                         'filament_flow_ratio': ['0.98'], 'filament_max_volumetric_speed': ['7.5'],
                         'hot_plate_temp': ['60'], 'hot_plate_temp_initial_layer': ['65']}
        check('studio_editor_six_original_bound_fields', editor['source_id'] == imported['source_id']
              and {field['key'] for field in editor['fields']} == set(values)
              and {field['native_key'] for field in editor['fields']} == set(native_values)
              and editor['settings_sha256'] == sha256(settings_bytes))
        proposal = {'source_sha256': sha256(source_bytes), 'settings_sha256': sha256(settings_bytes),
                    'values': values}
        review = get_json(server, editor_path + '/review', method='POST', token=token, payload=proposal)
        expected_settings = {**json.loads(settings_bytes), **native_values}
        core_keys = {'printer_settings_id', 'print_settings_id', 'filament_settings_id', 'printer_model',
                     'printer_technology', 'nozzle_diameter', 'printable_area', 'printable_height',
                     'machine_start_gcode', 'machine_end_gcode', 'layer_height', 'initial_layer_print_height',
                     'wall_loops', 'top_shell_layers', 'bottom_shell_layers', 'sparse_infill_density',
                     'outer_wall_speed', 'inner_wall_speed', 'sparse_infill_speed', 'initial_layer_speed',
                     'curr_bed_type', 'filament_type', 'filament_diameter', 'filament_density',
                     'filament_flow_ratio', 'filament_max_volumetric_speed', 'nozzle_temperature',
                     'nozzle_temperature_initial_layer', 'hot_plate_temp', 'hot_plate_temp_initial_layer'}
        expected_core = {key: expected_settings[key] for key in core_keys}
        effective_bytes = json.dumps(expected_settings, sort_keys=True, separators=(',', ':'),
                                    ensure_ascii=False, allow_nan=False).encode('utf-8')
        check('studio_review_six_independent_changes', review['changed_count'] == 6
              and review['provenance'] == 'user_selected'
              and {change['native_key']: change['after'] for change in review['changes']} == native_values
              and all(change['before'] == json.loads(settings_bytes)[change['native_key']]
                      for change in review['changes'])
              and review['effective_settings_sha256'] == sha256(effective_bytes))
        get_json(server, editor_path + '/revisions', method='POST', token=token, expected=422,
                 payload={**proposal, 'review_sha256': '0' * 64})
        check('studio_changed_review_does_not_publish', not list((data / 'studio-settings-revisions').glob('*/revision.json')))
        revision = get_json(server, editor_path + '/revisions', method='POST', token=token, expected=201,
                            payload={**proposal, 'review_sha256': review['review_sha256']})
        revision_id = revision['revision']['revision_id']
        revision_path = '/api/studio-settings-revisions/' + revision_id
        check('studio_saved_revision_matches_review', get_json(server, revision_path) == revision
              and revision['source'] == imported and revision['revision']['proposal'] == proposal
              and revision['review'] == {key: value for key, value in review.items() if key != 'source_id'})

        # Persist inputs before any CAD exists, then rediscover without a job ID.
        def library_snapshot(*, edited=False, draft=None):
            return {'schema_version': 1, 'source_id': imported['source_id'],
                    'settings_revision_id': revision_id if edited else None,
                    'source_sha256': sha256(source_bytes), 'settings_sha256': sha256(settings_bytes),
                    'effective_settings_sha256': sha256(effective_bytes) if edited else sha256(settings_bytes),
                    'draft_values': draft}

        unfinished_values = {**values, 'filament_flow_ratio': ' 1. ',
                             'filament_max_volumetric_speed': 'x' * 33}
        library_records = []
        for title, snapshot in [('원본 설정', library_snapshot()),
                                ('사용자 변경값', library_snapshot(edited=True)),
                                ('미완성 초안', library_snapshot(edited=True, draft=unfinished_values))]:
            record = get_json(server, '/api/studio-workspaces', method='POST', token=token, expected=201,
                              payload={'title': title, 'snapshot': snapshot})
            check('studio_library_save_' + title, record['title'] == title and record['snapshot'] == snapshot
                  and record['revision'] == 1)
            library_records.append(record)
        check('studio_library_saved_without_cad', get_json(server, '/api/jobs')['jobs'] == [])
        updated_record = get_json(server, '/api/studio-workspaces/' + library_records[1]['id'],
            method='PUT', token=token, payload={'title': '사용자 변경값 이름 수정',
                'snapshot': library_records[1]['snapshot'], 'expected_revision': 1})
        check('studio_library_conditional_update', updated_record['revision'] == 2
              and updated_record['snapshot'] == library_records[1]['snapshot'])
        stale_payload = {'title': '오래된 창', 'snapshot': library_records[1]['snapshot'], 'expected_revision': 1}
        get_json(server, '/api/studio-workspaces/' + updated_record['id'], method='PUT', token=token,
                 expected=409, payload=stale_payload)
        get_json(server, '/api/studio-workspaces/' + updated_record['id'], method='DELETE', token=token,
                 expected=409, payload={'expected_revision': 1})
        check('studio_library_conflicts_preserve_newer_record',
              get_json(server, '/api/studio-workspaces/' + updated_record['id'])['workspace'] == updated_record)
        library_records[1] = updated_record
        disposable = get_json(server, '/api/studio-workspaces', method='POST', token=token, expected=201,
                             payload={'title': '삭제할 이름', 'snapshot': library_snapshot(edited=True)})
        status, body, _ = request(server.base, '/api/studio-workspaces/' + disposable['id'], method='DELETE',
                                 token=token, payload={'expected_revision': 1})
        check('studio_library_delete_retains_original_and_recipe', status == 204 and body == b''
              and get_json(server, revision_path) == revision
              and request(server.base, imported['archive_url'])[1] == source_bytes)
        duplicate_source = get_json(server, '/api/studio-projects/import', method='POST', token=token, expected=201,
            payload={'filename': imported['source']['filename'], 'content_base64': base64.b64encode(source_bytes).decode('ascii')})

        def library_catalog(current_server, kind):
            items, cursor = [], None
            for _ in range(8):
                query = urllib.parse.urlencode({'kind': kind, 'limit': 1, **({'before': cursor} if cursor else {})})
                page = get_json(current_server, '/api/studio-library?' + query)
                items.extend(page['items'])
                cursor = page['next_cursor']
                if cursor is None:
                    return items
            raise RuntimeError('Studio catalog pagination did not finish')

        source_catalog = library_catalog(server, 'sources')
        revision_catalog = library_catalog(server, 'revisions')
        workspace_catalog = library_catalog(server, 'workspaces')
        check('studio_library_legacy_equal_names_discoverable', len(source_catalog) == 2
              and {item['id'] for item in source_catalog} == {imported['source_id'], duplicate_source['source_id']}
              and [item['id'] for item in revision_catalog] == [revision_id])
        check('studio_library_catalog_bounded_inputs_only', len(workspace_catalog) == 3
              and {item['id'] for item in workspace_catalog} == {item['id'] for item in library_records}
              and all(item['metadata_status'] == 'recorded' for item in source_catalog + revision_catalog + workspace_catalog)
              and 'draft_values' not in json.dumps(workspace_catalog)
              and 'ready' not in json.dumps(workspace_catalog))
        library_opened = [get_json(server, '/api/studio-workspaces/' + item['id']) for item in library_records]
        check('studio_library_open_exact_inputs_without_current_review',
              all(item['workspace'] == record and item['source'] == imported
                  and item['editor']['settings_sha256'] == sha256(settings_bytes)
                  and set(item) == {'workspace', 'source', 'settings_revision', 'editor'}
                  for item, record in zip(library_opened, library_records))
              and library_opened[0]['settings_revision'] is None
              and library_opened[1]['settings_revision'] == revision
              and library_opened[2]['workspace']['snapshot']['draft_values'] == unfinished_values)
        write_json(downloads / 'studio-library-records.json', library_records)
        write_json(downloads / 'studio-library-opened.json', library_opened)
        write_json(downloads / 'studio-library-catalogs.json', {
            'sources': source_catalog, 'revisions': revision_catalog, 'workspaces': workspace_catalog})
        report['studio_library'] = {'records': library_records, 'source_ids': [imported['source_id'], duplicate_source['source_id']],
                                    'revision_id': revision_id, 'created_before_cad': True,
                                    'unfinished_values': unfinished_values}

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

        # A supported source format is not a sufficient build-volume review.
        # Exercise actual installed HTTP boundaries and verify that no partial
        # attempt directory or prepared download is published for an oversized CAD.
        small_settings = {**json.loads(settings_bytes), 'printable_height': '11'}
        small_stream = io.BytesIO()
        with zipfile.ZipFile(small_stream, 'w', zipfile.ZIP_DEFLATED) as fixture:
            fixture.writestr('Metadata/project_settings.config', json.dumps(small_settings))
            fixture.writestr('3D/3dmodel.model', fixture_xml)
        small_source = get_json(server, '/api/studio-projects/import', method='POST', token=token, expected=201,
            payload={'filename': '합성 높이 초과 검사.3mf',
                     'content_base64': base64.b64encode(small_stream.getvalue()).decode('ascii')})
        oversized = get_json(server, '/api/slice', method='POST', token=token,
            payload={'job_id': models[1]['id'], 'studio_project_id': small_source['source_id'], 'execute': True})
        oversized_job = get_json(server, '/api/jobs/' + models[1]['id'])
        check('print_volume_rejects_oversized_before_staging', small_source['supported'] is True
              and oversized['plan']['ready'] is False and oversized['plan']['project_prepared'] is False
              and oversized['execution'] is None
              and oversized['plan']['print_volume']['status'] == 'height_exceeded'
              and oversized['plan']['print_volume']['model_dimensions_mm'] == [80, 18, 12]
              and oversized['plan']['print_volume']['recorded_volume_mm'][2] == 11
              and not Path(oversized['plan']['job_dir']).exists()
              and 'prepared_three_mf' not in oversized_job['artifacts'])
        write_json(downloads / 'print-volume-rejected.json', oversized)

        prepared = get_json(server, '/api/slice', method='POST', token=token,
                            payload={'job_id': models[1]['id'], 'studio_project_id': imported['source_id'],
                                     'execute': False})
        plan = prepared['plan']
        check('studio_preparation_without_native', plan['kind'] == 'studio_project'
              and plan['project_prepared'] is True and plan['ready'] is False and prepared['execution'] is None
              and plan['project_source']['source_id'] == imported['source_id'])
        volume_review = plan['print_volume']
        check('print_volume_review_bound_to_verified_cad_and_settings', volume_review['status'] == 'fits'
              and volume_review['can_prepare'] is True and volume_review['placement_applied'] is False
              and volume_review['model_dimensions_mm'] == [80, 18, 12]
              and volume_review['model_sha256'] == models[1]['artifacts']['three_mf']['sha256']
              and volume_review['settings_sha256'] == sha256(settings_bytes)
              and plan['project_receipt']['print_volume'] == volume_review)
        prepared_job = get_json(server, '/api/jobs/' + models[1]['id'])
        check('studio_history_has_distinct_prepared_download', 'prepared_three_mf' in prepared_job['artifacts']
              and 'sliced_three_mf' not in prepared_job['artifacts']
              and prepared_job['latest_slice']['plan'] == plan)
        prepared_url = prepared_job['artifacts']['prepared_three_mf']
        code, prepared_bytes, _ = request(server.base, prepared_url)
        check('studio_prepared_download_receipt', code == 200 and sha256(prepared_bytes) == plan['project_sha256']
              and len(prepared_bytes) == plan['project_receipt']['project_bytes'])
        (downloads / 'prepared-project.3mf').write_bytes(prepared_bytes)
        with zipfile.ZipFile(io.BytesIO(prepared_bytes)) as derivative, zipfile.ZipFile(downloads / 'cable_comb-model.3mf') as cad:
            check('studio_prepared_crc_and_exact_settings', derivative.testzip() is None
                  and derivative.read('Metadata/project_settings.config') == settings_bytes)
            current_mesh = ET.fromstring(cad.read('3D/3dmodel.model')).find('.//{*}mesh')
            prepared_mesh = ET.fromstring(derivative.read('3D/3dmodel.model')).find('.//{*}mesh')
            def mesh_values(mesh):
                return ([tuple(float(vertex.attrib[key]) for key in 'xyz') for vertex in mesh.findall('{*}vertices/{*}vertex')],
                        [tuple(int(face.attrib[key]) for key in ('v1', 'v2', 'v3')) for face in mesh.findall('{*}triangles/{*}triangle')])
            check('studio_prepared_current_cad_vertices_and_topology', current_mesh is not None and prepared_mesh is not None
                  and mesh_values(current_mesh) == mesh_values(prepared_mesh))
        code, bundle_bytes, _ = request(server.base, prepared_job['bundle_url'])
        with zipfile.ZipFile(io.BytesIO(bundle_bytes)) as bundle:
            check('studio_prepared_bundle_distinguishes_original_cad', code == 200
                  and bundle.read('prepared-project.3mf') == prepared_bytes
                  and bundle.read('model.3mf') == (downloads / 'cable_comb-model.3mf').read_bytes())
        report['studio_project'] = {'source': imported, 'preparation': prepared,
                                    'fixture_settings_sha256': sha256(settings_bytes),
                                    'fixture_provenance': 'synthetic container and synthetic CI native settings; no user GUI-export claim',
                                    'job_id': models[1]['id'], 'prepared_sha256': sha256(prepared_bytes),
                                    'prepared_bytes': len(prepared_bytes)}
        write_json(downloads / 'studio-source-inspection.json', imported)
        write_json(downloads / 'studio-preparation.json', prepared)

        edited = get_json(server, '/api/slice', method='POST', token=token,
                          payload={'job_id': models[2]['id'], 'studio_settings_revision_id': revision_id,
                                   'execute': False})
        edited_plan = edited['plan']
        check('studio_revision_preparation_without_native', edited['execution'] is None
              and edited_plan['project_prepared'] is True and edited_plan['ready'] is False
              and edited_plan['project_source'] == imported
              and edited_plan['settings_revision'] == revision['revision']
              and edited_plan['settings_review'] == revision['review']
              and edited_plan['expected_settings'] == expected_core
              and edited_plan['project_receipt']['settings_preserved'] is False)
        edited_job = get_json(server, '/api/jobs/' + models[2]['id'])
        edited_url = edited_job['artifacts']['prepared_three_mf']
        code, edited_bytes, _ = request(server.base, edited_url)
        check('studio_revision_download_matches_receipt', code == 200
              and sha256(edited_bytes) == edited_plan['project_sha256']
              and edited_job['latest_slice']['plan'] == edited_plan
              and 'sliced_three_mf' not in edited_job['artifacts'])
        with zipfile.ZipFile(io.BytesIO(edited_bytes)) as derivative, zipfile.ZipFile(downloads / 'magnet_frame-model.3mf') as cad:
            check('studio_revision_complete_effective_settings', derivative.testzip() is None
                  and derivative.read('Metadata/project_settings.config') == effective_bytes)
            model = ET.fromstring(derivative.read('3D/3dmodel.model'))
            metadata = {item.attrib['name']: item.text for item in model.findall('{*}metadata')}
            check('studio_revision_metadata_and_current_cad',
                  metadata['3DPrinterAgent:SettingsRevisionID'] == revision_id
                  and metadata['3DPrinterAgent:ReviewSHA256'] == review['review_sha256']
                  and metadata['3DPrinterAgent:OriginalSettingsSHA256'] == sha256(settings_bytes)
                  and metadata['3DPrinterAgent:EffectiveSettingsSHA256'] == sha256(effective_bytes)
                  and mesh_values(model.find('.//{*}mesh')) == mesh_values(ET.fromstring(cad.read('3D/3dmodel.model')).find('.//{*}mesh')))
        code, edited_bundle, _ = request(server.base, edited_job['bundle_url'])
        with zipfile.ZipFile(io.BytesIO(edited_bundle)) as bundle:
            check('studio_revision_bundle_retains_current_cad', code == 200
                  and bundle.read('prepared-project.3mf') == edited_bytes
                  and bundle.read('model.3mf') == (downloads / 'magnet_frame-model.3mf').read_bytes())
        code, original_after_edit, _ = request(server.base, imported['archive_url'])
        check('studio_revision_original_archive_unchanged', code == 200 and original_after_edit == source_bytes)
        for name, value in (('settings-editor', editor), ('settings-review', review), ('settings-revision', revision),
                            ('edited-preparation', edited), ('edited-job', edited_job)):
            write_json(downloads / (name + '.json'), value)
        (downloads / 'edited-project.3mf').write_bytes(edited_bytes)
        (downloads / 'edited-job-bundle.zip').write_bytes(edited_bundle)
        write_json(downloads / 'edited-effective-expectations.json', expected_settings)
        report['studio_settings_revision'] = {'revision': revision, 'review': review, 'preparation': edited,
            'job_id': models[2]['id'], 'native_values': native_values,
            'effective_settings_sha256': sha256(effective_bytes), 'prepared_sha256': sha256(edited_bytes),
            'prepared_bytes': len(edited_bytes), 'provenance': 'user_selected synthetic qualification values'}
        source_record = models[0]['source']
        check('customized_original_is_recorded', source_record['recipe']['parameters']['width'] == 90
              and source_record['changed_parameters'] == ['width'] and source_record['customized'] is True)
        recipe_digest = sha256(json.dumps(source_record['recipe'], sort_keys=True, separators=(',', ':'),
                                         ensure_ascii=False, allow_nan=False).encode('utf-8'))
        check('recorded_recipe_hash', recipe_digest == selected['recipe_sha256'] == source_record['recipe_sha256'])

        # A genuine child model keeps the parent's unmentioned dimensions and
        # beginner recipe, with independently observed artifact identities.
        edit_parent = get_json(server, '/api/jobs/' + models[0]['id'])
        parent_manifest_code, parent_manifest_bytes, _ = request(server.base, edit_parent['artifacts']['manifest'])
        edit_proposal = get_json(server, '/api/model-edits/plan', method='POST', token=token,
            payload={'text': '높이를 5mm 늘려줘', 'mode': 'templates',
                     'base_parameters': edit_parent['result']['parameters'], 'parent_job_id': edit_parent['id']})
        edit_review = edit_proposal['review']
        expected_edit_parameters = {**edit_parent['result']['parameters'], 'height': 23.0}
        check('model_edit_plan_preserves_base', edit_proposal['status'] == 'ready'
              and edit_proposal['engine'] == 'template_rules'
              and edit_review['parameters'] == expected_edit_parameters
              and edit_review['changes'] == [{'field': 'height', 'before': 18.0, 'after': 23.0}])
        expected_parent_identity = {'job_id': edit_parent['id'],
            'parameters_sha256': sha256(json.dumps(edit_parent['result']['parameters'], ensure_ascii=False,
                sort_keys=True, separators=(',', ':'), allow_nan=False).encode('utf-8')),
            'model_sha256': models[0]['artifacts']['three_mf']['sha256'],
            'manifest_sha256': sha256(parent_manifest_bytes)}
        check('model_edit_parent_matches_verified_artifacts', parent_manifest_code == 200
              and edit_review['selection']['parent'] == expected_parent_identity)
        edit_payload = {**edit_review['parameters'], 'model_edit': edit_review['selection'],
                        'project_selection': {'id': selected['id'], 'recipe_sha256': selected['recipe_sha256']}}
        before_edit_jobs = get_json(server, '/api/jobs')['jobs']
        get_json(server, '/api/models', method='POST', token=token, expected=422,
                 payload={**edit_payload, 'height': 24})
        check('model_edit_invalid_selection_has_no_job', get_json(server, '/api/jobs')['jobs'] == before_edit_jobs)
        contextual_job = get_json(server, '/api/models', method='POST', token=token, payload=edit_payload)
        contextual_record = {**edit_review, 'provenance': 'user_confirmed_parameters'}
        check('model_edit_generation_preserves_source', contextual_job['model_edit'] == contextual_record
              and contextual_job['result']['parameters'] == expected_edit_parameters
              and contextual_job['design_source']['recipe'] == source_record['recipe']
              and contextual_job['design_source']['recipe_sha256'] == source_record['recipe_sha256']
              and contextual_job['design_source']['changed_parameters'] == ['height', 'width']
              and contextual_job['id'] != edit_parent['id'])
        check('model_edit_no_print_claim', contextual_job['result']['print_status'] == 'not_tested'
              and contextual_job['latest_slice'] is None)
        contextual_history = get_json(server, '/api/jobs?limit=20')
        check('model_edit_history_lists_verified_record',
              [item.get('model_edit') for item in contextual_history['jobs']
               if item['id'] == contextual_job['id']] == [contextual_record])
        write_json(downloads / 'contextual-history.json', contextual_history)
        contextual_manifest = get_json(server, contextual_job['artifacts']['manifest'])
        contextual_downloads = {}
        for artifact_kind, metadata in contextual_manifest['artifacts'].items():
            code, content, _ = request(server.base, contextual_job['artifacts'][artifact_kind])
            check('model_edit_download_receipt_' + artifact_kind,
                  code == 200 and len(content) == metadata['bytes'] and sha256(content) == metadata['sha256'])
            filename = {'stl': 'model.stl', 'step': 'model.step', 'three_mf': 'model.3mf', 'source': 'model.py'}[artifact_kind]
            (downloads / ('contextual-' + filename)).write_bytes(content)
            contextual_downloads[artifact_kind] = content
        code, contextual_bundle, _ = request(server.base, contextual_job['bundle_url'])
        with zipfile.ZipFile(io.BytesIO(contextual_bundle)) as bundle:
            check('model_edit_record_manifest_and_bundle', code == 200 and bundle.testzip() is None
                  and contextual_manifest['model_edit'] == contextual_record
                  and json.loads(bundle.read('manifest.json')) == contextual_manifest
                  and json.loads(bundle.read('job.json'))['model_edit'] == contextual_record
                  and bundle.read('model.3mf') == contextual_downloads['three_mf'])
        contextual_shape = cq.importers.importStep(str(downloads / 'contextual-model.step')).val()
        contextual_bounds = contextual_shape.BoundingBox()
        check('model_edit_step_matches_requested_dimensions', contextual_shape.isValid()
              and len(contextual_shape.Solids()) == 1 and contextual_shape.Volume() > 0
              and all(abs(getattr(contextual_bounds, axis + 'len') - expected) < 1e-5
                      for axis, expected in zip('xyz', (92, 60, 23))))
        with zipfile.ZipFile(io.BytesIO(contextual_downloads['three_mf'])) as archive:
            contextual_mesh = ET.fromstring(archive.read('3D/3dmodel.model')).find('.//{*}mesh')
            vertices = contextual_mesh.findall('.//{*}vertex')
            check('model_edit_3mf_matches_requested_dimensions', archive.testzip() is None
                  and len(vertices) >= 8 and all(abs(max(float(v.attrib[axis]) for v in vertices)
                      - min(float(v.attrib[axis]) for v in vertices) - expected) < 1e-5
                      for axis, expected in zip('xyz', (92, 60, 23))))
        for name, value in (('contextual-parent-job', edit_parent), ('contextual-proposal', edit_proposal),
                            ('contextual-job', contextual_job), ('contextual-manifest', contextual_manifest)):
            write_json(downloads / (name + '.json'), value)
        (downloads / 'contextual-parent-manifest.json').write_bytes(parent_manifest_bytes)
        (downloads / 'contextual-job-bundle.zip').write_bytes(contextual_bundle)
        report['model_edit'] = {'parent': expected_parent_identity, 'proposal': edit_proposal,
            'job_id': contextual_job['id'], 'record': contextual_record,
            'artifacts': contextual_manifest['artifacts'], 'expected_dimensions_mm': {'x': 92, 'y': 60, 'z': 23}}

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
            return {path.relative_to(data).as_posix(): sha256(path.read_bytes()) for path in data.rglob('*')
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
        check('restart_reconciles_index_and_interrupted_job', recovery['indexed'] == 5
              and recovery['interrupted'] == 1 and recovery['unreadable'] == 0, json.dumps(recovery))
        check('restart_rotates_session', refreshed['session_token'] != token)
        old_session = get_json(restarted, '/api/discovery', method='POST', payload={}, token=token, expected=403)
        check('expired_session_has_explicit_code', old_session.get('code') == 'session_expired')
        get_json(restarted, '/api/discovery', method='POST', payload={}, token=refreshed['session_token'])
        restored = get_json(restarted, '/api/profile-workspaces/' + workspace['id'])
        check('workspace_survives_real_restart', restored == workspace and restored['snapshot'] == snapshot)
        source_reopened = get_json(restarted, '/api/studio-projects/' + imported['source_id'])
        project_reopened = get_json(restarted, '/api/jobs/' + models[1]['id'])
        code, reopened_bytes, _ = request(restarted.base, prepared_url)
        check('studio_source_and_prepared_download_survive_restart', source_reopened == imported
              and project_reopened == prepared_job and code == 200 and reopened_bytes == prepared_bytes)
        revision_reopened = get_json(restarted, revision_path)
        edited_reopened = get_json(restarted, '/api/jobs/' + models[2]['id'])
        code, edited_reopened_bytes, _ = request(restarted.base, edited_url)
        check('studio_revision_survives_real_restart', revision_reopened == revision and edited_reopened == edited_job
              and code == 200 and edited_reopened_bytes == edited_bytes)
        restarted_library = library_catalog(restarted, 'workspaces')
        restarted_library_opened = [get_json(restarted, '/api/studio-workspaces/' + item['id']) for item in library_records]
        check('studio_library_survives_real_restart', restarted_library == workspace_catalog
              and restarted_library_opened == library_opened
              and library_catalog(restarted, 'sources') == source_catalog
              and library_catalog(restarted, 'revisions') == revision_catalog)
        write_json(downloads / 'restarted-studio-library.json', restarted_library_opened)
        write_json(downloads / 'restarted-settings-revision.json', revision_reopened)
        write_json(downloads / 'restarted-edited-job.json', edited_reopened)
        retained_job = get_json(restarted, '/api/jobs/' + models[0]['id'])
        check('generation_source_survives_restart', retained_job['design_source'] == source_record
              and retained_job['result']['parameters']['width'] == 92)
        contextual_reopened = get_json(restarted, '/api/jobs/' + contextual_job['id'])
        check('model_edit_survives_real_restart', contextual_reopened == contextual_job
              and get_json(restarted, contextual_job['artifacts']['manifest']) == contextual_manifest)
        write_json(downloads / 'restarted-contextual-job.json', contextual_reopened)
        restarted_contextual_history = get_json(restarted, '/api/jobs?limit=20')
        check('model_edit_history_survives_real_restart',
              [item.get('model_edit') for item in restarted_contextual_history['jobs']
               if item['id'] == contextual_job['id']] == [contextual_record])
        write_json(downloads / 'restarted-contextual-history.json', restarted_contextual_history)
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
        check('history_cursor_reaches_all_recovered_jobs', cursor is None and len(paged_ids) == 5
              and set(paged_ids) == {model['id'] for model in models} | {interrupted_id, contextual_job['id']})

        def backup_command(name, arguments, expected_exit=0):
            operation = subprocess.run([entrypoint, *map(str, arguments)], cwd=work, env=environment,
                                       capture_output=True, text=True, encoding='utf-8', timeout=60)
            (args.report_dir / (name + '-stdout.json')).write_text(operation.stdout, encoding='utf-8')
            (args.report_dir / (name + '-stderr.log')).write_text(operation.stderr, encoding='utf-8')
            check('cli_' + name + '_exit', operation.returncode == expected_exit,
                  f'exit {operation.returncode}; expected {expected_exit}')
            return json.loads(operation.stdout)

        archive = args.report_dir / 'workspace.ppa-backup.zip'
        locked = backup_command('backup-live-owner', ['backup', '--data-dir', data, '--output', archive], 1)
        check('backup_live_owner_rejected', locked['status'] == 'error' and not archive.exists())
        restarted.stop()
        original_bytes = data_hashes()
        created_backup = backup_command('backup-created', ['backup', '--data-dir', data, '--output', archive])
        check('backup_created_verified', created_backup['status'] == 'created'
              and created_backup['archive_sha256'] == sha256(archive.read_bytes())
              and created_backup['file_count'] == len(original_bytes))
        inspected_backup = backup_command('backup-inspected', ['backup-info', '--archive', archive])
        check('backup_inspection_matches_created_archive', inspected_backup['status'] == 'verified'
              and inspected_backup['archive_sha256'] == created_backup['archive_sha256']
              and inspected_backup['file_count'] == created_backup['file_count'])
        restored_data = work / '복원 data space'
        restored_backup = backup_command('backup-restored', ['restore', '--archive', archive, '--destination', restored_data])
        restored_bytes = {p.relative_to(restored_data).as_posix(): sha256(p.read_bytes())
                          for p in restored_data.rglob('*') if p.is_file() and p.name != '.printer-agent.lock'}
        check('backup_restore_to_new_directory', restored_backup['status'] == 'restored'
              and restored_backup['data_dir'] == str(restored_data.resolve()) and restored_bytes == original_bytes)
        existing = backup_command('backup-existing-target', ['restore', '--archive', archive, '--destination', restored_data], 1)
        check('backup_existing_destination_rejected', existing['status'] == 'error'
              and restored_bytes == {p.relative_to(restored_data).as_posix(): sha256(p.read_bytes())
                                     for p in restored_data.rglob('*') if p.is_file() and p.name != '.printer-agent.lock'})
        corrupt_archive = args.report_dir / 'synthetic-truncated-backup.zip'
        content = archive.read_bytes()
        corrupt_archive.write_bytes(content[:len(content) // 2])
        rejected_destination = work / 'must-not-appear'
        rejected = backup_command('backup-corrupt', ['restore', '--archive', corrupt_archive, '--destination', rejected_destination], 1)
        check('backup_corrupt_archive_rejected', rejected['status'] == 'error' and not rejected_destination.exists())
        restored_server = Server(restored_data, work, args.report_dir, 'server-restored', environment)
        servers.append(restored_server)
        restored_bootstrap = restored_server.wait_ready()
        restored_workspace = get_json(restored_server, '/api/profile-workspaces/' + workspace['id'])
        restored_job = get_json(restored_server, '/api/jobs/' + models[0]['id'])
        restored_interrupted = get_json(restored_server, '/api/jobs/' + interrupted_id)
        check('restored_job_and_workspace_identity', restored_workspace == workspace and restored_job == retained_job
              and restored_interrupted == abandoned
              and restored_bootstrap['storage']['path'] == str(restored_data.resolve())
              and sha256((restored_data / partial.relative_to(data)).read_bytes()) == partial_sha)
        verified_downloads = []
        for model in models:
            restored_model = get_json(restored_server, '/api/jobs/' + model['id'])
            code, content, _ = request(restored_server.base, restored_model['artifacts']['three_mf'])
            verified_downloads.append(code == 200 and sha256(content) == model['artifacts']['three_mf']['sha256'])
        check('restored_verified_downloads', all(verified_downloads) and len(verified_downloads) == 3)
        restored_source = get_json(restored_server, '/api/studio-projects/' + imported['source_id'])
        restored_project = get_json(restored_server, '/api/jobs/' + models[1]['id'])
        source_code, restored_source_bytes, _ = request(restored_server.base, imported['archive_url'])
        prepared_code, restored_prepared_bytes, _ = request(restored_server.base, prepared_url)
        check('studio_source_and_preparation_survive_backup_restore', restored_source == imported
              and restored_project == prepared_job and source_code == prepared_code == 200
              and restored_source_bytes == source_bytes and restored_prepared_bytes == prepared_bytes)
        check('print_volume_review_survives_restart_and_restore',
              project_reopened['latest_slice']['plan']['print_volume'] == volume_review
              and restored_project['latest_slice']['plan']['print_volume'] == volume_review)
        restored_revision = get_json(restored_server, revision_path)
        restored_edited = get_json(restored_server, '/api/jobs/' + models[2]['id'])
        code, restored_edited_bytes, _ = request(restored_server.base, edited_url)
        check('studio_revision_survives_backup_restore', restored_revision == revision and restored_edited == edited_job
              and code == 200 and restored_edited_bytes == edited_bytes)
        restored_library = library_catalog(restored_server, 'workspaces')
        restored_library_opened = [get_json(restored_server, '/api/studio-workspaces/' + item['id']) for item in library_records]
        check('studio_library_survives_backup_restore', restored_library == workspace_catalog
              and restored_library_opened == library_opened
              and library_catalog(restored_server, 'sources') == source_catalog
              and library_catalog(restored_server, 'revisions') == revision_catalog)
        write_json(downloads / 'restored-studio-library.json', restored_library_opened)
        fresh_edited = get_json(restored_server, '/api/slice', method='POST', token=restored_bootstrap['session_token'],
                               payload={'job_id': models[2]['id'], 'studio_settings_revision_id': restored_library_opened[1]['workspace']['snapshot']['settings_revision_id'],
                                        'execute': False})
        fresh_job = get_json(restored_server, '/api/jobs/' + models[2]['id'])
        code, fresh_bytes, _ = request(restored_server.base, fresh_job['artifacts']['prepared_three_mf'])
        fresh_plan = fresh_edited['plan']
        check('studio_revision_fresh_preparation_after_restore', fresh_plan['project_prepared'] is True
              and fresh_plan['settings_revision'] == revision['revision']
              and fresh_plan['settings_review'] == revision['review']
              and fresh_plan['expected_settings'] == expected_core
              and fresh_plan['project_sha256'] == edited_plan['project_sha256']
              and code == 200 and fresh_bytes == edited_bytes)
        check('studio_library_reopened_settings_prepare_current_cad',
              fresh_plan['project_receipt']['model_sha256'] == models[2]['artifacts']['three_mf']['sha256']
              and fresh_plan['settings_revision']['revision_id'] == restored_library_opened[1]['workspace']['snapshot']['settings_revision_id']
              and fresh_plan['expected_settings'] == expected_core)
        check('studio_revision_restored_preparation_uses_new_directory',
              Path(fresh_plan['project_path']).is_relative_to(restored_data)
              and not Path(fresh_plan['project_path']).is_relative_to(data)
              and fresh_plan['project_path'] != edited_plan['project_path'])
        for name, value in (('restored-settings-revision', restored_revision), ('restored-edited-job', restored_edited),
                            ('restored-fresh-preparation', fresh_edited), ('restored-fresh-job', fresh_job)):
            write_json(downloads / (name + '.json'), value)
        (downloads / 'restored-fresh-project.3mf').write_bytes(fresh_bytes)
        report['studio_settings_revision']['restored_preparation'] = fresh_edited
        report['studio_settings_revision']['restored_prepared_sha256'] = sha256(fresh_bytes)
        contextual_restored = get_json(restored_server, '/api/jobs/' + contextual_job['id'])
        code, contextual_restored_bytes, _ = request(restored_server.base, contextual_job['artifacts']['three_mf'])
        check('model_edit_survives_backup_restore', contextual_restored == contextual_job and code == 200
              and contextual_restored_bytes == contextual_downloads['three_mf']
              and get_json(restored_server, contextual_job['artifacts']['manifest']) == contextual_manifest)
        restored_contextual_history = get_json(restored_server, '/api/jobs?limit=20')
        check('model_edit_history_survives_backup_restore',
              [item.get('model_edit') for item in restored_contextual_history['jobs']
               if item['id'] == contextual_job['id']] == [contextual_record])
        write_json(downloads / 'restored-contextual-history.json', restored_contextual_history)
        contextual_prepared = get_json(restored_server, '/api/slice', method='POST', token=restored_bootstrap['session_token'],
            payload={'job_id': contextual_job['id'], 'studio_settings_revision_id': revision_id, 'execute': False})
        contextual_prepared_job = get_json(restored_server, '/api/jobs/' + contextual_job['id'])
        code, contextual_prepared_bytes, _ = request(restored_server.base, contextual_prepared_job['artifacts']['prepared_three_mf'])
        contextual_plan = contextual_prepared['plan']
        with zipfile.ZipFile(io.BytesIO(contextual_prepared_bytes)) as archive:
            current_mesh = ET.fromstring(archive.read('3D/3dmodel.model')).find('.//{*}mesh')
            check('model_edit_fresh_studio_preparation_after_restore', code == 200
                  and contextual_prepared['execution'] is None and contextual_plan['project_prepared'] is True
                  and contextual_plan['project_receipt']['model_sha256'] == sha256(contextual_downloads['three_mf'])
                  and contextual_plan['settings_revision'] == revision['revision']
                  and Path(contextual_plan['project_path']).is_relative_to(restored_data)
                  and contextual_prepared_job['model_edit'] == contextual_record
                  and archive.testzip() is None
                  and archive.read('Metadata/project_settings.config') == effective_bytes
                  and mesh_values(current_mesh) == mesh_values(contextual_mesh))
        reproposed = get_json(restored_server, '/api/model-edits/plan', method='POST', token=restored_bootstrap['session_token'],
            payload={'text': '높이를 1mm 늘려줘', 'base_parameters': expected_edit_parameters,
                     'parent_job_id': contextual_job['id']})
        check('model_edit_restored_job_is_a_verified_new_parent', reproposed['review']['parameters']['height'] == 24.0
              and reproposed['review']['selection']['parent']['job_id'] == contextual_job['id']
              and reproposed['review']['selection']['parent']['model_sha256'] == sha256(contextual_downloads['three_mf']))
        for name, value in (('restored-contextual-job', contextual_restored),
                            ('restored-contextual-preparation', contextual_prepared),
                            ('restored-contextual-prepared-job', contextual_prepared_job),
                            ('restored-contextual-reproposal', reproposed)):
            write_json(downloads / (name + '.json'), value)
        (downloads / 'restored-contextual-project.3mf').write_bytes(contextual_prepared_bytes)
        report['model_edit']['restored_preparation'] = contextual_prepared
        report['model_edit']['restored_prepared_sha256'] = sha256(contextual_prepared_bytes)
        check('backup_source_bytes_unchanged', original_bytes == data_hashes())
        report['backup'] = {'created': created_backup, 'inspected': inspected_backup, 'restored': restored_backup,
                            'source_files': original_bytes, 'restored_before_start_files': restored_bytes,
                            'source_data_dir': str(data), 'restored_data_dir': str(restored_data),
                            'restored_recovery': restored_bootstrap['storage']['recovery'],
                            'all_three_model_downloads_verified': all(verified_downloads)}

        # Further integrity faults now target only the restored copy. The original
        # source and verified backup remain unchanged for independent inspection.
        restarted = restored_server
        tampered = restored_data / 'jobs' / models[0]['id'] / 'model.3mf'
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
    with DataDirectoryLease(restored_data):
        check('restored_server_releases_data_directory', True)


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
