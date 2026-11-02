import { chromium } from 'playwright';
const browser = await chromium.launch();
const ctx = await browser.newContext({ locale:'zh-CN', viewport:{width:1400,height:1200}, userAgent:'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36'});
const page = await ctx.newPage();
await page.goto('https://www.shidianguji.com/zh/book/SDZJ0641/chapter/1kf9lwwlsqyaj', { waitUntil:'domcontentloaded', timeout:60000 });
await page.waitForTimeout(7000);
const r = await page.evaluate(()=>{
  const p=[...document.querySelectorAll('p')].find(x=>(x.textContent||'').includes('故名曰寤生'));
  return {html: p.outerHTML.slice(0,1200), nkids: p.children.length, inner: p.innerHTML.slice(0,900)};
});
console.log(JSON.stringify(r,null,1));
await browser.close();
