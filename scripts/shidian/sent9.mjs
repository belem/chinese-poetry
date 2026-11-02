import { chromium } from 'playwright';
const browser = await chromium.launch();
const ctx = await browser.newContext({ locale:'zh-CN', viewport:{width:1400,height:1200}, userAgent:'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36'});
const page = await ctx.newPage();
await page.goto('https://www.shidianguji.com/zh/book/SDZJ0641/chapter/1kf9lwwlsqyaj', { waitUntil:'domcontentloaded', timeout:60000 });
await page.waitForTimeout(7000);
const r = await page.evaluate(()=>{
  // 找「起初，郑武公娶了申国的女子」所在的元素
  const hit=[...document.querySelectorAll('*')].filter(e=>e.children.length===0 && /起初，鄭武公娶了申國|起初，郑武公娶了申国/.test(e.textContent||''));
  return hit.map(e=>{
    let chain=[], p=e;
    for(let i=0;i<4&&p;i++){ chain.push(p.tagName+'.'+(typeof p.className==='string'?p.className:'')); p=p.parentElement; }
    return {text:e.textContent.slice(0,80), chain, ownKeys:Object.keys(e).filter(k=>/react/i.test(k))};
  });
});
console.log(JSON.stringify(r,null,1).slice(0,3000));
await browser.close();
