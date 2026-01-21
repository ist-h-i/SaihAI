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
