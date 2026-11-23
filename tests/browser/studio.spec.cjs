const { test, expect } = require('@playwright/test');

// Modeling studio: the 3D view in the middle, a live mesh preview while the draft changes
// (nothing stored; the API test checks the job list), and a generated CAD model only from the explicit generate button.

test.beforeEach(async ({ page }) => {
  page.__errors = [];
  page.on('pageerror', error => page.__errors.push(String(error)));
  await page.goto('/');
  await expect(page.locator('#generate-button')).toBeEnabled();
});

test.afterEach(async ({ page }) => {
  expect(page.__errors).toEqual([]);
});

test('the studio opens on a live preview that stores nothing and follows the dimensions', async ({ page, isMobile }) => {
  const status = page.locator('#preview-status');
  await expect(status).toHaveText('실시간 미리보기 · 파일 생성 전', { timeout: 20_000 });
  await expect(page.locator('#model-canvas')).toBeVisible();
  await expect(page.locator('#model-result')).toBeHidden();
  await expect(page.locator('#download-links a')).toHaveCount(0);
  await expect(page.locator('#preview-caption')).toContainText('120 × 80 × 35 mm');
  if (!isMobile) {
    // The view sits beside the templates and the dimensions, and starts above the fold.
    const [rail, stage, inspector] = await Promise.all(['.studio-rail', '#preview-stage', '.studio-inspector'].map(s => page.locator(s).boundingBox()));
    expect(rail.x + rail.width).toBeLessThanOrEqual(stage.x);
    expect(stage.x + stage.width).toBeLessThanOrEqual(inspector.x);
    expect(stage.y).toBeLessThan(page.viewportSize().height / 2);
    expect(stage.height).toBeGreaterThan(420);
  }

  const previewed = page.waitForResponse(r => r.url().endsWith('/api/models/preview') && r.request().method() === 'POST');
  await page.locator('#parameter-width').fill('150');
  const response = await previewed;
  expect(response.status()).toBe(200);
  expect((await response.json()).preview_only).toBe(true);
  await expect(page.locator('#preview-caption')).toContainText('150 × 80 × 35 mm');
  await expect(status).toHaveText('실시간 미리보기 · 파일 생성 전');
  await expect(page.locator('#model-result')).toBeHidden();

  // An invalid value is never drawn as current.
  await page.locator('#parameter-width').fill('5');
  await expect(status).toHaveText('치수 확인 필요');
  await page.locator('#parameter-width').fill('150');
  await expect(status).toHaveText('실시간 미리보기 · 파일 생성 전');

  // Only the generate button makes files; the result is the real CAD mesh.
  const generated = page.waitForResponse(r => r.url().endsWith('/api/models') && r.request().method() === 'POST');
  await page.locator('#generate-button').click();
  expect((await generated).status()).toBe(200);
  await expect(status).toHaveText('실제 CAD 메시');
  await expect(page.locator('#model-result')).toBeVisible();
  await expect(page.locator('#download-links a').first()).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1)).toBe(true);
});

test('live preview can be turned off, is remembered, and template changes redraw it', async ({ page }) => {
  const status = page.locator('#preview-status');
  await expect(status).toHaveText('실시간 미리보기 · 파일 생성 전', { timeout: 20_000 });
  await page.locator('#preview-live').uncheck();
  await expect(page.locator('#model-canvas')).toBeHidden();
  await expect(status).toHaveText('아직 생성 전');
  await page.reload();
  await expect(page.locator('#generate-button')).toBeEnabled();
  await expect(page.locator('#preview-live')).not.toBeChecked();
  await page.locator('#parameter-height').fill('40');
  await page.waitForTimeout(900);
  await expect(page.locator('#model-canvas')).toBeHidden();

  await page.locator('#preview-live').check();
  await expect(status).toHaveText('실시간 미리보기 · 파일 생성 전', { timeout: 20_000 });
  await page.locator('.template-card[data-template="keycap"]').click();
  const confirm = page.locator('#model-confirm-replace');
  if (await confirm.isVisible()) await confirm.click();
  await expect(page.locator('#parameter-key_units')).toBeVisible();
  await expect(status).toHaveText('실시간 미리보기 · 파일 생성 전', { timeout: 20_000 });
  await expect(page.locator('#preview-caption')).toContainText('18 × 18 × 8 mm');
});
