import { test, expect } from '@playwright/test';
import fs from 'node:fs';
import path from 'node:path';

test('brand logo text uses "Saih" + highlighted "AI" (desktop + mobile)', async () => {
  const appTsPath = path.resolve(process.cwd(), 'frontend/src/app/app.ts');
  const source = fs.readFileSync(appTsPath, 'utf8');

  const expected = 'Saih<span class="text-fuchsia-400">AI</span>';
  expect(source.split(expected).length - 1).toBe(2);
  expect(source).not.toContain('saih<span class="text-fuchsia-400">AI</span>');
});

