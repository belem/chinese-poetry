import { chromium } from 'playwright';
import fs from 'node:fs';
const browser = await chromium.launch();
const ctx = await browser.newContext({ locale:'zh-CN', viewport:{width:1400,height:1200}, userAgent:'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36'});
const page = await ctx.newPage();
const bodies=[];
page.on('response', async r=>{ const u=r.url(); if(/ancientlib/.test(u)){ try{ const t=await r.text(); bodies.push({u:u.split('?')[0], len:t.length, hasTrans: /起初|譯文|译文|translat/i.test(t)}); }catch(e){} } });
await page.goto('https://www.shidianguji.com/zh/book/SDZJ0641/chapter/1kf9lwwlsqyaj', { waitUntil:'domcontentloaded', timeout:60000 });
await page.waitForTimeout(9000);
console.log(bodies.map(b=>`${b.u} ${b.len} trans=${b.hasTrans}`).join('\n'));
// also dump ROUTER_DATA keys
const rd = await page.evaluate(()=>{
  const s=[...document.querySelectorAll('script')].map(x=>x.textContent||'').find(t=>t.includes('_ROUTER_DATA'));
  if(!s) return null;
  try { const j=JSON.parse(s.replace(/^.*?=\s*/s,'').replace(/;?\s*$/,'')); return Object.keys(j.loaderData||{}); } catch(e){ return 'parse fail: '+e.message; }
});
console.log('ROUTER_DATA loaderData keys:', rd);
await browser.close();
