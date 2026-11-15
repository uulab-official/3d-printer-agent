"""Authoritative named Studio inputs and a bounded recorded-metadata catalog.

Only named create/update/open verifies archives. Catalog labels are recorded
inputs and never establish current compatibility or print readiness.
"""
from contextlib import closing
import json
from pathlib import Path
import re
import sqlite3
import uuid

from .runtime import _check_database, _DATABASES, StorageCompatibilityError
from .storage import _parse_json, _read_regular, _valid_timestamp, now_iso
from .studio_project import MAX_ARCHIVE_BYTES
from .studio_revisions import _MAX_REVISION_BYTES
from .studio_settings import _FIELDS, _RECORD_KEYS, _number, verify_revision, settings_editor
from .studio_sources import _MAX_RECEIPT_BYTES
from .workspaces import _title, _revision, _workspace_id, MAX_SAFE_INTEGER, WorkspaceConflict


MAX_SNAPSHOT_BYTES = 16 * 1024
_SNAPSHOT_FIELDS = {'schema_version', 'source_id', 'settings_revision_id', 'source_sha256',
                    'settings_sha256', 'effective_settings_sha256', 'draft_values'}
_DRAFT_FIELDS = {field[0] for field in _FIELDS}
_MESSAGE = '보관한 Studio 작업 또는 연결된 원본·설정 변경 기록을 읽을 수 없습니다. 확인된 백업을 복구하거나 새 작업으로 저장하세요.'
_SCHEMA = '''CREATE TABLE studio_workspaces (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    revision INTEGER NOT NULL CHECK(revision >= 1),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    snapshot_json TEXT NOT NULL
)'''
# Oversized stored JSON never becomes a Python string. CAST ensures the budget
# is UTF-8 bytes rather than SQLite's Unicode character length.
_ROW_COLUMNS = '''
    CASE WHEN typeof(id) = 'text' AND length(CAST(id AS BLOB)) = 32 THEN id ELSE NULL END AS id,
    CASE WHEN typeof(title) = 'text' AND length(CAST(title AS BLOB)) <= 480 THEN title ELSE NULL END AS title,
    CASE WHEN typeof(revision) = 'integer' THEN revision ELSE NULL END AS revision,
    CASE WHEN typeof(created_at) = 'text' AND length(CAST(created_at AS BLOB)) <= 320 THEN created_at ELSE NULL END AS created_at,
    CASE WHEN typeof(updated_at) = 'text' AND length(CAST(updated_at AS BLOB)) <= 320 THEN updated_at ELSE NULL END AS updated_at,
    CASE WHEN typeof(snapshot_json) = 'text' AND length(CAST(snapshot_json AS BLOB)) <= 16384
         THEN snapshot_json ELSE NULL END AS snapshot_json'''


class StudioWorkspaceIntegrityError(ValueError):
    """A persisted named input or its immutable reference is unreadable."""


def _sha(value):
    return isinstance(value, str) and re.fullmatch(r'[a-f0-9]{64}', value) is not None


def _snapshot_text(value):
    if not isinstance(value, dict) or set(value) != _SNAPSHOT_FIELDS:
        raise ValueError('정확한 Studio 작업 입력 항목이 필요합니다.')
    if type(value['schema_version']) is not int or value['schema_version'] != 1:
        raise ValueError('Studio 작업 형식은 schema_version 1이어야 합니다.')
    _workspace_id(value['source_id'])
    if value['settings_revision_id'] is not None:
        _workspace_id(value['settings_revision_id'])
    if not all(_sha(value[key]) for key in ('source_sha256', 'settings_sha256', 'effective_settings_sha256')):
        raise ValueError('원본과 설정의 SHA-256이 필요합니다.')
    draft = value['draft_values']
    if draft is not None and (not isinstance(draft, dict) or set(draft) != _DRAFT_FIELDS
                             or any(not isinstance(v, str) or len(v) > 512 for v in draft.values())):
        raise ValueError('여섯 편집 항목을 각각 512자 이하 문자열로 저장하세요.')
    try:
        raw = json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(',', ':'))
        if len(raw.encode('utf-8')) > MAX_SNAPSHOT_BYTES:
            raise ValueError('Studio 작업 입력은 16 KiB 이하여야 합니다.')
    except (TypeError, ValueError, UnicodeError, RecursionError) as exc:
        raise ValueError('Studio 작업에는 크기 제한 안의 올바른 문자열이 필요합니다.') from exc
    return raw


def _record(row):
    try:
        result = dict(row)
        _workspace_id(result['id'])
        if _title(result['title']) != result['title']:
            raise ValueError('Untrimmed title')
        _revision(result['revision'])
        if not all(_valid_timestamp(result[key]) for key in ('created_at', 'updated_at')):
            raise ValueError('Invalid timestamps')
        raw = result.pop('snapshot_json')
        if not isinstance(raw, str) or len(raw.encode('utf-8')) > MAX_SNAPSHOT_BYTES:
            raise ValueError('Invalid snapshot size')
        result['snapshot'] = _parse_json(raw)
        _snapshot_text(result['snapshot'])
        return result
    except (ValueError, KeyError, TypeError, UnicodeError, RecursionError, OverflowError) as exc:
        raise StudioWorkspaceIntegrityError(_MESSAGE) from exc


def _metadata_json(path, maximum):
    value = _parse_json(_read_regular(path, maximum))
    # Bounded receipt bytes may still encode escaped surrogate strings or a
    # finite-looking exponent that JSON decodes to infinity. Reject both before
    # any metadata is placed in a serializable catalog item.
    json.dumps(value, ensure_ascii=False, allow_nan=False).encode('utf-8')
    return value


def _short(value, maximum=160):
    return value[:maximum] if isinstance(value, str) else ''


def _summary(summary):
    if not isinstance(summary, dict):
        raise ValueError('Invalid recorded summary')
    keys = ('printer_model', 'printer_preset', 'nozzle_diameter', 'plate_type',
            'filament_name', 'filament_type', 'process_preset')
    if any(key not in summary for key in keys):
        raise ValueError('Invalid recorded setup')
    def label(value):
        if isinstance(value, str):
            return _short(value, 100)
        # Unsupported, retained inspections can legitimately contain numbers,
        # multiple-filament arrays or other JSON values. They are recorded
        # metadata too; describing them does not claim editing support.
        return json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(',', ':'))[:100]
    return ' · '.join(label(summary[key]) for key in keys if summary[key] is not None)[:900]


def _item(identifier, kind):
    return {'id': identifier, 'kind': kind, 'title': f'읽을 수 없는 기록 {identifier[:8]}',
            'created_at': None, 'updated_at': None, 'source_id': None,
            'settings_revision_id': None, 'revision': None, 'has_draft': False,
            'metadata_status': 'unreadable', 'detail': '보관한 메타데이터를 읽을 수 없습니다. 원본 파일을 보존하고 확인하세요.',
            'summary': ''}


class StudioWorkspaceStore:
    def __init__(self, root: Path, sources, revisions):
        self.root = Path(root).expanduser().resolve()
        if sources.root != self.root or revisions.root != self.root:
            raise ValueError('Studio 작업과 원본·설정 변경 기록은 같은 데이터 폴더에 있어야 합니다.')
        self.sources, self.revisions = sources, revisions
        self.root.mkdir(parents=True, exist_ok=True)
        self.db_path = self.root / 'studio-workspaces.sqlite3'
        columns = next(entry[3] for entry in _DATABASES if entry[0] == 'studio_workspace_database')
        result = _check_database(self.db_path, 'studio_workspaces', columns, derived=False)
        if not result['passed']:
            raise StorageCompatibilityError(result['detail'])
        if result['state'] == 'not_initialized':
            with closing(self._connect()) as db, db:
                db.execute(_SCHEMA)

    def _connect(self):
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        return connection

    @staticmethod
    def _read(db, workspace_id):
        try:
            row = db.execute(f'SELECT {_ROW_COLUMNS} FROM studio_workspaces WHERE id = ?', (workspace_id,)).fetchone()
        except sqlite3.Error as exc:
            raise StudioWorkspaceIntegrityError(_MESSAGE) from exc
        if row is None:
            raise KeyError('Studio 작업을 찾을 수 없습니다.')
        return _record(row)

    def _verified(self, snapshot):
        original, _ = self.sources.read(snapshot['source_id'])
        if (original['source']['sha256'] != snapshot['source_sha256']
                or original['settings_sha256'] != snapshot['settings_sha256']):
            raise ValueError('Studio 작업과 원본 설정의 해시가 다릅니다.')
        envelope = None
        effective = original
        if snapshot['settings_revision_id'] is not None:
            envelope = self.revisions.get(snapshot['settings_revision_id'])
            effective, _ = verify_revision(original, envelope['revision'], source_id=snapshot['source_id'])
        if effective['settings_sha256'] != snapshot['effective_settings_sha256']:
            raise ValueError('Studio 작업과 변경 설정의 해시가 다릅니다.')
        editor = {**settings_editor(original), 'source_id': snapshot['source_id']}
        return self.sources._public(original, snapshot['source_id']), envelope, editor

    def create(self, title, snapshot):
        title, raw = _title(title), _snapshot_text(snapshot)
        # A dangling reference submitted as new input is an invalid request.
        try:
            self._verified(snapshot)
        except KeyError as exc:
            raise ValueError('선택한 Studio 원본 또는 설정 변경 기록을 찾을 수 없습니다.') from exc
        identifier, now = uuid.uuid4().hex, now_iso()
        with closing(self._connect()) as db, db:
            db.execute('INSERT INTO studio_workspaces VALUES (?, ?, 1, ?, ?, ?)', (identifier, title, now, now, raw))
            return self._read(db, identifier)

    def get(self, workspace_id):
        identifier = _workspace_id(workspace_id)
        with closing(self._connect()) as db:
            record = self._read(db, identifier)
        try:
            source, revision, editor = self._verified(record['snapshot'])
        except (OSError, ValueError, KeyError, TypeError, RecursionError, OverflowError) as exc:
            raise StudioWorkspaceIntegrityError(_MESSAGE) from exc
        return {'workspace': record, 'source': source, 'settings_revision': revision, 'editor': editor}

    def update(self, workspace_id, title, snapshot, expected_revision):
        identifier, expected = _workspace_id(workspace_id), _revision(expected_revision)
        title, raw = _title(title), _snapshot_text(snapshot)
        if expected >= MAX_SAFE_INTEGER - 1:
            raise ValueError('작업 revision의 저장 가능한 범위를 넘었습니다.')
        try:
            self._verified(snapshot)
        except KeyError as exc:
            raise ValueError('선택한 Studio 원본 또는 설정 변경 기록을 찾을 수 없습니다.') from exc
        with closing(self._connect()) as db, db:
            db.execute('BEGIN IMMEDIATE')
            self._read(db, identifier)
            changed = db.execute('''UPDATE studio_workspaces SET title=?, revision=revision+1,
                updated_at=?, snapshot_json=? WHERE id=? AND revision=?''',
                                 (title, now_iso(), raw, identifier, expected))
            if changed.rowcount != 1:
                raise WorkspaceConflict('다른 창에서 Studio 작업을 변경했습니다. 복사본으로 저장하거나 최신 작업을 다시 열어 주세요.')
            return self._read(db, identifier)

    def delete(self, workspace_id, expected_revision):
        identifier, expected = _workspace_id(workspace_id), _revision(expected_revision)
        with closing(self._connect()) as db, db:
            db.execute('BEGIN IMMEDIATE')
            self._read(db, identifier)
            changed = db.execute('DELETE FROM studio_workspaces WHERE id=? AND revision=?', (identifier, expected))
            if changed.rowcount != 1:
                raise WorkspaceConflict('다른 창에서 Studio 작업을 변경했습니다. 최신 작업을 다시 열어 주세요.')

    def list_entries(self, kind, *, limit=25, before=None):
        if kind not in ('workspaces', 'sources', 'revisions'):
            raise ValueError('Studio 목록 종류는 workspaces, sources, revisions 중 하나여야 합니다.')
        if type(limit) is not int or not 1 <= limit <= 100:
            raise ValueError('목록 개수는 1–100 정수여야 합니다.')
        if before is not None:
            _workspace_id(before)
        if kind == 'workspaces':
            with closing(self._connect()) as db:
                rows = db.execute('''SELECT id FROM studio_workspaces
                    WHERE typeof(id) = 'text' AND length(CAST(id AS BLOB)) = 32
                    AND id NOT GLOB '*[^a-f0-9]*'
                    AND (? IS NULL OR id < ?) ORDER BY id DESC LIMIT ?''',
                                  (before, before, limit+1)).fetchall()
                identifiers = [row['id'] for row in rows]
                # Lookahead fetches only IDs, never off-page snapshots.
                items = [self._workspace_item(db, identifier) for identifier in identifiers[:limit]]
        else:
            store = self.sources if kind == 'sources' else self.revisions
            store._check_parent()
            directory = store.sources_dir if kind == 'sources' else store.revisions_dir
            identifiers = sorted((entry.name for entry in directory.iterdir()
                                  if re.fullmatch(r'[a-f0-9]{32}', entry.name)
                                  and (before is None or entry.name < before)), reverse=True)[:limit+1]
            items = [self._source_item(identifier) if kind == 'sources' else self._revision_item(identifier)
                     for identifier in identifiers[:limit]]
        return {'items': items, 'next_cursor': identifiers[limit-1] if len(identifiers) > limit else None}

    def _workspace_item(self, db, identifier):
        item = _item(identifier, 'workspace')
        try:
            record = self._read(db, identifier)
            snapshot = record['snapshot']
            item.update(title=record['title'], created_at=record['created_at'], updated_at=record['updated_at'],
                        source_id=snapshot['source_id'], settings_revision_id=snapshot['settings_revision_id'],
                        revision=record['revision'], has_draft=snapshot['draft_values'] is not None,
                        metadata_status='recorded', detail='저장한 입력 메타데이터입니다. 열 때 원본을 다시 확인합니다.',
                        summary=f"원본 {snapshot['source_id'][:8]} · 설정 변경 {snapshot['settings_revision_id'][:8] if snapshot['settings_revision_id'] else '원본 설정'}")
        except (OSError, ValueError, KeyError, TypeError, RecursionError, OverflowError):
            pass
        return item

    def _source_item(self, identifier):
        item = _item(identifier, 'source')
        try:
            record = _metadata_json(self.sources._directory(identifier) / 'receipt.json', _MAX_RECEIPT_BYTES)
            if (not isinstance(record, dict) or set(record) != {'schema_version','source_id','created_at','inspection'}
                    or type(record['schema_version']) is not int or record['schema_version'] != 1
                    or record['source_id'] != identifier or not _valid_timestamp(record['created_at'])):
                raise ValueError('Invalid source receipt')
            inspection = record['inspection']
            if not isinstance(inspection, dict) or set(inspection) != {'schema_version','source','producer','settings_sha256','summary','supported','issues','warnings'}:
                raise ValueError('Invalid source inspection')
            source = inspection['source']
            if (not isinstance(source, dict) or set(source) != {'filename','bytes','sha256'}
                    or not isinstance(source['filename'], str) or not source['filename'].strip()
                    or type(source['bytes']) is not int or not 0 < source['bytes'] <= MAX_ARCHIVE_BYTES
                    or not _sha(source['sha256']) or not _sha(inspection['settings_sha256'])
                    or type(inspection['schema_version']) is not int or inspection['schema_version'] != 1
                    or type(inspection['supported']) is not bool or not isinstance(inspection['producer'], dict)
                    or not isinstance(inspection['issues'], list) or not isinstance(inspection['warnings'], list)):
                raise ValueError('Invalid source metadata')
            text = _summary(inspection['summary'])
            item.update(title=_short(source['filename'], 240), created_at=record['created_at'], updated_at=record['created_at'],
                        source_id=identifier, metadata_status='recorded',
                        detail=('가져올 때 기록한 메타데이터입니다. 열 때 원본을 다시 확인합니다.' if inspection['supported']
                                else '지원 범위 밖으로 기록된 원본입니다. 열 때 현재 지원 범위와 원본을 다시 확인합니다.'),
                        summary=f'{identifier[:8]} · {record["created_at"]} · {text}'[:1200])
        except (OSError, ValueError, KeyError, TypeError, UnicodeError, RecursionError, OverflowError):
            pass
        return item

    def _revision_item(self, identifier):
        item = _item(identifier, 'revision')
        try:
            record = _metadata_json(self.revisions._directory(identifier) / 'revision.json', _MAX_REVISION_BYTES)
            if (not isinstance(record, dict) or set(record) != _RECORD_KEYS
                    or type(record['schema_version']) is not int or record['schema_version'] != 1
                    or record['revision_id'] != identifier or not _valid_timestamp(record['created_at'])
                    or record['provenance'] != 'user_selected' or not _sha(record['review_sha256'])
                    or not _sha(record['effective_settings_sha256'])):
                raise ValueError('Invalid revision metadata')
            _workspace_id(record['source_id'])
            proposal = record['proposal']
            if (not isinstance(proposal, dict) or set(proposal) != {'source_sha256','settings_sha256','values'}
                    or not _sha(proposal['source_sha256']) or not _sha(proposal['settings_sha256'])
                    or not isinstance(proposal['values'], dict) or not proposal['values']
                    or not set(proposal['values']).issubset(_DRAFT_FIELDS)
                    or not isinstance(record['changes'], list) or len(record['changes']) != len(proposal['values'])):
                raise ValueError('Invalid recorded proposal')
            for field in _FIELDS:
                if field[0] in proposal['values']:
                    _number(proposal['values'][field[0]], *field[3:])
            fields = []
            for change in record['changes']:
                if (not isinstance(change, dict) or set(change) != {'field','native_key','before','after'}
                        or change['field'] not in proposal['values'] or change['field'] in fields
                        or not isinstance(change['native_key'], str)
                        or any(not isinstance(change[key], list) or len(change[key]) != 1
                               or not isinstance(change[key][0], str) for key in ('before','after'))
                        or change['after'] != [proposal['values'][change['field']]]):
                    raise ValueError('Invalid recorded changes')
                fields.append(change['field'])
            item.update(title=f'설정 변경 {identifier[:8]}', created_at=record['created_at'], updated_at=record['created_at'],
                        source_id=record['source_id'], settings_revision_id=identifier, metadata_status='recorded',
                        detail='저장한 변경 항목 메타데이터입니다. 열 때 원본에서 다시 확인합니다.',
                        summary=f"원본 {record['source_id'][:8]} · {record['created_at']} · {', '.join(fields)}"[:1200])
        except (OSError, ValueError, KeyError, TypeError, UnicodeError, RecursionError, OverflowError):
            pass
        return item
