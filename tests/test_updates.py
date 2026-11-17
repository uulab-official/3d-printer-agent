"""The explicit new-version check: one anonymous read, honest outcomes, no install."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import httpx
from fastapi.testclient import TestClient

from print_agent import __version__, updates
from print_agent.app import create_app


def transport(status=200, body=None, raw=None, error=None):
    seen = []

    def handler(request):
        seen.append(request)
        if error:
            raise error
        content = raw if raw is not None else json.dumps(body if body is not None else {}).encode()
        return httpx.Response(status, content=content)
    return httpx.MockTransport(handler), seen


def release(tag, **extra):
    return {'tag_name': tag, 'html_url': f'https://github.com/{updates.REPOSITORY}/releases/tag/{tag}',
            'published_at': '2026-11-17T06:35:19Z', 'draft': False, 'prerelease': False, **extra}


class UpdateCheckTests(unittest.TestCase):
    def bump(self, delta):
        major, minor, patch_ = updates.parse_version(__version__)
        return f'v{major}.{minor + delta}.{patch_}' if minor + delta >= 0 else 'v0.0.0'

    def test_newer_same_and_older_releases(self):
        for tag, status in ((self.bump(1), 'update_available'), (f'v{__version__}', 'up_to_date'), (self.bump(-1), 'ahead')):
            with self.subTest(tag=tag):
                mock, seen = transport(body=release(tag))
                result = updates.check_for_update(transport=mock)
                self.assertEqual(result['status'], status)
                self.assertEqual(result['current_version'], __version__)
                self.assertEqual(str(seen[0].url), updates.LATEST_URL)
                self.assertEqual(seen[0].method, 'GET')
                self.assertNotIn('cookie', {key.lower() for key in seen[0].headers})

    def test_unusable_answers_are_reported_not_trusted(self):
        cases = [dict(status=500, body={}), dict(raw=b'not json'), dict(body={'tag_name': 'latest'}),
                 dict(body=release('v99.0.0', draft=True)), dict(body=release('v99.0.0', prerelease=True)),
                 dict(raw=b'x' * (updates.MAX_RESPONSE_BYTES + 1)), dict(error=httpx.ConnectError('offline'))]
        for case in cases:
            with self.subTest(case=str(case)[:60]):
                mock, _ = transport(**case)
                result = updates.check_for_update(transport=mock)
                self.assertEqual(result['status'], 'unavailable')
                self.assertIsNone(result['latest_version'])

    def test_release_link_must_point_at_this_repository(self):
        mock, _ = transport(body=release('v99.0.0', html_url='https://evil.example/download'))
        result = updates.check_for_update(transport=mock)
        self.assertEqual(result['status'], 'update_available')
        self.assertEqual(result['release_url'], updates.RELEASES_PAGE)

    def test_api_requires_the_session_and_never_runs_on_bootstrap(self):
        with tempfile.TemporaryDirectory() as temp, TestClient(create_app(Path(temp), test_mode=True)) as client:
            with patch.object(updates, 'check_for_update', return_value={'status': 'up_to_date'}) as check:
                headers = {'X-Session-Token': client.get('/api/bootstrap').json()['session_token']}
                check.assert_not_called()
                self.assertEqual(client.post('/api/updates/check', json={}).status_code, 403)
                self.assertEqual(client.post('/api/updates/check', json={}, headers=headers).json(), {'status': 'up_to_date'})
                check.assert_called_once()


if __name__ == '__main__':
    unittest.main()
