import { chromium } from 'playwright';
const browser = await chromium.launch();
const ctx = await browser.newContext({ locale:'zh-CN', viewport:{width:1400,height:1200}, userAgent:'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36'});
const page = await ctx.newPage();
await page.goto('https://www.shidianguji.com/zh/book/SDZJ0641/chapter/1kf9lwwlsqyaj', { waitUntil:'domcontentloaded', timeout:60000 });
await page.waitForTimeout(7000);
const r = await page.evaluate(()=>{
  const ps=[...document.querySelectorAll('p')].filter(x=>(x.textContent||'').includes('故名曰寤生'));
  return ps.map(p=>({nk:p.children.length, html:p.outerHTML.slice(0,1500)}));
});
console.log(JSON.stringify(r,null,1).slice(0,5000));
await browser.close();
