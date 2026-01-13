import { test, expect } from '@playwright/test';
import fs from 'node:fs';

test.describe('Docs: uiux-improvement-plan.md', () => {
  test('exists and covers acceptance criteria sections', async () => {
    const doc = fs.readFileSync(
      new URL('../../docs/uiux-improvement-plan.md', import.meta.url),
      'utf8'
    );

    const required = [
      '/login',
      '/dashboard',
      '/simulator',
      '/genome',
      '症状',
      '原因',
      '影響',
      '根拠',
      '文字情報削減',
      'サイハイくん',
      'emotion',
      'Issue #34',
      'ログイン画面の emotion 使い分け',
      '`anxiety`',
      '`energy`',
      '`hope`',
      '`effort`',
      '`standard`',
      'トーン&マナー',
      'ロードマップ',
    ];

    for (const section of required) {
      expect(doc).toContain(section);
    }

    expect(doc).not.toContain('TBD');
  });
});
