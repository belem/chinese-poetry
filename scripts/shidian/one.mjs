import { chromium } from 'playwright';
import fs from 'node:fs';
const [id, outFile] = process.argv.slice(2);
const browser = await chromium.launch();
const ctx = await browser.newContext({ locale:'zh-CN', viewport:{width:1400,height:1200}, userAgent:'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36'});
const page = await ctx.newPage();
let body=null;
page.on('response', async r=>{ if(/read\/book\/paragraphs\/v3/.test(r.url())){ try{ body=await r.text(); }catch(e){} } });
await page.goto('https://www.shidianguji.com/zh/book/SDZJ0641/chapter/'+id, { waitUntil:'domcontentloaded', timeout:60000 });
for(let i=0;i<24 && !body;i++) await page.waitForTimeout(500);
console.log('body?', !!body, body? body.length : 0);
if (body) {
  const d=JSON.parse(body).data;
  const done=JSON.parse(fs.readFileSync(outFile,'utf8'));
  const paras=[];
  for(const p of d.paragraphs||[]){
    let c=p.content; if(typeof c==='string'){ try{c=JSON.parse(c);}catch(e){continue;} }
    const text=[],notes=[];
    for(const l of c.lines||[]){ if(l.lineType===1) text.push(l.content); else if(l.lineType===2) notes.push(l.content); }
    const t=text.join('');
    const tc=p.translateContent;
    const trans=tc&&tc.sentences? tc.sentences.map(s=>s.content).join('') : '';
    if(!t&&!notes.length) continue;
    paras.push({text:t,notes,trans});
  }
  done[id]={title:'古文序',level:1,volume:'(front)',paras};
  fs.writeFileSync(outFile, JSON.stringify(done,null,1));
  console.log('saved', id, paras.length);
}
await browser.close();
