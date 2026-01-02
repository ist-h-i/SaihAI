// @ts-check
import { defineConfig } from '@playwright/test';

/**
 * Evidence strategy:
 * - Always take screenshots (so the PR can be validated visually).
 * - Record video/trace on CI to provide reproducible evidence.
 *
 * For cost/storage control, tune these in your real repo.
 */
export default defineConfig({
  testDir: './tests',
  timeout: 60_000,
  expect: { timeout: 10_000 },
  retries: process.env.CI ? 1 : 0,
  reporter: [['html', { open: 'never' }], ['line']],
  use: {
    headless: true,
    screenshot: 'on',
    video: process.env.CI ? 'on' : 'retain-on-failure',
    trace: process.env.CI ? 'on' : 'retain-on-failure'
  },
  outputDir: 'test-results',
  projects: [
    { name: 'chromium', use: { browserName: 'chromium' } }
  ]
});
