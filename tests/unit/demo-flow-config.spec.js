import { test, expect } from '@playwright/test';
import fs from 'node:fs';
import path from 'node:path';

test('demo flow uses fixed calendar window and invitee config', async () => {
  const demoPath = path.resolve(process.cwd(), 'backend/app/domain/demo.py');
  const source = fs.readFileSync(demoPath, 'utf8');

  expect(source).toContain('18, 0');
  expect(source).toContain('timedelta(minutes=30)');
  expect(source).toContain('DEMO_TIMEZONE');
  expect(source).toContain('INVITEE_EMAILS');
  expect(source).toContain('calendar_id');
});
