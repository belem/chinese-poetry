import { chromium } from 'playwright';
import fs from 'node:fs';
const [book, outDir, ...rest] = process.argv.slice(2);
const opt=(n,d)=>{const i=rest.indexOf(n);return i>=0?rest[i+1]:d};
const delay=Number(opt('--delay',3000));
fs.mkdirSync(outDir,{recursive:true});
const b = await chromium.launch();
const c = await b.newContext({locale:'zh-CN'});
const p = await c.newPage();
await p.goto(`https://www.shidianguji.com/zh/book/${book}/chapter/x`, {waitUntil:'domcontentloaded'}).catch(()=>{});
await p.waitForTimeout(3000);
// 用搜索页拿到该书的章节 id 列表
const search = opt('--search');
await p.goto('https://www.shidianguji.com/zh/search/'+encodeURIComponent(search), {waitUntil:'domcontentloaded'});
await p.waitForTimeout(4000);
let ids = await p.evaluate((book)=>Array.from(document.querySelectorAll('a')).map(a=>a.getAttribute('href')||'').filter(h=>h.includes(`/book/${book}/chapter/`)).map(h=>h.split('/').pop()), book);
ids=[...new Set(ids)];
console.log('seed chapters', ids.length);
const seen=new Set();
const queue=[...ids];
const file=outDir+'/chapters.jsonl';
if (fs.existsSync(file)) fs.rmSync(file);
while(queue.length){
  const id=queue.shift();
  if(seen.has(id)) continue;
  seen.add(id);
  await p.goto(`https://www.shidianguji.com/zh/book/${book}/chapter/${id}`,{waitUntil:'domcontentloaded'});
  await p.waitForTimeout(2500);
  const html=await p.content().catch(()=>'');
  const found=[...html.matchAll(/chapterId\\?":\\?"([a-z0-9]{8,})/g)].map(m=>m[1]);
  for(const f of found) if(!seen.has(f)&&!queue.includes(f)) queue.push(f);
  const m=html.match(/\\?"paragraphList\\?":(\[)/);
  let lines=[];
  if(m){
    // 提取所有 content 里的 lines
    const re=/\\"content\\":\\"\{.*?\\"\}/g;
    const seg=html.slice(m.index, m.index+400000);
    for(const mm of seg.matchAll(/\\"lineType\\":(\d+),\\"content\\":\\"((?:[^"\\]|\\.){0,2000}?)\\"/g)){
      lines.push([Number(mm[1]), mm[2].replace(/\\\\/g,'\\').replace(/\\"/g,'"')]);
    }
  }
  fs.appendFileSync(file, JSON.stringify({id, lines})+'\n');
  console.log(id, lines.length, 'queue', queue.length);
  await p.waitForTimeout(delay);
  if(seen.size>60) break;
}
await b.close();
