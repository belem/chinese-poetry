// 书页目录树 → [{index,id,name,anchor}]。虚拟列表一次只渲染十几项，所以边滚边收。
//   node toc.mjs <bookId> <out.json>
import fs from 'node:fs';
import { chromium } from 'playwright';

const [book, out] = process.argv.slice(2);
if (!book || !out) { console.error('usage: node toc.mjs <bookId> <out.json>'); process.exit(2); }

const browser = await chromium.launch();
const ctx = await browser.newContext({
  locale: 'zh-CN',
  userAgent: 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
});
const page = await ctx.newPage();
await page.goto('https://www.shidianguji.com/zh/book/' + book, { waitUntil: 'domcontentloaded', timeout: 60000 });
await page.waitForFunction(() => document.querySelectorAll('[class*="tree-option"]').length > 0, null, { timeout: 30000 }).catch(() => {});
await page.waitForTimeout(3000);

// 只认 a 自己承载的那一条：祖先/兄弟节点的 innerText 会把整段目录串起来
const grab = () => page.evaluate(() => [...document.querySelectorAll('a[href*="/chapter/"]')].map(a => {
  const box = a.querySelector('[class*="fullLabel"]') || a;
  return {
    id: a.getAttribute('href').split('/chapter/')[1],
    name: (box.innerText || '').replace(/\s+/g, ' ').trim(),
    menu: /(^|\s)label(\s|$)/.test(a.parentElement?.className || ''),
  };
})).then(l => l.filter(c => c.menu));

const map = new Map();
const absorb = list => { for (const c of list) if (c.id && !map.has(c.id)) map.set(c.id, c); };

absorb(await grab());
// 目录容器是虚拟滚动区，滚到底再滚一次，直到条目数不再增长
const scroller = await page.evaluateHandle(() => {
  const el = document.querySelector('[class*="tree-option"]');
  let n = el;
  while (n && !(n.scrollHeight > n.clientHeight + 10)) n = n.parentElement;
  return n || document.scrollingElement;
});
let last = 0, stable = 0;
while (stable < 4) {
  await page.evaluate(h => { h.scrollTop = h.scrollHeight; }, scroller);
  await page.waitForTimeout(900);
  absorb(await grab());
  if (map.size === last) stable++; else { stable = 0; last = map.size; }
  if (map.size > 4000) break;
}
const list = [...map.values()].map((c, i) => ({ index: i + 1, id: c.id, name: c.name }));
fs.writeFileSync(out, JSON.stringify(list, null, 1));
console.log('toc', book, list.length);
await browser.close();
