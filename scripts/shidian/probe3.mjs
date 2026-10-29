import { chromium } from 'playwright';
const b = await chromium.launch();
const c = await b.newContext({locale:'zh-CN'});
const p = await c.newPage();
for (const url of ['https://www.shidianguji.com/zh/book/K1261','https://www.shidianguji.com/zh/book/K1261/chapter/1kbj99m8sur02']) {
  await p.goto(url, {waitUntil:'domcontentloaded'});
  await p.waitForTimeout(4000);
  const t = await p.evaluate(()=>document.body.innerText);
  console.log('=====', url);
  console.log(t.slice(0,800));
}
await b.close();
