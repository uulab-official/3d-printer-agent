"""Lightweight local runtime selection, ownership, and installation diagnostics.

Importing this module does not import CAD or web dependencies. A broken native
installation must still be able to produce a useful doctor report.
"""
from contextlib import closing
import errno
import importlib
import importlib.metadata
import os
from pathlib import Path
import platform
import re
import stat
import sys
import tempfile
import time

from . import __version__


def _recognizable_legacy(root: Path) -> bool:
    if not root.is_dir():
        return False
    if any((root / name).is_file() for name in ('history.sqlite3', 'profile-workspaces.sqlite3')):
        return True
    jobs = root / 'jobs'
    if jobs.is_dir():
        return any(re.fullmatch(r'[a-f0-9]{32}', entry.name) and entry.is_dir()
                   and (entry / 'job.json').is_file() for entry in jobs.iterdir())
    return False


def _user_data_directory() -> Path:
    system = platform.system()
    if system == 'Darwin':
        return Path.home() / 'Library' / 'Application Support' / '3DPrinterAgent'
    if system == 'Windows':
        candidate = os.getenv('LOCALAPPDATA', '')
        base = Path(candidate) if candidate and Path(candidate).is_absolute() else Path.home() / 'AppData' / 'Local'
        return base / '3DPrinterAgent'
    candidate = os.getenv('XDG_DATA_HOME', '')
    base = Path(candidate) if candidate and Path(candidate).is_absolute() else Path.home() / '.local' / 'share'
    return base / '3d-printer-agent'


def resolve_data_directory(explicit: Path | None = None) -> dict:
    """Resolve storage without creating, moving, opening, or rewriting its data.

    Existing recognizable ``./data`` remains a cwd-dependent compatibility path.
    Empty/unrelated directories do not hide the stable per-user default.
    """
    configured = os.getenv('PPA_DATA_DIR', '')
    if explicit is not None:
        path, source = Path(explicit), 'argument'
    elif configured.strip():
        path, source = Path(configured), 'environment'
    else:
        legacy = Path.cwd() / 'data'
        if _recognizable_legacy(legacy):
            path, source = legacy, 'legacy'
        else:
            path, source = _user_data_directory(), 'user_default'
    return {'path': str(path.expanduser().resolve()), 'source': source, 'legacy': source == 'legacy'}


class DataDirectoryInUse(RuntimeError):
    """Another live process owns the selected application's data directory."""


class DataDirectoryLease:
    """A nonblocking OS lease, held until context exit or process termination.

    The lock file is intentionally stable and is never unlinked on release.
    Lock-file presence is not ownership: the operating system owns that fact.
    """
    def __init__(self, root: Path):
        self.root = Path(root).expanduser().resolve()
        self._stream = None

    @staticmethod
    def _lock(stream):
        stream.seek(0)
        if os.name == 'nt':
            import msvcrt
            msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
        elif os.name == 'posix':
            import fcntl
            fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        else:
            raise RuntimeError('이 운영체제에서 데이터 디렉터리의 독점 사용을 확인할 수 없습니다.')

    @staticmethod
    def _unlock(stream):
        stream.seek(0)
        if os.name == 'nt':
            import msvcrt
            msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl
            fcntl.flock(stream.fileno(), fcntl.LOCK_UN)

    def __enter__(self):
        if self._stream is not None:
            raise RuntimeError('이미 사용 중인 데이터 디렉터리 lease를 중복 획득할 수 없습니다.')
        self.root.mkdir(parents=True, exist_ok=True)
        lock_path = self.root / '.printer-agent.lock'
        if lock_path.is_symlink():
            raise ValueError('데이터 디렉터리의 잠금 파일은 심볼릭 링크일 수 없습니다.')
        flags = os.O_RDWR | os.O_CREAT | getattr(os, 'O_CLOEXEC', 0) | getattr(os, 'O_NOFOLLOW', 0)
        descriptor = os.open(lock_path, flags, 0o600)
        try:
            if not stat.S_ISREG(os.fstat(descriptor).st_mode):
                raise ValueError('데이터 디렉터리의 잠금 경로는 일반 파일이어야 합니다.')
            stream = os.fdopen(descriptor, 'r+b', buffering=0)
        except BaseException:
            os.close(descriptor)
            raise
        try:
            try:
                self._lock(stream)
            except OSError as exc:
                if exc.errno in {errno.EACCES, errno.EAGAIN, errno.EWOULDBLOCK, errno.EDEADLK}:
                    raise DataDirectoryInUse(
                        f'이 데이터 디렉터리를 다른 3D Printer Agent가 사용 중입니다: {self.root}. '
                        '기존 앱을 종료하거나 --data-dir로 다른 폴더를 선택하세요.'
                    ) from exc
                raise
            # Windows byte-range locks can cover the first byte beyond EOF. Only
            # the successful owner initializes a new file; rejected owners never
            # rewrite its bytes or any application data.
            if os.fstat(stream.fileno()).st_size == 0:
                stream.write(b'\0')
            self._stream = stream
            return self
        except BaseException:
            stream.close()
            raise

    def __exit__(self, exc_type, exc_value, traceback):
        stream, self._stream = self._stream, None
        if stream is not None:
            try:
                self._unlock(stream)
            finally:
                stream.close()
        return False


def _message(exc: Exception) -> str:
    message = f'{type(exc).__name__}: {exc}'
    secret = os.getenv('PPA_LLM_API_KEY', '')
    if secret:
        message = message.replace(secret, '[redacted]')
    return message[:700]


def _check_storage(path: Path) -> str:
    parent = path
    while not parent.exists() and parent != parent.parent:
        parent = parent.parent
    if not parent.is_dir():
        raise ValueError('데이터 경로 또는 상위 경로가 폴더가 아닙니다. --data-dir에 폴더 경로를 지정하세요.')
    # Probe only our newly created temporary child, never any user database or
    # job. A missing selected directory stays missing after diagnosis.
    with tempfile.TemporaryDirectory(prefix='.printer-agent-check-', dir=parent) as temporary:
        probe = Path(temporary) / 'write-read-check'
        probe.write_bytes(b'printer-agent-storage-check')
        if probe.read_bytes() != b'printer-agent-storage-check':
            raise OSError('데이터 위치의 쓰기·읽기 결과가 일치하지 않습니다.')
    return ('기존 데이터 폴더의 임시 파일 쓰기·읽기를 확인했습니다.' if path.is_dir()
            else '상위 폴더에서 임시 파일 쓰기·읽기를 확인했습니다. 데이터 폴더는 앱 시작 시 생성합니다.')


def _check_database(path: Path, table: str, columns: set[str], *, derived: bool) -> dict:
    """Read-only integrity/schema observation, never an implicit repair."""
    if not path.exists():
        return {'passed': True, 'state': 'not_initialized', 'repairable': False,
                'detail': '아직 저장 파일이 없습니다. 앱 시작 시 초기화합니다.'}
    if not path.is_file():
        return {'passed': False, 'state': 'invalid_path', 'repairable': False,
                'detail': '데이터베이스 경로가 일반 파일이 아닙니다. 기존 경로를 보존하고 위치를 확인하세요.'}
    try:
        sqlite3 = importlib.import_module('sqlite3')
    except Exception as exc:
        return {'passed': False, 'state': 'not_checked', 'repairable': False,
                'detail': 'SQLite 구성 요소를 불러올 수 없어 저장소를 확인하지 못했습니다. ' + _message(exc)}
    repair_note = (' 앱을 다시 시작하면 원본 작업 기록을 기준으로 인덱스를 복구하며 손상 파일은 보존합니다.'
                   if derived else ' 필라멘트 작업의 원본 저장소입니다. 파일을 보존하고 확인된 백업으로 복구하세요.')
    try:
        with closing(sqlite3.connect(path.resolve().as_uri() + '?mode=ro', uri=True, timeout=0.5)) as connection:
            connection.execute('PRAGMA query_only = ON')
            deadline = time.monotonic() + 2
            connection.set_progress_handler(lambda: int(time.monotonic() > deadline), 10000)
            if connection.execute('PRAGMA quick_check(1)').fetchall() != [('ok',)]:
                return {'passed': False, 'state': 'corrupt', 'repairable': derived,
                        'detail': 'SQLite 무결성 검사에서 문제를 발견했습니다.' + repair_note}
            tables = {row[0] for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT GLOB 'sqlite_*'")}
            if not tables:
                return {'passed': True, 'state': 'uninitialized', 'repairable': False,
                        'detail': 'SQLite 파일에 사용자 테이블이 없습니다. 앱 시작 시 저장 구조를 초기화합니다.'}
            if table not in tables or not columns.issubset(
                {row[1] for row in connection.execute(f'PRAGMA table_info({table})')}
            ):
                return {'passed': False, 'state': 'schema_unrecognized', 'repairable': False,
                        'detail': '예상하는 저장 테이블 또는 열을 확인할 수 없습니다. '
                                  '자동 복구가 가능한 구조로 확인되지 않았습니다. 기존 파일을 보존하고 '
                                  '호환되는 앱 버전 또는 확인된 백업을 검토하세요.'}
            return {'passed': True, 'state': 'checked', 'repairable': False,
                    'detail': '읽기 전용 SQLite 무결성 검사와 필요한 저장 열을 확인했습니다.'}
    except sqlite3.Error as exc:
        code = getattr(exc, 'sqlite_errorcode', None)
        base_code = code & 0xff if isinstance(code, int) else None
        if base_code in {sqlite3.SQLITE_BUSY, sqlite3.SQLITE_LOCKED, sqlite3.SQLITE_INTERRUPT}:
            return {'passed': False, 'state': 'not_checked', 'repairable': False,
                    'detail': '사용 중이거나 진단 제한시간을 넘겨 저장소를 확인하지 못했습니다. 작업이 끝난 뒤 다시 확인하세요. 손상으로 판정하지 않았습니다.'}
        if base_code in {sqlite3.SQLITE_CORRUPT, sqlite3.SQLITE_NOTADB}:
            return {'passed': False, 'state': 'corrupt', 'repairable': derived,
                    'detail': 'SQLite 저장 파일을 정상적으로 읽을 수 없습니다.' + repair_note}
        return {'passed': False, 'state': 'not_checked', 'repairable': False,
                'detail': '읽기 전용 저장소 확인에 실패했습니다. ' + _message(exc)}
    except (OSError, ValueError) as exc:
        return {'passed': False, 'state': 'not_checked', 'repairable': False,
                'detail': '저장 파일의 위치와 읽기 권한을 확인하세요. ' + _message(exc)}


def diagnose(data_dir: Path | None = None, *, probe_slicer: bool = False) -> dict:
    """Check required components independently; optional services never gate CAD."""
    report = {
        'version': __version__, 'python': platform.python_version(),
        'platform': {'system': platform.system(), 'release': platform.release(), 'machine': platform.machine()},
        'storage': None, 'checks': [], 'cadquery': None,
        'provider': {'configured': False, 'status': 'unavailable'},
        'slicer': {'available': False, 'version': None, 'printer_status': 'not_checked', 'diagnostics': []},
    }

    def record(check_id, passed, detail, *, version=None):
        check = {'id': check_id, 'required': True, 'passed': bool(passed), 'detail': detail}
        if version is not None:
            check['version'] = str(version)
        report['checks'].append(check)

    supported_python = (3, 11) <= sys.version_info[:2] < (3, 14)
    record('python', supported_python, 'Python 3.11–3.13 범위가 필요하며 설치 검증 기준은 Python 3.12입니다.')
    for name in ('cadquery', 'fastapi', 'uvicorn', 'pydantic', 'httpx', 'sqlite3'):
        try:
            module = importlib.import_module(name)
            version = getattr(module, 'sqlite_version', None) if name == 'sqlite3' else getattr(module, '__version__', None)
            if version is None:
                try:
                    version = importlib.metadata.version(name)
                except importlib.metadata.PackageNotFoundError:
                    pass
            record(name, True, '구성 요소를 불러왔습니다.', version=version)
            if name == 'cadquery':
                report['cadquery'] = version
        except Exception as exc:
            record(name, False, _message(exc) + ' 설치 안내에 따라 같은 Python 환경의 의존성을 확인하세요.')

    try:
        static = Path(__file__).resolve().parent / 'static'
        for name in ('index.html', 'style.css', 'app.js'):
            path = static / name
            if not path.is_file() or not path.read_bytes():
                raise FileNotFoundError(f'앱 화면 파일이 없거나 비어 있습니다: {name}')
        record('static_assets', True, '설치된 앱의 HTML·CSS·JavaScript 파일을 확인했습니다.')
    except Exception as exc:
        record('static_assets', False, _message(exc))

    try:
        report['storage'] = resolve_data_directory(data_dir)
        detail = _check_storage(Path(report['storage']['path']))
        record('storage', True, detail)
    except Exception as exc:
        record('storage', False, _message(exc))

    if report['storage'] is not None:
        root = Path(report['storage']['path'])
        for check_id, filename, table, columns, derived in (
            ('history_database', 'history.sqlite3', 'jobs',
             {'id', 'created_at', 'title', 'template', 'status', 'user_outcome'}, True),
            ('workspace_database', 'profile-workspaces.sqlite3', 'profile_workspaces',
             {'id', 'title', 'revision', 'created_at', 'updated_at', 'document_count', 'snapshot_json'}, False),
        ):
            result = _check_database(root / filename, table, columns, derived=derived)
            report['checks'].append({'id': check_id, 'required': True, **result})

    try:
        report['provider'] = importlib.import_module('.planner', __package__).provider_config()
    except Exception as exc:
        report['provider']['diagnostic'] = _message(exc)
    try:
        slicer = importlib.import_module('.slicer', __package__)
        report['slicer'] = slicer.probe_environment() if probe_slicer else slicer.detect_environment()
    except Exception as exc:
        report['slicer']['diagnostics'].append(_message(exc))
    report['ready'] = all(check['passed'] for check in report['checks'] if check['required'])
    return report
