const fs = require('node:fs/promises');
const crypto = require('node:crypto');
const { test, expect } = require('@playwright/test');

// The server and CAD engine are real. No network routes or CAD results are mocked.
async function openView(page, view) {
  const menu = page.locator('#menu-toggle');
  if (await menu.isVisible()) await menu.click();
  await page.locator(`.nav-item[data-view="${view}"]`).click();
  await expect(page.locator(`#view-${view}`)).toBeVisible();
}

async function noHorizontalOverflow(page) {
  await expect.poll(() => page.evaluate(() =>
    document.documentElement.scrollWidth <= window.innerWidth + 1
  )).toBe(true);
}

test.beforeEach(async ({ page }) => {
  const errors = [];
  page.__expectedHttpFailures = [];
  page.on('pageerror', error => errors.push(String(error)));
  page.on('console', message => {
    // HTTP failures are checked with their URL and status below, including the
    // intentionally rejected model in the failure-history regression.
    if (message.type() === 'error' && !message.text().startsWith('Failed to load resource: the server responded with a status of')) errors.push(message.text());
  });
  page.on('response', response => {
    if (response.status() < 400) return;
    if (page.__expectedHttpFailures.some(item => response.url().endsWith(item.path) && response.status() === item.status)) return;
    errors.push(`${response.status()} ${response.url()}`);
  });
  page.on('requestfailed', request => {
    const error = request.failure()?.errorText;
    if (request.url().endsWith('/files/three_mf') && error === 'net::ERR_ABORTED') return;
    errors.push(`${request.url()}: ${error}`);
  });
  page.__errors = errors;
  await page.goto('/');
  await expect(page.locator('#generate-button')).toBeEnabled();
  await expect(page.locator('#template-cards .template-card')).toHaveCount(3);
  await expect(page.locator('#plan-mode option[value="llm"]')).toHaveJSProperty('disabled', true);
  await expect(page.locator('#environment-badge')).toContainText('사용 불가');
  await noHorizontalOverflow(page);
});

test.afterEach(async ({ page }) => {
  expect(page.__errors).toEqual([]);
});

test('Korean request creates real CAD, downloads it, records an outcome, and invalidates an old preview', async ({ page }, testInfo) => {
  await page.locator('#request-text').fill('가로 12cm 세로 8cm 높이 3.5cm 수납함을 3칸으로 만들어줘');
  await page.locator('#plan-button').click();
  await expect(page.locator('#parameter-width')).toHaveValue('120');
  await expect(page.locator('#parameter-depth')).toHaveValue('80');
  await expect(page.locator('#parameter-height')).toHaveValue('35');
  await expect(page.locator('#parameter-dividers')).toHaveValue('2');
  await expect(page.locator('#generate-button')).toBeEnabled();

  const responsePromise = page.waitForResponse(response =>
    response.url().endsWith('/api/models') && response.request().method() === 'POST');
  await page.locator('#generate-button').click();
  const response = await responsePromise;
  expect(response.status()).toBe(200);
  const job = await response.json();
  expect(job.result.geometry_status).toBe('validated');
  expect(job.result.print_status).toBe('not_tested');
  expect(job.result.dimensions_mm).toEqual({ x: 120, y: 80, z: 35 });
  expect(job.result.parameters.dividers).toBe(2);
  expect(job.result.mesh.faces.length).toBeGreaterThan(0);

  await expect(page.locator('#model-result')).toBeVisible();
  await expect(page.locator('#model-metrics')).toContainText('120 × 80 × 35 mm');
  const canvas = page.locator('#model-canvas');
  await expect(canvas).toBeVisible();
  await expect.poll(() => canvas.evaluate(element => {
    const pixels = element.getContext('2d').getImageData(0, 0, element.width, element.height).data;
    let opaque = 0;
    for (let index = 3; index < pixels.length; index += 4) if (pixels[index] === 255) opaque++;
    return opaque;
  })).toBeGreaterThan(1000);
  const beforeZoom = await canvas.evaluate(element => element.toDataURL());
  await page.locator('#zoom-in').click();
  await expect.poll(() => canvas.evaluate(element => element.toDataURL())).not.toBe(beforeZoom);
  await page.locator('#reset-view').click();
  await page.locator('.preview-card').screenshot({ path: testInfo.outputPath('real-cad-preview.png') });

  const manifestResponse = await page.request.get(job.artifacts.manifest);
  expect(manifestResponse.ok()).toBe(true);
  const manifest = await manifestResponse.json();
  const downloadPromise = page.waitForEvent('download');
  await page.locator('#download-links a').filter({ hasText: '3MF 형상' }).click();
  const download = await downloadPromise;
  const file = testInfo.outputPath('downloaded-model.3mf');
  await download.saveAs(file);
  const content = await fs.readFile(file);
  expect(content.subarray(0, 2).toString()).toBe('PK');
  expect(crypto.createHash('sha256').update(content).digest('hex')).toBe(manifest.artifacts.three_mf.sha256);

  // File assembly uses the real generated job, but does not imply native slicing.
  // This browser project deliberately has no installed Bambu executable.
  const bundle = nativeConfigFixture();
  await page.locator('#slicer-details > summary').click();
  await expect(page.locator('#probe-slicer')).toBeDisabled();
  const previousBundle = '{ "source": "user_export", "unfinished": "keep until assembled" }';
  await page.locator('#slicer-json').fill(previousBundle);
  await page.locator('#slicer-machine-file').setInputFiles(presetUpload('machine.json', bundle.machine));
  await expect(page.locator('#slicer-machine-summary')).toContainText(bundle.machine.name);
  await expect(page.locator('#slicer-json')).toBeDisabled();
  await expect(page.locator('#slicer-json')).toHaveValue(previousBundle);
  await page.locator('#slicer-process-file').setInputFiles(presetUpload('process.json', bundle.process));
  await expect(page.locator('#slicer-process-summary')).toContainText(bundle.process.name);
  await page.locator('#slicer-filament-files').setInputFiles(presetUpload('filament.json', bundle.filaments[0]));
  await expect(page.locator('#slicer-filaments-summary')).toContainText(bundle.filaments[0].name);
  await expect(page.locator('#slicer-plate')).toHaveValue('');
  await expect(page.locator('#prepare-slice')).toBeDisabled();
  await expect(page.locator('#execute-slice')).toBeDisabled();
  await page.locator('#slicer-plate').selectOption(bundle.plate_type);
  await expect(page.locator('#assemble-slicer')).toBeEnabled();
  await page.locator('#assemble-slicer').click();
  await expect(page.locator('#slicer-json')).toBeEnabled();
  expect(JSON.parse(await page.locator('#slicer-json').inputValue())).toEqual(bundle);
  await expect(page.locator('#slicer-helper-feedback')).toContainText('파일의 값을 그대로');
  await expect(page.locator('#execute-slice')).toBeDisabled();
  await fs.writeFile(testInfo.outputPath('assembled-slicer-config.json'), await page.locator('#slicer-json').inputValue());
  await noHorizontalOverflow(page);
  await page.locator('.slicer-card').screenshot({ path: testInfo.outputPath('native-config-helper.png') });
  await page.locator('#slicer-machine-file').setInputFiles({ name: 'malformed-machine.json', mimeType: 'application/json', buffer: Buffer.from('{bad') });
  await expect(page.locator('#slicer-helper-feedback')).toContainText('malformed-machine.json');
  await expect(page.locator('#slicer-machine-summary')).toContainText(bundle.machine.name);
  expect(JSON.parse(await page.locator('#slicer-json').inputValue())).toEqual(bundle);
  await page.locator('#cancel-slicer-assembly').click();
  await expect(page.locator('#slicer-json')).toBeEnabled();
  expect(JSON.parse(await page.locator('#slicer-json').inputValue())).toEqual(bundle);
  await expect(page.locator('#prepare-slice')).toBeDisabled();

  const notes = `Browser CI: ${testInfo.project.name}; no physical print performed.`;
  await page.locator('#outcome-result').selectOption('not_tested');
  await page.locator('#outcome-notes').fill(notes);
  const savedPromise = page.waitForResponse(result => result.url().endsWith(`/api/jobs/${job.id}/outcome`));
  await page.locator('#save-outcome').click();
  const saved = await (await savedPromise).json();
  expect(saved.user_outcome.source).toBe('user_reported');
  expect(saved.result.print_status).toBe('not_tested');
  await expect(page.locator('#save-outcome')).toBeEnabled();
  await openView(page, 'history');
  const card = page.locator('.history-item').filter({ hasText: job.title }).first();
  await expect(card).toBeVisible();
  await card.getByRole('button', { name: '열기' }).click();
  await expect(page.locator('#model-result')).toBeVisible();
  await expect(page.locator('#outcome-notes')).toHaveValue(notes);
  await expect(page.locator('#generate-button')).toBeEnabled();

  await page.locator('.template-card[data-template="cable_comb"]').click();
  await expect(page.locator('#model-result')).toBeHidden();
  await expect(canvas).toBeHidden();
  await expect(page.locator('#download-links a')).toHaveCount(0);
  await expect(page.locator('#parameter-slots')).toHaveValue('5');
  await noHorizontalOverflow(page);
  await page.screenshot({ path: testInfo.outputPath('workspace.png'), fullPage: true });
});

test('missing material evidence and unknown shipping remain visible', async ({ page }, testInfo) => {
  await openView(page, 'profiles');
  await page.locator('#profile-json').fill('{}');
  const profilePromise = page.waitForResponse(response => response.url().endsWith('/api/profiles/review'));
  await page.locator('#review-profile').click();
  const profile = await (await profilePromise).json();
  expect(profile.decision).toBe('needs_input');
  expect(profile.can_prepare_profile).toBe(false);
  await expect(page.locator('#profile-decision')).toHaveText('정보 입력 필요');
  await noHorizontalOverflow(page);

  await openView(page, 'offers');
  for (const [index, name, price, grams, shipping] of [
    [1, 'A', '12000', '1000', '3000'],
    [2, 'B', '7000', '500', '0'],
    [3, 'C', '9000', '1000', ''],
  ]) {
    for (const [field, value] of Object.entries({ name, price, grams, shipping })) {
      await page.locator(`#offer-${index}-${field}`).fill(value);
    }
  }
  const comparisonPromise = page.waitForResponse(response => response.url().endsWith('/api/offers/compare'));
  await page.locator('#compare-offers').click();
  const comparison = await (await comparisonPromise).json();
  expect(comparison.live_prices).toBe(false);
  expect(comparison.groups.KRW[0].name).toBe('B');
  expect(comparison.groups.KRW[0].price_per_kg).toBe(14000);
  expect(comparison.groups.KRW[2].price_per_kg).toBeNull();
  await expect(page.locator('#offers-result')).toBeVisible();
  await expect(page.locator('#offer-comparison tbody tr').first().locator('td').first()).toHaveText('B');
  await expect(page.locator('#offer-comparison')).toContainText('14,000');
  await expect(page.locator('#offer-comparison')).toContainText('15,000');
  await expect(page.locator('#offer-comparison')).toContainText('배송비 미확인');
  await noHorizontalOverflow(page);
  await page.screenshot({ path: testInfo.outputPath('price-comparison.png'), fullPage: true });

  await expect(page.locator('#compare-offers')).toBeEnabled();
  await page.locator('#offer-1-price').fill('13000');
  await expect(page.locator('#offers-result')).toBeHidden();
});

test('a rejected CAD request remains inspectable in history without a fake model', async ({ page }, testInfo) => {
  await page.locator('#parameter-width').fill('10');
  await page.locator('#parameter-depth').fill('10');
  await page.locator('#parameter-height').fill('2');
  await page.locator('#parameter-wall').fill('8');
  page.__expectedHttpFailures.push({ path: '/api/models', status: 422 });
  const rejectedPromise = page.waitForResponse(response =>
    response.url().endsWith('/api/models') && response.request().method() === 'POST');
  await page.locator('#generate-button').click();
  const rejected = await rejectedPromise;
  expect(rejected.status()).toBe(422);
  const failure = await rejected.json();
  expect(typeof failure.detail).toBe('string');
  expect(failure.detail.length).toBeGreaterThan(0);
  await expect(page.locator('#model-feedback')).toContainText(failure.detail);
  await expect(page.locator('#model-result')).toBeHidden();
  await expect(page.locator('#generate-button')).toBeEnabled();

  await openView(page, 'history');
  const failed = page.locator('.history-item').filter({ hasText: '모델 생성 실패' }).first();
  await expect(failed).toBeVisible();
  await failed.getByRole('button', { name: '기록 보기' }).click();
  await expect(page.locator('#history-feedback')).toContainText(failure.detail);
  await expect(page.locator('#model-result')).toBeHidden();
  await expect(page.locator('#model-canvas')).toBeHidden();
  await noHorizontalOverflow(page);
  await page.screenshot({ path: testInfo.outputPath('failed-job-history.png'), fullPage: true });
});

function presetUpload(name, profile) {
  return { name, mimeType: 'application/json', buffer: Buffer.from(JSON.stringify(profile)) };
}

// Native-shaped synthetic inputs exercise UI preservation, not print settings.
function nativeConfigFixture() {
  return {
    source: 'user_export', plate_type: 'High Temp Plate',
    machine: {
      name: 'Browser fixture machine 0.4 nozzle', type: 'machine', from: 'system',
      printer_model: 'Browser fixture machine', printer_technology: 'FFF',
      nozzle_diameter: ['0.4'], printable_area: ['0x0', '200x0', '200x200', '0x200'], printable_height: '200',
      machine_start_gcode: '; synthetic fixture start', machine_end_gcode: '; synthetic fixture end',
    },
    process: {
      name: 'Browser fixture process', type: 'process', from: 'user',
      compatible_printers: ['Browser fixture machine 0.4 nozzle'],
      layer_height: '0.2', initial_layer_print_height: '0.2', wall_loops: '2', top_shell_layers: '4', bottom_shell_layers: '4',
      sparse_infill_density: '15%', outer_wall_speed: '50', inner_wall_speed: '75', sparse_infill_speed: '100', initial_layer_speed: '20',
    },
    filaments: [{
      name: 'Browser fixture filament', type: 'filament', from: 'user', filament_type: ['PLA'],
      filament_diameter: ['1.75'], filament_density: ['1.2'], filament_flow_ratio: ['1'], filament_max_volumetric_speed: ['10'],
      nozzle_temperature: ['210'], nozzle_temperature_initial_layer: ['215'], hot_plate_temp: ['55'], hot_plate_temp_initial_layer: ['55'],
    }],
  };
}

// Synthetic settings prove data flow only; they are not printing recommendations.
function inheritedPresetFixture() {
  const setup = {
    printer_model: 'Fixture Printer', printer_preset: 'Fixture Printer 0.4 nozzle',
    nozzle_diameter: 0.4, plate_type: 'Textured PEI Plate', extruder: 'fixture_extruder',
    feed_mode: 'external_spool', material_id: 'fixture:synthetic-pla', material_identity_status: 'exact',
  };
  const base = {
    type: 'filament', name: 'Synthetic Base', instantiation: 'false',
    description: '<img src=x onerror="window.fixtureExecuted=true">',
    nozzle_temperature: ['205'], nozzle_temperature_initial_layer: ['205'],
    filament_flow_ratio: ['0.98'], filament_max_volumetric_speed: ['12'],
    textured_plate_temp: ['55'], textured_plate_temp_initial_layer: ['55'],
  };
  const child = {
    id: 'synthetic-child',
    settings: { type: 'filament', name: 'Synthetic Child', inherits: 'Synthetic Base', nozzle_temperature: ['215'], compatible_printers: ['Fixture Printer 0.4 nozzle'] },
    scope: Object.fromEntries(Object.entries(setup).filter(([key]) => key !== 'material_identity_status')),
    source: { authority: 'user', publisher: 'Synthetic fixture; not a manufacturer' },
  };
  return { base, child, setup };
}

test('imported presets recover a missing parent, preserve overrides and export evidence without stale results', async ({ page }, testInfo) => {
  const { base, child, setup } = inheritedPresetFixture();
  await openView(page, 'profiles');
  await page.locator('#profile-file').setInputFiles(presetUpload('child.json', child));
  await expect(page.locator('#profile-target option')).toHaveCount(1);
  await expect(page.locator('#profile-target')).toHaveValue('0');
  const missingResponse = page.waitForResponse(response => response.url().endsWith('/api/profiles/resolve'));
  await page.locator('#review-profile').click();
  const missing = await (await missingResponse).json();
  expect(missing.status).toBe('needs_input');
  expect(missing.resolved_profile).toBeNull();
  await expect(page.locator('#profile-resolution-issues')).toContainText('Synthetic Base');
  await expect(page.locator('#profile-result')).toBeHidden();
  await expect(page.locator('#review-profile')).toBeEnabled();

  await page.locator('#profile-file').setInputFiles(presetUpload('base.json', base));
  await expect(page.locator('#profile-target option')).toHaveCount(2);
  await expect(page.locator('#profile-target')).toHaveValue('0');
  await expect(page.locator('#profile-resolution')).toBeHidden();
  await expect(page.locator('#profile-download')).toBeHidden();
  expect(JSON.parse(await page.locator('#profile-json').inputValue())).toEqual(child);

  const edited = structuredClone(child);
  edited.settings.nozzle_temperature = ['220'];
  await page.locator('#profile-json').fill(JSON.stringify(edited));
  for (const [name, value] of Object.entries(setup)) {
    const field = page.locator(`.setup-grid [name="${name}"]`);
    if (name === 'material_identity_status') await field.selectOption(value);
    else await field.fill(String(value));
  }
  const resolvedResponse = page.waitForResponse(response => response.url().endsWith('/api/profiles/resolve'));
  await page.locator('#review-profile').click();
  const resolved = await (await resolvedResponse).json();
  expect(resolved.status).toBe('resolved');
  expect(resolved.full_config).toBe(false);
  expect(resolved.native_verified).toBe(false);
  expect(resolved.chain.map(item => item.name)).toEqual(['Synthetic Base', 'Synthetic Child']);
  expect(resolved.resolved_profile.settings.nozzle_temperature).toEqual(['220']);
  expect(resolved.resolved_profile.settings.filament_flow_ratio).toEqual(['0.98']);
  expect(resolved.field_sources.nozzle_temperature.history.map(item => item.value)).toEqual([['205'], ['220']]);
  expect(resolved.field_sources.filament_flow_ratio.inherited).toBe(true);
  await expect(page.locator('#profile-chain')).toContainText('Synthetic Base');
  await expect(page.locator('#profile-fields tr[data-field="nozzle_temperature"] td').first()).toHaveText('["220"]');
  await expect(page.locator('#profile-fields tr[data-field="filament_flow_ratio"]')).toContainText('base.json');
  await expect(page.locator('#profile-decision')).toHaveText('프로필 준비 가능');
  await expect(page.locator('#profile-resolution img')).toHaveCount(0);
  expect(await page.evaluate(() => window.fixtureExecuted)).toBeUndefined();

  const downloadPromise = page.waitForEvent('download');
  await page.locator('#profile-download').click();
  const download = await downloadPromise;
  expect(download.suggestedFilename()).toBe('filament-review.json');
  const file = testInfo.outputPath('filament-review.json');
  await download.saveAs(file);
  const report = JSON.parse(await fs.readFile(file, 'utf8'));
  expect(report.documents[0].profile.settings.nozzle_temperature).toEqual(['220']);
  expect(report.imported_documents[0].profile).toEqual(child);
  expect(report.imported_documents[1].profile).toEqual(base);
  expect(report.edited_filenames).toEqual(['child.json']);
  expect(report.setup).toEqual(setup);
  expect(report.full_config).toBe(false);
  expect(report.native_verified).toBe(false);
  expect(report.documents.every(document => /^[a-f0-9]{64}$/.test(document.sha256))).toBe(true);
  await noHorizontalOverflow(page);
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.screenshot({ path: testInfo.outputPath('filament-inheritance.png'), fullPage: true });

  await expect(page.locator('#review-profile')).toBeEnabled();
  await page.locator('#setup-nozzle').fill('0.6');
  await expect(page.locator('#profile-result')).toBeHidden();
  await expect(page.locator('#profile-resolution')).toBeHidden();
  await expect(page.locator('#profile-download')).not.toHaveAttribute('href');
  await page.locator('#profile-target').selectOption('1');
  expect(JSON.parse(await page.locator('#profile-json').inputValue())).toEqual(base);
  await page.locator('#profile-target').selectOption('0');
  expect(JSON.parse(await page.locator('#profile-json').inputValue())).toEqual(edited);
  await page.locator('#profile-clear').click();
  await expect(page.locator('#profile-library')).toBeHidden();
  await page.locator('#profile-json').fill('{}');
  const standalone = page.waitForResponse(response => response.url().endsWith('/api/profiles/review'));
  await page.locator('#review-profile').click();
  expect((await standalone).status()).toBe(200);
  await expect(page.locator('#profile-resolution')).toBeHidden();
});

test('unsupported includes and malformed imports stay visible without claiming a resolved preset', async ({ page }, testInfo) => {
  const { base, child } = inheritedPresetFixture();
  child.settings.include = ['Unresolved template'];
  await openView(page, 'profiles');
  await page.locator('#profile-file').setInputFiles([presetUpload('child.json', child), presetUpload('base.json', base)]);
  await expect(page.locator('#profile-target option')).toHaveCount(2);
  const response = page.waitForResponse(result => result.url().endsWith('/api/profiles/resolve'));
  await page.locator('#review-profile').click();
  const blocked = await (await response).json();
  expect(blocked.status).toBe('blocked');
  expect(blocked.resolved_profile).toBeNull();
  expect(blocked.review).toBeNull();
  await expect(page.locator('#profile-resolution-issues')).not.toBeEmpty();
  await expect(page.locator('#profile-fields table')).toHaveCount(0);
  await expect(page.locator('#profile-result')).toBeHidden();
  await expect(page.locator('#review-profile')).toBeEnabled();
  const previous = await page.locator('#profile-json').inputValue();
  await page.locator('#profile-file').setInputFiles({ name: 'broken.json', mimeType: 'application/json', buffer: Buffer.from('{broken') });
  await expect(page.locator('#profile-feedback')).toContainText('broken.json');
  await expect(page.locator('#profile-json')).toHaveValue(previous);
  await expect(page.locator('#profile-target option')).toHaveCount(2);
  await expect(page.locator('#profile-resolution')).toBeHidden();
  await expect(page.locator('#profile-download')).not.toHaveAttribute('href');
  await noHorizontalOverflow(page);
  await page.screenshot({ path: testInfo.outputPath('filament-import-error.png'), fullPage: true });
});

test('guided filament edits survive save and reload with original evidence and stale validation', async ({ page }, testInfo) => {
  const { base, child, setup } = inheritedPresetFixture();
  child.validation = { status: 'measured_on_matching_setup', setup_fingerprint: child.scope };
  await openView(page, 'profiles');
  await page.locator('#profile-file').setInputFiles([presetUpload('base.json', base), presetUpload('child.json', child)]);
  await expect(page.locator('#profile-target option')).toHaveCount(2);
  await page.locator('#profile-target').selectOption('1');
  for (const [name, value] of Object.entries(setup)) {
    const field = page.locator(`.setup-grid [name="${name}"]`);
    if (name === 'material_identity_status') await field.selectOption(value);
    else await field.fill(String(value));
  }
  const originalReview = page.waitForResponse(response => response.url().endsWith('/api/profiles/resolve'));
  await page.locator('#review-profile').click();
  const originalReport = await (await originalReview).json();
  expect(originalReport.edit_review.status).toBe('unchanged');
  expect(originalReport.review.validation_status).toBe('reported_validated');
  await expect(page.locator('#guided-filament_flow_ratio')).toHaveValue('0.98');
  await expect(page.locator('#guided-filament_flow_ratio')).toBeEnabled();
  await page.locator('#guided-filament_flow_ratio').fill('0.99');
  await expect(page.locator('#profile-json')).toBeDisabled();
  await expect(page.locator('#profile-resolution')).toBeHidden();
  await expect(page.locator('#workspace-status')).toHaveText('편집값 적용 필요');
  expect(JSON.parse(await page.locator('#profile-json').inputValue())).toEqual(child);
  await page.locator('#profile-guided-apply').click();
  await expect(page.locator('#profile-json')).toBeEnabled();
  const edited = JSON.parse(await page.locator('#profile-json').inputValue());
  expect(edited.settings.filament_flow_ratio).toEqual(['0.99']);
  expect(edited.settings.inherits).toBe('Synthetic Base');
  expect(edited.source).toEqual(child.source);
  expect(edited.validation).toEqual(child.validation);

  const title = `Filament CI ${testInfo.project.name} ${Date.now()}`;
  await page.locator('#workspace-title').fill(title);
  const savedPromise = page.waitForResponse(response => response.url().endsWith('/api/profile-workspaces') && response.request().method() === 'POST');
  await page.locator('#workspace-save').click();
  const savedResponse = await savedPromise;
  expect(savedResponse.status()).toBe(201);
  const saved = await savedResponse.json();
  expect(saved.snapshot.documents[0].profile).toEqual(base);
  expect(saved.snapshot.documents[1].profile).toEqual(child);
  expect(JSON.parse(saved.snapshot.documents[1].draft_text)).toEqual(edited);
  expect(saved.snapshot.target_index).toBe(1);
  expect(saved.snapshot.setup).toEqual(Object.fromEntries(Object.entries(setup).map(([name, value]) => [name, String(value)])));
  await expect(page.locator('#workspace-status')).toHaveText('저장됨');
  await expect(page.locator('#workspace-save')).toBeEnabled();

  await page.reload();
  await expect(page.locator('#generate-button')).toBeEnabled();
  await openView(page, 'profiles');
  await expect(page.locator(`#workspace-list option[value="${saved.id}"]`)).toHaveCount(1);
  await page.locator('#workspace-list').selectOption(saved.id);
  await page.locator('#workspace-open').click();
  await expect(page.locator('#workspace-title')).toHaveValue(title);
  await expect(page.locator('#profile-target')).toHaveValue('1');
  expect(JSON.parse(await page.locator('#profile-json').inputValue())).toEqual(edited);
  for (const [name, value] of Object.entries(setup)) await expect(page.locator(`.setup-grid [name="${name}"]`)).toHaveValue(String(value));
  await expect(page.locator('#workspace-status')).toHaveText('저장됨');
  await expect(page.locator('#profile-result')).toBeHidden();
  await expect(page.locator('#profile-resolution')).toBeHidden();
  await expect(page.locator('#profile-download')).not.toHaveAttribute('href');

  const editedReview = page.waitForResponse(response => response.url().endsWith('/api/profiles/resolve'));
  await page.locator('#review-profile').click();
  const reviewed = await (await editedReview).json();
  expect(reviewed.edit_review.status).toBe('changed');
  expect(reviewed.edit_review.changed_fields).toEqual(['filament_flow_ratio']);
  expect(reviewed.edit_review.validation_invalidated).toBe(true);
  expect(reviewed.review.validation_status).toBe('stale');
  expect(reviewed.review.can_prepare_profile).toBe(false);
  expect(reviewed.field_sources.filament_flow_ratio.edited).toBe(true);
  await expect(page.locator('#profile-summary')).toContainText('재확인 필요');
  await expect(page.locator('#profile-edit-review')).toContainText('이전 검증 보고');
  await expect(page.locator('#profile-fields tr[data-field="filament_flow_ratio"]')).toContainText('사용자 수정값');
  const downloadPromise = page.waitForEvent('download');
  await page.locator('#profile-download').click();
  const download = await downloadPromise;
  const reportPath = testInfo.outputPath('filament-workspace-review.json');
  await download.saveAs(reportPath);
  const report = JSON.parse(await fs.readFile(reportPath, 'utf8'));
  expect(report.imported_documents.map(document => document.profile)).toEqual([base, child]);
  expect(report.documents.map(document => document.profile)).toEqual([base, edited]);
  expect(report.review.validation_status).toBe('stale');
  expect(report.setup).toEqual(setup);
  expect(report.full_config).toBe(false);
  expect(report.native_verified).toBe(false);
  await noHorizontalOverflow(page);
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.screenshot({ path: testInfo.outputPath('saved-filament-workspace.png'), fullPage: true });

  const unfinished = '  { "name": "unfinished",\n  "settings": ';
  await page.locator('#profile-json').fill(unfinished);
  const updatePromise = page.waitForResponse(response => response.url().endsWith(`/api/profile-workspaces/${saved.id}`) && response.request().method() === 'PUT');
  await page.locator('#workspace-save').click();
  const updated = await (await updatePromise).json();
  expect(updated.revision).toBe(2);
  expect(updated.snapshot.documents[1].draft_text).toBe(unfinished);
  await expect(page.locator('#workspace-save')).toBeEnabled();
  await expect(page.locator('#workspace-status')).toHaveText('저장됨');
  await page.reload();
  await expect(page.locator('#generate-button')).toBeEnabled();
  await openView(page, 'profiles');
  await expect(page.locator(`#workspace-list option[value="${saved.id}"]`)).toHaveCount(1);
  await page.locator('#workspace-list').selectOption(saved.id);
  await page.locator('#workspace-open').click();
  await expect(page.locator('#profile-json')).toHaveValue(unfinished);
  await expect(page.locator('#profile-guided-help')).toContainText('그대로 저장');
  await expect(page.locator('#workspace-open')).toBeEnabled();
  page.once('dialog', dialog => dialog.accept());
  await page.locator('#profile-restore').click();
  expect(JSON.parse(await page.locator('#profile-json').inputValue())).toEqual(child);
  await page.locator('#profile-target').selectOption('0');
  page.once('dialog', dialog => dialog.accept());
  await page.locator('#profile-remove').click();
  await expect(page.locator('#profile-target option')).toHaveCount(1);
  expect(JSON.parse(await page.locator('#profile-json').inputValue())).toEqual(child);
  const missingParent = page.waitForResponse(response => response.url().endsWith('/api/profiles/resolve'));
  await page.locator('#review-profile').click();
  expect((await (await missingParent).json()).status).toBe('needs_input');
  await expect(page.locator('#profile-resolution-issues')).toContainText('Synthetic Base');
});

test('workspace conflicts preserve edits, allow a separate copy and delete only its saved record', async ({ page }, testInfo) => {
  await openView(page, 'profiles');
  const original = { name: 'Pasted synthetic profile', type: 'filament', nozzle_temperature: 210 };
  await page.locator('#profile-json').fill(JSON.stringify(original));
  await page.locator('#profile-adopt').click();
  await expect(page.locator('#profile-target option')).toHaveCount(1);
  const title = `Conflict CI ${testInfo.project.name} ${Date.now()}`;
  await page.locator('#workspace-title').fill(title);
  const createPromise = page.waitForResponse(response => response.url().endsWith('/api/profile-workspaces') && response.request().method() === 'POST');
  await page.locator('#workspace-save').click();
  const saved = await (await createPromise).json();
  await expect(page.locator('#workspace-save')).toBeEnabled();
  const bootstrap = await (await page.request.get('/api/bootstrap')).json();
  const otherTab = await page.request.put(`/api/profile-workspaces/${saved.id}`, {
    headers: { 'X-Session-Token': bootstrap.session_token },
    data: { title: `${title} changed elsewhere`, snapshot: saved.snapshot, expected_revision: 1 },
  });
  expect(otherTab.status()).toBe(200);
  expect((await otherTab.json()).revision).toBe(2);
  const unfinished = '{ "name": "keep this unfinished draft",';
  await page.locator('#profile-json').fill(unfinished);
  page.__expectedHttpFailures.push({ path: `/api/profile-workspaces/${saved.id}`, status: 409 });
  const conflictPromise = page.waitForResponse(response => response.url().endsWith(`/api/profile-workspaces/${saved.id}`) && response.request().method() === 'PUT');
  await page.locator('#workspace-save').click();
  expect((await conflictPromise).status()).toBe(409);
  await expect(page.locator('#workspace-feedback')).toContainText('다른 이름으로 저장');
  await expect(page.locator('#profile-json')).toHaveValue(unfinished);
  await expect(page.locator('#workspace-status')).toHaveText('저장하지 않은 변경');
  await page.locator('#workspace-title').fill(`${title} copy`);
  const copyPromise = page.waitForResponse(response => response.url().endsWith('/api/profile-workspaces') && response.request().method() === 'POST');
  await page.locator('#workspace-save-copy').click();
  const copy = await (await copyPromise).json();
  expect(copy.id).not.toBe(saved.id);
  expect(copy.snapshot.documents[0].profile).toEqual(original);
  expect(copy.snapshot.documents[0].draft_text).toBe(unfinished);
  await expect(page.locator('#workspace-save-copy')).toBeEnabled();
  await expect(page.locator('#workspace-status')).toHaveText('저장됨');
  const deletePromise = page.waitForResponse(response => response.url().endsWith(`/api/profile-workspaces/${copy.id}`) && response.request().method() === 'DELETE');
  page.once('dialog', dialog => dialog.accept());
  await page.locator('#workspace-delete').click();
  expect((await deletePromise).status()).toBe(200);
  await expect(page.locator('#workspace-delete')).toBeDisabled();
  await expect(page.locator('#workspace-feedback')).toContainText('저장본을 삭제');
  await expect(page.locator('#profile-json')).toHaveValue(unfinished);
  await expect(page.locator(`#workspace-list option[value="${copy.id}"]`)).toHaveCount(0);
  const retained = await page.request.get(`/api/profile-workspaces/${saved.id}`);
  expect(retained.status()).toBe(200);
  expect((await retained.json()).revision).toBe(2);
  await noHorizontalOverflow(page);
  await page.screenshot({ path: testInfo.outputPath('filament-workspace-recovery.png'), fullPage: true });
});
