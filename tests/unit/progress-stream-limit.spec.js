import { test, expect } from '@playwright/test';
import fs from 'node:fs';
import path from 'node:path';

test('progress stream caps entries to latest 2000 lines', async () => {
  const storePath = path.resolve(process.cwd(), 'frontend/src/app/core/simulator-store.ts');
  const source = fs.readFileSync(storePath, 'utf8');

  expect(source).toContain('streamLineLimit = 2000');
  expect(source).toContain('capStreamLines');
  expect(source).toContain('slice(-this.streamLineLimit)');
});

test('progress stream list is not fixed height', async () => {
  const pagePath = path.resolve(process.cwd(), 'frontend/src/app/pages/simulator.page.ts');
  const source = fs.readFileSync(pagePath, 'utf8');

  expect(source).not.toContain('h-40 overflow-hidden');
});

test('agent log section renders the progress stream template', async () => {
  const pagePath = path.resolve(process.cwd(), 'frontend/src/app/pages/simulator.page.ts');
  const source = fs.readFileSync(pagePath, 'utf8');

  expect(source).toContain('根拠ログ（Agent Log）');
  expect(source).toContain('[ngTemplateOutlet]="progressStreamTemplate"');
  expect(source).not.toContain('@for (l of overlayLog()');
});
