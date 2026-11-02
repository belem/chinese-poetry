import { chromium } from 'playwright';
const [url] = process.argv.slice(2);
const browser = await chromium.launch();
const ctx = await browser.newContext({ locale:'zh-CN', viewport:{width:1400,height:1200}, userAgent:'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36'});
const page = await ctx.newPage();
await page.goto(url, { waitUntil:'domcontentloaded', timeout:60000 });
await page.waitForTimeout(7000);
const r = await page.evaluate(()=>{
  const p=[...document.querySelectorAll('p')].find(x=>(x.textContent||'').includes('故名曰寤生'));
  const k=Object.keys(p).find(k=>k.startsWith('__reactProps'));
  const kids=p[k].children?.props?.children || [];
  return kids.map(c=>({key:c.key, data:c.props?.data, sm:c.props?.simplifiedMode, pk:Object.keys(c.props||{})}));
});
console.log(JSON.stringify(r,null,1).slice(0,3000));
await browser.close();
