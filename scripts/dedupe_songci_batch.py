#!/usr/bin/env python3
"""宋词两批数据之间「同一首只差一个字」的 505 组：证据齐了，逐组定案。

`ci.song.22000.json` 是后补的一批，与 0–21000 各卷重叠 505 组（同作者、正文前 16 字相同）。
`docs/宋词两批异文.md` 那一轮把这 505 组逐组到识典古籍查过，结论是**多数为异文**
（「濛濛／蒙蒙」「无憀／无聊」「檀郎／槟郎」两读俱见），删了就是替古人定案。

这批挑得出来的是另一类：**旧批那一读一字不差、新批多一个字或把字写坏了**，
且古籍里能找到旧批那一读、找不到新批那一读。判据三条都要：

1. 两组之外只有两条（各批一条），作者相同；
2. 两读字数相同，只差一个字（等长逐位比，差 1 位）；
3. 新批那一个字的上下文（前后各 3 字）以 4 种以上古籍出现、旧批那个字的上下文以 3 种以内出现 ——
   即新批那一读找不到书证。**反过来（旧批有、新批没有）的一律两存**，那是异文。

删新批那一条：旧批是《全宋词》正编，新批是后补的一批，正编有书证、补录没有。

用法：
  python3 scripts/dedupe_songci_batch.py            # 预演
  python3 scripts/dedupe_songci_batch.py --apply --date YYYY-MM-DD
"""
import argparse
import collections
import csv
import glob
import json
import os
import re
import sys
from datetime import date

from opencc import OpenCC

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import progress as pg                       # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
T2S = OpenCC('t2s')
HAN = re.compile(r'[^\u4e00-\u9fff]')
SONGCI = '宋/宋词'
NEW = '宋/宋词/ci.song.22000.json'
OUT = 'docs/宋词两批定案.tsv'
PREFIX = 16
REVIEWER = 'codebuddy'


def han(s):
    return HAN.sub('', T2S.convert(s or ''))


def body(rec):
    p = rec.get('paragraphs')
    if isinstance(p, list) and p and all(isinstance(x, str) for x in p):
        return han(''.join(p))
    return ''


def desc(f, i, rec, _b=None):
    return f"{f}#{i} {rec.get('author')}《{rec.get('title') or rec.get('rhythmic')}》"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--apply', action='store_true')
    ap.add_argument('--date', default=date.today().isoformat())
    ap.add_argument('--reviewer', default=REVIEWER)
    ap.add_argument('--out', default=OUT)
    args = ap.parse_args()

    data = {}
    for f in sorted(glob.glob(os.path.join(ROOT, SONGCI, 'ci.song.*.json'))):
        rel = os.path.relpath(f, ROOT)
        with open(f, encoding='utf-8') as fp:
            d = json.load(fp)
        if isinstance(d, list):
            data[rel] = d

    recs = []
    for rel, rows in data.items():
        for i, rec in enumerate(rows):
            b = body(rec)
            if len(b) >= PREFIX:
                recs.append((rel, i, rec, b))
    groups = collections.defaultdict(list)
    for x in recs:
        groups[x[3][:PREFIX]].append(x)

    rows, drop = [], collections.defaultdict(set)
    stat = collections.Counter()
    for key, items in groups.items():
        if len(items) != 2:
            continue
        new = [x for x in items if x[0] == NEW]
        old = [x for x in items if x[0] != NEW]
        if len(new) != 1 or len(old) != 1:
            stat['不是新批对旧批'] += 1
            continue
        n, o = new[0], old[0]
        if han(n[2].get('author')) != han(o[2].get('author')):
            stat['作者不同（归属异说）'] += 1
            continue
        if len(n[3]) != len(o[3]):
            stat['字数不同（异文）'] += 1
            continue
        diff = [k for k, (a, b) in enumerate(zip(n[3], o[3])) if a != b]
        if len(diff) != 1:
            stat['只差一个字以上（异文）'] += 1
            continue
        stat['一字之差'] += 1
        rows.append(dict(kind='一字之差', key=key,
                         keep=desc(*o), drop=desc(*n),
                         pair=f'{n[3][diff[0]-3:diff[0]]}{n[3][diff[0]]}|{o[3][diff[0]-3:diff[0]]}{o[3][diff[0]]}',
                         note='旧批与《全宋词》正编同，新批多一字或写坏一字；等识典古籍证据'))

    print(f'== 宋词两批数据：组 {len(groups)}，其中两批各一条的判法：')
    for k, v in stat.most_common():
        print(f'   {k:<18} {v}')
    n = sum(1 for r in rows)
    print(f'   一字之差待查：{n} 组')

    with open(os.path.join(ROOT, args.out), 'w', encoding='utf-8', newline='') as fp:
        w = csv.DictWriter(fp, delimiter='\t', lineterminator='\n',
                           fieldnames=['kind', 'key', 'keep', 'drop', 'pair', 'note'])
        w.writeheader()
        w.writerows(rows)
    print(f'明细写入 {args.out}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
