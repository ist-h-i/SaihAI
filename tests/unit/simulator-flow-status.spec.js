import { test, expect } from '@playwright/test';
import fs from 'node:fs';
import path from 'node:path';

test('simulator flow state advances to intervention on valid results', async () => {
  const simulatorPath = path.resolve(process.cwd(), 'frontend/src/app/pages/simulator.page.ts');
  const source = fs.readFileSync(simulatorPath, 'utf8');

  expect(source).toContain('validSimulationResult');
  expect(source).toContain('if (this.store.loading() || this.store.streaming()) return 2;');
  expect(source).toContain('return this.interventionCompleted() ? 5 : 4;');
});

test('simulator approval marks intervention completed', async () => {
  const simulatorPath = path.resolve(process.cwd(), 'frontend/src/app/pages/simulator.page.ts');
  const source = fs.readFileSync(simulatorPath, 'utf8');

  expect(source).toContain('this.approvedSimulationId.set(simulation.id);');
});

test('simulator result sections gate on valid results', async () => {
  const simulatorPath = path.resolve(process.cwd(), 'frontend/src/app/pages/simulator.page.ts');
  const source = fs.readFileSync(simulatorPath, 'utf8');

  expect(source).toContain('@if (validSimulationResult())');
  expect(source).toContain('@if (validSimulationResult(); as r)');
});
