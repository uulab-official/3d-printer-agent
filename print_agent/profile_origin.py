"""Import receipts stay separate from profile settings and publisher claims."""
import re


_FIELDS = {'type', 'archive_name', 'archive_sha256', 'member_path', 'member_sha256'}


def copy_archive_origin(value):
    """Validate and copy supplied byte identity; this does not authenticate it.

    The importer computes these hashes from received bytes. Later workspace and
    review requests carry user-supplied receipts, never verified authority.
    """
    if not isinstance(value, dict) or set(value) != _FIELDS:
        raise ValueError('가져오기 정보에는 type, archive_name, archive_sha256, member_path, member_sha256이 필요합니다.')
    if value['type'] != 'bambu_preset_archive':
        raise ValueError('지원하는 가져오기 정보는 bambu_preset_archive입니다.')
    for field in ('archive_name', 'member_path'):
        item = value[field]
        if not isinstance(item, str) or not item.strip() or len(item) > 240:
            raise ValueError('가져온 묶음과 내부 파일 이름은 1자 이상 240자 이하의 문자열이어야 합니다.')
        try:
            item.encode('utf-8')
        except UnicodeError as exc:
            raise ValueError('가져오기 정보에 올바른 문자열이 필요합니다.') from exc
    for field in ('archive_sha256', 'member_sha256'):
        item = value[field]
        if not isinstance(item, str) or not re.fullmatch(r'[0-9a-f]{64}', item):
            raise ValueError('가져오기 정보의 SHA-256은 소문자 16진수 64자리여야 합니다.')
    return dict(value)
