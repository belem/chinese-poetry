#!/usr/bin/env python3
"""《全宋诗》内部的两类全同重出，一次清完：

  same_author   同一人、同一题、正文（t2s 归一去非汉字）**整篇逐字相同**的两条。
                这批评语是一卷一千条切出来的，同一个人的一段被前后切在两个文件里
                （盛世忠 15 首一字不差地出现在 poet.song.202000 与 poet.song.220000），
                删后出现的那份。宋太宗《逍遥詠》《緣識》的组诗重出（题名不同）不在此列，
                已按识典古籍逐组核过，两存。

  same_title    作者署名不同（繁简、僧俗、形近）但去掉朝代/僧字后同一人、同一题、
                整篇逐字相同的两条 —— 同 `scripts/dedupe_tang.py` 的「同作者重出」。
                作者真的不同的一律不动：那是归属异说，与《全唐诗》一个口径。

正文有出入的一律两存（异文），不在此脚本范围。

用法：
  python3 scripts/dedupe_quanmingshi.py            # 预演
  python3 scripts/dedupe_quanmingshi.py --apply --date YYYY-MM-DD
"""
import argparse
import collections
import csv
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
BOOK = '宋/诗/全宋诗'
OUT = 'docs/全宋诗全同重出.tsv'
REVIEWER = 'codebuddy'
# 同一个人，两种署名（t2s 之后比）：只收确定性高的
ALIAS = {'王庭圭': '王庭珪', '晁公溯': '晁公遡', '陳摶': '陈抟', '王炎双溪': '王炎'}


def han(s):
    return HAN.sub('', T2S.convert(s or ''))


def body(rec):
    return han(''.join(rec.get('paragraphs') or []))


def title_key(rec):
    return han(rec.get('title') or '')


def author_key(rec):
    a = han(rec.get('author') or '')
    return ALIAS.get(a, a)


def files():
    d = os.path.join(ROOT, BOOK)
    fs = [f for f in os.listdir(d) if re.fullmatch(r'poet\.song\.\d+\.json', f)]
    return [f'{BOOK}/{f}' for f in sorted(fs, key=lambda f: int(f.split('.')[2]))]


def load(rel):
    with open(os.path.join(ROOT, rel), encoding='utf-8') as fp:
        return json.load(fp)


def dump(rel, data):
    """写回，且只让「删掉的记录」进 diff（同 scripts/dedupe_songci_full.py）。"""
    path = os.path.join(ROOT, rel)
    raw = open(path, encoding='utf-8').read()
    m = re.search(r'\n( +)\S', raw)
    indent = len(m.group(1)) if m else 2
    out = json.dumps(data, ensure_ascii=False, indent=indent) + ('\n' if raw.endswith('\n') else '')
    sep = '\n' + ' ' * indent + '{'
    head, *old = raw.split(sep)
    _, *new = out.split(sep)
    if len(new) == len(old):
        return

    def same(x, y):
        a, b = x.split('\n'), y.split('\n')
        return len(a) == len(b) and all(p.rstrip(' ') == q.rstrip(' ') for p, q in zip(a, b))

    res, i, j = [head], 0, 0
    while j < len(new) and i < len(old):
        if same(old[i], new[j]):
            res.append(old[i])
            i, j = i + 1, j + 1
        else:
            i += 1
    res.extend(old[i:])
    text = sep.join(res)
    if text != raw:
        with open(path, 'w', encoding='utf-8') as fp:
            fp.write(text)


def desc(f, i, r):
    return f"{f}#{i} {r.get('author')}《{r.get('title')}》"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--apply', action='store_true')
    ap.add_argument('--date', default=date.today().isoformat())
    ap.add_argument('--reviewer', default=REVIEWER)
    ap.add_argument('--out', default=OUT)
    args = ap.parse_args()

    rels = files()
    data = {rel: load(rel) for rel in rels}
    index = collections.defaultdict(list)
    for rel in rels:
        for i, rec in enumerate(data[rel]):
            b = body(rec)
            if len(b) >= 16:
                index[b[:16]].append((rel, i, rec, b))

    drop = collections.defaultdict(set)
    rows = []
    for key, grp in index.items():
        if len(grp) < 2:
            continue
        by_body = collections.defaultdict(list)
        for x in grp:
            by_body[x[3]].append(x)
        for b, group in by_body.items():
            if len(group) < 2:
                continue
            # 组内再按「同一人 + 同一题」切
            by_work = collections.defaultdict(list)
            for x in group:
                by_work[(author_key(x[2]), title_key(x[2]))].append(x)
            for (a, t), g in by_work.items():
                if len(g) < 2:
                    continue
                # 留「先出现」的那条：卷号小的、同卷里下标小的
                g.sort(key=lambda x: (int(x[0].split('.')[-2]), x[1]))
                keep = g[0]
                kind = 'same_author' if len({x[2].get('author') for x in g}) == 1 else 'same_title'
                for x in g[1:]:
                    drop[x[0]].add(x[1])
                    rows.append(dict(kind=kind, keep=desc(*keep[:3]), drop=desc(*x[:3]),
                                     length=len(b),
                                     note='同人同题、正文逐字相同，留卷号靠前的那条'))

    n = sum(len(v) for v in drop.values())
    print(f'== {BOOK} 全同重出：删 {n} 条（{len(rows)} 组）')
    for kind in ('same_author', 'same_title'):
        k = [r for r in rows if r['kind'] == kind]
        print(f'   {kind}: {len(k)} 条')
        for r in k[:4]:
            print(f'     留 {r["keep"]} ← 删 {r["drop"]}')

    if not args.apply:
        print('（预演，未写盘；加 --apply 写回）')
        return

    for rel in rels:
        if rel not in drop:
            continue
        data[rel] = [r for i, r in enumerate(data[rel]) if i not in drop[rel]]
        dump(rel, data[rel])

    with open(os.path.join(ROOT, args.out), 'w', encoding='utf-8', newline='') as fp:
        w = csv.DictWriter(fp, delimiter='\t', lineterminator='\n',
                           fieldnames=['kind', 'keep', 'drop', 'length', 'note'])
        w.writeheader()
        w.writerows(rows)
    print(f'明细写入 {args.out}')

    by_file = collections.defaultdict(list)
    for r in rows:
        rel, idx = r['drop'].split('#')
        by_file[rel].append({'original': f'#{idx} {r["drop"].split(" ", 1)[1]}',
                             'corrected': '删除',
                             'note': f'与 {r["keep"]} 同人同题、正文逐字相同，删卷号靠后的一条'})
    for rel, fixes in sorted(by_file.items()):
        rec = pg.merge(rel, dict(fixes=fixes))
        rec['note'] = ((rec.get('note') or '').rstrip() +
                       f' {args.date} 重复清理：删 {len(fixes)} 条全同重出的副本，逐条见 {args.out}。').strip()
        pg.write_record(rel, pg.ordered(rec))
    pg.write_index()
    print(f'进度记录 {len(by_file)} 个文件')


if __name__ == '__main__':
    main()
