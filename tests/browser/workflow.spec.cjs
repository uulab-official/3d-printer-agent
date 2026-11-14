const fs = require('node:fs/promises');
const crypto = require('node:crypto');
const { test, expect } = require('@playwright/test');
const { filamentArchive, printerArchive } = require('./archive-fixture.cjs');
const { isolatedRuntime } = require('./runtime-server.cjs');

// Servers and CAD are real. Recovery scenarios explicitly label delayed real
// responses and synthetic HTTP 503 failures. Runtime scenarios restart a real
// isolated process; the history seed creates synthetic failed/interrupted jobs.
// CAD generation is never mocked.
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

async function openProfileEvidence(page, testInfo) {
  await page.locator('#profile-evidence summary').click();
  await expect(page.locator('#profile-evidence')).toHaveJSProperty('open', true);
  try {
    await expect(page.locator('#evidence-scope-printer_model')).toBeVisible();
    await expect(page.locator('#evidence-source-authority')).toBeVisible();
  } catch (error) {
    const layout = await page.locator('#profile-evidence').evaluate(details =>
      [details, ...details.querySelectorAll('[role="group"], fieldset, legend, h4, .guided-fields, input')].map(element => {
        const style = getComputedStyle(element), rect = element.getBoundingClientRect();
        return { tag: element.tagName, id: element.id, hidden: element.hidden,
          display: style.display, visibility: style.visibility, contentVisibility: style.contentVisibility,
          width: rect.width, height: rect.height };
      }));
    await testInfo.attach('evidence-layout.json', { body: JSON.stringify(layout, null, 2), contentType: 'application/json' });
    throw error;
  }
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

test('real server restart reconnects without replay and preserves unfinished work before confirmed history restore', async ({ page }, testInfo) => {
  test.setTimeout(120000);
  const runtime = await isolatedRuntime(testInfo);
  try {
    await runtime.start();
    await page.goto(runtime.url);
    await expect(page.locator('#generate-button')).toBeEnabled();
    await expect(page.locator('#storage-path')).toContainText('로컬 작업 데이터');
    await page.locator('#storage-details > summary').click();
    await expect(page.locator('#storage-path')).toBeVisible();
    await page.locator('#discovery-cards [data-project-id="small-parts-tray"]').click();
    await page.locator('#discovery-apply').click();
    // The server really creates CAD, but reconnect happens before this older
    // successful response reaches the browser. Recover it explicitly in history.
    let releaseGeneration, generated;
    const heldGeneration = new Promise(resolve => { releaseGeneration = resolve; });
    const generatedOnServer = new Promise(resolve => { generated = resolve; });
    await page.route(runtime.url + '/api/models', async route => {
      const actual = await route.fetch();
      expect(actual.status()).toBe(200);
      generated();
      await heldGeneration;
      await route.fulfill({ response: actual });
    }, { times: 1 });
    const created = page.waitForResponse(response => response.url() === runtime.url + '/api/models');
    await page.locator('#generate-button').click();
    await generatedOnServer;
    const refreshedConnection = page.waitForResponse(response => response.url() === runtime.url + '/api/bootstrap');
    await page.locator('#reconnect-button').click();
    await (await refreshedConnection).finished();
    releaseGeneration();
    const job = await (await created).json();
    expect(job.result.geometry_status).toBe('validated');
    await expect(page.locator('#generate-button')).toBeEnabled();
    await expect(page.locator('#model-result')).toBeHidden();
    await expect(page.locator('#model-feedback')).toContainText(/연결|이전/);
    await openView(page, 'history');
    await page.locator('.history-item').filter({ hasText: job.title }).getByRole('button', { name: '열기' }).click();
    await expect(page.locator('#model-replace-confirm')).toBeVisible();
    await page.locator('#model-confirm-replace').click();
    await expect(page.locator('#model-result')).toBeVisible();

    const requestText = '연결이 끊겨도 이 요청과 미완성 치수는 그대로 보관합니다.';
    await page.locator('#request-text').fill(requestText);
    await page.locator('#parameter-width').fill('');
    await page.locator('#parameter-width').press('-');
    expect(await page.locator('#parameter-width').evaluate(input => input.validity.badInput)).toBe(true);
    await openView(page, 'profiles');
    const unfinishedProfile = '{ "name": "재연결 중 보존할 편집",';
    await page.locator('#profile-json').fill(unfinishedProfile);
    await openView(page, 'models');

    await runtime.stop();
    const restarted = await runtime.start();
    page.__expectedHttpFailures.push({ path: '/api/discovery', status: 403 });
    expect((await findProjects(page)).status()).toBe(403);
    await expect(page.locator('#connection-detail')).toContainText('연결');
    await expect(page.locator('#reconnect-button')).toBeEnabled();
    await page.locator('#local-runtime').screenshot({ path: testInfo.outputPath('session-expired.png'), scale: 'css' });

    const writes = [];
    const countWrites = request => { if (!['GET', 'HEAD'].includes(request.method())) writes.push(request.url()); };
    page.on('request', countWrites);
    const freshBootstrap = page.waitForResponse(response => response.url() === runtime.url + '/api/bootstrap');
    await page.locator('#reconnect-button').click();
    expect((await (await freshBootstrap).json()).session_token).toBe(restarted.session_token);
    await expect(page.locator('#generate-button')).toBeEnabled();
    expect(await page.locator('#parameter-width').evaluate(input => input.validity.badInput)).toBe(true);
    await expect(page.locator('#request-text')).toHaveValue(requestText);
    await expect(page.locator('#profile-json')).toHaveValue(unfinishedProfile);
    expect(writes).toEqual([]);
    page.off('request', countWrites);
    await page.locator('#local-runtime').screenshot({ path: testInfo.outputPath('session-reconnected.png'), scale: 'css' });

    await openView(page, 'history');
    const card = page.locator('.history-item').filter({ hasText: job.title });
    await card.getByRole('button', { name: '열기' }).click();
    await expect(page.locator('#model-replace-confirm')).toBeVisible();
    await noHorizontalOverflow(page);
    await page.locator('#model-replace-confirm').screenshot({ path: testInfo.outputPath('history-replacement.png'), scale: 'css' });
    await page.locator('#model-cancel-replace').click();
    expect(await page.locator('#parameter-width').evaluate(input => input.validity.badInput)).toBe(true);
    await expect(page.locator('#request-text')).toHaveValue(requestText);
    await card.getByRole('button', { name: '열기' }).click();
    await page.locator('#model-confirm-replace').click();
    await expect(page.locator('#model-result')).toBeVisible();
    await expect(page.locator('#parameter-width')).toHaveValue('90');
    await expect(page.locator('#generated-source')).toContainText('작은 물건 트레이');
    await expect(page.locator('#profile-json')).toHaveValue(unfinishedProfile);

    const retained = await (await page.request.get(runtime.url + '/api/jobs/' + job.id)).json();
    expect(retained.design_source).toEqual(job.design_source);
    const manifest = await (await page.request.get(runtime.url + job.artifacts.manifest)).json();
    const bytes = await (await page.request.get(runtime.url + job.artifacts.three_mf)).body();
    expect(crypto.createHash('sha256').update(bytes).digest('hex')).toBe(manifest.artifacts.three_mf.sha256);
    await fs.writeFile(testInfo.outputPath('recovered-job.json'), JSON.stringify(retained, null, 2));
    await fs.writeFile(testInfo.outputPath('recovered-manifest.json'), JSON.stringify(manifest, null, 2));
    await fs.writeFile(testInfo.outputPath('recovered-model.3mf'), bytes);
    await noHorizontalOverflow(page);
  } finally {
    await runtime.stop();
  }
});

test('history reaches older real CAD beyond a hundred records and retains its list after superseded failures', async ({ page }, testInfo) => {
  test.setTimeout(120000);
  const runtime = await isolatedRuntime(testInfo);
  try {
    await runtime.start();
    await page.goto(runtime.url);
    await expect(page.locator('#generate-button')).toBeEnabled();
    const created = page.waitForResponse(response => response.url() === runtime.url + '/api/models');
    await page.locator('#generate-button').click();
    const original = await (await created).json();
    await expect(page.locator('#model-result')).toBeVisible();
    await runtime.stop();
    const seeded = await runtime.seedInterruptedHistory();
    const bootstrap = await runtime.start();
    expect(bootstrap.storage.recovery).toEqual({ indexed: 104, interrupted: 1, unreadable: 1 });
    await page.locator('#reconnect-button').click();
    await expect(page.locator('#storage-recovery')).toContainText('1');
    await openView(page, 'history');
    await expect(page.locator('.history-item')).toHaveCount(20);
    await expect(page.locator('#history-more')).toBeVisible();
    await expect(page.locator('#history-list')).toContainText('중단');

    // Hold a real list response, then replace only that older response with an
    // explicitly synthetic failure after a newer real refresh has succeeded.
    let release, fetched;
    const held = new Promise(resolve => { release = resolve; });
    const ready = new Promise(resolve => { fetched = resolve; });
    page.__expectedHttpFailures.push({ path: '/api/jobs?limit=20', status: 503 });
    await page.route('**/api/jobs?limit=20', async route => {
      const actual = await route.fetch();
      expect(actual.status()).toBe(200);
      fetched();
      await held;
      await route.fulfill({ status: 503, contentType: 'application/json',
        body: JSON.stringify({ detail: '브라우저 검사 전용 오래된 실패 응답' }) });
    }, { times: 1 });
    const staleResponse = page.waitForResponse(response => response.url() === runtime.url + '/api/jobs?limit=20' && response.status() === 503);
    await page.locator('#refresh-history').click();
    await ready;
    const latestResponse = page.waitForResponse(response => response.url() === runtime.url + '/api/jobs?limit=20' && response.status() === 200);
    await openView(page, 'models');
    await openView(page, 'history');
    await (await latestResponse).finished();
    await expect(page.locator('.history-item')).toHaveCount(20);
    release();
    await (await staleResponse).finished();
    await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));
    await expect(page.locator('.history-item')).toHaveCount(20);
    await expect(page.locator('#history-feedback')).not.toContainText('오래된 실패');

    await page.route('**/api/jobs?limit=20', route => route.fulfill({ status: 503,
      contentType: 'application/json', body: JSON.stringify({ detail: '브라우저 검사 전용 현재 목록 오류' }) }), { times: 1 });
    await page.locator('#refresh-history').click();
    await expect(page.locator('#history-feedback')).toContainText('현재 목록 오류');
    await expect(page.locator('.history-item')).toHaveCount(20);
    await page.locator('#refresh-history').click();
    await expect(page.locator('#history-feedback')).toBeHidden();
    for (let count = 0; count < 5; count++) {
      await page.locator('#history-more').click();
      await expect(page.locator('.history-item')).toHaveCount(Math.min(40 + count * 20, 105));
    }
    await expect(page.locator('#history-more')).toBeHidden();
    const oldest = page.locator('.history-item').filter({ hasText: original.title });
    await expect(oldest).toBeVisible();
    await noHorizontalOverflow(page);
    await oldest.screenshot({ path: testInfo.outputPath('older-cad-history.png'), scale: 'css' });
    await page.locator('#storage-details > summary').click();
    await expect(page.locator('#storage-path')).toBeVisible();
    await page.locator('#local-runtime').screenshot({ path: testInfo.outputPath('startup-recovery.png'), scale: 'css' });
    await oldest.getByRole('button', { name: '열기' }).click();
    await expect(page.locator('#model-result')).toBeVisible();
    const interrupted = await (await page.request.get(runtime.url + '/api/jobs/' + seeded.interrupted)).json();
    expect(interrupted.status).toBe('interrupted');
    expect(interrupted.request.width).toBe(139);
    expect(interrupted.artifacts).toEqual({});
    const originalAgain = await (await page.request.get(runtime.url + '/api/jobs/' + original.id)).json();
    expect(originalAgain.result).toEqual(original.result);
    await fs.writeFile(testInfo.outputPath('history-recovery.json'), JSON.stringify({
      seed: seeded, recovery: bootstrap.storage.recovery, interrupted, original_job_id: original.id,
      reached_records: 105, older_real_cad_preserved: true,
    }, null, 2));
  } finally {
    await runtime.stop();
  }
});

async function findProjects(page) {
  const response = page.waitForResponse(item =>
    item.url().endsWith('/api/discovery') && item.request().method() === 'POST');
  await page.locator('#discovery-submit').click();
  return await response;
}

test('local project discovery reaches customized real CAD and preserves its recipe through downloads and history', async ({ page }, testInfo) => {
  await expect(page.locator('#discovery-cards [data-project-id]')).toHaveCount(6);
  await page.locator('#discovery-purpose [data-purpose="organization"]').click();
  for (const [axis, value] of Object.entries({ width: '150', depth: '90', height: '30' })) {
    await page.locator(`#space-${axis}`).fill(value);
  }
  const recommendationResponse = await findProjects(page);
  expect(recommendationResponse.status()).toBe(200);
  const recommendations = await recommendationResponse.json();
  expect(recommendations.matches.map(item => item.project.id)).toEqual(['small-parts-tray', 'desk-sorter']);
  await expect(page.locator('#discovery-cards [data-project-id]')).toHaveCount(2);
  await fs.writeFile(testInfo.outputPath('discovery-recommendations.json'), await recommendationResponse.text());
  await noHorizontalOverflow(page);
  await page.locator('#discovery-cards').screenshot({ path: testInfo.outputPath('discovery-candidates.png'), scale: 'css' });

  await page.locator('#discovery-cards [data-project-id="desk-sorter"]').click();
  await expect(page.locator('#discovery-detail')).toBeVisible();
  await expect(page.locator('#discovery-measurements')).toContainText('측정');
  await expect(page.locator('#parameter-width')).toHaveValue('120');
  await page.locator('#discovery-detail').screenshot({ path: testInfo.outputPath('discovery-detail.png'), scale: 'css' });
  await page.locator('#discovery-apply').click();
  await expect(page.locator('#parameter-width')).toHaveValue('150');
  await expect(page.locator('#parameter-dividers')).toHaveValue('2');
  await expect(page.locator('#draft-source')).toContainText('세 칸 책상 정리함');
  await expect(page.locator('#model-result')).toBeHidden();
  await page.locator('#parameter-width').fill('152');

  const generatedResponse = page.waitForResponse(response =>
    response.url().endsWith('/api/models') && response.request().method() === 'POST');
  await page.locator('#generate-button').click();
  const response = await generatedResponse;
  expect(response.status()).toBe(200);
  const job = await response.json();
  const recipe = recommendations.matches.find(item => item.project.id === 'desk-sorter').project;
  expect(response.request().postDataJSON().project_selection).toEqual({
    id: recipe.id, recipe_sha256: recipe.recipe_sha256,
  });
  expect(job.result.dimensions_mm).toEqual({ x: 152, y: 90, z: 30 });
  expect(job.result.geometry_status).toBe('validated');
  expect(job.result.print_status).toBe('not_tested');
  expect(job.result.checks.every(item => item.passed)).toBe(true);
  expect(job.design_source.project_id).toBe('desk-sorter');
  expect(job.design_source.recipe_sha256).toBe(recipe.recipe_sha256);
  expect(job.design_source.recipe.parameters.width).toBe(150);
  expect(job.design_source.customized).toBe(true);
  expect(job.design_source.changed_parameters).toEqual(['width']);
  expect(job.latest_slice).toBeNull();
  await fs.writeFile(testInfo.outputPath('discovery-job.json'), await response.text());
  await expect(page.locator('#generated-source')).toBeVisible();
  await expect(page.locator('#generated-source')).toContainText('세 칸 책상 정리함');
  await expect(page.locator('#generated-source')).toContainText('가로');
  await expect(page.locator('#model-canvas')).toBeVisible();
  await noHorizontalOverflow(page);
  await page.locator('#model-result').screenshot({ path: testInfo.outputPath('discovery-generated.png'), scale: 'css' });

  const manifestDownloadPromise = page.waitForEvent('download');
  await page.locator('#download-links a').filter({ hasText: '생성 기록' }).click();
  const manifestDownload = await manifestDownloadPromise;
  const manifestFile = testInfo.outputPath('discovery-manifest.json');
  await manifestDownload.saveAs(manifestFile);
  const manifest = JSON.parse(await fs.readFile(manifestFile, 'utf8'));
  expect(manifest.design_source).toEqual(job.design_source);
  expect(manifest.parameters.width).toBe(152);
  expect(manifest.physical_print_status).toBe('not_tested');
  expect(manifest.slicer_status).toBe('not_run');
  const modelDownloadPromise = page.waitForEvent('download');
  await page.locator('#download-links a').filter({ hasText: '3MF 형상' }).click();
  const modelDownload = await modelDownloadPromise;
  const modelFile = testInfo.outputPath('discovery-model.3mf');
  await modelDownload.saveAs(modelFile);
  const modelBytes = await fs.readFile(modelFile);
  expect(modelBytes.length).toBe(manifest.artifacts.three_mf.bytes);
  expect(crypto.createHash('sha256').update(modelBytes).digest('hex')).toBe(manifest.artifacts.three_mf.sha256);

  // Browsing another idea must not relabel or invalidate the existing model.
  const manifestHref = await page.locator('#download-links a').filter({ hasText: '생성 기록' }).getAttribute('href');
  await page.locator('#discovery-cards [data-project-id="small-parts-tray"]').click();
  await expect(page.locator('#parameter-width')).toHaveValue('152');
  await expect(page.locator('#model-result')).toBeVisible();
  await expect(page.locator('#generated-source')).toContainText('세 칸 책상 정리함');
  await expect(page.locator('#download-links a').filter({ hasText: '생성 기록' })).toHaveAttribute('href', manifestHref);
  await page.locator('#discovery-apply').click();
  await expect(page.locator('#discovery-replace-confirm')).toBeVisible();
  await page.locator('#discovery-cancel-apply').click();
  await expect(page.locator('#parameter-width')).toHaveValue('152');
  await expect(page.locator('#model-result')).toBeVisible();

  await openView(page, 'history');
  await page.locator('.history-item').filter({ hasText: job.title }).first().getByRole('button', { name: '열기' }).click();
  await expect(page.locator('#parameter-width')).toHaveValue('152');
  await expect(page.locator('#draft-source')).toContainText('세 칸 책상 정리함');
  await expect(page.locator('#generated-source')).toContainText('세 칸 책상 정리함');
  await expect(page.locator('#model-result')).toBeVisible();
  await page.locator('.template-card[data-template="cable_comb"]').click();
  await expect(page.locator('#draft-source')).toBeHidden();
  await expect(page.locator('#model-result')).toBeHidden();
  await expect(page.locator('#download-links a')).toHaveCount(0);
  await noHorizontalOverflow(page);
});

test('discovery preserves unfinished drafts and recovers from empty, stale and failed recommendation responses', async ({ page }, testInfo) => {
  const requestText = '아직 수정 중인 요청을 그대로 보관합니다.';
  await page.locator('#request-text').fill(requestText);
  const width = page.locator('#parameter-width');
  await width.fill('');
  await width.press('-');
  await expect(width).toHaveValue('');
  expect(await width.evaluate(element => element.validity.badInput)).toBe(true);
  await page.locator('#discovery-purpose [data-purpose="cables"]').click();
  expect((await findProjects(page)).status()).toBe(200);
  await expect(page.locator('#discovery-cards [data-project-id]')).toHaveCount(2);
  await page.locator('#discovery-cards [data-project-id="three-cable-rest"]').click();
  await page.locator('#discovery-apply').click();
  await expect(page.locator('#discovery-replace-confirm')).toBeVisible();
  await page.locator('#discovery-cancel-apply').click();
  expect(await width.evaluate(element => element.validity.badInput)).toBe(true);
  await expect(page.locator('#request-text')).toHaveValue(requestText);
  await expect(page.locator('#draft-source')).toBeHidden();
  await width.fill('133');

  await page.locator('#space-height').fill('11');
  const emptyResponse = await findProjects(page);
  expect((await emptyResponse.json()).matches).toEqual([]);
  await expect(page.locator('#discovery-cards [data-project-id]')).toHaveCount(0);
  await expect(page.locator('#discovery-summary')).toContainText('없습니다');
  await expect(width).toHaveValue('133');
  await page.locator('#discovery-cards').screenshot({ path: testInfo.outputPath('discovery-empty.png'), scale: 'css' });

  let discoveryRequests = 0;
  const countRequests = request => { if (request.url().endsWith('/api/discovery')) discoveryRequests += 1; };
  page.on('request', countRequests);
  await page.locator('#space-width').press('-');
  expect(await page.locator('#space-width').evaluate(element => element.validity.badInput)).toBe(true);
  await page.locator('#discovery-submit').click();
  await expect(page.locator('#discovery-feedback')).toContainText('완성');
  expect(discoveryRequests).toBe(0);
  page.off('request', countRequests);
  for (const [axis, value] of Object.entries({ width: '60', depth: '20', height: '12' })) {
    await page.locator(`#space-${axis}`).fill(value);
  }
  expect((await findProjects(page)).status()).toBe(200);
  await expect(page.locator('#discovery-cards [data-project-id="three-cable-rest"]')).toBeVisible();
  await expect(page.locator('#discovery-cards [data-project-id]')).toHaveCount(1);

  // Delay a real successful HTTP response; its six results must not replace newer inputs.
  await page.locator('#discovery-purpose [data-purpose="all"]').click();
  for (const axis of ['width', 'depth', 'height']) await page.locator(`#space-${axis}`).fill('');
  let releaseResponse, signalFetched;
  const held = new Promise(resolve => { releaseResponse = resolve; });
  const fetched = new Promise(resolve => { signalFetched = resolve; });
  const delayedRoute = async route => {
    const actual = await route.fetch();
    expect((await actual.json()).matches).toHaveLength(6);
    signalFetched();
    await held;
    await route.fulfill({ response: actual });
  };
  await page.route('**/api/discovery', delayedRoute, { times: 1 });
  const oldResponse = page.waitForResponse(response => response.url().endsWith('/api/discovery'));
  await page.locator('#discovery-submit').click();
  await fetched;
  await expect(page.locator('#space-height')).toBeEnabled();
  await page.locator('#space-height').fill('7');
  releaseResponse();
  await (await oldResponse).finished();
  await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));
  await expect(page.locator('#discovery-cards [data-project-id]')).toHaveCount(1);
  await expect(page.locator('#discovery-cards [data-project-id="three-cable-rest"]')).toBeVisible();
  await expect(page.locator('#discovery-summary')).toContainText('이전');
  await expect(page.locator('#discovery-apply')).toBeDisabled();
  expect((await findProjects(page)).status()).toBe(200);
  await expect(page.locator('#discovery-cards [data-project-id="round-insert-frame"]')).toBeVisible();

  // Explicit synthetic transport failure exercises recovery; model/CAD data stay real.
  page.__expectedHttpFailures.push({ path: '/api/discovery', status: 503 });
  await page.route('**/api/discovery', route => route.fulfill({
    status: 503, contentType: 'application/json',
    body: JSON.stringify({ detail: '브라우저 테스트용 일시 오류' }),
  }), { times: 1 });
  await page.locator('#space-height').fill('8');
  expect((await findProjects(page)).status()).toBe(503);
  await expect(page.locator('#discovery-feedback')).toContainText('일시 오류');
  await expect(width).toHaveValue('133');
  await expect(page.locator('#request-text')).toHaveValue(requestText);
  await expect(page.locator('#discovery-cards [data-project-id="round-insert-frame"]')).toBeVisible();
  await expect(page.locator('#discovery-apply')).toBeDisabled();
  expect((await findProjects(page)).status()).toBe(200);
  await page.locator('#discovery-cards [data-project-id="round-insert-frame"]').click();
  await page.locator('#discovery-apply').click();
  await expect(page.locator('#discovery-replace-confirm')).toBeVisible();
  await noHorizontalOverflow(page);
  await page.locator('#discovery-detail').screenshot({ path: testInfo.outputPath('discovery-replacement.png'), scale: 'css' });
  await page.locator('#discovery-confirm-apply').click();
  await expect(page.locator('#parameter-width')).toHaveValue('65');
  await expect(page.locator('#parameter-inset_diameter')).toHaveValue('52');
  await expect(page.locator('#draft-source')).toContainText('원형 사진 인셋 프레임');

  await page.locator('#request-text').fill('가로 90mm 세로 60mm 높이 18mm 수납함');
  await page.locator('#plan-button').click();
  await expect(page.locator('#parameter-width')).toHaveValue('90');
  await expect(page.locator('#draft-source')).toBeHidden();
  await expect(page.locator('#model-result')).toBeHidden();
  await noHorizontalOverflow(page);
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
  await expect(page.locator('#model-replace-confirm')).toBeVisible();
  await page.locator('#model-confirm-replace').click();
  await expect(page.locator('#model-result')).toBeVisible();
  await expect(page.locator('#outcome-notes')).toHaveValue(notes);
  await expect(page.locator('#generate-button')).toBeEnabled();

  await page.locator('.template-card[data-template="cable_comb"]').click();
  await expect(page.locator('#model-replace-confirm')).toBeVisible();
  await page.locator('#model-confirm-replace').click();
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

test('purchase comparisons retain form locking and protect drafts through edits and explicit retry', async ({ page }, testInfo) => {
  await openView(page, 'offers');
  const exitProtected = () => page.evaluate(() => {
    const event = new Event('beforeunload', { cancelable: true });
    window.dispatchEvent(event);
    return event.defaultPrevented;
  });
  expect(await exitProtected()).toBe(false);
  for (const [field, value] of Object.entries({ name: '조건 변경 검증용 상품', price: '1000', grams: '1000', shipping: '' })) {
    await page.locator(`#offer-1-${field}`).fill(value);
  }
  expect(await exitProtected()).toBe(true);
  const requests = [];
  const recordRequest = request => {
    if (request.method() === 'POST' && request.url().endsWith('/api/offers/compare')) requests.push(request.postDataJSON());
  };
  page.on('request', recordRequest);
  const compareResponse = () => page.waitForResponse(response => response.url().endsWith('/api/offers/compare'));
  async function holdComparison(syntheticFailure = false) {
    let release, fetched;
    const held = new Promise(resolve => { release = resolve; });
    const arrived = new Promise(resolve => { fetched = resolve; });
    await page.route('**/api/offers/compare', async route => {
      const actual = await route.fetch();
      expect(actual.status()).toBe(200);
      fetched();
      await held;
      if (syntheticFailure) await route.fulfill({ status: 503, contentType: 'application/json',
        body: JSON.stringify({ detail: '브라우저 검사 전용 현재 비교 실패' }) });
      else await route.fulfill({ response: actual });
    }, { times: 1 });
    return { arrived, release };
  }

  // Hold a real response and verify normal users cannot edit pending inputs.
  // Defensive programmatic mutation cases belong to the controller tests.
  const first = await holdComparison();
  const oldResponse = compareResponse();
  await page.locator('#compare-offers').click();
  await first.arrived;
  await expect(page.locator('#offer-1-price')).toBeDisabled();
  await expect(page.locator('#offer-currency')).toBeDisabled();
  await expect(page.locator('#compare-offers')).toBeDisabled();
  expect(await exitProtected()).toBe(true);
  first.release();
  const oldBytes = await (await oldResponse).body();
  const old = JSON.parse(oldBytes);
  expect(old.groups.KRW[0].shipping).toBeNull();
  await expect(page.locator('#compare-offers')).toBeEnabled();
  await expect(page.locator('#offers-result')).toBeVisible();
  await expect(page.locator('#offers-feedback')).toBeHidden();
  await expect(page.locator('#offer-comparison')).toContainText('배송비 미확인');
  await expect(page.locator('#offer-currency')).toHaveValue('KRW');
  await expect(page.locator('#offer-1-price')).toHaveValue('1000');
  expect(requests).toHaveLength(1);
  await page.locator('#offer-1-price').fill('1000.0');
  await expect(page.locator('#offers-result')).toBeHidden();
  await expect(page.locator('#offer-1-price')).toHaveValue('1000.0');
  await noHorizontalOverflow(page);
  await page.locator('#view-offers').screenshot({ path: testInfo.outputPath('purchase-comparison-edit.png'), scale: 'css' });

  await page.locator('#offer-currency').selectOption('USD');
  await page.locator('#offer-1-shipping').fill('0');
  const freshResponse = compareResponse();
  await page.locator('#compare-offers').click();
  const freshBytes = await (await freshResponse).body();
  const fresh = JSON.parse(freshBytes);
  expect(fresh.groups.USD[0].shipping).toBe(0);
  expect(fresh.groups.USD[0].price_per_kg).toBe(1000);
  await expect(page.locator('#offers-result')).toBeVisible();
  await expect(page.locator('#offer-1-price')).toHaveValue('1000.0');
  await expect(page.locator('#offer-comparison')).toContainText('1,000.00');
  expect(await exitProtected()).toBe(true); // Calculating does not save the draft.

  // A delayed real request receives an explicitly synthetic current error.
  page.__expectedHttpFailures.push({ path: '/api/offers/compare', status: 503 });
  const failing = await holdComparison(true);
  const failedResponse = compareResponse();
  await page.locator('#compare-offers').click();
  await failing.arrived;
  await expect(page.locator('#offer-currency')).toBeDisabled();
  failing.release();
  expect((await failedResponse).status()).toBe(503);
  await expect(page.locator('#compare-offers')).toBeEnabled();
  await expect(page.locator('#offers-result')).toBeHidden();
  await expect(page.locator('#offers-feedback')).toContainText('현재 비교 실패');
  await expect(page.locator('#connection-status')).toContainText('연결됨');
  await expect(page.locator('#offer-currency')).toHaveValue('USD');
  await expect(page.locator('#offer-1-price')).toHaveValue('1000.0');
  expect(requests).toHaveLength(3);

  await page.locator('#offer-currency').selectOption('JPY');
  await page.locator('#offer-1-price').fill('2000');
  await page.locator('#offer-1-shipping').fill('');
  const retryResponse = compareResponse();
  await page.locator('#compare-offers').click();
  const retryBytes = await (await retryResponse).body();
  const retry = JSON.parse(retryBytes);
  expect(retry.groups.JPY[0].price).toBe(2000);
  expect(retry.groups.JPY[0].shipping).toBeNull();
  expect(retry.groups.JPY[0].price_per_kg).toBeNull();
  expect(retry.live_prices).toBe(false);
  await expect(page.locator('#offers-result')).toBeVisible();
  await expect(page.locator('#offer-comparison')).toContainText('배송비 미확인');
  await expect(page.locator('#offers-feedback')).toBeHidden();
  expect(requests).toHaveLength(4);
  expect(requests.map(payload => payload.offers[0].currency)).toEqual(['KRW', 'USD', 'USD', 'JPY']);
  await noHorizontalOverflow(page);
  await page.locator('#view-offers').screenshot({ path: testInfo.outputPath('purchase-comparison-retry.png'), scale: 'css' });
  await fs.writeFile(testInfo.outputPath('purchase-comparison-original.json'), oldBytes);
  await fs.writeFile(testInfo.outputPath('purchase-comparison-current.json'), freshBytes);
  await fs.writeFile(testInfo.outputPath('purchase-comparison-retry.json'), retryBytes);
  await fs.writeFile(testInfo.outputPath('purchase-comparison-recovery.json'), JSON.stringify({
    requests, synthetic_http_503: true, automatic_replays: 0,
    purchase_inputs_locked_while_comparison_pending: true,
    exact_numeric_spelling_preserved: true,
    unfinished_inputs_protected_on_exit: true, comparisons_saved: false,
  }, null, 2));
  page.off('request', recordRequest);
  await expect(page.locator('#compare-offers')).toBeEnabled();
  for (let index = 1; index <= 3; index++) {
    for (const field of ['name', 'price', 'grams', 'shipping']) await page.locator(`#offer-${index}-${field}`).fill('');
  }
  await page.locator('#offer-currency').selectOption('KRW');
  expect(await exitProtected()).toBe(false);
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
  await expect(page.locator('#profile-resolution')).toBeVisible();
  await expect(page.locator('#profile-download')).toHaveAttribute('href', /^blob:/);
  await noHorizontalOverflow(page);
  await page.screenshot({ path: testInfo.outputPath('filament-import-error.png'), fullPage: true });
});

test('Studio filament archives recover missing parents and retain exact origin through saved workspaces', async ({ page }, testInfo) => {
  const { base, child, setup } = inheritedPresetFixture();
  const original = { ...child.settings, from: 'User', filament_settings_id: [child.settings.name] };
  delete original.type; // Native exports can identify filament settings without type.
  const text = ` ${JSON.stringify(original, null, 2)}\n`;
  const path = 'Example/Child.json';
  const upload = filamentArchive('synthetic-material.bbsflmt', [{ path, text }]);
  await openView(page, 'profiles');
  const importedResponse = page.waitForResponse(response => response.url().endsWith('/api/profiles/import-archive'));
  await page.locator('#profile-archive').setInputFiles(upload);
  const imported = await (await importedResponse).json();
  expect(imported.documents).toHaveLength(1);
  expect(imported.documents[0].profile).toEqual(original);
  expect(imported.documents[0].draft_text).toBe(text);
  const origin = imported.documents[0].origin;
  expect(origin).toEqual({
    type: 'bambu_preset_archive', archive_name: upload.name,
    archive_sha256: crypto.createHash('sha256').update(upload.buffer).digest('hex'),
    member_path: path, member_sha256: crypto.createHash('sha256').update(text).digest('hex'),
  });
  await expect(page.locator('#profile-target option')).toHaveCount(1);
  await expect(page.locator('#profile-json')).toHaveValue(text);
  await page.locator('#profile-origin summary').click();
  await expect(page.locator('#profile-origin-fields')).toContainText(upload.name);
  await expect(page.locator('#profile-origin-fields')).toContainText(origin.archive_sha256);
  const missingResponse = page.waitForResponse(response => response.url().endsWith('/api/profiles/resolve'));
  await page.locator('#review-profile').click();
  const missing = await (await missingResponse).json();
  expect(missing.status).toBe('needs_input');
  expect(missing.documents[0].origin).toEqual(origin);
  await expect(page.locator('#profile-resolution-issues')).toContainText('Synthetic Base');
  await expect(page.locator('#review-profile')).toBeEnabled();

  await page.locator('#profile-file').setInputFiles(presetUpload('base.json', base));
  await expect(page.locator('#profile-target option')).toHaveCount(2);
  await expect(page.locator('#profile-target')).toHaveValue('0');
  await expect(page.locator('#profile-json')).toHaveValue(text);
  for (const [name, value] of Object.entries(setup)) {
    const field = page.locator(`.setup-grid [name="${name}"]`);
    if (name === 'material_identity_status') await field.selectOption(value);
    else await field.fill(String(value));
  }
  await page.locator('#guided-nozzle_temperature').fill('220');
  await page.locator('#profile-guided-apply').click();
  const editedText = await page.locator('#profile-json').inputValue();
  expect(JSON.parse(editedText)).toEqual({ ...original, nozzle_temperature: ['220'] });
  const title = `Archive ${testInfo.project.name} ${Date.now()}`;
  await page.locator('#workspace-title').fill(title);
  const savedResponse = page.waitForResponse(response => response.url().endsWith('/api/profile-workspaces') && response.request().method() === 'POST');
  await page.locator('#workspace-save').click();
  const saved = await (await savedResponse).json();
  expect(saved.snapshot.documents[0].origin).toEqual(origin);
  expect(saved.snapshot.documents[0].profile).toEqual(original);
  expect(saved.snapshot.documents[0].draft_text).toBe(editedText);
  expect(saved.snapshot.documents[1]).not.toHaveProperty('origin');
  await expect(page.locator('#workspace-status')).toHaveText('저장됨');
  await page.reload();
  await expect(page.locator('#generate-button')).toBeEnabled();
  await openView(page, 'profiles');
  await expect(page.locator(`#workspace-list option[value="${saved.id}"]`)).toHaveCount(1);
  await page.locator('#workspace-list').selectOption(saved.id);
  await page.locator('#workspace-open').click();
  await expect(page.locator('#workspace-title')).toHaveValue(title);
  await expect(page.locator('#profile-json')).toHaveValue(editedText);
  await expect(page.locator('#profile-resolution')).toBeHidden();
  await expect(page.locator('#profile-download')).not.toHaveAttribute('href');
  await page.locator('#profile-origin summary').click();
  await expect(page.locator('#profile-origin-fields')).toContainText(origin.member_sha256);
  const resolvedResponse = page.waitForResponse(response => response.url().endsWith('/api/profiles/resolve'));
  await page.locator('#review-profile').click();
  const resolved = await (await resolvedResponse).json();
  expect(resolved.status).toBe('resolved');
  expect(resolved.full_config).toBe(false);
  expect(resolved.native_verified).toBe(false);
  expect(resolved.documents[0].origin).toEqual(origin);
  expect(resolved.imported_documents[0].origin).toEqual(origin);
  expect(resolved.imported_documents[0].profile).toEqual(original);
  expect(resolved.resolved_profile.settings.nozzle_temperature).toEqual(['220']);
  const downloadPromise = page.waitForEvent('download');
  await page.locator('#profile-download').click();
  const download = await downloadPromise;
  const reportPath = testInfo.outputPath('archive-workspace-review.json');
  await download.saveAs(reportPath);
  const report = JSON.parse(await fs.readFile(reportPath, 'utf8'));
  expect(report.documents[0].origin).toEqual(origin);
  expect(report.imported_documents[0].profile).toEqual(original);
  await expect(page.locator('#slicer-json')).toHaveValue('');
  await noHorizontalOverflow(page);
  await page.screenshot({ path: testInfo.outputPath('archive-workspace.png'), fullPage: true });
});

test('mixed Studio bundles adopt pasted inputs and repeated imports preserve edited drafts and reports', async ({ page }, testInfo) => {
  const { child } = inheritedPresetFixture();
  const profile = { ...child.settings, from: 'User', filament_settings_id: [child.settings.name] };
  const text = JSON.stringify(profile, null, 2);
  const upload = printerArchive('synthetic-printer.bbscfg', { path: 'filament/Child.json', text });
  await openView(page, 'profiles');
  const pasted = ' {"name":"Pasted local draft"}\n';
  await page.locator('#profile-json').fill(pasted);
  const response = page.waitForResponse(result => result.url().endsWith('/api/profiles/import-archive'));
  await page.locator('#profile-archive').setInputFiles(upload);
  const imported = await (await response).json();
  expect(imported.documents).toHaveLength(1);
  expect(imported.ignored_members.map(member => member.path).sort()).toEqual(['printer/Printer.json', 'process/Process.json']);
  await expect(page.locator('#profile-target option')).toHaveCount(2);
  await expect(page.locator('#profile-target')).toHaveValue('0');
  await expect(page.locator('#profile-json')).toHaveValue(pasted);
  await expect(page.locator('#profile-feedback')).toContainText('2개 항목');
  await expect(page.locator('#profile-feedback')).toContainText('printer/Printer.json');
  await page.locator('#profile-target').selectOption('1');
  const edited = JSON.stringify({ ...profile, nozzle_temperature: ['223'] });
  await page.locator('#profile-json').fill(edited);
  const reviewResponse = page.waitForResponse(result => result.url().endsWith('/api/profiles/resolve'));
  await page.locator('#review-profile').click();
  expect((await (await reviewResponse).json()).status).toBe('needs_input');
  await expect(page.locator('#review-profile')).toBeEnabled();
  const reportUrl = await page.locator('#profile-download').getAttribute('href');
  await page.locator('#profile-archive').setInputFiles(upload);
  await expect(page.locator('#profile-feedback')).toContainText('건너뛰었습니다');
  await expect(page.locator('#profile-target option')).toHaveCount(2);
  await expect(page.locator('#profile-target')).toHaveValue('1');
  await expect(page.locator('#profile-json')).toHaveValue(edited);
  await expect(page.locator('#profile-resolution')).toBeVisible();
  await expect(page.locator('#profile-download')).toHaveAttribute('href', reportUrl);
  await page.locator('#profile-origin summary').click();
  await expect(page.locator('#profile-origin-fields')).toContainText(upload.name);
  await expect(page.locator('#slicer-json')).toHaveValue('');
  await noHorizontalOverflow(page);
  await page.screenshot({ path: testInfo.outputPath('mixed-archive.png'), fullPage: true });
});

test('invalid and conflicting archives roll back the whole import while preserving a current review', async ({ page }, testInfo) => {
  const { base, child } = inheritedPresetFixture();
  await openView(page, 'profiles');
  await page.locator('#profile-file').setInputFiles([presetUpload('child.json', child), presetUpload('base.json', base)]);
  await expect(page.locator('#profile-target option')).toHaveCount(2);
  const reviewResponse = page.waitForResponse(result => result.url().endsWith('/api/profiles/resolve'));
  await page.locator('#review-profile').click();
  expect((await (await reviewResponse).json()).status).toBe('resolved');
  await expect(page.locator('#review-profile')).toBeEnabled();
  const previous = await page.locator('#profile-json').inputValue();
  const reportUrl = await page.locator('#profile-download').getAttribute('href');
  const good = { path: 'Example/Other.json', text: JSON.stringify({ name: 'Another filament', type: 'filament', filament_settings_id: ['Another filament'] }) };
  const malformed = filamentArchive('invalid-material.bbsflmt', [good, { path: 'Example/Bad.json', text: '[]' }]);
  page.__expectedHttpFailures.push({ path: '/api/profiles/import-archive', status: 422 });
  const rejected = page.waitForResponse(result => result.url().endsWith('/api/profiles/import-archive'));
  await page.locator('#profile-archive').setInputFiles(malformed);
  expect((await rejected).status()).toBe(422);
  await expect(page.locator('#profile-feedback')).toContainText('유지했습니다');
  await expect(page.locator('#profile-target option')).toHaveCount(2);
  await expect(page.locator('#profile-target')).toHaveValue('0');
  await expect(page.locator('#profile-json')).toHaveValue(previous);
  await expect(page.locator('#profile-resolution')).toBeVisible();
  await expect(page.locator('#profile-download')).toHaveAttribute('href', reportUrl);

  const conflict = { ...child.settings, filament_settings_id: [child.settings.name], nozzle_temperature: ['230'] };
  const conflicting = filamentArchive('conflicting-material.bbsflmt', [good, { path: 'Example/Child.json', text: JSON.stringify(conflict) }]);
  await page.locator('#profile-archive').setInputFiles(conflicting);
  await expect(page.locator('#profile-feedback')).toContainText('내용이 다릅니다');
  await expect(page.locator('#profile-target option')).toHaveCount(2);
  await expect(page.locator('#profile-json')).toHaveValue(previous);
  await expect(page.locator('#profile-resolution')).toBeVisible();
  await expect(page.locator('#profile-download')).toHaveAttribute('href', reportUrl);
  await noHorizontalOverflow(page);
  await page.screenshot({ path: testInfo.outputPath('archive-import-recovery.png'), fullPage: true });
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

test('guided source and applicability evidence wraps only the draft and survives archive workspace reload', async ({ page }, testInfo) => {
  const { base, child, setup } = inheritedPresetFixture();
  const original = { ...child.settings, from: 'User', filament_settings_id: [child.settings.name] };
  delete original.type;
  const originalText = ` ${JSON.stringify(original, null, 2)}\n`;
  const upload = filamentArchive('evidence-fixture.bbsflmt', [{ path: 'Example/Evidence.json', text: originalText }]);
  const parent = { settings: base, scope: child.scope, source: { authority: 'manufacturer', publisher: 'Parent only; never child evidence' } };
  const source = {
    authority: 'manufacturer', publisher: '<img src=x onerror="window.evidenceExecuted=true"> Synthetic publisher',
    url: `https://example.invalid/filament/${'exact-product-'.repeat(12)}source`, retrieved_at: '2026-11-13T09:15:00+09:00',
  };
  const ownedSetup = { ...setup, material_id: 'fixture:owned-different-product' };
  await openView(page, 'profiles');
  const importedResponse = page.waitForResponse(response => response.url().endsWith('/api/profiles/import-archive'));
  await page.locator('#profile-archive').setInputFiles(upload);
  const imported = await (await importedResponse).json();
  const origin = imported.documents[0].origin;
  expect(origin.archive_sha256).toBe(crypto.createHash('sha256').update(upload.buffer).digest('hex'));
  expect(origin.member_sha256).toBe(crypto.createHash('sha256').update(originalText).digest('hex'));
  await expect(page.locator('#profile-target option')).toHaveCount(1);
  await page.locator('#profile-file').setInputFiles(presetUpload('parent-with-evidence.json', parent));
  await expect(page.locator('#profile-target option')).toHaveCount(2);
  for (const [name, value] of Object.entries(ownedSetup)) {
    const field = page.locator(`.setup-grid [name="${name}"]`);
    if (name === 'material_identity_status') await field.selectOption(value);
    else await field.fill(String(value));
  }
  await openProfileEvidence(page, testInfo);
  await expect(page.locator('#profile-json')).toHaveValue(originalText);
  for (const [name, value] of Object.entries(child.scope)) {
    const field = page.locator(`#evidence-scope-${name}`);
    await expect(field).toHaveValue(''); // Neither the parent nor current setup supplies evidence automatically.
    await field.fill(String(value));
  }
  for (const [name, value] of Object.entries(source)) {
    const field = page.locator(`#evidence-source-${name}`);
    await expect(field).toHaveValue('');
    await field.fill(value);
  }
  await expect(page.locator('#profile-json')).toBeDisabled();
  await expect(page.locator('#profile-target')).toBeDisabled();
  await expect(page.locator('#profile-archive')).toBeDisabled();
  await expect(page.locator('#setup-material')).toHaveValue(ownedSetup.material_id);
  await expect(page.locator('#workspace-status')).toHaveText('편집값 적용 필요');
  await expect(page.locator('#profile-json')).toHaveValue(originalText);

  const title = `Evidence ${testInfo.project.name} ${Date.now()}`;
  await page.locator('#workspace-title').fill(title);
  const saveResponse = page.waitForResponse(response => response.url().endsWith('/api/profile-workspaces') && response.request().method() === 'POST');
  await page.locator('#workspace-save').click(); // Save applies all pending evidence as one draft edit.
  const saved = await (await saveResponse).json();
  const edited = { settings: original, scope: child.scope, source };
  expect(saved.snapshot.documents[0].profile).toEqual(original);
  expect(JSON.parse(saved.snapshot.documents[0].draft_text)).toEqual(edited);
  expect(saved.snapshot.documents[0].origin).toEqual(origin);
  expect(saved.snapshot.documents[1].profile).toEqual(parent);
  expect(saved.snapshot.setup).toEqual(Object.fromEntries(Object.entries(ownedSetup).map(([key, value]) => [key, String(value)])));
  await expect(page.locator('#workspace-status')).toHaveText('저장됨');
  await page.reload();
  await expect(page.locator('#generate-button')).toBeEnabled();
  await openView(page, 'profiles');
  await expect(page.locator(`#workspace-list option[value="${saved.id}"]`)).toHaveCount(1);
  await page.locator('#workspace-list').selectOption(saved.id);
  await page.locator('#workspace-open').click();
  await expect(page.locator('#workspace-title')).toHaveValue(title);
  await expect(page.locator('#profile-resolution')).toBeHidden();
  await expect(page.locator('#profile-download')).not.toHaveAttribute('href');
  expect(JSON.parse(await page.locator('#profile-json').inputValue())).toEqual(edited);
  await expect(page.locator('#setup-material')).toHaveValue(ownedSetup.material_id);
  await openProfileEvidence(page, testInfo);
  await expect(page.locator('#evidence-scope-material_id')).toHaveValue(setup.material_id);
  await expect(page.locator('#evidence-source-publisher')).toHaveValue(source.publisher);
  await expect(page.locator('#evidence-source-retrieved_at')).toHaveValue(source.retrieved_at);
  const mismatchResponse = page.waitForResponse(response => response.url().endsWith('/api/profiles/resolve'));
  await page.locator('#review-profile').click();
  const mismatch = await (await mismatchResponse).json();
  expect(mismatch.review.decision).toBe('blocked');
  expect(mismatch.review.reasons.some(item => item.code === 'PROFILE_SCOPE_MISMATCH')).toBe(true);
  expect(mismatch.review.validation_status).toBe('unverified');
  expect(mismatch.edit_review.status).toBe('unchanged');
  expect(mismatch.edit_review.evidence_status).toBe('compared');
  expect(mismatch.edit_review.evidence_changes).toHaveLength(11);
  expect(mismatch.edit_review.evidence_changes.every(item => !item.before_present && item.after_present)).toBe(true);
  await expect(page.locator('#review-profile')).toBeEnabled();
  await page.locator('#setup-material').fill(setup.material_id);
  await expect(page.locator('#profile-download')).not.toHaveAttribute('href');
  const updatedResponse = page.waitForResponse(response => response.url().endsWith(`/api/profile-workspaces/${saved.id}`) && response.request().method() === 'PUT');
  await page.locator('#workspace-save').click();
  expect((await (await updatedResponse).json()).revision).toBe(2);
  await expect(page.locator('#workspace-status')).toHaveText('저장됨');
  const reviewedResponse = page.waitForResponse(response => response.url().endsWith('/api/profiles/resolve'));
  await page.locator('#review-profile').click();
  const reviewed = await (await reviewedResponse).json();
  expect(reviewed.review.decision).toBe('ready_to_prepare');
  expect(reviewed.review.validation_status).toBe('unverified');
  expect(reviewed.review.warnings.some(item => item.startsWith('SOURCE_CLAIM_ONLY:'))).toBe(true);
  expect(reviewed.edit_review.changed_fields).toEqual([]);
  expect(reviewed.edit_review.validation_invalidated).toBe(false);
  expect(reviewed.documents[0].profile).toEqual(edited);
  expect(reviewed.imported_documents[0].profile).toEqual(original);
  expect(reviewed.documents[1].profile).toEqual(parent);
  expect(reviewed.documents[0].origin).toEqual(origin);
  expect(reviewed.imported_documents[0].origin).toEqual(origin);
  expect(reviewed.setup).toEqual(setup);
  expect(reviewed.full_config).toBe(false);
  expect(reviewed.native_verified).toBe(false);
  await expect(page.locator('#profile-evidence-changes tr[data-evidence-path]')).toHaveCount(11);
  await expect(page.locator('#profile-evidence-review')).toContainText(JSON.stringify(source.publisher));
  await expect(page.locator('#profile-evidence-review img')).toHaveCount(0);
  expect(await page.evaluate(() => window.evidenceExecuted)).toBeUndefined();
  const downloadPromise = page.waitForEvent('download');
  await page.locator('#profile-download').click();
  const download = await downloadPromise;
  const reportPath = testInfo.outputPath('filament-evidence-review.json');
  await download.saveAs(reportPath);
  expect(JSON.parse(await fs.readFile(reportPath, 'utf8')).edit_review).toEqual(reviewed.edit_review);
  await noHorizontalOverflow(page);
  await page.locator('#profile-evidence').scrollIntoViewIfNeeded();
  await page.screenshot({ path: testInfo.outputPath('filament-evidence-editor.png'), fullPage: true });
});

test('evidence edits cancel atomically and keep source corrections distinct from changed validation scope', async ({ page }, testInfo) => {
  const { base, child, setup } = inheritedPresetFixture();
  child.scope.nozzle_diameter = ['0.40'];
  child.scope.extra_scope_note = ['preserve unknown evidence'];
  child.source = { authority: 'custom authority', publisher: { legacy: 'do not coerce' }, url: 'original source text', retrieved_at: 'original time text' };
  child.validation = { status: 'measured_on_matching_setup', setup_fingerprint: structuredClone(child.scope), note: 'Supplied synthetic claim' };
  child.extra_envelope_note = { preserved: true };
  await openView(page, 'profiles');
  await page.locator('#profile-file').setInputFiles([presetUpload('base.json', base), presetUpload('child.json', child)]);
  await expect(page.locator('#profile-target option')).toHaveCount(2);
  await page.locator('#profile-target').selectOption('1');
  for (const [name, value] of Object.entries(setup)) {
    const field = page.locator(`.setup-grid [name="${name}"]`);
    if (name === 'material_identity_status') await field.selectOption(value);
    else await field.fill(String(value));
  }
  await openProfileEvidence(page, testInfo);
  await expect(page.locator('#evidence-source-authority')).toHaveValue('custom authority');
  await expect(page.locator('#evidence-source-publisher')).toBeDisabled();
  await expect(page.locator('#profile-evidence-source')).toContainText('do not coerce');
  await expect(page.locator('#evidence-scope-nozzle_diameter')).toHaveValue('0.40');
  await page.locator('#guided-nozzle_temperature').fill('220');
  await page.locator('#evidence-scope-nozzle_diameter').fill('');
  await page.locator('#evidence-scope-nozzle_diameter').pressSequentially('-');
  expect(await page.locator('#evidence-scope-nozzle_diameter').evaluate(input => input.validity.badInput)).toBe(true);
  await page.locator('#profile-guided-apply').click();
  await expect(page.locator('#profile-guided-feedback')).toBeVisible();
  await expect(page.locator('#workspace-status')).toHaveText('편집값 적용 필요');
  expect(JSON.parse(await page.locator('#profile-json').inputValue())).toEqual(child);
  await expect(page.locator('#guided-nozzle_temperature')).toHaveValue('220');
  await page.locator('#evidence-scope-nozzle_diameter').fill('-0.4');
  await page.locator('#profile-guided-apply').click();
  await expect(page.locator('#profile-guided-feedback')).toBeVisible();
  await expect(page.locator('#workspace-status')).toHaveText('편집값 적용 필요');
  expect(JSON.parse(await page.locator('#profile-json').inputValue())).toEqual(child);
  await expect(page.locator('#guided-nozzle_temperature')).toHaveValue('220');
  await expect(page.locator('#evidence-scope-nozzle_diameter')).toHaveValue('-0.4');
  await page.locator('#profile-guided-cancel').click();
  await expect(page.locator('#profile-json')).toBeEnabled();
  await expect(page.locator('#profile-evidence')).toHaveJSProperty('open', true);
  await expect(page.locator('#evidence-scope-nozzle_diameter')).toBeVisible();
  await expect(page.locator('#guided-nozzle_temperature')).toHaveValue('215');
  await expect(page.locator('#evidence-scope-nozzle_diameter')).toHaveValue('0.40');
  expect(JSON.parse(await page.locator('#profile-json').inputValue())).toEqual(child);

  const correctedUrl = 'https://example.invalid/corrected-evidence';
  await page.locator('#evidence-source-url').fill(correctedUrl);
  const sourceResponse = page.waitForResponse(response => response.url().endsWith('/api/profiles/resolve'));
  await page.locator('#review-profile').click(); // Review also applies pending evidence.
  const sourceReport = await (await sourceResponse).json();
  expect(sourceReport.edit_review.status).toBe('unchanged');
  expect(sourceReport.edit_review.evidence_changes).toEqual([{
    path: 'source.url', before_present: true, after_present: true, before: child.source.url, after: correctedUrl,
  }]);
  expect(sourceReport.edit_review.validation_invalidated).toBe(false);
  expect(sourceReport.review.validation_status).toBe('reported_validated');
  expect(sourceReport.documents[1].profile.source.publisher).toEqual(child.source.publisher);
  expect(sourceReport.documents[1].profile.extra_envelope_note).toEqual(child.extra_envelope_note);
  await expect(page.locator('#profile-evidence-changes tr[data-evidence-path="source.url"]')).toContainText(child.source.url);
  await expect(page.locator('#profile-evidence-changes tr[data-evidence-path="source.url"]')).toContainText(correctedUrl);
  await expect(page.locator('#review-profile')).toBeEnabled();

  await page.locator('#evidence-scope-material_id').fill('fixture:a-different-product');
  await page.locator('#evidence-source-url').fill(''); // Empty means explicit removal of this source key only.
  await expect(page.locator('#profile-download')).not.toHaveAttribute('href');
  const scopeResponse = page.waitForResponse(response => response.url().endsWith('/api/profiles/resolve'));
  await page.locator('#review-profile').click();
  const scoped = await (await scopeResponse).json();
  expect(scoped.edit_review.status).toBe('unchanged');
  expect(scoped.edit_review.changed_fields).toEqual([]);
  expect(scoped.edit_review.validation_invalidated).toBe(true);
  expect(scoped.review.validation_status).toBe('stale');
  expect(scoped.review.decision).toBe('blocked');
  expect(scoped.review.reasons.some(item => item.code === 'VALIDATION_EVIDENCE_CHANGED')).toBe(true);
  expect(scoped.edit_review.evidence_changes.find(item => item.path === 'source.url')).toEqual({
    path: 'source.url', before_present: true, after_present: false, before: child.source.url,
  });
  expect(scoped.imported_documents[1].profile).toEqual(child);
  expect(scoped.documents[1].profile.settings).toEqual(child.settings);
  expect(scoped.documents[1].profile.scope.nozzle_diameter).toEqual(['0.40']);
  expect(scoped.documents[1].profile.scope.extra_scope_note).toEqual(child.scope.extra_scope_note);
  expect(scoped.documents[1].profile.source.publisher).toEqual(child.source.publisher);
  expect(scoped.documents[1].profile.source.retrieved_at).toBe(child.source.retrieved_at);
  expect(scoped.documents[1].profile.source).not.toHaveProperty('url');
  expect(scoped.documents[1].profile.validation).toEqual(child.validation);
  expect(scoped.full_config).toBe(false);
  expect(scoped.native_verified).toBe(false);
  const downloadPromise = page.waitForEvent('download');
  await page.locator('#profile-download').click();
  await (await downloadPromise).saveAs(testInfo.outputPath('filament-evidence-stale-review.json'));
  await noHorizontalOverflow(page);
  await page.locator('#profile-evidence').scrollIntoViewIfNeeded();
  await page.screenshot({ path: testInfo.outputPath('filament-evidence-stale.png'), fullPage: true });
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
