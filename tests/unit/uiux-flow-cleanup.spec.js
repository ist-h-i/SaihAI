import { test, expect } from '@playwright/test';
import fs from 'node:fs';
import path from 'node:path';

test('app shell removes demo/global CTA noise', async () => {
  const appPath = path.resolve(process.cwd(), 'frontend/src/app/app.ts');
  const source = fs.readFileSync(appPath, 'utf8');

  expect(source).not.toContain('Debug & Demo');
  expect(source).not.toContain('緊急介入 (Alert)');
  expect(source).not.toContain('AI自動編成 (手動)');
  expect(source).not.toContain('レポート');
});

test('dashboard CTA copy is consolidated', async () => {
  const dashboardPath = path.resolve(process.cwd(), 'frontend/src/app/pages/dashboard.page.ts');
  const source = fs.readFileSync(dashboardPath, 'utf8');

  expect(source).toContain('介入へ');
  expect(source).not.toContain('secondaryLabel="シミュレーターへ"');
  expect(source).not.toContain('primaryLabel="シミュレーターへ"');
  expect(source).not.toContain('デモ');
});

test('simulator CTA removes demos and promotes intervention entry', async () => {
  const simulatorPath = path.resolve(process.cwd(), 'frontend/src/app/pages/simulator.page.ts');
  const source = fs.readFileSync(simulatorPath, 'utf8');

  expect(source).not.toContain('デモ');
  expect(source).toContain('介入（HITL）を開く');
  expect(source).toContain('再シミュレーション');
});

test('cleanup doc lists removals and regression checks', async () => {
  const docPath = path.resolve(process.cwd(), 'docs/uiux-flow-cleanup-issue-47.md');
  const doc = fs.readFileSync(docPath, 'utf8');

  expect(doc).toContain('削除/統合一覧');
  expect(doc).toContain('回帰確認チェックリスト');
  expect(doc).toContain('Dashboard');
  expect(doc).toContain('Genome');
  expect(doc).toContain('Simulator');
});
