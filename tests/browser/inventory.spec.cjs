const { test, expect } = require('@playwright/test');
const { installStudioTabs } = require('./studio-tabs.cjs');

test.beforeEach(({ page }) => installStudioTabs(page));

// Real server and storage. Only the generated job is marked as sliced with a 12.5 g
// slicer estimate (synthetic; the browser CI has no Bambu Studio), so the outcome card
// can offer the deduction.
async function openView(page, view) {
  const menu = page.locator('#menu-toggle');
  if (await menu.isVisible()) await menu.click();
  await page.locator(`.nav-item[data-view="${view}"]`).click();
  await expect(page.locator(`#view-${view}`)).toBeVisible();
}

test('spools are added, weighed and deducted once by a sliced print', async ({ page }, testInfo) => {
  const errors = [];
  page.on('pageerror', error => errors.push(String(error)));
  const brand = `Test ${testInfo.project.name}`;
  await page.goto('/');
  await expect(page.locator('#generate-button')).toBeEnabled();

  await openView(page, 'inventory');
  await page.locator('#spool-brand').fill(brand);
  await page.locator('#spool-material').fill('pla');
  await page.locator('#spool-color-name').fill('흰색');
  await expect(page.locator('#spool-color-hex')).toHaveValue('#f4f4f1');  // a common colour name fills the swatch
  await page.locator('#spool-color-name').fill('검정');
  await page.locator('#spool-location').fill('책상 서랍');
  await page.locator('#spool-price').fill('25000');
  const created = page.waitForResponse(r => r.url().endsWith('/api/spools') && r.request().method() === 'POST');
  await page.locator('#spool-save').click();
  const spool = await (await created).json();
  expect(spool.material).toBe('PLA');
  const card = page.locator(`[data-spool="${spool.id}"]`);
  await expect(card).toContainText(`${brand} PLA · 검정`);
  expect(spool.color_hex).toBe('#232323');
  await expect(card).toContainText('1,000 / 1,000 g');

  // Scale reading 1080 g with a 250 g empty spool leaves 830 g.
  await card.locator('input[type="number"]').fill('1080');
  await card.getByRole('button', { name: '무게 반영' }).click();
  await expect(card).toContainText('830 / 1,000 g · 개봉');

  await page.route('**/api/models', async route => {
    if (route.request().method() !== 'POST') return route.continue();
    const response = await route.fetch();
    const job = await response.json();
    job.latest_slice = { recorded_at: job.created_at, phase: 'finished', plan: { ready: true }, execution: { status: 'sliced', filament_grams: 12.5 } };
    await route.fulfill({ response, json: job });
  });
  await openView(page, 'models');
  await page.locator('#generate-button').click();
  await expect(page.locator('#outcome-spool')).toBeVisible();
  await expect(page.locator('#outcome-spool-grams')).toHaveValue('12.5');
  await page.locator('#outcome-spool-select').selectOption(spool.id);
  await page.locator('#outcome-spool-use').click();
  await expect(page.locator('#outcome-spool-feedback')).toContainText('12.5 g을 뺐습니다');
  await expect(page.locator('#outcome-spool-use')).toBeDisabled();  // one deduction per print and spool

  await openView(page, 'inventory');
  await expect(card).toContainText('817.5 / 1,000 g');
  const csv = await page.request.get('/api/spools.csv');
  expect((await csv.text())).toContain(brand);
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
  expect(overflow).toBeLessThanOrEqual(1);
  expect(errors).toEqual([]);
});
