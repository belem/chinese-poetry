// 逐章节抓渲染层文本（<article> 里的 h/p 序列），用于把异体字归一到通行繁体。
//   node fetch_dom_lite.mjs <bookId> <outDir> [--delay 400]
import fs from 'node:fs';
import path from 'node:path';
import { chromium } from 'playwright';
const args = process.argv.slice(2);
const opt = (n, d) => { const i = args.indexOf(n); return i >= 0 ? args[i + 1] : d; };
const pos = args.filter((a, i) => !a.startsWith('--') && !(i > 0 && args[i - 1].startsWith('--')));
const [book, outDir] = pos;
const delay = Number(opt('--delay', 400));
const cat = JSON.parse(fs.readFileSync(path.join(outDir, 'catalog_full.json'), 'utf8'));
const todo = cat.filter(c => c.hasMainContent && !fs.existsSync(path.join(outDir, `dom-${c.chapterId}.html`)));
console.log(cat.length, 'nodes, todo', todo.length);
const b = await chromium.launch();
const ctx = await b.newContext({ locale: 'zh-CN', userAgent: 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36' });
const p = await ctx.newPage();
let ok = 0; const fail = [];
for (const c of todo) {
  let done = false;
  for (let a = 0; a < 3 && !done; a++) {
    try {
      await p.goto(`https://www.shidianguji.com/zh/book/${book}/chapter/${c.chapterId}`, { waitUntil: 'domcontentloaded', timeout: 45000 });
      await p.waitForFunction(() => (document.querySelector('article')?.innerHTML || '').length > 40, null, { timeout: 20000 }).catch(() => {});
      const html = await p.evaluate(() => {
        const a = document.querySelector('article.chapter-reader') || document.querySelector('article');
        if (!a) return '';
        a.querySelector('footer')?.remove();
        return a.innerHTML;
      });
      if (html.length < 40) throw new Error('empty');
      fs.writeFileSync(path.join(outDir, `dom-${c.chapterId}.html`), html);
      done = true; ok++;
    } catch (e) { await p.waitForTimeout(2500); }
  }
  if (!done) fail.push(c.chapterId);
  if ((ok + fail.length) % 100 === 0) console.log(ok + fail.length, '/', todo.length);
  await p.waitForTimeout(delay);
}
console.log('ok', ok, 'fail', fail.length, fail.slice(0,8).join(','));
await b.close();
