// SSR 直出（带 __ssrDirect 时 data 里是 chapter-reader 的 HTML）。node fetch_ssr_ch7.mjs <bookId> <outDir> [--delay] [--limit]
import fs from 'node:fs';
import path from 'node:path';
import { chromium } from 'playwright';
const args = process.argv.slice(2);
const opt = (n, d) => { const i = args.indexOf(n); return i >= 0 ? args[i + 1] : d; };
const pos = args.filter((a, i) => !a.startsWith('--') && !(i > 0 && args[i - 1].startsWith('--')));
const [book, outDir] = pos;
const delay = Number(opt('--delay', 1200)), limit = Number(opt('--limit', 0));
fs.mkdirSync(outDir, { recursive: true });
const catalog = JSON.parse(fs.readFileSync(path.join(outDir, 'catalog.json'), 'utf8')).chapters;
let todo = catalog.filter(c => !fs.existsSync(path.join(outDir, `ch7-${c.chapterId}.json`)));
if (limit) todo = todo.slice(0, limit);
console.log(catalog.length, 'chapters, fetching', todo.length);
const b = await chromium.launch();
const ctx = await b.newContext({ locale: 'zh-CN', userAgent: 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36' });
const p = await ctx.newPage();
await p.goto(`https://www.shidianguji.com/zh/book/${book}/chapter/${catalog[3].chapterId}`, { waitUntil: 'domcontentloaded', timeout: 60000 });
await p.waitForTimeout(8000);
let n = 0, fails = [];
for (const c of todo) {
  let ok = false;
  for (let a = 0; a < 3 && !ok; a++) {
    try {
      const j = await p.evaluate(async (u) => { const r = await fetch(u); return JSON.parse(await r.text()); }, `/zh/book/${book}/chapter/${c.chapterId}?__loader=__session%2F%28lang%24%29%2Fbook%2F%24&__ssrDirect=true`);
      if (!j.paragraphList || !j.paragraphList.length) throw new Error('no paragraphList');
      fs.writeFileSync(path.join(outDir, `ch7-${c.chapterId}.json`), JSON.stringify({ chapterId: c.chapterId, volume: j.volume, paragraphList: j.paragraphList }));
      ok = true;
    } catch (e) { console.log('retry', c.chapterId, e.message.slice(0, 50)); await p.waitForTimeout(4000); }
  }
  if (!ok) fails.push(c.chapterId);
  if (++n % 25 === 0) console.log(n, '/', todo.length, 'fails', fails.length);
  await p.waitForTimeout(delay);
}
console.log('fails:', fails.join(','));
await b.close();
