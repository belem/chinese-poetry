#!/usr/bin/env python3
"""张岱《陶庵梦忆》散篇在 `poet.ming.json`／`ci.ming.json` 里的副本：删，留单行本。

```json
明/小说/陶庵梦忆/taoanzhmyi.json#11  张岱《陶庵梦忆·卷一·木猶龍》   ← 留
明/诗/poet.ming.json#266            张岱《陶庵梦忆·卷一·木犹龙》   ← 删
```

`poet.ming.json`／`ci.ming.json` 是从 `历代/` 拆出来的补录，混进了《陶庵梦忆》的
6 篇散记（木犹龙、吴中绝技、扬州清明、西湖香市、龙山雪、西湖七月半）。整部书另在
`明/小说/陶庵梦忆/`。按「一件作品只留一份正文」删补录那份 —— 而且这些是**散文**，
挂在「诗」「词」目录下本来就不对。

判据：作者相同、题名去掉繁简差异后相同（补录把 `猶/犹`、`絶/绝`、`揚/扬` 转成了简体）、
正文相似度 ≥ 0.95。

同一批里还有三条不该在这一批动的，逐条说明：

- `水浒传` 第 41 回里引的苏轼《念奴娇·赤壁怀古》—— 小说引用诗词，不是重复，
  小说正文也不能为去重而改。
- 《陶庵梦忆·卷七·龍山雪》与补录的《陶庵梦忆·卷七·浴雪龙山》题名不同、正文差两字，
  是两篇还是同一篇的两读，未核，两存。

用法：
  python3 scripts/dedupe_taoanzhmyi.py            # 预演
  python3 scripts/dedupe_taoanzhmyi.py --apply --date YYYY-MM-DD --reviewer <名字>
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
KEEP = '明/小说/陶庵梦忆/taoanzhmyi.json'
BOOKS = ['明/诗/poet.ming.json', '明/词/ci.ming.json']
OUT = 'docs/陶庵梦忆去重.tsv'
# 《陶庵梦忆》的篇章与补录那份题名逐字相同（「陶庵梦忆·卷七·西湖香市」），
# 可以直接按题名配对，不必借正文前 N 字；正文相似度只用来判「是不是同一篇」。
MIN_RATIO = 0.95


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


# 题名不同、正文能对上的两篇：补录把篇题拆错了（《龍山雪》记成《浴雪龙山》，
# 卷七一题两记），按正文相似度 ≥ 0.95 判同一篇。（宋/宋词 那篇《西湖七月半》
# 与《陶庵梦忆》的篇名一致，走上面的题名配对。）
ALSO = [
    ('明/诗/poet.ming.json', '陶庵梦忆·卷七·浴雪龙山', '陶庵梦忆·卷七·龍山雪'),
    ('明/词/ci.ming.json', '西湖七月半', '陶庵梦忆·卷七·西湖七月半'),
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--apply', action='store_true')
    ap.add_argument('--date', default=date.today().isoformat())
    ap.add_argument('--reviewer', default='codebuddy')
    ap.add_argument('--out', default=OUT)
    args = ap.parse_args()

    keep = load(KEEP)
    idx = {}
    for i, r in enumerate(keep):
        idx.setdefault((r.get('author'), T2S.convert((r.get('title') or '').strip())), []).append((i, r))

    rows, drops = [], {}
    for book in BOOKS:
        data = load(book)
        for i, r in enumerate(data):
            b = body(r)
            if not b or '陶庵梦忆' not in (r.get('title') or ''):
                continue
            # 题名繁简不同（补录作「木犹龙」，单行本作「木猶龍」），按 t2s 后的题名配对
            key = (r.get('author'), T2S.convert((r.get('title') or '').strip()))
            cands = idx.get(key, [])
            if not cands:
                continue
            best = max(cands, key=lambda c: difflib.SequenceMatcher(None, body(c[1]), b).ratio())
            ratio = difflib.SequenceMatcher(None, body(best[1]), b).ratio()
            if ratio < MIN_RATIO:
                print(f'   两存 {r.get("title")}：ratio={ratio:.3f}（与《{best[1].get("title")}》不是同一篇）')
                continue
            drops.setdefault(book, set()).add(r.get('id'))
            rows.append(dict(keep=f"{KEEP}#{best[0]} {best[1].get('author')}《{best[1].get('title')}》",
                             drop=f"{book}#{i} {r.get('author')}《{r.get('title')}》",
                             ratio=f'{ratio:.3f}'))

    for book, dtitle, ktitle in ALSO:
        data = load(book)
        cand = [r for r in data if (r.get('title') or '') == dtitle]
        kept = [(i, r) for i, r in enumerate(keep) if (r.get('title') or '') == ktitle]
        if not cand or not kept:
            print(f'   已删过或找不到：{dtitle}')
            continue
        r, (i, kr) = cand[0], kept[0]
        ratio = difflib.SequenceMatcher(None, body(kr), body(r)).ratio()
        if ratio < MIN_RATIO:
            print(f'   两存 {dtitle}：ratio={ratio:.3f}')
            continue
        drops.setdefault(book, set()).add(r.get('id'))
        rows.append(dict(keep=f"{KEEP}#{i} {kr.get('author')}《{kr.get('title')}》",
                         drop=f"{book} {r.get('author')}《{dtitle}》", ratio=f'{ratio:.3f}'))

    print(f'== 《陶庵梦忆》副本：{len(rows)} 条')
    for r in rows:
        print(f"   删 {r['drop'][:56]:<56} ← 留 {r['keep'][:44]}  {r['ratio']}")

    if not args.apply:
        print('\n（预演，未改动文件；加 --apply 落盘）')
        return

    fixes = {}
    for book, ids in drops.items():
        data = load(book)
        gone = [r for r in data if r.get('id') in ids]
        dump(book, [r for r in data if r.get('id') not in ids])
        fixes[book] = [dict(original=f"{r.get('id')} {r.get('author')}《{r.get('title')}》",
                            corrected='删除',
                            note='[taoanzhmyi] 与《陶庵梦忆》单行本重出（且是散文，不宜挂在诗/词目录下），删补录那份')
                       for r in gone]

    with open(os.path.join(ROOT, args.out), 'w', encoding='utf-8', newline='') as fp:
        w = csv.writer(fp, delimiter='\t', lineterminator='\n')
        w.writerow(['保留', '重复', '相似度', '处理'])
        for r in rows:
            w.writerow([r['keep'], r['drop'], r['ratio'], '删补录那份，留《陶庵梦忆》单行本'])
    print(f'明细写入 {args.out}')

    for book, items in fixes.items():
        rec = pg.merge(book, dict(fixes=items, date=args.date, reviewer=args.reviewer))
        rec['note'] = ((rec.get('note') or '').rstrip() +
                       f' {args.date} 删 {len(items)} 条《陶庵梦忆》副本，逐条见 {args.out}。').strip()
        pg.write_record(book, pg.ordered(rec))
    pg.write_index()
    print(f'进度记录 {len(fixes)} 个文件')


if __name__ == '__main__':
    main()
