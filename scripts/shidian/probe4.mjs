import { chromium } from 'playwright';
const browser = await chromium.launch();
const ctx = await browser.newContext({ locale:'zh-CN', userAgent:'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36'});
const page = await ctx.newPage();
const qs = process.argv.slice(2);
for (const q of qs) {
  await page.goto('https://www.shidianguji.com/zh/search/' + encodeURIComponent(q), {waitUntil:'domcontentloaded', timeout:60000});
  await page.waitForTimeout(5000);
  const info = await page.evaluate(()=>{
    const out=[];
    document.querySelectorAll('a[href*="/chapter/"]').forEach(a=>{
      let p=a, txt='';
      for(let i=0;i<5&&p;i++){ p=p.parentElement; if(p && p.innerText) { txt=p.innerText.replace(/\s+/g,' ').slice(0,220); if(txt.length>40) break; } }
      out.push({href:a.getAttribute('href'), txt});
    });
    return out;
  });
  console.log('### QUERY', q);
  for (const x of info) console.log(x.href, '|', x.txt);
}
await browser.close();
