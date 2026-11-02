// 输出识典某本书的篇目目录（chapterId + name），供后续抓取
//   node toc2.mjs <bookId> <out.json>
import fs from 'node:fs';
import { chromium } from 'playwright';
const [book, out] = process.argv.slice(2);
const BASE = 'https://www.shidianguji.com/zh/book/';
const browser = await chromium.launch();
const ctx = await browser.newContext({ locale:'zh-CN', userAgent:'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36'});
const page = await ctx.newPage();
await page.goto(BASE + book, { waitUntil:'domcontentloaded', timeout:60000 });
await page.waitForTimeout(4000);
let html = await page.content();
let chs = [...html.matchAll(/"chapterId":"([a-z0-9]+)","chapterType":1,"chapterDetailType":3,"chapterLevel":(\d+),"chapterName":\[\{"content":"([^"]*)"/g)]
  .map(m=>({id:m[1], level:+m[2], name:m[3]}));
if (!chs.length) {
  // 兜底：点开目录树再取
  await page.evaluate(()=>{ document.querySelectorAll('div,span,li').forEach(e=>{ if(/^目\s*录$/.test((e.innerText||'').trim()) && e.click) e.click(); }); });
  await page.waitForTimeout(3000);
  html = await page.content();
  chs = [...html.matchAll(/"chapterId":"([a-z0-9]+)","chapterType":1,"chapterDetailType":3,"chapterLevel":(\d+),"chapterName":\[\{"content":"([^"]*)"/g)]
    .map(m=>({id:m[1], level:+m[2], name:m[3]}));
}
const seen=new Set(); chs=chs.filter(c=>{ if(seen.has(c.id))return false; seen.add(c.id); return true; });
fs.writeFileSync(out, JSON.stringify(chs,null,1));
console.log(book, chs.length, 'chapters');
console.log(chs.slice(0,10).map(c=>`${c.level} ${c.id} ${c.name}`).join('\n'));
await browser.close();
