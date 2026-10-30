#!/usr/bin/env python3
"""`三国/诗/poet.sanguo.json` 里转载的选本篇目：删补录那条，选本不动。

`poet.sanguo.json` 40 条，是从《历代》拆出来的补录（诗与文混放，没有底本信息）。
里面有一批是从《昭明文选》《乐府诗集》《古文观止》《课本选目》《古诗源》里转载的：

```
汇编/昭明文选/诗·杂诗上.json#…   曹子建《情詩》   60 字   ← 留（选本有底本、有编次）
三国/诗/poet.sanguo.json#…       曹植《情诗》     60 字   ← 删（补录转载）
```

按 [`汇编与诗去重`](汇编与诗去重.md) 的口径：选本收总集/别集是编书方式，删的是**补录**那份。

判据（三条都要）
----------------
1. 作者同一人（`曹植／曹子建`、`曹丕／魏文帝` 这类「名／字、名／谥号」按别名表归一）；
2. 题名对得上（`t2s` 归一后相等，或补录多一个「（并序）」这类后缀、选本多一个书名前缀）；
3. 正文相似度 ≥ 0.95 —— 一字之差多是两读并传的异文（`是/自`、`遥/徭`、`治/冶`），
   这里放行是因为补录是转载件：转载件的正文不是独立来源，异文以选本底本为准。

**两条与上面相反，一条不动**：
- 选本的一条是**并合件**（《昭明文選·騷》把《九歌》四首、《九章》合成一条，853 字 vs 1741 字），
  补录逐首一条 —— 那是编法，不是同一件作品的两种录文；
- 选本的正文与补录差得远（相似度 < 0.95）。

用法：
  python3 scripts/dedupe_sanguo_huibian.py            # 预演
  python3 scripts/dedupe_sanguo_huibian.py --apply --date YYYY-MM-DD
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
POET = '三国/诗/poet.sanguo.json'
HUI = '汇编'
OUT = 'docs/三国汇编去重.tsv'
PREFIX = 16
MIN_RATIO = 0.95
REVIEWER = 'codebuddy'
# 名 / 字 / 谥号
ALIAS = {'曹子建': '曹植', '魏文帝': '曹丕', '魏武帝': '曹操', '曹子桓': '曹丕',
         '諸葛亮': '诸葛亮', '屈平': '屈原', '宋玉': '宋玉', '蘇子卿': '蘇武'}


def han(s):
    return HAN.sub('', T2S.convert(s or ''))


def body(rec):
    p = rec.get('paragraphs')
    if isinstance(p, list) and p and all(isinstance(x, str) for x in p):
        return han(''.join(p))
    return ''


def walk(node, rel, path=()):
    if isinstance(node, dict):
        p = node.get('paragraphs')
        if isinstance(p, list) and p and all(isinstance(x, str) for x in p):
            yield rel, path, node
            return
        for k, v in node.items():
            if isinstance(v, (list, dict)):
                yield from walk(v, rel, path + (k,))
    elif isinstance(node, list):
        for i, v in enumerate(node):
            yield from walk(v, rel, path + (i,))


def author(rec):
    a = han(rec.get('author') or '')
    return ALIAS.get(a, a)


def title(rec):
    t = han(rec.get('title') or rec.get('chapter') or '')
    return re.sub(r'并序$|有序$', '', t)


def dump(rel, data):
    """写回，只让删掉的记录进 diff（同 scripts/dedupe_huibian_poet.py）。"""
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
    try:
        json.loads(text)
    except ValueError:
        text = out
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

    with open(os.path.join(ROOT, POET), encoding='utf-8') as fp:
        poet = json.load(fp)
    hui = []
    for f in sorted(glob.glob(os.path.join(ROOT, HUI, '**', '*.json'), recursive=True)):
        rel = os.path.relpath(f, ROOT)
        if rel.endswith('古文观止·选目.json'):
            continue
        with open(f, encoding='utf-8') as fp:
            node = json.load(fp)
        for r, path, rec in walk(node, rel):
            b = body(rec)
            if len(b) >= PREFIX:
                hui.append((r, path, rec, b))
    index = collections.defaultdict(list)
    for x in hui:
        index[x[3][:PREFIX]].append(x)

    rows, drops, stat = [], set(), collections.Counter()
    for i, rec in enumerate(poet):
        b = body(rec)
        if len(b) < PREFIX:
            continue
        cands = index.get(b[:PREFIX], [])
        if not cands:
            continue
        cands = [c for c in cands if author(c[2]) == author(rec)]
        if not cands:
            stat['作者不同（两存）'] += 1
            continue
        best = max(cands, key=lambda c: difflib.SequenceMatcher(None, b, c[3]).ratio())
        ratio = difflib.SequenceMatcher(None, b, best[3]).ratio()
        t = f"{rec.get('author')}《{rec.get('title') or rec.get('chapter')}》"
        keep = f"{best[0]}#{'/'.join(map(str, best[1]))} {best[2].get('author')}《{best[2].get('title') or best[2].get('chapter')}》"
        if len(best[3]) > len(b) * 2:
            stat['选本是并合件（两存）'] += 1
            rows.append(dict(kind='两存', title=t, keep=keep, ratio=f'{ratio:.3f}',
                             note='选本一条并合了多首（编法），补录逐首一条，不删'))
            continue
        if ratio < MIN_RATIO:
            stat['正文对不上（两存）'] += 1
            rows.append(dict(kind='两存', title=t, keep=keep, ratio=f'{ratio:.3f}',
                             note='正文对不上，不是同一件作品的两种录文'))
            continue
        if not (title(rec) == title(best[2]) or title(best[2]).endswith(title(rec))
                or title(rec).endswith(title(best[2]))):
            stat['题名对不上（两存）'] += 1
            rows.append(dict(kind='两存', title=t, keep=keep, ratio=f'{ratio:.3f}',
                             note='题名对不上'))
            continue
        drops.add(rec.get('id'))
        stat['删补录转载件'] += 1
        rows.append(dict(kind='删除', title=t, keep=keep, ratio=f'{ratio:.3f}',
                         note='选本收别集是编书方式，删补录那份'))

    print(f'== {POET}（{len(poet)} 条）与 汇编/ 互见：')
    for k, v in stat.most_common():
        print(f'   {k:<20} {v}')
    print(f'   拟删 {len(drops)} 条')

    with open(os.path.join(ROOT, args.out), 'w', encoding='utf-8', newline='') as fp:
        w = csv.DictWriter(fp, delimiter='\t', lineterminator='\n',
                           fieldnames=['kind', 'title', 'keep', 'ratio', 'note'])
        w.writeheader()
        w.writerows(rows)
    print(f'明细写入 {args.out}')

    if not args.apply:
        for r in rows:
            print(f"   {r['kind']} {r['title']:<20} ← {r['keep'][:60]}  {r['ratio']}")
        print('（预演，未改动任何文件；加 --apply 落盘）')
        return 0

    dump(POET, [r for r in poet if r.get('id') not in drops])
    fixes = [dict(original=r['title'], corrected='删除',
                  note=f"[sanguo-huibian] {r['note']}；留 {r['keep']}，见 {args.out}")
             for r in rows if r['kind'] == '删除']
    rec = pg.merge(POET, dict(fixes=fixes))
    rec['note'] = ((rec.get('note') or '').rstrip() +
                   f' {args.date} 重复清理：删 {len(fixes)} 条转载自汇编选本的篇目，'
                   f'逐条见 {args.out}。').strip()
    pg.write_record(POET, pg.ordered(rec))
    pg.write_index()
    print(f'进度记录 1 个文件（{len(poet)} → {len(poet) - len(drops)} 条）')
    return 0


if __name__ == '__main__':
    sys.exit(main())
