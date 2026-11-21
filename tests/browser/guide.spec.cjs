const { test, expect } = require('@playwright/test');

// Real server: the welcome, the term help next to a heading and the glossary view.
test('a first visit shows the welcome, term help explains a word and the glossary finds it', async ({ page }) => {
  const errors = [];
  page.on('pageerror', error => errors.push(String(error)));
  await page.goto('/');
  await expect(page.locator('#generate-button')).toBeEnabled();
  await expect(page.locator('#welcome')).toBeVisible();

  // Term help next to a heading opens a short explanation, Escape closes it and returns focus.
  await page.locator('.nav-item[data-view="inventory"]').evaluate(button => button.click());
  const help = page.locator('#inventory-form-heading + .term-help');
  await expect(help).toHaveText('‘스풀’ 뜻');
  await help.click();
  await expect(page.locator('#term-popover')).toBeVisible();
  await expect(page.locator('#term-popover-title')).toHaveText('스풀');
  await expect(help).toHaveAttribute('aria-expanded', 'true');
  await page.keyboard.press('Escape');
  await expect(page.locator('#term-popover')).toBeHidden();
  await expect(help).toBeFocused();

  // "용어 사전에서 보기" opens the glossary at that entry.
  await help.click();
  await page.locator('#term-popover-more').click();
  await expect(page.locator('#view-guide')).toBeVisible();
  await expect(page.locator('#term-spool')).toBeFocused();
  await expect(page.locator('#term-spool')).toHaveClass(/is-highlighted/);

  await expect(page.locator('#onboarding-steps > li')).toHaveCount(5);
  await page.locator('#glossary-search').fill('서포트');
  await expect(page.locator('#term-support')).toBeVisible();
  await page.locator('#glossary-search').fill('');
  await page.locator('[data-glossary-category="file"]').click();
  await expect(page.locator('#glossary-list .glossary-item')).toHaveCount(4);
  await page.locator('#term-stl [data-glossary-show="three_mf"]').click();
  await expect(page.locator('#term-three_mf')).toBeFocused();

  // An onboarding step opens its view; closing the welcome is remembered after a reload.
  await page.locator('#onboarding-steps [data-step="settings"] button').click();
  await expect(page.locator('#view-profiles')).toBeVisible();
  await page.locator('.nav-item[data-view="models"]').evaluate(button => button.click());
  await page.locator('#welcome-dismiss').click();
  await expect(page.locator('#welcome')).toBeHidden();
  await page.reload();
  await expect(page.locator('#generate-button')).toBeEnabled();
  await expect(page.locator('#welcome')).toBeHidden();

  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
  expect(overflow).toBeLessThanOrEqual(1);
  expect(errors).toEqual([]);
});
