const fs = require('node:fs');
const path = require('node:path');
const { defineConfig, devices } = require('@playwright/test');

const root = __dirname;
const output = path.join(root, 'qa-output', 'playwright');

// Every run starts from an empty app data folder, as CI does. The config is loaded again in
// each worker; the variable set by the first (main) load stops a worker from clearing the
// folder while the server is already using it.
const data = path.join(output, 'data');
if (!process.env.PPA_BROWSER_DATA_READY) {
  fs.rmSync(data, { recursive: true, force: true });
  process.env.PPA_BROWSER_DATA_READY = '1';
}

module.exports = defineConfig({
  testDir: './tests/browser',
  outputDir: path.join(output, 'results'),
  fullyParallel: false,
  workers: 1,
  forbidOnly: Boolean(process.env.CI),
  retries: 0,
  timeout: 60_000,
  expect: { timeout: 10_000 },
  reporter: [
    ['list'],
    ['html', { outputFolder: path.join(output, 'report'), open: 'never' }],
    ['json', { outputFile: path.join(output, 'results.json') }],
  ],
  use: {
    baseURL: 'http://127.0.0.1:8765',
    locale: 'ko-KR',
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
    video: 'off',
  },
  projects: [
    { name: 'desktop-chromium', use: { ...devices['Desktop Chrome'], viewport: { width: 1440, height: 1050 } } },
    { name: 'mobile-chromium', use: { ...devices['Pixel 7'], viewport: { width: 390, height: 844 } } },
  ],
  webServer: {
    command: 'python -m print_agent --port 8765',
    cwd: root,
    url: 'http://127.0.0.1:8765/api/bootstrap',
    timeout: 60_000,
    reuseExistingServer: false,
    stdout: 'pipe',
    stderr: 'pipe',
    env: {
      PPA_DATA_DIR: data,
      PPA_LLM_BASE_URL: '',
      PPA_LLM_MODEL: '',
      PPA_LLM_API_KEY: '',
      PPA_BAMBU_PATH: path.join(output, 'no-native-slicer'),
    },
  },
});
