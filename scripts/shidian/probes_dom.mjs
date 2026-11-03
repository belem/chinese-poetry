import fs from 'node:fs';
import { chromium } from 'playwright';
const b = await chromium.launch();
const ctx = await b.newContext({locale:'zh-CN', userAgent:'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36'});
const p = await ctx.newPage();
for (const cid of ['SBCK309_6','SBCK309_5']) {
  await p.goto('https://www.shidianguji.com/zh/book/SBCK309/chapter/'+cid, {waitUntil:'domcontentloaded', timeout:60000});
  await p.waitForTimeout(6000);
  const html = await p.evaluate(()=>{
    const a = document.querySelector('article') || document.body;
    return a.outerHTML.slice(0, 6000);
  });
  console.log('=====', cid);
  console.log(html);
}
await b.close();
