// SPDX-License-Identifier: MIT
// Optional QA using an already-installed Playwright module and browser.
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const output = path.join(root, '.build');
await fs.mkdir(output, { recursive: true });
const { chromium } = process.env.PLAYWRIGHT_MODULE
  ? await import(pathToFileURL(process.env.PLAYWRIGHT_MODULE).href)
  : await import('playwright');
const browser = await chromium.launch({ headless: true,
  ...(process.env.EDGE_PATH ? { executablePath: process.env.EDGE_PATH } : {}) });
const page = await browser.newPage({ viewport: { width: 1280, height: 960 } });
const errors = [], requests = [], checks = [];
page.on('pageerror', error => errors.push(String(error)));
page.on('request', request => { if (!request.url().startsWith('file:')) requests.push(request.url()); });
async function check(name, action) { await action(); checks.push({ name, passed: true }); }
async function fits() { assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)); }
try {
  await page.goto(pathToFileURL(path.join(root, 'docs/index.html')).href);
  await check('nine stages and complete detail panels', async () => {
    assert.equal(await page.locator('.stage').count(), 9);
    assert.equal(await page.locator('.stage[aria-pressed=true] strong').textContent(), '集成与导出约定');
    for (let i = 0; i < 9; i++) {
      await page.locator('.stage').nth(i).click();
      assert.equal(await page.locator('.stage[aria-pressed=true]').count(), 1);
      assert.equal(await page.locator('#detail .section').count(), 3);
      assert.match(await page.locator('#detail .status').textContent(), new RegExp('STAGE 0' + i));
    }
  });
  await check('desktop roadmap', async () => {
    await fits(); await page.locator('.stage').nth(1).click();
    await page.screenshot({ path: path.join(root, 'docs/assets/roadmap-desktop.png'), fullPage: true, animations: 'disabled' });
  });
  await check('390px roadmap and keyboard activation', async () => {
    await page.setViewportSize({ width: 390, height: 844 }); await fits();
    await page.locator('.stage').nth(5).focus(); await page.keyboard.press('Enter');
    assert.match(await page.locator('#detail h2').textContent(), /CSI/);
    await page.screenshot({ path: path.join(output, 'roadmap-mobile.png'), fullPage: true, animations: 'disabled' });
  });
  await page.goto(pathToFileURL(path.join(root, 'examples/report/report.html')).href);
  await check('standalone report and simulated provenance', async () => {
    assert.equal(await page.locator('[role=tab]').count(), 2);
    assert.match(await page.locator('.report:visible .origin').textContent(), /SIMULATED/);
    assert.equal(await page.locator('.report:visible .stat strong').first().textContent(), '160'); await fits();
  });
  await check('hotspot filters and sample scrubbing', async () => {
    await page.locator('.report:visible .filter button', { hasText: '走远' }).click();
    assert.equal(await page.locator('.report:visible .filter [aria-pressed=true]').textContent(), '走远');
    assert(await page.locator('.report:visible .series').count() > 0);
    await page.locator('.report:visible .scrub').focus(); await page.keyboard.press('End');
    assert.match(await page.locator('.report:visible .readout').textContent(), /79.5 s/);
    await page.locator('.report:visible .filter button', { hasText: '全部' }).click();
  });
  await check('CSI keyboard tab and metric selection', async () => {
    await page.locator('[role=tab]').first().focus(); await page.keyboard.press('ArrowRight');
    await page.locator('.report:visible .metric').selectOption('gap_ms');
    await page.locator('.report:visible .scrub').focus(); await page.keyboard.press('End');
    assert.match(await page.locator('.report:visible .readout').textContent(), /间隔 50 ms/);
  });
  await check('desktop report and provenance details', async () => {
    await page.setViewportSize({ width: 1280, height: 960 });
    await page.locator('[role=tab]').first().click(); await page.locator('.report:visible summary').click();
    assert.match(await page.locator('.report:visible pre').textContent(), /sha256/);
    await page.locator('.report:visible summary').click(); await fits();
    await page.screenshot({ path: path.join(root, 'docs/assets/report-desktop.png'), fullPage: true, animations: 'disabled' });
  });
  await check('zero external requests and JavaScript errors', async () => {
    assert.deepEqual(requests, []); assert.deepEqual(errors, []);
  });
  await fs.writeFile(path.join(output, 'browser-results.json'), JSON.stringify({
    browser: await browser.version(), simulated: true, checks, errors, external_requests: requests,
  }, null, 2) + '\n');
  process.stdout.write(`PASS ${checks.length} browser groups; 0 external requests; 0 JavaScript errors\n`);
} finally { await browser.close(); }
