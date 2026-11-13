"""Atomic, revision-aware storage for local filament inputs and unfinished drafts.

Snapshots preserve input evidence only. They never persist a current review,
execute preset content, or treat a saved workspace as a validated configuration.
"""
from contextlib import closing
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import re
import sqlite3
import uuid


MAX_WORKSPACE_BYTES = 8 * 1024 * 1024
MAX_ORIGINAL_BYTES = 2 * 1024 * 1024
MAX_SAFE_INTEGER = 2**53 - 1
_SNAPSHOT_FIELDS = {'schema_version', 'documents', 'target_index', 'profile_text', 'setup'}
_DOCUMENT_FIELDS = {'filename', 'profile', 'draft_text'}
_SETUP_FIELDS = {
    'printer_model', 'printer_preset', 'nozzle_diameter', 'plate_type',
    'extruder', 'feed_mode', 'material_id', 'material_identity_status',
}


class WorkspaceConflict(ValueError):
    """The saved revision changed since the caller last opened it."""


def _json_text(value):
    """Reject values that cannot survive the browser's JSON representation."""
    pending = [(value, 0)]
    while pending:
        item, depth = pending.pop()
        if depth > 64:
            raise ValueError('작업 JSON 중첩은 최대 64단계까지 저장할 수 있습니다.')
        if isinstance(item, dict):
            if any(not isinstance(key, str) for key in item):
                raise ValueError('작업 JSON 객체의 키는 문자열이어야 합니다.')
            pending.extend((child, depth + 1) for child in item.values())
        elif isinstance(item, list):
            pending.extend((child, depth + 1) for child in item)
        elif isinstance(item, bool) or item is None or isinstance(item, str):
            continue
        elif isinstance(item, int):
            if abs(item) > MAX_SAFE_INTEGER:
                raise ValueError('브라우저에서 정확히 보존할 수 없는 큰 정수는 저장할 수 없습니다.')
        elif isinstance(item, float):
            if not math.isfinite(item) or (item.is_integer() and abs(item) > MAX_SAFE_INTEGER):
                raise ValueError('유한하고 브라우저에서 보존할 수 있는 숫자가 필요합니다.')
        else:
            raise ValueError('작업에는 JSON 객체·배열·문자열·숫자·boolean·null만 저장할 수 있습니다.')
    try:
        text = json.dumps(value, ensure_ascii=False, separators=(',', ':'), allow_nan=False)
        text.encode('utf-8')
        return text
    except (TypeError, ValueError, OverflowError, RecursionError, UnicodeError) as exc:
        raise ValueError('올바른 문자열과 유한한 숫자로 구성된 작업 JSON이 필요합니다.') from exc


def _snapshot_text(snapshot):
    if not isinstance(snapshot, dict) or set(snapshot) != _SNAPSHOT_FIELDS:
        raise ValueError('작업에는 schema_version, documents, target_index, profile_text, setup만 필요합니다.')
    if type(snapshot['schema_version']) is not int or snapshot['schema_version'] != 1:
        raise ValueError('지원하는 작업 형식은 schema_version 1입니다.')
    documents = snapshot['documents']
    if not isinstance(documents, list) or len(documents) > 64:
        raise ValueError('한 작업에는 필라멘트 문서를 최대 64개까지 저장할 수 있습니다.')
    target = snapshot['target_index']
    if type(target) is not int or not 0 <= target < max(1, len(documents)):
        raise ValueError('선택한 문서 번호가 작업의 파일 모음 범위 안에 있어야 합니다.')
    if not isinstance(snapshot['profile_text'], str) or (documents and snapshot['profile_text'] != ''):
        raise ValueError('profile_text는 문자열이며, 파일 모음이 있으면 빈 문자열이어야 합니다.')
    setup = snapshot['setup']
    if not isinstance(setup, dict) or set(setup) != _SETUP_FIELDS:
        raise ValueError('프린터와 재료의 사용 조건 8개를 모두 문자열로 저장해야 합니다.')
    if any(not isinstance(value, str) or len(value) > 512 for value in setup.values()):
        raise ValueError('각 사용 조건은 512자 이내의 문자열이어야 합니다.')
    if setup['material_identity_status'] not in {'unknown', 'ambiguous', 'exact'}:
        raise ValueError('제품 식별 상태는 unknown, ambiguous, exact 중 하나여야 합니다.')
    originals = []
    for document in documents:
        if not isinstance(document, dict) or set(document) != _DOCUMENT_FIELDS:
            raise ValueError('각 작업 문서에는 filename, profile, draft_text만 필요합니다.')
        filename = document['filename']
        if not isinstance(filename, str) or not filename.strip() or len(filename) > 240:
            raise ValueError('파일 이름은 비어 있지 않은 240자 이내의 문자열이어야 합니다.')
        if not isinstance(document['profile'], dict) or not isinstance(document['draft_text'], str):
            raise ValueError('가져온 원본은 JSON 객체, 편집 내용은 문자열이어야 합니다.')
        originals.append({'filename': filename, 'profile': document['profile']})
    encoded = _json_text(snapshot)
    if len(encoded.encode('utf-8')) > MAX_WORKSPACE_BYTES:
        raise ValueError('원본과 편집 내용을 합친 작업은 8 MiB 이하여야 합니다.')
    if len(_json_text(originals).encode('utf-8')) > MAX_ORIGINAL_BYTES:
        raise ValueError('가져온 원본 문서의 합계는 2 MiB 이하여야 합니다.')
    return encoded


def _title(value):
    if not isinstance(value, str) or not 1 <= len(value.strip()) <= 120:
        raise ValueError('작업 이름은 1자 이상 120자 이하로 입력하세요.')
    try:
        value.encode('utf-8')
    except UnicodeError as exc:
        raise ValueError('작업 이름에 올바른 문자열이 필요합니다.') from exc
    return value.strip()


def _workspace_id(value):
    if not isinstance(value, str) or not re.fullmatch(r'[a-f0-9]{32}', value):
        raise ValueError('올바른 필라멘트 작업 ID가 필요합니다.')
    return value


def _revision(value):
    if type(value) is not int or not 1 <= value < MAX_SAFE_INTEGER:
        raise ValueError('마지막으로 열었던 작업의 올바른 revision이 필요합니다.')
    return value


def _now():
    return datetime.now(timezone.utc).isoformat()


def _record(row):
    result = dict(row)
    result['snapshot'] = json.loads(result.pop('snapshot_json'))
    result.pop('document_count')
    return result


class ProfileWorkspaceStore:
    """One SQLite row per snapshot; conditional writes protect independent tabs."""

    def __init__(self, root: Path):
        self.root = Path(root).expanduser().resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.db_path = self.root / 'profile-workspaces.sqlite3'
        with closing(self._connect()) as db, db:
            db.execute('''CREATE TABLE IF NOT EXISTS profile_workspaces (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                revision INTEGER NOT NULL CHECK (revision >= 1),
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                document_count INTEGER NOT NULL,
                snapshot_json TEXT NOT NULL
            )''')

    def _connect(self):
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        return connection

    @staticmethod
    def _read(db, workspace_id):
        row = db.execute('SELECT * FROM profile_workspaces WHERE id = ?', (workspace_id,)).fetchone()
        if row is None:
            raise KeyError('필라멘트 작업을 찾을 수 없습니다.')
        return row

    @classmethod
    def _require_changed(cls, db, cursor, workspace_id):
        if cursor.rowcount == 0:
            cls._read(db, workspace_id)
            raise WorkspaceConflict('다른 창에서 작업을 변경했습니다. 현재 편집 내용을 복사본으로 저장하거나 최신 작업을 다시 열어 주세요.')

    def create(self, title, snapshot):
        title, snapshot_json = _title(title), _snapshot_text(snapshot)
        workspace_id, now = uuid.uuid4().hex, _now()
        with closing(self._connect()) as db, db:
            db.execute('''INSERT INTO profile_workspaces
                (id, title, revision, created_at, updated_at, document_count, snapshot_json)
                VALUES (?, ?, 1, ?, ?, ?, ?)''',
                (workspace_id, title, now, now, len(snapshot['documents']), snapshot_json))
            return _record(self._read(db, workspace_id))

    def get(self, workspace_id):
        workspace_id = _workspace_id(workspace_id)
        with closing(self._connect()) as db:
            return _record(self._read(db, workspace_id))

    def list_workspaces(self):
        with closing(self._connect()) as db:
            rows = db.execute('''SELECT id, title, revision, created_at, updated_at, document_count
                FROM profile_workspaces ORDER BY updated_at DESC, id DESC''').fetchall()
            return [dict(row) for row in rows]

    def update(self, workspace_id, title, snapshot, expected_revision):
        workspace_id, expected_revision = _workspace_id(workspace_id), _revision(expected_revision)
        title, snapshot_json = _title(title), _snapshot_text(snapshot)
        with closing(self._connect()) as db, db:
            # Acquire the write lock before computing the timestamp. The single
            # conditional update keeps metadata and the exact snapshot together.
            db.execute('BEGIN IMMEDIATE')
            cursor = db.execute('''UPDATE profile_workspaces SET
                title = ?, revision = revision + 1, updated_at = ?, document_count = ?, snapshot_json = ?
                WHERE id = ? AND revision = ?''',
                (title, _now(), len(snapshot['documents']), snapshot_json, workspace_id, expected_revision))
            self._require_changed(db, cursor, workspace_id)
            return _record(self._read(db, workspace_id))

    def delete(self, workspace_id, expected_revision):
        workspace_id, expected_revision = _workspace_id(workspace_id), _revision(expected_revision)
        with closing(self._connect()) as db, db:
            db.execute('BEGIN IMMEDIATE')
            cursor = db.execute('DELETE FROM profile_workspaces WHERE id = ? AND revision = ?',
                                (workspace_id, expected_revision))
            self._require_changed(db, cursor, workspace_id)
            return {'deleted': True, 'id': workspace_id}
