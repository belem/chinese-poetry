import { chromium } from 'playwright';
const browser = await chromium.launch();
const ctx = await browser.newContext({ locale:'zh-CN', userAgent:'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36'});
const page = await ctx.newPage();
await page.goto('https://www.shidianguji.com/zh/book/SDZJ0641/chapter/1kf9lwwlsqlnf', {waitUntil:'domcontentloaded', timeout:60000});
await page.waitForTimeout(6000);
const txt = await page.evaluate(()=>document.body.innerText);
console.log(txt.slice(0,4000));
await browser.close();
