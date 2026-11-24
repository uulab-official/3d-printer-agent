const { test, expect } = require('@playwright/test');
const { installStudioTabs } = require('./studio-tabs.cjs');

test.beforeEach(({ page }) => installStudioTabs(page));
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
  await expect(fit).toHaveText('Snapmaker U1 출력판(270 × 270 × 높이 270 mm)에 들어갑니다. 남는 공간: 가로 150 mm · 세로 190 mm · 높이 235 mm.');
  await expect(page.locator('#preview-bed-legend')).toHaveText('출처: Snapmaker U1 공식 사양 페이지(snapmaker.com/snapmaker-u1/specs)');
  await expect(fit).toHaveClass(/is-success/);

  // The plate is drawn: the canvas shows the plate tint around the model, not only the model.
  const tinted = await page.locator('#model-canvas').evaluate((canvas) => {
    const data = canvas.getContext('2d').getImageData(0, 0, canvas.width, canvas.height).data;
    let count = 0;
    for (let index = 0; index < data.length; index += 4) if (data[index] === 0x2f && data[index + 1] === 0x32 && data[index + 2] === 0x37) count += 1;  // MeshViewer.DARK.bed
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
  await expect(page.locator('#import-bed-fit')).toContainText('이 방향으로 놓으면: Bambu Lab X2D 출력판(256 × 256 × 높이 261 mm)에 들어갑니다. 남는 공간:');
  await expect(page.locator('#preview-bed-legend')).toContainText('세로 점선 사이: 두 노즐이 함께 닿는 영역(가로 235.5 mm)');
  expect(errors).toEqual([]);
});

test('a printer that reports its model fills an empty plate choice', async ({ page }) => {
  // Synthetic, labelled printer report: the browser CI has no printer.
  await page.route('**/api/printers/status', (route) => route.fulfill({ json: {
    schema_version: 1, observed_at: '2026-11-22T00:00:00Z', target: { host: '192.168.0.20', serial: '01S00PLATE000001', port: 8883 },
    connection: { state: 'reporting', detail: '프린터가 현재 상태를 보고했습니다(합성 응답).' }, certificate: { sha256: 'd'.repeat(64), pinned: false },
    identity: { product_name: 'Bambu Lab X2D' }, scope: '합성 응답', print: { state: 'IDLE', state_label: '대기 중', material_slots: [] } } }));
  await page.goto('/');
  await expect(page.locator('#generate-button')).toBeEnabled();
  await expect(page.locator('#preview-bed')).toHaveValue('');
  const menu = page.locator('#menu-toggle');
  if (await menu.isVisible()) await menu.click();
  await page.locator('.nav-item[data-view="printers"]').click();
  await page.locator('#printer-host').fill('192.168.0.20');
  await page.locator('#printer-serial').fill('01S00PLATE000001');
  await page.locator('#printer-access-code').fill('BROWSER-ONLY-CODE');
  await page.locator('#printer-check').click();
  await expect(page.locator('#toast')).toContainText('X2D의 출력판을 모델 미리보기에 표시합니다');
  await expect(page.locator('#preview-bed')).toHaveValue('bambu-n6');
});
