// 抓《古文觀止》譯文的正确顺序（按正文 logicSentenceId 首次出现顺序）
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
    const handler = async r => { if (/read\/book\/paragraphs\/v3/.test(r.url())) { try { body = await r.text(); } catch (e) {} } };
    page.on('response', handler);
    await page.goto('https://www.shidianguji.com/zh/book/SDZJ0641/chapter/' + c.id, { waitUntil:'domcontentloaded', timeout:60000 });
    for (let i = 0; i < 20 && !body; i++) await page.waitForTimeout(500);
    page.off('response', handler);
    if (!body) throw new Error('no paragraphs');
    const paras = JSON.parse(body).data.paragraphs || [];
    const res = [];
    for (const p of paras) {
      const ct = typeof p.content === 'string' ? JSON.parse(p.content) : p.content;
      const lines = ct?.lines || [];
      const order = [];
      for (const l of lines) if (l.lineType === 1 && l.logicSentenceId && l.logicSentenceId !== '0' && !order.includes(l.logicSentenceId)) order.push(l.logicSentenceId);
      const tc = p.translateContent?.sentences || [];
      const map = new Map(tc.map(s => [s.logicSentenceId, s.content]));
      const trans = order.map(id => map.get(id) || '').join('');
      const extra = tc.filter(s => !order.includes(s.logicSentenceId)).map(s => s.content).join('');
      const notes = lines.filter(l => l.lineType === 2).map(l => l.content);
      res.push({ trans, extra, notes });
    }
    done[c.id] = res;
    fs.writeFileSync(out, JSON.stringify(done, null, 1));
    n++;
    if (n % 20 === 0) console.log('done', n);
  } catch (e) { console.log('ERR', c.id, e.message); }
  await page.waitForTimeout(1200);
}
await browser.close();
console.log('total', Object.keys(done).length);
