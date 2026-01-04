import { test, expect } from '@playwright/test';
import fs from 'node:fs';

test.describe('Docs: aws-setup.md (staging)', () => {
  test('exists, has required sections, and is linked from README/setup.md', async () => {
    const doc = fs.readFileSync(new URL('../../docs/aws-setup.md', import.meta.url), 'utf8');
    const readme = fs.readFileSync(new URL('../../README.md', import.meta.url), 'utf8');
    const setup = fs.readFileSync(new URL('../../docs/setup.md', import.meta.url), 'utf8');

    const required = [
      'AWS リソース構築手順（staging）',
      'Goals（この手順書で到達する状態）',
      '前提',
      'Bedrock（モデル有効化）',
      'CDK（staging）デプロイ手順',
      'サービス別手順（構築 → 取得値 → 設定 → 動作確認）',
      'GitHub Secrets（staging）登録一覧',
      '構築後チェックリスト（staging）'
    ];
    for (const h of required) {
      expect(doc).toContain(h);
    }

    // Key mapping: outputs -> secrets/env vars
    expect(doc).toContain('Outputs');
    expect(doc).toContain('AWS_REGION');
    expect(doc).toContain('DATABASE_URL');
    expect(doc).toContain('SAIHAI_API_BASE_URL');

    // Linked from other entry points
    expect(readme).toMatch(/docs\/aws-setup\.md/);
    expect(setup).toMatch(/docs\/aws-setup\.md/);
  });
});

