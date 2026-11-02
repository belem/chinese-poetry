import { chromium } from 'playwright';
import fs from 'node:fs';
const cat = JSON.parse(fs.readFileSync(process.argv[2],'utf8'));
const out = process.argv[3];
const done = fs.existsSync(out) ? JSON.parse(fs.readFileSync(out,'utf8')) : {};
const browser = await chromium.launch();
const ctx = await browser.newContext({ locale:'zh-CN', viewport:{width:1400,height:1200}, userAgent:'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36'});
const page = await ctx.newPage();
let n=0;
for (const c of cat) {
  if (done[c.id] !== undefined) continue;
  try {
    await page.goto('https://www.shidianguji.com/zh/book/SDZJ0641/chapter/'+c.id, { waitUntil:'domcontentloaded', timeout:60000 });
    await page.waitForTimeout(6000);
    const r = await page.evaluate(()=>{
      const art=document.querySelector('article.chapter-reader');
      if(!art) return {h3:[], h4:[]};
      return {h3:[...art.children].filter(e=>e.tagName==='H3').map(e=>(e.textContent||'').trim()),
              h4:[...art.children].filter(e=>e.tagName==='H4').map(e=>(e.textContent||'').trim())};
    });
    done[c.id] = r;
    if (r.h3.length>1 || r.h4.length) console.log('MERGE?', c.name, JSON.stringify(r));
    fs.writeFileSync(out, JSON.stringify(done,null,1));
  } catch(e) { console.log('ERR', c.id, e.message); }
  n++;
  if (n%20===0) console.log('scanned', n);
  await page.waitForTimeout(1200);
}
await browser.close();
console.log('scanned total', Object.keys(done).length);
