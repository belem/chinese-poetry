import { chromium } from 'playwright';
import fs from 'node:fs';
const [url, out] = process.argv.slice(2);
const browser = await chromium.launch();
const ctx = await browser.newContext({ locale:'zh-CN', viewport:{width:1400,height:1200}, userAgent:'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36'});
const page = await ctx.newPage();
await page.goto(url, { waitUntil:'domcontentloaded', timeout:60000 });
await page.waitForTimeout(7000);
const props = await page.evaluate(()=>{
  const p=[...document.querySelectorAll('p')].find(x=>(x.textContent||'').includes('故名曰寤生'));
  const k=Object.keys(p).find(k=>k.startsWith('__reactProps'));
  const pp=Object.keys(p).find(k=>k.startsWith('__reactFiber'));
  const props=p[k], fiber=p[pp];
  return {
    propsKeys: props?Object.keys(props):null,
    propsPreview: JSON.stringify(props).slice(0,800),
    fiberKeys: fiber?Object.keys(fiber):null,
    fiberMemo: JSON.stringify(fiber?.memoizedProps).slice(0,800),
    fiberState: JSON.stringify(fiber?.memoizedState).slice(0,500),
    returnProps: JSON.stringify(fiber?.return?.memoizedProps).slice(0,800),
  };
});
console.log(JSON.stringify(props,null,1).slice(0,4000));
await browser.close();
