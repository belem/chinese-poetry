import { chromium } from 'playwright';
import fs from 'node:fs';
const [url, out] = process.argv.slice(2);
const browser = await chromium.launch();
const ctx = await browser.newContext({ locale:'zh-CN', viewport:{width:1400,height:900}, userAgent:'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36'});
const page = await ctx.newPage();
await page.goto(url, { waitUntil:'domcontentloaded', timeout:60000 });
await page.waitForTimeout(6000);
const r = await page.evaluate(()=>{
  const ps=[...document.querySelectorAll('p.i4upjN9E')];
  return ps.slice(0,2).map(p=>{
    const dump=(e,d=0)=>{
      const t=(e.childNodes.length===0? e.textContent: '').trim();
      const kids=[...e.children].map(c=>dump(c,d+1));
      return {tag:e.tagName, cls:typeof e.className==='string'?e.className:'', attrs:[...e.attributes].map(a=>a.name+'='+a.value.slice(0,40)), text:t, kids};
    };
    return dump(p);
  });
});
fs.writeFileSync(out, JSON.stringify(r,null,1));
console.log(JSON.stringify(r,null,1).slice(0,6000));
await browser.close();
