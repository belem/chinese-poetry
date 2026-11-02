import { chromium } from 'playwright';
const browser = await chromium.launch();
const ctx = await browser.newContext({ locale:'zh-CN', userAgent:'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36'});
const page = await ctx.newPage();
const cap=[];
page.on('response', async r=>{ const u=r.url(); if(/ancientlib/.test(u)){ try{const t=await r.text(); cap.push({u:u.split('?')[0], status:r.status(), len:t.length, head:t.slice(0,200)});}catch(e){} } });
await page.goto('https://www.shidianguji.com/zh/book/SDZJ0641/chapter/1kf9lwr20s4yj', { waitUntil:'domcontentloaded', timeout:60000 });
await page.waitForTimeout(6000);
const tocText = await page.evaluate(()=>{
  // 目录面板：找包含 '古文觀止卷之一' 和很多 chapter 链接的最小容器
  const as=[...document.querySelectorAll('a[href*="/chapter/"]')];
  return {count: as.length, sample: as.slice(0,5).map(a=>a.getAttribute('href')+' '+a.innerText.trim())};
});
console.log(JSON.stringify(tocText,null,1));
console.log(cap.map(c=>`${c.status} ${c.u} ${c.len}`).join('\n'));
await browser.close();
