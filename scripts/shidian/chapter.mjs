// 识典古籍（shidianguji.com）整本抓取：把一本书每个章节的正文落成 JSON。
//
//   node scripts/shidian/chapter.mjs <bookId> <outDir> [--catalog 目次.json] [--limit N] [--delay ms]
//
// 为什么不走检索：章节页 HTML 里内嵌着整章的正文数据（`paragraphList`，每段是一个带 `lineType`
// 的 JSON 串，8=作者 9=题名 1=正文 3=空行），一次请求拿全篇；逐句检索一本 284 首的词选要几千次请求。
//
// 章节 id 从 `anthologies/<选本>.json` 的 `source` 字段拿（形如 `zzm/1kffh2j2cmgbp`），
// 这里只需书 id；已有同名文件的章节会跳过，可中断续跑。
//
// 收录要求：平台方请控制频率（默认每章间隔 2 秒），只抓自己需要的书。
import fs from 'node:fs';
import path from 'node:path';
import { chromium } from 'playwright';

const args = process.argv.slice(2);
const opt = (n, d) => { const i = args.indexOf(n); return i >= 0 ? args[i + 1] : d; };
const positional = args.filter((a, i) => !a.startsWith('--') && !(i > 0 && args[i - 1].startsWith('--')));
const [book, outDir] = positional;
const delay = Number(opt('--delay', 2000));
const limit = Number(opt('--limit', 0));
const catalogArg = opt('--catalog');
if (!book || !outDir) {
  console.error('usage: node chapter.mjs <bookId> <outDir> [--limit N] [--delay ms]');
  process.exit(2);
}
fs.mkdirSync(outDir, { recursive: true });

// 章节 id 的来源：catalog（章节页 HTML 里内嵌整本书的目录，含全部 chapterLevel:3 的章节）
// 或按 `anthologies/<选本>.json` 的 source 顺序（形如 zzm/1kffh2j2cmgbp）。
const BASE = 'https://www.shidianguji.com/zh/book/';
const browser = await chromium.launch();
const ctx = await browser.newContext({ locale: 'zh-CN' });
const page = await ctx.newPage();

let chapters = [];
if (catalogArg) {
  for (const spec of JSON.parse(fs.readFileSync(catalogArg, 'utf8')).entries || []) {
    chapters.push({ id: spec.source.split('/').pop(), name: spec.title || '' });
  }
} else {
  // 先打开任意一章，正文页的 HTML 里带着整本书的目录（chapterLevel 3 = 具体篇目）
  await page.goto(BASE + book, { waitUntil: 'domcontentloaded', timeout: 60000 });
  await page.waitForTimeout(2500);
  const html = await page.content();
  for (const m of html.matchAll(/"chapterId":"([a-z0-9]+)","chapterType":1,"chapterDetailType":3,"chapterLevel":3,"chapterName":\[\{"content":"([^"]*)"/g)) {
    if (!chapters.some(c => c.id === m[1])) chapters.push({ id: m[1], name: m[2] });
  }
  if (!chapters.length) {
    console.error('目录页没带出章节表（纯客户端渲染的书），请用 --catalog 指定目次文件');
    process.exit(1);
  }
}
console.log(`${book}: ${chapters.length} 章`);
const todo = limit > 0 ? chapters.slice(0, limit) : chapters;

let n = 0;
for (const [i, c] of todo.entries()) {
  const fn = path.join(outDir, `${String(i + 1).padStart(3, '0')}.json`);
  if (fs.existsSync(fn)) continue;
  let ok = false;
  for (let attempt = 0; attempt < 3 && !ok; attempt++) {
    try {
      await page.goto(BASE + book + '/chapter/' + c.id, { waitUntil: 'domcontentloaded', timeout: 45000 });
      await page.waitForTimeout(1200);
      const text = await page.evaluate(() => document.body.innerText);
      if (text.includes('页面不存在')) throw new Error('404');
      await page.waitForTimeout(1500);
      // 正文可能只在内嵌数据里（页面渲染报「数据异常」时仍然有），所以认 HTML 不认可见文本
      const html = await page.content();
      if (!html.includes('"paragraphList"')) throw new Error('no paragraphList');
      fs.writeFileSync(fn, html);
      ok = true;
      n++;
    } catch (e) {
      console.log('retry', c.id, e.message);
      await page.waitForTimeout(4000);
    }
  }
  if (!ok) console.log('FAIL', c.id, c.name);
  if (ok && n % 20 === 0) console.log('snapped', i + 1, c.name);
  await page.waitForTimeout(delay);
}
await browser.close();
console.log(`新抓 ${n} 章 → ${outDir}`);
