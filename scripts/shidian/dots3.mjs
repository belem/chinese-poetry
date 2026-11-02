import fs from 'node:fs';
import { chromium } from 'playwright';
const [id, out] = process.argv.slice(2);
const browser = await chromium.launch();
const ctx = await browser.newContext({ locale:'zh-CN', viewport:{width:1400,height:1200}, userAgent:'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36' });
const page = await ctx.newPage();
await page.goto('https://www.shidianguji.com/zh/book/SDZJ0641/chapter/'+id, { waitUntil:'domcontentloaded', timeout:60000 });
await page.waitForTimeout(8000);
const r = await page.evaluate(() => {
  const art = document.querySelector('article.chapter-reader');
  return [...art.children].filter(e => e.tagName === 'P').map(p => (p.innerText || '').trim());
});
const d = JSON.parse(fs.readFileSync(out, 'utf8'));
d[id] = r;
fs.writeFileSync(out, JSON.stringify(d));
console.log(r.length, r.map(x=>x.slice(0,30)));
await browser.close();
