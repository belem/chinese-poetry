#!/usr/bin/env python3
"""元曲「同一支曲长短两录、题名只差间隔号写法」的那一批：删短的那条。

`元/元曲/yuanqu.json` 里同一支曲被录了两遍：`双调・水仙子夜雨`（485 字，正文全）与
`双调·水仙子·夜雨`（48 字，只有一支）。两录题名只差间隔号写法（`・` 与 `·`）与书题断法，
作者同一人。`scripts/dedupe_duplicates.py` 的 `yuanqu_cover()` 只认「短的是长的**开头**」，
短的那条若从长句中间开始（长句是套数、短句是其中一支），它就判不了，于是留了 38 组。

这一批把「题名是同一支曲、又有一份正文是另一份的一节」的逐组核过，能在**不比对古籍**的
前提下定案的都在这里：留正文长的那条，删短的那条；两读有出文的（`孤/辜` 这类用字）
不另记，正文取长的那条。逐组判定见 docs/元曲长短两录.tsv。

不动的：
  - 作者不同（关汉卿／曾瑞、汤舜民／詹时雨、真氏／真真……）：归属异说，两存；
  - 长的那条未必更全（`柯丹邱《荆钗记》一封书` 182 字 vs 260 字两条都是本书的曲文），两存；
  - 短的那条是另一支曲（同曲牌的异曲），不在这里判。

用法：
  python3 scripts/dedupe_yuanqu_pairs.py                      # 预演
  python3 scripts/dedupe_yuanqu_pairs.py --apply --date YYYY-MM-DD
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
from dedupe_duplicates import same_title, tune_parts   # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
T2S = OpenCC('t2s')
HAN = re.compile(r'[^\u4e00-\u9fff]')
YUANQU = '元/元曲/yuanqu.json'
OUT = 'docs/元曲长短两录.tsv'
REVIEWER = 'codebuddy'
ALIAS = {'王德信': '王实甫', '真真': '真氏', '朱帘秀': '珠帘秀'}


def han(s):
    return HAN.sub('', T2S.convert(s or ''))


def body(rec):
    p = rec.get('paragraphs')
    return han(p if isinstance(p, str) else ''.join(p or ''))


def author(rec):
    a = T2S.convert(str(rec.get('author') or '').strip())
    return ALIAS.get(a, a)


def title(rec):
    return str(rec.get('title') or '')


MARK = re.compile(r'之[一二三四五六七八九十]+')      # 四首并作一条时夹在中间的「之一」「之二」


def clauses(text):
    """一句一句分（`。？！` 断），并抹掉夹在中间的「之一」「之二」。"""
    return [MARK.sub('', c) for c in re.split(r'[。？！]', text) if c]


def subset_span(long_, short, max_diff=2):
    """短的每一句都能在长的里找到「只差一两个字」的那一句（按序），就是长的一节。

    同一支曲两录的断句未必相同：`双调・水仙子夜雨`（485 字，八支合成一条）里那一支是
    「一声梧叶一声秋，一点芭蕉一点愁……」；`中吕・山坡羊燕子` 两录只差「渭河／渭水」一个字，
    可整条一口气写下来、没有句号。所以按「整串找近似出现（允许 max_diff 处一字之差）」判，
    对不上就退到「只比这一句的头 8 个字」—— 一字之差落在句尾时，靠这一层兜住。
    """
    pos = 0
    for c in clauses(short):
        opts = [c] + ([c[:8]] if len(c) > 10 else [])
        for want in opts:
            k = find_loose(long_, want, pos, max_diff)
            if k >= 0:
                pos = k + len(want)
                break
        else:
            return False
    return True


def clause_coverage(long_, short):
    """短的那条里，有多少句能在长的里找到「只差一两个字」的同一句（按序，不重复计）。"""
    from difflib import SequenceMatcher
    pool = [c for c in clauses(long_) if len(c) >= 6]
    hit = 0
    for c in clauses(short):
        if len(c) < 6:
            continue
        for k, cand in enumerate(pool):
            n = min(len(c), len(cand))
            if SequenceMatcher(None, c[:n], cand[:n], autojunk=False).ratio() >= 0.85:
                pool.pop(k)
                hit += 1
                break
    return hit / max(1, len([c for c in clauses(short) if len(c) >= 6]))


def find_loose(long_, want, start, budget):
    """在 long_[start:] 里找 want 的近似出现（允许 budget 处一字之差），返回起点，找不到 -1。"""
    from difflib import SequenceMatcher
    n = len(want)
    for k in range(start, max(start, len(long_) - n + 1)):
        window = long_[k:k + n + budget]
        if SequenceMatcher(None, want, window[:n], autojunk=False).ratio() >= (n - budget) / n:
            return k
    return -1


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

    data = json.load(open(os.path.join(ROOT, YUANQU), encoding='utf-8'))
    bodies = [body(r) for r in data]
    index = collections.defaultdict(list)
    for i, b in enumerate(bodies):
        if len(b) >= 16:
            index[b[:16]].append(i)

    drop, rows = set(), []
    for i, b in enumerate(bodies):
        if len(b) < 16:
            continue
        for j in index.get(b[:16], []):
            if j <= i or j in drop:
                continue
            short, long_ = (i, j) if len(bodies[i]) < len(bodies[j]) else (j, i)
            if long_ in drop:
                continue
            sb, lb = bodies[short], bodies[long_]
            a, c = author(data[short]), author(data[long_])
            pair = f"{data[short].get('author')}／{data[long_].get('author')}"
            if a != c:
                rows.append(dict(kind='两存', title=title(data[short]), keep=title(data[long_]),
                                 short=len(sb), long=len(lb), note=f'作者不同（{pair}）：归属异说，两存'))
                continue
            if not same_title(data[short], data[long_]):
                rows.append(dict(kind='两存', title=title(data[short]), keep=title(data[long_]),
                                 short=len(sb), long=len(lb), note='题名不是同一支曲，两存'))
                continue
            # 短的是长的一节（同章内按句对齐），或短的是长的开头
            # 戏文改本（同一支曲牌下的另一支）不算：两支长度相近、整句却对不上，
            # 逐句对齐只能靠「头 8 字」兜住，那不是同一支曲的两份录文
            coverage = clause_coverage(lb, sb)
            if not (lb.startswith(sb) or (subset_span(lb, sb) and coverage >= 0.5)):
                rows.append(dict(kind='两存', title=title(data[short]), keep=title(data[long_]),
                                 short=len(sb), long=len(lb),
                                 note='短的不是长的一节（同曲牌的另一支），两存'))
                continue
            drop.add(short)
            rows.append(dict(kind='删除', title=title(data[short]), keep=title(data[long_]),
                             short=len(sb), long=len(lb),
                             note='同一支曲长短两录，删短的（只录了其中一支）'))

    n = sum(r['kind'] == '删除' for r in rows)
    print(f'== 元曲长短两录：{len(rows)} 组，删 {n} 条、两存 {len(rows) - n} 组')
    with open(os.path.join(ROOT, args.out), 'w', encoding='utf-8', newline='') as fp:
        w = csv.DictWriter(fp, delimiter='\t', lineterminator='\n',
                           fieldnames=['kind', 'title', 'keep', 'short', 'long', 'note'])
        w.writeheader()
        w.writerows(rows)
    print(f'明细写入 {args.out}')

    if not args.apply:
        print('（预演，未改动任何文件；加 --apply 落盘）')
        return 0

    dump(YUANQU, [r for i, r in enumerate(data) if i not in drop])
    fixes = [dict(original=r['title'], corrected='删除',
                  note=f"与《{r['keep']}》是同一支曲的长短两录（{r['short']} 字 vs {r['long']} 字），删短的")
             for r in rows if r['kind'] == '删除']
    rec = pg.merge(YUANQU, dict(fixes=fixes))
    rec['note'] = ((rec.get('note') or '').rstrip() +
                   f' {args.date} 重复清理：删 {len(fixes)} 条「同一支曲长短两录」的短录，'
                   f'逐组见 {args.out}。').strip()
    pg.write_record(YUANQU, pg.ordered(rec))
    pg.write_index()
    print('进度记录 1 个文件')
    return 0


if __name__ == '__main__':
    sys.exit(main())
