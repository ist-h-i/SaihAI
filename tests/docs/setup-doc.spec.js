import { test, expect } from '@playwright/test';
import fs from 'node:fs';

test.describe('Docs: setup.md', () => {
  test('contains required sections and is linked from README', async () => {
    const setup = fs.readFileSync(new URL('../../docs/setup.md', import.meta.url), 'utf8');
    const readme = fs.readFileSync(new URL('../../README.md', import.meta.url), 'utf8');

    // Required sections (Acceptance Criteria coverage)
    const required = [
      '外部サービス一覧（カテゴリ別）',
      'AI: AWS Bedrock のセットアップ',
      'DB: PostgreSQL + pgvector のセットアップ',
      'Slack: Web API / アプリ作成',
      '環境変数/シークレット一覧と取得元',
      'ローカル動作確認（サマリ）',
      'ドキュメントの配置/参照'
    ];
    for (const h of required) {
      expect(setup).toContain(h);
    }

    // README からの参照リンク
    expect(readme).toMatch(/docs\/setup\.md/);
  });
});

