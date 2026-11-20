"""Imported model files: immutable originals with a verified analysis receipt.

The original bytes are never changed. Every read rechecks their SHA-256, and an
oriented 3MF is rebuilt from the original and the recorded placement on request.
"""
import hashlib
import json
import os
import re
import shutil
import uuid
from pathlib import Path

from . import model_import
from .storage import _atomic_write, _parse_json, _read_regular, now_iso

_MAX_RECEIPT_BYTES = 512 * 1024
_INTEGRITY_MESSAGE = '불러온 모델 원본 또는 기록이 달라졌습니다. 원본 파일을 다시 불러와 주세요.'
_FILENAME = re.compile(r'[^\\/:*?"<>|\x00-\x1f]{1,120}')


class ImportIntegrityError(ValueError):
    """Stored original bytes or their receipt no longer agree."""


def _public_analysis(analysis):
    return {key: value for key, value in analysis.items() if not key.startswith('_')}


class ImportStore:
    def __init__(self, root: Path):
        self.root = Path(root).expanduser().resolve()
        self.directory = self.root / 'imports'
        if self.directory.is_symlink() or (self.directory.exists() and not self.directory.is_dir()):
            raise ImportIntegrityError(_INTEGRITY_MESSAGE)
        self.directory.mkdir(mode=0o700, parents=True, exist_ok=True)

    def _folder(self, import_id):
        if not isinstance(import_id, str) or re.fullmatch(r'[a-f0-9]{32}', import_id) is None:
            raise ValueError('올바른 불러온 모델 ID가 필요합니다.')
        folder = self.directory / import_id
        if folder.is_symlink() or (folder.exists() and not folder.is_dir()):
            raise ImportIntegrityError(_INTEGRITY_MESSAGE)
        return folder

    def create(self, filename, content):
        name = str(filename or '').strip()
        if _FILENAME.fullmatch(name) is None:
            raise ValueError('파일 이름이 올바르지 않습니다.')
        # Analyse completely before claiming an ID or creating anything on disk.
        analysis = model_import.analyse(name, content)
        import_id = uuid.uuid4().hex
        folder = self._folder(import_id)
        folder.mkdir(mode=0o700)
        try:
            with (folder / ('source.' + analysis['format'])).open('xb') as stream:
                stream.write(content)
                stream.flush()
                os.fsync(stream.fileno())
            receipt = {'schema_version': 1, 'import_id': import_id, 'created_at': now_iso(), 'filename': name,
                       'format': analysis['format'], 'bytes': len(content), 'sha256': hashlib.sha256(content).hexdigest(),
                       'analysis': _public_analysis(analysis)}
            encoded = json.dumps(receipt, ensure_ascii=False, allow_nan=False).encode('utf-8')
            if len(encoded) > _MAX_RECEIPT_BYTES:
                raise ValueError('분석 기록이 너무 큽니다.')
            _atomic_write(folder / 'receipt.json', encoded)  # the publication marker
        except BaseException:
            shutil.rmtree(folder)
            raise
        return self._public(receipt, analysis)

    def _receipt(self, import_id):
        folder = self._folder(import_id)
        path = folder / 'receipt.json'
        if not path.exists() and not path.is_symlink():
            if folder.exists():
                raise ImportIntegrityError(_INTEGRITY_MESSAGE)
            raise KeyError('불러온 모델을 찾을 수 없습니다.')
        try:
            receipt = _parse_json(_read_regular(path, _MAX_RECEIPT_BYTES))
            if (not isinstance(receipt, dict) or receipt.get('import_id') != import_id
                    or receipt.get('format') not in ('stl', '3mf') or not isinstance(receipt.get('analysis'), dict)):
                raise ValueError('Invalid import receipt')
        except (OSError, ValueError, TypeError, RecursionError) as exc:
            raise ImportIntegrityError(_INTEGRITY_MESSAGE) from exc
        return folder, receipt

    def read_source(self, import_id):
        folder, receipt = self._receipt(import_id)
        try:
            content = _read_regular(folder / ('source.' + receipt['format']), model_import.MAX_MODEL_BYTES)
        except OSError as exc:
            raise ImportIntegrityError(_INTEGRITY_MESSAGE) from exc
        if len(content) != receipt['bytes'] or hashlib.sha256(content).hexdigest() != receipt['sha256']:
            raise ImportIntegrityError(_INTEGRITY_MESSAGE)
        return receipt, content

    def get(self, import_id):
        receipt, content = self.read_source(import_id)
        analysis = model_import.analyse(receipt['filename'], content)
        if _public_analysis(analysis) != receipt['analysis']:
            raise ImportIntegrityError(_INTEGRITY_MESSAGE)
        return self._public(receipt, analysis)

    def oriented(self, import_id, orientation_id):
        """A 3MF of the original mesh in a recorded placement, rebuilt from verified bytes."""
        receipt, content = self.read_source(import_id)
        analysis = model_import.analyse(receipt['filename'], content)
        placement = next((item for item in analysis['orientations'] if item['id'] == orientation_id), None)
        if placement is None:
            raise ValueError('없는 출력 방향입니다.')
        vertices, faces = analysis['_mesh']
        stem = re.sub(r'\.[A-Za-z0-9]+$', '', receipt['filename'])
        data = model_import.three_mf(model_import.oriented_vertices(vertices, placement['rotation']), faces, stem)
        return f'{stem}-출력방향{orientation_id + 1}.3mf', data

    def list(self, limit=20):
        entries = []
        for folder in self.directory.iterdir():
            if not folder.is_dir() or folder.is_symlink() or re.fullmatch(r'[a-f0-9]{32}', folder.name) is None:
                continue
            try:
                _, receipt = self._receipt(folder.name)
            except (ImportIntegrityError, KeyError):
                entries.append({'import_id': folder.name, 'unreadable': True, 'created_at': None})
                continue
            analysis = receipt['analysis']
            recommended = analysis['orientations'][analysis['recommended_id']]
            entries.append({'import_id': folder.name, 'filename': receipt['filename'], 'created_at': receipt['created_at'],
                            'format': receipt['format'], 'triangles': analysis['facts']['triangles'],
                            'status': recommended['review']['status']})
        entries.sort(key=lambda item: item.get('created_at') or '', reverse=True)
        return {'imports': entries[:limit]}

    @staticmethod
    def _public(receipt, analysis):
        vertices, faces = analysis['_mesh']
        public = {key: receipt[key] for key in ('import_id', 'created_at', 'filename', 'format', 'bytes', 'sha256')}
        public.update(_public_analysis(analysis))
        public['preview'] = model_import.preview_mesh(vertices, faces)
        public['source_url'] = f'/api/imports/{receipt["import_id"]}/source'
        public['scope'] = ('불러온 메시의 형상만 본 조언입니다. 원본 파일은 바꾸지 않고, 출력 방향은 회전·이동만 한 새 3MF로 내려받습니다. '
                           '벽 두께·슬라이서 결과·실물 출력은 확인하지 않았습니다.')
        return public
