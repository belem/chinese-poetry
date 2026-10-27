// 识典古籍整书顺序抓取：从起始章节出发，用「下一篇」逐章走到书末，正文按页缓存到 JSON。
// 目录树是懒加载的、不可靠，用顺序走页拿到的正文段落自己切分章节更稳。
//
//   node scripts/anthology/crawl_book.mjs <bookId> <startChapterId> <outFile> [--limit N] [--delay ms]
//
// 可中断续跑：<outFile> 已存在时从最后一页的「下一篇」继续。
import { chromium } from '../shidian/node_modules/playwright/index.mjs';
import fs from 'node:fs';

const [book, start, out] = process.argv.slice(2).filter((a) => !a.startsWith('--'));
const opt = (n, d) => { const i = process.argv.indexOf(n); return i > 0 ? process.argv[i + 1] : d; };
const limit = Number(opt('--limit', 0));
const delay = Number(opt('--delay', 1500));
const UA = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) '
         + 'Chrome/131.0.0.0 Safari/537.36';

const pages = fs.existsSync(out) ? JSON.parse(fs.readFileSync(out, 'utf8')) : [];
const seen = new Set(pages.map((p) => p.url));
const browser = await chromium.launch();
const ctx = await browser.newContext({ locale: 'zh-CN', userAgent: UA });
const page = await ctx.newPage();

// 先访问一次搜索结果，拿到站点下发的 cookie / verifyFp，否则书籍页会返回「数据异常」
await page.goto('https://www.shidianguji.com/zh/search/' + encodeURIComponent('登鸛鵲樓'), { waitUntil: 'domcontentloaded' });
await page.waitForTimeout(2500);

const nextOf = async () => {
  const before = page.url();
  await page.evaluate(() => {
    const a = Array.from(document.querySelectorAll('a,button')).find((e) => /^下一篇/.test(e.innerText || ''));
    a && a.click();
  });
  await page.waitForTimeout(delay);
  return page.url() === before ? null : page.url();
};

let url = pages.length
  ? await (async () => {
      await page.goto(pages[pages.length - 1].url, { waitUntil: 'domcontentloaded' });
      await page.waitForTimeout(delay);
      return nextOf();
    })()
  : `https://www.shidianguji.com/zh/book/${book}/chapter/${start}`;

let n = 0;
while (url && (!limit || n < limit)) {
  if (seen.has(url)) break;
  await page.goto(url, { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(delay);
  const text = await page.evaluate(() => document.body.innerText);
  const title = await page.evaluate(() => (document.querySelector('h1') || {}).innerText || '');
  pages.push({ url, title: title.trim(), text });
  seen.add(url);
  fs.writeFileSync(out, JSON.stringify(pages));
  if (++n % 10 === 0) console.log(n, url);
  url = await nextOf();
}
if (pages.length) {
  delete pages[pages.length - 1].next;
  fs.writeFileSync(out, JSON.stringify(pages));
}
console.log('pages in cache:', pages.length);
await browser.close();
