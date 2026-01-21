import { test, expect } from '@playwright/test';
import fs from 'node:fs';
import path from 'node:path';

test('saved plans migration is present', async () => {
  const migrationPath = path.resolve(
    process.cwd(),
    'backend/migrations/0007_saved_plans.up.sql'
  );
  const sql = fs.readFileSync(migrationPath, 'utf8');

  expect(sql).toContain('CREATE TABLE saved_plans');
  expect(sql).toContain('content_json');
  expect(sql).toContain('selected_plan');
});

test('saved plan endpoints are exposed in v1 api', async () => {
  const apiPath = path.resolve(process.cwd(), 'backend/app/api/v1.py');
  const source = fs.readFileSync(apiPath, 'utf8');

  expect(source).toContain('@router.get("/plans"');
  expect(source).toContain('@router.get("/plans/{plan_id}"');
  expect(source).toContain('@router.patch("/plans/{plan_id}"');
  expect(source).toContain('@router.delete("/plans/{plan_id}"');
});

test('simulator page includes saved plan controls', async () => {
  const simulatorPath = path.resolve(process.cwd(), 'frontend/src/app/pages/simulator.page.ts');
  const source = fs.readFileSync(simulatorPath, 'utf8');

  expect(source).toContain('保存済みプラン');
  expect(source).toContain('タイトル更新');
  expect(source).toContain('新規作成');
});
