const { test, expect } = require('@playwright/test');

// The check runs only on request; the response is synthetic so the test needs no network.
test('the new-version check runs only when asked and links the release and update guide', async ({ page }) => {
  const calls = [];
  await page.route('**/api/updates/check', async route => {
    calls.push(route.request().postDataJSON());
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({
      schema_version: 1, status: 'update_available', detail: '새 버전 9.9.9이 있습니다.', current_version: '0.22.0',
      latest_version: '9.9.9', published_at: '2026-11-17T06:35:19Z',
      release_url: 'https://github.com/uulab-official/3d-printer-agent/releases/tag/v9.9.9',
      update_guide: 'https://github.com/uulab-official/3d-printer-agent/blob/main/docs/RELEASES.md' }) });
  });
  await page.goto('/');
  await expect(page.locator('#generate-button')).toBeEnabled();
  expect(calls).toEqual([]);
  await page.locator('#storage-details > summary').click();
  await page.locator('#update-check').click();
  await expect(page.locator('#update-result')).toContainText('최신 9.9.9');
  await expect(page.locator('#update-result a')).toHaveCount(2);
  await expect(page.locator('#update-result a').first()).toHaveAttribute('rel', 'noopener noreferrer');
  expect(calls).toEqual([{}]);
});
