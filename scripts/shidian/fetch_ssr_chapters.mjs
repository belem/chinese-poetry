// 用 SSR 直出抓整本书【全部章节】，一次请求一「卷」，响应里 paragraphList 覆盖该卷所有章节。
//   node fetch_ssr_chapters.mjs <bookId> <outDir> [--delay 2500] [--limit N]
// 产出 outDir/catalog.json（章节表）、outDir/vol-<volumeId>.json（该卷 paragraphList）、
// 以及 outDir/html-<volumeId>.html（该卷各章节 article 的 DOM 直出，含 h3/h4/h5/p 的层级与拼接后的正文）。
// 为什么要 HTML：paragraphList 里的 lineType:1 行在引号、专名、夹注处被切碎，拼接规则不公开；
// SSR 响应里 `chapterReadHtml` 字段是已拼接好的 <article>，段落边界即页面上看得见的段落。
import fs from 'node:fs';
import path from 'node:path';
import { chromium } from 'playwright';

const args = process.argv.slice(2);
const opt = (n, d) => { const i = args.indexOf(n); return i >= 0 ? args[i + 1] : d; };
const pos = args.filter((a, i) => !a.startsWith('--') && !(i > 0 && args[i - 1].startsWith('--')));
const [book, outDir] = pos;
const delay = Number(opt('--delay', 2500));
const limit = Number(opt('--limit', 0));
const UA = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36';
fs.mkdirSync(outDir, { recursive: true });

const b = await chromium.launch();
const ctx = await b.newContext({ locale: 'zh-CN', userAgent: UA });
const p = await ctx.newPage();
await p.goto(`https://www.shidianguji.com/zh/book/${book}`, { waitUntil: 'domcontentloaded', timeout: 60000 });
await p.waitForTimeout(6000);
const ssr = async (cid) => {
  const u = `/zh/book/${book}/chapter/${cid}?__loader=__session%2F%28lang%24%29%2Fbook%2F%24&__ssrDirect=true`;
  const r = await p.evaluate(async (x) => { const res = await fetch(x); return await res.text(); }, u);
  return JSON.parse(r);
};

const catFile = path.join(outDir, 'catalog.json');
let catalog;
if (fs.existsSync(catFile)) catalog = JSON.parse(fs.readFileSync(catFile, 'utf8'));
else {
  const j = await ssr('SBCK309_1');
  catalog = { bookInfo: { bookId: j.bookInfo.bookId, bookName: j.bookInfo.bookName, authors: j.bookInfo.authors, abstract: j.bookInfo.abstract }, chapters: j.bookInfo.catalog.chapters };
  fs.writeFileSync(catFile, JSON.stringify(catalog, null, 1));
}
console.log('chapters', catalog.chapters.length);

const vols = []; const byVol = new Map();
for (const c of catalog.chapters) {
  if (!byVol.has(c.volumeId)) { byVol.set(c.volumeId, []); vols.push(c.volumeId); }
  byVol.get(c.volumeId).push(c.chapterId);
}
let todo = vols.filter(v => !fs.existsSync(path.join(outDir, `vol-${v}.json`)));
if (limit > 0) todo = todo.slice(0, limit);
console.log(`${vols.length} volumes, ${vols.length - todo.length} done, fetching ${todo.length}`);

let n = 0;
for (const v of todo) {
  const cid = byVol.get(v)[0];
  let ok = false;
  for (let a = 0; a < 3 && !ok; a++) {
    try {
      const j = await ssr(cid);
      if (!j.paragraphList) throw new Error('no paragraphList');
      fs.writeFileSync(path.join(outDir, `vol-${v}.json`), JSON.stringify({ chapterId: cid, chapters: byVol.get(v), paragraphList: j.paragraphList }));
      const html = {};
      for (const k of Object.keys(j)) if (/html/i.test(k)) html[k] = j[k];
      html.chapterId = cid;
      fs.writeFileSync(path.join(outDir, `html-${v}.json`), JSON.stringify(html));
      ok = true;
    } catch (e) { console.log('retry', cid, e.message); await p.waitForTimeout(4000); }
  }
  if (++n % 10 === 0 || !ok) console.log(n, '/', todo.length, ok ? 'ok' : 'FAIL');
  await p.waitForTimeout(delay);
}
await b.close();
