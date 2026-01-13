import { test, expect } from '@playwright/test';
import fs from 'node:fs';
import path from 'node:path';

test('login page renders Haisa speech as avatar + bubble with emotion rules', async () => {
  const loginPagePath = path.resolve(process.cwd(), 'frontend/src/app/pages/login.page.ts');
  const source = fs.readFileSync(loginPagePath, 'utf8');

  expect(source).toContain("const LOGIN_GUIDANCE_MESSAGE = '入力したらログインを押してください。';");
  expect(source).toContain('<app-haisa-speech');
  expect(source).toContain('[showAvatar]="true"');
  expect(source).toContain('[speaker]="\'サイハイくん\'"');
  expect(source).toContain('[message]="haisaMessage()"');
  expect(source).toContain('[emotion]="haisaEmotion()"');

  expect(source).toContain("if (this.error()) return 'anxiety';");
  expect(source).toContain("if (this.loading()) return 'energy';");
  expect(source).toContain("if (hasUserId && hasPassword) return 'hope';");
  expect(source).toContain("if (hasUserId || hasPassword) return 'effort';");
  expect(source).toContain("return 'standard';");
});
