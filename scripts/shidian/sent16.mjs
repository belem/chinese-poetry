import { chromium } from 'playwright';
const browser = await chromium.launch();
const ctx = await browser.newContext({ locale:'zh-CN', viewport:{width:1400,height:1200}, userAgent:'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36'});
const page = await ctx.newPage();
await page.goto('https://www.shidianguji.com/zh/book/SDZJ0641/chapter/1kf9lwwlsqyaj', { waitUntil:'domcontentloaded', timeout:60000 });
await page.waitForTimeout(8000);
const r = await page.evaluate(()=>{
  // 找「起初」所在元素，沿祖先链看类名
  const walker=document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  const out=[];
  while(walker.nextNode()){
    const t=walker.currentNode.nodeValue||'';
    if(/起初/.test(t)){
      let e=walker.currentNode.parentElement, chain=[];
      for(let i=0;i<6&&e;i++){ chain.push({tag:e.tagName,cls:typeof e.className==='string'?e.className:'',nk:e.children.length}); e=e.parentElement; }
      out.push({text:t.slice(0,60), chain});
    }
  }
  return out.slice(0,3);
});
console.log(JSON.stringify(r,null,1).slice(0,3000));
await browser.close();
