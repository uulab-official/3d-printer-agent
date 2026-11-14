"""Canonical job records, a recoverable history index and verified byte snapshots.

The application owns the data-directory lease. Recovery is deliberately explicit:
constructing another store never interrupts a live operation.
"""
import base64
import binascii
import copy
from contextlib import closing
import hashlib
import io
import json
import logging
import os
import re
import sqlite3
import stat
import threading
import uuid
import zipfile
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath

from . import __version__
from .schemas import GeometryRequest


_GENERATED_FILES = {'stl': 'model.stl', 'step': 'model.step', 'three_mf': 'model.3mf', 'source': 'model.py'}
_SLICE_FILES = {'sliced_three_mf', 'prepared_three_mf'}
_ALLOWED_FILES = {*_GENERATED_FILES, 'manifest', *_SLICE_FILES}
_JOB_STATUSES = {'generating', 'geometry_validated', 'failed', 'interrupted'}
_MAX_ARTIFACT_BYTES = 512 * 1024 * 1024
_MAX_RECORD_BYTES = 64 * 1024 * 1024
_MAX_MANIFEST_BYTES = 8 * 1024 * 1024
_UNREADABLE_MESSAGE = '작업 기록 파일을 읽을 수 없습니다. 원본 파일은 보존했습니다.'
_INTEGRITY_MESSAGE = '저장한 파일의 크기 또는 SHA-256이 원래 기록과 다르거나 파일을 읽을 수 없습니다. 원본 파일을 복구하거나 모델을 다시 생성하세요.'
_SCHEMA = 'CREATE TABLE IF NOT EXISTS jobs (id TEXT PRIMARY KEY, created_at TEXT NOT NULL, title TEXT NOT NULL, template TEXT, status TEXT NOT NULL, user_outcome TEXT)'
_LOGGER = logging.getLogger(__name__)
_ABSENT_HASH = object()


class ArtifactIntegrityError(ValueError):
    """A saved receipt cannot establish the bytes being returned."""


class JobRecordError(ValueError):
    """A known record is damaged or cannot safely be interpreted."""


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def _valid_timestamp(value):
    if not isinstance(value, str) or not 1 <= len(value) <= 80:
        return False
    try:
        return datetime.fromisoformat(value).utcoffset() is not None
    except (ValueError, TypeError, OverflowError):
        return False


def _json_bytes(value):
    try:
        return json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False).encode('utf-8')
    except (TypeError, ValueError, UnicodeError, RecursionError) as exc:
        raise ValueError('유효한 JSON 문자열과 유한한 숫자로 구성된 작업 기록이 필요합니다.') from exc


def _same_json(left, right):
    """Compare JSON values without equating booleans with numeric values."""
    return json.dumps(left, sort_keys=True, separators=(',', ':'), allow_nan=False) == json.dumps(
        right, sort_keys=True, separators=(',', ':'), allow_nan=False)


def _parse_json(content):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError('Duplicate JSON key')
            result[key] = value
        return result
    def constant(_):
        raise ValueError('Nonfinite JSON')
    return json.loads(content, object_pairs_hook=pairs, parse_constant=constant)


def _receipt(filename, content):
    return {'filename': filename, 'bytes': len(content), 'sha256': hashlib.sha256(content).hexdigest()}


def _check_receipt(value, filename):
    if (not isinstance(value, dict) or value.get('filename') != filename
            or type(value.get('bytes')) is not int or not 0 < value['bytes'] <= _MAX_ARTIFACT_BYTES
            or not isinstance(value.get('sha256'), str)
            or re.fullmatch(r'[a-f0-9]{64}', value['sha256']) is None):
        raise ArtifactIntegrityError(_INTEGRITY_MESSAGE)
    return value


def _read_regular(path, maximum, *, expected_size=None):
    """Read at most the admitted budget; never follow a final symlink or FIFO."""
    if path.is_symlink():
        raise OSError('Symlink is not a saved regular file')
    metadata = path.stat()
    if not stat.S_ISREG(metadata.st_mode) or metadata.st_size > maximum:
        raise OSError('Invalid file type or size')
    if expected_size is not None and metadata.st_size != expected_size:
        raise OSError('File size changed')
    flags = os.O_RDONLY | getattr(os, 'O_BINARY', 0) | getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_NONBLOCK', 0)
    with os.fdopen(os.open(path, flags), 'rb') as stream:
        current = os.fstat(stream.fileno())
        if not stat.S_ISREG(current.st_mode) or current.st_size > maximum:
            raise OSError('Invalid opened file type or size')
        if expected_size is not None and current.st_size != expected_size:
            raise OSError('Opened file size changed')
        content = stream.read(maximum + 1)
    if len(content) > maximum or (expected_size is not None and len(content) != expected_size):
        raise OSError('File size changed while reading')
    return content


def _atomic_write(path, content):
    temporary = path.parent / ('.' + path.name + '-' + uuid.uuid4().hex + '.tmp')
    try:
        with temporary.open('xb') as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


class JobStore:
    def __init__(self, root: Path):
        self.root = Path(root).expanduser().resolve()
        self.jobs_dir = self.root / 'jobs'
        if self.jobs_dir.is_symlink():
            raise JobRecordError('작업 보관 폴더는 심볼릭 링크일 수 없습니다.')
        self.jobs_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = self.root / 'history.sqlite3'
        self.lock = threading.RLock()
        self._index_error = None
        self.recovered_index_backup = None
        try:
            with closing(self._connect()) as db, db:
                self._schema(db)
        except sqlite3.DatabaseError as exc:
            # Do not repair a running application's index during construction.
            # The owner must call recover() after acquiring the exclusive lease.
            self._index_error = exc

    def _require_index(self):
        if self._index_error is not None:
            raise JobRecordError('작업 이력 인덱스를 읽을 수 없습니다. 앱을 종료한 뒤 다시 시작해 복구를 확인해 주세요.') from self._index_error

    def _connect(self, *, recovering=False):
        if not recovering:
            self._require_index()
        if self.db_path.is_symlink():
            raise JobRecordError('작업 이력 인덱스는 심볼릭 링크일 수 없습니다.')
        db = sqlite3.connect(self.db_path)
        db.row_factory = sqlite3.Row
        return db

    @staticmethod
    def _schema(db):
        db.execute(_SCHEMA)
        db.execute('CREATE INDEX IF NOT EXISTS jobs_history_order ON jobs (created_at DESC, id DESC)')

    def directory(self, job_id: str) -> Path:
        if not isinstance(job_id, str) or not re.fullmatch(r'[a-f0-9]{32}', job_id):
            raise ValueError('올바른 작업 ID가 필요합니다.')
        folder = self.jobs_dir / job_id
        if folder.is_symlink():
            raise JobRecordError('작업 폴더는 심볼릭 링크일 수 없습니다. 원본은 변경하지 않았습니다.')
        return folder

    @staticmethod
    def _row(job):
        return (job['id'], job['created_at'], job['title'], job.get('template'), job['status'],
                json.dumps(job.get('user_outcome'), ensure_ascii=False, allow_nan=False))

    def _write_record(self, job):
        content = _json_bytes(job)
        if len(content) > _MAX_RECORD_BYTES:
            raise ValueError('작업 기록은 64 MiB 이하여야 합니다. 기존 기록은 변경하지 않았습니다.')
        _atomic_write(self.directory(job['id']) / 'job.json', content)

    def _write(self, job):
        # The record is canonical. Recovery repairs a failed derived-index write.
        self._require_index()
        self._write_record(job)
        with closing(self._connect()) as db, db:
            db.execute('INSERT OR REPLACE INTO jobs VALUES (?,?,?,?,?,?)', self._row(job))

    def _read(self, job_id, *, recovering=False):
        if not recovering:
            self._require_index()
        folder = self.directory(job_id)
        path = folder / 'job.json'
        if not path.exists() and not path.is_symlink():
            if folder.exists():
                raise JobRecordError(_UNREADABLE_MESSAGE)
            raise KeyError('작업을 찾을 수 없습니다.')
        try:
            job = _parse_json(_read_regular(path, _MAX_RECORD_BYTES))
            required = {'id', 'created_at', 'title', 'template', 'status', 'result', 'artifacts', '_files',
                        'bundle_url', 'events', 'latest_slice', 'user_outcome'}
            if not isinstance(job, dict) or not required.issubset(job) or job['id'] != job_id:
                raise ValueError('Record identity or fields differ')
            if (not _valid_timestamp(job['created_at']) or not isinstance(job['title'], str)
                    or job['status'] not in _JOB_STATUSES
                    or job['template'] not in (None, 'tray', 'cable_comb', 'magnet_frame')
                    or not isinstance(job['events'], list)
                    or any(not isinstance(event, dict) or not isinstance(event.get('type'), str) for event in job['events'])
                    or not isinstance(job['_files'], dict) or not isinstance(job['artifacts'], dict)
                    or set(job['_files']) != set(job['artifacts']) or set(job['_files']) - _ALLOWED_FILES
                    or any(not isinstance(name, str) for name in job['_files'].values())
                    or any(not isinstance(url, str) for url in job['artifacts'].values())
                    or (job['result'] is not None and not isinstance(job['result'], dict))
                    or (job['latest_slice'] is not None and not isinstance(job['latest_slice'], dict))
                    or (job['user_outcome'] is not None and not isinstance(job['user_outcome'], dict))
                    or (job['bundle_url'] is not None and not isinstance(job['bundle_url'], str))):
                raise ValueError('Invalid record structure')
            if job['status'] == 'geometry_validated':
                result = job['result']
                fields = {'parameters', 'dimensions_mm', 'volume_mm3', 'geometry_status', 'checks', 'warnings'}
                if (not isinstance(result, dict) or not fields.issubset(result)
                        or not isinstance(result['parameters'], dict)
                        or not isinstance(result['dimensions_mm'], dict)
                        or result.get('template') != job['template']):
                    raise ValueError('Missing completed geometry record')
            latest = job['latest_slice']
            if latest is not None:
                if (not _valid_timestamp(latest.get('recorded_at'))
                        or latest.get('phase') not in (None, 'running', 'finished', 'interrupted')
                        or ('plan' not in latest) or ('execution' not in latest)
                        or (latest['plan'] is not None and not isinstance(latest['plan'], dict))
                        or (latest['execution'] is not None and not isinstance(latest['execution'], dict))):
                    raise ValueError('Invalid saved slice structure')
            if 'request' in job:
                GeometryRequest.model_validate(job['request'])
            if 'design_source' in job and not isinstance(job['design_source'], dict):
                raise ValueError('Invalid source record')
            _json_bytes(job)
            return job
        except (OSError, ValueError, TypeError, RecursionError, OverflowError) as exc:
            raise JobRecordError(_UNREADABLE_MESSAGE) from exc

    @staticmethod
    def _public(job):
        return {key: value for key, value in job.items() if not key.startswith('_')}

    @staticmethod
    def _clear_slice(job):
        for kind in _SLICE_FILES:
            job['_files'].pop(kind, None)
            job['artifacts'].pop(kind, None)
            if isinstance(job.get('_artifact_receipts'), dict):
                job['_artifact_receipts'].pop(kind, None)
        job.pop('_slice_artifact_receipt', None)
        job.pop('_prepared_artifact_receipt', None)

    def reserve(self, *, request=None, design_source=None):
        normalized = GeometryRequest.model_validate(request).model_dump(mode='json') if request is not None else None
        if design_source is not None and not isinstance(design_source, dict):
            raise ValueError('원본 설계 기록은 객체여야 합니다.')
        if design_source is not None:
            _json_bytes(design_source)
        with self.lock:
            self._require_index()
            job_id = uuid.uuid4().hex
            folder = self.directory(job_id)
            folder.mkdir(mode=0o700)
            job = {'id': job_id, 'created_at': now_iso(), 'title': '모델 생성 중',
                   'template': normalized['template'] if normalized is not None else None,
                   'status': 'generating', 'result': None, 'artifacts': {}, '_files': {}, 'bundle_url': None,
                   'events': [], 'latest_slice': None, 'user_outcome': None}
            if normalized is not None:
                job['request'] = normalized
            if design_source is not None:
                job['design_source'] = copy.deepcopy(design_source)
            self._write(job)
            return job_id, folder

    def _preserve_index(self):
        """Keep an exclusive, verified copy before replacing a corrupt index."""
        backup = self.root / ('history-unreadable-' + uuid.uuid4().hex + '.sqlite3')
        try:
            digest = hashlib.sha256()
            with self.db_path.open('rb') as source, backup.open('xb') as destination:
                if not stat.S_ISREG(os.fstat(source.fileno()).st_mode):
                    raise OSError('Index is not a regular file')
                while chunk := source.read(1024 * 1024):
                    digest.update(chunk)
                    destination.write(chunk)
                destination.flush()
                os.fsync(destination.fileno())
            with backup.open('rb') as stream:
                if hashlib.file_digest(stream, 'sha256').digest() != digest.digest():
                    raise OSError('Preserved copy differs')
            with self.db_path.open('rb') as stream:
                if hashlib.file_digest(stream, 'sha256').digest() != digest.digest():
                    raise OSError('Index changed while preserving it')
            return backup
        except OSError as exc:
            raise JobRecordError('손상된 이력 인덱스의 원본 사본을 보존하지 못했습니다. 저장 공간과 권한을 확인하세요. 기존 인덱스는 교체하지 않았습니다.') from exc

    def recover(self):
        """Reconcile canonical files after the caller acquires exclusive ownership."""
        with self.lock:
            backup = None
            try:
                with closing(self._connect(recovering=True)) as db, db:
                    self._schema(db)
                    previous = {row['id']: dict(row) for row in db.execute('SELECT * FROM jobs')
                                if isinstance(row['id'], str) and re.fullmatch(r'[a-f0-9]{32}', row['id'])}
            except sqlite3.DatabaseError as exc:
                self._index_error = exc
                # A locked/read-only/unrecognized database is not evidence of
                # byte corruption and must not be renamed or replaced.
                if (getattr(exc, 'sqlite_errorcode', 0) & 0xff) not in (sqlite3.SQLITE_CORRUPT, sqlite3.SQLITE_NOTADB):
                    raise JobRecordError('작업 이력 인덱스를 복구할 수 없습니다. 저장 공간과 권한을 확인하세요. 기존 인덱스는 교체하지 않았습니다.') from exc
                backup = self._preserve_index()
                previous = {}
            folders = {path.name: path for path in self.jobs_dir.iterdir()
                       if re.fullmatch(r'[a-f0-9]{32}', path.name)}
            rows = []
            counts = {'indexed': 0, 'interrupted': 0, 'unreadable': 0}
            for job_id in sorted(set(previous) | set(folders)):
                try:
                    job = self._read(job_id, recovering=True)
                except (JobRecordError, KeyError):
                    old = previous.get(job_id, {})
                    created = old.get('created_at')
                    if not _valid_timestamp(created):
                        try:
                            created = datetime.fromtimestamp(folders[job_id].lstat().st_mtime, timezone.utc).isoformat()
                        except (OSError, KeyError, ValueError, OverflowError):
                            created = '1970-01-01T00:00:00+00:00'
                    rows.append((job_id, created, '읽을 수 없는 작업 기록', None, 'unreadable', 'null'))
                    counts['unreadable'] += 1
                    continue
                changed = False
                if job['status'] == 'generating':
                    job.update(status='interrupted', title='중단된 모델 생성', result=None,
                               artifacts={}, _files={}, bundle_url=None, latest_slice=None)
                    job.pop('_artifact_receipts', None)
                    job.pop('_slice_artifact_receipt', None)
                    job.pop('_prepared_artifact_receipt', None)
                    job['events'].append({'at': now_iso(), 'type': 'generation_interrupted',
                                          'message': '이전 실행에서 모델 생성이 완료되지 않았습니다. 입력과 부분 파일은 보존했으며 검증된 다운로드는 없습니다.'})
                    counts['interrupted'] += 1
                    changed = True
                latest = job.get('latest_slice')
                if isinstance(latest, dict) and latest.get('phase') == 'running':
                    self._clear_slice(job)
                    job['latest_slice'] = {'recorded_at': now_iso(), 'phase': 'interrupted',
                                           'plan': latest.get('plan'),
                                           'execution': {'status': 'interrupted', 'output_path': None,
                                                         'print_status': 'not_started'}}
                    job['events'].append({'at': now_iso(), 'type': 'slicer_interrupted',
                                          'message': '이전 슬라이싱이 완료되지 않았습니다. 기존 출력 파일을 현재 결과로 제공하지 않습니다.'})
                    changed = True
                if changed:
                    self._write_record(job)
                rows.append(self._row(job))
                counts['indexed'] += 1
            replacement = self.root / ('.history-recovery-' + uuid.uuid4().hex + '.sqlite3') if backup else None
            try:
                with closing(sqlite3.connect(replacement) if replacement else self._connect(recovering=True)) as db, db:
                    self._schema(db)
                    db.execute('BEGIN IMMEDIATE')
                    db.execute('DELETE FROM jobs')
                    db.executemany('INSERT INTO jobs VALUES (?,?,?,?,?,?)', rows)
                if replacement:
                    with replacement.open('rb') as stream:
                        os.fsync(stream.fileno())
                    replacement.replace(self.db_path)
                    self.recovered_index_backup = backup.name
                    _LOGGER.warning('Recovered derived history index; original bytes preserved in %s', backup.name)
                self._index_error = None
            finally:
                if replacement:
                    replacement.unlink(missing_ok=True)
            return counts

    def finish(self, job_id, result, *, design_source=None):
        with self.lock:
            job = self._read(job_id)
            if job['status'] != 'generating':
                raise ValueError('생성 중인 작업에만 완료 결과를 저장할 수 있습니다.')
            if 'request' in job:
                actual = GeometryRequest.model_validate(result['parameters']).model_dump(mode='json')
                if actual != job['request'] or result['template'] != actual['template']:
                    raise ValueError('생성 결과의 치수가 저장한 요청과 다릅니다.')
            if design_source is not None:
                if not isinstance(design_source, dict):
                    raise ValueError('원본 설계 기록은 객체여야 합니다.')
                if 'design_source' in job and not _same_json(design_source, job['design_source']):
                    raise ValueError('생성 전에 저장한 원본 설계 기록을 바꿀 수 없습니다.')
                job['design_source'] = copy.deepcopy(design_source)
            folder = self.directory(job_id)
            hashes = {}
            for kind, filename in result['files'].items():
                if _GENERATED_FILES.get(kind) != filename:
                    raise ValueError('허용되지 않은 생성 파일입니다.')
                try:
                    content = _read_regular(folder / filename, _MAX_ARTIFACT_BYTES)
                except OSError as exc:
                    raise ValueError('생성 파일의 내용을 확인할 수 없습니다.') from exc
                if not content:
                    raise ValueError('생성 파일의 내용이 없습니다.')
                hashes[kind] = _receipt(filename, content)
            if not hashes:
                raise ValueError('내려받을 생성 파일이 없습니다.')
            manifest = {'schema_version': 1, 'app_version': __version__, 'job_id': job_id, 'created_at': job['created_at'],
                        'template': result['template'], 'units': 'mm', 'parameters': result['parameters'],
                        'dimensions_mm': result['dimensions_mm'], 'volume_mm3': result['volume_mm3'],
                        'geometry_status': result['geometry_status'], 'physical_print_status': 'not_tested',
                        'slicer_status': 'not_run', 'checks': result['checks'], 'warnings': result['warnings'],
                        'artifacts': hashes}
            if 'design_source' in job:
                manifest['design_source'] = copy.deepcopy(job['design_source'])
            manifest_bytes = _json_bytes(manifest)
            _atomic_write(folder / 'manifest.json', manifest_bytes)
            job['_files'] = {**result['files'], 'manifest': 'manifest.json'}
            job['_artifact_receipts'] = {**hashes, 'manifest': _receipt('manifest.json', manifest_bytes)}
            job['artifacts'] = {kind: f'/api/jobs/{job_id}/files/{kind}' for kind in job['_files']}
            job['bundle_url'] = f'/api/jobs/{job_id}/bundle'
            job['result'] = copy.deepcopy(result)
            job['template'] = result['template']
            title = {'tray': '칸막이 수납함', 'cable_comb': '열린 케이블 받침', 'magnet_frame': '원형 인셋 프레임'}[result['template']]
            size = result['dimensions_mm']
            job['title'] = f"{title} · {size['x']:g} × {size['y']:g} × {size['z']:g} mm"
            job['status'] = 'geometry_validated'
            job['events'].append({'at': now_iso(), 'type': 'geometry_validated',
                                  'message': 'CAD 형상 검증 및 파일 내보내기 완료. 실물 출력은 미검증입니다.'})
            self._write(job)
            return self._public(job)

    def fail(self, job_id, message):
        with self.lock:
            job = self._read(job_id)
            job.update(status='failed', title='모델 생성 실패', result=None, artifacts={}, _files={}, bundle_url=None)
            job.pop('_artifact_receipts', None)
            job['events'].append({'at': now_iso(), 'type': 'generation_failed', 'message': str(message)[:1000]})
            self._write(job)

    def get(self, job_id):
        with self.lock:
            return self._public(self._read(job_id))

    @staticmethod
    def _cursor(created_at, job_id):
        raw = json.dumps([1, created_at, job_id], separators=(',', ':')).encode('utf-8')
        return base64.urlsafe_b64encode(raw).decode('ascii').rstrip('=')

    @staticmethod
    def _parse_cursor(before):
        if not isinstance(before, str) or not 1 <= len(before) <= 512 or re.fullmatch(r'[A-Za-z0-9_-]+', before) is None:
            raise ValueError('작업 이력의 페이지 위치가 올바르지 않습니다. 목록을 새로 고쳐 주세요.')
        try:
            value = _parse_json(base64.b64decode(before + '=' * (-len(before) % 4), altchars=b'-_', validate=True))
            if (not isinstance(value, list) or len(value) != 3 or type(value[0]) is not int or value[0] != 1
                    or not _valid_timestamp(value[1]) or not isinstance(value[2], str)
                    or re.fullmatch(r'[a-f0-9]{32}', value[2]) is None):
                raise ValueError('Invalid cursor structure')
            return value[1], value[2]
        except (ValueError, TypeError, binascii.Error, UnicodeError, RecursionError) as exc:
            raise ValueError('작업 이력의 페이지 위치가 올바르지 않습니다. 목록을 새로 고쳐 주세요.') from exc

    def list_jobs_page(self, *, limit=20, before=None):
        if type(limit) is not int or not 1 <= limit <= 100:
            raise ValueError('한 페이지에는 작업 1~100개를 요청할 수 있습니다.')
        cursor = self._parse_cursor(before) if before is not None else None
        query = 'SELECT * FROM jobs'
        args = []
        if cursor:
            query += ' WHERE (created_at, id) < (?, ?)'
            args.extend(cursor)
        query += ' ORDER BY created_at DESC, id DESC LIMIT ?'
        args.append(limit + 1)
        with self.lock, closing(self._connect()) as db:
            rows = db.execute(query, args).fetchall()
        jobs = []
        for row in rows[:limit]:
            item = dict(row)
            item['user_outcome'] = json.loads(item['user_outcome'])
            if item['status'] == 'unreadable':
                item['diagnostic'] = _UNREADABLE_MESSAGE
            jobs.append(item)
        next_cursor = self._cursor(jobs[-1]['created_at'], jobs[-1]['id']) if len(rows) > limit else None
        return {'jobs': jobs, 'next_cursor': next_cursor}

    def list_jobs(self):
        return self.list_jobs_page(limit=100)['jobs']

    def _artifact_location(self, job, kind):
        filename = job['_files'].get(kind)
        if filename is None:
            raise KeyError('등록된 파일이 없습니다.')
        try:
            # Older Windows jobs used Path.__str__ for slice paths. Interpret
            # that separator while retaining the original recorded filename.
            normalized = filename.replace('\\', '/') if kind in _SLICE_FILES else filename
            relative = PurePosixPath(normalized)
            if ('\\' in normalized or relative.is_absolute() or not relative.parts
                    or any(part in ('', '.', '..') for part in relative.parts)
                    or str(relative) != normalized or ':' in normalized):
                raise ValueError('Unsafe relative path')
            if kind in _GENERATED_FILES and filename != _GENERATED_FILES[kind]:
                raise ValueError('Unexpected generated filename')
            if kind == 'manifest' and filename != 'manifest.json':
                raise ValueError('Unexpected manifest filename')
            if kind in _SLICE_FILES and relative.suffix.lower() != '.3mf':
                raise ValueError('Unexpected sliced filename')
            if kind == 'prepared_three_mf' and relative.name != 'prepared-project.3mf':
                raise ValueError('Unexpected prepared project filename')
            folder = self.directory(job['id'])
            path = folder.joinpath(*relative.parts)
            current = path
            while current != folder:
                if current.is_symlink():
                    raise ValueError('Symlink in artifact path')
                current = current.parent
            if not path.resolve().is_relative_to(folder.resolve()):
                raise ValueError('Artifact escapes its job')
            return path
        except (OSError, ValueError, TypeError) as exc:
            raise ArtifactIntegrityError(_INTEGRITY_MESSAGE) from exc

    def _verify_bytes(self, job, kind, receipt):
        path = self._artifact_location(job, kind)
        receipt = _check_receipt(receipt, job['_files'][kind])
        try:
            content = _read_regular(path, receipt['bytes'], expected_size=receipt['bytes'])
        except OSError as exc:
            raise ArtifactIntegrityError(_INTEGRITY_MESSAGE) from exc
        if hashlib.sha256(content).hexdigest() != receipt['sha256']:
            raise ArtifactIntegrityError(_INTEGRITY_MESSAGE)
        return path, content

    def _legacy_manifest(self, job):
        """Existing metadata is checked; no original manifest hash is invented."""
        path = self._artifact_location(job, 'manifest')
        try:
            content = _read_regular(path, _MAX_MANIFEST_BYTES)
            manifest = _parse_json(content)
            result = job['result']
            expected = {'schema_version': 1, 'job_id': job['id'], 'created_at': job['created_at'],
                        'template': job['template'], 'units': 'mm', 'physical_print_status': 'not_tested',
                        'slicer_status': 'not_run', **{key: result[key] for key in
                        ('parameters', 'dimensions_mm', 'volume_mm3', 'geometry_status', 'checks', 'warnings')}}
            if 'design_source' in job:
                expected['design_source'] = job['design_source']
            if (not isinstance(manifest, dict) or set(manifest) != set(expected) | {'app_version', 'artifacts'}
                    or any(not _same_json(manifest.get(key), value) for key, value in expected.items())
                    or not isinstance(manifest['app_version'], str) or not isinstance(manifest['artifacts'], dict)):
                raise ValueError('Manifest does not describe saved job')
            originals = set(job['_files']) - {'manifest', *_SLICE_FILES}
            if set(manifest['artifacts']) != originals:
                raise ValueError('Manifest member list differs')
            for kind in originals:
                _check_receipt(manifest['artifacts'][kind], job['_files'][kind])
            return path, content, manifest['artifacts']
        except (OSError, ValueError, KeyError, TypeError, RecursionError) as exc:
            raise ArtifactIntegrityError(_INTEGRITY_MESSAGE) from exc

    def _snapshots(self, job, kinds):
        snapshots = {}
        if '_artifact_receipts' in job:
            receipts = job['_artifact_receipts']
            if not isinstance(receipts, dict) or set(receipts) != set(job['_files']):
                raise ArtifactIntegrityError(_INTEGRITY_MESSAGE)
            for kind in kinds:
                snapshots[kind] = self._verify_bytes(job, kind, receipts.get(kind))
            return snapshots
        manifest_path, manifest_bytes, receipts = self._legacy_manifest(job)
        requested = set(kinds)
        # A legacy manifest has no independent byte receipt: its model receipts
        # and canonical saved metadata must agree before the manifest is offered.
        verify = (set(receipts) | requested) - {'manifest', *_SLICE_FILES} if 'manifest' in requested else requested - _SLICE_FILES
        for kind in verify:
            snapshots[kind] = self._verify_bytes(job, kind, receipts.get(kind))
        if 'manifest' in requested:
            snapshots['manifest'] = manifest_path, manifest_bytes
        if 'prepared_three_mf' in requested:
            # This artifact kind did not exist before versioned byte receipts.
            # A new preparation of a legacy job gets its own explicit receipt.
            snapshots['prepared_three_mf'] = self._verify_bytes(
                job, 'prepared_three_mf', job.get('_prepared_artifact_receipt'))
        if 'sliced_three_mf' in requested:
            receipt = job.get('_slice_artifact_receipt')
            if receipt is not None:
                snapshots['sliced_three_mf'] = self._verify_bytes(job, 'sliced_three_mf', receipt)
            else:
                execution = (job.get('latest_slice') or {}).get('execution') or {}
                expected_hash = execution.get('output_sha256')
                if not isinstance(expected_hash, str) or re.fullmatch(r'[a-f0-9]{64}', expected_hash) is None:
                    raise ArtifactIntegrityError('이전 슬라이싱 파일의 원래 SHA-256 기록이 없습니다. 다시 슬라이싱해 주세요.')
                path = self._artifact_location(job, 'sliced_three_mf')
                try:
                    content = _read_regular(path, _MAX_ARTIFACT_BYTES)
                except OSError as exc:
                    raise ArtifactIntegrityError(_INTEGRITY_MESSAGE) from exc
                if not content or hashlib.sha256(content).hexdigest() != expected_hash:
                    raise ArtifactIntegrityError(_INTEGRITY_MESSAGE)
                snapshots['sliced_three_mf'] = path, content
        return {kind: snapshots[kind] for kind in kinds}

    def read_artifact(self, job_id, kind):
        with self.lock:
            job = self._read(job_id)
            if kind not in job['_files']:
                raise KeyError('등록된 파일이 없습니다.')
            return self._snapshots(job, [kind])[kind]

    def artifact_path(self, job_id, kind):
        return self.read_artifact(job_id, kind)[0]

    def bundle(self, job_id):
        with self.lock:
            job = self._read(job_id)
            if not job['artifacts']:
                raise KeyError('내려받을 생성 파일이 없습니다.')
            snapshots = self._snapshots(job, list(job['_files']))
            public_record = _json_bytes(self._public(job))
        stream = io.BytesIO()
        with zipfile.ZipFile(stream, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
            for path, content in snapshots.values():
                archive.writestr(path.name, content)
            archive.writestr('job.json', public_record)
        return stream.getvalue()

    def record_outcome(self, job_id, result, notes):
        if result not in ('success', 'failure', 'not_tested') or not isinstance(notes, str) or len(notes) > 4000:
            raise ValueError('출력 결과와 4,000자 이내의 메모가 필요합니다.')
        with self.lock:
            job = self._read(job_id)
            report = {'result': result, 'notes': notes, 'source': 'user_reported', 'recorded_at': now_iso()}
            job['user_outcome'] = report
            job['events'].append({'at': now_iso(), 'type': 'user_reported_outcome', 'message': result, 'report': report})
            self._write(job)
            return self._public(job)

    def begin_slice(self, job_id):
        with self.lock:
            job = self._read(job_id)
            if job['status'] != 'geometry_validated':
                raise ValueError('형상 검증이 완료된 모델이 필요합니다.')
            self._clear_slice(job)
            job['latest_slice'] = {'recorded_at': now_iso(), 'phase': 'running', 'plan': None, 'execution': None}
            job['events'].append({'at': now_iso(), 'type': 'slicer_started', 'message': '새 슬라이싱을 준비합니다. 프린터 실행은 수행하지 않았습니다.'})
            self._write(job)
            return self._public(job)

    def record_slice(self, job_id, plan, execution):
        with self.lock:
            job = self._read(job_id)
            self._clear_slice(job)
            job['latest_slice'] = {'recorded_at': now_iso(), 'phase': 'finished',
                                   'plan': copy.deepcopy(plan), 'execution': copy.deepcopy(execution)}
            integrity_error = None
            try:
                if plan.get('kind') == 'studio_project' and plan.get('project_prepared') is True:
                    derivative = plan.get('project_receipt')
                    expected_hash = plan.get('project_sha256')
                    if (not isinstance(derivative, dict) or not isinstance(expected_hash, str)
                            or re.fullmatch(r'[a-f0-9]{64}', expected_hash) is None
                            or derivative.get('project_sha256') != expected_hash
                            or type(derivative.get('project_bytes')) is not int):
                        raise ValueError('Missing prepared project receipt')
                    self._record_slice_artifact(job, 'prepared_three_mf', plan.get('project_path'),
                                                expected_hash, derivative['project_bytes'])
                if execution and execution['status'] in ('sliced', 'needs_review'):
                    self._record_slice_artifact(job, 'sliced_three_mf', execution.get('output_path'),
                                                execution.get('output_sha256', _ABSENT_HASH))
            except (OSError, ValueError, TypeError):
                integrity_error = ArtifactIntegrityError(_INTEGRITY_MESSAGE)
                self._clear_slice(job)
                execution = {'status': 'failed', 'output_path': None, 'print_status': 'not_started',
                             'checks': [{'name': 'stored_artifact', 'passed': False, 'detail': _INTEGRITY_MESSAGE}]}
                job['latest_slice']['execution'] = execution
            status = execution['status'] if execution else ('prepared' if plan.get('ready') or plan.get('project_prepared') else 'blocked')
            job['events'].append({'at': now_iso(), 'type': 'slicer_' + status, 'message': '프린터 실행은 수행하지 않았습니다.'})
            self._write(job)
            if integrity_error is not None:
                raise integrity_error
            return self._public(job)

    def _record_slice_artifact(self, job, kind, filename, expected_hash=_ABSENT_HASH, expected_bytes=None):
        if not filename:
            raise ValueError('Missing prepared or sliced output')
        path = Path(filename)
        relative = path.absolute().relative_to(self.directory(job['id'])).as_posix()
        job['_files'][kind] = relative
        self._artifact_location(job, kind)
        content = _read_regular(path, _MAX_ARTIFACT_BYTES, expected_size=expected_bytes)
        if not content:
            raise ValueError('Empty prepared or sliced output')
        receipt = _receipt(relative, content)
        if expected_hash is not _ABSENT_HASH and expected_hash != receipt['sha256']:
            raise ValueError('Artifact changed after preparation or execution read-back')
        if '_artifact_receipts' in job:
            job['_artifact_receipts'][kind] = receipt
        else:
            key = '_prepared_artifact_receipt' if kind == 'prepared_three_mf' else '_slice_artifact_receipt'
            job[key] = receipt
        job['artifacts'][kind] = f"/api/jobs/{job['id']}/files/{kind}"
