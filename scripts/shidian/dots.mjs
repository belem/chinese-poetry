// 抓《古文觀止》正文与其译文（不带标点、不含夹注），并从页面取带标点的整理本（若平台提供）
import fs from 'node:fs';
import { chromium } from 'playwright';
const cat = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
const out = process.argv[3];
const done = fs.existsSync(out) ? JSON.parse(fs.readFileSync(out, 'utf8')) : {};
const browser = await chromium.launch();
const ctx = await browser.newContext({ locale:'zh-CN', viewport:{width:1400,height:1200}, userAgent:'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36' });
const page = await ctx.newPage();
let n = 0;
for (const c of cat) {
  if (done[c.id] !== undefined) continue;
  try {
    await page.goto('https://www.shidianguji.com/zh/book/SDZJ0641/chapter/' + c.id, { waitUntil:'domcontentloaded', timeout:60000 });
    await page.waitForTimeout(6000);
    const r = await page.evaluate(() => {
      const art = document.querySelector('article.chapter-reader');
      if (!art) return null;
      const ps = [...art.children].filter(e => e.tagName === 'P');
      return ps.map(p => (p.innerText || '').replace(/[\u200b-\u200f]/g, '').trim());
    });
    done[c.id] = r;
    fs.writeFileSync(out, JSON.stringify(done));
    n++;
    if (n % 25 === 0) console.log('done', n);
  } catch (e) { console.log('ERR', c.id, e.message); }
  await page.waitForTimeout(1100);
}
await browser.close();
console.log('total', Object.keys(done).length);
