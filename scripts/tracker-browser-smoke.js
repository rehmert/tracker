#!/usr/bin/env node

/*
 * Optional read-only Playwright browser checks.
 *
 * Usage:
 * node scripts/tracker-browser-smoke.js http://127.0.0.1:8000
 */

(async () => {
  const base = process.argv[2];

  if (!base || !/^https?:\/\//.test(base)) {
    console.error(
      'Usage: node scripts/tracker-browser-smoke.js ' +
      'http://127.0.0.1:8000'
    );

    process.exit(2);
  }

  let chromium;

  try {
    ({ chromium } = require('playwright'));
  } catch {
    console.error(
      'Playwright is not installed. ' +
      'Browser tests are optional.'
    );

    process.exit(2);
  }

  const browser = await chromium.launch({
    headless: true
  });

  const failures = [];

  try {
    for (const width of [390, 1280]) {
      const page = await browser.newPage({
        viewport: {
          width,
          height: 900
        }
      });

      const errors = [];

      page.on('pageerror', error => {
        errors.push(String(error));
      });

      const response = await page.goto(
        base.replace(/\/$/, '') + '/vials',
        {
          waitUntil: 'domcontentloaded',
          timeout: 15000
        }
      );

      if (!response || response.status() >= 500) {
        failures.push(
          `${width}px: HTTP ${response?.status()}`
        );
      }

      await page.waitForTimeout(750);

      const metrics = await page.evaluate(() => ({
        title: document.title,
        bodyWidth: document.body.scrollWidth,
        viewport: innerWidth,
        forms: document.forms.length,
        tables: document.querySelectorAll('table').length
      }));

      console.log(JSON.stringify({
        width,
        status: response?.status(),
        ...metrics,
        errors
      }, null, 2));

      if (errors.length) {
        failures.push(
          `${width}px: ${errors.join('; ')}`
        );
      }

      if (metrics.bodyWidth > width + 12) {
        console.warn(
          `${width}px: horizontal page overflow detected`
        );
      }

      await page.close();
    }

  } finally {
    await browser.close();
  }

  if (failures.length) {
    console.error(
      failures.join('\n')
    );

    process.exit(1);
  }

})().catch(error => {
  console.error(error);
  process.exit(1);
});
