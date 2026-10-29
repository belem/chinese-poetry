import { chromium } from 'playwright';
const b = await chromium.launch();
const c = await b.newContext({locale:'zh-CN'});
const p = await c.newPage();
await p.goto('https://www.shidianguji.com/zh/book/K1261', {waitUntil:'domcontentloaded'});
await p.waitForTimeout(5000);
// 点开目录
for (const sel of ['text=目录','[class*=catalog]','[class*=chapter]']) {
  try { await p.click(sel, {timeout:3000}); console.log('clicked', sel); break; } catch(e) { console.log('miss', sel); }
}
await p.waitForTimeout(3000);
const links = await p.evaluate(()=>Array.from(document.querySelectorAll('a')).map(a=>a.getAttribute('href')).filter(h=>h&&h.includes('/chapter/')));
console.log('chapter links', links.length, links.slice(0,5));
const t = await p.evaluate(()=>document.body.innerText.slice(0,600));
console.log(t);
await b.close();
