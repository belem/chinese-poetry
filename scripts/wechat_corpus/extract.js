// 从 poem-wechat-mini-program/scripts/corpus/data 抽出条目正文（含 text-master 引用展开）。
// 用法: node extract.js <data目录> > out.json
const fs = require('fs');
const path = require('path');
const dir = process.argv[2];
if (!dir) { console.error('usage: node extract.js <data-dir>'); process.exit(1); }
const load = (f) => { global.window = {}; require(path.resolve(dir, f)); return global.window; };

const master = {};
load('text-master.js').TEXT_MASTER.forEach((e) => {
  master[e.id] = e;
  (e.entries || []).forEach((x) => { master[x] = e; });
});

const COLLECTIONS = {
  'poems-yuefu.js': 'POEMS_YUEFU', 'poems-gushi.js': 'POEMS_GUSHI',
  'poems-tangshi.js': 'POEMS_TANGSHI', 'poems-yuanqu.js': 'POEMS_YUANQU',
  'poems-zhaoming.js': 'POEMS_ZHAOMING', 'poems-guwen.js': 'POEMS_GUWEN',
  'poems-classic.js': 'POEMS_CLASSIC',
};
const out = {};
for (const [file, key] of Object.entries(COLLECTIONS)) {
  const items = load(file)[key] || [];
  out[file] = items.map((it) => {
    const m = it.textRef ? master[it.textRef] : null;
    const rec = Object.assign({}, it);
    if (m) { rec.text = m.text || ''; rec.translation = m.translation || ''; }
    return rec;
  }).filter((r) => r.text);
}
process.stdout.write(JSON.stringify(out, null, 1));
