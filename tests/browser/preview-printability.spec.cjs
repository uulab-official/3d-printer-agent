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

test('regenerating with new dimensions shows the previous model as a labelled, optional outline', async ({ page }) => {
  await generate(page, { width: '120', depth: '80', height: '35' });
  await expect(page.locator('#preview-previous-toggle')).toBeHidden();
  await page.locator('#parameter-height').fill('55');
  await generate(page, {});
  const toggle = page.locator('#preview-previous-toggle');
  await expect(toggle).toBeVisible();
  await expect(page.locator('#preview-previous-label')).toHaveText('이전 120 × 80 × 35 mm');
  const box = await toggle.boundingBox();
  expect(box.height).toBeLessThan(34);
  await page.locator('#preview-previous').uncheck();
  await expect(page.locator('#preview-previous')).not.toBeChecked();
  // Same dimensions again: no outline of an identical model.
  await generate(page, {});
  await expect(toggle).toBeHidden();
});

test('choosing another nozzle rechecks the saved job without regenerating it', async ({ page }) => {
  const result = await generate(page, { width: '60', depth: '40', height: '20', wall: '1.2' });
  expect(result.printability.basis.nozzle_mm).toBe(0.4);
  const rechecked = page.waitForResponse(r => /\/api\/jobs\/[^/]+\/printability$/.test(r.url()));
  await page.locator('#printability-nozzle').selectOption('0.8');
  const response = await rechecked;
  expect(response.status()).toBe(200);
  await expect(page.locator('#printability-basis')).toContainText('0.8 mm 노즐');
  await expect(page.locator('[data-check="min_thickness"]')).toHaveClass(/is-warn/);
  await expect(page.locator('#printability-status')).toHaveText('확인할 점이 있어요');
  await page.locator('#printability-nozzle').selectOption('0.4');
  await expect(page.locator('#printability-status')).toHaveText('형상 점검 통과');
});

test('phone stand starts from discovery, edits its angle in degrees and outlines the previous back', async ({ page }) => {
  await page.locator('[data-project-id="desk-phone-stand"]').click();
  await page.locator('#discovery-detail').getByRole('button', { name: /이 시작점으로 치수 준비/ }).click();
  await expect(page.locator('label[for="parameter-lean_angle"]')).toHaveText('등판 각도 · °');
  await expect(page.locator('label[for="parameter-fit_clearance"]')).toHaveText('홈 여유 · mm');
  const first = await generate(page, {});
  expect(first.template).toBe('phone_stand');
  expect(first.printability.status).toBe('ok');
  await page.locator('#model-edit-text').fill('각도를 75도로 바꿔줘');
  await page.locator('#model-edit-panel').getByRole('button', { name: '수정 제안 검토' }).click();
  await expect(page.locator('#model-edit-changes')).toHaveText('등판 각도: 65 → 75 °');
  await page.locator('#model-edit-review').getByRole('button', { name: '치수 수정 적용' }).click();
  await expect(page.locator('#parameter-lean_angle')).toHaveValue('75');
  const second = await generate(page, {});
  expect(second.parameters.lean_angle).toBe(75);
  expect(second.dimensions_mm).toEqual(first.dimensions_mm);
  await expect(page.locator('#preview-previous-label')).toHaveText('이전 모델 · 같은 크기');
});

test('journey bar walks an owner from dimensions to a recorded result and resets on edits', async ({ page }) => {
  const steps = page.locator('#journey-steps .journey-step');
  await expect(steps).toHaveCount(4);
  await expect(steps.nth(0)).toHaveAttribute('aria-current', 'step');
  await generate(page, { width: '120', depth: '80', height: '35', wall: '2' });
  await expect(steps.nth(2)).toHaveAttribute('aria-current', 'step');
  await expect(page.locator('#journey-next-button')).toHaveText('출력 방법 보기 →');
  await page.locator('#journey-next-button').click();
  await expect(page.locator('#print-quickstart')).toBeInViewport();
  const download = page.waitForEvent('download');
  await page.locator('#download-links a', { hasText: '3MF 형상' }).click();
  await download;
  await expect(steps.nth(2)).toContainText('3MF 내려받음');
  await expect(page.locator('#journey-next-button')).toHaveText('결과 기록하기 →');
  await page.locator('#journey-next-button').click();
  await expect(page.locator('#outcome-result')).toBeFocused();
  await page.locator('#outcome-result').selectOption('success');
  await page.locator('#save-outcome').click();
  await expect(steps.nth(3)).toContainText('성공으로 기록');
  await expect(page.locator('#journey-steps .is-done')).toHaveCount(4);
  await page.locator('#parameter-height').fill('40');
  await expect(steps.nth(0)).toHaveAttribute('aria-current', 'step');
  await expect(page.locator('#journey-steps .is-done')).toHaveCount(0);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1)).toBe(true);
});

test('history tells same-size jobs apart, filters by recorded result and the healthy connection stays one line', async ({ page }) => {
  await expect(page.locator('#local-runtime')).toHaveClass(/is-quiet/);
  await expect(page.locator('#connection-detail')).toBeHidden();
  await generate(page, { width: '120', depth: '80', height: '35', wall: '0.8' });
  await page.locator('#parameter-wall').fill('2');
  await generate(page, {});
  await page.locator('#outcome-result').selectOption('success');
  await page.locator('#outcome-notes').fill('딱 맞음');
  await page.locator('#save-outcome').click();
  await expect(page.locator('#outcome-feedback')).toContainText('기록했습니다');
  const menu = page.locator('#menu-toggle');
  if (await menu.isVisible()) await menu.click();
  await page.locator('.nav-item[data-view="history"]').click();
  // The browser project shares one server, so check this case's two newest jobs only.
  const items = page.locator('#history-list .history-item');
  await expect(items.nth(0)).toContainText('벽 두께 2 mm');
  await expect(items.nth(0)).toContainText('메모: 딱 맞음');
  await expect(items.nth(1)).toContainText('벽 두께 0.8 mm');
  await expect(items.nth(1)).toContainText('점검 확인할 점');
  await page.locator('[data-history-filter="success"]').click();
  await expect(items.nth(0)).toContainText('메모: 딱 맞음');
  await expect(page.locator('.history-filter-note')).toHaveText(/^불러온 \d+개 중 \d+개가 조건에 맞습니다\./);
  for (const item of await items.all()) await expect(item).toContainText('출력 성공 · 사용자 보고');
  await page.locator('[data-history-filter="unrecorded"]').click();
  for (const item of await items.all()) await expect(item).toContainText('실물 출력 미기록');
  await expect(items.nth(0)).toContainText('벽 두께 0.8 mm');
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1)).toBe(true);
});

test('everyday requests become announced plans that generate valid CAD', async ({ page }) => {
  await page.locator('#request-text').fill('사진 넣는 액자 10cm 원형');
  await page.locator('#plan-button').click();
  const feedback = page.locator('#plan-feedback');
  await expect(feedback).toContainText('113 × 113 mm로 키웠습니다');
  await expect(feedback).toContainText('입력하지 않아 기본값을 쓴 치수: 높이 7 mm');
  await expect(feedback).not.toContainText('width');
  await expect(page.locator('#parameter-inset_diameter')).toHaveValue('100');
  const frame = await generate(page, {});
  expect(frame.dimensions_mm).toEqual({ x: 113, y: 113, z: 7 });
  await page.locator('#request-text').fill('서랍 정리함 3칸, 서랍 안쪽이 30x20cm 높이 6cm');
  const planned = page.waitForResponse(r => r.url().endsWith('/api/plan'));
  await page.locator('#plan-button').click();
  await planned;
  // Replacing a generated model asks first; wait for whichever appears.
  const confirm = page.locator('#model-confirm-replace');
  await expect(confirm.or(feedback.filter({ hasText: '안쪽 치수' }))).toBeVisible();
  if (await confirm.isVisible()) await confirm.click();
  await expect(feedback).toContainText('안쪽 치수를 모델의 바깥 치수로 사용했습니다');
  await expect(page.locator('#parameter-width')).toHaveValue('300');
  await expect(page.locator('#parameter-depth')).toHaveValue('200');
  await expect(page.locator('#parameter-dividers')).toHaveValue('2');
});

test('the material line links to purchase comparison, which prices the current model', async ({ page }) => {
  const result = await generate(page, { width: '120', depth: '80', height: '35', wall: '2' });
  const grams = result.printability.items.find(item => item.id === 'material').grams;
  expect(grams).toBeGreaterThan(0);
  await page.locator('[data-check="material"]').getByRole('button', { name: '구매 비교에서 재료비 보기 →' }).click();
  await expect(page.locator('#view-offers')).toBeVisible();
  await expect(page.locator('#offers-model-hint')).toContainText(`약 ${grams} g`);
  for (const [key, value] of Object.entries({ name: '테스트 PLA', price: '20000', grams: '1000', shipping: '0' })) {
    await page.locator(`#offer-1-${key}`).fill(value);
  }
  await page.locator('#compare-offers').click();
  await expect(page.locator('#offer-comparison th').last()).toContainText('현재 모델 재료비 상한');
  await expect(page.locator('.offer-model-cost').first()).toContainText(`₩${Math.round(20 * grams).toLocaleString('ko-KR')}`);
  await expect(page.locator('#offer-model-note')).toContainText('슬라이서 결과');
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1)).toBe(true);
});

test('material setup starts with the profile, explains how to get one and saves last', async ({ page }) => {
  const menu = page.locator('#menu-toggle');
  if (await menu.isVisible()) await menu.click();
  await page.locator('.nav-item[data-view="profiles"]').click();
  const headings = await page.locator('#view-profiles h2').allTextContents();
  expect(headings.indexOf('필라멘트 프로필')).toBeLessThan(headings.indexOf('다음에도 이어서 편집하세요'));
  expect(headings.indexOf('내 프린터와 재료')).toBeLessThan(headings.indexOf('다음에도 이어서 편집하세요'));
  const howto = page.locator('.profile-howto');
  await howto.locator('summary').click();
  await expect(howto).toContainText('프리셋 묶음 내보내기');
  await expect(page.locator('#setup-printer-fill')).toBeHidden();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1)).toBe(true);
});
