const { test, expect } = require('@playwright/test');

// Real server and inventory storage. The printer report is a labelled synthetic response
// (the browser CI has no printer); linking a spool writes only the person's own record.
async function openView(page, view) {
  const menu = page.locator('#menu-toggle');
  if (await menu.isVisible()) await menu.click();
  await page.locator(`.nav-item[data-view="${view}"]`).click();
  await expect(page.locator(`#view-${view}`)).toBeVisible();
}

test('a reported AMS slot is linked to a spool, warns on a material mismatch and can be unlinked', async ({ page }, testInfo) => {
  const errors = [];
  page.on('pageerror', error => errors.push(String(error)));
  // Projects share one server; distinct serials and brands keep their links apart.
  const serial = testInfo.project.name.startsWith('mobile') ? '01S00AMSLINKM001' : '01S00AMSLINKD001';
  const brand = `AMS ${testInfo.project.name}`;
  await page.goto('/');
  await expect(page.locator('#generate-button')).toBeEnabled();

  await openView(page, 'inventory');
  await page.locator('#spool-brand').fill(brand);
  await page.locator('#spool-material').fill('PLA');
  await page.locator('#spool-color-name').fill('흰색');
  const created = page.waitForResponse(r => r.url().endsWith('/api/spools') && r.request().method() === 'POST');
  await page.locator('#spool-save').click();
  const spool = await (await created).json();

  await page.route('**/api/printers/status', route => route.fulfill({ json: {
    schema_version: 1, observed_at: '2026-11-21T00:00:00Z', target: { host: '192.168.0.20', serial, port: 8883 },
    connection: { state: 'reporting', detail: '프린터가 현재 상태를 보고했습니다(합성 응답).' }, certificate: { sha256: 'c'.repeat(64), pinned: false },
    identity: { product_name: 'Bambu Lab P1S' }, scope: '합성 응답',
    print: { state: 'IDLE', state_label: '대기 중', material_slots: [
      { unit: 0, slot: 0, material: 'PLA', color: 'FFFFFFFF' }, { unit: 0, slot: 1, material: 'PETG', color: '202020FF' }, { unit: 0, slot: 2, empty: true }] } } }));
  await openView(page, 'printers');
  await page.locator('#printer-host').fill('192.168.0.20');
  await page.locator('#printer-serial').fill(serial);
  await page.locator('#printer-access-code').fill('BROWSER-ONLY-CODE');
  await page.locator('#printer-check').click();
  const links = page.locator('#printer-slot-links');
  await expect(links.locator('[data-slot-link]')).toHaveCount(2);  // the empty slot gets no choice

  const linked = page.waitForResponse(r => r.url().endsWith(`/api/spools/${spool.id}/slot`));
  await links.locator('[data-slot-link="ams-0-1"]').selectOption(spool.id);
  expect((await linked).status()).toBe(200);
  await expect(page.locator('#printer-feedback')).toContainText('AMS 1 · 2번 칸에');
  await expect(links.locator('[data-position="ams-0-1"]')).toContainText('재고 기록은 PLA, 프린터 보고는 PETG');

  // Moving the spool to the matching slot clears the warning and leaves one link.
  await links.locator('[data-slot-link="ams-0-0"]').selectOption(spool.id);
  await expect(links.locator('[data-slot-link="ams-0-0"]')).toHaveValue(spool.id);
  await expect(links.locator('[data-slot-link="ams-0-1"]')).toHaveValue('');
  await expect(links).not.toContainText('프린터 보고는');

  await openView(page, 'inventory');
  const card = page.locator(`[data-spool="${spool.id}"]`);
  await expect(card).toContainText(`프린터 ${serial} · AMS 1 · 1번 칸에 넣어 둠`);
  await expect(card).toContainText('프린터에 장착');
  await card.getByRole('button', { name: '연결 해제' }).click();
  await expect(card).not.toContainText('넣어 둠');
  await expect(card).toContainText('개봉');
  expect((await (await page.request.get('/api/spools.csv')).text())).toContain(brand);

  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
  expect(overflow).toBeLessThanOrEqual(1);
  expect(errors).toEqual([]);
});
