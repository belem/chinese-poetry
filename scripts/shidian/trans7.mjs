import { chromium } from 'playwright';
import fs from 'node:fs';
const browser = await chromium.launch();
const ctx = await browser.newContext({ locale:'zh-CN', userAgent:'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36'});
const page = await ctx.newPage();
await page.goto('https://www.shidianguji.com/zh/book/SDZJ0641/chapter/1kf9lwwlsqyaj', { waitUntil:'domcontentloaded', timeout:60000 });
await page.waitForTimeout(5000);
await page.screenshot({path:'/tmp/gwz/shot1.png'});
// 找「译文」的 bounding box
const boxes = await page.evaluate(()=>[...document.querySelectorAll('*')].filter(e=>e.children.length===0 && e.innerText && /译文/.test(e.innerText)).map(e=>{const r=e.getBoundingClientRect(); return {t:e.innerText.trim(), x:r.x, y:r.y, w:r.width, h:r.height};}));
console.log(JSON.stringify(boxes));
const b = boxes.find(b=>b.t==='译文' && b.y<200);
if (b) { await page.mouse.move(b.x+b.w/2, b.y+b.h/2); await page.waitForTimeout(2500); await page.screenshot({path:'/tmp/gwz/shot2.png'}); }
const txt = await page.evaluate(()=>document.body.innerText);
fs.writeFileSync('/tmp/gwz/trans_try.txt', txt);
console.log(txt.length);
await browser.close();
