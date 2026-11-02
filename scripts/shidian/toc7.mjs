import { chromium } from 'playwright';
import fs from 'node:fs';
const browser = await chromium.launch();
const ctx = await browser.newContext({ locale:'zh-CN', userAgent:'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36'});
const page = await ctx.newPage();
const cap=[];
page.on('response', async r=>{ const u=r.url(); if(/ancientlib/.test(u) && /(pages|chapter-list|paragraphs)/.test(u)){ try{const t=await r.text(); cap.push({u, t});}catch(e){} } });
await page.goto('https://www.shidianguji.com/zh/book/SDZJ0641/chapter/1kf9lwr20s4yj', { waitUntil:'domcontentloaded', timeout:60000 });
await page.waitForTimeout(6000);
for(const c of cap){ fs.writeFileSync('/tmp/gwz/cap_'+c.u.replace(/[^a-z0-9]/gi,'_').slice(-40)+'.json', c.t); console.log(c.u.split('?')[0], c.t.length); }
await browser.close();
