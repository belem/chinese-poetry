import { chromium } from 'playwright';
import fs from 'node:fs';
const browser = await chromium.launch();
const ctx = await browser.newContext({ locale:'zh-CN', userAgent:'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36'});
const page = await ctx.newPage();
const reqs=[];
page.on('request', r=>{ const u=r.url(); if(/ancientlib/.test(u)) reqs.push(u); });
await page.goto('https://www.shidianguji.com/zh/book/SDZJ0641/chapter/1kf9lwr20s4yj', { waitUntil:'domcontentloaded', timeout:60000 });
await page.waitForTimeout(6000);
// 打开目录面板
for (const label of ['目录','目錄']) {
  await page.evaluate((lb)=>{ [...document.querySelectorAll('*')].filter(e=>e.children.length===0 && e.innerText && e.innerText.trim()===lb).forEach(e=>e.click()); }, label);
}
await page.waitForTimeout(4000);
const n = await page.evaluate(()=>document.querySelectorAll('a[href*="/chapter/"]').length);
console.log('chapter links after opening toc:', n);
const items = await page.evaluate(()=>[...document.querySelectorAll('a[href*="/chapter/"]')].map(a=>a.getAttribute('href')+'|'+a.innerText.trim().replace(/\s+/g,' ')).slice(0,40));
console.log(items.join('\n'));
console.log('--- api urls ---\n' + [...new Set(reqs.map(u=>u.split('?')[0]))].join('\n'));
await browser.close();
