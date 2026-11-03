// 逐章节取渲染后的 <article class="chapter-reader"> HTML（正文已按页面段落拼好，h3/h4/h5 是层级标题）。
//   node fetch_dom_chapters.mjs <bookId> <outDir> [--delay 1200] [--limit N]
// 产出 outDir/ch-<chapterId>.html；已存在即跳过，可中断续跑。
import fs from 'node:fs';
import path from 'node:path';
import { chromium } from 'playwright';

const args = process.argv.slice(2);
const opt = (n, d) => { const i = args.indexOf(n); return i >= 0 ? args[i + 1] : d; };
const pos = args.filter((a, i) => !a.startsWith('--') && !(i > 0 && args[i - 1].startsWith('--')));
const [book, outDir] = pos;
const delay = Number(opt('--delay', 1200));
const limit = Number(opt('--limit', 0));
const UA = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36';
fs.mkdirSync(outDir, { recursive: true });

const catalog = JSON.parse(fs.readFileSync(path.join(outDir, 'catalog.json'), 'utf8')).chapters;
let todo = catalog.filter(c => !fs.existsSync(path.join(outDir, `ch-${c.chapterId}.html`)));
if (limit > 0) todo = todo.slice(0, limit);
console.log(`${catalog.length} chapters, fetching ${todo.length}`);

const b = await chromium.launch();
const ctx = await b.newContext({ locale: 'zh-CN', userAgent: UA });
let p = await ctx.newPage();
let n = 0, fails = [];
for (const c of todo) {
  let ok = false;
  for (let a = 0; a < 3 && !ok; a++) {
    try {
      if (p.isClosed()) p = await ctx.newPage();
      await p.goto(`https://www.shidianguji.com/zh/book/${book}/chapter/${c.chapterId}`, { waitUntil: 'domcontentloaded', timeout: 45000 });
      await p.waitForFunction(() => document.querySelector('article.chapter-reader, article'), null, { timeout: 20000 }).catch(() => {});
      await p.waitForTimeout(500);
      const html = await p.evaluate(() => {
        const a = document.querySelector('article.chapter-reader') || document.querySelector('article');
        if (!a) return '';
        a.querySelector('footer')?.remove();
        return a.innerHTML;
      });
      if (html.length < 20) throw new Error('empty article');
      fs.writeFileSync(path.join(outDir, `ch-${c.chapterId}.html`), html);
      ok = true;
    } catch (e) {
      console.log('retry', c.chapterId, e.message.slice(0, 60));
      await p.close().catch(() => {}); p = await ctx.newPage();
      await p.waitForTimeout(3000);
    }
  }
  if (!ok) fails.push(c.chapterId);
  if (++n % 20 === 0) console.log(n, '/', todo.length, 'fails', fails.length);
  await p.waitForTimeout(delay);
}
console.log('done, fails:', fails.join(','));
await b.close();
