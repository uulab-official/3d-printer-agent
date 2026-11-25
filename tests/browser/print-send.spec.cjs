const { test, expect } = require('@playwright/test');
const { installStudioTabs } = require('./studio-tabs.cjs');

test.beforeEach(({ page }) => installStudioTabs(page));

// The send card in a real browser. CAD generation is real; the browser CI has no
// Bambu Studio and no printer, so the slice marker and printer answers below are
// labelled synthetic responses. Nothing is uploaded or printed.
const CODE = 'BROWSER-ONLY-CODE';

async function openView(page, view) {
  const menu = page.locator('#menu-toggle');
  if (await menu.isVisible()) await menu.click();
  await page.locator(`.nav-item[data-view="${view}"]`).click();
  await expect(page.locator(`#view-${view}`)).toBeVisible();
}

function review(extra) {
  return {
    job_title: '케이블 정리대', host: '192.168.0.20', serial: '01S00BROWSER0001', certificate_sha256: 'a'.repeat(64),
    file_bytes: 4096, filename: 'pa-synthetic.gcode.3mf', subtask: 'printer-agent synthetic', mapping: null,
    summary: { plate: 1, printer_model_id: 'C12', nozzle_diameters: '0.4', prediction_seconds: 900, weight_g: 3.1,
               filaments: [{ id: 1, type: 'PETG-CF', color: '#202020', used_g: 3.1, nozzle_c: 250 }] },
    printer: { state: 'IDLE', state_label: '대기 중', nozzle: { diameter_mm: 0.4, type: 'stainless_steel' } },
    material_slots: [{ unit: 0, slot: 0, material: 'PETG', color: '202020FF', nozzle_min_c: 230, nozzle_max_c: 260 },
                     { unit: 0, slot: 1, material: 'PLA', color: 'FFFFFFFF', nozzle_min_c: 190, nozzle_max_c: 230 }],
    connection: { state: 'reporting', detail: '프린터가 현재 상태를 보고했습니다.' },
    requirements: '프린터에서 LAN 전용 모드와 개발자 모드를 켜야 보낼 수 있습니다.', problems: [], warnings: [], ...extra,
  };
}

test.beforeEach(async ({ page }) => {
  page.__sendErrors = [];
  page.on('pageerror', error => page.__sendErrors.push(String(error)));
  await page.goto('/');
  await expect(page.locator('#generate-button')).toBeEnabled();
});

test.afterEach(async ({ page }) => {
  expect(page.__sendErrors).toEqual([]);
});

test('send card: a refused review, a fresh review after a slot change, the bed confirmation and the start report', async ({ page }) => {
  // Real CAD; the response is marked as sliced so the send card appears (synthetic).
  await page.route('**/api/models', async route => {
    if (route.request().method() !== 'POST') return route.continue();
    const response = await route.fetch();
    const job = await response.json();
    job.artifacts = { ...job.artifacts, sliced_three_mf: `/api/jobs/${job.id}/files/sliced_three_mf` };
    job.latest_slice = { recorded_at: job.created_at, phase: 'finished', plan: { ready: true }, execution: { status: 'sliced' } };
    await route.fulfill({ response, json: job });
  });
  const reviews = [];
  const answers = [
    review({ problems: ['이 파일은 P1S용으로 슬라이스했지만 프린터는 A1입니다. 출력판 크기와 시작 동작이 달라 보내지 않습니다.'],
             printer_model: { sliced_code: 'C12', sliced_name: 'P1S', reported_product: 'Bambu Lab A1' } }),
    review({ ready: true, review_token: 'tok-first-synthetic-0001', expires_in_seconds: 180,
             printer_model: { sliced_code: 'C12', sliced_name: 'P1S', reported_product: 'Bambu Lab P1S' },
             mapping: { use_ams: true, ams_mapping: [0], slots: [{ filament: 1, location: 'AMS 1 · 1번 칸', tray: 0 }] },
             warnings: ['PETG-CF는 섬유가 든 마모성 필라멘트인데 프린터는 스테인리스강 노즐을 보고했습니다.'] }),
    review({ ready: true, review_token: 'tok-second-synthetic-002', expires_in_seconds: 180,
             printer_model: { sliced_code: 'C12', sliced_name: 'P1S', reported_product: 'Bambu Lab P1S' },
             mapping: { use_ams: true, ams_mapping: [1], slots: [{ filament: 1, location: 'AMS 1 · 2번 칸', tray: 1 }] },
             warnings: ['필라멘트 1의 슬라이스 노즐 온도 250°C가 고른 칸이 보고한 권장 범위 190~230°C를 벗어납니다.'] }),
  ];
  await page.route('**/api/printers/print/review', async route => {
    reviews.push(route.request().postDataJSON());
    await route.fulfill({ json: answers[Math.min(reviews.length - 1, answers.length - 1)] });
  });
  const starts = [];
  await page.route('**/api/printers/print/start', async route => {
    starts.push(route.request().postDataJSON());
    await route.fulfill({ json: { status: 'started', detail: '프린터가 출력 시작을 보고했습니다(합성 응답).', scope: '합성 응답입니다.',
      stages: { printer_ready: true, uploaded: true, command_sent: true, printer_reported_start: true },
      printer: { state: 'RUNNING', state_label: '출력 중', progress_percent: 0 } } });
  });
  await page.route('**/api/printers/status', route => route.fulfill({ json: {
    connection: { state: 'reporting', detail: 'ok' }, observed_at: '2026-11-19T00:00:00Z', certificate: { sha256: 'a'.repeat(64) },
    print: { state: 'RUNNING', state_label: '출력 중', job_name: 'printer-agent synthetic', progress_percent: 1 } } }));

  await openView(page, 'printers');
  await page.locator('#printer-host').fill('192.168.0.20');
  await page.locator('#printer-serial').fill('01S00BROWSER0001');
  await page.locator('#printer-access-code').fill(CODE);
  await openView(page, 'models');
  await page.locator('[data-template="cable_comb"]').click();
  const confirmReplace = page.locator('#model-replace-confirm');
  if (await confirmReplace.isVisible()) await page.locator('#model-replace-confirm button').first().click();
  await page.locator('#generate-button').click();

  const card = page.locator('#print-send-card');
  await expect(card).toBeVisible();
  await expect(page.locator('#print-send-target')).toContainText('192.168.0.20 · 01S00BROWSER0001');
  await expect(page.locator('#print-send-start')).toBeDisabled();

  // 1. A slice for another model: no token, the reason and both models are shown.
  await page.locator('#print-send-review').click();
  await expect(page.locator('#print-send-badge')).toHaveText('보낼 수 없음');
  await expect(page.locator('#print-send-summary')).toContainText('슬라이스 P1S · 프린터 보고 Bambu Lab A1');
  await expect(page.locator('#print-send-summary')).toContainText('보낼 수 없는 이유');
  await expect(page.locator('#print-send-confirm')).toBeDisabled();
  await expect(page.locator('#print-send-start')).toBeDisabled();
  expect(reviews[0].slots).toBeNull();
  expect(reviews[0].access_code).toBe(CODE);

  // 2. Choose a slot and review again: ready, with the wear warning; start needs the bed confirmation.
  const slot = page.locator('[data-print-slot="0"]');
  await expect(slot.locator('option')).toHaveText(['선택하세요', 'AMS 1 · 1번 칸 · PETG · #202020', 'AMS 1 · 2번 칸 · PLA · #FFFFFF', '외부 스풀']);
  await slot.selectOption('0');
  await page.locator('#print-send-review').click();
  await expect(page.locator('#print-send-badge')).toHaveText('보낼 준비 됨');
  expect(reviews[1].slots).toEqual([0]);
  await expect(page.locator('#print-send-summary')).toContainText('마모성 필라멘트');
  await expect(page.locator('#print-send-start')).toBeDisabled();
  await page.locator('#print-send-confirm').check();
  await expect(page.locator('#print-send-start')).toBeEnabled();

  // 3. A different slot drops the reviewed token until a fresh review.
  await slot.selectOption('1');
  await expect(page.locator('#print-send-badge')).toHaveText('다시 확인 필요');
  await expect(page.locator('#print-send-start')).toBeDisabled();
  await expect(page.locator('#print-send-confirm')).not.toBeChecked();
  await page.locator('#print-send-review').click();
  await expect(page.locator('#print-send-badge')).toHaveText('보낼 준비 됨');
  expect(reviews[2].slots).toEqual([1]);
  await expect(page.locator('#print-send-summary')).toContainText('190~230°C');

  // 4. Start with the confirmation: one start request with the second token, stages shown, no code on the page.
  await page.locator('#print-send-confirm').check();
  await page.locator('#print-send-start').click();
  await expect(page.locator('#print-send-badge')).toHaveText('프린터가 출력 시작을 보고함');
  expect(starts).toEqual([{ review_token: 'tok-second-synthetic-002', access_code: CODE, bed_clear_confirmed: true }]);
  await expect(page.locator('#print-send-result')).toContainText('프린터의 출력 시작 보고');
  await expect(page.locator('#print-send-start')).toBeDisabled();
  expect(await page.content()).not.toContain(CODE);
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
  expect(overflow).toBeLessThanOrEqual(1);
});
