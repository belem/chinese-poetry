// 从 poem-wechat-mini-program/scripts/corpus/data 抽出条目正文（含 text-master 引用展开）。
// 注意：条目可能内联正文，也可能只给 textRef 指向 text-master，两种都要认。
// 只保留 collect.py 要用的字段：正文、标题、作者（及本名）、朝代、编排组。
// 用法: node extract.js <data目录> > out.json
const fs = require('fs');
const path = require('path');
const dir = process.argv[2];
if (!dir) { console.error('usage: node extract.js <data-dir>'); process.exit(1); }
// 在 vm 沙箱里跑，共用同一个 window：有些文件是 IIFE 往 window 上挂数组，
// 用 require 会各拿一个模块作用域、拿不到别的文件挂上去的东西
const vm = require('vm');
const sandbox = { window: {} };
vm.createContext(sandbox);
const load = (f) => {
  vm.runInContext(fs.readFileSync(path.resolve(dir, f), 'utf8'), sandbox, { filename: f });
  return sandbox.window;
};

const master = {};

load('text-master.js').TEXT_MASTER.forEach((e) => {
  master[e.id] = e;
  (e.entries || []).forEach((x) => { master[x] = e; });
});

// 课内是 12 册课本，一册一个集子，名字与上游文件对齐
const COLLECTIONS = {
  'poems-1.js': 'POEMS_1', 'poems-2.js': 'POEMS_2', 'poems-3.js': 'POEMS_3',
  'poems-4.js': 'POEMS_4', 'poems-5.js': 'POEMS_5', 'poems-6.js': 'POEMS_6',
  'poems-7.js': 'POEMS_7', 'poems-8.js': 'POEMS_8', 'poems-9.js': 'POEMS_9',
  'poems-10.js': 'POEMS_10', 'poems-11.js': 'POEMS_11', 'poems-12.js': 'POEMS_12',
  'poems-yuefu.js': 'POEMS_YUEFU', 'poems-gushi.js': 'POEMS_GUSHI',
  'poems-tangshi.js': 'POEMS_TANGSHI', 'poems-yuanqu.js': 'POEMS_YUANQU',
  'poems-zhaoming.js': 'POEMS_ZHAOMING', 'poems-guwen.js': 'POEMS_GUWEN',
  'poems-classic.js': 'POEMS_CLASSIC', 'poems-songci.js': 'POEMS_SONGCI',
  'poems-jinxiandai.js': 'POEMS_JINXIANDAI',
  'poems-seasonal-361.js': 'POEMS_SEASONAL_SEASON',
};
const out = {};
for (const [file, key] of Object.entries(COLLECTIONS)) {
  const items = load(file)[key] || [];
  out[file] = items.map((it) => {
    const m = it.textRef ? master[it.textRef] : null;
    const rec = Object.assign({}, it);
    return {
      id: rec.id, title: rec.title || '', author: rec.author || '',
      authorName: rec.authorName || '', dynasty: rec.dynasty || '',
      group: rec.gradeGroup || rec.group || '',
      text: it.text || (m && m.text) || '',
    };
  }).filter((r) => r.text);
}
process.stdout.write(JSON.stringify(out, null, 1));
