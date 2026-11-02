import { chromium } from 'playwright';
const browser = await chromium.launch();
const ctx = await browser.newContext({ locale:'zh-CN', userAgent:'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36'});
const page = await ctx.newPage();
await page.goto('https://www.shidianguji.com/zh/book/SDZJ0641/chapter/1kf9lwr20s4yj', { waitUntil:'domcontentloaded', timeout:60000 });
await page.waitForTimeout(6000);
// 递归找存有 chapterId 的 JS 对象
const res = await page.evaluate(()=>{
  const found=[];
  const seen=new Set();
  function walk(o, path, depth){
    if(!o||typeof o!=='object'||depth>8||seen.has(o))return; seen.add(o);
    if(Array.isArray(o)){
      if(o.length>50 && o[0] && (o[0].chapterId||o[0].id) && (o[0].chapterName||o[0].name)) found.push({path, len:o.length, sample:o.slice(0,3)});
      o.forEach((v,i)=>walk(v, path+'['+i+']', depth+1));
    } else {
      for(const k in o){ walk(o[k], path+'.'+k, depth+1); }
    }
  }
  // 从 __INITIAL_STATE__ / __NEXT_DATA__ 等全局对象找
  const keys = Object.keys(window).filter(k=>/^__|state|store/i.test(k));
  for(const k of keys){ try{ walk(window[k], k, 0); }catch(e){} }
  return {keys, found: found.map(f=>({path:f.path,len:f.len,sample:JSON.stringify(f.sample).slice(0,300)}))};
});
console.log(JSON.stringify(res,null,1).slice(0,3000));
await browser.close();
