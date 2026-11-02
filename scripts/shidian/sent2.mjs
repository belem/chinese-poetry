import { chromium } from 'playwright';
import fs from 'node:fs';
const [url, out] = process.argv.slice(2);
const browser = await chromium.launch();
const ctx = await browser.newContext({ locale:'zh-CN', viewport:{width:1400,height:900}, userAgent:'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36'});
const page = await ctx.newPage();
await page.goto(url, { waitUntil:'domcontentloaded', timeout:60000 });
await page.waitForTimeout(6000);
const html = await page.evaluate(()=>{
  const ps=[...document.querySelectorAll('p.i4upjN9E')];
  return ps.slice(0,2).map(p=>p.outerHTML);
});
fs.writeFileSync(out, html.join('\n\n'));
console.log(html[0].slice(0,3000));
await browser.close();
