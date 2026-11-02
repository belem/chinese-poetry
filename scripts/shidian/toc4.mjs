import { chromium } from 'playwright';
const browser = await chromium.launch();
const ctx = await browser.newContext({ locale:'zh-CN', userAgent:'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36'});
const page = await ctx.newPage();
const captures=[];
page.on('response', async r=>{
  const u=r.url();
  if (/\/api\/ancientlib\//.test(u) && /(catalog|toc|chapter|menu|bookinfo|book\/get)/i.test(u)) {
    try{ const b = await r.text(); captures.push({u:u.split('?')[0], len:b.length, b:b.slice(0,300)}); }catch(e){}
  }
});
await page.goto('https://www.shidianguji.com/zh/book/SDZJ0641/chapter/1kf9lwr20s4yj', { waitUntil:'domcontentloaded', timeout:60000 });
await page.waitForTimeout(6000);
// look for toc in DOM: right side 目录 list
const tocHtml = await page.evaluate(()=>{
  const el=[...document.querySelectorAll('*')].find(e=>/(古文觀止卷之一)/.test(e.innerText||'') && e.children.length>3 && (e.innerText||'').length<20000);
  return el? el.outerHTML : '';
});
console.log('tocHtml len', tocHtml.length);
const ids = [...tocHtml.matchAll(/chapter\/([a-z0-9]+)/g)].map(m=>m[1]);
console.log('ids from toc', ids.length, ids.slice(0,10));
console.log(captures.map(c=>c.u+' '+c.len).join('\n'));
