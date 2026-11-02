import { chromium } from 'playwright';
import fs from 'node:fs';
const [id, out] = process.argv.slice(2);
const browser = await chromium.launch();
const ctx = await browser.newContext({ locale:'zh-CN', viewport:{width:1400,height:1200}, userAgent:'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36'});
const page = await ctx.newPage();
const caps=[];
page.on('response', async r=>{ if(/read\/book\/paragraphs\/v3/.test(r.url())){ try{ caps.push(await r.text()); }catch(e){} } });
await page.goto('https://www.shidianguji.com/zh/book/SDZJ0641/chapter/'+id, { waitUntil:'domcontentloaded', timeout:60000 });
await page.waitForTimeout(9000);
// 滚到底，可能触发后续分页
for (let i=0;i<25;i++){ await page.mouse.wheel(0,1500); await page.waitForTimeout(250); }
await page.waitForTimeout(3000);
fs.writeFileSync(out, JSON.stringify(caps));
console.log('captures', caps.length, caps.map(c=>c.length));
await browser.close();
