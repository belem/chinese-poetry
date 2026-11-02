import { chromium } from 'playwright';
const browser = await chromium.launch();
const ctx = await browser.newContext({ locale:'zh-CN', viewport:{width:1400,height:1200}, userAgent:'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36'});
const page = await ctx.newPage();
await page.goto('https://www.shidianguji.com/zh/book/SDZJ0641/chapter/1kf9lxpygcrw3', { waitUntil:'domcontentloaded', timeout:60000 });
await page.waitForTimeout(9000);
const r = await page.evaluate(()=>{
  const all=[...document.querySelectorAll('p,h1,h2,h3,div')].filter(e=>(e.textContent||'').trim().length>0 && (e.textContent||'').trim().length<60);
  return all.slice(0,40).map(e=>({tag:e.tagName,cls:typeof e.className==='string'?e.className:'',t:e.textContent.trim().slice(0,30)}));
});
console.log(JSON.stringify(r,null,1).slice(0,4000));
await browser.close();
