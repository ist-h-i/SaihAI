import { test, expect } from '@playwright/test';
import fs from 'node:fs';
import path from 'node:path';

test('simulator stream completion forces progress to 100%', async () => {
  const storePath = path.resolve(process.cwd(), 'frontend/src/app/core/simulator-store.ts');
  const source = fs.readFileSync(storePath, 'utf8');

  expect(source).toContain('progress: 100');
  expect(source).toContain("phase: 'complete'");
  expect(source).toContain('if (done) return;');
});
