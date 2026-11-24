const { test, expect } = require('@playwright/test');
const { installStudioTabs } = require('./studio-tabs.cjs');

test.beforeEach(({ page }) => installStudioTabs(page));

// Studio plates: drafts side by side. Previews only (no job is stored until generate); no
// slicer, printer or physical print is involved.
test.beforeEach(async ({ page }) => {
  page.__errors = [];
  page.on('pageerror', error => page.__errors.push(String(error)));
  await page.goto('/');
  await expect(page.locator('#generate-button')).toBeEnabled();
  await expect(page.locator('#preview-status')).toHaveText('실시간 미리보기 · 파일 생성 전', { timeout: 20_000 });
});

test.afterEach(async ({ page }) => {
  expect(page.__errors).toEqual([]);
});

async function confirmIfAsked(page) {
  const confirm = page.locator('#model-confirm-replace');
  if (await confirm.isVisible()) await confirm.click();
}

test('plates keep their own drafts, switch from the list and survive a reload', async ({ page }) => {
  await expect(page.locator('.plate-open')).toHaveCount(1);
  await page.locator('#parameter-width').fill('140');
  await expect(page.locator('#preview-caption')).toContainText('140 × 80 × 35 mm', { timeout: 20_000 });

  await page.locator('#plate-add').click();
  await confirmIfAsked(page);
  await expect(page.locator('.plate-open')).toHaveCount(2);
  await expect(page.locator('.plate-row.is-current .plate-open strong')).toHaveText('플레이트 2');
  await page.locator('.template-card[data-template="keycap"]').click();
  await confirmIfAsked(page);
  await expect(page.locator('#preview-caption')).toContainText('18 × 18 × 8 mm', { timeout: 20_000 });
  await expect(page.locator('[data-plate="1"]')).toContainText('키캡 · 1u “A”');

  // Plate 1 still has its own width.
  await page.locator('[data-plate="0"]').click();
  await confirmIfAsked(page);
  await expect(page.locator('#parameter-width')).toHaveValue('140');
  await expect(page.locator('#preview-caption')).toContainText('140 × 80 × 35 mm', { timeout: 20_000 });
  await expect(page.locator('#preview-previous-toggle')).toBeHidden();

  await page.reload();
  await expect(page.locator('#generate-button')).toBeEnabled();
  await expect(page.locator('.plate-open')).toHaveCount(2);
  await expect(page.locator('#parameter-width')).toHaveValue('140');

  // Removing the open plate opens its neighbour.
  await page.locator('.plate-row.is-current .plate-remove').click();
  await confirmIfAsked(page);
  await expect(page.locator('.plate-open')).toHaveCount(1);
  await expect(page.locator('#parameter-key_units')).toBeVisible();
});

test('example sets add keycap plates that preview and generate like any draft', async ({ page }) => {
  test.setTimeout(120_000);
  await page.locator('[data-example-set="keycaps"]').click();
  await confirmIfAsked(page);
  await expect(page.locator('.plate-open')).toHaveCount(7);
  await expect(page.locator('.plate-row.is-current .plate-open')).toContainText('“Esc”');
  await expect(page.locator('#parameter-top_tilt')).toHaveValue('6');
  await expect(page.locator('#preview-status')).toHaveText('실시간 미리보기 · 파일 생성 전', { timeout: 30_000 });
  await expect(page.locator('#preview-caption')).toContainText('18 × 18 × 9.63 mm');

  // The spacebar plate: a blank 6.25u key with stabilizer stems.
  await page.locator('[data-plate="6"]').click();
  await confirmIfAsked(page);
  await expect(page.locator('#parameter-key_units')).toHaveValue('6.25');
  await expect(page.locator('#preview-caption')).toContainText('118.01 × 18', { timeout: 30_000 });
  const generated = page.waitForResponse(r => r.url().endsWith('/api/models') && r.request().method() === 'POST');
  await page.locator('#generate-button').click();
  expect((await generated).status()).toBe(200);
  await expect(page.locator('#model-result')).toBeVisible();
  await expect(page.locator('[data-plate="6"] .plate-file')).toHaveText('파일 있음');
});

test('rounded household examples preview as valid shapes', async ({ page }) => {
  test.setTimeout(120_000);
  await page.locator('[data-example-set="home"]').click();
  await confirmIfAsked(page);
  await expect(page.locator('.plate-open')).toHaveCount(8);
  await expect(page.locator('#parameter-corner_radius')).toHaveValue('6');
  await expect(page.locator('#preview-caption')).toContainText('150 × 90 × 30 mm', { timeout: 30_000 });
  await page.locator('[data-plate="4"]').click();
  await confirmIfAsked(page);
  await expect(page.locator('#parameter-corner_radius')).toHaveValue('1.5');
  await expect(page.locator('#preview-caption')).toContainText('70 × 80 × 90 mm', { timeout: 30_000 });
  // A radius thicker than the plates is refused with a reason, not drawn.
  await page.locator('#parameter-corner_radius').fill('3');
  await expect(page.locator('#preview-status')).toHaveText('미리보기 불가', { timeout: 20_000 });
  await expect(page.locator('#preview-caption')).toContainText('모서리 둥글기');
});
