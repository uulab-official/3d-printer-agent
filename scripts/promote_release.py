#!/usr/bin/env python3
"""Promote exact qualified wheel bytes; never rebuild or execute downloaded files.

GitHub workflow_run uses trusted current-main code. API authentication is restricted
to GitHub API/upload hosts; download redirects receive no authorization header.
Official contracts: https://docs.github.com/en/rest/releases/releases and
https://docs.github.com/en/rest/releases/assets .
"""
import argparse
import ast
import configparser
from dataclasses import dataclass
from datetime import datetime, timezone
from email.parser import BytesParser
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import subprocess
import tomllib
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
import zipfile


WORKFLOW_PATHS = (
    '.github/workflows/ci.yml',
    '.github/workflows/package-qualification.yml',
    '.github/workflows/native-bambu.yml',
)
PLATFORMS = {'ubuntu-24.04': ('Linux', 'x86_64'), 'macos-15': ('Darwin', 'arm64'),
             'windows-2025': ('Windows', 'AMD64')}
REQUIRED_CHECKS = frozenset({
    'working_directory_outside_checkout', 'imported_package_outside_checkout',
    'installed_console_entrypoint', 'installed_doctor_success', 'wheel_crc',
    'cad_validated_tray', 'cad_validated_cable_comb', 'cad_validated_magnet_frame',
    'second_live_server_is_rejected', 'rejected_owner_does_not_modify_user_data',
    'restart_reconciles_index_and_interrupted_job', 'workspace_survives_real_restart',
    'generation_source_survives_restart', 'partial_file_bytes_preserved',
    'history_cursor_reaches_all_recovered_jobs', 'altered_artifact_is_not_downloaded',
    'altered_artifact_blocks_bundle', 'unrelated_verified_download_remains_available',
    'stopped_server_releases_data_directory', 'backup_live_owner_rejected',
    'backup_created_verified', 'backup_inspection_matches_created_archive',
    'backup_source_bytes_unchanged', 'backup_restore_to_new_directory',
    'restored_job_and_workspace_identity', 'restored_verified_downloads',
    'backup_existing_destination_rejected', 'backup_corrupt_archive_rejected',
    'restored_server_releases_data_directory',
})
MAX_JSON = 8 * 1024 * 1024
MAX_ZIP_BYTES = 64 * 1024 * 1024
MAX_EXPANDED_BYTES = 256 * 1024 * 1024
MAX_MEMBERS = 1000
SHA_PATTERN = re.compile(r'[a-f0-9]{40}')
DIGEST_PATTERN = re.compile(r'[a-f0-9]{64}')
VERSION_PATTERN = re.compile(r'(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)')


class PromotionError(ValueError):
    """A concrete failure that must leave any existing release untouched."""


def require(condition, detail):
    if not condition:
        raise PromotionError(detail)


def sha256(content):
    return hashlib.sha256(content).hexdigest()


def json_bytes(value):
    return (json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False) + '\n').encode('utf-8')


def _pairs(items):
    result = {}
    for key, value in items:
        require(key not in result, 'Duplicate JSON key in release evidence')
        result[key] = value
    return result


def read_json(content):
    require(isinstance(content, bytes) and len(content) <= MAX_JSON, 'JSON evidence exceeds its size limit')
    try:
        return json.loads(content, object_pairs_hook=_pairs,
                          parse_constant=lambda value: (_ for _ in ()).throw(PromotionError('Nonfinite JSON evidence')))
    except (UnicodeError, json.JSONDecodeError, RecursionError, OverflowError) as exc:
        raise PromotionError('Invalid JSON evidence') from exc


def positive_integer(value):
    return type(value) is int and value > 0


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, response, code, message, headers, new_url):
        return None


class GitHubAPI:
    def __init__(self, token, *, opener=None):
        require(isinstance(token, str) and token and '\n' not in token and '\r' not in token,
                'A GitHub job token is required')
        self._token = token
        self._opener = opener or urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())

    @staticmethod
    def _api_url(path):
        require(isinstance(path, str) and path.startswith('/') and not path.startswith('//')
                and not any(ord(char) < 32 for char in path), 'Invalid authenticated API path')
        return 'https://api.github.com' + path

    def _headers(self, accept='application/vnd.github+json'):
        return {'Authorization': 'Bearer ' + self._token, 'Accept': accept,
                'X-GitHub-Api-Version': '2026-03-10', 'User-Agent': '3d-printer-agent-release-promotion',
                'Cache-Control': 'no-cache'}

    def _read(self, response, limit):
        declared = response.headers.get('Content-Length')
        if declared:
            require(declared.isdecimal() and int(declared) <= limit, 'Response exceeds its download limit')
        chunks, total = [], 0
        while True:
            chunk = response.read(min(65536, limit - total + 1))
            if not chunk:
                break
            total += len(chunk)
            require(total <= limit, 'Response exceeds its download limit')
            chunks.append(chunk)
        return b''.join(chunks)

    def json(self, method, path, payload=None, *, not_found=False):
        url = self._api_url(path)
        body = None if payload is None else json_bytes(payload)
        headers = self._headers()
        if body is not None:
            headers['Content-Type'] = 'application/json'
        request = urllib.request.Request(url, data=body, headers=headers, method=method)
        try:
            with self._opener.open(request, timeout=45) as response:
                return read_json(self._read(response, MAX_JSON))
        except urllib.error.HTTPError as exc:
            status = exc.code
            exc.close()
            if status == 404 and not_found and method == 'GET':
                return None
            raise PromotionError(f'GitHub API {method} failed with HTTP {status}') from None
        except (OSError, urllib.error.URLError) as exc:
            raise PromotionError('GitHub API connection failed') from None

    @staticmethod
    def _download_url(url):
        parsed = urllib.parse.urlsplit(url)
        host = (parsed.hostname or '').lower()
        allowed = ('github.com', 'githubusercontent.com', 'blob.core.windows.net', 'amazonaws.com')
        require(parsed.scheme == 'https' and parsed.port in (None, 443) and not parsed.username
                and not parsed.password and any(host == suffix or host.endswith('.' + suffix) for suffix in allowed),
                'Untrusted artifact redirect was refused')
        return url

    def download(self, path, *, limit):
        url, authenticated = self._api_url(path), True
        for _ in range(6):
            headers = self._headers('application/octet-stream') if authenticated else {'User-Agent': '3d-printer-agent-release-promotion'}
            request = urllib.request.Request(url, headers=headers)
            try:
                with self._opener.open(request, timeout=45) as response:
                    return self._read(response, limit)
            except urllib.error.HTTPError as exc:
                code, location = exc.code, exc.headers.get('Location')
                exc.close()
                if code in (301, 302, 303, 307, 308) and location:
                    url, authenticated = self._download_url(urllib.parse.urljoin(url, location)), False
                    continue
                raise PromotionError(f'Artifact download failed with HTTP {code}') from None
            except (OSError, urllib.error.URLError):
                raise PromotionError('Artifact download connection failed') from None
        raise PromotionError('Artifact redirect limit exceeded')

    def upload(self, repository, release_id, name, content):
        require(positive_integer(release_id), 'Invalid release identifier')
        url = f'https://uploads.github.com/repos/{repository}/releases/{release_id}/assets?' + urllib.parse.urlencode({'name': name})
        headers = self._headers()
        headers['Content-Type'] = 'application/octet-stream'
        request = urllib.request.Request(url, data=content, headers=headers, method='POST')
        try:
            with self._opener.open(request, timeout=45) as response:
                return read_json(self._read(response, MAX_JSON))
        except urllib.error.HTTPError as exc:
            code = exc.code
            exc.close()
            raise PromotionError(f'Release asset upload failed with HTTP {code}; any draft is preserved') from None
        except (OSError, urllib.error.URLError):
            raise PromotionError('Release asset upload connection failed; any draft is preserved') from None


@dataclass(frozen=True)
class SourceSnapshot:
    commit: str
    version: str
    files: dict
    qualification_script: bytes
    cadquery_version: str
    dependencies: tuple = ()
    requires_python: str = '>=3.11,<3.14'


def source_snapshot(root):
    def git(*arguments):
        try:
            return subprocess.check_output(['git', '-C', str(root), *arguments], stderr=subprocess.DEVNULL, timeout=20)
        except (OSError, subprocess.SubprocessError):
            raise PromotionError('Cannot read the trusted checkout') from None
    commit = git('rev-parse', 'HEAD').decode().strip()
    require(SHA_PATTERN.fullmatch(commit), 'Checkout does not identify an exact commit')
    try:
        project = tomllib.loads(git('show', f'{commit}:pyproject.toml').decode('utf-8'))['project']
        version = project['version']
        dependencies = project['dependencies']
        cadquery = [item.partition('==')[2] for item in dependencies if item.startswith('cadquery==')]
        require(project['name'] == '3d-printer-agent-local' and VERSION_PATTERN.fullmatch(version)
                and len(cadquery) == 1 and cadquery[0], 'Unsupported release project/version')
        names = git('ls-tree', '-r', '--name-only', commit, '--', 'print_agent').decode('utf-8').splitlines()
        names = [name for name in names if name.endswith('.py') or
                 (name.startswith('print_agent/static/') and name.rsplit('.', 1)[-1] in {'html', 'css', 'js'})]
        files = {name: git('show', f'{commit}:{name}') for name in names}
        tree = ast.parse(files['print_agent/__init__.py'])
        versions = [ast.literal_eval(item.value) for item in tree.body if isinstance(item, ast.Assign)
                    and any(isinstance(target, ast.Name) and target.id == '__version__' for target in item.targets)]
        require(versions == [version], 'Application and project versions differ')
        return SourceSnapshot(commit, version, files, git('show', f'{commit}:scripts/qualify_install.py'),
                              cadquery[0], tuple(dependencies), project['requires-python'])
    except (KeyError, TypeError, UnicodeError, ValueError, SyntaxError) as exc:
        if isinstance(exc, PromotionError):
            raise
        raise PromotionError('Cannot parse release identity from committed source') from None


def pages(api, path, field=None):
    for number in range(1, 21):
        separator = '&' if '?' in path else '?'
        result = api.json('GET', path + separator + urllib.parse.urlencode({'per_page': 100, 'page': number}))
        rows = result.get(field) if field and isinstance(result, dict) else result
        require(isinstance(rows, list) and all(isinstance(item, dict) for item in rows), 'Invalid paginated GitHub response')
        yield from rows
        if len(rows) < 100:
            return
    raise PromotionError('GitHub pagination bound exceeded')


def safe_zip(content):
    require(len(content) <= MAX_ZIP_BYTES, 'ZIP input exceeds its size limit')
    result, seen, total = {}, set(), 0
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            entries = archive.infolist()
            require(len(entries) <= MAX_MEMBERS, 'ZIP entry limit exceeded')
            for entry in entries:
                require(entry.orig_filename == entry.filename and '\x00' not in entry.orig_filename,
                        'Noncanonical ZIP member name')
                name = entry.filename.rstrip('/')
                path = PurePosixPath(name)
                require(name and not path.is_absolute() and '\\' not in name and ':' not in name
                        and '\x00' not in name and all(part not in ('', '.', '..') for part in name.split('/')),
                        'Unsafe ZIP member path')
                key = unicodedata.normalize('NFC', name).casefold()
                require(key not in seen, 'Colliding ZIP member paths')
                seen.add(key)
                mode = stat.S_IFMT(entry.external_attr >> 16)
                require(mode in (0, stat.S_IFREG, stat.S_IFDIR) and not (entry.flag_bits & 1)
                        and entry.compress_type in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED), 'Unsupported ZIP member')
                require((not entry.is_dir() and mode != stat.S_IFDIR) or
                        (entry.is_dir() and entry.file_size == 0 and mode != stat.S_IFREG), 'ZIP member type differs from its path')
                require(entry.file_size <= MAX_ZIP_BYTES and total + entry.file_size <= MAX_EXPANDED_BYTES,
                        'ZIP expansion limit exceeded')
                chunks, count = [], 0
                with archive.open(entry) as member:
                    while True:
                        chunk = member.read(65536)
                        if not chunk:
                            break
                        count += len(chunk)
                        require(count <= entry.file_size and count <= MAX_ZIP_BYTES
                                and total + count <= MAX_EXPANDED_BYTES, 'ZIP actual expansion limit exceeded')
                        chunks.append(chunk)
                require(count == entry.file_size, 'ZIP declared size differs from actual bytes')
                total += count
                if not entry.is_dir():
                    result[name] = b''.join(chunks)
    except (zipfile.BadZipFile, RuntimeError, EOFError, OSError) as exc:
        raise PromotionError('Invalid ZIP evidence') from None
    return result


def same_source(run, repository, commit):
    return (isinstance(run, dict) and run.get('event') == 'push' and run.get('head_branch') == 'main'
            and run.get('head_sha') == commit and run.get('repository', {}).get('full_name') == repository
            and run.get('head_repository', {}).get('full_name') == repository)


def check_reports(files, platform, source, receipt_bytes, receipt):
    require(files.get('wheel-receipt.json') == receipt_bytes, 'Platform wheel receipt differs from shared receipt')
    report = read_json(files.get('report.json', b''))
    require(isinstance(report, dict) and report.get('schema_version') == 1 and report.get('status') == 'passed'
            and report.get('source_commit') == source.commit, 'Platform report does not qualify this commit')
    checks = report.get('checks')
    require(isinstance(checks, list) and checks and all(isinstance(item, dict) and item.get('passed') is True
            and isinstance(item.get('id'), str) for item in checks), 'Platform checks are incomplete or failed')
    require(type(report.get('checks_total')) is int and report['checks_total'] == len(checks)
            and type(report.get('checks_passed')) is int and report['checks_passed'] == len(checks), 'Platform check totals differ')
    required = REQUIRED_CHECKS | {'installed_bytes_' + name for name in source.files}
    require(required <= {item['id'] for item in checks}, 'Platform report omits required installation/recovery checks')
    observed = report.get('platform', {})
    require((observed.get('system'), observed.get('machine')) == PLATFORMS[platform]
            and re.fullmatch(r'3\.12\.[0-9]+', report.get('python', '')), 'Platform runtime differs from the qualified matrix')
    versions = report.get('versions', {})
    require(versions.get('application') == versions.get('distribution') == source.version
            and versions.get('cadquery') == source.cadquery_version, 'Platform application/dependency version differs')
    wheel = report.get('wheel', {})
    require(all(wheel.get(key) == receipt[key] for key in ('filename', 'bytes', 'sha256'))
            and wheel.get('receipt_sha256') == sha256(receipt_bytes), 'Platform did not install the shared wheel bytes')
    script_hashes = {sha256(source.qualification_script)}
    if platform == 'windows-2025':
        script_hashes.add(sha256(source.qualification_script.replace(b'\r\n', b'\n').replace(b'\n', b'\r\n')))
    require(report.get('script_sha256') in script_hashes, 'Qualification script differs from committed source')
    require(report.get('packaged_application_files') == len(source.files), 'Installed package inventory differs')
    limits = report.get('limits', {})
    require(isinstance(limits, dict) and limits.get('synthetic_data') is True
            and all(limits.get(key) is False for key in ('native_slicer_executed', 'browser_executed',
                    'live_provider_executed', 'physical_print_verified')), 'Platform qualification scope differs')
    return report


def verified_package(api, repository, run, source):
    prefix = f'/repos/{repository}'
    names = ['installable-wheel-' + source.commit] + ['package-evidence-' + item for item in PLATFORMS]
    artifacts = list(pages(api, prefix + f'/actions/runs/{run["id"]}/artifacts', 'artifacts'))
    payloads, receipts = {}, []
    for name in names:
        matches = [item for item in artifacts if item.get('name') == name]
        require(matches, 'A required qualification artifact is missing')
        require(all(positive_integer(item.get('id')) for item in matches)
                and len({item['id'] for item in matches}) == len(matches), 'Qualification artifact identifiers are invalid or ambiguous')
        # Rerunning failed jobs retains earlier artifacts and successful platform
        # jobs. Select the greatest artifact ID, then validate only that version;
        # a bad newest artifact must never fall back to an older passing report.
        item = max(matches, key=lambda candidate: candidate['id'])
        require(positive_integer(item.get('id')) and positive_integer(item.get('size_in_bytes'))
                and item['size_in_bytes'] <= MAX_ZIP_BYTES and item.get('expired') is False
                and re.fullmatch(r'sha256:[a-f0-9]{64}', item.get('digest', ''))
                and item.get('workflow_run', {}).get('id') == run['id']
                and item.get('workflow_run', {}).get('head_sha') == source.commit, 'Qualification artifact identity is invalid')
        content = api.download(prefix + f'/actions/artifacts/{item["id"]}/zip', limit=MAX_ZIP_BYTES)
        require(len(content) == item['size_in_bytes'] and 'sha256:' + sha256(content) == item['digest'],
                'Qualification artifact archive digest/size differs')
        payloads[name] = safe_zip(content)
        receipts.append({'id': item['id'], 'name': name, 'bytes': len(content), 'sha256': sha256(content)})
    shared = payloads[names[0]]
    expected_wheel = f'3d_printer_agent_local-{source.version}-py3-none-any.whl'
    require(set(shared) == {expected_wheel, 'wheel-receipt.json', 'SHA256SUMS'}, 'Shared wheel artifact inventory differs')
    receipt_bytes, wheel_bytes = shared['wheel-receipt.json'], shared[expected_wheel]
    receipt = read_json(receipt_bytes)
    require(isinstance(receipt, dict) and receipt.get('schema_version') == 1
            and receipt.get('source_commit') == source.commit and receipt.get('filename') == expected_wheel
            and type(receipt.get('bytes')) is int and receipt['bytes'] == len(wheel_bytes)
            and receipt.get('sha256') == sha256(wheel_bytes), 'Wheel receipt does not match exact qualified bytes/source')
    checksum = f'{sha256(wheel_bytes)}  {expected_wheel}\n'.encode('ascii')
    require(shared['SHA256SUMS'] == checksum, 'Wheel checksum file differs')
    wheel_files = safe_zip(wheel_bytes)
    metadata_root = f'3d_printer_agent_local-{source.version}.dist-info/'
    allowed_metadata = {metadata_root + name for name in (
        'METADATA', 'WHEEL', 'entry_points.txt', 'top_level.txt', 'RECORD', 'licenses/LICENSE')}
    require(all(name.startswith('print_agent/') or name in allowed_metadata for name in wheel_files),
            'Wheel contains files outside the committed application and supported metadata')
    package_files = {name: content for name, content in wheel_files.items() if name.startswith('print_agent/')}
    require(package_files == source.files, 'Packaged application files differ from the exact committed source')
    metadata_names = [name for name in wheel_files if name.endswith('.dist-info/METADATA')]
    require(len(metadata_names) == 1, 'Wheel metadata is missing or ambiguous')
    metadata = BytesParser().parsebytes(wheel_files[metadata_names[0]])
    require(metadata.get_all('Name') == ['3d-printer-agent-local'] and metadata.get_all('Version') == [source.version],
            'Wheel metadata version/project differs')
    require(sorted(metadata.get_all('Requires-Dist', [])) == sorted(source.dependencies)
            and len(metadata.get_all('Requires-Python', [])) == 1
            and {item.strip() for item in metadata['Requires-Python'].split(',')}
            == {item.strip() for item in source.requires_python.split(',')}, 'Wheel dependency/Python declarations differ from source')
    wheel_metadata = BytesParser().parsebytes(wheel_files.get(metadata_root + 'WHEEL', b''))
    require(wheel_metadata.get_all('Tag') == ['py3-none-any']
            and wheel_metadata.get_all('Root-Is-Purelib') == ['true']
            and wheel_metadata.get_all('Wheel-Version') == ['1.0'], 'Wheel runtime compatibility metadata differs')
    try:
        entrypoints = configparser.ConfigParser(interpolation=None, strict=True)
        entrypoints.optionxform = str
        entrypoints.read_string(wheel_files.get(metadata_root + 'entry_points.txt', b'').decode('utf-8'))
        require(entrypoints.sections() == ['console_scripts'] and not entrypoints.defaults()
                and dict(entrypoints['console_scripts']) == {'printer-agent': 'print_agent.__main__:main'},
                'Wheel console entrypoint differs from the supported application')
    except (configparser.Error, UnicodeError):
        raise PromotionError('Invalid wheel console entrypoint metadata') from None
    assets = dict(shared)
    reports = {}
    for platform in PLATFORMS:
        files = payloads['package-evidence-' + platform]
        reports[platform] = check_reports(files, platform, source, receipt_bytes, receipt)
        assets['qualification-' + platform + '.json'] = files['report.json']
    return assets, receipt, receipts, reports


def tag_commit(api, prefix, tag):
    value = api.json('GET', prefix + '/git/ref/tags/' + urllib.parse.quote(tag, safe=''), not_found=True)
    if value is None:
        return None
    for _ in range(6):
        target = value.get('object', {}) if isinstance(value, dict) else {}
        require(isinstance(target.get('sha'), str) and SHA_PATTERN.fullmatch(target['sha']), 'Tag target is invalid')
        if target.get('type') == 'commit':
            return target['sha']
        require(target.get('type') == 'tag', 'Tag does not resolve to a commit')
        value = api.json('GET', prefix + '/git/tags/' + target['sha'])
    raise PromotionError('Annotated tag depth exceeded')


def verify_asset(api, prefix, asset, name, content):
    require(positive_integer(asset.get('id')) and asset.get('name') == name
            and asset.get('state') == 'uploaded' and asset.get('size') == len(content), 'Release asset metadata differs')
    if asset.get('digest') is not None:
        require(asset['digest'] == 'sha256:' + sha256(content), 'Release asset digest differs')
    actual = api.download(prefix + f'/releases/assets/{asset["id"]}', limit=MAX_ZIP_BYTES)
    require(actual == content, 'Release asset read-back differs; existing bytes were preserved')


def successful_gates(api, repository, commit):
    prefix = f'/repos/{repository}'
    runs = list(pages(api, prefix + '/actions/runs?' + urllib.parse.urlencode({
        'head_sha': commit, 'event': 'push', 'branch': 'main'}), 'workflow_runs'))
    selected = []
    for path in WORKFLOW_PATHS:
        candidates = [run for run in runs if run.get('path') == path and same_source(run, repository, commit)]
        if not candidates:
            return None, 'A required workflow has not completed for this exact main push'
        require(all(positive_integer(run.get('id')) for run in candidates), 'Workflow run identity is invalid')
        newest = max(candidates, key=lambda run: run['id'])
        current = api.json('GET', prefix + f'/actions/runs/{newest["id"]}')
        if (not same_source(current, repository, commit) or current.get('path') != path
                or current.get('id') != newest['id'] or current.get('status') != 'completed'
                or current.get('conclusion') != 'success'):
            return None, 'Latest required workflow outcome is not a completed success'
        require(positive_integer(current.get('run_attempt')), 'Workflow attempt is missing')
        selected.append(current)
    return selected, None


def promote(api, repository, event, source, report=None):
    report = {} if report is None else report
    report.update(schema_version=1, repository=repository, source_commit=source.commit, status='checking', phase='gates')
    require(re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', repository), 'Invalid repository identity')
    require(SHA_PATTERN.fullmatch(source.commit) and VERSION_PATTERN.fullmatch(source.version), 'Invalid committed release identity')
    prefix, tag = f'/repos/{repository}', 'v' + source.version

    def skipped(reason):
        report.update(status='skipped', reason=reason)
        return report

    def current_main():
        current = api.json('GET', prefix + '/git/ref/heads/main')
        return current.get('object', {}).get('type') == 'commit' and current['object'].get('sha') == source.commit

    trigger = event.get('workflow_run', {}) if isinstance(event, dict) else {}
    if (not isinstance(event, dict) or event.get('repository', {}).get('full_name') != repository
            or not same_source(trigger, repository, source.commit) or trigger.get('path') not in WORKFLOW_PATHS
            or trigger.get('status') != 'completed' or trigger.get('conclusion') != 'success'):
        return skipped('Event is not a successful qualifying push on this repository/main checkout')
    if not current_main():
        return skipped('Qualification commit is no longer current main')
    selected, reason = successful_gates(api, repository, source.commit)
    if reason:
        return skipped(reason)

    def revalidate_gates(phase):
        report['phase'] = phase
        latest, reason = successful_gates(api, repository, source.commit)
        if not reason and [(run['path'], run['id'], run['run_attempt']) for run in latest] != [
                (run['path'], run['id'], run['run_attempt']) for run in selected]:
            reason = 'Latest required workflow run or attempt changed during promotion'
        report.setdefault('gate_revalidations', []).append({'phase': phase, 'unchanged': reason is None})
        return reason

    gates = [{'path': run['path'], 'id': run['id'], 'attempt': run['run_attempt'],
              'url': f'https://github.com/{repository}/actions/runs/{run["id"]}', 'conclusion': 'success'} for run in selected]
    report.update(gates=gates, phase='artifact_verification')
    assets, wheel, artifacts, reports = verified_package(api, repository, selected[1], source)
    evidence = {'schema_version': 1, 'repository': repository, 'source_commit': source.commit,
                'version': source.version, 'wheel': wheel, 'gates': gates, 'qualification_artifacts': artifacts,
                'packaged_source_files': len(source.files),
                'platform_reports': {platform: {'filename': 'qualification-' + platform + '.json',
                    'sha256': sha256(assets['qualification-' + platform + '.json']),
                    'checks_passed': data['checks_passed'], 'checks_total': data['checks_total'],
                    'platform': data['platform'], 'python': data['python'], 'script_sha256': data['script_sha256']}
                    for platform, data in reports.items()},
                'limits': {'native_bambu': 'Separate synthetic Linux native workflow', 'signed_installer': False,
                           'automatic_updater': False, 'user_hardware_qualified': False, 'physical_print_verified': False}}
    assets['release-evidence.json'] = json_bytes(evidence)
    report.update(version=source.version, tag=tag, wheel=wheel, artifacts=artifacts, phase='release_validation')
    body = (f'3D Printer Agent {tag}\n\n'
            f'Qualified source: `{source.commit}`. These are the exact shared wheel bytes installed on Linux, macOS and Windows.\n\n'
            f'Wheel SHA-256: `{wheel["sha256"]}`. See `SHA256SUMS`, `wheel-receipt.json`, `release-evidence.json` and the platform qualification reports.\n\n'
            'Use Python 3.12 in a virtual environment. Back up saved local data before upgrading; see docs/LOCAL_OPERATION.md. '
            'This local CAD/settings workspace does not certify user hardware or physical printing and is not a signed installer or automatic updater.\n\n'
            f'<!-- 3d-printer-agent-release-promotion-v1 source={source.commit} evidence={sha256(assets["release-evidence.json"])} -->')
    release_name = '3D Printer Agent ' + tag
    existing_tag = tag_commit(api, prefix, tag)
    require(existing_tag in (None, source.commit), 'Existing version tag targets another commit; no tag was moved')
    releases = [release for release in pages(api, prefix + '/releases') if release.get('tag_name') == tag]
    require(len(releases) <= 1, 'Release version is ambiguous')
    if releases:
        release = releases[0]
        require(release.get('target_commitish') == source.commit and release.get('name') == release_name
                and release.get('body') == body and release.get('prerelease') is False
                and type(release.get('draft')) is bool, 'Existing release is not this exact promotion; it was left unchanged')
    else:
        if not current_main():
            return skipped('Main advanced before draft creation')
        report['phase'] = 'draft_creation'
        release = api.json('POST', prefix + '/releases', {'tag_name': tag, 'target_commitish': source.commit,
                          'name': release_name, 'body': body, 'draft': True, 'prerelease': False})
    require(positive_integer(release.get('id')), 'Release identifier is invalid')
    release_id = release['id']
    report.update(release_id=release_id, release_url=f'https://github.com/{repository}/releases/tag/{tag}', phase='asset_verification')
    existing = list(pages(api, prefix + f'/releases/{release_id}/assets'))
    existing_names = [item.get('name') for item in existing]
    require(len(existing_names) == len(set(existing_names)) and set(existing_names) <= set(assets),
            'Existing release has unexpected/duplicate assets; no assets were changed')
    if not release['draft']:
        require(existing_tag == source.commit and set(existing_names) == set(assets), 'Published release is incomplete or has a different tag')
    # Validate every existing byte before resuming any partial draft upload.
    # A conflicting draft must remain completely unchanged by this invocation.
    for asset in existing:
        verify_asset(api, prefix, asset, asset['name'], assets[asset['name']])
    verified = []
    for name, content in sorted(assets.items()):
        matches = [item for item in existing if item['name'] == name]
        if matches:
            asset = matches[0]
        else:
            require(release['draft'], 'Published release asset is absent; published releases are immutable')
            if not current_main():
                return skipped('Main advanced during draft assembly; draft preserved')
            report['phase'] = 'asset_upload'
            asset = api.upload(repository, release_id, name, content)
            verify_asset(api, prefix, asset, name, content)
        verified.append({'name': name, 'id': asset['id'], 'bytes': len(content), 'sha256': sha256(content)})
        report['assets'] = list(verified)
    if release['draft']:
        if not current_main():
            return skipped('Main advanced before publication; verified draft preserved')
        require(tag_commit(api, prefix, tag) in (None, source.commit), 'Version tag changed during promotion; draft preserved')
        fresh = api.json('GET', prefix + f'/releases/{release_id}')
        require(fresh.get('draft') is True and fresh.get('body') == body and fresh.get('target_commitish') == source.commit,
                'Draft changed during promotion; it was not published')
        final_assets = list(pages(api, prefix + f'/releases/{release_id}/assets'))
        require({item.get('name'): item.get('id') for item in final_assets} == {item['name']: item['id'] for item in verified}
                and len(final_assets) == len(verified), 'Draft asset inventory changed before publication')
        current_tag = tag_commit(api, prefix, tag)
        reason = revalidate_gates('gate_revalidation_before_tag')
        if reason:
            return skipped(reason + '; draft preserved before tag creation')
        if current_tag is None:
            # A create-only ref fails if another actor won the name. Never use
            # an update/delete ref API and never let release creation select main.
            created_tag = api.json('POST', prefix + '/git/refs', {'ref': 'refs/tags/' + tag, 'sha': source.commit})
            require(created_tag.get('object', {}).get('sha') == source.commit, 'GitHub did not confirm the exact version tag')
        require(tag_commit(api, prefix, tag) == source.commit, 'Version tag differs before publication; draft preserved')
        if not current_main():
            return skipped('Main advanced before final publication; qualified tag and draft preserved')
        reason = revalidate_gates('gate_revalidation_before_publication')
        if reason:
            return skipped(reason + '; qualified tag and draft preserved without publication')
        report['phase'] = 'publication'
        published = api.json('PATCH', prefix + f'/releases/{release_id}', {'draft': False})
        require(published.get('draft') is False, 'GitHub did not confirm publication')
        report.update(status='published', phase='complete')
    else:
        report.update(status='already_published', phase='complete')
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repository', required=True)
    parser.add_argument('--event', type=Path, required=True)
    parser.add_argument('--source-root', type=Path, required=True)
    parser.add_argument('--report-dir', type=Path, required=True)
    args = parser.parse_args()
    args.report_dir.mkdir(parents=True, exist_ok=True)
    report = {'schema_version': 1, 'status': 'checking', 'started_at': datetime.now(timezone.utc).isoformat()}
    result = 0
    try:
        require(os.getenv('GITHUB_ACTIONS') == 'true' and os.getenv('GITHUB_EVENT_NAME') == 'workflow_run',
                'Release writes are only available in the automatic workflow_run job')
        api = GitHubAPI(os.getenv('GITHUB_TOKEN', ''))
        source = source_snapshot(args.source_root)
        promote(api, args.repository, read_json(args.event.read_bytes()), source, report)
    except PromotionError as exc:
        report.update(status='failed', error=str(exc)[:700])
        result = 1
    except Exception as exc:
        report.update(status='failed', error='Unexpected promotion error: ' + type(exc).__name__)
        result = 1
    finally:
        report['completed_at'] = datetime.now(timezone.utc).isoformat()
        (args.report_dir / 'report.json').write_bytes(json_bytes(report))
        print(json.dumps({key: report[key] for key in ('status', 'phase', 'reason', 'error', 'release_url') if key in report}))
    return result


if __name__ == '__main__':
    raise SystemExit(main())
