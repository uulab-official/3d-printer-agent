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

test('review regressions: comparison follows the current model and only 3MF counts as downloaded', async ({ page }) => {
  const first = await generate(page, { width: '120', depth: '80', height: '35', wall: '2' });
  const stl = page.waitForEvent('download');
  await page.locator('#download-links a', { hasText: 'STL' }).click();
  await stl;
  await expect(page.locator('#journey-steps .journey-step').nth(2)).not.toContainText('3MF 내려받음');
  const menu = page.locator('#menu-toggle');
  const open = async view => { if (await menu.isVisible()) await menu.click(); await page.locator(`.nav-item[data-view="${view}"]`).click(); };
  await open('offers');
  for (const [key, value] of Object.entries({ name: '테스트 PLA', price: '20000', grams: '1000', shipping: '0' })) await page.locator(`#offer-1-${key}`).fill(value);
  await page.locator('#compare-offers').click();
  const firstGrams = first.printability.items.find(item => item.id === 'material').grams;
  await expect(page.locator('#offer-comparison th').last()).toContainText(`${firstGrams} g`);
  await open('models');
  await page.locator('#parameter-height').fill('70');
  const second = await generate(page, {});
  const secondGrams = second.printability.items.find(item => item.id === 'material').grams;
  expect(secondGrams).not.toBe(firstGrams);
  await open('offers');
  await expect(page.locator('#offer-comparison th').last()).toContainText(`${secondGrams} g`);
  await expect(page.locator('#offer-model-note')).toContainText(`${secondGrams} g`);
});

test('parameter panel edits with steppers and sliders, and copied settings paste back exactly', async ({ page, context, browserName }, testInfo) => {
  await expect(page.locator('#parameter-fields .parameter-group legend')).toHaveText(['크기', '두께', '모양', '색']);
  await page.getByRole('button', { name: '가로 늘리기 (1 mm)' }).click();
  await page.getByRole('button', { name: '가로 늘리기 (1 mm)' }).click();
  await expect(page.locator('#parameter-width')).toHaveValue('122');
  await expect(page.locator('[data-slider-for="width"]')).toHaveValue('122');
  await page.locator('[data-slider-for="depth"]').fill('150');
  await expect(page.locator('#parameter-depth')).toHaveValue('150');
  await expect(page.locator('[data-field="wall"] .parameter-desc')).toContainText('노즐 지름의 2배');
  // Copy: clipboard may be refused in automation; either path leaves the exact text available.
  await context.grantPermissions(['clipboard-read', 'clipboard-write']).catch(() => {});
  await page.locator('#copy-parameters').click();
  await expect(page.locator('#parameter-share-feedback')).toBeVisible();
  const copied = await page.evaluate(async () => {
    const shown = document.getElementById('paste-text').value;
    if (shown) return shown;
    try { return await navigator.clipboard.readText(); } catch { return ''; }
  });
  const data = JSON.parse(copied);
  expect(data).toMatchObject({ format: '3d-printer-agent/parameters', template: 'tray', parameters: { width: 122, depth: 150 } });
  // Change the draft, then paste the copied settings back.
  await page.locator('#parameter-width').fill('200');
  await page.locator('#paste-parameters').click();
  await page.locator('#paste-text').fill(copied);
  await page.locator('#paste-apply').click();
  const confirm = page.locator('#model-confirm-replace');
  if (await confirm.isVisible()) await confirm.click();
  await expect(page.locator('#parameter-width')).toHaveValue('122');
  await expect(page.locator('#parameter-share-feedback')).toContainText('붙여 넣은 설정을 적용했습니다');
  await page.locator('#paste-parameters').click();
  await page.locator('#paste-text').fill('{"template":"tray","parameters":{"width":5}}');
  await page.locator('#paste-apply').click();
  await expect(page.locator('#parameter-share-feedback')).toContainText('10~500 mm');
  await expect(page.locator('#parameter-width')).toHaveValue('122');
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1)).toBe(true);
});

test('name keychain: text field, request parsing, readable top view and a single printable solid', async ({ page }) => {
  await page.locator('#request-text').fill('이름이 민수인 키링 글자 크기 14mm');
  const planned = page.waitForResponse(r => r.url().endsWith('/api/plan'));
  await page.locator('#plan-button').click();
  await planned;
  const confirm = page.locator('#model-confirm-replace');
  if (await confirm.isVisible()) await confirm.click();
  await expect(page.locator('#parameter-text')).toHaveValue('민수');
  await expect(page.locator('#parameter-text_size')).toHaveValue('14');
  await expect(page.locator('#parameter-fields .parameter-group legend').first()).toHaveText('글자');
  await expect(page.locator('label[for="parameter-wall"]')).toHaveText('테두리 여백 · mm');
  await page.locator('#parameter-text').fill('Samantha');
  const result = await generate(page, {});
  expect(result.template).toBe('name_tag');
  expect(result.geometry_status).toBe('validated');
  expect(result.dimensions_mm.z).toBeCloseTo(4, 3);
  await expect(page.locator('#result-heading')).toContainText('이름 키링 “Samantha”');
  await page.locator('[data-preview-view="top"]').click();
  await expect(page.locator('[data-preview-view="top"]')).toHaveAttribute('aria-pressed', 'true');
  await page.locator('#parameter-text').fill('');
  await expect(page.locator('#model-result')).toBeHidden();
  await page.locator('#generate-button').click();
  await expect(page.locator('#parameter-text')).toHaveJSProperty('validity.valueMissing', true);
});

test('a coloured keychain request, a spoken colour edit and the two-filament 3MF', async ({ page }) => {
  // Colours are named filament choices; the screen colour only approximates them.
  await page.locator('#request-text').fill('빨간 글자로 "지우" 키링, 판은 흰색');
  await page.locator('#plan-button').click();
  await expect(page.locator('#parameter-text')).toHaveValue('지우');
  await expect(page.locator('#parameter-color')).toHaveValue('white');
  await expect(page.locator('#parameter-accent_color')).toHaveValue('red');
  await expect(page.locator('[data-color-for="accent_color"][data-color-value="red"]')).toHaveAttribute('aria-checked', 'true');
  await expect(page.locator('#parameter-fields .parameter-group legend')).toHaveText(['글자', '두께', '모양', '색']);
  const generated = page.waitForResponse(r => r.url().endsWith('/api/models') && r.request().method() === 'POST');
  await page.locator('#generate-button').click();
  const job = await (await generated).json();
  expect(job.result.color_parts.map(part => [part.key, part.color, part.filament])).toEqual([['base', 'white', 1], ['letters', 'red', 2]]);
  await expect(page.locator('#preview-colors')).toContainText('글자: 빨강 · 필라멘트 2');
  await expect(page.locator('#preview-colors')).toContainText('받침: 흰색 · 필라멘트 1');
  const colorLink = page.locator('#download-links a.download-link', { hasText: '색상 3MF' });
  await expect(colorLink).toHaveAttribute('href', new RegExp(job.artifacts.color_three_mf.replace(/[/.]/g, '\\$&') + '$'));
  const download = await page.request.get(job.artifacts.color_three_mf);
  expect(download.status()).toBe(200);
  expect((await download.body()).subarray(0, 2).toString()).toBe('PK');
  // The canvas really paints the letter colour: count strongly red pixels.
  await page.locator('#preview-canvas, canvas').first().scrollIntoViewIfNeeded();
  const redPixels = async () => page.evaluate(() => {
    const canvas = document.querySelector('#preview-stage canvas');
    const data = canvas.getContext('2d').getImageData(0, 0, canvas.width, canvas.height).data;
    let red = 0, blue = 0;
    for (let index = 0; index < data.length; index += 4) {
      const [r, g, b] = [data[index], data[index + 1], data[index + 2]];
      if (r > 150 && g < 90 && b < 90) red += 1;
      if (b > 150 && r < 90 && g < 140) blue += 1;
    }
    return { red, blue };
  });
  await expect.poll(async () => (await redPixels()).red).toBeGreaterThan(50);

  // A spoken edit changes only the letter colour; dimensions and text stay.
  await page.locator('#model-edit-text').fill('글자를 파란색으로 바꿔줘');
  await page.locator('#model-edit-propose').click();
  await expect(page.locator('#model-edit-changes')).toContainText('글자 색');
  await page.locator('#model-edit-apply').click();
  await expect(page.locator('#parameter-accent_color')).toHaveValue('blue');
  await expect(page.locator('#parameter-text')).toHaveValue('지우');
  const regenerated = page.waitForResponse(r => r.url().endsWith('/api/models') && r.request().method() === 'POST');
  await page.locator('#generate-button').click();
  const editedResponse = await regenerated;
  const edited = await editedResponse.json();
  expect(editedResponse.status(), JSON.stringify(edited)).toBe(200);
  expect(edited.result.parameters).toMatchObject({ text: '지우', color: 'white', accent_color: 'blue' });
  expect(edited.result.dimensions_mm).toEqual(job.result.dimensions_mm);
  await expect(page.locator('#preview-colors')).toContainText('글자: 파랑');
  await expect.poll(async () => (await redPixels()).blue).toBeGreaterThan(50);

  // Choosing a swatch by hand is an ordinary draft change.
  await page.locator('[data-color-for="color"][data-color-value="black"]').click();
  await expect(page.locator('#parameter-color')).toHaveValue('black');
  await expect(page.locator('[data-color-for="color"][data-color-value="black"]')).toHaveAttribute('aria-checked', 'true');
});

test('a reported failure with reasons offers next steps and a reviewed model fix', async ({ page }) => {
  await page.locator('[data-template="cable_comb"]').click();
  const confirm = page.locator('#model-replace-confirm');
  if (await confirm.isVisible()) await page.locator('#model-replace-confirm button').first().click();
  const generated = page.waitForResponse(r => r.url().endsWith('/api/models') && r.request().method() === 'POST');
  await page.locator('#generate-button').click();
  const job = await (await generated).json();
  expect(job.result.parameters.fit_clearance).toBe(0.3);
  await page.locator('#outcome-result').selectOption('failure');
  await expect(page.locator('#outcome-reasons')).toBeVisible();
  await page.locator('[data-outcome-reason="too_tight"]').check();
  await page.locator('[data-outcome-reason="stringing"]').check();
  const saved = page.waitForResponse(r => r.url().endsWith(`/api/jobs/${job.id}/outcome`));
  await page.locator('#save-outcome').click();
  expect((await (await saved).json()).user_outcome.reasons).toEqual(['stringing', 'too_tight']);  // display order
  const recovery = page.locator('#outcome-recovery');
  await expect(recovery).toContainText('다음에 바꿔 볼 것');
  await expect(recovery.locator('[data-reason="stringing"]')).toContainText('노즐 온도');
  const fix = recovery.locator('[data-recovery-edit]');
  await expect(fix).toHaveCount(1);
  await expect(fix).toContainText('0.3 → 0.5');
  await fix.click();
  await expect(page.locator('#model-edit-text')).toHaveValue('여유 0.2mm 늘려줘');
  await expect(page.locator('#model-edit-changes')).toContainText('0.5');
  await page.locator('#model-edit-apply').click();
  await expect(page.locator('#parameter-fit_clearance')).toHaveValue('0.5');
  const regenerated = page.waitForResponse(r => r.url().endsWith('/api/models') && r.request().method() === 'POST');
  await page.locator('#generate-button').click();
  const fixed = await (await regenerated).json();
  expect(fixed.result.parameters.fit_clearance).toBe(0.5);
  expect(fixed.model_edit.changes).toEqual([{ field: 'fit_clearance', before: 0.3, after: 0.5 }]);
});

test('a printer-reported failure comes first in recovery with its codes and the HMS search link', async ({ page }) => {
  // The server-side link is tested against the synthetic printer in Python; this checks the real page rendering.
  const generated = page.waitForResponse(r => r.url().endsWith('/api/models') && r.request().method() === 'POST');
  await page.locator('#generate-button').click();
  const job = await (await generated).json();
  await page.route(`**/api/jobs/${job.id}/recovery`, async route => {
    const real = await (await route.fetch()).json();
    real.items.unshift({ reason: 'printer_reported', label: '프린터가 보고한 실패', model_edit: null, codes: ['0300-400C'],
      lookup_url: 'https://wiki.bambulab.com/en/hms/home', actions: ['보고된 코드: 0300-400C.', '이 앱은 코드의 뜻을 해석하지 않습니다.'] });
    await route.fulfill({ json: real });
  });
  await page.locator('#outcome-result').selectOption('failure');
  await page.locator('[data-outcome-reason="warping"]').check();
  await page.locator('#save-outcome').click();
  const reported = page.locator('#outcome-recovery .recovery-item').first();
  await expect(reported).toHaveAttribute('data-reason', 'printer_reported');
  await expect(reported).toContainText('0300-400C');
  const link = reported.getByRole('link', { name: /HMS 코드 검색/ });
  await expect(link).toHaveAttribute('href', 'https://wiki.bambulab.com/en/hms/home');
  await expect(link).toHaveAttribute('rel', 'noopener noreferrer');
  await expect(page.locator('#outcome-recovery [data-reason="warping"]')).toContainText('브림');
});

test('a wall hook from a request prints without supports and edits by its own words', async ({ page }) => {
  await page.locator('#request-text').fill('헤드폰 걸이 만들어줘');
  await page.locator('#plan-button').click();
  await expect(page.locator('#parameter-depth')).toHaveValue('50');
  await expect(page.locator('[data-field="depth"] label')).toContainText('걸이 길이');
  await expect(page.locator('[data-field="hole_diameter"] label')).toContainText('나사 구멍 지름');
  const generated = page.waitForResponse(r => r.url().endsWith('/api/models') && r.request().method() === 'POST');
  await page.locator('#generate-button').click();
  const job = await (await generated).json();
  expect(job.result.template).toBe('wall_hook');
  expect(job.result.dimensions_mm).toEqual({ x: 30, y: 50, z: 60 });
  expect(job.result.printability.items.find(item => item.id === 'overhang').status).toBe('pass');
  await page.locator('#model-edit-text').fill('걸이 길이 10mm 늘려줘');
  await page.locator('#model-edit-propose').click();
  await expect(page.locator('#model-edit-changes')).toContainText('60');
  await page.locator('#model-edit-apply').click();
  await expect(page.locator('#parameter-depth')).toHaveValue('60');
});

test('a keycap from a request: key size, blank legend, the cross stem fit and a size edit', async ({ page }) => {
  await page.locator('#request-text').fill('ESC 키캡 빨간색으로');
  await page.locator('#plan-button').click();
  await expect(page.locator('#parameter-key_units')).toHaveValue('1');
  await expect(page.locator('#parameter-text')).toHaveValue('ESC');
  await expect(page.locator('[data-field="key_units"] label')).toHaveText('키 크기 · u');
  await expect(page.locator('[data-field="bottom"] label')).toContainText('윗면 두께');
  await expect(page.locator('#parameter-width')).toHaveCount(0);
  const generated = page.waitForResponse(r => r.url().endsWith('/api/models') && r.request().method() === 'POST');
  await page.locator('#generate-button').click();
  const job = await (await generated).json();
  expect(job.result.template).toBe('keycap');
  expect(job.result.dimensions_mm.x).toBeCloseTo(18, 3);
  expect(job.result.parameters.color).toBe('red');
  const items = Object.fromEntries(job.result.printability.items.map(item => [item.id, item]));
  expect(items.fit_clearance.status).toBe('pass');
  expect(items.overhang.detail).toContain('브릿지');
  await expect(page.locator('#result-heading')).toContainText('키캡 1u “ESC”');
  await page.locator('#model-edit-text').fill('키 크기 1.5u로 바꿔줘');
  await page.locator('#model-edit-propose').click();
  await expect(page.locator('#model-edit-changes')).toContainText('1.5');
  await page.locator('#model-edit-apply').click();
  await expect(page.locator('#parameter-key_units')).toHaveValue('1.5');
  await page.locator('#parameter-text').fill('');
  const blank = await generate(page, {});
  expect(blank.parameters.text).toBe('');
  expect(blank.dimensions_mm.x).toBeCloseTo(27.525, 3);
});

test('caliper measurements are recorded with the outcome and compared with the CAD size', async ({ page }) => {
  const generated = page.waitForResponse(r => r.url().endsWith('/api/models') && r.request().method() === 'POST');
  await page.locator('#generate-button').click();
  const job = await (await generated).json();
  const { x, y, z } = job.result.dimensions_mm;
  await page.locator('#outcome-result').selectOption('success');
  await page.locator('#outcome-measure > summary').click();
  const values = [[x - 0.1, y + 0.05, z], [x - 0.15, y, z + 0.05], [x - 0.1, y - 0.05, z]];
  for (const [index, sample] of values.entries()) {
    const row = page.locator(`[data-measure-row="${index + 1}"]`);
    for (const [axis, value] of ['x', 'y', 'z'].map((axis, i) => [axis, sample[i]])) await row.locator(`[data-measure="${axis}"]`).fill(String(value));
  }
  await page.locator('#outcome-tolerance').fill('0.2');
  const saved = page.waitForResponse(r => r.url().endsWith(`/api/jobs/${job.id}/outcome`));
  await page.locator('#save-outcome').click();
  const outcome = (await (await saved).json()).user_outcome;
  expect(outcome.measurement_review.status).toBe('within');
  const review = page.locator('#outcome-measure-review');
  await expect(review).toContainText('실측 3개');
  await expect(review).toContainText('허용 오차 안');
  await expect(review.locator('tr')).toHaveCount(4);
  // A half-filled sample is refused before anything is sent.
  await page.locator('[data-measure-row="3"] [data-measure="z"]').fill('');
  await page.locator('#save-outcome').click();
  await expect(page.locator('#outcome-feedback')).toContainText('샘플 3');
});
