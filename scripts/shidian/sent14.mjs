import { chromium } from 'playwright';
const browser = await chromium.launch();
const ctx = await browser.newContext({ locale:'zh-CN', viewport:{width:1400,height:1200}, userAgent:'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36'});
const page = await ctx.newPage();
await page.goto('https://www.shidianguji.com/zh/book/SDZJ0641/chapter/1kf9lwwlsqyaj', { waitUntil:'domcontentloaded', timeout:60000 });
await page.waitForTimeout(7000);
await page.mouse.wheel(0,800); await page.waitForTimeout(2500);
const r2 = await page.evaluate(()=>{
  const all=[...document.querySelectorAll('*')].filter(e=>!/(SCRIPT|STYLE)/.test(e.tagName));
  const hit=all.filter(e=>/起初，鄭武公娶了申國/.test(e.textContent||''));
  return hit.map(e=>({tag:e.tagName, cls:typeof e.className==='string'?e.className:'', nk:e.children.length, t:(e.textContent||'').slice(0,80)}));
});
console.log('TRANS NODES:', JSON.stringify(r2,null,1).slice(0,2000));
const nodeCount = await page.evaluate(()=>document.querySelectorAll('p').length);
console.log('p count', nodeCount);
await browser.close();
