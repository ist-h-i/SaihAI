import { test, expect } from '@playwright/test';
import fs from 'node:fs';

test.describe('Docs: tasklist.md', () => {
  test('contains required sections and key anchors', async () => {
    const tasklist = fs.readFileSync(new URL('../../docs/tasklist.md', import.meta.url), 'utf8');

    const required = [
      '参照資料一覧',
      '現状実装の棚卸し',
      '主要画面（現状の画面一覧＝正）',
      '/dashboard',
      '/simulator',
      '/genome',
      'タスク運用基準',
      'Issue→PR',
      'タスクリスト',
      '実装（Implementation）',
      'インフラ構築（AWS）',
      '外部API連携',
      'AIエンドポイント要件表',
      '主要エンドポイント一覧',
      'Bearer JWT',
      'サブタスク（PR単位',
      'IMP-003',
      'AWS-001',
      'EXT-001',
    ];

    for (const section of required) {
      expect(tasklist).toContain(section);
    }

    expect(tasklist).not.toContain('TBD');
  });
});
