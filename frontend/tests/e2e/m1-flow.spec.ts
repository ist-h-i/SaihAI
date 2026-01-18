import { Page, test, expect } from '@playwright/test';

const mockConfig = {
  apiBaseUrl: 'http://127.0.0.1:4200/mock-api',
  authToken: '',
};

const sampleProjects = [
  {
    id: 'alpha',
    name: 'Alpha',
    budget: 1200,
    requiredSkills: ['TypeScript', 'Angular'],
  },
];

const sampleMembers = [
  {
    id: 'm1',
    name: 'Aki',
    cost: 300,
    availability: 80,
    skills: ['TypeScript', 'Angular'],
    notes: 'High performer',
  },
  {
    id: 'm2',
    name: 'Rin',
    cost: 260,
    availability: 70,
    skills: ['TypeScript'],
    notes: 'Stable contributor',
  },
];

const dashboardPayload = {
  kpis: [
    {
      label: 'エンゲージメント',
      value: 82,
      suffix: '%',
      delta: '▲ 2.4pt',
      color: '#10b981',
      deltaColor: '#10b981',
    },
  ],
  alerts: [],
  members: sampleMembers,
  proposals: [
    {
      id: 1,
      projectId: 'alpha',
      planType: 'Plan_B',
      description: 'Future growth plan',
      recommendationScore: 82,
      isRecommended: true,
    },
  ],
  pendingActions: [
    {
      id: 11,
      proposalId: 1,
      actionType: 'mail_draft',
      title: 'Plan_B draft',
      status: 'pending',
    },
  ],
  watchdog: [{ t: '09:00', text: 'Analysis complete', dot: '#6366f1' }],
  checkpointWaiting: false,
};

const evaluationPayload = {
  id: 'sim-1',
  project: { id: 'alpha', name: 'Alpha', budget: 1200 },
  team: [
    { id: 'm1', name: 'Aki', cost: 300 },
    { id: 'm2', name: 'Rin', cost: 260 },
  ],
  metrics: {
    budgetUsed: 560,
    budgetPct: 47,
    skillFitPct: 80,
    careerFitPct: 70,
    riskPct: 30,
  },
  pattern: 'Unanimous',
  timeline: [
    { t: '1ヶ月後', level: 'good', text: 'Stable' },
    { t: '3ヶ月後', level: 'ok', text: 'On track' },
    { t: '6ヶ月後', level: 'ok', text: 'Healthy' },
  ],
  meetingLog: [
    {
      agent_id: 'PM',
      decision: 'APPROVE',
      risk_score: 10,
      risk_reason: 'OK',
      message: 'Budget ok',
    },
  ],
  agents: {
    pm: { vote: 'ok', note: 'budget ok' },
    hr: { vote: 'ok', note: 'growth ok' },
    risk: { vote: 'ok', note: 'risk ok' },
    gunshi: { recommend: 'A', note: 'steady' },
  },
  requirementResult: [{ name: 'TypeScript', fulfilled: true }],
};

const plansPayload = [
  {
    id: 'plan-sim-1-A',
    simulationId: 'sim-1',
    planType: 'A',
    summary: 'Steady plan',
    prosCons: { pros: ['Stable'], cons: ['Slow'] },
    score: 90,
    recommended: true,
  },
  {
    id: 'plan-sim-1-B',
    simulationId: 'sim-1',
    planType: 'B',
    summary: 'Future plan',
    prosCons: { pros: ['Growth'], cons: ['Cost'] },
    score: 80,
    recommended: false,
  },
  {
    id: 'plan-sim-1-C',
    simulationId: 'sim-1',
    planType: 'C',
    summary: 'Cost plan',
    prosCons: { pros: ['Cost'], cons: ['Risk'] },
    score: 70,
    recommended: false,
  },
];

const routeConfig = async (page: Page) => {
  await page.route('**/assets/runtime-config.json', (route) =>
    route.fulfill({ json: mockConfig })
  );
};

test('login -> dashboard -> simulator evaluate -> generate', async ({ page }) => {
  await routeConfig(page);

  await page.route('**/mock-api/auth/login', (route) => {
    route.fulfill({ json: { access_token: 'token-123', token_type: 'bearer' } });
  });
  await page.route('**/mock-api/dashboard/initial', (route) => {
    route.fulfill({ json: dashboardPayload });
  });
  await page.route('**/mock-api/projects', (route) => {
    route.fulfill({ json: sampleProjects });
  });
  await page.route('**/mock-api/projects/**/team', (route) => {
    route.fulfill({ json: { projectId: 'alpha', members: [] } });
  });
  await page.route('**/mock-api/members', (route) => {
    route.fulfill({ json: sampleMembers });
  });
  await page.route('**/mock-api/simulations/evaluate', (route) => {
    route.fulfill({ json: evaluationPayload });
  });
  await page.route('**/mock-api/simulations/**/plans/generate', (route) => {
    route.fulfill({ json: plansPayload });
  });

  await page.goto('/login');
  await page.getByPlaceholder('例: U001').fill('m1');
  await page.getByPlaceholder('dev password').fill('saihai');
  await page.getByRole('button', { name: 'ログイン' }).click();

  await expect(page).toHaveURL(/dashboard/);
  await expect(page.getByText('AI 提案')).toBeVisible();
  await expect(page.getByText('承認待ち')).toBeVisible();

  await page.goto('/simulator');
  await page.getByRole('combobox').selectOption('alpha');
  await page.getByText('Aki').click();
  await page.getByText('Rin').click();
  await page.getByRole('main').getByRole('button', { name: 'AI自動編成', exact: true }).click();

  await expect(page.getByText('3プラン（A/B/C）')).toBeVisible();
  await expect(page.getByText('要件カバー率')).toBeVisible();
  await expect(page.getByText('Plan A')).toBeVisible();
});

test('mobile flow supports input and approval', async ({ page }) => {
  await routeConfig(page);

  await page.route('**/mock-api/auth/login', (route) => {
    route.fulfill({ json: { access_token: 'token-123', token_type: 'bearer' } });
  });
  await page.route('**/mock-api/dashboard/initial', (route) => {
    route.fulfill({ json: dashboardPayload });
  });
  await page.route('**/mock-api/projects', (route) => {
    route.fulfill({ json: sampleProjects });
  });
  await page.route('**/mock-api/projects/**/team', (route) => {
    route.fulfill({ json: { projectId: 'alpha', members: [] } });
  });
  await page.route('**/mock-api/members', (route) => {
    route.fulfill({ json: sampleMembers });
  });
  await page.route('**/mock-api/simulations/evaluate', (route) => {
    route.fulfill({ json: evaluationPayload });
  });
  await page.route('**/mock-api/simulations/**/plans/generate', (route) => {
    route.fulfill({ json: plansPayload });
  });

  await page.setViewportSize({ width: 390, height: 844 });

  await page.goto('/login');
  await page.getByPlaceholder('例: U001').fill('m1');
  await page.getByPlaceholder('dev password').fill('saihai');
  await page.getByRole('button', { name: 'ログイン' }).click();

  await expect(page.getByRole('button', { name: 'メニュー' })).toBeVisible();
  await page.getByRole('button', { name: 'メニュー' }).click();
  await expect(page.getByRole('dialog', { name: 'ナビゲーション' })).toBeVisible();
  await page.getByRole('link', { name: '戦術シミュレーター' }).click();

  await expect(page).toHaveURL(/simulator/);
  await page.getByRole('combobox').selectOption('alpha');
  await page.getByText('Aki').click();
  await page.getByText('Rin').click();
  await page.getByRole('main').getByRole('button', { name: 'AI自動編成', exact: true }).click();

  await expect(page.getByText('3プラン（A/B/C）')).toBeVisible();
  await page.getByRole('button', { name: '介入（HITL）を開く' }).click();
  await expect(page.getByText('介入チェックポイント')).toBeVisible();
  const overlay = page.locator('.surface-overlay');
  const scrollArea = overlay.locator('[data-overlay-scroll]');
  await expect(scrollArea).toBeVisible();
  const { scrollWidth, clientWidth } = await overlay.evaluate((el) => ({
    scrollWidth: el.scrollWidth,
    clientWidth: el.clientWidth,
  }));
  expect(scrollWidth).toBeLessThanOrEqual(clientWidth + 2);

  const planHeading = overlay.getByText('戦略プランの選択');
  await planHeading.scrollIntoViewIfNeeded();
  const planInView = await planHeading.evaluate((el) => {
    const container = el.closest('[data-overlay-scroll]');
    if (!container) return false;
    const elRect = el.getBoundingClientRect();
    const containerRect = container.getBoundingClientRect();
    return elRect.top >= containerRect.top - 1 && elRect.bottom <= containerRect.bottom + 1;
  });
  expect(planInView).toBe(true);

  const chatInput = overlay.getByPlaceholder('指示を入力（空欄で承認）');
  await chatInput.scrollIntoViewIfNeeded();
  const inputInView = await chatInput.evaluate((el) => {
    const container = el.closest('[data-overlay-scroll]');
    if (!container) return false;
    const elRect = el.getBoundingClientRect();
    const containerRect = container.getBoundingClientRect();
    return elRect.top >= containerRect.top - 1 && elRect.bottom <= containerRect.bottom + 1;
  });
  expect(inputInView).toBe(true);

  const executeButton = overlay.getByRole('button', { name: '実行' });
  await executeButton.scrollIntoViewIfNeeded();
  await executeButton.click();
  await expect(page.getByText('承認されました。実行します。')).toBeVisible();
  await expect(page.getByText('介入チェックポイント')).toBeHidden();
});
