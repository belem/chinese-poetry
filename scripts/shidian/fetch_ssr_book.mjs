// 用 SSR 直出抓整本书：目录取自 bookInfo.catalog.chapters，正文逐「卷」拉（一次拿到该卷全部章节的段落）。
//   node fetch_ssr_book.mjs <bookId> <outDir> [--delay 2500] [--limit N]
// 产出 outDir/catalog.json、outDir/<volumeId>.json（paragraphList 原样），中断可续跑。
import fs from 'node:fs';
import path from 'node:path';
import { chromium } from 'playwright';

const args = process.argv.slice(2);
const opt = (n, d) => { const i = args.indexOf(n); return i >= 0 ? args[i + 1] : d; };
const pos = args.filter((a, i) => !a.startsWith('--') && !(i > 0 && args[i - 1].startsWith('--')));
const [book, outDir] = pos;
const delay = Number(opt('--delay', 2500));
const limit = Number(opt('--limit', 0));
const BASE = 'https://www.shidianguji.com';
const UA = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36';
fs.mkdirSync(outDir, { recursive: true });

const b = await chromium.launch();
const ctx = await b.newContext({ locale: 'zh-CN', userAgent: UA });
const p = await ctx.newPage();
const ssr = async (chapterId) => {
  const url = `/zh/book/${book}/chapter/${chapterId}?__loader=__session%2F%28lang%24%29%2Fbook%2F%24&__ssrDirect=true`;
  return await p.evaluate(async (u) => {
    const r = await fetch(u);
    return { status: r.status, text: await r.text() };
  }, url);
};

await p.goto(`${BASE}/zh/book/${book}`, { waitUntil: 'domcontentloaded', timeout: 60000 });
await p.waitForTimeout(6000);

const catFile = path.join(outDir, 'catalog.json');
let catalog;
if (fs.existsSync(catFile)) catalog = JSON.parse(fs.readFileSync(catFile, 'utf8'));
else {
  const first = await ssr('SBCK309_1');
  const j = JSON.parse(first.text);
  catalog = { bookInfo: { bookId: j.bookInfo.bookId, bookName: j.bookInfo.bookName, authors: j.bookInfo.authors }, chapters: j.bookInfo.catalog.chapters };
  fs.writeFileSync(catFile, JSON.stringify(catalog, null, 1));
}
console.log('chapters', catalog.chapters.length);

// 按卷分组：volumeId 相同的章节一次请求全拿到
const vols = [];
const byVol = new Map();
for (const c of catalog.chapters) {
  if (!byVol.has(c.volumeId)) { byVol.set(c.volumeId, []); vols.push(c.volumeId); }
  byVol.get(c.volumeId).push(c.chapterId);
}
let todo = vols.filter(v => !fs.existsSync(path.join(outDir, `${v}.json`)));
if (limit > 0) todo = todo.slice(0, limit);
console.log(`${vols.length} volumes, ${vols.length - todo.length} done, fetching ${todo.length}`);

let n = 0;
for (const v of todo) {
  const cid = byVol.get(v)[0];
  let ok = false;
  for (let attempt = 0; attempt < 3 && !ok; attempt++) {
    const r = await ssr(cid);
    try {
      const j = JSON.parse(r.text);
      if (!j.paragraphList) throw new Error('no paragraphList');
      fs.writeFileSync(path.join(outDir, `${v}.json`), JSON.stringify({ chapterId: cid, paragraphList: j.paragraphList }));
      ok = true;
    } catch (e) {
      console.log('retry', cid, e.message);
      await p.waitForTimeout(4000);
    }
  }
  console.log(++n, '/', todo.length, v, ok ? 'ok' : 'FAIL');
  await p.waitForTimeout(delay);
}
await b.close();
