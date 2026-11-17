const { test, expect } = require('@playwright/test');

// The where-to-buy directory is curated data; links open stores but nothing is fetched from them.
test('store guide narrows by material and kind, keeps unconfirmed stores apart and links safely', async ({ page }) => {
  const errors = [];
  page.on('pageerror', error => errors.push(String(error)));
  await page.goto('/');
  await expect(page.locator('#generate-button')).toBeEnabled();
  const menu = page.locator('#menu-toggle');
  if (await menu.isVisible()) await menu.click();
  await page.locator('[data-view="offers"]').click();
  const guide = page.locator('#store-guide');
  await expect(guide).toBeVisible();
  await expect(page.locator('#store-guide-checked')).toContainText('확인');
  const total = await page.locator('#store-guide-list .store-item').count();
  expect(total).toBeGreaterThan(20);
  await page.locator('[data-store-filter="kind"][data-value="bambu"]').click();
  await expect(page.locator('[data-store-filter="kind"][data-value="bambu"]')).toHaveAttribute('aria-checked', 'true');
  const bambu = page.locator('#store-guide-list .store-item');
  expect(await bambu.count()).toBeLessThan(total);
  await expect(bambu.first()).toContainText('Bambu Lab 한국 공식 스토어');
  const link = bambu.first().locator('a.store-link').first();
  await expect(link).toHaveAttribute('rel', 'noopener noreferrer');
  await expect(link).toHaveAttribute('target', '_blank');
  await expect(link).toHaveAttribute('href', /^https:\/\//);
  await page.locator('[data-store-filter="kind"][data-value="all"]').click();
  await page.locator('[data-store-filter="material"][data-value="레진"]').click();
  for (const text of await page.locator('#store-guide-list .store-materials').allTextContents()) expect(text).toContain('레진');
  await page.locator('[data-store-filter="material"][data-value="all"]').click();
  await page.locator('#store-search').fill('없는 판매처 이름');
  await expect(page.locator('#store-guide-count')).toContainText('없습니다');
  await page.locator('#store-search').fill('');
  await expect(page.locator('#store-guide-unconfirmed-summary')).toContainText('확인하지 못한 곳');
  await expect(page.locator('#store-guide-scope')).toContainText('퓨어필라');
  await expect(page.locator('#store-guide-list')).not.toContainText('퓨어필라');
  // Narrow screens stay within the viewport.
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  expect(overflow).toBeLessThanOrEqual(1);
  expect(errors).toEqual([]);
});
