import { test, expect } from '@playwright/test';
import fs from 'node:fs';

const scenariosPath = new URL('../../evidence/scenarios.json', import.meta.url);
const scenarios = JSON.parse(fs.readFileSync(scenariosPath, 'utf8'));
const baseUrl = process.env.E2E_BASE_URL ?? process.env.PLAYWRIGHT_BASE_URL ?? '';

const isAbsoluteUrl = (value) =>
  value.toLowerCase().startsWith('http://') || value.toLowerCase().startsWith('https://');
const resolveUrl = (value) => {
  if (isAbsoluteUrl(value)) return value;
  if (!baseUrl) {
    throw new Error('Scenario url requires E2E_BASE_URL or PLAYWRIGHT_BASE_URL');
  }
  return new URL(value, baseUrl).toString();
};

const runUiEvidence = process.env.PW_UI_EVIDENCE === '1';

const applyScenarioInit = async (page, scenario) => {
  if (scenario?.colorScheme === 'dark' || scenario?.colorScheme === 'light') {
    await page.emulateMedia({ colorScheme: scenario.colorScheme });
  }

  if (scenario?.localStorage && typeof scenario.localStorage === 'object') {
    const entries = Object.entries(scenario.localStorage).map(([k, v]) => [String(k), String(v)]);
    await page.addInitScript(({ items }) => {
      for (const [key, value] of items) {
        try {
          globalThis.localStorage?.setItem(key, value);
        } catch {
          // ignore storage failures
        }
      }
    }, { items: entries });
  }
};

const runScenarioActions = async (page, scenario) => {
  if (!Array.isArray(scenario?.actions)) return;
  for (const action of scenario.actions) {
    if (!action || typeof action !== 'object') continue;
    if (action.type === 'click' && action.selector) {
      await page.locator(String(action.selector)).first().click();
      continue;
    }
    if (action.type === 'waitForSelector' && action.selector) {
      await page.waitForSelector(String(action.selector), { state: 'visible' });
      continue;
    }
    if (action.type === 'waitForTimeout' && typeof action.ms === 'number') {
      await page.waitForTimeout(action.ms);
      continue;
    }
  }
};

test.describe('UI Evidence', () => {
  // NOTE: This environment may not permit Chromium sandboxing and can crash the browser process.
  // Enable explicitly when running on a runner that supports Playwright browsers.
  test.skip(!runUiEvidence, 'Set PW_UI_EVIDENCE=1 to enable UI evidence runs');
  for (const scenario of scenarios) {
    test(`${scenario.name}`, async ({ page }, testInfo) => {
      await applyScenarioInit(page, scenario);
      if (scenario.inlineHtml) {
        await page.setContent(String(scenario.inlineHtml), { waitUntil: 'domcontentloaded' });
      } else if (scenario.url) {
        if (!isAbsoluteUrl(String(scenario.url)) && !baseUrl) {
          test.skip(true, 'Scenario url requires E2E_BASE_URL or PLAYWRIGHT_BASE_URL');
        }
        await page.goto(resolveUrl(String(scenario.url)), { waitUntil: 'domcontentloaded' });
      } else {
        throw new Error('Scenario requires either url or inlineHtml');
      }

      if (scenario.assertText) {
        await expect(page.locator('body')).toContainText(scenario.assertText);
      }

      await runScenarioActions(page, scenario);

      const safe = scenario.name.replace(/[^a-z0-9-_]+/gi, '-').toLowerCase().slice(0, 80);
      const screenshotPath = testInfo.outputPath(`evidence-${safe}.png`);
      await page.screenshot({ path: screenshotPath, fullPage: true });
    });
  }
});
