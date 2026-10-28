// 识典古籍（shidianguji.com）整本书抓取：目录 + 每章 HTML，可中断续跑。
//
//   node scripts/shidian/book.mjs <bookId> <outDir> [--delay ms]
//
// 为什么不走检索：章节页 HTML 里内嵌整章正文（`paragraphList`，逐行带 `lineType`），一次请求拿一整回；
// 逐句检索一部 120 回的小说要上千次请求。目录用页面里的虚拟滚动目录树收集（一次只渲染十几项，
// 需滚到底反复收），比按"上一篇/下一篇"爬更省事，也顺带拿到官方回目名。
//
// 产出：<outDir>/catalog.json（[{index,id,name}]）、<outDir>/<NNN>.html（章节页原文）。
// 已存在的章节文件跳过，重跑即续跑。请控制频率（默认每章间隔 2 秒），只抓自己需要的书。
import fs from 'node:fs';
import path from 'node:path';
import { chromium } from 'playwright';

const args = process.argv.slice(2);
const opt = (n, d) => { const i = args.indexOf(n); return i >= 0 ? args[i + 1] : d; };
const positional = args.filter((a, i) => !a.startsWith('--') && !(i > 0 && args[i - 1].startsWith('--')));
const [book, outDir] = positional;
const delay = Number(opt('--delay', 3000));
if (!book || !outDir) {
  console.error('usage: node book.mjs <bookId> <outDir> [--delay ms]');
  process.exit(2);
}
fs.mkdirSync(outDir, { recursive: true });

const BASE = 'https://www.shidianguji.com/book/';
const browser = await chromium.launch();
const ctx = await browser.newContext({
  locale: 'zh-CN',
  userAgent: 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
});
let page = await ctx.newPage();

// 1. 目录：打开书页，在虚拟滚动目录树里边滚边收
const catalogFile = path.join(outDir, 'catalog.json');
let chapters;
if (fs.existsSync(catalogFile)) {
  chapters = JSON.parse(fs.readFileSync(catalogFile, 'utf8'));
  console.log(`catalog 复用：${chapters.length} 章`);
} else {
  // 目录树一次只渲染十几项（虚拟列表），够不着尾部；改用章节页里的「下一篇」串成链，
  // 回目名取页面内嵌数据里的本篇题名（chapterName）。
  await page.goto(BASE + book, { waitUntil: 'domcontentloaded', timeout: 60000 });
  await page.waitForTimeout(5000);
  const first = await page.evaluate(() => {
    const a = document.querySelector('[class*="tree-option"] a[href*="/chapter/"]');
    return a ? a.href.split('/chapter/')[1] : null;
  });
  if (!first) {
    console.error('书页没有章节目录');
    process.exit(1);
  }
  const seen = new Set();
  chapters = [];
  let cur = first;
  while (cur && !seen.has(cur)) {
    seen.add(cur);
    await page.goto(BASE + book + '/chapter/' + cur, { waitUntil: 'domcontentloaded', timeout: 45000 });
    await page.waitForTimeout(1500);
    const r = await page.evaluate(() => {
      const html = document.documentElement.outerHTML;
      let name = '';
      const m = html.match(/\\"chapterName\\":\\"([^\\"]{1,80})\\"/) ||
                html.match(/<title>([^<]*)<\/title>/);
      if (m) name = m[1];
      const nx = [...document.querySelectorAll('a')].find(a => /下一篇/.test(a.innerText || '') && /\/chapter\//.test(a.href));
      return { name, next: nx ? nx.href.split('/chapter/')[1] : null };
    });
    chapters.push({ id: cur, name: r.name });
    if (chapters.length % 20 === 0) console.log('catalog', chapters.length, r.name);
    cur = r.next;
  }
  fs.writeFileSync(catalogFile, JSON.stringify(chapters, null, 1));
  console.log(`catalog 新建：${chapters.length} 章`);
}
const indexed = chapters.map((c, i) => ({ ...c, index: i + 1 }));

// 2. 抓章节页
let n = 0;
for (const c of indexed) {
  const fn = path.join(outDir, `${String(c.index).padStart(3, '0')}.html`);
  if (fs.existsSync(fn) && fs.statSync(fn).size > 10000) continue;
  let ok = false;
  for (let attempt = 0; attempt < 3 && !ok; attempt++) {
    try {
      if (attempt > 0) {           // 换一张新标签页重试：同一页反复跳转会被限流
        await page.close().catch(() => {});
        page = await ctx.newPage();
      }
      await page.goto(BASE + book + '/chapter/' + c.id, { waitUntil: 'domcontentloaded', timeout: 45000 });
      // 内嵌数据在 HTML 里，等它出现即可，不必等页面渲染完
      await page.waitForFunction(() => document.documentElement.outerHTML.includes('paragraphList'), null, { timeout: 20000 })
        .catch(() => {});
      const html = await page.content();
      if (html.includes('页面不存在') && !html.includes('paragraphList')) throw new Error('404');
      if (!html.includes('paragraphList')) throw new Error('no paragraphList');
      fs.writeFileSync(fn, html);
      ok = true;
      n++;
    } catch (e) {
      console.log('retry', c.id, c.name, String(e.message).slice(0, 120));
      await new Promise(r => setTimeout(r, 5000));
    }
  }
  if (!ok) console.log('FAIL', c.id, c.name);
  if (ok && n % 10 === 0) console.log('snapped', c.index, c.name);
  await new Promise(r => setTimeout(r, delay));
}
await browser.close();
console.log(`新抓 ${n} 章 → ${outDir}`);
