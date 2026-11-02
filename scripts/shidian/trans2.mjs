import { chromium } from 'playwright';
const browser = await chromium.launch();
const ctx = await browser.newContext({ locale:'zh-CN', userAgent:'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36'});
const page = await ctx.newPage();
await page.goto('https://www.shidianguji.com/zh/book/SDZJ0641/chapter/1kf9lwwlsqyaj', { waitUntil:'domcontentloaded', timeout:60000 });
await page.waitForTimeout(5000);
const info = await page.evaluate(()=>{
  // 找页面顶部那个「译文」控件
  const cands=[...document.querySelectorAll('*')].filter(e=>(e.innerText||'').trim()==='译文' && e.children.length<=1);
  return cands.map(e=>({tag:e.tagName, cls:e.className, parentTag:e.parentElement?.tagName, parentCls:e.parentElement?.className, outer:e.outerHTML.slice(0,300)}));
});
console.log(JSON.stringify(info,null,1).slice(0,2000));
// try clicking 译文 and capture network
const cap=[];
page.on('request', r=>{ if(/ancientlib/.test(r.url())) cap.push(r.url().split('?')[0]); });
const before = cap.length;
await page.mouse.click(1,1);
await page.evaluate(()=>{ const e=[...document.querySelectorAll('*')].find(x=>(x.innerText||'').trim()==='译文'&&x.children.length<=1); e && e.click(); });
await page.waitForTimeout(4000);
console.log([...new Set(cap.slice(before))].join('\n'));
const html = await page.content();
const i = html.indexOf('译文');
console.log((await page.evaluate(()=>document.body.innerText)).slice(300, 1200));
await browser.close();
