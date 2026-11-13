"""Read bounded Studio preset archives as evidence, without extracting or merging.

Format reference: BambuStudio 56a57d00a591360cf41bf21383915ee5bf357be5,
src/slic3r/GUI/CreatePresetsDialog.cpp (export) and
src/libslic3r/PresetBundle.cpp (native category discriminators).
This parser neither reproduces Studio's defaults nor qualifies native import.
"""
import hashlib
import io
import json
import math
import stat
import struct
import zipfile
import zlib


_MAX_ARCHIVE_BYTES = 4 * 1024 * 1024
_MAX_EXPANDED_BYTES = 4 * 1024 * 1024
_MAX_JSON_BYTES = 2 * 1024 * 1024
_MAX_DOCUMENT_BYTES = 2 * 1024 * 1024
_MAX_MEMBERS = 256
_MAX_DOCUMENTS = 64
_MAX_JSON_DEPTH = 64
_MAX_SAFE_INTEGER = 2**53 - 1
_MANIFEST = 'bundle_structure.json'
_LOCAL_HEADER = struct.Struct('<4s5H3I2H')
_NATIVE_IDENTITIES = {
    'printer_settings_id': 'machine',
    'print_settings_id': 'process',
    'filament_settings_id': 'filament',
}
_WARNINGS = [
    '가져온 파일의 명시값만 보존합니다. 패키지에 없는 부모·Studio 기본값·variant·nil 처리는 해석하지 않습니다.',
    '파일명과 바이트 해시는 가져온 입력을 구분하며, 발행처 인증이나 실제 출력·교정 검증을 뜻하지 않습니다.',
    '묶음의 version은 Studio 실행 파일의 확인된 버전으로 사용하지 않습니다. 가져온 프로필을 현재 조건으로 검토하세요.',
]


def _safe_path(value, *, directory=False, archive_name=False):
    if not isinstance(value, str) or not value.strip() or len(value) > 240:
        raise ValueError('묶음과 내부 파일 이름은 1자 이상 240자 이하이어야 합니다.')
    try:
        value.encode('utf-8')
    except UnicodeError as exc:
        raise ValueError('파일 이름에 올바른 UTF-8 문자열이 필요합니다.') from exc
    path = value[:-1] if directory and value.endswith('/') else value
    if (not path or '\\' in path or ':' in path
            or any(ord(char) < 32 or ord(char) == 127 for char in value)
            or any(part in ('', '.', '..') for part in path.split('/'))
            or (archive_name and '/' in path)):
        raise ValueError('안전한 상대 경로와 파일 이름만 가져올 수 있습니다.')
    return path


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('중복 JSON 키가 있어 원본 값을 확정할 수 없습니다.')
        result[key] = value
    return result


def _reject_constant(_):
    raise ValueError('JSON에는 NaN·Infinity 대신 유한한 숫자가 필요합니다.')


def _read_json(raw, path):
    try:
        text = raw.decode('utf-8')
        value = json.loads(text, object_pairs_hook=_unique_object, parse_constant=_reject_constant)
    except (UnicodeError, ValueError, RecursionError) as exc:
        raise ValueError(f'{path}: 올바른 UTF-8 JSON 객체가 필요합니다. {exc}') from exc
    if not isinstance(value, dict):
        raise ValueError(f'{path}: JSON의 최상위 값은 객체이어야 합니다.')
    pending = [(value, 0)]
    while pending:
        item, depth = pending.pop()
        if depth > _MAX_JSON_DEPTH:
            raise ValueError(f'{path}: JSON 중첩은 최대 64단계까지 지원합니다.')
        if isinstance(item, dict):
            for key, child in item.items():
                pending.extend(((key, depth + 1), (child, depth + 1)))
        elif isinstance(item, list):
            pending.extend((child, depth + 1) for child in item)
        elif isinstance(item, str):
            try:
                item.encode('utf-8')
            except UnicodeError as exc:
                raise ValueError(f'{path}: JSON에 올바른 Unicode 문자열이 필요합니다.') from exc
        elif isinstance(item, (int, float)) and not isinstance(item, bool):
            if ((isinstance(item, float) and not math.isfinite(item))
                    or (isinstance(item, int) and abs(item) > _MAX_SAFE_INTEGER)
                    or (isinstance(item, float) and item.is_integer() and abs(item) > _MAX_SAFE_INTEGER)):
                raise ValueError(f'{path}: 브라우저에서 정확히 보존할 수 있는 유한한 숫자가 필요합니다.')
    return value, text


def _member_bytes(archive, info, content, allowance):
    """Verify complete member data, independent of claimed uncompressed size.

    ZipExtFile clips reads to file_size, so a forged prefix size and CRC could
    hide trailing output. Use ZipFile.open for structural/name checks, then
    decode the bounded compressed span and verify EOF, actual size and CRC.
    """
    with archive.open(info):
        offset = info.header_offset
        if offset < 0 or offset + _LOCAL_HEADER.size > len(content):
            raise ValueError('ZIP 파일의 로컬 헤더 위치가 올바르지 않습니다.')
        header = _LOCAL_HEADER.unpack_from(content, offset)
        if (header[0] != b'PK\x03\x04' or header[2] != info.flag_bits
                or header[3] != info.compress_type):
            raise ValueError('ZIP 파일의 로컬 헤더와 중앙 목록이 일치하지 않습니다.')
        start = offset + _LOCAL_HEADER.size + header[9] + header[10]
        end = start + info.compress_size
        if not start <= end <= len(content):
            raise ValueError('ZIP 파일의 압축 데이터 범위가 올바르지 않습니다.')
        compressed = content[start:end]
        if info.compress_type == zipfile.ZIP_STORED:
            raw = compressed
        else:
            decoder = zlib.decompressobj(-zlib.MAX_WBITS)
            raw = decoder.decompress(compressed, allowance + 1)
            if len(raw) > allowance:
                raise ValueError('압축 해제 크기 제한을 초과했습니다. 전체 4 MiB, 각 JSON 2 MiB까지 지원합니다.')
            if not decoder.eof or decoder.unused_data or decoder.unconsumed_tail:
                raise ValueError('DEFLATE 스트림이 잘렸거나 뒤에 추가 압축 데이터가 있습니다.')
        if len(raw) > allowance:
            raise ValueError('압축 해제 크기 제한을 초과했습니다. 전체 4 MiB, 각 JSON 2 MiB까지 지원합니다.')
        if len(raw) != info.file_size:
            raise ValueError('압축 파일의 크기 정보와 전체 데이터의 실제 크기가 다릅니다.')
        if zlib.crc32(raw) != info.CRC:
            raise ValueError('ZIP 파일의 CRC가 일치하지 않습니다. 손상되지 않은 파일을 다시 선택하세요.')
        return raw


def _read_members(content):
    """Check every entry, including omitted assets, and never write to disk."""
    members = {}
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            entries = archive.infolist()
            if len(entries) > _MAX_MEMBERS:
                raise ValueError('압축 묶음은 폴더를 포함해 최대 256개 항목까지 지원합니다.')
            seen, declared_bytes = {}, 0
            for info in entries:
                path = _safe_path(info.orig_filename, directory=info.is_dir())
                if info.orig_filename != info.filename:
                    raise ValueError('내부 파일 이름에 잘린 문자 또는 잘못된 경로가 있습니다.')
                if path in seen:
                    raise ValueError('중복된 내부 파일 경로는 가져올 수 없습니다.')
                seen[path] = info.is_dir()
                mode = stat.S_IFMT(info.external_attr >> 16)
                if mode not in (0, stat.S_IFREG, stat.S_IFDIR) or (mode == stat.S_IFDIR and not info.is_dir()):
                    raise ValueError('링크와 특수 항목은 지원하지 않습니다. 일반 파일과 폴더만 가져오세요.')
                if info.flag_bits & (1 | 64):
                    raise ValueError('암호화된 압축 파일은 지원하지 않습니다.')
                if info.compress_type not in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED):
                    raise ValueError('지원하는 ZIP 압축 방식은 저장 또는 DEFLATE입니다.')
                declared_bytes += info.file_size
                if declared_bytes > _MAX_EXPANDED_BYTES:
                    raise ValueError('무시할 파일을 포함한 압축 해제 크기는 합계 4 MiB 이하여야 합니다.')
                if info.filename.lower().endswith('.json') and info.file_size > _MAX_JSON_BYTES:
                    raise ValueError('각 JSON 파일은 2 MiB 이하여야 합니다.')
            for path in seen:
                parts = path.split('/')
                if any('/'.join(parts[:index]) in seen and not seen['/'.join(parts[:index])]
                       for index in range(1, len(parts))):
                    raise ValueError('같은 경로를 파일과 상위 폴더로 함께 사용할 수 없습니다.')
            actual_bytes = 0
            for info in entries:
                allowance = _MAX_EXPANDED_BYTES - actual_bytes
                if info.filename.lower().endswith('.json'):
                    allowance = min(allowance, _MAX_JSON_BYTES)
                raw = _member_bytes(archive, info, content, allowance)
                actual_bytes += len(raw)
                if info.is_dir():
                    if raw:
                        raise ValueError('폴더 항목에는 파일 데이터가 없어야 합니다.')
                    continue
                path = info.filename
                if path.rsplit('/', 1)[-1] == _MANIFEST and path != _MANIFEST:
                    raise ValueError('bundle_structure.json manifest는 묶음의 최상위 경로에 있어야 합니다.')
                if path.lower().endswith('.json'):
                    profile, text = _read_json(raw, path)
                    members[path] = {'profile': profile, 'text': text,
                                     'sha256': hashlib.sha256(raw).hexdigest()}
                else:
                    members[path] = None
    except (zipfile.BadZipFile, zipfile.LargeZipFile, RuntimeError, NotImplementedError,
            EOFError, OSError, zlib.error) as exc:
        raise ValueError('ZIP 구조 또는 CRC가 손상되었거나 지원하지 않는 압축 파일입니다.') from exc
    return members


def _manifest_categories(members, extension):
    if _MANIFEST not in members:
        if extension != 'zip':
            raise ValueError('Bambu 묶음에 bundle_structure.json manifest가 필요합니다.')
        return None
    manifest = members[_MANIFEST]['profile']
    kind = manifest.get('bundle_type')
    formats = {'filament config bundle': 'bbsflmt', 'printer config bundle': 'bbscfg'}
    if not isinstance(kind, str) or kind not in formats or (extension != 'zip' and formats[kind] != extension):
        raise ValueError('manifest의 bundle_type과 파일 형식이 일치하지 않습니다.')
    if not isinstance(manifest.get('version'), str) or not isinstance(manifest.get('bundle_id'), str):
        raise ValueError('manifest의 version과 bundle_id는 문자열이어야 합니다.')
    title_key = 'filament_name' if formats[kind] == 'bbsflmt' else 'printer_preset_name'
    if not isinstance(manifest.get(title_key), str) or not manifest[title_key].strip():
        raise ValueError('manifest에 묶음의 프리셋 이름이 필요합니다.')
    categories = {}

    def add(paths, category, directory):
        if not isinstance(paths, list):
            raise ValueError('manifest의 파일 참조는 경로 문자열 목록이어야 합니다.')
        for path in paths:
            _safe_path(path)
            if (path == _MANIFEST or not path.lower().endswith('.json')
                    or path.rsplit('/', 1)[0] != directory or '/' not in path):
                raise ValueError('manifest의 파일 참조 경로와 종류별 폴더가 일치하지 않습니다.')
            if path in categories:
                raise ValueError('manifest의 파일 참조 목록에 중복 경로가 있습니다.')
            if path not in members or members[path] is None:
                raise ValueError('manifest에서 참조한 JSON 파일이 묶음에 없습니다.')
            categories[path] = category

    if formats[kind] == 'bbsflmt':
        vendors = manifest.get('filament_vendor')
        if not isinstance(vendors, list):
            raise ValueError('manifest의 filament_vendor 목록이 필요합니다.')
        seen_vendors = set()
        for item in vendors:
            if not isinstance(item, dict) or not isinstance(item.get('vendor'), str) or not item['vendor'].strip():
                raise ValueError('manifest의 vendor와 filament_path 목록이 필요합니다.')
            vendor = item['vendor']
            _safe_path(vendor)
            if vendor in seen_vendors:
                raise ValueError('manifest에 중복된 vendor 목록이 있습니다.')
            seen_vendors.add(vendor)
            add(item.get('filament_path'), 'filament', vendor)
    else:
        for key, category, directory in (('printer_config', 'machine', 'printer'),
                ('filament_config', 'filament', 'filament'), ('process_config', 'process', 'process')):
            add(manifest.get(key), category, directory)
    unlisted = {path for path, member in members.items() if member is not None and path != _MANIFEST} - categories.keys()
    if unlisted:
        raise ValueError('manifest 목록에 없는 JSON 파일이 있습니다. 원래 내보낸 묶음을 확인하세요.')
    return categories


def _preset_kind(profile, path):
    categories = {_NATIVE_IDENTITIES[key] for key in _NATIVE_IDENTITIES if key in profile}
    if 'type' in profile:
        declared = profile['type']
        if not isinstance(declared, str) or declared not in {'machine', 'process', 'filament'}:
            raise ValueError(f'{path}: 지원하는 프리셋 종류(type)를 확인할 수 없습니다.')
        categories.add(declared)
    if len(categories) > 1:
        raise ValueError(f'{path}: type과 프리셋 식별자의 종류가 충돌합니다.')
    if not categories:
        return None
    name = profile.get('name')
    if not isinstance(name, str) or not name.strip() or len(name) > 256:
        raise ValueError(f'{path}: 프리셋 name은 1자 이상 256자 이하의 이름이어야 합니다.')
    return next(iter(categories))


def import_preset_archive(filename: str, content: bytes) -> dict:
    """Return atomic review candidates and byte receipts, never installed presets."""
    _safe_path(filename, archive_name=True)
    extension = filename.rsplit('.', 1)[-1].lower()
    if extension not in {'bbsflmt', 'bbscfg', 'zip'}:
        raise ValueError('Studio 내보내기 파일 .bbsflmt, .bbscfg 또는 .zip을 선택하세요.')
    if not isinstance(content, bytes) or not content:
        raise ValueError('비어 있지 않은 압축 파일 바이트가 필요합니다.')
    if len(content) > _MAX_ARCHIVE_BYTES:
        raise ValueError('압축 파일은 4 MiB 이하여야 합니다.')
    members = _read_members(content)
    categories = _manifest_categories(members, extension)
    digest = hashlib.sha256(content).hexdigest()
    documents, ignored = [], []
    for path, member in members.items():
        if path == _MANIFEST:
            continue
        if member is None:
            ignored.append({'path': path, 'reason': '프리셋 JSON이 아닌 파일입니다.'})
            continue
        category = _preset_kind(member['profile'], path)
        if categories is not None and categories[path] != category:
            raise ValueError(f'{path}: manifest의 종류와 JSON 프리셋 식별자가 일치하지 않습니다.')
        if category != 'filament':
            reasons = {'machine': '프린터 프리셋은 필라멘트 작업에 추가하지 않습니다.',
                       'process': '출력 설정 프리셋은 필라멘트 작업에 추가하지 않습니다.',
                       None: '필라멘트 프리셋의 종류를 확인할 수 없는 JSON입니다.'}
            ignored.append({'path': path, 'reason': reasons[category]})
            continue
        documents.append({'filename': path, 'profile': member['profile'], 'draft_text': member['text'],
            'origin': {'type': 'bambu_preset_archive', 'archive_name': filename,
                'archive_sha256': digest, 'member_path': path, 'member_sha256': member['sha256']}})
        if len(documents) > _MAX_DOCUMENTS:
            raise ValueError('한 번에 가져올 필라멘트 프리셋은 최대 64개입니다.')
    if not documents:
        raise ValueError('가져올 필라멘트 프리셋이 없습니다. Studio의 필라멘트 내보내기 묶음을 선택하세요.')
    originals = [{key: value for key, value in document.items() if key != 'draft_text'} for document in documents]
    if len(json.dumps(originals, ensure_ascii=False, separators=(',', ':'), allow_nan=False).encode('utf-8')) > _MAX_DOCUMENT_BYTES:
        raise ValueError('가져올 원본 문서의 합계는 2 MiB 이하여야 합니다.')
    return {'schema_version': 1, 'archive': {'filename': filename, 'sha256': digest, 'format': extension},
            'documents': documents, 'ignored_members': ignored, 'warnings': list(_WARNINGS)}
