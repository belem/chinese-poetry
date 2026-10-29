import { chromium } from 'playwright';
const b = await chromium.launch();
const c = await b.newContext({locale:'zh-CN'});
const p = await c.newPage();
await p.goto('https://www.shidianguji.com/zh/book/K1261/chapter/1kbj99m8sur02', {waitUntil:'domcontentloaded'});
await p.waitForTimeout(4000);
const res = await p.evaluate(async ()=>{
  const out = {};
  for (const u of ['/api/book/K1261/catalog','/api/book/K1261','/api/book/K1261/chapter/1kbj99m8sur02']) {
    try { const r = await fetch(u); out[u] = [r.status, (await r.text()).slice(0,200)]; } catch(e) { out[u]='err'; }
  }
  return out;
});
console.log(JSON.stringify(res,null,1).slice(0,1500));
await b.close();
