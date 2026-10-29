#!/usr/bin/env python3
"""选本目次 ↔ 库内记录，按整首正文配对（比 check_anthology.py 的首句 12 字锚点稳）

  python3 scripts/shidian/align_anthology.py <底本正文.json> <目次.json> <输出.json>

底本正文由 scripts/shidian/chapter.mjs + 解析得到：{「001.json」: [[lineType, content], ...]}，
按目次顺序编号。给出每首的库位置、相似度，供人工/对勘脚本复核。

本脚本只读，不写数据文件。
"""
import json, re, difflib, glob, sys, collections
from opencc import OpenCC
t2s = OpenCC('t2s').convert
def norm(s): return re.sub(r'[^\u4e00-\u9fff]', '', t2s(s))

SRC = sys.argv[1] if len(sys.argv) > 1 else 'anthologies/songci300.json'
res = json.load(open(sys.argv[2] if len(sys.argv) > 2 else '/tmp/chap300/source.json', encoding='utf-8'))
entries = json.load(open(SRC, encoding='utf-8'))['entries']

idx = []
for f in sorted(glob.glob('宋/宋词/ci.song.*.json')):
    d = json.load(open(f, encoding='utf-8'))
    for i, x in enumerate(d):
        b = norm(''.join(x.get('paragraphs') or []))
        if b: idx.append((f, i, b, x.get('author'), x.get('rhythmic'), 'tags' in x))

rows = []
for i, e in enumerate(entries):
    lines = res[f'{i+1:03d}.json']
    body = norm(''.join(c for t, c in lines if t == 1))
    best = (0, None)
    head = body[:8]
    cands = [t for t in idx if head and head[:5] in t[2]]
    if not cands:
        cands = [t for t in idx if t[2][:5] and t[2][:5] in body]
    if not cands:
        cands = idx
    for t in cands:
        s = t[2][:len(body)] if len(t[2]) >= len(body) else t[2]
        r = difflib.SequenceMatcher(None, body[:120], t[2][:120]).ratio() if body else 0
        if r > best[0]: best = (r, t)
    rows.append({'no': e['no'], 'author': e['author'], 'title': e['title'],
                 'ratio': round(best[0], 3),
                 'where': f"{best[1][0].split('/')[-1]}#{best[1][1]}" if best[1] else '',
                 'lib_author': best[1][3] if best[1] else '',
                 'lib_rhythmic': best[1][4] if best[1] else '',
                 'lib_tagged': best[1][5] if best[1] else False,
                 'body': body})
json.dump(rows, open(sys.argv[3] if len(sys.argv) > 3 else '/tmp/chap300/rows.json', 'w'), ensure_ascii=False, indent=1)
import collections
print(collections.Counter('>=0.95' if r['ratio'] >= 0.95 else '0.8-0.95' if r['ratio'] >= 0.8 else '0.5-0.8' if r['ratio'] >= 0.5 else '<0.5' for r in rows))
