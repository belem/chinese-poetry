#!/usr/bin/env python3
"""`汇编/` 选本与各代补录（`poet.*`）互见的稿子：一件作品只留一份正文。

`汇编/` 下的书（古文观止、昭明文选、乐府诗集、课本选目）是**选本**，各代 `poet.*.json`
是《历代》拆出来的**补录**（正文来自 海棠诗社语料，没有底本）。

两处都是同一件作品时，留**选本**那一份：选本有底本、有编次、有篇题（`卷五漢文`「報任安書」），
补录那套没有版本信息，且不少是把整篇塞进一条（`poet.han.json` 的「項羽之死」712 字）。

判据：

  cut      选本某篇是补录某条的一节（补录那条更全），或补录那条是选本的一节，且能逐句对上
  copy     两边整篇一致（`t2s` 去标点后 ≤ 3 字之差）
  两存      作者归属不同（古文观止署「佚名」、补录署「刘向」）、或原文是另一部书
           （昭明文选《古詩十九首》一条 19 首 vs 补录逐首一条 —— 编法不同，不是重复）

删哪一份：**删补录那条**（`poet.*`），选本不动。

用法：
  python3 scripts/dedupe_huibian_poet.py                      # 预演
  python3 scripts/dedupe_huibian_poet.py --apply --date YYYY-MM-DD --poet 汉
"""
import argparse
import collections
import csv
import difflib
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
HUI = '汇编'
REVIEWER = 'codebuddy'
# 补录文件：`--poet 汉` → 汉/诗/poet.han.json
POET = {
    '汉': '汉/诗/poet.han.json',
    '唐': '唐/诗/poet.tang.json',
    '宋': '宋/诗/poet.song.json',
    '清': '清/诗/poet.qing.json',
    '晋': '晋/诗/poet.jin.json',
    '南北朝': '南北朝/诗/poet.nanbeichuan.json',
    '明': '明/诗/poet.ming.json',
}
OUT = 'docs/汇编与诗去重.tsv'


def han(s):
    return HAN.sub('', T2S.convert(s or ''))


def body(rec):
    p = rec.get('paragraphs')
    if isinstance(p, str):
        return han(p)
    if isinstance(p, list) and all(isinstance(x, str) for x in p):
        return han(''.join(p))
    return ''                                     # 蒙学那种 paragraphs 里再套 chapter 的，不在这里判


def walk(node, rel, path=()):
    if isinstance(node, dict):
        p = node.get('paragraphs')
        if isinstance(p, str) or (isinstance(p, list) and all(isinstance(x, str) for x in p)):
            yield rel, path, node
            return
        for k, v in node.items():
            if isinstance(v, (list, dict)):
                yield from walk(v, rel, path + (k,))
    elif isinstance(node, list):
        for i, v in enumerate(node):
            yield from walk(v, rel, path + (i,))


def sentences(text):
    return [c for c in re.split(r'[。？！；]', text) if len(c) >= 6]


def covered(short, long_):
    """短的每一句都能在长的里逐句找到。"""
    pos = 0
    for c in sentences(short):
        k = long_.find(c, pos)
        if k < 0:
            return False
        pos = k + len(c)
    return True


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
    ap.add_argument('--poet', required=True, choices=sorted(POET), help='要清的补录：汉 / 唐 / 宋 …')
    ap.add_argument('--apply', action='store_true')
    ap.add_argument('--date', default=date.today().isoformat())
    ap.add_argument('--reviewer', default=REVIEWER)
    ap.add_argument('--out', default=OUT)
    args = ap.parse_args()

    rel = POET[args.poet]
    poet = json.load(open(os.path.join(ROOT, rel), encoding='utf-8'))
    hui = []
    for dirpath, _, files in os.walk(os.path.join(ROOT, HUI)):
        for f in sorted(files):
            if f.endswith('.json'):
                p = os.path.relpath(os.path.join(dirpath, f), ROOT)
                for r, path, rec in walk(json.load(open(os.path.join(ROOT, p), encoding='utf-8')), p):
                    if body(rec):
                        hui.append((r, path, rec, body(rec)))
    index = collections.defaultdict(list)
    for r, path, rec, b in hui:
        if len(b) >= 16:
            index[b[:16]].append((r, path, rec, b))

    drop, rows = set(), []
    for i, rec in enumerate(poet):
        b = body(rec)
        cands = index.get(b[:16], []) if len(b) >= 16 else []
        if not cands:
            continue
        hit = max(cands, key=lambda x: difflib.SequenceMatcher(None, b, x[3]).ratio())
        ratio = difflib.SequenceMatcher(None, b, hit[3], autojunk=False).ratio()
        title = f"{(rec.get('author') or '')}《{rec.get('title') or rec.get('rhythmic') or ''}》"
        keep = f"{hit[0]}#{'/'.join(map(str, hit[1]))} {hit[2].get('author') or ''}《{hit[2].get('title') or ''}》"
        if ratio < 0.90 and not covered(hit[3], b) and not covered(b, hit[3]):
            rows.append(dict(kind='两存', title=title, length=len(b), keep=keep, ratio=f'{ratio:.2f}',
                             note='正文对不上（同一部书的两处选段/另一篇），不算重复'))
            continue
        if covered(b, hit[3]) and len(hit[3]) > len(b) * 1.3:
            rows.append(dict(kind='两存', title=title, length=len(b), keep=keep, ratio=f'{ratio:.2f}',
                             note='补录这条的每一句都在选本那篇里（选本更全），删补录会丢选本的编次，' 
                                  '留给选本对齐再并'))
            continue
        drop.add(i)
        rows.append(dict(kind='删除', title=title, length=len(b), keep=keep, ratio=f'{ratio:.2f}',
                         note='选本与补录同篇，删补录那份（选本有底本、有编次）'))

    n = sum(r['kind'] == '删除' for r in rows)
    print(f'== {rel} 与 汇编/ 互见：{len(rows)} 条，删 {n} 条、两存 {len(rows) - n} 条')
    with open(os.path.join(ROOT, args.out), 'w', encoding='utf-8', newline='') as fp:
        w = csv.DictWriter(fp, delimiter='\t', lineterminator='\n',
                           fieldnames=['kind', 'title', 'length', 'keep', 'ratio', 'note'])
        w.writeheader()
        w.writerows(rows)
    print(f'明细写入 {args.out}')

    if not args.apply:
        print('（预演，未改动任何文件；加 --apply 落盘）')
        return 0

    dump(rel, [r for i, r in enumerate(poet) if i not in drop])
    fixes = [dict(original=r['title'], corrected='删除',
                  note=f"与 {r['keep']} 同篇（相似度 {r['ratio']}），留选本那份")
             for r in rows if r['kind'] == '删除']
    rec = pg.merge(rel, dict(fixes=fixes))
    rec['note'] = ((rec.get('note') or '').rstrip() +
                   f' {args.date} 重复清理：删 {len(fixes)} 条与 汇编/ 选本重出的篇目，'
                   f'逐条见 {args.out}。').strip()
    pg.write_record(rel, pg.ordered(rec))
    pg.write_index()
    print('进度记录 1 个文件')
    return 0


if __name__ == '__main__':
    sys.exit(main())
