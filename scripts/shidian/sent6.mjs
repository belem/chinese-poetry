import { chromium } from 'playwright';
import fs from 'node:fs';
const [url, out] = process.argv.slice(2);
const browser = await chromium.launch();
const ctx = await browser.newContext({ locale:'zh-CN', viewport:{width:1400,height:1200}, userAgent:'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36'});
const page = await ctx.newPage();
await page.goto(url, { waitUntil:'domcontentloaded', timeout:60000 });
await page.waitForTimeout(7000);
const info = await page.evaluate(()=>{
  const first=[...document.querySelectorAll('p')].find(p=>(p.textContent||'').includes('故名曰寤生'));
  const out=[];
  for (const k in first) if (/^__react/.test(k)) out.push(k+' -> '+String(first[k]).slice(0,100));
  // 父元素 & 兄弟
  const sibs=[...(first.parentElement?.children||[])].slice(0,6).map(e=>({tag:e.tagName,cls:e.className,t:(e.textContent||'').slice(0,80)}));
  return {reactKeys: out, parent: first.parentElement.className, sibs, outer: first.parentElement.outerHTML.slice(0,600)};
});
console.log(JSON.stringify(info,null,1).slice(0,4000));
await browser.close();
