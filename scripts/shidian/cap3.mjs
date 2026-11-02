import { chromium } from 'playwright';
const browser = await chromium.launch();
const ctx = await browser.newContext({ locale:'zh-CN', userAgent:'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36'});
const page = await ctx.newPage();
const reqs=[];
page.on('request', r=>{ const u=r.url(); if(/ancientlib/.test(u)) reqs.push(u); });
await page.goto('https://www.shidianguji.com/zh/book/SDZJ0641/chapter/1kf9lwr20s4yj', { waitUntil:'domcontentloaded', timeout:60000 });
await page.waitForTimeout(5000);
// click the last-toc volume entry (卷之十二) to trigger lazy load
const clicked = await page.evaluate(()=>{
  const as=[...document.querySelectorAll('a[href*="/chapter/"]')].filter(a=>/卷之/.test(a.innerText));
  if (as.length) { as[as.length-1].click(); return as.length; }
  return 0;
});
await page.waitForTimeout(4000);
// also click 下一篇 a few times to enumerate
console.log('vol links', clicked);
console.log([...new Set(reqs)].filter(u=>/chapter-list|pages|volume/.test(u)).join('\n'));
await browser.close();
