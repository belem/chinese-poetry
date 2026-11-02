import { chromium } from 'playwright';
const browser = await chromium.launch();
const ctx = await browser.newContext({ locale:'zh-CN', userAgent:'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36'});
const page = await ctx.newPage();
await page.goto('https://www.shidianguji.com/zh/search/%E6%A2%85%E8%8A%B1%E5%B6%BA%E8%A8%98', {waitUntil:'domcontentloaded', timeout:60000});
await page.waitForTimeout(6000);
const links = await page.evaluate(()=>[...document.querySelectorAll('a')].map(a=>a.getAttribute('href')).filter(h=>h&&/book|chapter/.test(h)));
console.log([...new Set(links)].slice(0,40).join('\n'));
await browser.close();
