import { chromium } from 'playwright';
const b = await chromium.launch();
const c = await b.newContext({locale:'zh-CN'});
const p = await c.newPage();
// 从搜索页拿到全部章节链接
await p.goto('https://www.shidianguji.com/zh/search/'+encodeURIComponent('御製緣識'), {waitUntil:'domcontentloaded'});
await p.waitForTimeout(4000);
const links = await p.evaluate(()=>Array.from(document.querySelectorAll('a')).map(a=>a.getAttribute('href')).filter(h=>h&&h.includes('/book/K1261/chapter/')));
console.log('chapters found on page1:', links.length);
// 打开「书」页拿目录
await p.goto('https://www.shidianguji.com/zh/book/K1261/chapter/'+links[0].split('/').pop(), {waitUntil:'domcontentloaded'});
await p.waitForTimeout(6000);
const html = await p.content();
const m = html.match(/\\?"chapterList\\?":(\[.{0,2000})/);
console.log('chapterList?', !!m);
if (m) console.log(m[1].slice(0,600));
// 试点击目录
const got = await p.evaluate(async ()=>{
  const r = await fetch('/api/book/K1261/catalog').catch(e=>null);
  return r ? r.status : 'no';
});
console.log('api', got);
await b.close();
