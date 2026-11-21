const { test, expect } = require('@playwright/test');
const fs = require('fs/promises');
const path = require('path');

// fixtures/overhanging-cap.stl: a 10 mm stem standing under a 60 × 40 mm cap (CadQuery,
// binary STL). As stored, the cap's underside overhangs; upside down it rests flat.
const FIXTURE = path.join(__dirname, 'fixtures', 'overhanging-cap.stl');

test.beforeEach(async ({ page }) => {
  page.__importErrors = [];
  page.on('pageerror', error => page.__importErrors.push(String(error)));
  await page.goto('/');
  await expect(page.locator('#generate-button')).toBeEnabled();
});

test.afterEach(async ({ page }) => {
  expect(page.__importErrors).toEqual([]);
});

test('an imported STL is checked, flipped onto its flat cap and downloaded in that placement', async ({ page }, testInfo) => {
  const menu = page.locator('#menu-toggle');
  if (await menu.isVisible()) await menu.click();
  await page.locator('.nav-item[data-view="imports"]').click();
  await expect(page.locator('#import-submit')).toBeDisabled();
  await page.locator('#import-file').setInputFiles(FIXTURE);
  const uploaded = page.waitForResponse(r => r.url().endsWith('/api/imports') && r.request().method() === 'POST');
  await page.locator('#import-submit').click();
  const body = await (await uploaded).json();
  expect(body.sha256).toHaveLength(64);
  await expect(page.locator('#import-badge')).toHaveText('점검 완료');

  const choices = page.locator('[data-import-orientation]');
  await expect(choices.first()).toContainText('위아래 뒤집기 · 추천');
  await expect(choices.first()).toHaveAttribute('aria-checked', 'true');
  await expect(page.locator('#import-status')).toHaveText('점검 통과');
  await expect(page.locator('[data-import-review="overhang"]')).toContainText('없음');
  await expect(page.locator('#import-canvas')).toBeVisible();

  // The file's own placement overhangs and barely touches the bed.
  await choices.filter({ hasText: '파일에 저장된 방향' }).click();
  await expect(page.locator('#import-status')).toHaveText('바꿔야 할 점 있음');
  await expect(page.locator('[data-import-review="bed_contact"]')).toContainText('바꿔야 함');

  await choices.first().click();
  const download = page.waitForEvent('download');
  await page.locator('#import-download').click();
  const file = await download;
  expect(file.suggestedFilename()).toBe('overhanging-cap-출력방향1.3mf');
  const saved = testInfo.outputPath('placed.3mf');
  await file.saveAs(saved);
  expect((await fs.readFile(saved)).subarray(0, 2).toString()).toBe('PK');

  const original = await page.request.get(body.source_url);
  expect(Buffer.compare(await original.body(), await fs.readFile(FIXTURE))).toBe(0);
  await expect(page.locator('#import-recent-list button')).toContainText(['overhanging-cap.stl']);
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
  expect(overflow).toBeLessThanOrEqual(1);
});

test('a chosen placement becomes a job that the model screen can slice, send and record', async ({ page }) => {
  const menu = page.locator('#menu-toggle');
  if (await menu.isVisible()) await menu.click();
  await page.locator('.nav-item[data-view="imports"]').click();
  await page.locator('#import-file').setInputFiles(FIXTURE);
  await page.locator('#import-submit').click();
  await expect(page.locator('#import-badge')).toHaveText('점검 완료');
  const created = page.waitForResponse(r => /\/api\/imports\/[a-f0-9]{32}\/jobs$/.test(r.url()));
  await page.locator('#import-make-job').click();
  const job = await (await created).json();
  expect(job.template).toBe('imported');
  expect(job.design_source.orientation.label).toBe('위아래 뒤집기');
  expect(Object.keys(job.artifacts).sort()).toEqual(['manifest', 'stl', 'three_mf']);
  await expect(page.locator('#view-models')).toBeVisible();
  await expect(page.locator('#result-heading')).toContainText('불러온 모델 “overhanging-cap.stl”');
  await expect(page.locator('#model-metrics')).toContainText('불러온 메시 · CAD 검증 아님');
  await expect(page.locator('#generated-source')).toContainText('출력 방향 · 위아래 뒤집기');
  await expect(page.locator('#printability-run')).toBeDisabled();
  await expect(page.locator('#outcome-card')).toBeVisible();
  await expect(page.locator('#print-send-card')).toBeHidden();  // not sliced yet
  // The same job reopens from history.
  if (await menu.isVisible()) await menu.click();
  await page.locator('.nav-item[data-view="history"]').click();
  await expect(page.locator('#history-list')).toContainText('불러온 모델 “overhanging-cap.stl”');
});

test('a file that is not a mesh model is refused without a result', async ({ page }) => {
  const menu = page.locator('#menu-toggle');
  if (await menu.isVisible()) await menu.click();
  await page.locator('.nav-item[data-view="imports"]').click();
  await page.locator('#import-file').setInputFiles({ name: 'broken.3mf', mimeType: 'model/3mf', buffer: Buffer.from('not a zip') });
  await page.locator('#import-submit').click();
  await expect(page.locator('#import-badge')).toHaveText('불러오지 못함');
  await expect(page.locator('#import-feedback')).toContainText('ZIP');
  await expect(page.locator('#import-result')).toBeHidden();
});

test('a file dropped on the picker is selected and checked like a chosen file', async ({ page }) => {
  const menu = page.locator('#menu-toggle');
  if (await menu.isVisible()) await menu.click();
  await page.locator('.nav-item[data-view="imports"]').click();
  const bytes = [...await fs.readFile(FIXTURE)];
  const transfer = await page.evaluateHandle(data => {
    const dt = new DataTransfer();
    dt.items.add(new File([new Uint8Array(data)], 'dropped-cap.stl', { type: 'model/stl' }));
    return dt;
  }, bytes);
  await page.dispatchEvent('#import-drop', 'dragover', { dataTransfer: transfer });
  await expect(page.locator('#import-drop')).toHaveClass(/is-dragging/);
  await page.dispatchEvent('#import-drop', 'drop', { dataTransfer: transfer });
  await expect(page.locator('#import-drop')).not.toHaveClass(/is-dragging/);
  await expect(page.locator('#import-file-name')).toContainText('dropped-cap.stl');
  await expect(page.locator('#import-badge')).toHaveText('파일 선택됨 · 점검 전');
  await expect(page.locator('#import-submit')).toBeEnabled();
  const uploaded = page.waitForResponse(r => r.url().endsWith('/api/imports') && r.request().method() === 'POST');
  await page.locator('#import-submit').click();
  expect((await (await uploaded).json()).filename).toBe('dropped-cap.stl');
  await expect(page.locator('#import-badge')).toHaveText('점검 완료');
});
