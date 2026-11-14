"""Release promotion contract with deterministic API/asset transport fixtures."""
from copy import deepcopy
import hashlib
import io
import json
from pathlib import Path
import unittest
from urllib.error import HTTPError
from urllib.parse import urlsplit
import zipfile

from scripts import promote_release as promotion


REPOSITORY = 'uulab-official/3d-printer-agent'
SHA = 'a' * 40
VERSION = '0.3.0'
WHEEL = f'3d_printer_agent_local-{VERSION}-py3-none-any.whl'


def digest(content):
    return hashlib.sha256(content).hexdigest()


def encoded(value):
    return (json.dumps(value, sort_keys=True, indent=2) + '\n').encode()


def zipped(files):
    output = io.BytesIO()
    with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED) as archive:
        for name, content in files.items():
            archive.writestr(name, content)
    return output.getvalue()


def source():
    return promotion.SourceSnapshot(SHA, VERSION, {
        'print_agent/__init__.py': b'__version__ = "0.3.0"\n',
        'print_agent/engine.py': b'# deterministic fixture; never executed\n',
        'print_agent/static/index.html': b'<html>Fixture</html>\n',
    }, b'# synthetic qualification source\n', '2.7.0', ('cadquery==2.7.0',))


def workflow(path, number):
    return {'id': number, 'path': path, 'head_sha': SHA, 'head_branch': 'main',
            'event': 'push', 'status': 'completed', 'conclusion': 'success', 'run_attempt': 1,
            'repository': {'full_name': REPOSITORY}, 'head_repository': {'full_name': REPOSITORY}}


class FakeAPI:
    def __init__(self):
        self.snapshot = source()
        self.main_sha = SHA
        self.main_reads = 0
        self.change_main_after = None
        self.runs = [workflow(path, index + 1) for index, path in enumerate(promotion.WORKFLOW_PATHS)]
        self.event = {'repository': {'full_name': REPOSITORY}, 'workflow_run': deepcopy(self.runs[-1])}
        self.artifacts = []
        self.binary = {}
        self.releases = []
        self.tag = None
        self.writes = []
        self.downloads = []
        self.fail_upload_after = None
        self.tamper_upload = False
        self.after_upload = None
        self.after_tag_create = None
        self.make_artifacts()

    def make_artifacts(self, wheel_files=None):
        files = dict(self.snapshot.files if wheel_files is None else wheel_files)
        files['3d_printer_agent_local-0.3.0.dist-info/METADATA'] = (
            b'Metadata-Version: 2.4\nName: 3d-printer-agent-local\nVersion: 0.3.0\n'
            b'Requires-Dist: cadquery==2.7.0\nRequires-Python: <3.14,>=3.11\n')
        files['3d_printer_agent_local-0.3.0.dist-info/WHEEL'] = (
            b'Wheel-Version: 1.0\nRoot-Is-Purelib: true\nTag: py3-none-any\n')
        files['3d_printer_agent_local-0.3.0.dist-info/entry_points.txt'] = (
            b'[console_scripts]\nprinter-agent = print_agent.__main__:main\n')
        wheel = zipped(files)
        receipt = encoded({'schema_version': 1, 'filename': WHEEL, 'bytes': len(wheel),
                           'sha256': digest(wheel), 'source_commit': SHA})
        self.artifacts = []
        self.artifact_files = {}
        self.add_artifact('installable-wheel-' + SHA, {
            WHEEL: wheel, 'wheel-receipt.json': receipt,
            'SHA256SUMS': f'{digest(wheel)}  {WHEEL}\n'.encode()})
        for platform, (system, machine) in promotion.PLATFORMS.items():
            required = sorted(promotion.REQUIRED_CHECKS | {'installed_bytes_' + name for name in self.snapshot.files})
            script = self.snapshot.qualification_script
            if platform == 'windows-2025':
                script = script.replace(b'\n', b'\r\n')
            report = {'schema_version': 1, 'status': 'passed', 'source_commit': SHA,
                      'checks': [{'id': name, 'passed': True, 'detail': ''} for name in required],
                      'checks_passed': len(required), 'checks_total': len(required),
                      'platform': {'system': system, 'machine': machine}, 'python': '3.12.10',
                      'versions': {'application': VERSION, 'distribution': VERSION, 'cadquery': '2.7.0'},
                      'packaged_application_files': len(self.snapshot.files),
                      'script_sha256': digest(script),
                      'wheel': {'filename': WHEEL, 'bytes': len(wheel), 'sha256': digest(wheel),
                                'receipt_sha256': digest(receipt)},
                      'limits': {'physical_print_verified': False, 'live_provider_executed': False,
                                 'native_slicer_executed': False, 'browser_executed': False, 'synthetic_data': True}}
            self.add_artifact('package-evidence-' + platform, {
                'report.json': encoded(report), 'wheel-receipt.json': receipt,
                'wheel.sha256': f'{digest(wheel)}  {WHEEL}\n'.encode(),
                'saved fixture/data.json': b'{"synthetic":true}\n'})

    def add_artifact(self, name, files):
        identifier = 20 + len(self.artifacts)
        content = zipped(files)
        self.artifacts.append({'id': identifier, 'name': name, 'size_in_bytes': len(content),
                               'digest': 'sha256:' + digest(content), 'expired': False,
                               'workflow_run': {'id': 2, 'head_sha': SHA}})
        self.binary[f'/repos/{REPOSITORY}/actions/artifacts/{identifier}/zip'] = content
        self.artifact_files[name] = dict(files)

    def replace_artifact(self, name, files):
        item = next(item for item in self.artifacts if item['name'] == name)
        content = zipped(files)
        item.update(size_in_bytes=len(content), digest='sha256:' + digest(content))
        self.binary[f'/repos/{REPOSITORY}/actions/artifacts/{item["id"]}/zip'] = content
        self.artifact_files[name] = dict(files)

    def mutate_report(self, platform, mutation):
        name = 'package-evidence-' + platform
        files = dict(self.artifact_files[name])
        report = json.loads(files['report.json'])
        mutation(report)
        files['report.json'] = encoded(report)
        self.replace_artifact(name, files)

    def json(self, method, path, payload=None, *, not_found=False):
        prefix = f'/repos/{REPOSITORY}'
        if method != 'GET':
            self.writes.append((method, path, deepcopy(payload)))
        if path == prefix + '/git/ref/heads/main':
            self.main_reads += 1
            if self.change_main_after is not None and self.main_reads > self.change_main_after:
                self.main_sha = 'b' * 40
            return {'object': {'type': 'commit', 'sha': self.main_sha}}
        if path.startswith(prefix + '/actions/runs?'):
            return {'workflow_runs': deepcopy(self.runs)}
        if path.startswith(prefix + '/actions/runs/2/artifacts?'):
            return {'artifacts': deepcopy(self.artifacts)}
        if path.startswith(prefix + '/actions/runs/'):
            identifier = int(path.rsplit('/', 1)[1])
            return deepcopy(next(run for run in self.runs if run['id'] == identifier))
        if path.startswith(prefix + '/git/ref/tags/'):
            return None if self.tag is None else {'object': {'type': 'commit', 'sha': self.tag}}
        if method == 'POST' and path == prefix + '/git/refs':
            assert self.tag is None
            self.tag = payload['sha']
            if self.after_tag_create:
                self.after_tag_create()
            return {'ref': payload['ref'], 'object': {'type': 'commit', 'sha': self.tag}}
        if path.startswith(prefix + '/releases?'):
            return deepcopy(self.releases)
        if method == 'POST' and path == prefix + '/releases':
            release = {**payload, 'id': 90, 'assets': [],
                       'html_url': f'https://github.com/{REPOSITORY}/releases/tag/v{VERSION}'}
            self.releases.append(release)
            return deepcopy(release)
        if path.startswith(prefix + '/releases/90/assets?'):
            return deepcopy(self.releases[0]['assets'])
        if path == prefix + '/releases/90':
            if method == 'PATCH':
                self.releases[0].update(payload)
                self.tag = self.releases[0]['target_commitish']
            return deepcopy(self.releases[0])
        raise AssertionError((method, path))

    def download(self, path, *, limit, accept):
        expected = ('application/vnd.github+json' if '/actions/artifacts/' in path
                    else 'application/octet-stream')
        assert accept == expected, (path, accept)
        self.downloads.append(path)
        content = self.binary[path]
        if len(content) > limit:
            raise promotion.PromotionError('download limit exceeded')
        return content

    def upload(self, repository, release_id, name, content):
        assert repository == REPOSITORY and release_id == 90
        assets = self.releases[0]['assets']
        if self.fail_upload_after is not None and len(assets) >= self.fail_upload_after:
            raise promotion.PromotionError('synthetic interrupted upload')
        assert not any(asset['name'] == name for asset in assets)
        self.writes.append(('UPLOAD', name, bytes(content)))
        identifier = 100 + len(assets)
        asset = {'id': identifier, 'name': name, 'size': len(content), 'state': 'uploaded',
                 'digest': 'sha256:' + digest(content)}
        assets.append(asset)
        self.binary[f'/repos/{REPOSITORY}/releases/assets/{identifier}'] = (
            b'changed after upload' if self.tamper_upload else content)
        if self.after_upload:
            self.after_upload()
        return deepcopy(asset)


class PromotionTests(unittest.TestCase):
    def setUp(self):
        self.api = FakeAPI()

    def promote(self):
        return promotion.promote(self.api, REPOSITORY, self.api.event, self.api.snapshot)

    def test_exact_qualified_bytes_are_uploaded_and_verified_before_publication(self):
        report = self.promote()
        self.assertEqual(report['status'], 'published')
        release = self.api.releases[0]
        self.assertFalse(release['draft'])
        self.assertEqual(release['target_commitish'], SHA)
        self.assertEqual(len(release['assets']), 7)
        uploaded = {item[1]: item[2] for item in self.api.writes if item[0] == 'UPLOAD'}
        for name, content in self.api.artifact_files['installable-wheel-' + SHA].items():
            self.assertEqual(uploaded[name], content)
        self.assertEqual(self.api.writes[-1], ('PATCH', f'/repos/{REPOSITORY}/releases/90', {'draft': False}))

    def test_download_callers_send_endpoint_specific_accept_headers(self):
        requests, redirects = [], {}
        fixture = self.api
        class Opener:
            def open(self, request, timeout):
                requests.append(request)
                address = urlsplit(request.full_url)
                if address.hostname == 'api.github.com':
                    artifact = '/actions/artifacts/' in address.path
                    expected = 'application/vnd.github+json' if artifact else 'application/octet-stream'
                    if request.get_header('Accept') != expected:
                        raise HTTPError(request.full_url, 415, 'Unsupported Media Type', {}, None)
                    content = fixture.binary[address.path]
                    if artifact:
                        target = 'https://release-assets.githubusercontent.com/synthetic/' + digest(address.path.encode())
                        redirects[target] = content
                        raise HTTPError(request.full_url, 302, 'redirect', {'Location': target}, None)
                    return Response(content)
                return Response(redirects[request.full_url])
        self.api.download = promotion.GitHubAPI('private-token', opener=Opener()).download
        self.assertEqual(self.promote()['status'], 'published')
        actions = [request for request in requests if '/actions/artifacts/' in request.full_url]
        assets = [request for request in requests if '/releases/assets/' in request.full_url]
        redirected = [request for request in requests if request.full_url in redirects]
        self.assertEqual((len(actions), len(assets), len(redirected)), (4, 7, 4))
        for request in actions:
            self.assertEqual(request.get_header('Accept'), 'application/vnd.github+json')
        for request in assets:
            self.assertEqual(request.get_header('Accept'), 'application/octet-stream')
        for request in actions + assets:
            self.assertEqual(request.get_header('Authorization'), 'Bearer private-token')
        for request in redirected:
            self.assertIsNone(request.get_header('Authorization'))

    def test_each_event_boundary_blocks_publishing_without_mutations(self):
        mutations = [lambda event: event['workflow_run'].update(event='pull_request'),
                     lambda event: event['workflow_run'].update(head_branch='feature'),
                     lambda event: event['workflow_run']['head_repository'].update(full_name='fork/repo'),
                     lambda event: event['repository'].update(full_name='fork/repo'),
                     lambda event: event['workflow_run'].update(conclusion='failure'),
                     lambda event: event['workflow_run'].update(path='.github/workflows/imposter.yml')]
        for mutation in mutations:
            with self.subTest(mutation=mutation):
                self.api = FakeAPI()
                mutation(self.api.event)
                self.assertEqual(self.promote()['status'], 'skipped')
                self.assertEqual(self.api.writes, [])

    def test_old_main_and_checkout_mismatch_do_not_publish(self):
        self.api.main_sha = 'b' * 40
        self.assertEqual(self.promote()['status'], 'skipped')
        self.assertEqual(len(self.api.writes), 0)
        self.api.main_sha = SHA
        self.api.snapshot = promotion.SourceSnapshot('b' * 40, VERSION, self.api.snapshot.files,
                                                    self.api.snapshot.qualification_script, '2.7.0')
        self.assertEqual(self.promote()['status'], 'skipped')
        self.assertEqual(self.api.writes, [])

    def test_latest_pending_or_failed_gate_is_not_replaced_by_older_success(self):
        for status, conclusion in [('queued', None), ('completed', 'failure')]:
            with self.subTest(status=status):
                self.api = FakeAPI()
                newer = deepcopy(self.api.runs[0])
                newer.update(id=9, status=status, conclusion=conclusion)
                self.api.runs.append(newer)
                self.assertEqual(self.promote()['status'], 'skipped')
                self.assertEqual(self.api.writes, [])

    def test_missing_or_mismatched_gate_is_a_noop(self):
        self.api.runs.pop(0)
        self.assertEqual(self.promote()['status'], 'skipped')
        self.assertEqual(self.api.writes, [])
        self.api = FakeAPI()
        self.api.runs[0]['head_sha'] = 'b' * 40
        self.assertEqual(self.promote()['status'], 'skipped')
        self.assertEqual(self.api.writes, [])

    def test_archive_digest_and_source_receipt_are_required(self):
        self.api.artifacts[0]['digest'] = 'sha256:' + '0' * 64
        with self.assertRaises(promotion.PromotionError):
            self.promote()
        self.assertEqual(self.api.writes, [])
        self.api = FakeAPI()
        name = 'installable-wheel-' + SHA
        files = dict(self.api.artifact_files[name])
        receipt = json.loads(files['wheel-receipt.json'])
        receipt['source_commit'] = 'b' * 40
        files['wheel-receipt.json'] = encoded(receipt)
        self.api.replace_artifact(name, files)
        with self.assertRaises(promotion.PromotionError):
            self.promote()
        self.assertEqual(self.api.writes, [])

    def test_newest_rerun_artifact_supersedes_retained_failed_platform_evidence(self):
        name = 'package-evidence-macos-15'
        passing_files = dict(self.api.artifact_files[name])
        old = next(item for item in self.api.artifacts if item['name'] == name)
        self.api.mutate_report('macos-15', lambda report: report.update(status='failed'))
        self.api.add_artifact(name, passing_files)
        newest_id = self.api.artifacts[-1]['id']
        # The list order and old successful platform attempts must not determine
        # which rerun artifact is selected.
        self.api.artifacts.reverse()
        self.api.runs[1]['run_attempt'] = 2
        report = self.promote()
        self.assertEqual(report['status'], 'published')
        selected = next(item for item in report['artifacts'] if item['name'] == name)
        self.assertEqual(selected['id'], newest_id)
        self.assertNotIn(f'/repos/{REPOSITORY}/actions/artifacts/{old["id"]}/zip', self.api.downloads)

    def test_invalid_newest_rerun_artifact_never_falls_back_to_older_success(self):
        for invalid in ('failed_report', 'archive_digest', 'provenance', 'expired'):
            with self.subTest(invalid=invalid):
                self.api = FakeAPI()
                name = 'package-evidence-macos-15'
                older = next(item for item in self.api.artifacts if item['name'] == name)
                files = dict(self.api.artifact_files[name])
                if invalid == 'failed_report':
                    report = json.loads(files['report.json'])
                    report['status'] = 'failed'
                    files['report.json'] = encoded(report)
                self.api.add_artifact(name, files)
                newest = self.api.artifacts[-1]
                if invalid == 'archive_digest':
                    newest['digest'] = 'sha256:' + '0' * 64
                elif invalid == 'provenance':
                    newest['workflow_run']['head_sha'] = 'b' * 40
                elif invalid == 'expired':
                    newest['expired'] = True
                expected = {'failed_report': 'Platform report', 'archive_digest': 'archive digest/size',
                            'provenance': 'artifact identity', 'expired': 'artifact identity'}[invalid]
                with self.assertRaisesRegex(promotion.PromotionError, expected):
                    self.promote()
                self.assertEqual(self.api.writes, [])
                self.assertNotIn(f'/repos/{REPOSITORY}/actions/artifacts/{older["id"]}/zip', self.api.downloads)

    def test_unsafe_and_unexpected_wheel_members_are_rejected(self):
        name = 'installable-wheel-' + SHA
        files = dict(self.api.artifact_files[name])
        files['../outside'] = b'not extracted'
        self.api.replace_artifact(name, files)
        with self.assertRaises(promotion.PromotionError):
            self.promote()
        self.assertEqual(self.api.writes, [])
        self.api = FakeAPI()
        modified = dict(self.api.snapshot.files)
        modified['print_agent/extra.py'] = b'never execute this\n'
        self.api.make_artifacts(modified)
        with self.assertRaises(promotion.PromotionError):
            self.promote()
        self.assertEqual(self.api.writes, [])

    def test_self_consistent_but_changed_wheel_source_is_rejected(self):
        modified = dict(self.api.snapshot.files)
        modified['print_agent/engine.py'] = b'changed after commit\n'
        self.api.make_artifacts(modified)
        with self.assertRaises(promotion.PromotionError):
            self.promote()
        self.assertEqual(self.api.writes, [])

    def test_extra_install_time_code_outside_application_package_is_rejected(self):
        files = dict(self.api.snapshot.files)
        files['startup.pth'] = b'import external_code\n'
        self.api.make_artifacts(files)
        with self.assertRaises(promotion.PromotionError):
            self.promote()
        self.assertEqual(self.api.writes, [])

    def test_failed_incomplete_and_other_wheel_platform_reports_cannot_publish(self):
        def missing_backup(report):
            report['checks'] = [item for item in report['checks'] if item['id'] != 'backup_restore_to_new_directory']
            report['checks_passed'] = report['checks_total'] = len(report['checks'])
        mutations = [lambda r: r.update(status='failed'),
                     lambda r: r['checks'][0].update(passed=False),
                     lambda r: r['wheel'].update(sha256='0' * 64),
                     lambda r: r['versions'].update(application='0.2.0'),
                     lambda r: r.update(script_sha256='0' * 64),
                     missing_backup]
        for mutation in mutations:
            with self.subTest(mutation=mutation):
                self.api = FakeAPI()
                self.api.mutate_report('macos-15', mutation)
                with self.assertRaises(promotion.PromotionError):
                    self.promote()
                self.assertEqual(self.api.writes, [])

    def test_tag_pointing_elsewhere_is_never_moved(self):
        self.api.tag = 'b' * 40
        with self.assertRaises(promotion.PromotionError):
            self.promote()
        self.assertEqual(self.api.tag, 'b' * 40)
        self.assertEqual(self.api.writes, [])

    def test_failed_upload_leaves_draft_and_exact_rerun_resumes(self):
        self.api.fail_upload_after = 2
        with self.assertRaises(promotion.PromotionError):
            self.promote()
        self.assertTrue(self.api.releases[0]['draft'])
        self.assertEqual(len(self.api.releases[0]['assets']), 2)
        self.api.writes.clear()
        self.api.fail_upload_after = None
        self.assertEqual(self.promote()['status'], 'published')
        self.assertEqual(sum(item[0] == 'UPLOAD' for item in self.api.writes), 5)
        self.assertFalse(any(item[0] == 'POST' and item[1].endswith('/releases') for item in self.api.writes))

    def test_every_existing_draft_asset_is_verified_before_resuming_uploads(self):
        self.promote()
        release = self.api.releases[0]
        release['draft'] = True
        self.api.tag = None
        retained = next(asset for asset in release['assets'] if asset['name'] == 'wheel-receipt.json')
        release['assets'] = [retained]
        self.api.binary[f'/repos/{REPOSITORY}/releases/assets/{retained["id"]}'] = b'changed existing bytes'
        self.api.writes.clear()
        with self.assertRaises(promotion.PromotionError):
            self.promote()
        self.assertEqual(self.api.writes, [])

    def test_new_version_tag_is_created_once_before_publication(self):
        self.promote()
        tag_writes = [item for item in self.api.writes if item[0] == 'POST' and item[1].endswith('/git/refs')]
        self.assertEqual(tag_writes, [('POST', f'/repos/{REPOSITORY}/git/refs', {'ref': 'refs/tags/v0.3.0', 'sha': SHA})])
        self.assertEqual(self.api.writes[-1][0], 'PATCH')

    def test_mismatched_draft_existing_asset_or_upload_readback_is_not_published(self):
        self.api.fail_upload_after = 1
        with self.assertRaises(promotion.PromotionError):
            self.promote()
        self.api.fail_upload_after = None
        self.api.releases[0]['body'] += '\nChanged by another actor.'
        self.api.writes.clear()
        with self.assertRaises(promotion.PromotionError):
            self.promote()
        self.assertEqual(self.api.writes, [])
        self.api = FakeAPI()
        self.api.tamper_upload = True
        with self.assertRaises(promotion.PromotionError):
            self.promote()
        self.assertTrue(self.api.releases[0]['draft'])
        self.assertFalse(any(item[0] == 'PATCH' for item in self.api.writes))

    def test_published_release_is_verified_without_any_write(self):
        self.promote()
        self.api.writes.clear()
        self.assertEqual(self.promote()['status'], 'already_published')
        self.assertEqual(self.api.writes, [])
        self.api.releases[0]['assets'].append({'id': 999, 'name': 'extra.txt', 'size': 1, 'state': 'uploaded'})
        with self.assertRaises(promotion.PromotionError):
            self.promote()
        self.assertEqual(self.api.writes, [])

    def test_main_advancing_before_write_prevents_publication(self):
        self.api.change_main_after = 1
        self.assertEqual(self.promote()['status'], 'skipped')
        self.assertEqual(self.api.writes, [])

    def test_changed_run_attempt_during_upload_preserves_unpublished_draft(self):
        for status, conclusion in [('in_progress', None), ('completed', 'success')]:
            with self.subTest(status=status):
                self.api = FakeAPI()
                self.api.after_upload = lambda: self.api.runs[0].update(
                    run_attempt=2, status=status, conclusion=conclusion)
                report = self.promote()
                self.assertEqual(report['status'], 'skipped')
                self.assertTrue(self.api.releases[0]['draft'])
                self.assertIsNone(self.api.tag)
                self.assertFalse(any(item[0] == 'PATCH' for item in self.api.writes))

    def test_newer_failed_run_during_upload_preserves_unpublished_draft(self):
        def append_new_failure():
            if not any(run['id'] == 9 for run in self.api.runs):
                newer = deepcopy(self.api.runs[0])
                newer.update(id=9, conclusion='failure')
                self.api.runs.append(newer)
        self.api.after_upload = append_new_failure
        self.assertEqual(self.promote()['status'], 'skipped')
        self.assertTrue(self.api.releases[0]['draft'])
        self.assertIsNone(self.api.tag)
        self.assertFalse(any(item[0] == 'PATCH' for item in self.api.writes))

    def test_gate_changes_after_tag_creation_preserve_unpublished_draft(self):
        for changed in ('attempt', 'newer_run'):
            with self.subTest(changed=changed):
                self.api = FakeAPI()
                def change_gate():
                    if changed == 'attempt':
                        self.api.runs[0].update(run_attempt=2, status='in_progress', conclusion=None)
                    else:
                        newer = deepcopy(self.api.runs[0])
                        newer.update(id=9, conclusion='failure')
                        self.api.runs.append(newer)
                self.api.after_tag_create = change_gate
                self.assertEqual(self.promote()['status'], 'skipped')
                self.assertTrue(self.api.releases[0]['draft'])
                self.assertEqual(self.api.tag, SHA)
                self.assertFalse(any(item[0] == 'PATCH' for item in self.api.writes))


class Response(io.BytesIO):
    def __init__(self, content):
        super().__init__(content)
        self.status = 200
        self.headers = {}


class TransportTests(unittest.TestCase):
    def test_download_budget_is_enforced_on_actual_bytes_without_declared_size(self):
        class Opener:
            def open(self, request, timeout):
                return Response(b'x' * 100)
        api = promotion.GitHubAPI('private-token', opener=Opener())
        with self.assertRaises(promotion.PromotionError):
            api.download('/repos/example/repo/actions/artifacts/1/zip', limit=10,
                         accept='application/vnd.github+json')

    def test_signed_download_redirect_never_receives_the_api_token(self):
        for path, accept in [('/repos/example/repo/actions/artifacts/1/zip', 'application/vnd.github+json'),
                             ('/repos/example/repo/releases/assets/1', 'application/octet-stream')]:
            with self.subTest(path=path):
                requests = []
                class Opener:
                    def open(self, request, timeout):
                        requests.append(request)
                        if len(requests) == 1:
                            raise HTTPError(request.full_url, 302, 'redirect',
                                            {'Location': 'https://release-assets.githubusercontent.com/synthetic?secret=signed'}, None)
                        return Response(b'qualified bytes')
                api = promotion.GitHubAPI('private-token', opener=Opener())
                self.assertEqual(api.download(path, limit=100, accept=accept), b'qualified bytes')
                self.assertEqual(requests[0].get_header('Accept'), accept)
                self.assertEqual(requests[0].get_header('Authorization'), 'Bearer private-token')
                self.assertIsNone(requests[1].get_header('Authorization'))

    def test_non_https_redirect_and_external_authenticated_request_are_rejected(self):
        calls = []
        class Opener:
            def open(self, request, timeout):
                calls.append(request)
                raise HTTPError(request.full_url, 302, 'redirect', {'Location': 'http://127.0.0.1/private'}, None)
        api = promotion.GitHubAPI('private-token', opener=Opener())
        with self.assertRaises(promotion.PromotionError) as caught:
            api.download('/repos/example/repo/actions/artifacts/1/zip', limit=100,
                         accept='application/vnd.github+json')
        self.assertNotIn('private-token', str(caught.exception))
        self.assertNotIn('127.0.0.1', str(caught.exception))
        with self.assertRaises(promotion.PromotionError):
            api.json('GET', 'https://foreign.example/steal')
        self.assertEqual(len(calls), 1)


if __name__ == '__main__':
    unittest.main()
