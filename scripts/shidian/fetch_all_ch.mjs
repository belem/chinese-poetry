// 按完整目录树（含 subChapters）逐章节抓 SSR paragraphList。
//   node fetch_all_ch.mjs <bookId> <outDir> [--delay 700]
import fs from 'node:fs';
import path from 'node:path';
import { chromium } from 'playwright';
const args = process.argv.slice(2);
const opt = (n, d) => { const i = args.indexOf(n); return i >= 0 ? args[i + 1] : d; };
const pos = args.filter((a, i) => !a.startsWith('--') && !(i > 0 && args[i - 1].startsWith('--')));
const [book, outDir] = pos;
const delay = Number(opt('--delay', 700));
const cat = JSON.parse(fs.readFileSync(path.join(outDir, 'catalog_full.json'), 'utf8'));
const todo = cat.filter(c => c.hasMainContent && !fs.existsSync(path.join(outDir, `ssr-${c.chapterId}.json`)));
console.log(cat.length, 'nodes, todo', todo.length);
const b = await chromium.launch();
const ctx = await b.newContext({ locale: 'zh-CN', userAgent: 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36' });
const p = await ctx.newPage();
await p.goto(`https://www.shidianguji.com/zh/book/${book}`, { waitUntil: 'domcontentloaded', timeout: 60000 });
await p.waitForTimeout(7000);
let ok = 0; const fail = [];
for (const c of todo) {
  let done = false;
  for (let a = 0; a < 3 && !done; a++) {
    try {
      const j = await p.evaluate(async (u) => { const r = await fetch(u); return JSON.parse(await r.text()); },
        `/zh/book/${book}/chapter/${c.chapterId}?__loader=__session%2F%28lang%24%29%2Fbook%2F%24&__ssrDirect=true`);
      if (!j.paragraphList || !j.paragraphList.length) throw new Error('empty');
      fs.writeFileSync(path.join(outDir, `ssr-${c.chapterId}.json`), JSON.stringify({ chapterId: c.chapterId, paragraphList: j.paragraphList }));
      done = true; ok++;
    } catch (e) { await p.waitForTimeout(3000); }
  }
  if (!done) fail.push(c.chapterId);
  if ((ok + fail.length) % 100 === 0) console.log(ok + fail.length, '/', todo.length);
  await p.waitForTimeout(delay);
}
console.log('ok', ok, 'fail', fail.length, fail.slice(0, 10).join(','));
await b.close();
