// 逐章节取渲染后的 <article> HTML。渲染层已把底本的异体字（朙/𦶎/髙）归一到通行繁体，
// 与库内口径一致；SSR paragraphList 保留底本原字形，只作校字参考。
//   node fetch_dom2.mjs <bookId> <outDir> [--delay 1000]
import fs from 'node:fs';
import path from 'node:path';
import { chromium } from 'playwright';
const args = process.argv.slice(2);
const opt = (n, d) => { const i = args.indexOf(n); return i >= 0 ? args[i + 1] : d; };
const pos = args.filter((a, i) => !a.startsWith('--') && !(i > 0 && args[i - 1].startsWith('--')));
const [book, outDir] = pos;
const delay = Number(opt('--delay', 1000));
fs.mkdirSync(outDir, { recursive: true });
const chapters = JSON.parse(fs.readFileSync(path.join(outDir, 'catalog.json'), 'utf8')).chapters;
const todo = chapters.filter(c => !fs.existsSync(path.join(outDir, `dom-${c.chapterId}.html`)));
console.log(chapters.length, 'chapters, todo', todo.length);
const b = await chromium.launch();
let ctx = await b.newContext({ locale: 'zh-CN', userAgent: 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36' });
let p = await ctx.newPage();
let ok = 0, fail = [];
for (const c of todo) {
  let done = false;
  for (let a = 0; a < 3 && !done; a++) {
    try {
      if (p.isClosed()) p = await ctx.newPage();
      await p.goto(`https://www.shidianguji.com/zh/book/${book}/chapter/${c.chapterId}`, { waitUntil: 'domcontentloaded', timeout: 45000 });
      await p.waitForFunction(() => (document.querySelector('article')?.innerHTML || '').length > 50, null, { timeout: 25000 }).catch(() => {});
      const html = await p.evaluate(() => {
        const a = document.querySelector('article.chapter-reader') || document.querySelector('article');
        if (!a) return '';
        a.querySelector('footer')?.remove();
        return a.innerHTML;
      });
      if (html.length < 50) throw new Error('empty');
      fs.writeFileSync(path.join(outDir, `dom-${c.chapterId}.html`), html);
      done = true; ok++;
    } catch (e) { await p.close().catch(() => {}); p = await ctx.newPage(); await p.waitForTimeout(3000); }
  }
  if (!done) fail.push(c.chapterId);
  if ((ok + fail.length) % 20 === 0) console.log(ok + fail.length, '/', todo.length);
  await p.waitForTimeout(delay);
}
console.log('ok', ok, 'fail', fail.length, fail.join(','));
await b.close();
