#!/usr/bin/env python3
"""`唐/词/ci.tang.json` 里的词，《全唐诗》也收了一遍：删 `ci.tang.json` 那份。

`唐/词/ci.tang.json` 是从《历代》拆出来的唐五代词补录（30 条），
《全唐诗》末几卷按「雜歌謠辭」「曲子詞」的路子把不少词也收进去了：

```
唐/诗/全唐诗/poet.tang.49000.json#411  呂巖《蘇幙遮》   61 字   ← 留
唐/词/ci.tang.json#24                  吕岩《苏幕遮》   62 字   ← 删
```

## 为什么留《全唐诗》那份

《全唐诗》是整部总集，一条一页、有 `title` 与卷次编次；`ci.tang.json` 是拆出来的补录，
`title` 字段是 `null`（词牌写在 `rhythmic` 里）。按「一件作品只留一份正文」，留总集、删补录。
删之前把补录那条的 `rhythmic` 记进总集那条的 `tags`，别丢了「这是词牌」这层信息。

## 判据

1. 正文 `t2s` 归一、去标点后前 16 字相同（`check_tree.py` 的候选口径）；
2. 作者同一人（繁简归一后比，`呂巖／吕岩` 是同一人）；
3. 等长（±2 字）且相似度 ≥ 0.90 —— 两边断句不同，只差通用字：
   `浮沉／浮沈`、`走遍／走徧`、`啼猿／啼猨`、`岩花／嵓花`、
   《苏幕遮》那条《全唐诗》多一个「鼎」（「这箇鼎解不解」）、
   《雨中花慢》那条《全唐诗》多一个「輧」；
4. 不是「总集只收了其中一首」：补录那条不比总集那条长一倍以上
   （《忆江南三首》81 字 vs 总集《憶江南 一》27 字、《长相思》两首 72 vs 36，这类反着留）。

用法：
  python3 scripts/dedupe_tangci_shi.py            # 预演：逐组打印
  python3 scripts/dedupe_tangci_shi.py --apply --date YYYY-MM-DD --reviewer <名字>
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
SHI = '唐/诗/全唐诗/poet.tang.*.json'
CI = '唐/词/ci.tang.json'
OUT = 'docs/唐词全唐诗去重.tsv'
MIN_RATIO = 0.90
MAX_SHI_RATIO = 0.75        # 总集那条不到补录的一半 → 只收了其中一首，反着留


def han(s):
    return HAN.sub('', T2S.convert(s or ''))


def body(rec):
    p = rec.get('paragraphs')
    return han(p if isinstance(p, str) else ''.join(p or ''))


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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--apply', action='store_true')
    ap.add_argument('--date', default=date.today().isoformat())
    ap.add_argument('--reviewer', default='codebuddy')
    ap.add_argument('--out', default=OUT)
    args = ap.parse_args()

    import glob
    shi = []
    for rel in sorted(glob.glob(os.path.join(ROOT, SHI))):
        rel = os.path.relpath(rel, ROOT)
        for i, rec in enumerate(load(rel)):
            b = body(rec)
            if len(b) >= 16:
                shi.append((rel, i, rec, b))
    index = {}
    for rel, i, rec, b in shi:
        index.setdefault(b[:16], []).append((rel, i, rec, b))

    rows, drops = [], set()
    for ci, rec in enumerate(load(CI)):
        b = body(rec)
        if len(b) < 16:
            continue
        for rel, i, other, ob in index.get(b[:16], []):
            if han(rec.get('author')) != han(other.get('author')):
                continue
            ratio = difflib.SequenceMatcher(None, b, ob, autojunk=False).ratio()
            # 补录那条总是多一两句（「何日更重游」「空房独守时」），所以允许它长到 1.6 倍
            same = len(b) <= len(ob) * 1.6 and ratio >= MIN_RATIO
            keep_ci = same and len(b) * MAX_SHI_RATIO > len(ob)
            if keep_ci:
                # 总集那条只收了其中一首 —— 反着来：留补录、删总集（本批不做，只记下来）
                rows.append(dict(ci=ci, rec=rec, rel=rel, index=i, other=other, ratio=ratio,
                                 dup=False, why='总集只收了其中一首，宜删总集那条'))
                continue
            rows.append(dict(ci=ci, rec=rec, rel=rel, index=i, other=other, ratio=ratio,
                             dup=same and not keep_ci))

    dup = [r for r in rows if r['dup']]
    print(f'== 唐词与《全唐诗》重出：{len(rows)} 组，删 {len(dup)} 条补录')
    for r in rows:
        print(f"   {'删' if r['dup'] else '存'} ci.tang#{r['ci']} {r['rec'].get('author')}"
              f"《{r['rec'].get('rhythmic')}》{len(body(r['rec']))} 字"
              f" ←→ {r['rel'].split('/')[-1]}#{r['index']}《{r['other'].get('title')}》"
              f"{len(body(r['other']))} 字  {r['ratio']:.3f}")

    if not args.apply:
        print('（预演，未改动任何文件；加 --apply 落盘）')
        return 0

    tags = {}
    for r in dup:
        if r['rec'].get('rhythmic'):
            tags.setdefault((r['rel'], r['index']), []).append(r['rec']['rhythmic'])
    for (rel, i), names in tags.items():
        data = load(rel)
        rec = dict(data[i])
        t = list(rec.get('tags') or [])
        for n in names:
            if n not in t:
                t.append(n)
        if t:
            rec['tags'] = t
        data[i] = rec
        dump(rel, data)

    ci_data = load(CI)
    dump(CI, [r for i, r in enumerate(ci_data) if i not in {r2['ci'] for r2 in dup}])

    with open(os.path.join(ROOT, args.out), 'w', encoding='utf-8', newline='') as fp:
        w = csv.writer(fp, delimiter='\t', lineterminator='\n')
        w.writerow(['保留', '重复', '相似度', '处理'])
        for r in rows:
            w.writerow([f"{r['rel']}#{r['index']} {r['other'].get('author')}《{r['other'].get('title')}》",
                        f"{CI}#{r['ci']} {r['rec'].get('author')}《{r['rec'].get('rhythmic')}》",
                        f"{r['ratio']:.3f}",
                        '删补录那条，词牌记进总集 tags' if r['dup']
                        else r.get('why') or '两存：正文有出入'])
    print(f'明细写入 {args.out}')

    rec = pg.merge(CI, dict(fixes=[dict(
        original=f"#{r['ci']} {r['rec'].get('author')}《{r['rec'].get('rhythmic')}》", corrected='删除',
        note=f"与《全唐诗》{r['rel']}#{r['other'].get('id')}《{r['other'].get('title')}》同篇，留总集；见 {args.out}")
        for r in dup], date=args.date, reviewer=args.reviewer))
    rec['note'] = ((rec.get('note') or '').rstrip() +
                   f" {args.date} 删 {len(dup)} 条与《全唐诗》重出的词。").strip()
    pg.write_record(CI, pg.ordered(rec))
    pg.write_index()
    return 0


if __name__ == '__main__':
    sys.exit(main())
