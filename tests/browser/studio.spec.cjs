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


test('the viewport stays clear: the printer and the first-run card sit in the panel and the plate fit is one chip', async ({ page, isMobile }) => {
  // Layout only: the plate is a recorded size for viewing, not a slice or a printer connection.
  await page.evaluate(() => { try { localStorage.removeItem('printAgent.welcomeDismissed'); } catch {} });
  await page.reload();
  await expect(page.locator('#generate-button')).toBeEnabled();
  const panel = page.locator('.studio-panel');
  await expect(panel.locator('#welcome')).toBeVisible();
  await expect(panel.locator('#preview-bed')).toBeVisible();
  await page.locator('#preview-bed').selectOption('bambu-n2s');
  await expect(page.locator('#preview-bed-legend')).toContainText('출처:');
  const fit = page.locator('#preview-bed-fit');
  await expect(fit).toContainText('Bambu Lab A1 출력판(256 × 256 × 높이 256 mm)에 들어갑니다.', { timeout: 20_000 });
  await expect(fit).toHaveClass(/viewport-chip/);
  await expect(fit).toHaveClass(/is-success/);
  // The whole sentence stays available as a tooltip and to assistive technology.
  expect(await fit.getAttribute('title')).toContain('남는 공간');
  await expect(page.locator('#preview-caption')).toHaveAttribute('title', /120 × 80 × 35 mm/);
  await expect(page.locator('#preview-caption')).toBeVisible();
  if (!isMobile) {
    // Nothing but one-line chips at the bottom of the viewport; no card over the model.
    const [stage, welcome, chip, caption] = await Promise.all(['#preview-stage', '#welcome', '#preview-bed-fit', '#preview-caption'].map(s => page.locator(s).boundingBox()));
    expect(welcome.x + welcome.width).toBeLessThanOrEqual(stage.x + 1);
    expect(chip.height).toBeLessThan(34);
    expect(caption.height).toBeLessThan(24);
    expect(chip.y).toBeGreaterThan(stage.y + stage.height * 0.8);
  }
});

test('dimension changes undo and redo like a design tool, and a new template starts a new history', async ({ page }) => {
  // The draft only: restored values go through the same change path, so the live preview follows them.
  const width = page.locator('#parameter-width'), depth = page.locator('#parameter-depth');
  const undo = page.locator('#draft-undo'), redo = page.locator('#draft-redo');
  await expect(page.locator('#preview-caption')).toContainText('120 × 80 × 35 mm', { timeout: 20_000 });
  await expect(undo).toBeDisabled();
  await expect(redo).toBeDisabled();

  await width.fill('150');
  await expect(undo).toBeEnabled();
  await expect(redo).toBeDisabled();
  await page.waitForTimeout(700);  // one history step per pause
  const more = page.locator('[data-step-for="depth"][data-direction="1"]');
  await more.click();
  await more.click();
  await expect(depth).toHaveValue('82');
  await page.waitForTimeout(700);

  await page.keyboard.press('ControlOrMeta+z');  // focus is on the +/- button, not a text box
  await expect(depth).toHaveValue('80');
  await expect(width).toHaveValue('150');
  await expect(redo).toBeEnabled();
  await undo.click();
  await expect(width).toHaveValue('120');
  await expect(undo).toBeDisabled();
  await expect(page.locator('#preview-caption')).toContainText('120 × 80 × 35 mm', { timeout: 20_000 });

  await page.keyboard.press('ControlOrMeta+Shift+z');
  await expect(width).toHaveValue('150');
  await redo.click();
  await expect(depth).toHaveValue('82');
  await expect(redo).toBeDisabled();
  await expect(page.locator('#preview-caption')).toContainText('150 × 82 × 35 mm', { timeout: 20_000 });

  // A new edit after an undo drops the redo branch.
  await undo.click();
  await expect(depth).toHaveValue('80');
  await width.fill('140');
  await expect(redo).toBeDisabled();

  // Inside a number box the browser's own undo applies; the shortcut does not jump the draft.
  await width.focus();
  await page.keyboard.press('ControlOrMeta+z');
  await expect(depth).toHaveValue('80');

  // Another template is a new draft with its own history.
  await page.locator('.template-card[data-template="magnet_frame"]').click();
  const confirm = page.locator('#model-confirm-replace');
  if (await confirm.isVisible()) await confirm.click();
  await expect(page.locator('.template-card[data-template="magnet_frame"]')).toHaveAttribute('aria-pressed', 'true');
  await expect(undo).toBeDisabled();
  await expect(redo).toBeDisabled();
});
