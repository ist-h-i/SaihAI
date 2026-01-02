import { test, expect } from '@playwright/test';
import fs from 'node:fs';

const scenariosPath = new URL('../../evidence/scenarios.json', import.meta.url);
const scenarios = JSON.parse(fs.readFileSync(scenariosPath, 'utf8'));

test.describe('UI Evidence', () => {
  for (const scenario of scenarios) {
    test(`${scenario.name}`, async ({ page }, testInfo) => {
      await page.goto(scenario.url, { waitUntil: 'domcontentloaded' });

      if (scenario.assertText) {
        await expect(page.locator('body')).toContainText(scenario.assertText);
      }

      // Force a deterministic screenshot file name for easy retrieval from artifacts.
      const safe = scenario.name.replace(/[^a-z0-9-_]+/gi, '-').toLowerCase().slice(0, 80);
      const screenshotPath = testInfo.outputPath(`evidence-${safe}.png`);
      await page.screenshot({ path: screenshotPath, fullPage: true });
    });
  }
});
