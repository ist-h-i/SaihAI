import { Page, test, expect } from '@playwright/test';

const sampleProjects = [
  {
    id: 'alpha',
    name: 'Alpha',
    budget: 1200,
    requiredSkills: ['TypeScript'],
  },
];

const sampleMembers = [
  {
    id: 'm1',
    name: 'Aki',
    cost: 300,
    availability: 80,
    skills: ['TypeScript'],
    notes: '',
  },
];

const mockConfig = (overrides?: { apiBaseUrl?: string; authToken?: string }) => ({
  apiBaseUrl: 'http://127.0.0.1:4200/mock-api',
  authToken: '',
  ...overrides,
});

const routeConfig = async (page: Page, overrides?: { apiBaseUrl?: string; authToken?: string }) => {
  await page.route('**/assets/runtime-config.json', (route) =>
    route.fulfill({ json: mockConfig(overrides) })
  );
};

const routeProjects = async (
  page: Page,
  handler?: (url: string, headers: Record<string, string>) => void
) => {
  await page.route('**/mock-api/projects', (route) => {
    if (handler) handler(route.request().url(), route.request().headers());
    route.fulfill({ json: sampleProjects });
  });
};

const routeMembers = async (page: Page) => {
  await page.route('**/mock-api/members', (route) => {
    route.fulfill({ json: sampleMembers });
  });
};

test('uses runtime config base url', async ({ page }) => {
  const urls: string[] = [];
  await routeConfig(page);
  await routeProjects(page, (url) => urls.push(url));
  await routeMembers(page);

  await page.goto('/simulator');

  await expect(page.locator('select')).toContainText('Alpha');
  expect(urls.some((url) => url.includes('/mock-api/projects'))).toBeTruthy();
});

test('injects auth header for api requests', async ({ page }) => {
  await routeConfig(page, { authToken: 'token-123' });
  await routeProjects(page, (_url, headers) => {
    expect(headers.authorization).toBe('Bearer token-123');
  });
  await routeMembers(page);

  await page.goto('/simulator');

  await expect(page.locator('select')).toContainText('Alpha');
});

test('shows toast when api returns error', async ({ page }) => {
  await routeConfig(page);
  await page.route('**/mock-api/projects', (route) => {
    route.fulfill({
      status: 500,
      contentType: 'application/json',
      body: JSON.stringify({ detail: 'boom' }),
    });
  });
  await routeMembers(page);

  await page.goto('/simulator');

  await expect(page.getByText('APIエラー')).toBeVisible();
});
