import { chromium } from 'playwright';
const b = await chromium.launch();
const c = await b.newContext({locale:'zh-CN'});
const p = await c.newPage();
await p.goto('https://www.shidianguji.com/zh/book/K1261/chapter/1kbj99m8sur02', {waitUntil:'domcontentloaded'});
await p.waitForTimeout(5000);
const h = await p.content();
// 找 卷第一…卷第七 的章节 id
const ids = [...h.matchAll(/chapterId\\?":\\?"([a-z0-9]+)/g)].map(m=>m[1]);
console.log('ids', [...new Set(ids)].slice(0,10));
const nums = [...h.matchAll(/"lineType":4,"content":"[^"]{0,30}/g)].slice(0,12).map(m=>m[0]);
console.log(nums);
const pref = [...h.matchAll(/\\"lineType\\":4,\\"content\\":\\"([^"\\]{0,24})/g)].slice(0,12).map(m=>m[1]);
console.log(pref);
await b.close();
