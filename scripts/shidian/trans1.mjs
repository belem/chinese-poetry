import { chromium } from 'playwright';
import fs from 'node:fs';
const browser = await chromium.launch();
const ctx = await browser.newContext({ locale:'zh-CN', userAgent:'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36'});
const page = await ctx.newPage();
const cap=[];
page.on('response', async r=>{ const u=r.url(); if(/ancientlib/.test(u) && /(translat|explain|note|word|translate)/i.test(u)) cap.push(u.split('?')[0]); });
await page.goto('https://www.shidianguji.com/zh/book/SDZJ0641/chapter/1kf9lwwlsqyaj', { waitUntil:'domcontentloaded', timeout:60000 });
await page.waitForTimeout(6000);
const before = await page.evaluate(()=>document.body.innerText.length);
// 点「译文」
const clicked = await page.evaluate(()=>{
  const els=[...document.querySelectorAll('*')].filter(e=>e.children.length===0 && /^译文$|^譯文$/.test((e.innerText||'').trim()));
  els.forEach(e=>e.click()); return els.length;
});
await page.waitForTimeout(4000);
const txt = await page.evaluate(()=>document.body.innerText);
console.log('before', before, 'clicked', clicked, 'after', txt.length);
console.log('--- API ---'); console.log([...new Set(cap)].join('\n'));
console.log('--- TEXT ---'); console.log(txt.slice(0, 3500));
await browser.close();
