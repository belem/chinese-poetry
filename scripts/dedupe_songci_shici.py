#!/usr/bin/env python3
"""一阕词同时收在《全宋词》与《全宋诗》里：删诗那一份。

宋人常把词题作诗题收进诗集（《漁父詞》《漁父樂》《開元樂詞》《白玉樓步虛詞》），
《全宋诗》按诗收，《全宋词》按词收，同一位作者的同一首被两书各录一次：

```
宋/宋词/ci.song.1000.json#80       沈括《开元乐・三台》              ← 留
宋/诗/全宋诗/poet.song.39000.json#155 沈括《開元樂詞  其一》           ← 删
```

判据：作者相同、《全宋词》那条正文是完整的（词牌 + 正文，不是残句）、
两读正文全同或相似度 ≥ 0.95。

删诗那一份：词籍是这个词调的本来归属（《全宋词》按词牌编次，`rhythmic` 字段记词牌），
《全宋诗》那边的题名是「漁父樂 無一事」这类后加的分首小注，不是诗题。

**作者不同的 24 组一条不动**：那是《全宋词》与《全宋诗》之间的归属异说
（同一首词两书各记一个人），按老口径两存。

用法：
  python3 scripts/dedupe_songci_shici.py            # 预演：逐组打印
  python3 scripts/dedupe_songci_shici.py --apply --date YYYY-MM-DD --reviewer <名字>
"""
import argparse
import csv
import difflib
import glob
import json
import os
import re
import sys
from datetime import date

from opencc import OpenCC

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import progress as pg  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
T2S = OpenCC('t2s')
HAN = re.compile(r'[^\u4e00-\u9fff]')
BOOK_CI = '宋/宋词'
BOOK_SHI = '宋/诗/全宋诗'
OUT = 'docs/宋词全宋诗去重.tsv'
PREFIX = 16
MIN_RATIO = 0.95


def han(s):
    return HAN.sub('', T2S.convert(s or ''))


def body(rec):
    return han(''.join(rec.get('paragraphs') or []))


def load(rel):
    with open(os.path.join(ROOT, rel), encoding='utf-8') as fp:
        return json.load(fp)


def dump(rel, data):
    path = os.path.join(ROOT, rel)
    raw = open(path, encoding='utf-8').read()
    m = re.search(r'\n( +)\S', raw)
    indent = len(m.group(1)) if m else 2
    out = json.dumps(data, ensure_ascii=False, indent=indent) + ('\n' if raw.endswith('\n') else '')
    src = raw.split('\n')
    out = '\n'.join(r + (' ' if i < len(src) - 1 and src[i].endswith(' ') else '')
                    for i, r in enumerate(out.split('\n')))
    with open(path, 'w', encoding='utf-8') as fp:
        fp.write(out)


def files_of(book):
    fs = [os.path.relpath(f, ROOT) for f in glob.glob(os.path.join(ROOT, book, '*.json'))]
    fs = [f for f in fs if re.search(r'\.\d+\.json$', f)]
    return sorted(fs, key=lambda f: int(re.search(r'\.(\d+)\.json$', f).group(1)))


def corpus():
    data, recs = {}, []
    for book in (BOOK_CI, BOOK_SHI):
        for rel in files_of(book):
            data[rel] = load(rel)
            for i, rec in enumerate(data[rel]):
                b = body(rec)
                if len(b) >= PREFIX:
                    recs.append((rel, i, rec, b))
    return data, recs


def groups_of(recs):
    g = {}
    for rel, i, rec, b in recs:
        g.setdefault(b[:PREFIX], []).append((rel, i, rec, b))
    return [v for v in g.values()
            if any(r.startswith(BOOK_CI + '/') for r, *_ in v)
            and any(r.startswith(BOOK_SHI + '/') for r, *_ in v)]


def desc(x):
    return f"{x[0]}#{x[1]} {x[2].get('author')}《{x[2].get('title') or x[2].get('rhythmic')}》"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--apply', action='store_true')
    ap.add_argument('--date', default=date.today().isoformat())
    ap.add_argument('--reviewer', default='codebuddy')
    ap.add_argument('--out', default=OUT)
    args = ap.parse_args()

    data, recs = corpus()
    grps = groups_of(recs)
    print(f'== 《全宋词》↔《全宋诗》正文前 {PREFIX} 字相同的组：{len(grps)}')

    rows, drops, stat = [], {}, {}
    for items in sorted(grps, key=lambda g: (g[0][2].get('author') or '')):
        ci = [x for x in items if x[0].startswith(BOOK_CI + '/')]
        shi = [x for x in items if x[0].startswith(BOOK_SHI + '/')]
        ca = {x[2].get('author') for x in ci}
        sa = {x[2].get('author') for x in shi}
        if ca != sa:
            stat['异作者'] = stat.get('异作者', 0) + 1
            rows.append(dict(kind='keep', keep=desc(ci[0]), drop=desc(shi[0]), why='作者不同，归属异说，两存'))
            continue
        c, s = ci[0], shi[0]
        ratio = difflib.SequenceMatcher(None, c[3], s[3]).ratio()
        if ratio < MIN_RATIO:
            stat['正文有出入'] = stat.get('正文有出入', 0) + 1
            rows.append(dict(kind='review', keep=desc(c), drop=desc(s), why=f'相似度 {ratio:.3f}'))
            continue
        stat['删诗那份'] = stat.get('删诗那份', 0) + 1
        drops.setdefault(s[0], set()).add(s[2].get('id'))
        rows.append(dict(kind='drop', keep=desc(c), drop=desc(s), why=f'同作者，相似度 {ratio:.3f}'))

    for k, v in sorted(stat.items(), key=lambda kv: -kv[1]):
        print(f'   {k:<10} {v} 组')
    print(f'   拟删 {sum(len(v) for v in drops.values())} 条，涉及 {len(drops)} 个文件')

    if not args.apply:
        for r in rows:
            if r['kind'] == 'drop':
                print(f"   删 {r['drop'][:56]:<56} ← 留 {r['keep'][:52]}")
        print('\n（预演，未改动文件；加 --apply 落盘）')
        return

    fixes = {}
    for rel, ids in drops.items():
        gone = [r for r in data[rel] if r.get('id') in ids]
        dump(rel, [r for r in data[rel] if r.get('id') not in ids])
        fixes[rel] = [dict(original=f"{r.get('id')} {r.get('author')}《{r.get('title')}》",
                           corrected='删除',
                           note='[songci-shici] 一阕词同时收在《全宋词》与《全宋诗》，删诗那一份')
                       for r in gone]

    with open(os.path.join(ROOT, args.out), 'w', encoding='utf-8', newline='') as fp:
        w = csv.writer(fp, delimiter='\t', lineterminator='\n')
        w.writerow(['判定', '保留', '重复', '处理'])
        for r in rows:
            w.writerow([r['kind'], r['keep'], r['drop'], r['why'] + ('，删诗那一份' if r['kind'] == 'drop' else '')])
    print(f'明细写入 {args.out}')

    for rel, items in fixes.items():
        rec = pg.merge(rel, dict(fixes=items, date=args.date, reviewer=args.reviewer))
        rec['note'] = ((rec.get('note') or '').rstrip() +
                       f' {args.date} 删 {len(items)} 条与《全宋词》重出的诗，逐条见 {args.out}。').strip()
        pg.write_record(rel, pg.ordered(rec))
    pg.write_index()
    print(f'进度记录 {len(fixes)} 个文件')


if __name__ == '__main__':
    main()
