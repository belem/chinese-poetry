import { chromium } from 'playwright';
import fs from 'node:fs';
const browser = await chromium.launch();
const ctx = await browser.newContext({ locale:'zh-CN', userAgent:'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36'});
const page = await ctx.newPage();
const seen = new Set();
page.on('response', async r=>{ const u=r.url(); const k=u.split('?')[0]; if(/chapter-list/.test(u) && !seen.has(k)){ seen.add(k); try{ fs.writeFileSync('/tmp/gwz/cl_'+k.replace(/[^a-z]/gi,'')+'.json', await r.text()); }catch(e){} } });
await page.goto('https://www.shidianguji.com/zh/book/SDZJ0641/chapter/1kf9lwr20s4yj', { waitUntil:'domcontentloaded', timeout:60000 });
await page.waitForTimeout(4000);
// scroll / click volume list
await page.evaluate(()=>{ const as=[...document.querySelectorAll('a[href*="/chapter/"]')].filter(a=>/卷之/.test(a.innerText)); as[as.length-1]?.click(); });
await page.waitForTimeout(3000);
await browser.close();
