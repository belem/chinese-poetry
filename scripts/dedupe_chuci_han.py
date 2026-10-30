#!/usr/bin/env python3
"""`汉/诗/poet.han.json` 里的《楚辞》副本：删，留 `先秦/楚辞/chuci.json`。

`poet.han.json` 是从 `历代/` 拆出来的补录，里面混着 27 条《楚辞》各篇
（《惜誓》《招隐士》《七谏》《九怀》《九叹》《九思》…），而《楚辞》整部书
另在 `先秦/楚辞/chuci.json`：

```
先秦/楚辞/chuci.json#28      贾谊《惜誓》                  ← 留
汉/诗/poet.han.json#68       贾谊《楚辞·惜誓》             ← 删
```

两读出自同一部底本（通行本《楚辞补注》），正文只差繁简与几处通用字
（沾濡／霑濡、後／后、虬／蚯、讬／托），不是异文。按「一件作品只留一份正文」（AGENTS.md），
删补录那份、留单行本 —— `chuci.json` 有 `section` 与分篇编次，`poet.han.json` 是一条条散录。

判据：作者相同、题名相同（补录加了「楚辞·」前缀，去掉后比）、正文相似度 ≥ 0.90。

用法：
  python3 scripts/dedupe_chuci_han.py            # 预演：逐组打印
  python3 scripts/dedupe_chuci_han.py --apply --date YYYY-MM-DD --reviewer <名字>
"""
import argparse
import csv
import difflib
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
BOOK = '汉/诗/poet.han.json'
KEEP = '先秦/楚辞/chuci.json'
OUT = 'docs/楚辞汉诗去重.tsv'
PREFIX = 16
MIN_RATIO = 0.90


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


def strip_book(t):
    """题名归一：去掉「楚辞·」前缀与「·其N·」「 其一」这类分篇序号。

    《楚辞》各篇的篇内小标题两书取法不同：`chuci.json` 题作《沉江》、
    `poet.han.json` 题作《楚辞·七谏·其二·沉江》，取末段比。
    """
    t = (t or '').strip()
    if t.startswith('楚辞·'):
        t = t[3:]
    t = re.sub(r'^.*·(?=[^·]+$)', '', t)
    return t.strip()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--apply', action='store_true')
    ap.add_argument('--date', default=date.today().isoformat())
    ap.add_argument('--reviewer', default='codebuddy')
    ap.add_argument('--out', default=OUT)
    args = ap.parse_args()

    keep = load(KEEP)
    data = load(BOOK)
    idx = {}
    for i, r in enumerate(keep):
        idx.setdefault((r.get('author'), body(r)[:PREFIX]), []).append((i, r))

    rows, drops = [], {}
    for i, r in enumerate(data):
        b = body(r)
        if len(b) < PREFIX:
            continue
        cands = idx.get((r.get('author'), b[:PREFIX]), [])
        if not cands:
            continue
        best = max(cands, key=lambda c: difflib.SequenceMatcher(None, body(c[1]), b).ratio())
        ratio = difflib.SequenceMatcher(None, body(best[1]), b).ratio()
        same_title = strip_book(r.get('title')) == (best[1].get('title') or '').strip()
        if ratio < MIN_RATIO or not same_title:
            print(f'   跳过 {r.get("author")}《{r.get("title")}》：ratio={ratio:.3f} 同题={same_title}')
            continue
        drops.setdefault(BOOK, set()).add(r.get('id'))
        rows.append(dict(keep=f"{KEEP}#{best[0]} {best[1].get('author')}《{best[1].get('title')}》",
                         drop=f"{BOOK}#{i} {r.get('author')}《{r.get('title')}》",
                         ratio=f'{ratio:.3f}', key=b[:PREFIX]))

    print(f'== 《楚辞》与 poet.han 的重出：{len(rows)} 组')
    for r in rows:
        print(f"   删 {r['drop'][:52]:<52} ← 留 {r['keep'][:44]}  {r['ratio']}")

    if not args.apply:
        print('\n（预演，未改动文件；加 --apply 落盘）')
        return

    dropped = [r for r in data if r.get('id') in drops.get(BOOK, set())]
    data = [r for r in data if r.get('id') not in drops.get(BOOK, set())]
    dump(BOOK, data)

    with open(os.path.join(ROOT, args.out), 'w', encoding='utf-8', newline='') as fp:
        w = csv.writer(fp, delimiter='\t', lineterminator='\n')
        w.writerow(['保留', '重复', '相似度', '正文前16字', '处理'])
        for r in rows:
            w.writerow([r['keep'], r['drop'], r['ratio'], r['key'], '删补录那份，留《楚辞》单行本'])
    print(f'明细写入 {args.out}')

    rec = pg.merge(BOOK, dict(fixes=[dict(
        original=f"{r.get('id')} {r.get('author')}《{r.get('title')}》", corrected='删除',
        note=f'[chuci] 与《楚辞》单行本重出（同作者同篇，相似度 ≥ {MIN_RATIO}），删补录那份；见 {args.out}')
        for r in dropped], date=args.date, reviewer=args.reviewer))
    rec['note'] = ((rec.get('note') or '').rstrip() +
                   f' {args.date} 删 {len(dropped)} 条《楚辞》副本，逐条见 {args.out}。').strip()
    pg.write_record(BOOK, pg.ordered(rec))
    pg.write_index()
    print(f'进度记录 1 个文件')


if __name__ == '__main__':
    main()
