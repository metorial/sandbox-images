let { chromium } = require('playwright');

(async () => {
  let browser = await chromium.launch({ args: ['--disable-dev-shm-usage'] });
  try {
    let page = await browser.newPage();
    await page.setContent('<title>Sandbox Browser</title><h1>Ready</h1>');
    if (await page.title() !== 'Sandbox Browser') throw new Error('Browser smoke test failed');
    await page.screenshot({ path: '/tmp/browser.png' });
    console.log('Chromium launched, rendered HTML and captured a screenshot');
  } finally {
    await browser.close();
  }
})().catch(error => { console.error(error); process.exit(1); });
