import { test, expect } from '@playwright/test';
import fs from 'node:fs';

const read = (path) => fs.readFileSync(new URL(path, import.meta.url), 'utf8');

test.describe('Docs: M2 HITL/Slack', () => {
  test('slack app design doc exists and lists endpoints', async () => {
    const doc = read('../../docs/slack-app.md');
    expect(doc).toContain('Slack App');
    expect(doc).toContain('/slack/interactions');
    expect(doc).toContain('/slack/events');
  });

  test('m2 migration includes hitl/watchdog tables', async () => {
    const migration = read('../../backend/migrations/0002_m2_hitl_watchdog.up.sql');
    const required = [
      'hitl_states',
      'hitl_approval_requests',
      'hitl_audit_logs',
      'execution_jobs',
      'watchdog_jobs',
      'watchdog_alerts'
    ];
    for (const name of required) {
      expect(migration).toContain(name);
    }
  });

  test('tasklist marks M2 items as done', async () => {
    const tasklist = read('../../docs/tasklist.md');
    const doneMarkers = [
      '[x] IMP-017-01',
      '[x] IMP-018-01',
      '[x] IMP-022-01',
      '[x] IMP-024-01',
      '[x] IMP-030-01',
      '[x] EXT-003-01',
      '[x] EXT-004-01',
      '[x] EXT-005-01',
      '[x] EXT-005-02'
    ];
    for (const marker of doneMarkers) {
      expect(tasklist).toContain(marker);
    }
  });
});
