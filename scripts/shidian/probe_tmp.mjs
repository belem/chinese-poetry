import { chromium } from 'playwright';
const browser = await chromium.launch();
const ctx = await browser.newContext({ locale:'zh-CN', userAgent:'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36'});
const page = await ctx.newPage();
page.on('response', async r => {
  const u = r.url();
  if (/api|search|chapter/i.test(u) && !/\.(js|css|png|jpg|woff)/.test(u)) {
    console.log('RESP', r.status(), u.slice(0,160));
  }
});
await page.goto('https://www.shidianguji.com/zh/book/cgjhvd2hqr8n7/chapter/cgjhvd2hqr8n7', {waitUntil:'domcontentloaded', timeout:60000}).catch(e=>console.log('goto err', e.message));
await page.waitForTimeout(5000);
console.log('URL', page.url());
console.log((await page.evaluate(()=>document.body.innerText)).slice(0,1500));
await browser.close();
