import { chromium } from 'playwright';
const b = await chromium.launch();
const p = await (await b.newContext({locale:'zh-CN', userAgent:'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36'})).newPage();
await p.goto('https://www.shidianguji.com/zh/book/SBCK309/chapter/SBCK309_366', {waitUntil:'domcontentloaded', timeout:60000});
await p.waitForTimeout(7000);
const r = await p.evaluate(()=>{
  const a=document.querySelector('article'); if(!a) return 'none';
  return {len:a.innerHTML.length, heads:[...a.querySelectorAll('h3,h4,h5,h6')].map(x=>x.tagName+':'+x.innerText.trim()).slice(0,20), ps:[...a.querySelectorAll('p')].length, text:a.innerText.length};
});
console.log(JSON.stringify(r,null,1).slice(0,1500));
await b.close();
