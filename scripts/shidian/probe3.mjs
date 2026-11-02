import { chromium } from 'playwright';
const browser = await chromium.launch();
const ctx = await browser.newContext({ locale:'zh-CN', userAgent:'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36'});
const page = await ctx.newPage();
for (const u of ['https://www.shidianguji.com/zh/book/SBCK285/chapter/SBCK285_636']) {
  await page.goto(u, {waitUntil:'domcontentloaded', timeout:60000});
  await page.waitForTimeout(4000);
  const txt = await page.evaluate(()=>document.body.innerText);
  console.log(txt.slice(0, 3000));
}
await browser.close();
