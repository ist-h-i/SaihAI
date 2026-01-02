import { defineConfig } from '@playwright/test';

export default defineConfig({
  testDir: './tests/e2e',
  timeout: 60_000,
  expect: { timeout: 10_000 },
  retries: process.env.CI ? 1 : 0,
  reporter: [['html', { open: 'never' }], ['line']],
  use: {
    baseURL: 'http://127.0.0.1:4200',
    headless: true,
    trace: process.env.CI ? 'on' : 'retain-on-failure'
  },
  webServer: {
    command: 'npm run start',
    url: 'http://127.0.0.1:4200',
    reuseExistingServer: !process.env.CI
  },
  outputDir: 'test-results',
  projects: [{ name: 'chromium', use: { browserName: 'chromium' } }]
});

