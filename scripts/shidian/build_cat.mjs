// 从书页目录树里取起点，再顺每章的「下一篇」链把整本书的章节 id 串齐。
// 识典的目录树是虚拟列表，一次只渲染十几项，滚到底也只多几项；「下一篇」是可靠的线性通道。
//   node build_cat.mjs <bookId> <out.json> [--start <chapterId>]
import fs from 'node:fs';
import { chromium } from 'playwright';

const args = process.argv.slice(2);
const opt = (n, d) => { const i = args.indexOf(n); return i >= 0 ? args[i + 1] : d; };
const positional = args.filter((a, i) => !a.startsWith('--') && !(i > 0 && args[i - 1].startsWith('--')));
const [book, out] = positional;
const start = opt('--start');
const delay = Number(opt('--delay', 800));
const BASE = 'https://www.shidianguji.com/zh/book/';

const browser = await chromium.launch();
const ctx = await browser.newContext({
  locale: 'zh-CN',
  userAgent: 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
});
let page = await ctx.newPage();

let cur = start;
if (!cur) {
  await page.goto(BASE + book, { waitUntil: 'domcontentloaded', timeout: 60000 });
  await page.waitForTimeout(6000);
  cur = await page.evaluate(() => {
    const a = document.querySelector('[class*="tree-option"] a[href*="/chapter/"]');
    return a ? a.href.split('/chapter/')[1] : null;
  });
}
if (!cur) { console.error('no start chapter'); process.exit(1); }

const seen = new Set();
const chapters = [];
while (cur && !seen.has(cur)) {
  seen.add(cur);
  let r = null;
  for (let att = 0; att < 3 && !r; att++) {
    try {
      if (att > 0) { await page.close().catch(() => {}); page = await ctx.newPage(); }
      await page.goto(BASE + book + '/chapter/' + cur, { waitUntil: 'domcontentloaded', timeout: 45000 });
      await page.waitForFunction(() => document.querySelectorAll('p').length > 2, null, { timeout: 15000 }).catch(() => {});
      await page.waitForTimeout(800);
      r = await page.evaluate(() => {
        const h2 = [...document.querySelectorAll('h2')].map(e => e.innerText.trim()).filter(Boolean);
        const ps = [...document.querySelectorAll('p')].map(e => e.innerText.trim()).filter(Boolean);
        const nx = [...new Set([...document.querySelectorAll('a')]
          .filter(a => /下一篇/.test(a.innerText || '') && /\/chapter\//.test(a.href))
          .map(a => a.href.split('/chapter/')[1]))];
        return { h2: h2[0] || '', first: ps[0] || '', next: nx[0] || null };
      });
    } catch (e) { r = null; await new Promise(s => setTimeout(s, 3000)); }
  }
  if (!r) { console.log('FAIL at', cur); break; }
  chapters.push({ id: cur, name: r.h2 || r.first.slice(0, 40) });
  if (chapters.length % 20 === 0) console.log('cat', chapters.length, r.h2 || r.first.slice(0, 30));
  cur = r.next;
  await new Promise(s => setTimeout(s, delay));
}
fs.writeFileSync(out, JSON.stringify(chapters, null, 1));
console.log('total', chapters.length, '→', out);
await browser.close();
