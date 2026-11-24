const { test, expect } = require('@playwright/test');
const { installStudioTabs } = require('./studio-tabs.cjs');

test.beforeEach(({ page }) => installStudioTabs(page));

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
    // A full-window workspace: the settings panel on the left, the viewport filling the rest
    // from just under the studio header to the bottom of the window, and the app menu folded
    // into an icon rail.
    const viewport = page.viewportSize();
    const [panel, stage, header] = await Promise.all(['.studio-panel', '#preview-stage', '.studio-header'].map(s => page.locator(s).boundingBox()));
    expect(panel.x + panel.width).toBeLessThanOrEqual(stage.x + 1);
    expect(stage.y).toBeLessThanOrEqual(header.y + header.height + 1);
    // The viewport reaches the status bar at the bottom of the window.
    const bar = await page.locator('.studio-statusbar').boundingBox();
    expect(stage.y + stage.height).toBeGreaterThanOrEqual(bar.y - 1);
    expect(bar.y + bar.height).toBeGreaterThanOrEqual(viewport.height - 1);
    expect(stage.x + stage.width).toBeGreaterThanOrEqual(viewport.width - 2);
    expect((await page.locator('.sidebar').boundingBox()).width).toBeLessThanOrEqual(72);
    await expect(page.locator('.topbar')).toBeHidden();
    // The viewport is dark, unlike the other screens.
    const background = await page.locator('.studio-viewport').evaluate(element => getComputedStyle(element).backgroundColor);
    const [r, g, b] = background.match(/\d+/g).map(Number);
    expect(r + g + b).toBeLessThan(300);
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
  if (!isMobile && page.viewportSize().width > 1180) {
    // The file result opens as a panel on the right of the viewport.
    const [stage, result] = await Promise.all(['#preview-stage', '#model-result'].map(s => page.locator(s).boundingBox()));
    expect(stage.x + stage.width).toBeLessThanOrEqual(result.x + 1);
  }
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

test('studio tabs swap the workspace and links to another tab open it', async ({ page, isMobile }) => {
  await expect(page.locator('#studio-panel-prepare')).toBeVisible();
  await expect(page.locator('#studio-panel-print')).toBeHidden();
  await page.locator('#studio-tab-discover').click();
  await expect(page.locator('#studio-tab-discover')).toHaveAttribute('aria-selected', 'true');
  await expect(page.locator('#discovery-cards')).toBeVisible();
  await expect(page.locator('#studio-panel-prepare')).toBeHidden();
  // Keyboard: arrows move between tabs.
  await page.locator('#studio-tab-discover').press('ArrowRight');
  await expect(page.locator('#studio-tab-print')).toBeFocused();
  await expect(page.locator('#slicer-heading')).toBeVisible();
  await page.locator('#studio-tab-prepare').click();
  // A link into another tab opens it (the template list links to the starting points).
  await page.getByRole('link', { name: '시작점 둘러보기' }).click();
  await expect(page.locator('#studio-panel-discover')).toBeVisible();
  if (!isMobile) expect(await page.evaluate(() => document.documentElement.scrollHeight <= window.innerHeight + 1)).toBe(true);
});

