import { test, expect } from '@playwright/test';
import fs from 'node:fs';
import path from 'node:path';

test('simulator accordions expose affordance + aria wiring', async () => {
  const simulatorPath = path.resolve(process.cwd(), 'frontend/src/app/pages/simulator.page.ts');
  const source = fs.readFileSync(simulatorPath, 'utf8');

  expect(source).toContain('ui-accordion__summary');
  expect(source).toContain('aria-controls="requirement-coverage-panel"');
  expect(source).toContain('aria-controls="future-timeline-panel"');
  expect(source).toContain('aria-controls="agent-insights-panel"');
});

test('flow label is styled as non-interactive status', async () => {
  const simulatorPath = path.resolve(process.cwd(), 'frontend/src/app/pages/simulator.page.ts');
  const source = fs.readFileSync(simulatorPath, 'utf8');

  expect(source).toContain('ui-flow-label');
  expect(source).toContain('ui-flow-panel');
});
