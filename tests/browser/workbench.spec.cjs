const { test, expect } = require('@playwright/test');
const { installStudioTabs } = require('./studio-tabs.cjs');

test.beforeEach(({ page }) => installStudioTabs(page));

// Layout only: every non-studio screen uses the studio frame. No CAD, slicing, printer or
// physical print is involved.
const BENCHES = [
  { view: 'profiles', main: '#profile-form', side: '#profile-setup' },
  { view: 'inventory', main: '#inventory-list', side: '#inventory-form' },
  { view: 'offers', main: '#store-guide', side: '#offers-form' },
  { view: 'printers', main: '#printer-form', side: '#klipper-form' },
  { view: 'history', main: '#history-list', side: '#history-filters' },
  { view: 'guide', main: '#glossary-list', side: '#onboarding-steps' },
];

async function openView(page, view) {
  const menu = page.locator('#menu-toggle');
  if (await menu.isVisible()) await menu.click();
  await page.locator(`.nav-item[data-view="${view}"]`).click();
  await expect(page.locator(`#view-${view}`)).toBeVisible();
}

test.beforeEach(async ({ page }) => {
  page.__workbenchErrors = [];
  page.on('pageerror', error => page.__workbenchErrors.push(String(error)));
  await page.goto('/');
  await expect(page.locator('#generate-button')).toBeEnabled();
});

test.afterEach(async ({ page }) => {
  expect(page.__workbenchErrors).toEqual([]);
});

test('each screen places its work beside a side panel on desktop and stacks on a phone', async ({ page, isMobile }, testInfo) => {
  for (const bench of BENCHES) {
    await openView(page, bench.view);
    const main = page.locator(bench.main);
    const side = page.locator(bench.side);
    await expect(side).toBeAttached();
    const mainBox = await page.locator(`#view-${bench.view} .workbench`).evaluate((root, selectors) => {
      const box = selector => root.querySelector(selector).getBoundingClientRect();
      const [main, side] = [box(selectors.main), box(selectors.side)];
      return { mainLeft: main.left, mainRight: main.right, sideLeft: side.left, sideRight: side.right, sideTop: side.top, mainTop: main.top };
    }, { main: bench.main, side: bench.side });
    if (isMobile) {
      // One column: both share the same horizontal span.
      expect(Math.abs(mainBox.sideLeft - mainBox.mainLeft)).toBeLessThan(40);
    } else {
      // Two columns: the panels do not overlap horizontally.
      const separate = mainBox.sideLeft >= mainBox.mainRight - 1 || mainBox.mainLeft >= mainBox.sideRight - 1;
      expect(separate, `${bench.view} main and side are in separate columns`).toBe(true);
    }
    await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1)).toBe(true);
    await expect(main).toBeAttached();
    await page.screenshot({ path: testInfo.outputPath(`workbench-${bench.view}.png`) });
  }
});

test('usage conditions in the side panel still belong to the profile form', async ({ page }) => {
  await openView(page, 'profiles');
  await expect(page.locator('#workspace-status')).toHaveText('새 작업');
  await page.locator('#setup-nozzle').fill('0.4');
  await expect(page.locator('#workspace-status')).toHaveText('저장하지 않은 변경');
  const owned = await page.evaluate(() => ['setup-printer-model', 'setup-nozzle', 'setup-identity', 'review-profile']
    .every(id => document.getElementById(id).form === document.getElementById('profile-form')));
  expect(owned).toBe(true);
});
