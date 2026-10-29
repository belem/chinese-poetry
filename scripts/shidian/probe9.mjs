import { chromium } from 'playwright';
const b = await chromium.launch();
const c = await b.newContext({locale:'zh-CN'});
const p = await c.newPage();
const ids = ['1kbj99kpu64ui','1kbj99lgel99v','1kbj99m58p4p5','1kbj99m8sur02','1kbj99n21phyd','1kbj99nxw1tlm','1kbj99kpu6u4q','1kbj99lgellwz'];
for (const id of ids) {
  await p.goto('https://www.shidianguji.com/zh/book/K1261/chapter/'+id, {waitUntil:'domcontentloaded'});
  await p.waitForTimeout(2500);
  const t = await p.evaluate(()=>document.body.innerText);
  const m = t.match(/(御製緣識卷[第一二三四五六七八九十]+)/);
  console.log(id, m? m[1]: '?', t.length);
}
await b.close();
