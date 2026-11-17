"""Explicit, read-only check for a newer published release.

Runs only when the person asks. It sends one anonymous GET for the public
"latest release" record of this repository and nothing about the user, their
data or this installation. It never downloads or installs anything; the
person follows the documented update steps (backup, verify the wheel hash,
install) themselves.
"""
from __future__ import annotations

import re

import httpx

from . import __version__

REPOSITORY = 'uulab-official/3d-printer-agent'
LATEST_URL = f'https://api.github.com/repos/{REPOSITORY}/releases/latest'
RELEASES_PAGE = f'https://github.com/{REPOSITORY}/releases'
UPDATE_GUIDE = f'https://github.com/{REPOSITORY}/blob/main/docs/RELEASES.md'
_VERSION = re.compile(r'v?(\d+)\.(\d+)\.(\d+)')
MAX_RESPONSE_BYTES = 256 * 1024


def parse_version(text) -> tuple[int, int, int] | None:
    match = _VERSION.fullmatch(text.strip()) if isinstance(text, str) else None
    return tuple(int(part) for part in match.groups()) if match else None


def _result(status, detail, **values):
    return {'schema_version': 1, 'status': status, 'detail': detail, 'current_version': __version__,
            'latest_version': None, 'published_at': None, 'release_url': RELEASES_PAGE,
            'update_guide': UPDATE_GUIDE, **values}


def check_for_update(*, transport: httpx.BaseTransport | None = None, timeout: float = 6.0) -> dict:
    """Return whether the latest published release is newer. Never raises for network outcomes."""
    current = parse_version(__version__)
    try:
        with httpx.Client(timeout=timeout, trust_env=False, follow_redirects=False, transport=transport,
                          headers={'Accept': 'application/vnd.github+json', 'User-Agent': '3d-printer-agent-update-check'}) as client:
            response = client.get(LATEST_URL)
    except httpx.HTTPError:
        return _result('unavailable', '릴리스 정보를 가져오지 못했습니다. 인터넷 연결을 확인한 뒤 다시 시도하세요.')
    if response.status_code != 200 or len(response.content) > MAX_RESPONSE_BYTES:
        return _result('unavailable', f'릴리스 정보를 확인하지 못했습니다(HTTP {response.status_code}).')
    try:
        data = response.json()
    except ValueError:
        return _result('unavailable', '릴리스 정보 형식을 읽지 못했습니다.')
    tag = data.get('tag_name') if isinstance(data, dict) else None
    latest = parse_version(tag)
    if latest is None or current is None or data.get('draft') or data.get('prerelease'):
        return _result('unavailable', '공개된 정식 릴리스 버전을 확인하지 못했습니다.')
    url = data.get('html_url')
    release_url = url if isinstance(url, str) and url.startswith(f'https://github.com/{REPOSITORY}/releases/') else RELEASES_PAGE
    published = data.get('published_at') if isinstance(data.get('published_at'), str) else None
    values = {'latest_version': '.'.join(map(str, latest)), 'published_at': published, 'release_url': release_url}
    if latest > current:
        return _result('update_available', f'새 버전 {values["latest_version"]}이 있습니다. 업데이트 전에 전체 작업을 백업하고, 내려받은 wheel의 SHA-256을 릴리스 안내와 비교하세요.', **values)
    if latest == current:
        return _result('up_to_date', '최신 버전을 쓰고 있습니다.', **values)
    return _result('ahead', '공개된 최신 릴리스보다 새 버전입니다(개발 중인 소스).', **values)
