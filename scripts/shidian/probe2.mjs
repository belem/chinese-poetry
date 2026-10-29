import { chromium } from 'playwright';
const b = await chromium.launch();
const c = await b.newContext({locale:'zh-CN'});
const p = await c.newPage();
await p.goto('https://www.shidianguji.com/zh/search/' + encodeURIComponent('御製緣識'), {waitUntil:'domcontentloaded'});
await p.waitForTimeout(4000);
const links = await p.evaluate(()=>Array.from(document.querySelectorAll('a')).map(a=>[a.getAttribute('href'), a.innerText.trim().slice(0,30)]).filter(x=>x[0]).slice(0,60));
console.log(JSON.stringify(links,null,1));
await b.close();
