const { test, expect } = require('@playwright/test');
const fs = require('node:fs');
const path = require('node:path');

// Real server and real CAD generation. The plate view is a visual reference from
// recorded plate sizes; the slicer settings remain the authority for a real slice.

async function generate(page, values) {
  for (const [field, value] of Object.entries(values)) await page.locator(`#parameter-${field}`).fill(value);
  const generated = page.waitForResponse((r) => r.url().endsWith('/api/models') && r.request().method() === 'POST');
  await page.locator('#generate-button').click();
  expect((await generated).status()).toBe(200);
  await expect(page.locator('#model-canvas')).toBeVisible();
}

test('a model is placed on a chosen printer plate, the choice is remembered and the view saves as an image', async ({ page }) => {
  const errors = [];
  page.on('pageerror', (error) => errors.push(String(error)));
  await page.goto('/');
  await expect(page.locator('#generate-button')).toBeEnabled();
  const select = page.locator('#preview-bed');
  const fit = page.locator('#preview-bed-fit');
  await expect(select.locator('option')).toHaveCount(17);  // none + 15 Bambu Lab + Snapmaker U1
  await expect(fit).toBeHidden();

  await select.selectOption('snapmaker-u1');
  await expect(fit).toHaveText('모델을 만들면 출력판에 들어가는지 알려 드립니다.');
  await generate(page, { width: '120', depth: '80', height: '35' });
  await expect(fit).toHaveText('Snapmaker U1 출력판(270 × 270 × 높이 270 mm)에 들어갑니다.');
  await expect(fit).toHaveClass(/is-success/);

  // The plate is drawn: the canvas shows the plate tint around the model, not only the model.
  const tinted = await page.locator('#model-canvas').evaluate((canvas) => {
    const data = canvas.getContext('2d').getImageData(0, 0, canvas.width, canvas.height).data;
    let count = 0;
    for (let index = 0; index < data.length; index += 4) if (data[index] === 0xe9 && data[index + 1] === 0xee && data[index + 2] === 0xf6) count += 1;
    return count;
  });
  expect(tinted).toBeGreaterThan(500);

  await page.reload();
  await expect(page.locator('#generate-button')).toBeEnabled();
  await expect(select).toHaveValue('snapmaker-u1');

  await select.selectOption('bambu-n1');
  await generate(page, { width: '200', depth: '80', height: '35' });
  await expect(fit).toContainText('A1 mini 출력판(180 × 180 × 높이 180 mm)보다 가로 20 mm 큽니다');
  await expect(fit).toHaveClass(/is-error/);

  const download = page.waitForEvent('download');
  await page.locator('#preview-save').click();
  const file = await download;
  expect(file.suggestedFilename()).toMatch(/미리보기\.png$/);
  const bytes = fs.readFileSync(await file.path());
  expect(bytes.subarray(1, 4).toString()).toBe('PNG');

  await select.selectOption('');
  await expect(fit).toBeHidden();
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
  expect(overflow).toBeLessThanOrEqual(1);
  expect(errors).toEqual([]);
});

test('an imported model is checked against the same chosen plate', async ({ page }) => {
  const errors = [];
  page.on('pageerror', (error) => errors.push(String(error)));
  await page.goto('/');
  await expect(page.locator('#generate-button')).toBeEnabled();
  await page.locator('#preview-bed').selectOption('bambu-n6');
  const menu = page.locator('#menu-toggle');
  if (await menu.isVisible()) await menu.click();
  await page.locator('.nav-item[data-view="imports"]').click();
  await page.locator('#import-file').setInputFiles(path.join(__dirname, 'fixtures', 'overhanging-cap.stl'));
  await page.locator('#import-submit').click();
  await expect(page.locator('#import-badge')).toHaveText('점검 완료');
  await expect(page.locator('#import-bed-fit')).toHaveText('이 방향으로 놓으면: Bambu Lab X2D 출력판(256 × 256 × 높이 261 mm)에 들어갑니다.');
  expect(errors).toEqual([]);
});
