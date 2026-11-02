import { chromium } from 'playwright';
const browser = await chromium.launch();
const ctx = await browser.newContext({ locale:'zh-CN', userAgent:'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36'});
const page = await ctx.newPage();
await page.goto('https://www.shidianguji.com/zh/book/SDZJ0641/chapter/1kf9lwwlsqyaj', { waitUntil:'domcontentloaded', timeout:60000 });
await page.waitForTimeout(5000);
// 逐个点带 data-popupid 的 span，看弹出内容
const res = await page.evaluate(async ()=>{
  const out=[];
  for (const e of document.querySelectorAll('span[data-popupid]')) {
    e.dispatchEvent(new MouseEvent('mouseenter',{bubbles:true}));
    e.dispatchEvent(new MouseEvent('mouseover',{bubbles:true}));
    e.click();
    await new Promise(r=>setTimeout(r,1500));
    out.push({txt:e.innerText, popups:[...document.querySelectorAll('.semi-popover, [class*=popover], [class*=tooltip], [role=tooltip]')].map(p=>p.innerText.slice(0,600))});
  }
  return out;
});
console.log(JSON.stringify(res,null,1).slice(0,3000));
await browser.close();
