// 补抓：正文段落取自 DOM（内嵌数据渲染不完整时用），译文仍取网络响应
import fs from 'node:fs';
import { chromium } from 'playwright';
const cat = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
const out = process.argv[3];
const done = fs.existsSync(out) ? JSON.parse(fs.readFileSync(out, 'utf8')) : {};
const browser = await chromium.launch();
const ctx = await browser.newContext({ locale:'zh-CN', viewport:{width:1400,height:1200}, userAgent:'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36' });
const page = await ctx.newPage();
for (const c of cat) {
  const cur = done[c.id];
  if (Array.isArray(cur) && cur.length) continue;
  try {
    await page.goto('https://www.shidianguji.com/zh/book/SDZJ0641/chapter/' + c.id, { waitUntil:'domcontentloaded', timeout:60000 });
    await page.waitForTimeout(7000);
    const r = await page.evaluate(() => {
      const art = document.querySelector('article.chapter-reader');
      if (!art) return null;
      return [...art.children].filter(e => e.tagName === 'P').map(p => (p.innerText || '').trim());
    });
    if (r && r.length) { done[c.id] = r; fs.writeFileSync(out, JSON.stringify(done)); console.log('ok', c.name, r.length); }
  } catch (e) { console.log('ERR', c.id, e.message); }
  await page.waitForTimeout(1000);
}
await browser.close();
