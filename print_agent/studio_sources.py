"""Immutable Studio project sources; original bytes are verified on every read."""
import copy
import hashlib
import json
import os
import re
import shutil
import uuid
from pathlib import Path

from .storage import _atomic_write, _parse_json, _read_regular, _same_json, _valid_timestamp, now_iso
from .studio_project import MAX_ARCHIVE_BYTES, inspect_studio_project, public_snapshot

_MAX_RECEIPT_BYTES = 256 * 1024
_INTEGRITY_MESSAGE = '가져온 Studio 프로젝트의 원본 또는 기록이 달라졌습니다. 보관한 원본을 복구하거나 파일을 다시 선택해 주세요.'


class StudioSourceIntegrityError(ValueError):
    """Stored source bytes or identity no longer match the import receipt."""


def _publish_receipt(path, value):
    content = json.dumps(value, ensure_ascii=False, allow_nan=False, indent=2).encode('utf-8')
    if len(content) > _MAX_RECEIPT_BYTES:
        raise ValueError('Studio 프로젝트의 설정 요약 기록이 너무 큽니다.')
    _atomic_write(path, content)


class StudioProjectStore:
    def __init__(self, root: Path):
        self.root = Path(root).expanduser().resolve()
        self.sources_dir = self.root / 'studio-projects'
        self._check_parent()
        self.sources_dir.mkdir(mode=0o700, parents=True, exist_ok=True)

    def _check_parent(self):
        if self.sources_dir.is_symlink() or (self.sources_dir.exists() and not self.sources_dir.is_dir()):
            raise StudioSourceIntegrityError(_INTEGRITY_MESSAGE)

    def _directory(self, source_id):
        if not isinstance(source_id, str) or re.fullmatch(r'[a-f0-9]{32}', source_id) is None:
            raise ValueError('올바른 Studio 프로젝트 원본 ID가 필요합니다.')
        self._check_parent()
        folder = self.sources_dir / source_id
        if folder.is_symlink() or (folder.exists() and not folder.is_dir()):
            raise StudioSourceIntegrityError(_INTEGRITY_MESSAGE)
        return folder

    @staticmethod
    def _public(snapshot, source_id):
        return {**copy.deepcopy(public_snapshot(snapshot)), 'source_id': source_id,
                'archive_url': f'/api/studio-projects/{source_id}/archive'}

    def import_project(self, filename, content):
        # Validate completely before claiming an ID or creating a source folder.
        snapshot = inspect_studio_project(filename, content)
        source_id = uuid.uuid4().hex
        folder = self._directory(source_id)
        # An existing empty directory is still someone else's record. mkdir is
        # exclusive on every supported OS; never rename over a collision.
        folder.mkdir(mode=0o700)
        try:
            with (folder / 'source.3mf').open('xb') as stream:
                stream.write(content)
                stream.flush()
                os.fsync(stream.fileno())
            receipt = {'schema_version': 1, 'source_id': source_id, 'created_at': now_iso(),
                       'inspection': public_snapshot(snapshot)}
            # The atomic receipt is the publication marker. A guessed ID before
            # this point cannot return a partial source through any read method.
            _publish_receipt(folder / 'receipt.json', receipt)
            return self.get(source_id)
        except BaseException:
            # Only the directory we exclusively created is eligible for cleanup.
            shutil.rmtree(folder)
            raise

    def read(self, source_id):
        folder = self._directory(source_id)
        receipt_path = folder / 'receipt.json'
        if not receipt_path.exists() and not receipt_path.is_symlink():
            raise KeyError('Studio 프로젝트 원본을 찾을 수 없습니다.')
        try:
            receipt = _parse_json(_read_regular(receipt_path, _MAX_RECEIPT_BYTES))
            if (not isinstance(receipt, dict) or set(receipt) != {'schema_version', 'source_id', 'created_at', 'inspection'}
                    or type(receipt['schema_version']) is not int or receipt['schema_version'] != 1
                    or receipt['source_id'] != source_id or not _valid_timestamp(receipt['created_at'])
                    or not isinstance(receipt['inspection'], dict)):
                raise ValueError('Invalid source receipt')
            source = receipt['inspection']['source']
            if (not isinstance(source, dict) or type(source.get('bytes')) is not int
                    or not 0 < source['bytes'] <= MAX_ARCHIVE_BYTES
                    or not isinstance(source.get('sha256'), str)
                    or re.fullmatch(r'[a-f0-9]{64}', source['sha256']) is None):
                raise ValueError('Invalid source identity')
            content = _read_regular(folder / 'source.3mf', MAX_ARCHIVE_BYTES, expected_size=source['bytes'])
            if hashlib.sha256(content).hexdigest() != source['sha256']:
                raise ValueError('Changed original bytes')
            snapshot = inspect_studio_project(source['filename'], content)
            if not _same_json(public_snapshot(snapshot), receipt['inspection']):
                raise ValueError('Changed source inspection')
            return snapshot, content
        except (OSError, ValueError, KeyError, TypeError, RecursionError, OverflowError) as exc:
            raise StudioSourceIntegrityError(_INTEGRITY_MESSAGE) from exc

    def get(self, source_id):
        snapshot, _ = self.read(source_id)
        return self._public(snapshot, source_id)

    def archive(self, source_id):
        snapshot, content = self.read(source_id)
        return snapshot['source']['filename'], content
