// 抓《古文觀止》識典古籍 SDZJ0641（光緒二十八年善成堂刊本，带注与白话译文）。
//
//   node gwz_fetch.mjs <catalog.json> <out.json> [--delay 2500] [--limit N]
//
// 每篇一请求：章节页会内嵌 paragraphs/v3 响应（正文 + 夹注 + translateContent 逐句白话），
// 直接从网络响应取，比解析 DOM 可靠。产出 {chapterId: {title, para:[{text, notes:[], trans}]}}。
import fs from 'node:fs';
import { chromium } from 'playwright';

const args = process.argv.slice(2);
const opt = (n, d) => { const i = args.indexOf(n); return i >= 0 ? args[i + 1] : d; };
const pos = args.filter((a, i) => !a.startsWith('--') && !(i > 0 && args[i - 1].startsWith('--')));
const [catFile, outFile] = pos;
const delay = Number(opt('--delay', 2500));
const limit = Number(opt('--limit', 0));
const BOOK = 'SDZJ0641';
const BASE = `https://www.shidianguji.com/zh/book/${BOOK}/chapter/`;

const cat = JSON.parse(fs.readFileSync(catFile, 'utf8'));
const done = fs.existsSync(outFile) ? JSON.parse(fs.readFileSync(outFile, 'utf8')) : {};
let todo = cat.filter(c => c.level >= 2 && !done[c.id]);
if (limit > 0) todo = todo.slice(0, limit);
console.log(`${cat.length} chapters, ${Object.keys(done).length} done, fetching ${todo.length}`);

const browser = await chromium.launch();
const ctx = await browser.newContext({
  locale: 'zh-CN', viewport: { width: 1400, height: 1200 },
  userAgent: 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
});
let page = await ctx.newPage();
let n = 0;
for (const c of todo) {
  let ok = false;
  for (let att = 0; att < 3 && !ok; att++) {
    try {
      if (att > 0) { await page.close().catch(() => {}); page = await ctx.newPage(); }
      let body = null;
      const handler = async r => { if (/read\/book\/paragraphs\/v3/.test(r.url())) { try { body = await r.text(); } catch (e) {} } };
      page.on('response', handler);
      await page.goto(BASE + c.id, { waitUntil: 'domcontentloaded', timeout: 60000 });
      for (let i = 0; i < 20 && !body; i++) await page.waitForTimeout(500);
      page.off('response', handler);
      if (!body) throw new Error('no paragraphs response');
      const data = JSON.parse(body).data;
      const paras = [];
      for (const p of data.paragraphs || []) {
        let content = p.content;
        if (typeof content === 'string') { try { content = JSON.parse(content); } catch (e) { continue; } }
        const text = [], notes = [];
        for (const l of content.lines || []) {
          if (l.lineType === 1) text.push(l.content);
          else if (l.lineType === 2) notes.push(l.content);
        }
        const t = text.join('');
        const tc = p.translateContent;
        const trans = tc && tc.sentences ? tc.sentences.map(s => s.content).join('') : '';
        if (!t && !notes.length) continue;
        paras.push({ text: t, notes, trans });
      }
      done[c.id] = { title: c.name, level: c.level, volume: c.volume, paras };
      fs.writeFileSync(outFile, JSON.stringify(done, null, 1));
      ok = true; n++;
      if (n % 10 === 0) console.log('fetched', n, c.name);
    } catch (e) {
      console.log('retry', c.id, c.name, e.message);
      await page.waitForTimeout(5000);
    }
  }
  if (!ok) console.log('FAIL', c.id, c.name);
  await page.waitForTimeout(delay);
}
await browser.close();
console.log('done, total', Object.keys(done).length);
