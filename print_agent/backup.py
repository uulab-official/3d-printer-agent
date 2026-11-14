"""Verified, offline workspace archives; no CAD, web or native-code imports.

Archives preserve saved bytes, including damaged records. Integrity verification
does not certify application health, authorship, or physical print suitability.
Restoration separately applies the lightweight storage compatibility gate.
"""
from contextlib import contextmanager
import ctypes
from datetime import datetime, timedelta, timezone
import errno
from functools import wraps
import hashlib
import io
import json
import os
from pathlib import Path
import re
import shutil
import stat
import struct
import sys
import tempfile
import unicodedata
import zipfile
import zlib

from . import __version__
from .runtime import DataDirectoryLease


MAX_FILES = 20_000
MAX_FILE_BYTES = 512 * 1024 * 1024
MAX_TOTAL_BYTES = 4 * 1024 * 1024 * 1024
MAX_MANIFEST_BYTES = 8 * 1024 * 1024
_CHUNK = 128 * 1024
_MAX_PATH_BYTES = 4096
_FORMAT = '3d-printer-agent-backup'
_LOCK_NAME = '.printer-agent.lock'
_MANIFEST_FIELDS = {'format', 'version', 'application_version', 'created_at',
                    'file_count', 'total_bytes', 'files'}
_RESERVED = {'CON', 'PRN', 'AUX', 'NUL', 'CONIN$', 'CONOUT$'} | {
    prefix + digit for prefix in ('COM', 'LPT') for digit in '123456789¹²³'
}


class BackupError(ValueError):
    """A backup cannot be verified or safely published; existing data is kept."""


def _operation(message):
    def decorate(function):
        @wraps(function)
        def run(*args, **kwargs):
            try:
                return function(*args, **kwargs)
            except BackupError:
                raise
            except (OSError, ValueError, UnicodeError, OverflowError, RecursionError, NotImplementedError,
                    struct.error, zipfile.BadZipFile, zipfile.LargeZipFile, zlib.error) as exc:
                raise BackupError(message) from exc
        return run
    return decorate


def _absolute(path):
    # Resolve ancestors, but never dereference the final component before the
    # operation checks it. A dangling symlink is an existing destination too.
    selected = Path(os.path.abspath(Path(path).expanduser()))
    return selected.parent.resolve(strict=True) / selected.name


def _exists(path):
    try:
        path.lstat()
        return True
    except FileNotFoundError:
        return False


def _linked(metadata):
    return (stat.S_ISLNK(metadata.st_mode)
            or bool(getattr(metadata, 'st_file_attributes', 0)
                    & getattr(stat, 'FILE_ATTRIBUTE_REPARSE_POINT', 0x400)))


def _fingerprint(metadata):
    return (metadata.st_dev, metadata.st_ino, metadata.st_mode, metadata.st_size,
            metadata.st_mtime_ns, metadata.st_ctime_ns)


@contextmanager
def _regular_file(path, expected=None):
    before = path.lstat()
    if _linked(before) or not stat.S_ISREG(before.st_mode):
        raise BackupError('심볼릭 링크·특수 파일은 백업하거나 복원할 수 없습니다. 일반 파일을 사용하세요.')
    if expected is not None and _fingerprint(before) != _fingerprint(expected):
        raise BackupError('백업 중 원본 파일이 변경됐습니다. 쓰는 프로그램을 종료한 뒤 다시 시도하세요.')
    flags = os.O_RDONLY | getattr(os, 'O_BINARY', 0) | getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_NONBLOCK', 0)
    with os.fdopen(os.open(path, flags), 'rb') as stream:
        opened = os.fstat(stream.fileno())
        if not stat.S_ISREG(opened.st_mode) or _fingerprint(opened) != _fingerprint(before):
            raise BackupError('파일을 여는 동안 원본이 변경됐습니다. 작업을 멈추고 다시 시도하세요.')
        yield stream, opened
        if (_fingerprint(os.fstat(stream.fileno())) != _fingerprint(opened)
                or _fingerprint(path.lstat()) != _fingerprint(before)):
            raise BackupError('검사 중 파일이 변경됐습니다. 다른 프로그램의 쓰기를 멈추고 다시 시도하세요.')


def _portable_parts(value):
    if not isinstance(value, str) or not value or len(value.encode('utf-8')) > _MAX_PATH_BYTES:
        raise BackupError('백업의 상대 경로 형식이나 길이가 지원 범위를 벗어났습니다.')
    parts = value.split('/')
    for part in parts:
        if (part in ('', '.', '..') or part.endswith(('.', ' '))
                or re.search(r'[<>:"\\|?*\x00-\x1f]', part)
                or len(part.encode('utf-8')) > 255
                or part.split('.')[0].upper() in _RESERVED):
            raise BackupError('백업에 안전하게 옮길 수 없는 파일 경로가 있습니다. 경로와 파일 이름을 확인하세요.')
    return parts


def _register_path(value, registry, *, is_file=True):
    parts = _portable_parts(value)
    # Store components, not every complete prefix. Deep paths otherwise make
    # the registry grow quadratically relative to the bounded manifest bytes.
    node = registry
    for index, original in enumerate(parts, 1):
        key = unicodedata.normalize('NFC', unicodedata.normalize('NFC', original).casefold())
        kind = 'file' if index == len(parts) and is_file else 'directory'
        previous = node.get(key)
        if previous is not None:
            if previous[:2] != (original, kind) or kind == 'file':
                raise BackupError('백업 경로가 중복되거나 대소문자·Unicode 정규화·폴더 이름이 충돌합니다.')
        else:
            previous = node[key] = original, kind, {}
        node = previous[2]
    return parts


def _recognized(names):
    return (any(name in names for name in ('history.sqlite3', 'profile-workspaces.sqlite3'))
            or any(re.fullmatch(r'jobs/[a-f0-9]{32}/job\.json', name) for name in names))


def _inventory(root):
    found, registry, pending = [], {}, [root]
    path_bytes, total = 0, 0
    while pending:
        directory = pending.pop()
        metadata = directory.lstat()
        if _linked(metadata) or not stat.S_ISDIR(metadata.st_mode):
            raise BackupError('백업 원본 안에 연결된 폴더나 지원하지 않는 파일이 있습니다.')
        with os.scandir(directory) as entries:
            for entry in entries:
                path = Path(entry.path)
                relative = path.relative_to(root).as_posix()
                if relative == _LOCK_NAME:
                    continue
                metadata = entry.stat(follow_symlinks=False)
                if _linked(metadata):
                    raise BackupError('연결된 파일·폴더는 백업하지 않습니다. 원본 일반 파일을 확인하세요.')
                if stat.S_ISDIR(metadata.st_mode):
                    _register_path(relative, registry, is_file=False)
                    pending.append(path)
                elif stat.S_ISREG(metadata.st_mode):
                    _register_path(relative, registry)
                    path_bytes += len(relative.encode('utf-8'))
                    total += metadata.st_size
                    if (len(found) >= MAX_FILES or metadata.st_size > MAX_FILE_BYTES
                            or total > MAX_TOTAL_BYTES or path_bytes > MAX_MANIFEST_BYTES):
                        raise BackupError('백업 용량 제한을 넘었습니다. 파일 수·개별 파일·전체 용량을 확인하세요.')
                    found.append((relative, metadata))
                else:
                    raise BackupError('일반 파일과 폴더만 백업할 수 있습니다. 특수 파일을 확인하세요.')
    return sorted(found, key=lambda item: item[0])


def _parse_manifest(content):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise BackupError('백업 manifest에 중복된 항목이 있습니다.')
            result[key] = value
        return result
    def constant(_):
        raise BackupError('백업 manifest에는 유한한 JSON 값이 필요합니다.')
    manifest = json.loads(content, object_pairs_hook=pairs, parse_constant=constant)
    if (not isinstance(manifest, dict) or set(manifest) != _MANIFEST_FIELDS
            or manifest['format'] != _FORMAT or type(manifest['version']) is not int
            or manifest['version'] != 1):
        raise BackupError('지원하는 3D Printer Agent 작업 공간 백업 형식이 아닙니다.')
    version, created = manifest['application_version'], manifest['created_at']
    if (not isinstance(version, str) or not re.fullmatch(r'[0-9][0-9A-Za-z.+_-]{0,63}', version)
            or not isinstance(created, str) or not 1 <= len(created) <= 80
            or datetime.fromisoformat(created).utcoffset() != timedelta(0)):
        raise BackupError('백업의 앱 버전 또는 UTC 생성 시간이 올바르지 않습니다.')
    count, total, files = manifest['file_count'], manifest['total_bytes'], manifest['files']
    if (type(count) is not int or not 1 <= count <= MAX_FILES or not isinstance(files, list)
            or len(files) != count or type(total) is not int or not 0 <= total <= MAX_TOTAL_BYTES):
        raise BackupError('백업 파일 목록 또는 전체 용량이 올바르지 않습니다.')
    registry, declared_total = {}, 0
    for item in files:
        if (not isinstance(item, dict) or set(item) != {'path', 'bytes', 'sha256'}
                or type(item['bytes']) is not int or not 0 <= item['bytes'] <= MAX_FILE_BYTES
                or not isinstance(item['sha256'], str) or not re.fullmatch(r'[a-f0-9]{64}', item['sha256'])):
            raise BackupError('백업 파일의 크기 또는 SHA-256 기록이 올바르지 않습니다.')
        _register_path(item['path'], registry)
        if item['path'] == _LOCK_NAME:
            raise BackupError('프로세스 잠금 파일은 작업 공간 백업에 포함할 수 없습니다.')
        declared_total += item['bytes']
    if declared_total != total:
        raise BackupError('백업 목록의 합계와 전체 용량이 다릅니다.')
    return manifest


def _directory_offset(stream, length):
    """Bound ZIP metadata before ZipFile allocates its central-directory list."""
    maximum_central = MAX_MANIFEST_BYTES + (MAX_FILES + 1) * 128
    maximum_archive = MAX_TOTAL_BYTES + 2 * MAX_MANIFEST_BYTES + (MAX_FILES + 1) * 256 + 16 * 1024 * 1024
    if not 22 <= length <= maximum_archive:
        raise BackupError('백업 ZIP 크기가 지원 범위를 벗어났거나 파일이 잘렸습니다.')
    tail_start = max(0, length - (65535 + 22))
    stream.seek(tail_start)
    tail = stream.read(length - tail_start)
    index = tail.rfind(b'PK\x05\x06')
    if index < 0 or index + 22 > len(tail):
        raise BackupError('완성된 ZIP 백업을 찾을 수 없습니다. 파일을 다시 확인하세요.')
    signature, disk, start_disk, disk_count, count, size, offset, comment = struct.unpack('<4s4H2LH', tail[index:index + 22])
    end_position = tail_start + index
    if disk or start_disk or disk_count != count or index + 22 + comment != len(tail):
        raise BackupError('분할되었거나 끝부분이 올바르지 않은 ZIP 백업입니다.')
    central_end = end_position
    if count == 0xffff or size == 0xffffffff or offset == 0xffffffff:
        if end_position < 20:
            raise BackupError('ZIP64 백업 정보가 잘렸습니다.')
        stream.seek(end_position - 20)
        marker, zip_disk, zip_offset, disks = struct.unpack('<4sLQL', stream.read(20))
        if marker != b'PK\x06\x07' or zip_disk or disks != 1 or zip_offset + 56 != end_position - 20:
            raise BackupError('지원하지 않는 ZIP64 백업 구조입니다.')
        stream.seek(zip_offset)
        values = struct.unpack('<4sQ2H2L4Q', stream.read(56))
        if values[0] != b'PK\x06\x06' or values[1] != 44 or values[4] or values[5] or values[6] != values[7]:
            raise BackupError('지원하지 않는 ZIP64 백업 구조입니다.')
        count, size, offset = values[7:10]
        central_end = zip_offset
    if not 2 <= count <= MAX_FILES + 1 or size > maximum_central or offset + size != central_end:
        raise BackupError('백업 ZIP의 파일 수·목록 용량·위치가 올바르지 않습니다.')
    return offset, count


def _member_layout(stream, info, central_offset):
    mode = info.external_attr >> 16
    if (info.orig_filename != info.filename or info.is_dir()
            or info.flag_bits & ~0x80e or info.compress_type not in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED)
            or stat.S_IFMT(mode) not in (0, stat.S_IFREG)
            or info.external_attr & 0x410):
        raise BackupError('암호화·링크·특수 파일 또는 지원하지 않는 ZIP 항목이 있습니다.')
    if info.header_offset < 0 or info.header_offset + 30 > central_offset:
        raise BackupError('백업 파일의 ZIP 위치가 올바르지 않습니다.')
    stream.seek(info.header_offset)
    header = stream.read(30)
    if len(header) != 30:
        raise BackupError('백업 ZIP 항목이 잘렸습니다.')
    values = struct.unpack('<4s5H3L2H', header)
    signature, _, flags, codec, _, _, crc, compressed, expanded, name_size, extra_size = values
    if signature != b'PK\x03\x04' or flags != info.flag_bits or codec != info.compress_type:
        raise BackupError('백업 ZIP의 원본 항목과 목록이 다릅니다.')
    name = stream.read(name_size).decode('utf-8' if flags & 0x800 else 'cp437')
    extra = stream.read(extra_size)
    if name != info.filename or len(extra) != extra_size:
        raise BackupError('백업 ZIP의 파일 이름 또는 확장 정보가 다릅니다.')
    if not flags & 8:
        if compressed == 0xffffffff or expanded == 0xffffffff:
            position, zip64 = 0, None
            while position + 4 <= len(extra):
                tag, size = struct.unpack_from('<HH', extra, position)
                position += 4
                if position + size > len(extra):
                    raise BackupError('백업 ZIP64 항목이 잘렸습니다.')
                if tag == 1:
                    zip64 = extra[position:position + size]
                position += size
            if zip64 is None:
                raise BackupError('백업 ZIP64 용량 정보가 없습니다.')
            position = 0
            if expanded == 0xffffffff:
                expanded = struct.unpack_from('<Q', zip64, position)[0]
                position += 8
            if compressed == 0xffffffff:
                compressed = struct.unpack_from('<Q', zip64, position)[0]
        if crc != info.CRC or compressed != info.compress_size or expanded != info.file_size:
            raise BackupError('백업 ZIP의 크기 또는 CRC 목록이 다릅니다.')
    start = info.header_offset + 30 + name_size + extra_size
    end = start + info.compress_size
    if info.compress_size < 0 or end > central_offset:
        raise BackupError('백업 ZIP의 압축 데이터 범위가 올바르지 않습니다.')
    if flags & 8:
        # Non-seeking writers place CRC/sizes after the payload. Account for
        # this descriptor explicitly so hidden local entries cannot occupy
        # unchecked gaps between the declared inventory and central directory.
        encoding = '<LQQ' if compressed == 0xffffffff or expanded == 0xffffffff else '<LLL'
        size = struct.calcsize(encoding)
        stream.seek(end)
        descriptor = stream.read(min(size + 4, central_offset - end))
        prefixes = (0, 4) if descriptor[:4] == b'PK\x07\x08' else (0,)
        for prefix in prefixes:
            if (len(descriptor) >= prefix + size
                    and struct.unpack_from(encoding, descriptor, prefix)
                    == (info.CRC, info.compress_size, info.file_size)):
                end += prefix + size
                break
        else:
            raise BackupError('백업 ZIP의 후행 CRC 또는 크기 정보가 다릅니다.')
    return start, end


def _stream_member(stream, info, start, expected, sink=None):
    """Count actual DEFLATE output, including forged smaller ZIP size fields."""
    if info.file_size != expected:
        raise BackupError('백업 파일 크기가 manifest와 다릅니다.')
    stream.seek(start)
    remaining, total, checksum = info.compress_size, 0, 0
    hasher = hashlib.sha256()
    decoder = zlib.decompressobj(-zlib.MAX_WBITS) if info.compress_type == zipfile.ZIP_DEFLATED else None
    def emit(content):
        nonlocal total, checksum
        total += len(content)
        if total > expected:
            raise BackupError('실제 압축 해제 크기가 백업에 기록된 제한을 넘었습니다.')
        checksum = zlib.crc32(content, checksum)
        hasher.update(content)
        if sink is not None:
            sink.write(content)
    while remaining:
        block = stream.read(min(_CHUNK, remaining))
        if not block:
            raise BackupError('백업 압축 데이터가 잘렸습니다.')
        remaining -= len(block)
        if decoder is None:
            emit(block)
        else:
            pending = block
            while pending:
                emit(decoder.decompress(pending, min(_CHUNK, expected - total + 1)))
                pending = decoder.unconsumed_tail
                if decoder.unused_data or (decoder.eof and (pending or remaining)):
                    raise BackupError('백업 파일 뒤에 선언되지 않은 압축 데이터가 있습니다.')
    if decoder is not None and (not decoder.eof or decoder.unused_data or decoder.unconsumed_tail):
        raise BackupError('백업 DEFLATE 데이터가 완성되지 않았습니다.')
    if total != expected or checksum & 0xffffffff != info.CRC:
        raise BackupError('백업 파일의 실제 크기 또는 CRC가 기록과 다릅니다.')
    return hasher.hexdigest()


def _verify_archive(path, destination=None):
    with _regular_file(path) as (stream, metadata):
        central_offset, count = _directory_offset(stream, metadata.st_size)
        with zipfile.ZipFile(stream) as archive:
            infos = archive.infolist()
            if len(infos) != count:
                raise BackupError('백업 ZIP의 파일 수가 일치하지 않습니다.')
            members, layouts, spans = {}, {}, []
            for info in infos:
                if info.filename in members:
                    raise BackupError('백업 ZIP에 중복된 파일이 있습니다.')
                members[info.filename] = info
                start, end = _member_layout(stream, info, central_offset)
                layouts[info.filename] = start
                spans.append((info.header_offset, end))
            spans.sort()
            if (spans[0][0] != 0 or spans[-1][1] != central_offset
                    or any(left[1] != right[0] for left, right in zip(spans, spans[1:]))):
                raise BackupError('백업 ZIP 항목이 겹치거나 목록 밖의 파일 데이터가 있습니다.')
            manifest_info = members.get('manifest.json')
            if manifest_info is None or not 0 < manifest_info.file_size <= MAX_MANIFEST_BYTES:
                raise BackupError('백업 manifest가 없거나 8 MiB 제한을 넘었습니다.')
            buffer = io.BytesIO()
            _stream_member(stream, manifest_info, layouts['manifest.json'], manifest_info.file_size, buffer)
            manifest = _parse_manifest(buffer.getvalue())
            expected_names = {'manifest.json'} | {'data/' + item['path'] for item in manifest['files']}
            if set(members) != expected_names:
                raise BackupError('백업에 선언되지 않았거나 빠진 파일이 있습니다.')
            for item in manifest['files']:
                name = 'data/' + item['path']
                if destination is None:
                    actual = _stream_member(stream, members[name], layouts[name], item['bytes'])
                else:
                    target = destination.joinpath(*item['path'].split('/'))
                    target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
                    with target.open('xb') as output:
                        actual = _stream_member(stream, members[name], layouts[name], item['bytes'], output)
                        output.flush()
                        os.fsync(output.fileno())
                if actual != item['sha256']:
                    raise BackupError('백업 파일의 SHA-256이 원래 목록과 다릅니다. 다른 백업을 확인하세요.')
        stream.seek(0)
        digest, read_bytes = hashlib.sha256(), 0
        while block := stream.read(_CHUNK):
            read_bytes += len(block)
            if read_bytes > metadata.st_size:
                raise BackupError('검사 중 백업 ZIP 크기가 바뀌었습니다.')
            digest.update(block)
        if read_bytes != metadata.st_size:
            raise BackupError('검사 중 백업 ZIP이 잘렸습니다.')
    return {
        'status': 'verified', 'application_version': manifest['application_version'],
        'file_count': manifest['file_count'], 'total_bytes': manifest['total_bytes'],
        'archive_bytes': read_bytes, 'archive_sha256': digest.hexdigest(), 'archive_path': str(path),
    }, manifest


def _publish_no_replace(source, destination):
    """Atomically publish a file/directory without replacing even an empty dir.

    Linux: renameat2(RENAME_NOREPLACE), man7.org/linux/man-pages/man2/rename.2.html.
    Darwin: renamex_np(RENAME_EXCL), Apple xnu bsd/sys/stdio.h (flag 0x4).
    Windows: os.rename always rejects existing destinations, Python 3.12 os docs.
    Unsupported kernels/filesystems fail closed; ordinary POSIX rename is unsafe.
    """
    try:
        if os.name == 'nt':
            os.rename(source, destination)
            return
        libc = ctypes.CDLL(None, use_errno=True)
        if sys.platform.startswith('linux'):
            function = getattr(libc, 'renameat2', None)
            if function is None:
                raise OSError(errno.ENOTSUP, 'renameat2 unavailable')
            function.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
            function.restype = ctypes.c_int
            result = function(-100, os.fsencode(source), -100, os.fsencode(destination), 1)
        elif sys.platform == 'darwin':
            function = getattr(libc, 'renamex_np', None)
            if function is None:
                raise OSError(errno.ENOTSUP, 'renamex_np unavailable')
            function.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_uint]
            function.restype = ctypes.c_int
            result = function(os.fsencode(source), os.fsencode(destination), 4)
        else:
            raise OSError(errno.ENOTSUP, 'Exclusive publication unsupported')
        if result != 0:
            code = ctypes.get_errno()
            raise OSError(code, os.strerror(code))
    except OSError as exc:
        if exc.errno in (errno.EEXIST, errno.ENOTEMPTY):
            raise BackupError('대상 경로가 이미 있습니다. 기존 자료는 유지했습니다. 새로운 경로를 선택하세요.') from exc
        if exc.errno in (errno.ENOSYS, errno.EINVAL, errno.ENOTSUP, errno.EOPNOTSUPP):
            raise BackupError('이 파일시스템은 덮어쓰기 없는 원자적 저장을 지원하지 않습니다. 다른 로컬 위치를 선택하세요.') from exc
        raise


@_operation('백업을 만들 수 없습니다. 원본·저장 위치의 접근 권한과 공간, 파일 형식을 확인하세요.')
def create_backup(data_dir: Path, output: Path) -> dict:
    root, target = _absolute(data_dir), _absolute(output)
    metadata = root.lstat()
    if _linked(metadata) or not stat.S_ISDIR(metadata.st_mode):
        raise BackupError('백업 원본은 이미 존재하는 일반 데이터 폴더여야 합니다.')
    if target.is_relative_to(root) or _exists(target):
        raise BackupError('원본 폴더 밖에 있는 새 백업 파일 경로를 선택하세요. 기존 파일은 덮어쓰지 않습니다.')
    temporary = None
    with DataDirectoryLease(root):
        inventory = _inventory(root)
        if not _recognized([name for name, _ in inventory]):
            raise BackupError('기존 3D Printer Agent 작업 공간을 확인하지 못했습니다. 실제 저장 위치를 선택하세요.')
        try:
            descriptor, filename = tempfile.mkstemp(prefix='.printer-agent-backup-', suffix='.tmp', dir=target.parent)
            temporary = Path(filename)
            records, total = [], 0
            with os.fdopen(descriptor, 'w+b') as destination:
                with zipfile.ZipFile(destination, 'w', compression=zipfile.ZIP_DEFLATED, allowZip64=True) as archive:
                    for name, metadata in inventory:
                        info = zipfile.ZipInfo('data/' + name)
                        info.compress_type = zipfile.ZIP_DEFLATED
                        info.create_system = 3
                        info.external_attr = (stat.S_IFREG | 0o600) << 16
                        info.file_size = metadata.st_size
                        hasher, size = hashlib.sha256(), 0
                        with _regular_file(root.joinpath(*name.split('/')), metadata) as (source, _), archive.open(info, 'w') as member:
                            while block := source.read(_CHUNK):
                                size += len(block)
                                total += len(block)
                                if size > metadata.st_size or size > MAX_FILE_BYTES or total > MAX_TOTAL_BYTES:
                                    raise BackupError('백업 중 원본 크기가 변경되거나 용량 제한을 넘었습니다.')
                                hasher.update(block)
                                member.write(block)
                        if size != metadata.st_size:
                            raise BackupError('백업 중 원본 파일이 잘렸습니다. 다른 프로그램의 쓰기를 멈추세요.')
                        records.append({'path': name, 'bytes': size, 'sha256': hasher.hexdigest()})
                    manifest = {'format': _FORMAT, 'version': 1, 'application_version': __version__,
                                'created_at': datetime.now(timezone.utc).isoformat(), 'file_count': len(records),
                                'total_bytes': total, 'files': records}
                    content = json.dumps(manifest, ensure_ascii=False, separators=(',', ':'), allow_nan=False).encode('utf-8')
                    if len(content) > MAX_MANIFEST_BYTES:
                        raise BackupError('백업 manifest가 8 MiB 제한을 넘었습니다.')
                    archive.writestr('manifest.json', content)
                destination.flush()
                os.fsync(destination.fileno())
            current = _inventory(root)
            if ([(name, _fingerprint(meta)) for name, meta in current]
                    != [(name, _fingerprint(meta)) for name, meta in inventory]):
                raise BackupError('백업 중 원본 파일 목록이 바뀌었습니다. 쓰기를 멈추고 다시 시도하세요.')
            report, _ = _verify_archive(temporary)
            _publish_no_replace(temporary, target)
            temporary = None
            return {**report, 'status': 'created', 'archive_path': str(target)}
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)


@_operation('백업을 검증할 수 없습니다. 완전한 백업 파일과 접근 권한을 확인하세요.')
def inspect_backup(archive: Path) -> dict:
    report, _ = _verify_archive(_absolute(archive))
    return report


@_operation('백업을 복원할 수 없습니다. 백업 파일과 새 대상 폴더의 접근 권한·공간을 확인하세요.')
def restore_backup(archive: Path, destination: Path) -> dict:
    from .runtime import require_compatible_data
    source, target = _absolute(archive), _absolute(destination)
    if _exists(target):
        raise BackupError('복원 대상이 이미 있습니다. 기존 자료는 유지했습니다. 새 폴더 이름을 선택하세요.')
    staging = Path(tempfile.mkdtemp(prefix='.printer-agent-restore-', dir=target.parent))
    try:
        report, manifest = _verify_archive(source, staging)
        if not _recognized([item['path'] for item in manifest['files']]):
            raise BackupError('복원할 데이터에 3D Printer Agent 작업 공간 기록이 없습니다.')
        require_compatible_data(staging)
        _publish_no_replace(staging, target)
        staging = None
        return {**report, 'status': 'restored', 'data_dir': str(target)}
    finally:
        if staging is not None:
            shutil.rmtree(staging)
