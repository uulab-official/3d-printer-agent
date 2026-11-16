const { test, expect } = require('@playwright/test');

// Real server and real CAD generation. The printability review is advisory and
// uses a stated 0.4 mm reference nozzle; it is not a slicer or physical result.

async function generate(page, values) {
  for (const [field, value] of Object.entries(values)) await page.locator(`#parameter-${field}`).fill(value);
  const generated = page.waitForResponse(r => r.url().endsWith('/api/models') && r.request().method() === 'POST');
  await page.locator('#generate-button').click();
  const response = await generated;
  expect(response.status()).toBe(200);
  return (await response.json()).result;
}

test.beforeEach(async ({ page }) => {
  page.__previewErrors = [];
  page.on('pageerror', error => page.__previewErrors.push(String(error)));
  await page.goto('/');
  await expect(page.locator('#generate-button')).toBeEnabled();
});

test.afterEach(async ({ page }) => {
  expect(page.__previewErrors).toEqual([]);
});

test('thin wall warning leads to the field, and the regenerated model passes', async ({ page }) => {
  const first = await generate(page, { width: '120', depth: '80', height: '35', wall: '0.8', dividers: '2' });
  expect(first.printability.status).toBe('review');
  const review = page.locator('#printability-review');
  await expect(review).toBeVisible();
  await expect(page.locator('#printability-status')).toHaveText('확인할 점이 있어요');
  const thin = review.locator('[data-check="min_thickness"]');
  await expect(thin).toHaveClass(/is-warn/);
  await expect(thin).toContainText('0.80 mm (바깥 벽)');
  await expect(review.locator('[data-check="fit_clearance"]')).toHaveCount(0);
  await thin.getByRole('button', { name: '이 치수 고치기 →' }).click();
  await expect(page.locator('#parameter-wall')).toBeFocused();
  await page.locator('#parameter-wall').fill('1.2');
  await expect(page.locator('#model-result')).toBeHidden();
  const second = await generate(page, {});
  expect(second.printability.status).toBe('ok');
  await expect(page.locator('#printability-status')).toHaveText('형상 점검 통과');
  await expect(review.locator('[data-check="min_thickness"]')).toContainText('1.20 mm');
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1)).toBe(true);
});

test('preview view presets, toggles and toolbar stay inside the stage', async ({ page }) => {
  await generate(page, { width: '120', depth: '80', height: '35' });
  const stage = await page.locator('#preview-stage').boundingBox();
  const card = await page.locator('.preview-card').boundingBox();
  expect(stage.x + stage.width).toBeLessThanOrEqual(card.x + card.width + 1);
  const tools = await page.locator('#preview-tools').boundingBox();
  expect(tools.x + tools.width).toBeLessThanOrEqual(stage.x + stage.width + 1);
  for (const view of ['front', 'side', 'top', 'iso']) {
    const button = page.locator(`[data-preview-view="${view}"]`);
    await button.click();
    await expect(button).toHaveAttribute('aria-pressed', 'true');
    await expect(page.locator('[data-preview-view][aria-pressed="true"]')).toHaveCount(1);
  }
  await page.locator('#preview-dimensions').uncheck();
  await page.locator('#preview-overhangs').uncheck();
  await expect(page.locator('#model-canvas')).toBeVisible();
  // A drag switches the selection back to a custom view.
  const canvas = await page.locator('#model-canvas').boundingBox();
  await page.mouse.move(canvas.x + canvas.width / 2, canvas.y + canvas.height / 2);
  await page.mouse.down();
  await page.mouse.move(canvas.x + canvas.width / 2 + 40, canvas.y + canvas.height / 2 + 10);
  await page.mouse.up();
  await expect(page.locator('[data-preview-view][aria-pressed="true"]')).toHaveCount(0);
});
