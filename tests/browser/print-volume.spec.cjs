const crypto = require('node:crypto');
const fs = require('node:fs/promises');
const path = require('node:path');
const { execFile } = require('node:child_process');
const { promisify } = require('node:util');
const { test, expect } = require('@playwright/test');

const runFile = promisify(execFile);

// Synthetic recorded settings only. The CAD, server requests and downloaded
// files are real; these tests do not launch Studio or claim a physical print.
async function studioUpload(name, width, depth, height) {
  const result = await runFile('python', ['-c', [
    'import base64, json, sys',
    'from tests.studio_project_fixtures import project_bytes',
    'print(base64.b64encode(project_bytes(settings_overrides=json.loads(sys.argv[1]))).decode())',
  ].join('\n'), JSON.stringify({
    printable_area: ['0x0', `${width}x0`, `${width}x${depth}`, `0x${depth}`],
    printable_height: String(height),
  })], { cwd: path.resolve(__dirname, '../..'), timeout: 30000, maxBuffer: 2 * 1024 * 1024 });
  return { name, mimeType: 'model/3mf', buffer: Buffer.from(result.stdout.trim(), 'base64') };
}

async function selectStudioSource(page, upload) {
  const imported = page.waitForResponse(response => response.url().endsWith('/api/studio-projects/import'));
  await page.locator('#studio-project-file').setInputFiles(upload);
  const response = await imported;
  expect(response.status()).toBe(201);
  const source = await response.json();
  expect(source.supported).toBe(true);
  await page.locator('#studio-project-apply').click();
  await expect(page.locator('#studio-project-applied')).toContainText(upload.name);
  return source;
}

async function generateTray(page) {
  for (const [field, value] of [['width', '120'], ['depth', '80'], ['height', '35']]) {
    await page.locator(`#parameter-${field}`).fill(value);
  }
  const generated = page.waitForResponse(response => response.url().endsWith('/api/models') && response.request().method() === 'POST');
  await page.locator('#generate-button').click();
  const response = await generated;
  expect(response.status()).toBe(200);
  const job = await response.json();
  expect(job.result.dimensions_mm).toMatchObject({ x: 120, y: 80, z: 35 });
  await expect(page.locator('#model-result')).toBeVisible();
  return job;
}

async function prepareStudioProject(page) {
  const prepared = page.waitForResponse(response => response.url().endsWith('/api/slice'));
  await page.locator('#prepare-studio-project').click();
  const response = await prepared;
  expect(response.status()).toBe(200);
  expect(response.request().postDataJSON().execute).toBe(false);
  const result = await response.json();
  expect(result.execution).toBeNull();
  return result;
}

test.beforeEach(async ({ page }) => {
  page.__printVolumeErrors = [];
  page.on('pageerror', error => page.__printVolumeErrors.push(String(error)));
  await page.goto('/');
  await expect(page.locator('#generate-button')).toBeEnabled();
});

test.afterEach(async ({ page }) => {
  expect(page.__printVolumeErrors).toEqual([]);
});

test('recorded printer volume blocks an oversized CAD and a new selected source requires a fresh comparison', async ({ page }, testInfo) => {
  test.setTimeout(120000);
  const job = await generateTray(page);
  const modelResponse = await page.request.get(job.artifacts.three_mf);
  expect(modelResponse.status()).toBe(200);
  const modelHash = crypto.createHash('sha256').update(await modelResponse.body()).digest('hex');
  const tinyUpload = await studioUpload('synthetic-10x10x5.3mf', 10, 10, 5);
  const tiny = await selectStudioSource(page, tinyUpload);
  const blocked = await prepareStudioProject(page);
  expect(blocked.plan).toMatchObject({ project_prepared: false, ready: false, print_volume: {
    schema_version: 1, status: 'height_exceeded', can_prepare: false,
    scope: 'upright_bounding_box_0_90', model_dimensions_mm: [120, 80, 35],
    recorded_volume_mm: [10, 10, 5], placement_applied: false,
    model_sha256: modelHash, settings_sha256: tiny.settings_sha256,
  } });
  const review = page.locator('#print-volume-review');
  await expect(review).toBeVisible();
  await expect(review).toContainText('기록된 출력 높이 초과');
  await expect(review.getByRole('row').filter({ hasText: '현재 CAD' }).locator('td')).toHaveText(['120', '80', '35']);
  await expect(review.getByRole('row').filter({ hasText: '설정에 기록된 출력 공간' }).locator('td')).toHaveText(['10', '10', '5']);
  await expect(page.locator('#studio-project-prepared-download')).toBeHidden();
  await expect(page.locator('#download-links a').filter({ hasText: '설정 포함 3MF' })).toHaveCount(0);
  await expect(page.locator('#execute-studio-project')).toBeDisabled();
  const blockedJob = await (await page.request.get(`/api/jobs/${job.id}`)).json();
  expect(blockedJob.artifacts.prepared_three_mf).toBeUndefined();
  expect(blockedJob.latest_slice.plan.print_volume).toEqual(blocked.plan.print_volume);
  const modelDownload = await page.locator('#download-links a').filter({ hasText: '3MF 형상' }).getAttribute('href');
  await review.getByRole('button', { name: '현재 치수 수정하기' }).click();
  await expect(page.locator('#parameter-heading')).toBeFocused();
  await expect(page.locator('#parameter-width')).toHaveValue('120');
  await expect(page.locator('#parameter-height')).toHaveValue('35');
  await expect(page.locator('#download-links a').filter({ hasText: '3MF 형상' })).toHaveAttribute('href', modelDownload);

  // Merely inspecting a candidate is separate from explicitly selecting it.
  const fitting = await selectStudioSource(page, await studioUpload('synthetic-160x100x60.3mf', 160, 100, 60));
  await expect(review).toHaveCount(0);
  const prepared = await prepareStudioProject(page);
  expect(prepared.plan).toMatchObject({ project_prepared: true, ready: false, print_volume: {
    status: 'fits', can_prepare: true, model_dimensions_mm: [120, 80, 35],
    recorded_volume_mm: [160, 100, 60], placement_applied: false,
    orientations: [{ rotation_degrees: 0, fits: true }, { rotation_degrees: 90, fits: false }],
    model_sha256: modelHash, settings_sha256: fitting.settings_sha256,
  } });
  expect(prepared.plan.project_receipt.print_volume).toEqual(prepared.plan.print_volume);
  await expect(review).toContainText('기록된 출력 공간과 크기 비교 완료');
  await expect(review.getByRole('row').filter({ hasText: '설정에 기록된 출력 공간' }).locator('td')).toHaveText(['160', '100', '60']);
  await expect(page.locator('#studio-project-prepared-download')).toBeVisible();
  await expect(page.locator('#execute-studio-project')).toBeDisabled();
  const downloading = page.waitForEvent('download');
  await page.locator('#studio-project-prepared-download').click();
  const preparedFile = testInfo.outputPath('volume-reviewed-project.3mf');
  await (await downloading).saveAs(preparedFile);
  expect(crypto.createHash('sha256').update(await fs.readFile(preparedFile)).digest('hex')).toBe(prepared.plan.project_sha256);
  await review.screenshot({ path: testInfo.outputPath('print-volume-review.png'), scale: 'css' });
  await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1)).toBe(true);

  // A selected source change removes both the old comparison and its download.
  await selectStudioSource(page, tinyUpload);
  await expect(review).toHaveCount(0);
  await expect(page.locator('#studio-project-prepared-download')).toBeHidden();
  await expect(page.locator('#download-links a').filter({ hasText: '설정 포함 3MF' })).toHaveCount(0);
  const blockedAgain = await prepareStudioProject(page);
  expect(blockedAgain.plan.print_volume.status).toBe('height_exceeded');
  await expect(review).toBeVisible();
  await page.locator('#parameter-height').fill('34');
  await expect(review).toHaveCount(0);
  await expect(page.locator('#model-result')).toBeHidden();
  await expect(page.locator('#prepare-studio-project')).toBeDisabled();
  await expect(page.locator('#studio-project-prepared-download')).toBeHidden();
  await testInfo.attach('print-volume-responses.json', { body: JSON.stringify({ blocked, prepared, blocked_again: blockedAgain }, null, 2), contentType: 'application/json' });
});

test('a visible model-ready toast does not intercept a real overlapping download click or tap', async ({ page, isMobile }, testInfo) => {
  // In the three-column studio the downloads sit under the centre view, away from the
  // bottom-right toast; one column puts a real download under it.
  if (!isMobile) await page.setViewportSize({ width: 900, height: 900 });
  await generateTray(page);
  await expect(page.locator('#toast')).toBeVisible();
  // Move the page with ordinary scrolling so an existing download lies behind
  // the live toast. No element styles, visibility or event handlers are changed.
  const href = await page.evaluate(() => {
    const toast = document.querySelector('#toast').getBoundingClientRect();
    const links = [...document.querySelectorAll('#download-links a')];
    const overlap = link => {
      const rect = link.getBoundingClientRect();
      return Math.min(rect.right, toast.right) - Math.max(rect.left, toast.left);
    };
    const link = links.sort((left, right) => overlap(right) - overlap(left))[0];
    if (!link || overlap(link) < 10) throw new Error('No genuine download horizontally overlaps the toast');
    const rect = link.getBoundingClientRect();
    window.scrollBy(0, rect.top + rect.height / 2 - toast.top - toast.height / 2);
    return link.getAttribute('href');
  });
  const point = await page.evaluate(href => {
    const link = [...document.querySelectorAll('#download-links a')].find(item => item.getAttribute('href') === href);
    const target = link.getBoundingClientRect();
    const toast = document.querySelector('#toast').getBoundingClientRect();
    const left = Math.max(target.left, toast.left), right = Math.min(target.right, toast.right);
    const top = Math.max(target.top, toast.top), bottom = Math.min(target.bottom, toast.bottom);
    if (right - left < 4 || bottom - top < 4) throw new Error('The live toast must overlap the actual pointer target');
    return { x: (left + right) / 2, y: (top + bottom) / 2 };
  }, href);
  await expect(page.locator('#toast')).toBeVisible();
  const downloading = page.waitForEvent('download', { timeout: 2000 });
  if (isMobile) await page.touchscreen.tap(point.x, point.y);
  else await page.mouse.click(point.x, point.y);
  const download = await downloading;
  expect(new URL(download.url()).pathname).toBe(new URL(href, page.url()).pathname);
  await expect(page.locator('#toast')).toBeVisible();
  await testInfo.attach('toast-pointer-check.json', { body: JSON.stringify({ input: isMobile ? 'tap' : 'mouse', href, point, toast_visible_after_download: true }), contentType: 'application/json' });
});
