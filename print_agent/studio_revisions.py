"""Immutable user-selected setting recipes, always rederived from their source."""
import copy
import json
import re
import shutil
import uuid
from pathlib import Path

from .storage import _atomic_write, _parse_json, _read_regular, now_iso
from .studio_settings import make_revision, verify_revision


_MAX_REVISION_BYTES = 64 * 1024
_INTEGRITY_MESSAGE = '보관한 Studio 설정 변경 기록이 원본과 일치하지 않습니다. 원본을 다시 확인한 뒤 변경값을 새로 검토해 주세요.'


class StudioRevisionIntegrityError(ValueError):
    """A stored setting revision cannot be verified against its original."""


def _publish_revision(path, record):
    content = (json.dumps(record, ensure_ascii=False, allow_nan=False, sort_keys=True, indent=2) + '\n').encode('utf-8')
    if len(content) > _MAX_REVISION_BYTES:
        raise ValueError('Studio 설정 변경 기록은 64 KiB 이하여야 합니다.')
    _atomic_write(path, content)


class StudioSettingsRevisionStore:
    def __init__(self, root: Path, sources):
        self.root = Path(root).expanduser().resolve()
        if sources.root != self.root:
            raise ValueError('원본과 설정 변경 기록은 같은 데이터 폴더에 있어야 합니다.')
        self.sources = sources
        self.revisions_dir = self.root / 'studio-settings-revisions'
        self._check_parent()
        self.revisions_dir.mkdir(mode=0o700, parents=True, exist_ok=True)

    def _check_parent(self):
        if self.revisions_dir.is_symlink() or (self.revisions_dir.exists() and not self.revisions_dir.is_dir()):
            raise StudioRevisionIntegrityError(_INTEGRITY_MESSAGE)

    def _directory(self, revision_id):
        if not isinstance(revision_id, str) or re.fullmatch(r'[a-f0-9]{32}', revision_id) is None:
            raise ValueError('올바른 Studio 설정 변경 기록 ID가 필요합니다.')
        self._check_parent()
        folder = self.revisions_dir / revision_id
        if folder.is_symlink() or (folder.exists() and not folder.is_dir()):
            raise StudioRevisionIntegrityError(_INTEGRITY_MESSAGE)
        return folder

    def create(self, source_id, proposal, review_sha256):
        snapshot, _ = self.sources.read(source_id)
        revision_id = uuid.uuid4().hex
        record = make_revision(snapshot, proposal, source_id=source_id,
                               revision_id=revision_id, created_at=now_iso(), review_sha256=review_sha256)
        folder = self._directory(revision_id)
        # Validation precedes publication; an existing directory is never ours.
        folder.mkdir(mode=0o700)
        try:
            _publish_revision(folder / 'revision.json', record)
            return self.get(revision_id)
        except BaseException:
            shutil.rmtree(folder)
            raise

    def read(self, revision_id):
        path = self._directory(revision_id) / 'revision.json'
        if not path.exists() and not path.is_symlink():
            raise KeyError('Studio 설정 변경 기록을 찾을 수 없습니다.')
        try:
            record = _parse_json(_read_regular(path, _MAX_REVISION_BYTES))
            if (not isinstance(record, dict) or record.get('revision_id') != revision_id
                    or not isinstance(record.get('source_id'), str)
                    or re.fullmatch(r'[a-f0-9]{32}', record['source_id']) is None):
                raise ValueError('Invalid revision identity')
        except (OSError, ValueError, KeyError, TypeError, RecursionError, OverflowError) as exc:
            raise StudioRevisionIntegrityError(_INTEGRITY_MESSAGE) from exc
        # Keep a missing source (404) distinct from a corrupt source (409).
        snapshot, content = self.sources.read(record['source_id'])
        try:
            verify_revision(snapshot, record, source_id=record['source_id'])
        except (ValueError, KeyError, TypeError, RecursionError, OverflowError) as exc:
            raise StudioRevisionIntegrityError(_INTEGRITY_MESSAGE) from exc
        return snapshot, content, record

    def get(self, revision_id):
        snapshot, _, record = self.read(revision_id)
        _, review = verify_revision(snapshot, record, source_id=record['source_id'])
        return {'revision': copy.deepcopy(record), 'review': review,
                'source': self.sources._public(snapshot, record['source_id'])}
