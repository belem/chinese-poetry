import { chromium } from 'playwright';
import fs from 'node:fs';
const [url, out] = process.argv.slice(2);
const browser = await chromium.launch();
const ctx = await browser.newContext({ locale:'zh-CN', viewport:{width:1400,height:900}, userAgent:'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36'});
const page = await ctx.newPage();
await page.goto(url, { waitUntil:'domcontentloaded', timeout:60000 });
await page.waitForTimeout(6000);
const r = await page.evaluate(()=>{
  const main = document.querySelector('article.chapter-reader') || document.body;
  const out=[];
  for (const e of main.querySelectorAll('*')) {
    const t=(e.innerText||'').trim();
    if(!t || t.length>2000) continue;
    const kids=[...e.children].filter(c=>(c.innerText||'').trim());
    if (kids.length) continue;
    out.push({tag:e.tagName, cls:typeof e.className==='string'?e.className:'', t});
  }
  return out;
});
fs.writeFileSync(out, JSON.stringify(r,null,1));
console.log((r||[]).slice(0,60).map(x=>`${x.tag}.${x.cls} | ${x.t.slice(0,120)}`).join('\n'));
await browser.close();
