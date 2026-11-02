import { chromium } from 'playwright';
import fs from 'node:fs';
const [url, out] = process.argv.slice(2);
const browser = await chromium.launch();
const ctx = await browser.newContext({ locale:'zh-CN', viewport:{width:1400,height:1200}, userAgent:'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36'});
const page = await ctx.newPage();
await page.goto(url, { waitUntil:'domcontentloaded', timeout:60000 });
await page.waitForTimeout(6000);
// 滚到底触发全文渲染
for (let i=0;i<30;i++){ await page.mouse.wheel(0, 1500); await page.waitForTimeout(400); }
await page.waitForTimeout(2000);
const info = await page.evaluate(()=>{
  const out=[];
  // 找出所有含「初，鄭武公娶于申」的元素链
  const hit=[...document.querySelectorAll('*')].filter(e=>(e.innerText||'').includes('故名曰寤生。遂惡之'));
  const leafs = hit.filter(e=>!hit.some(o=>o!==e && e.contains(o)));
  for (const e of leafs.slice(0,20)) out.push({tag:e.tagName, cls:e.className, t:e.innerText.trim().slice(0,150)});
  return out;
});
console.log(JSON.stringify(info,null,1));
const art = await page.evaluate(()=>{ const a=document.querySelector('article.chapter-reader'); return a? a.outerHTML.slice(0,20000):'no article'; });
fs.writeFileSync(out, art);
console.log(art.slice(0,1500));
await browser.close();
