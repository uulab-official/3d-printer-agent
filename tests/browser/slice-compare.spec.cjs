const { test, expect } = require('@playwright/test');

// The browser CI has no Bambu Studio: the environment flag and the comparison answer are
// labelled synthetic responses. CAD generation and the settings JSON edit are real.
const BUNDLE = {
  source: 'user_export', plate_type: 'textured_pei_plate',
  machine: { name: 'Synthetic printer', nozzle_diameter: ['0.4'] },
  process: { name: 'Synthetic 0.20mm', layer_height: '0.2', sparse_infill_density: '15%', wall_loops: '2' },
  filaments: [{ name: 'Synthetic PLA' }],
};

test('four-way slice comparison shows estimates and applies one variant to the settings JSON', async ({ page }) => {
  const errors = [];
  page.on('pageerror', error => errors.push(String(error)));
  await page.route('**/api/bootstrap', async route => {
    const response = await route.fetch();
    const body = await response.json();
    body.environment = { ...body.environment, available: true, cli_supported: true, diagnostics: [] };
    await route.fulfill({ response, json: body });
  });
  const requests = [];
  await page.route('**/api/slice/compare', async route => {
    const request = route.request().postDataJSON();
    requests.push(request);
    const variants = [
      { id: 'original', label: '지금 설정', description: '넣은 설정 그대로', overrides: {}, status: 'sliced', minutes: 100, grams: 50, layers: 175, support: false, diagnostics: [] },
      { id: 'fine', label: '곱게', description: '', overrides: { layer_height: '0.12' }, status: 'sliced', minutes: 160, grams: 52, layers: 292, support: false, diagnostics: [] },
      { id: 'fast', label: '빠르게', description: '', overrides: { layer_height: '0.28', sparse_infill_density: '10%' }, status: 'sliced', minutes: 70, grams: 47, layers: 125, support: false, diagnostics: [] },
      { id: 'strong', label: '튼튼하게', description: '', overrides: { wall_loops: '4', sparse_infill_density: '40%' }, status: 'not_ready', diagnostics: ['출력 영역 밖(합성)'] },
    ];
    await route.fulfill({ json: { id: request.job_id, slice_comparison: { schema_version: 1, variants, scope: '합성 응답입니다.' } } });
  });
  await page.goto('/');
  await expect(page.locator('#generate-button')).toBeEnabled();
  await page.locator('#generate-button').click();
  await expect(page.locator('#preview-status')).toContainText('실제 CAD');

  await page.locator('#slicer-details > summary').click();
  await expect(page.locator('#compare-slices')).toBeDisabled();  // nothing to compare yet
  await page.locator('#slicer-json').fill(JSON.stringify(BUNDLE));
  await expect(page.locator('#compare-slices')).toBeEnabled();
  await page.locator('#compare-slices').click();

  const table = page.locator('#slice-compare');
  await expect(table).toBeVisible();
  expect(requests[0].config_bundle).toEqual(BUNDLE);
  await expect(table.locator('[data-compare-variant="fast"]')).toContainText('70분 (-30%)');
  await expect(table.locator('[data-compare-variant="fine"]')).toContainText('160분 (+60%)');
  await expect(table.locator('[data-compare-variant="strong"]')).toContainText('슬라이스하지 못함');

  await table.locator('[data-compare-variant="fast"] button').click();
  const applied = JSON.parse(await page.locator('#slicer-json').inputValue());
  expect(applied.process).toEqual({ ...BUNDLE.process, layer_height: '0.28', sparse_infill_density: '10%' });
  expect(applied.machine).toEqual(BUNDLE.machine);
  await expect(page.locator('#slice-feedback')).toContainText('“빠르게” 설정을 설정 JSON에 넣었습니다');
  await expect(page.locator('#execute-slice')).toBeDisabled();  // review the plan again first
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
  expect(overflow).toBeLessThanOrEqual(1);
  expect(errors).toEqual([]);
});
