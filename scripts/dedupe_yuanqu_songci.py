#!/usr/bin/env python3
"""元人词人在《元曲》里另存一条的：删《元曲》那一条，词归《全宋词》。

`元/元曲/yuanqu.json` 是元人诗词曲的唯一总集，但其中几位（汪元量、王奕、仇远）
本是宋末元初的词人，《全宋词》里各有一份，词牌在 `rhythmic` 上；《元曲》这份是把
同一首词题作诗题又收了一次，`rhythmic` 上是词牌或曲牌，`title` 上是词题：

```
宋/宋词/ci.song.18000.json#2a35g4   汪元量《望江南・忆江南》  54 字   ← 留
元/元曲/yuanqu.json#f13i6k          汪元量《幽州九日》        54 字   ← 删（同一首词）
```

判据（四条都要）：
1. 作者同一人；
2. 正文 `t2s` 归一去标点后相似度 ≥ 0.95（两读多是一字之差：`捻/拈`、`收/必`）；
3. 《元曲》那条的 `rhythmic` 与词那条的词牌主干相同（`望江南` / `望江南・忆江南`）；
4. 《元曲》那条不是套数曲（曲牌里带「・」按「宫调・曲牌」算，词牌的「・」是「本名・别名」，
   两者靠第 3 条区分：**词牌主干要在《全宋词》里出现过**）。

删《元曲》那条：词籍是这个词调的本来归属，`rhythmic` 是词牌、`title` 是词题；
《元曲》那份把词题写进 `title`、把词牌写进 `rhythmic`，正文用的是另一套录文（多不分句）。

**作者不同的一律两存**：`宋江《念奴娇》` 与 `施耐庵《念奴娇》` 是《水浒传》成书过程的归属异说。

用法：
  python3 scripts/dedupe_yuanqu_songci.py            # 预演
  python3 scripts/dedupe_yuanqu_songci.py --apply --date YYYY-MM-DD
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
from dedupe_tang_song import dump           # noqa: E402  按原排版写回，只让改动的几条进 diff

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
T2S = OpenCC('t2s')
HAN = re.compile(r'[^\u4e00-\u9fff]')
YUANQU = '元/元曲/yuanqu.json'
CI = '宋/宋词'
OUT = 'docs/元曲宋词去重.tsv'
PREFIX = 16
MIN_RATIO = 0.95
REVIEWER = 'codebuddy'


def han(s):
    return HAN.sub('', T2S.convert(s or ''))


def body(rec):
    return han(''.join(rec.get('paragraphs') or []))


# 词牌别名：《元曲》里作「一剪梅」，《全宋词》作「一翦梅」；「八声甘州」对「八声甘州」
ALIAS = {'一剪梅': '一翦梅', '忆江南': '望江南', '望江南': '望江南', '贺新郎': '金缕曲',
         '金缕曲': '金缕曲', '长相思': '长相思', '忆王孙': '忆王孙', '八声甘州': '八声甘州'}


def pai(rec):
    """词牌主干：「望江南・忆江南」→ 望江南；「八声甘州（题维扬摘星楼）」→ 八声甘州。

    《元曲》那份常把词题塞进 `rhythmic` 的括号里（`title` 是空），《全宋词》那份
    `rhythmic` 只有词牌，所以两边都要先把括号与「・」后缀去掉再比。
    """
    p = han(re.split(r'[（(]', rec.get('rhythmic') or '')[0] if False else re.split(r'[（(・]', rec.get('rhythmic') or '')[0])
    return ALIAS.get(p, p)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--apply', action='store_true')
    ap.add_argument('--date', default=date.today().isoformat())
    ap.add_argument('--reviewer', default=REVIEWER)
    ap.add_argument('--out', default=OUT)
    args = ap.parse_args()

    with open(os.path.join(ROOT, YUANQU), encoding='utf-8') as fp:
        yuan = json.load(fp)
    ci, recs = {}, []
    for f in sorted(glob.glob(os.path.join(ROOT, CI, 'ci.song.*.json'))):
        rel = os.path.relpath(f, ROOT)
        with open(f, encoding='utf-8') as fp:
            d = json.load(fp)
        if not isinstance(d, list):
            continue
        ci[rel] = d
        for i, r in enumerate(d):
            b = body(r)
            if len(b) >= PREFIX:
                recs.append((rel, i, r, b))
    index = collections.defaultdict(list)
    for x in recs:
        index[x[3][:PREFIX]].append(x)

    rows, drops, stat = [], set(), collections.Counter()
    for rec in yuan:
        b = body(rec)
        if len(b) < PREFIX:
            continue
        cands = [c for c in index.get(b[:PREFIX], []) if c[2].get('author') == rec.get('author')]
        if not cands:
            if index.get(b[:PREFIX]):
                stat['作者不同（两存）'] += 1
            continue
        # 先按词牌主干筛一遍：同一作者同一词牌往往有好几首，只比正文会在几首之间乱配
        same = [c for c in cands if pai(c[2]) == pai(rec)] or cands
        best = max(same, key=lambda c: difflib.SequenceMatcher(None, b, c[3]).ratio())
        ratio = difflib.SequenceMatcher(None, b, best[3]).ratio()
        t = f"{rec.get('author')}《{rec.get('title') or rec.get('rhythmic')}》"
        keep = f"{best[0]}#{best[1]} {best[2].get('author')}《{best[2].get('rhythmic')}》"
        if ratio < MIN_RATIO:
            stat['正文有出入（两存）'] += 1
            rows.append(dict(kind='两存', title=t, keep=keep, ratio=f'{ratio:.3f}',
                             note='正文对不上，不是同一首'))
            continue
        if not pai(rec) or not any(pai(c[2]) == pai(rec) for c in same):
            stat['曲牌与词牌不同（两存）'] += 1
            rows.append(dict(kind='两存', title=t, keep=keep, ratio=f'{ratio:.3f}',
                             note=f'曲牌 {pai(rec)} 与词牌 {pai(best[2])} 不是同一个调子'))
            continue
        drops.add(rec.get('id'))
        stat['删《元曲》那一条'] += 1
        rows.append(dict(kind='删除', title=t, keep=keep, ratio=f'{ratio:.3f}',
                         note='同一首词，《全宋词》有词牌与词题，删《元曲》那份'))

    print(f'== 《元曲》与《全宋词》互见：{len(yuan)} 条里')
    for k, v in stat.most_common():
        print(f'   {k:<22} {v}')
    print(f'   拟删 {len(drops)} 条')

    with open(os.path.join(ROOT, args.out), 'w', encoding='utf-8', newline='') as fp:
        w = csv.DictWriter(fp, delimiter='\t', lineterminator='\n',
                           fieldnames=['kind', 'title', 'keep', 'ratio', 'note'])
        w.writeheader()
        w.writerows(rows)
    print(f'明细写入 {args.out}')

    if not args.apply:
        for r in rows:
            print(f"   {r['kind']} {r['title'][:26]:<26} ← {r['keep'][:52]}  {r['ratio']}")
        print('（预演，未改动任何文件；加 --apply 落盘）')
        return 0

    dump(YUANQU, [r for r in yuan if r.get('id') not in drops])
    fixes = [dict(original=r['title'], corrected='删除',
                  note=f"[yuanqu-songci] {r['note']}；留 {r['keep']}，见 {args.out}")
             for r in rows if r['kind'] == '删除']
    rec = pg.merge(YUANQU, dict(fixes=fixes))
    rec['note'] = ((rec.get('note') or '').rstrip() +
                   f' {args.date} 重复清理：删 {len(fixes)} 条与《全宋词》同首的词，'
                   f'逐条见 {args.out}。').strip()
    pg.write_record(YUANQU, pg.ordered(rec))
    pg.write_index()
    print(f'进度记录 1 个文件（{len(yuan)} → {len(yuan) - len(drops)} 条）')
    return 0


if __name__ == '__main__':
    sys.exit(main())
