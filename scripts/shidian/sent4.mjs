import { chromium } from 'playwright';
import fs from 'node:fs';
const [url, out] = process.argv.slice(2);
const browser = await chromium.launch();
const ctx = await browser.newContext({ locale:'zh-CN', viewport:{width:1400,height:1200}, userAgent:'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36'});
const page = await ctx.newPage();
await page.goto(url, { waitUntil:'domcontentloaded', timeout:60000 });
await page.waitForTimeout(7000);
await page.screenshot({path:'/tmp/gwz/s3.png'});
const info = await page.evaluate(()=>{
  const all=[...document.querySelectorAll('*')];
  const hit=all.filter(e=>(e.textContent||'').includes('故名曰寤生'));
  return {count:hit.length, chain: hit.slice(-4).map(e=>({tag:e.tagName,cls:typeof e.className==='string'?e.className:'',html:e.outerHTML.slice(0,400)}))};
});
console.log(JSON.stringify(info,null,1).slice(0,3000));
await browser.close();
