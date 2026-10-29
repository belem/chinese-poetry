#!/usr/bin/env python3
"""《幽梦影》在 `清/诗/poet.qing.json` 里的一整套副本：删副本，留 `清/幽梦影/youmengying.json`。

`poet.qing.json` 是《历代》按作者朝代拆出来的补录（正文来自 海棠诗社语料），里面混进了
张潮《幽梦影》的 227 条：题名一律「幽梦影·卷一·其一」这种，正文是各条的语录。
整部书已在 `清/幽梦影/youmengying.json` 收全（219 条，带 `comment` 评语），
按「一件作品只留一份正文」删掉 `poet.qing.json` 里那一套。

判据（三条都要）：

1. 题名以「幽梦影」开头；
2. 与《幽梦影》某条正文**逐字相同**（t2s、去非汉字之后），或**是它的一段**（子序列）——
   子序列那几条是 `poet.qing.json` 摘了半条（「花与叶俱可观者…」之于「花之宜于目而复宜于鼻者…」
   那一整条），摘录不是另一种版本；
3. 对应的《幽梦影》那条本身不比它短（否则是副本更全，留给人工）。

不删的两类：

- 「序·一」「跋·一」四条：《幽梦影》那本没收序跋，删了就丢正文；
- 找不到对应的：两存，记进 TSV 待核。

用法：
  python3 scripts/dedupe_youmengying.py                       # 预演
  python3 scripts/dedupe_youmengying.py --apply --date YYYY-MM-DD
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
QING = '清/诗/poet.qing.json'
YMY = '清/幽梦影/youmengying.json'
OUT = 'docs/幽梦影去重.tsv'
REVIEWER = 'codebuddy'
BOOK = '幽梦影'


def dump(rel, data):
    """写回，且只让「删掉的记录」进 diff（与 scripts/dedupe_songci_full.py 同一份写法）。

    原文按「`\n` + 缩进 + `{`」切成每条记录一段，重新序列化后逐条对回来 —— 记录只是删、
    不改，两端一次单调对齐即可。对得上的段整段照抄原文（行尾空格随原文），
    删掉的段整段不进输出。
    """
    path = os.path.join(ROOT, rel)
    raw = open(path, encoding='utf-8').read()
    m = re.search(r'\n( +)\S', raw)
    indent = len(m.group(1)) if m else 2
    out = json.dumps(data, ensure_ascii=False, indent=indent) + ('\n' if raw.endswith('\n') else '')
    sep = '\n' + ' ' * indent + '{'
    head, *old = raw.split(sep)
    _, *new = out.split(sep)
    if len(new) == len(old):
        text = raw                            # 没删条（重跑），原文一字不动
    else:
        def same(x, y):
            a, b = x.split('\n'), y.split('\n')
            return len(a) == len(b) and all(p.rstrip(' ') == q.rstrip(' ') for p, q in zip(a, b))

        res, i, j = [head], 0, 0
        while j < len(new) and i < len(old):
            if same(old[i], new[j]):
                res.append(old[i])
                i, j = i + 1, j + 1
            else:
                i += 1                        # 老的这条在新输出里没有 = 删掉的
        res.extend(old[i:])                   # 末尾没动过的几条照抄（收尾的 `]` 在最后一条里）
        text = sep.join(res)
    if text != raw:
        with open(path, 'w', encoding='utf-8') as fp:
            fp.write(text)


def han(s):
    return HAN.sub('', T2S.convert(s or ''))


def body(rec):
    p = rec.get('paragraphs')
    return han(p if isinstance(p, str) else ''.join(p or []))


def differs_within(a, b, limit):
    """两串等长（或差不到 limit 字）时，不同的字不超过 limit 个。"""
    import difflib
    sm = difflib.SequenceMatcher(None, a, b, autojunk=False)
    return sum(max(i2 - i1, j2 - j1) for tag, i1, i2, j1, j2 in sm.get_opcodes() if tag != 'equal') <= limit


def subsequence(short, long_):
    """短的每一句都按序在长的里出现（摘条、去评语都算）。"""
    pos = 0
    for part in re.split(r'(?<=[。？！；])', short):
        part = han(part)
        if not part:
            continue
        k = long_.find(part, pos)
        if k < 0:
            return False
        pos = k + len(part)
    return pos > 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--apply', action='store_true')
    ap.add_argument('--date', default=date.today().isoformat())
    ap.add_argument('--reviewer', default=REVIEWER)
    ap.add_argument('--out', default=OUT)
    args = ap.parse_args()

    qing = json.load(open(os.path.join(ROOT, QING), encoding='utf-8'))
    book = json.load(open(os.path.join(ROOT, YMY), encoding='utf-8'))
    by_body = collections.defaultdict(list)
    for y in book:
        by_body[body(y)].append(y)

    drop, rows = set(), []
    for i, rec in enumerate(qing):
        title = str(rec.get('title') or '')
        if not title.startswith(BOOK):
            continue
        b = body(rec)
        if not b:
            continue
        hit = by_body.get(b)
        why = '正文逐字相同'
        if not hit:
            hit, why = None, ''
            for y in book:
                yb = body(y)
                if yb.startswith(b) or b.startswith(yb):
                    hit = [y]                     # 一头是另一头的前缀（「畅／物」这类一字之差也到这里）
                    why = ('是《幽梦影》某条的一段（摘录）' if len(b) < len(yb)
                           else '正文与《幽梦影》某条一字之差，取整部书那本的正文')
                    break
        if not hit and not re.search(r'[序跋]', title):
            # 抄错一两个字的那几条（「其机畅也」对「其机物也」、「欸乃」对「欺乃」）：
            # 长度相当、整句对得上的只有一处出入，就算同一条
            for y in book:
                yb = body(y)
                if abs(len(yb) - len(b)) <= 1 and differs_within(b, yb, 2):
                    hit = [y]
                    why = '正文与《幽梦影》某条一字之差，取整部书那本的正文'
                    break
        if not hit:
            hit = [y for y in book if subsequence(b, body(y))]
            why = '每句都见于《幽梦影》某条（摘句）'
        if not hit:
            rows.append(dict(kind='两存', title=title, length=len(b),
                             keep='', note='《幽梦影》里找不到对应的一条，留待核'))
            continue
        keep = hit[0]
        if re.search(r'[序跋]', title):
            rows.append(dict(kind='两存', title=title, length=len(b),
                             keep=f'{YMY} id={keep.get("id")}',
                             note='《幽梦影》那本未收序跋，删了会丢正文'))
            continue
        drop.add(i)
        rows.append(dict(kind='删除', title=title, length=len(b),
                         keep=f'{YMY} id={keep.get("id")}', note=why))

    n = sum(r['kind'] == '删除' for r in rows)
    print(f'== 《幽梦影》副本：poet.qing.json 里 {len(rows)} 条，删 {n} 条、两存 {len(rows) - n} 条')

    with open(os.path.join(ROOT, args.out), 'w', encoding='utf-8', newline='') as fp:
        w = csv.DictWriter(fp, delimiter='\t', lineterminator='\n',
                           fieldnames=['kind', 'title', 'length', 'keep', 'note'])
        w.writeheader()
        w.writerows(rows)
    print(f'明细写入 {args.out}')

    if not args.apply:
        print('（预演，未改动任何文件；加 --apply 落盘）')
        return 0

    dump(QING, [r for i, r in enumerate(qing) if i not in drop])
    fixes = [dict(original=r['title'], corrected='删除',
                  note=f"与 {r['keep']} 重出（{r['note']}），整部书见 {YMY}")
             for r in rows if r['kind'] == '删除']
    rec = pg.merge(QING, dict(fixes=fixes))
    rec['note'] = ((rec.get('note') or '').rstrip() +
                   f' {args.date} 重复清理：删 {len(fixes)} 条《幽梦影》副本（整部书见 {YMY}），'
                   f'逐条见 {args.out}。').strip()
    pg.write_record(QING, pg.ordered(rec))
    pg.write_index()
    print(f'进度记录 1 个文件')
    return 0


if __name__ == '__main__':
    sys.exit(main())
