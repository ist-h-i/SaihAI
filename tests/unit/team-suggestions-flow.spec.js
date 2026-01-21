import { test, expect } from '@playwright/test';
import fs from 'node:fs';
import path from 'node:path';

test('simulator store supports team-suggestion mode', async () => {
  const storePath = path.resolve(process.cwd(), 'frontend/src/app/core/simulator-store.ts');
  const source = fs.readFileSync(storePath, 'utf8');

  expect(source).toContain('teamSuggestionsResponse');
  expect(source).toContain('loadTeamSuggestions');
  expect(source).toContain('applyTeamSuggestion(suggestion: TeamSuggestion)');
});

test('api client exposes team-suggestion endpoints', async () => {
  const apiPath = path.resolve(process.cwd(), 'frontend/src/app/core/api-client.ts');
  const source = fs.readFileSync(apiPath, 'utf8');

  expect(source).toContain("/simulations/team-suggestions");
  expect(source).toContain("/simulations/team-suggestions/apply");
});

