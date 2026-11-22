const { test, expect } = require('@playwright/test');
const { spawn } = require('node:child_process');
const path = require('node:path');

// Real app server and a real local HTTP server: the synthetic Moonraker script
// (scripts/fake_moonraker.py) shaped like a four-toolhead Klipper printer.
// Nothing is printed; the app only sends its four read requests.
async function startFakeMoonraker(port, extra = []) {
  const python = process.env.PPA_PYTHON || 'python';
  const child = spawn(python, [path.join(__dirname, '..', '..', 'scripts', 'fake_moonraker.py'), '--port', String(port), ...extra],
    { stdio: ['ignore', 'pipe', 'pipe'] });
  await new Promise((resolve, reject) => {
    const timer = setTimeout(() => reject(new Error('fake Moonraker did not start')), 10000);
    child.stdout.on('data', (chunk) => { if (String(chunk).includes('synthetic Moonraker')) { clearTimeout(timer); resolve(); } });
    child.on('exit', (code) => { clearTimeout(timer); reject(new Error(`fake Moonraker exited ${code}`)); });
  });
  return child;
}

async function openPrinters(page) {
  const menu = page.locator('#menu-toggle');
  if (await menu.isVisible()) await menu.click();
  await page.locator('.nav-item[data-view="printers"]').click();
  await expect(page.locator('#view-printers')).toBeVisible();
}

test('a Klipper printer reached through Moonraker shows four toolheads and asks again after an input change', async ({ page }, testInfo) => {
  const port = 17125 + testInfo.workerIndex * 2;
  const fake = await startFakeMoonraker(port, ['--api-key', 'synthetic-key-1234']);
  try {
    const errors = [];
    page.on('pageerror', (error) => errors.push(String(error)));
    await page.goto('/');
    await expect(page.locator('#generate-button')).toBeEnabled();
    await openPrinters(page);

    await page.locator('#klipper-host').fill('127.0.0.1');
    await page.locator('#klipper-port').fill(String(port));
    await page.locator('#klipper-check').click();
    await expect(page.locator('#klipper-feedback')).toContainText('API 키');
    await expect(page.locator('#klipper-result')).toBeHidden();

    await page.locator('#klipper-api-key').fill('synthetic-key-1234');
    const read = page.waitForResponse((r) => r.url().endsWith('/api/printers/moonraker/status'));
    await page.locator('#klipper-check').click();
    const body = await (await read).text();
    expect(body).not.toContain('synthetic-key-1234');
    const result = page.locator('#klipper-result');
    await expect(page.locator('#klipper-status-badge')).toHaveText('출력 중');
    await expect(result).toContainText('약 30분 (진행률로 추정)');
    await expect(result).toContainText('42 / 120');
    await expect(result.locator('.klipper-tools li')).toHaveCount(4);
    await expect(result.locator('.klipper-tools li.is-active')).toContainText('툴헤드 2');
    await expect(result).toContainText('Klipper v0.13.0-synthetic');

    await page.locator('#klipper-port').fill(String(port + 1));
    await expect(result).toHaveAttribute('aria-hidden', 'true');
    await expect(page.locator('#klipper-status-badge')).toHaveText('입력이 바뀌어 다시 확인 필요');
    await page.locator('#klipper-check').click();
    await expect(page.locator('#klipper-feedback')).toContainText('연결하지 못했습니다');

    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
    expect(overflow).toBeLessThanOrEqual(1);
    expect(errors).toEqual([]);
  } finally {
    fake.kill();
  }
});
