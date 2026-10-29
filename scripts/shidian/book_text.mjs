// 整本书抓正文：目录（toc.mjs 产出）＋ 每章渲染后的段落。
//
//   node book_text.mjs <bookId> <toc.json> <out.json> [--delay ms]
//
// 与 text.mjs 同一取法（渲染后的 <p>，段落边界就是页面上看得见的段落），
// 差别只在目录来源：toc.mjs 直接读页面目录树，不靠「下一篇」串链，续跑按 id 断点。
// 产出 {章节id: {index, name, paragraphs}}，已抓过的跳过。
import fs from 'node:fs';
import { chromium } from 'playwright';

const args = process.argv.slice(2);
const opt = (n, d) => { const i = args.indexOf(n); return i >= 0 ? args[i + 1] : d; };
const pos = args.filter((a, i) => !a.startsWith('--') && !(i > 0 && args[i - 1].startsWith('--')));
const [book, tocFile, outFile] = pos;
const delay = Number(opt('--delay', 1200));
if (!book || !tocFile || !outFile) {
  console.error('usage: node book_text.mjs <bookId> <toc.json> <out.json> [--delay ms]');
  process.exit(2);
}

const toc = JSON.parse(fs.readFileSync(tocFile, 'utf8'));
const done = fs.existsSync(outFile) ? JSON.parse(fs.readFileSync(outFile, 'utf8')) : {};
const BASE = 'https://www.shidianguji.com/zh/book/' + book + '/chapter/';

const browser = await chromium.launch();
const ctx = await browser.newContext({
  locale: 'zh-CN',
  userAgent: 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
});
let page = await ctx.newPage();
let n = 0;
for (const c of toc) {
  if (done[c.id]?.paragraphs?.length) continue;
  let ok = false;
  for (let att = 0; att < 3 && !ok; att++) {
    try {
      if (att > 0) { await page.close().catch(() => {}); page = await ctx.newPage(); }
      await page.goto(BASE + c.id, { waitUntil: 'domcontentloaded', timeout: 45000 });
      await page.waitForFunction(() => document.querySelectorAll('p').length > 3, null, { timeout: 20000 }).catch(() => {});
      await page.waitForTimeout(600);
      const r = await page.evaluate(() => {
        const ps = [...document.querySelectorAll('p')].filter(e => {
          const t = (e.innerText || '').trim();
          return t && !/登录后阅读|下载APP|加入书架|随时查阅/.test(t);
        });
        // 正文容器：页面上段落最多的那个 class
        const cnt = {};
        for (const e of ps) if (e.className) cnt[e.className] = (cnt[e.className] || 0) + 1;
        const cls = Object.keys(cnt).sort((a, b) => cnt[b] - cnt[a])[0];
        const nodes = cls ? ps.filter(e => e.className === cls) : ps;
        return nodes.map(e => e.innerText.replace(/[ \t]+/g, ' ').replace(/\s*\n\s*/g, '').trim()).filter(Boolean);
      });
      if (!r.length) throw new Error('empty');
      done[c.id] = { index: c.index, name: c.name, paragraphs: r };
      fs.writeFileSync(outFile, JSON.stringify(done, null, 1));
      ok = true; n++;
      if (n % 10 === 0) console.log('done', n, c.index, c.name);
    } catch (e) {
      console.log('retry', c.id, c.name, String(e.message).slice(0, 80));
      await new Promise(r => setTimeout(r, 4000));
    }
  }
  if (!ok) console.log('FAIL', c.index, c.id, c.name);
  await new Promise(r => setTimeout(r, delay));
}
console.log('ok', book, Object.keys(done).length, '/', toc.length);
await browser.close();
