const { test, expect } = require('@playwright/test');
const { installStudioTabs } = require('./studio-tabs.cjs');

test.beforeEach(({ page }) => installStudioTabs(page));

// The first case uses the real server and a closed loopback port: it proves the
// separate "unreachable" state, not a printer connection. The second case labels
// a synthetic reporting response so layout and pinning can be checked without a
// printer, an account, credentials or a physical print.
const CODE = 'BROWSER-ONLY-CODE';

async function openPrinters(page) {
  const menu = page.locator('#menu-toggle');
  if (await menu.isVisible()) await menu.click();
  await page.locator('.nav-item[data-view="printers"]').click();
  await expect(page.locator('#view-printers')).toBeVisible();
}

async function fillTarget(page, serial) {
  await page.locator('#printer-host').fill('127.0.0.1');
  await page.locator('#printer-serial').fill(serial);
  await page.locator('#printer-access-code').fill(CODE);
}

test.beforeEach(async ({ page }) => {
  page.__printerErrors = [];
  page.on('pageerror', error => page.__printerErrors.push(String(error)));
  await page.goto('/');
  await expect(page.locator('#generate-button')).toBeEnabled();
});

test.afterEach(async ({ page }) => {
  expect(page.__printerErrors).toEqual([]);
});

test('closed loopback port is reported as unreachable without print values or the code', async ({ page }, testInfo) => {
  await openPrinters(page);
  await expect(page.locator('#printer-check')).toBeDisabled();
  // Projects share one server; distinct serials keep its 5 s per-printer limit independent.
  await fillTarget(page, testInfo.project.name.startsWith('mobile') ? '01S00BROWSERM001' : '01S00BROWSERD001');
  const response = page.waitForResponse(r => r.url().endsWith('/api/printers/status'));
  await page.locator('#printer-check').click();
  const result = await (await response).json();
  expect(result.connection.state).toBe('unreachable');
  expect(result.print).toBeNull();
  await expect(page.locator('#printer-feedback')).toContainText('8883 포트에 연결하지 못했습니다');
  await expect(page.locator('#printer-status-badge')).toHaveText('상태를 받지 못함');
  await expect(page.locator('#printer-result')).toBeHidden();
  expect(await page.locator('#view-printers').innerText()).not.toContain(CODE);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1)).toBe(true);
});

test('synthetic reporting response renders reported values and pins its certificate', async ({ page }) => {
  const bodies = [];
  const fingerprint = 'ab'.repeat(32);
  await page.route('**/api/printers/status', async route => {
    const body = route.request().postDataJSON();
    bodies.push(body);
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({
      schema_version: 1, observed_at: '2026-11-16T00:00:00Z',
      target: { host: body.host, serial: body.serial, port: 8883 },
      connection: { state: 'reporting', detail: '프린터가 현재 상태를 보고했습니다.' },
      certificate: { sha256: fingerprint, issuer_verified: false, pinned: Boolean(body.pinned_certificate_sha256), matches_pin: body.pinned_certificate_sha256 ? true : null },
      identity: { product_name: 'Synthetic fixture printer', firmware: '00.00.00.00', modules: [] },
      print: { state: 'RUNNING', state_label: '출력 중', progress_percent: 42, remaining_minutes: 37, layer: 51, total_layers: 120,
        error_code: 0, error_code_hex: null, hms: [{ hms_code: '0700_8000_0002_0001' }],
        temperatures_c: { nozzle: 219.6, nozzle_target: 220, bed: 55, bed_target: 55, chamber: null },
        nozzle: { diameter_mm: 0.4, type: 'stainless_steel' }, wifi_signal: null,
        material_slots: [{ unit: 0, slot: 0, material: 'PLA', product: 'PLA Basic', color: 'FFFFFFFF', filament_id: 'GFA00' }] },
      scope: '읽기 전용 LAN 상태 확인입니다.',
    }) });
  });
  await openPrinters(page);
  await fillTarget(page, '01S00BROWSER0002');
  await page.locator('#printer-check').click();
  await expect(page.locator('#printer-status-badge')).toHaveText('출력 중');
  const result = page.locator('#printer-result');
  await expect(result).toContainText('42%');
  await expect(result).toContainText('51 / 120');
  await expect(result).toContainText('0700_8000_0002_0001');
  await expect(result).toContainText('GFA00');
  await expect(result).toContainText('처음 확인한 인증서');
  await expect(page.locator('#printer-unpin')).toBeVisible();
  expect(bodies[0].pinned_certificate_sha256).toBeUndefined();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1)).toBe(true);
  await page.locator('#printer-check').click();
  await expect(result).toContainText('고정한 인증서와 일치');
  await expect(result.locator('progress')).toHaveAttribute('aria-label', '프린터 보고 진행률 42%');
  await expect(result.locator('.printer-swatch')).toHaveCount(1);
  await expect(result).toContainText('스테인리스강');
  expect(bodies[1].pinned_certificate_sha256).toBe(fingerprint);
  await page.locator('#printer-host').fill('127.0.0.2');
  await expect(result).toHaveClass(/is-stale/);
  await expect(result).toHaveAttribute('aria-hidden', 'true');
  await expect(page.locator('#printer-feedback')).toContainText('이전 대상의 확인 결과');
  await expect(page.locator('#printer-status-badge')).toHaveText('입력이 바뀌어 다시 확인 필요');
});

test('a remembered printer survives a reload with its pin but never the access code', async ({ page }) => {
  const fingerprint = 'cd'.repeat(32);
  const bodies = [];
  await page.route('**/api/printers/status', async route => {
    const body = route.request().postDataJSON();
    bodies.push(body);
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({
      schema_version: 1, observed_at: '2026-11-17T00:00:00Z', target: { host: body.host, serial: body.serial, port: 8883 },
      connection: { state: 'reporting', detail: '프린터가 현재 상태를 보고했습니다.' },
      certificate: { sha256: fingerprint, issuer_verified: false, pinned: Boolean(body.pinned_certificate_sha256), matches_pin: body.pinned_certificate_sha256 ? true : null },
      identity: { modules: [], firmware: null, product_name: 'Synthetic P1S' },
      print: { state: 'IDLE', state_label: '대기 중', progress_percent: null, remaining_minutes: null, layer: null, total_layers: null, job_name: null, file_name: null,
               error_code: 0, error_code_hex: null, hms: [], temperatures_c: {}, nozzle: { diameter_mm: 0.4, type: null }, wifi_signal: null, material_slots: [] },
      scope: 'synthetic' }) });
  });
  await openPrinters(page);
  await fillTarget(page, '01S00REMEMBER001');
  await page.locator('#printer-remember').check();
  await page.locator('#printer-check').click();
  await expect(page.locator('#printer-saved')).toBeVisible();
  // Named by what the person entered; the printer-reported product name is only a hint.
  await expect(page.locator('#printer-saved-list')).toContainText('127.0.0.1 · …R001');
  await expect(page.locator('#printer-saved-list button').first()).toHaveAttribute('title', /프린터 보고: Synthetic P1S/);
  const stored = await page.evaluate(() => localStorage.getItem('ppa.printers.v1'));
  expect(stored).toContain(fingerprint);
  expect(stored).not.toContain(CODE);
  await page.reload();
  await expect(page.locator('#generate-button')).toBeEnabled();
  await openPrinters(page);
  await expect(page.locator('#printer-host')).toHaveValue('127.0.0.1');
  await expect(page.locator('#printer-serial')).toHaveValue('01S00REMEMBER001');
  await expect(page.locator('#printer-access-code')).toHaveValue('');
  await page.locator('#printer-access-code').fill(CODE);
  await page.waitForTimeout(5200);
  await page.locator('#printer-check').click();
  await expect.poll(() => bodies.length).toBe(2);
  expect(bodies[1].pinned_certificate_sha256).toBe(fingerprint);
  await page.locator('#printer-saved-list').getByRole('button', { name: /기억 삭제/ }).click();
  await expect(page.locator('#printer-saved')).toBeHidden();
  expect(await page.evaluate(() => localStorage.getItem('ppa.printers.v1'))).toBe('[]');
});
