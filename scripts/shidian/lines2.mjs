// 逐行抓《古文觀止》正文行（lineType=1 是正文，2/9 等是夹注、题名、作者），保留原文行序
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
  let body = null;
  try {
    const h = async r => { if (/read\/book\/paragraphs\/v3/.test(r.url())) { try { body = await r.text(); } catch (e) {} } };
    page.on('response', h);
    await page.goto('https://www.shidianguji.com/zh/book/SDZJ0641/chapter/' + c.id, { waitUntil:'domcontentloaded', timeout:60000 });
    for (let i = 0; i < 20 && !body; i++) await page.waitForTimeout(500);
    page.off('response', h);
    if (!body) throw new Error('no paragraphs');
    const paras = JSON.parse(body).data.paragraphs || [];
    const res = paras.map(p => {
      const ct = typeof p.content === 'string' ? JSON.parse(p.content) : p.content;
      return (ct?.lines || []).map(l => ({ t: l.lineType, c: l.content }));
    });
    done[c.id] = res;
    fs.writeFileSync(out, JSON.stringify(done));
    n++;
    if (n % 25 === 0) console.log('done', n);
  } catch (e) { console.log('ERR', c.id, e.message); }
  await page.waitForTimeout(1100);
}
await browser.close();
console.log('total', Object.keys(done).length);
