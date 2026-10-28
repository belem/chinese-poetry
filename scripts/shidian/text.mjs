// 识典古籍（shidianguji.com）章节页 → 段落文本。
//
//   node scripts/shidian/text.mjs <书id> <catalog.json> <out.json> [--delay ms]
//
// 为什么不解析内嵌的 `paragraphList`：那里的一个 paragraph 常被切成多段（`lineType:1` 的行
// 逐句断在引号、专名、夹注处），拼接规则不公开；而同一份数据渲染成 DOM 后，服务端已经把
// 一行内的碎片接回去了，段落边界就是页面上看得见的段落。所以这里用浏览器取渲染后的 `<p>`。
//
// 目录（章节 id）由 book.mjs 生成；本脚本只负责正文，产出 {章节id: {name, paragraphs}}，
// 已抓过的章节跳过，可中断续跑。
import fs from 'node:fs';
import { chromium } from 'playwright';

const args = process.argv.slice(2);
const opt = (n, d) => { const i = args.indexOf(n); return i >= 0 ? args[i + 1] : d; };
const positional = args.filter((a, i) => !a.startsWith('--') && !(i > 0 && args[i - 1].startsWith('--')));
const [book, catalogFile, outFile] = positional;
const delay = Number(opt('--delay', 1200));
if (!book || !catalogFile || !outFile) {
  console.error('usage: node text.mjs <bookId> <catalog.json> <out.json> [--delay ms]');
  process.exit(2);
}

const catalog = JSON.parse(fs.readFileSync(catalogFile, 'utf8'));
const done = fs.existsSync(outFile) ? JSON.parse(fs.readFileSync(outFile, 'utf8')) : {};
let page = null;
const browser = await chromium.launch();
const ctx = await browser.newContext({
  locale: 'zh-CN',
  userAgent: 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
});
const newPage = async () => { page = await ctx.newPage(); return page; };
await newPage();

const BASE = 'https://www.shidianguji.com/zh/book/';
let n = 0;
for (const [i, c] of catalog.entries()) {
  if (done[c.id]?.paragraphs?.length) continue;
  let ok = false;
  for (let attempt = 0; attempt < 3 && !ok; attempt++) {
    try {
      if (attempt > 0) { await page.close().catch(() => {}); await newPage(); }
      await page.goto(BASE + book + '/chapter/' + c.id, { waitUntil: 'domcontentloaded', timeout: 45000 });
      await page.waitForFunction(() => document.querySelectorAll('p').length > 3, null, { timeout: 20000 }).catch(() => {});
      await page.waitForFunction(() => document.documentElement.outerHTML.includes('read-layout-main'), null, { timeout: 15000 }).catch(() => {});
      const r = await page.evaluate(() => {
        // 正文段落容器：页面上最常见、且承载长文本的那个 class
        const ps = [...document.querySelectorAll('p')].filter(e => {
          const t = (e.innerText || '').trim();
          return t.length > 0 && !/登录后阅读|下载APP|加入书架|随时查阅/.test(t);
        });
        const cnt = {};
        for (const e of ps) if (e.className) cnt[e.className] = (cnt[e.className] || 0) + 1;
        const cls = Object.keys(cnt).sort((a, b) => cnt[b] - cnt[a])[0];
        const nodes = cls ? [...document.querySelectorAll('p')].filter(e => e.className === cls) : [];
        const h2 = document.querySelector('h2');
        // 回目在小标题里；页面偶尔渲染不出 h3，就从内嵌 HTML 的 chapter-reader 里取
        let h3 = document.querySelector('h3');
        if (!h3) {
          const m = document.documentElement.outerHTML.match(/<article class="chapter-reader">[\s\S]*?<h3[^>]*>([^<]*)<\/h3>/);
          if (m) h3 = { innerText: m[1] };
        }
        return {
          name: h2 ? h2.innerText.trim() : '',
          subtitle: h3 ? h3.innerText.trim() : '',
          paragraphs: nodes.map(e => e.innerText.replace(/[ \t]+/g, ' ').replace(/\s*\n\s*/g, '').trim()).filter(Boolean),
        };
      });
      // 插图、空白页之类没有正文的条目：记空数组，不再重试
      if (r.paragraphs.length < 1 && !/插/.test(c.name || '')) throw new Error('empty');
      done[c.id] = { index: i + 1, name: c.name || r.name, subtitle: r.subtitle, paragraphs: r.paragraphs };
      fs.writeFileSync(outFile, JSON.stringify(done, null, 1));
      ok = true;
      n++;
    } catch (e) {
      console.log('retry', c.id, c.name, String(e.message).slice(0, 100));
      await new Promise(r => setTimeout(r, 4000));
    }
  }
  if (!ok) console.log('FAIL', c.id, c.name);
  if (ok && n % 10 === 0) console.log('done', i + 1, '/', catalog.length, c.name);
  await new Promise(r => setTimeout(r, delay));
}
await browser.close();
console.log(`新抓 ${n} 章，共 ${Object.keys(done).length} 章 → ${outFile}`);
