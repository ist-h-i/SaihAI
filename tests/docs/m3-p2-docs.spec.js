import { test, expect } from '@playwright/test';
import fs from 'node:fs';

const read = (path) => fs.readFileSync(new URL(path, import.meta.url), 'utf8');

test.describe('Docs: M3 P2', () => {
  test('tasklist marks M3 P2 items as done', async () => {
    const tasklist = read('../../docs/tasklist.md');
    const done = ['[x] IMP-029', '[x] IMP-032', '[x] EXT-006', '[x] EXT-007', '[x] EXT-008'];
    for (const marker of done) {
      expect(tasklist).toContain(marker);
    }
  });

  test('migration adds external action and ingestion tables', async () => {
    const migration = read('../../backend/migrations/0003_m3_extensions.up.sql');
    const required = ['external_action_runs', 'input_ingestion_runs', 'action_payload'];
    for (const name of required) {
      expect(migration).toContain(name);
    }
  });

  test('streaming endpoint and frontend stream usage exist', async () => {
    const backend = read('../../backend/app/api/v1.py');
    const frontend = read('../../frontend/src/app/core/simulator-store.ts');
    expect(backend).toContain('/plans/stream');
    expect(frontend).toContain('EventSource');
    expect(frontend).toContain('/plans/stream');
  });

  test('CI follow-up notes exist', async () => {
    const todo = read('../../docs/todolist.md');
    expect(todo).toContain('frontend build');
    expect(todo).toContain('backend validation');
  });
});
