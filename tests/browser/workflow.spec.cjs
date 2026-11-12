const fs = require('node:fs/promises');
const crypto = require('node:crypto');
const { test, expect } = require('@playwright/test');

// The server and CAD engine are real. No network routes or CAD results are mocked.
async function openView(page, view) {
  const menu = page.locator('#menu-toggle');
  if (await menu.isVisible()) await menu.click();
  await page.locator(`.nav-item[data-view="${view}"]`).click();
  await expect(page.locator(`#view-${view}`)).toBeVisible();
}

async function noHorizontalOverflow(page) {
  await expect.poll(() => page.evaluate(() =>
    document.documentElement.scrollWidth <= window.innerWidth + 1
  )).toBe(true);
}

test.beforeEach(async ({ page }) => {
  const errors = [];
  page.__expectedHttpFailures = [];
  page.on('pageerror', error => errors.push(String(error)));
  page.on('console', message => {
    // HTTP failures are checked with their URL and status below, including the
    // intentionally rejected model in the failure-history regression.
    if (message.type() === 'error' && !message.text().startsWith('Failed to load resource: the server responded with a status of')) errors.push(message.text());
  });
  page.on('response', response => {
    if (response.status() < 400) return;
    if (page.__expectedHttpFailures.some(item => response.url().endsWith(item.path) && response.status() === item.status)) return;
    errors.push(`${response.status()} ${response.url()}`);
  });
  page.on('requestfailed', request => {
    const error = request.failure()?.errorText;
    if (request.url().endsWith('/files/three_mf') && error === 'net::ERR_ABORTED') return;
    errors.push(`${request.url()}: ${error}`);
  });
  page.__errors = errors;
  await page.goto('/');
  await expect(page.locator('#generate-button')).toBeEnabled();
  await expect(page.locator('#template-cards .template-card')).toHaveCount(3);
  await expect(page.locator('#plan-mode option[value="llm"]')).toHaveJSProperty('disabled', true);
  await expect(page.locator('#environment-badge')).toContainText('사용 불가');
  await noHorizontalOverflow(page);
});

test.afterEach(async ({ page }) => {
  expect(page.__errors).toEqual([]);
});

test('Korean request creates real CAD, downloads it, records an outcome, and invalidates an old preview', async ({ page }, testInfo) => {
  await page.locator('#request-text').fill('가로 12cm 세로 8cm 높이 3.5cm 수납함을 3칸으로 만들어줘');
  await page.locator('#plan-button').click();
  await expect(page.locator('#parameter-width')).toHaveValue('120');
  await expect(page.locator('#parameter-depth')).toHaveValue('80');
  await expect(page.locator('#parameter-height')).toHaveValue('35');
  await expect(page.locator('#parameter-dividers')).toHaveValue('2');
  await expect(page.locator('#generate-button')).toBeEnabled();

  const responsePromise = page.waitForResponse(response =>
    response.url().endsWith('/api/models') && response.request().method() === 'POST');
  await page.locator('#generate-button').click();
  const response = await responsePromise;
  expect(response.status()).toBe(200);
  const job = await response.json();
  expect(job.result.geometry_status).toBe('validated');
  expect(job.result.print_status).toBe('not_tested');
  expect(job.result.dimensions_mm).toEqual({ x: 120, y: 80, z: 35 });
  expect(job.result.parameters.dividers).toBe(2);
  expect(job.result.mesh.faces.length).toBeGreaterThan(0);

  await expect(page.locator('#model-result')).toBeVisible();
  await expect(page.locator('#model-metrics')).toContainText('120 × 80 × 35 mm');
  const canvas = page.locator('#model-canvas');
  await expect(canvas).toBeVisible();
  await expect.poll(() => canvas.evaluate(element => {
    const pixels = element.getContext('2d').getImageData(0, 0, element.width, element.height).data;
    let opaque = 0;
    for (let index = 3; index < pixels.length; index += 4) if (pixels[index] === 255) opaque++;
    return opaque;
  })).toBeGreaterThan(1000);
  const beforeZoom = await canvas.evaluate(element => element.toDataURL());
  await page.locator('#zoom-in').click();
  await expect.poll(() => canvas.evaluate(element => element.toDataURL())).not.toBe(beforeZoom);
  await page.locator('#reset-view').click();
  await page.locator('.preview-card').screenshot({ path: testInfo.outputPath('real-cad-preview.png') });

  const manifestResponse = await page.request.get(job.artifacts.manifest);
  expect(manifestResponse.ok()).toBe(true);
  const manifest = await manifestResponse.json();
  const downloadPromise = page.waitForEvent('download');
  await page.locator('#download-links a').filter({ hasText: '3MF 형상' }).click();
  const download = await downloadPromise;
  const file = testInfo.outputPath('downloaded-model.3mf');
  await download.saveAs(file);
  const content = await fs.readFile(file);
  expect(content.subarray(0, 2).toString()).toBe('PK');
  expect(crypto.createHash('sha256').update(content).digest('hex')).toBe(manifest.artifacts.three_mf.sha256);

  const notes = `Browser CI: ${testInfo.project.name}; no physical print performed.`;
  await page.locator('#outcome-result').selectOption('not_tested');
  await page.locator('#outcome-notes').fill(notes);
  const savedPromise = page.waitForResponse(result => result.url().endsWith(`/api/jobs/${job.id}/outcome`));
  await page.locator('#save-outcome').click();
  const saved = await (await savedPromise).json();
  expect(saved.user_outcome.source).toBe('user_reported');
  expect(saved.result.print_status).toBe('not_tested');
  await expect(page.locator('#save-outcome')).toBeEnabled();
  await openView(page, 'history');
  const card = page.locator('.history-item').filter({ hasText: job.title }).first();
  await expect(card).toBeVisible();
  await card.getByRole('button', { name: '열기' }).click();
  await expect(page.locator('#model-result')).toBeVisible();
  await expect(page.locator('#outcome-notes')).toHaveValue(notes);
  await expect(page.locator('#generate-button')).toBeEnabled();

  await page.locator('.template-card[data-template="cable_comb"]').click();
  await expect(page.locator('#model-result')).toBeHidden();
  await expect(canvas).toBeHidden();
  await expect(page.locator('#download-links a')).toHaveCount(0);
  await expect(page.locator('#parameter-slots')).toHaveValue('5');
  await noHorizontalOverflow(page);
  await page.screenshot({ path: testInfo.outputPath('workspace.png'), fullPage: true });
});

test('missing material evidence and unknown shipping remain visible', async ({ page }, testInfo) => {
  await openView(page, 'profiles');
  await page.locator('#profile-json').fill('{}');
  const profilePromise = page.waitForResponse(response => response.url().endsWith('/api/profiles/review'));
  await page.locator('#review-profile').click();
  const profile = await (await profilePromise).json();
  expect(profile.decision).toBe('needs_input');
  expect(profile.can_prepare_profile).toBe(false);
  await expect(page.locator('#profile-decision')).toHaveText('정보 입력 필요');
  await noHorizontalOverflow(page);

  await openView(page, 'offers');
  for (const [index, name, price, grams, shipping] of [
    [1, 'A', '12000', '1000', '3000'],
    [2, 'B', '7000', '500', '0'],
    [3, 'C', '9000', '1000', ''],
  ]) {
    for (const [field, value] of Object.entries({ name, price, grams, shipping })) {
      await page.locator(`#offer-${index}-${field}`).fill(value);
    }
  }
  const comparisonPromise = page.waitForResponse(response => response.url().endsWith('/api/offers/compare'));
  await page.locator('#compare-offers').click();
  const comparison = await (await comparisonPromise).json();
  expect(comparison.live_prices).toBe(false);
  expect(comparison.groups.KRW[0].name).toBe('B');
  expect(comparison.groups.KRW[0].price_per_kg).toBe(14000);
  expect(comparison.groups.KRW[2].price_per_kg).toBeNull();
  await expect(page.locator('#offers-result')).toBeVisible();
  await expect(page.locator('#offer-comparison tbody tr').first().locator('td').first()).toHaveText('B');
  await expect(page.locator('#offer-comparison')).toContainText('14,000');
  await expect(page.locator('#offer-comparison')).toContainText('15,000');
  await expect(page.locator('#offer-comparison')).toContainText('배송비 미확인');
  await noHorizontalOverflow(page);
  await page.screenshot({ path: testInfo.outputPath('price-comparison.png'), fullPage: true });

  await expect(page.locator('#compare-offers')).toBeEnabled();
  await page.locator('#offer-1-price').fill('13000');
  await expect(page.locator('#offers-result')).toBeHidden();
});

test('a rejected CAD request remains inspectable in history without a fake model', async ({ page }, testInfo) => {
  await page.locator('#parameter-width').fill('10');
  await page.locator('#parameter-depth').fill('10');
  await page.locator('#parameter-height').fill('2');
  await page.locator('#parameter-wall').fill('8');
  page.__expectedHttpFailures.push({ path: '/api/models', status: 422 });
  const rejectedPromise = page.waitForResponse(response =>
    response.url().endsWith('/api/models') && response.request().method() === 'POST');
  await page.locator('#generate-button').click();
  const rejected = await rejectedPromise;
  expect(rejected.status()).toBe(422);
  const failure = await rejected.json();
  expect(typeof failure.detail).toBe('string');
  expect(failure.detail.length).toBeGreaterThan(0);
  await expect(page.locator('#model-feedback')).toContainText(failure.detail);
  await expect(page.locator('#model-result')).toBeHidden();
  await expect(page.locator('#generate-button')).toBeEnabled();

  await openView(page, 'history');
  const failed = page.locator('.history-item').filter({ hasText: '모델 생성 실패' }).first();
  await expect(failed).toBeVisible();
  await failed.getByRole('button', { name: '기록 보기' }).click();
  await expect(page.locator('#history-feedback')).toContainText(failure.detail);
  await expect(page.locator('#model-result')).toBeHidden();
  await expect(page.locator('#model-canvas')).toBeHidden();
  await noHorizontalOverflow(page);
  await page.screenshot({ path: testInfo.outputPath('failed-job-history.png'), fullPage: true });
});
