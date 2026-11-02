import { chromium } from 'playwright';
import fs from 'node:fs';
const browser = await chromium.launch();
const ctx = await browser.newContext({ locale:'zh-CN', viewport:{width:1400,height:1200}, userAgent:'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36'});
const page = await ctx.newPage();
let saved=null;
page.on('response', async r=>{ const u=r.url(); if(/read\/book\/paragraphs\/v3/.test(u)){ try{ saved=await r.text(); }catch(e){} } });
await page.goto('https://www.shidianguji.com/zh/book/SDZJ0641/chapter/1kf9lwwlsqyaj', { waitUntil:'domcontentloaded', timeout:60000 });
await page.waitForTimeout(9000);
fs.writeFileSync('/tmp/gwz/paras_v3.json', saved||'');
console.log('saved', (saved||'').length);
const d=JSON.parse(saved);
const ps=d.data.paragraphs;
console.log('paragraphs', ps.length);
for(const p of ps.slice(0,3)){
  const c=JSON.parse(p.content);
  console.log('--- paragraph', p.paragraphId, 'lines', c.lines.length);
  for(const l of c.lines.slice(0,12)) console.log('  ', l.lineType, JSON.stringify(l.content).slice(0,90));
}
await browser.close();
