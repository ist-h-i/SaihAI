import { test, expect, Page } from '@playwright/test';

const THEME_KEY = 'saihai.theme';

const mockConfig = {
  apiBaseUrl: 'http://127.0.0.1:4200/mock-api',
  authToken: 'token-123',
};

const routeConfig = async (page: Page) => {
  await page.route('**/assets/runtime-config.json', (route) => route.fulfill({ json: mockConfig }));
  await page.route('**/mock-api/dashboard/initial', (route) =>
    route.fulfill({
      json: {
        kpis: [],
        alerts: [],
        members: [],
        proposals: [],
        pendingActions: [],
        watchdog: [],
        checkpointWaiting: false,
      },
    })
  );
  await page.route('**/mock-api/history**', (route) => route.fulfill({ json: [] }));
};

test.describe('theme toggle', () => {
  test('defaults to OS preference when not stored (dark)', async ({ page }) => {
    await routeConfig(page);
    await page.addInitScript((key) => localStorage.removeItem(key), THEME_KEY);
    await page.emulateMedia({ colorScheme: 'dark' });

    await page.goto('/dashboard');
    await expect(page.getByText('経営ダッシュボード')).toBeVisible();
    await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark');
  });

  test('defaults to OS preference when not stored (light)', async ({ page }) => {
    await routeConfig(page);
    await page.addInitScript((key) => localStorage.removeItem(key), THEME_KEY);
    await page.emulateMedia({ colorScheme: 'light' });

    await page.goto('/dashboard');
    await expect(page.getByText('経営ダッシュボード')).toBeVisible();
    await expect(page.locator('html')).toHaveAttribute('data-theme', 'light');
  });

  test('stored theme overrides OS preference', async ({ page }) => {
    await routeConfig(page);
    await page.addInitScript((key) => localStorage.setItem(key, 'dark'), THEME_KEY);
    await page.emulateMedia({ colorScheme: 'light' });

    await page.goto('/dashboard');
    await expect(page.getByText('経営ダッシュボード')).toBeVisible();
    await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark');
  });

  test('toggle updates theme + persists across reload', async ({ page }) => {
    await routeConfig(page);
    await page.addInitScript((key) => localStorage.removeItem(key), THEME_KEY);
    await page.emulateMedia({ colorScheme: 'dark' });

    await page.goto('/dashboard');
    await expect(page.getByText('経営ダッシュボード')).toBeVisible();
    await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark');

    const toggle = page.getByTestId('theme-toggle').first();
    await expect(toggle).toBeVisible();
    await toggle.click();

    await expect(page.locator('html')).toHaveAttribute('data-theme', 'light');
    await expect.poll(() => page.evaluate((key) => localStorage.getItem(key), THEME_KEY)).toBe(
      'light'
    );

    await page.reload();
    await expect(page.locator('html')).toHaveAttribute('data-theme', 'light');
  });
});

