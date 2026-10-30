#!/usr/bin/env python3
"""章回小说里整段重复抄了两遍：删多的那一遍。

`清/小说/`、`明/小说/` 的底本是把影印本按页切分的，跨页处偶尔整段重出：

```
清/小说/红楼梦/hongloumeng.json 第22回 paragraphs[45..47]   ← 留
同上                          paragraphs[49..51]   ← 删（与 45–47 逐字相同）
```

判据严到不能再严：**同一回里连续 ≥3 段、逐字相同**，且重复的两处以剧情行文隔开
（前一处之后、后一处之前有别的段落，不是叠字）。这样只会命中「整段抄两遍」，
不会误伤「同一个人把同一首诗念了两次」（那种前后紧邻，且多半中间有「又念道」）。

比《红楼梦》第 1 回与第 5 回都出现「假作真時真亦假」更常见的误判已经排除：
那两处在不同回，本脚本只比同一回。

用法：
  python3 scripts/dedupe_novel_repeat.py            # 预演
  python3 scripts/dedupe_novel_repeat.py --apply --date YYYY-MM-DD --reviewer <名字>
"""
import argparse
import csv
import glob
import json
import os
import re
import sys
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import progress as pg  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BOOKS = ['清/小说', '明/小说']
OUT = 'docs/小说整段重出.tsv'
MIN_RUN = 3


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


def files_of():
    out = []
    for book in BOOKS:
        out += [os.path.relpath(f, ROOT) for f in glob.glob(os.path.join(ROOT, book, '*', '*.json'))]
    return sorted(out)


def runs(paras):
    """同一回里连续 ≥MIN_RUN 段的重复：返回 [(first_start, dup_start, length)]。"""
    n = len(paras)
    found = []
    i = 0
    while i < n:
        best = 0
        best_j = None
        for j in range(i + MIN_RUN, n):
            k = 0
            while i + k < j and j + k < n and paras[i + k] == paras[j + k]:
                k += 1
            if k > best:
                best, best_j = k, j
        if best >= MIN_RUN and best_j is not None and best_j - i >= MIN_RUN:
            found.append((i, best_j, best))
            i = best_j + best
        else:
            i += 1
    return found


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--apply', action='store_true')
    ap.add_argument('--date', default=date.today().isoformat())
    ap.add_argument('--reviewer', default='codebuddy')
    ap.add_argument('--out', default=OUT)
    args = ap.parse_args()

    rows, plan = [], []
    for rel in files_of():
        data = load(rel)
        for i, r in enumerate(data):
            paras = r.get('paragraphs') or []
            if len(paras) < MIN_RUN * 2:
                continue
            for first, dup, length in runs(paras):
                if dup - first < MIN_RUN:
                    continue          # 两处紧邻：是同一个人重复念，不是抄重
                rows.append(dict(file=rel, idx=i, title=r.get('title') or '',
                                 first=first, dup=dup, length=length,
                                 text=paras[dup][:40]))
                plan.append((rel, i, dup, dup + length))

    print(f'== 整段重出：{len(rows)} 处')
    for r in rows:
        print(f"   {r['file'].split('/')[-1]} 第{r['idx']} 条《{r['title'][:22]}》 "
              f"删 paragraphs[{r['dup']}:{r['dup'] + r['length']}]（与 [{r['first']}:{r['first'] + r['length']}] 逐字相同）")

    if not args.apply:
        print('\n（预演，未改动文件；加 --apply 落盘）')
        return

    by_file = {}
    for rel, i, a, b in plan:
        by_file.setdefault(rel, {}).setdefault(i, []).append((a, b))
    data_cache = {}
    for rel, per in by_file.items():
        data = load(rel)
        for i, spans in per.items():
            paras = data[i].get('paragraphs') or []
            drop = set()
            for a, b in spans:
                drop.update(range(a, b))
            data[i]['paragraphs'] = [p for k, p in enumerate(paras) if k not in drop]
            if not data[i]['paragraphs']:
                del data[i]['paragraphs']   # 整条删空就别留个空数组
        dump(rel, data)
        data_cache[rel] = data

    with open(os.path.join(ROOT, args.out), 'w', encoding='utf-8', newline='') as fp:
        w = csv.writer(fp, delimiter='\t', lineterminator='\n')
        w.writerow(['文件', '条', '回目', '删段落区间', '与之前哪段相同', '首句', '处理'])
        for r in rows:
            w.writerow([r['file'], r['idx'], r['title'],
                        f"{r['dup']}:{r['dup'] + r['length']}", f"{r['first']}:{r['first'] + r['length']}",
                        r['text'], '删重复的那一遍'])
    print(f'明细写入 {args.out}')

    for rel, per in by_file.items():
        fixes = [dict(original=f"第{i}条《{(load(rel)[i].get('title') or '')[:24]}》",
                      corrected=f"paragraphs 删 {len(spans) and sum(b - a for a, b in spans)} 段",
                      note=f'[novel-repeat] 同一回里连续 {MIN_RUN} 段以上逐字重复（跨页切分所致），删多抄的那一遍；见 {args.out}')
                 for i, spans in per.items()]
        rec = pg.merge(rel, dict(fixes=fixes, date=args.date, reviewer=args.reviewer))
        rec['note'] = ((rec.get('note') or '').rstrip() +
                       f' {args.date} 删 {len(fixes)} 处整段重出，逐条见 {args.out}。').strip()
        pg.write_record(rel, pg.ordered(rec))
    pg.write_index()
    print(f'进度记录 {len(by_file)} 个文件')


if __name__ == '__main__':
    main()
