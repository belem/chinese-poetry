import { chromium } from 'playwright';
const browser = await chromium.launch();
const ctx = await browser.newContext({ locale:'zh-CN', userAgent:'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36'});
const page = await ctx.newPage();
const cap=[];
page.on('request', r=>{ if(/ancientlib/.test(r.url())) cap.push(r.url().split('?')[0]+' | '+(r.postData()||'').slice(0,200)); });
await page.goto('https://www.shidianguji.com/zh/book/SDZJ0641/chapter/1kf9lwwlsqyaj', { waitUntil:'domcontentloaded', timeout:60000 });
await page.waitForTimeout(5000);
const n0=cap.length;
// hover the 译文 trigger
const el = await page.$('span[data-popupid]');
await el.hover();
await page.waitForTimeout(3500);
console.log('NEW REQ:\n'+[...new Set(cap.slice(n0))].join('\n'));
const txt = await page.evaluate(()=>document.body.innerText);
console.log('TEXT AFTER HOVER:', txt.slice(0,800));
await browser.close();
