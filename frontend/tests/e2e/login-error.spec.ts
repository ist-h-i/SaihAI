import { Page, test, expect } from '@playwright/test';

const mockConfig = {
  apiBaseUrl: 'http://127.0.0.1:4200/mock-api',
  authToken: '',
};

const routeConfig = async (page: Page, overrides: Record<string, unknown> = {}) => {
  await page.route('**/assets/runtime-config.json', (route) =>
    route.fulfill({ json: { ...mockConfig, ...overrides } })
  );
};

test('login failure shows inline warning and re-enables form', async ({ page }) => {
  await routeConfig(page);
  await page.route('**/mock-api/auth/login', (route) =>
    route.fulfill({ status: 401, json: { detail: 'invalid credentials' } })
  );

  await page.goto('/login');
  await page.getByPlaceholder('例: U001').fill('wrong');
  await page.getByPlaceholder('dev password').fill('wrong');
  await page.getByRole('button', { name: 'ログイン' }).click();

  await expect(
    page.getByText('ログインに失敗しました。入力内容を確認してください。')
  ).toBeVisible();
  await expect(page.getByRole('button', { name: 'ログイン' })).toBeEnabled();
});

test('login timeout shows timeout warning and re-enables form', async ({ page }) => {
  await routeConfig(page, { loginTimeoutMs: 200 });
  await page.route('**/mock-api/auth/login', (route) =>
    route.fulfill({
      status: 200,
      json: { access_token: 'token-123', token_type: 'bearer' },
      delay: 1000,
    })
  );

  await page.goto('/login');
  await page.getByPlaceholder('例: U001').fill('slow');
  await page.getByPlaceholder('dev password').fill('slow');
  await page.getByRole('button', { name: 'ログイン' }).click();

  await expect(
    page.getByText('認証がタイムアウトしました。時間をおいて再度お試しください。')
  ).toBeVisible();
  await expect(page.getByRole('button', { name: 'ログイン' })).toBeEnabled();
  await expect(page).toHaveURL(/login/);
});
