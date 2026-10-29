#!/usr/bin/env python3
"""`唐/词/ci.tang.json` 里与《花间集》重出的词：删补录那一份，留选本。

`唐/词/ci.tang.json` 是《历代》按作者朝代拆出来的补录（正文来自 海棠诗社语料），65 条里有 35 条
是《花间集》里已有的词。花间集在 `五代十国/词/五代诗词/huajianji/`，2026-10 已按
「选本并进总集」把 `poet.tang` 里同作者的副本删过（`scripts/merge_anthologies.py`），
`ci.tang.json` 是后来才拆出来的，两者之间一直没清，同一首词两边各有一份正文。

判据：

  正文 `t2s` 去标点后等长（差 ≤ 2 字）、相似度 ≥ 0.90 —— 一字之差（`樽/尊`、`绿/渌`、`消/销`、
  `玻璃/颇黎`、`裙/裾`）就是同一首的两种写法；
  作者同一人，或补录**没署作者**/署了「无名氏」。

作者不同的一律不动（归属异说两存，与《全唐诗》《全宋词》同一口径）。
题名是「其N」的组词（韦庄《菩萨蛮五首》一条 230 字、温庭筠《新添声杨柳枝词》）不拆，
拆了就是另编书，不在这一轮。

删哪一份：删 `ci.tang.json` 那条 —— 花间集是有底本的选本（有词牌、有卷次），补录那套没有。

用法：
  python3 scripts/dedupe_tangci.py                      # 预演
  python3 scripts/dedupe_tangci.py --apply --date YYYY-MM-DD
"""
import argparse
import collections
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
import progress as pg                       # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
T2S = OpenCC('t2s')
HAN = re.compile(r'[^\u4e00-\u9fff]')
CT = '唐/词/ci.tang.json'
HJ_DIR = '五代十国/词/五代诗词/huajianji'
OUT = 'docs/唐词花间集去重.tsv'
REVIEWER = 'codebuddy'
NONE_AUTHOR = {'', '无名氏', '佚名', '不详'}


def han(s):
    return HAN.sub('', T2S.convert(s or ''))


def body(rec):
    p = rec.get('paragraphs')
    return han(p if isinstance(p, str) else ''.join(p or []))


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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--apply', action='store_true')
    ap.add_argument('--date', default=date.today().isoformat())
    ap.add_argument('--reviewer', default=REVIEWER)
    ap.add_argument('--out', default=OUT)
    args = ap.parse_args()

    ct = json.load(open(os.path.join(ROOT, CT), encoding='utf-8'))
    hj = []
    for f in sorted(glob.glob(os.path.join(ROOT, HJ_DIR, '*.json'))):
        for r in json.load(open(f, encoding='utf-8')):
            if isinstance(r, dict) and body(r):
                hj.append((os.path.relpath(f, ROOT), r))
    index = collections.defaultdict(list)
    for rel, r in hj:
        index[body(r)].append((rel, r))

    drop, rows = set(), []
    for i, rec in enumerate(ct):
        b = body(rec)
        best, ratio, exact = None, 0.0, False
        if b in index:
            best, ratio, exact = index[b][0][1], 1.0, True
        else:
            for _, r in hj:
                rb = body(r)
                if abs(len(rb) - len(b)) > 2:
                    continue
                k = difflib.SequenceMatcher(None, b, rb, autojunk=False).ratio()
                if k > ratio:
                    best, ratio = r, k
        author = T2S.convert((rec.get('author') or '').strip())
        other = T2S.convert((best.get('author') or '').strip()) if best else ''
        same_author = author in NONE_AUTHOR or author == other
        if not (exact or ratio >= 0.90) or not same_author:
            if best and ratio >= 0.90:
                note = f'正文相近但作者不同（{author or "未署"}／{other}）：归属异说，两存'
                keep = f"{HJ_DIR} {other}《{best.get('title')}》"
                shown = f'{ratio:.2f}'
            else:                      # 花间集里根本没有这一首：不列相似度，免得把 0.10 当成结论
                note, keep, shown = '花间集里没有这一首（或组词不拆），不属重复', '', ''
            rows.append(dict(kind='两存', title=f"{author}《{rec.get('rhythmic') or ''}》",
                             length=len(b), keep=keep, ratio=shown, note=note))
            continue
        drop.add(i)
        rows.append(dict(kind='删除', title=f"{author}《{rec.get('rhythmic') or ''}》", length=len(b),
                         keep=f"{HJ_DIR} {other}《{best.get('title')}》", ratio=f'{ratio:.2f}',
                         note='与花间集同首，留选本那份'))

    n = sum(r['kind'] == '删除' for r in rows)
    print(f'== `ci.tang.json`：{len(ct)} 条，删 {n} 条、两存 {len(rows) - n} 条')
    with open(os.path.join(ROOT, args.out), 'w', encoding='utf-8', newline='') as fp:
        w = csv.DictWriter(fp, delimiter='\t', lineterminator='\n',
                           fieldnames=['kind', 'title', 'length', 'keep', 'ratio', 'note'])
        w.writeheader()
        w.writerows(rows)
    print(f'明细写入 {args.out}')

    if not args.apply:
        print('（预演，未改动任何文件；加 --apply 落盘）')
        return 0

    dump(CT, [r for i, r in enumerate(ct) if i not in drop])
    fixes = [dict(original=r['title'], corrected='删除',
                  note=f"与 {r['keep']} 同首（相似度 {r['ratio']}），留选本那份")
             for r in rows if r['kind'] == '删除']
    rec = pg.merge(CT, dict(fixes=fixes))
    rec['note'] = ((rec.get('note') or '').rstrip() +
                   f' {args.date} 重复清理：删 {len(fixes)} 条与《花间集》重出的词，'
                   f'逐条见 {args.out}。').strip()
    pg.write_record(CT, pg.ordered(rec))
    pg.write_index()
    print('进度记录 1 个文件')
    return 0


if __name__ == '__main__':
    sys.exit(main())
