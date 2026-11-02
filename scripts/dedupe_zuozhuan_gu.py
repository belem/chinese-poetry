#!/usr/bin/env python3
"""《左傳》整本与《古文观止》里同题的篇目：删**选本**那一份，正文只留整本。

2026-11 起 `先秦/文/zuozhuan.json`（278 条按选本篇目排的散录）已整份删除，
改由 `reference/二十四史/春秋左氏传.txt` 整本重出为 `史书/春秋左氏传/zuozhuan.json`
（十二公二百五十五年，见 `docs/春秋左氏传重建.md`）。那时起判据也换了：不再要求
「`t2s` 归一后一字不差」——选本是繁体无书名号、整本是简体有书名号，一字不差从来不是常态；
改判「正文是否出在这部书里」，办法是拿选本篇目去整本里做六字窗覆盖，过半即同篇。

```
史书/春秋左氏传/zuozhuan.json#47gj1l  《左傳·隐公·隐公元年》        ← 留
汇编/古文观止/卷一周文.json#d66698     左丘明《鄭伯克段于鄢》         ← 删（正文即隐公元年那一节）
```

《古文观止》这一层目录记的是「古文观止收了哪几篇」——删掉整条会丢这条信息，
所以 `汇编/古文观止/古文观止·选目.json` 里那 34 条的「记录」改指 `zuozhuan.json#<新 id>`，
正文只有整本那一份。

**《國語》不动。** `卷二周文.json` 里署左丘明的那 12 篇，11 篇出《國語》、1 篇是《穀梁傳》本，
覆盖新《左傳》的上限只有 0.01，不属于这一批。

用法：
  python3 scripts/dedupe_zuozhuan_gu.py            # 预演：逐组打印
  python3 scripts/dedupe_zuozhuan_gu.py --apply --date YYYY-MM-DD --reviewer <名字>
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
GU_DIR = '汇编/古文观止'
TOC = '汇编/古文观止/古文观止·选目.json'
BOOK = '史书/春秋左氏传/zuozhuan.json'
WINDOW = 6            # 六字窗覆盖率：选本正文有多少落在整本里
# 过此即为同篇。《國語》诸篇上限 0.013；《穀梁傳》的《虞師晉師滅夏陽》0.053；
# 《左傳》卷一诸篇下限 0.11。《穀梁傳》那篇与《左傳》讲同一件史事、措辞全出《穀梁》，
# 既不是《左傳》的摘录，也不能因为讲了同一件事就被删，阈值卡在它之上。
THRESHOLD = 0.10
FILES = ['卷一周文.json', '卷二周文.json']


def han(s):
    return HAN.sub('', T2S.convert(s or ''))


def body(rec):
    """`t2s` 之后的正文字符（去标点）。"""
    p = rec.get('paragraphs')
    return han(p if isinstance(p, str) else ''.join(p or []))


def cover(text, hay):
    """text 有多少字落在 hay 里（按六字窗）。"""
    n, hit, i = len(text), 0, 0
    while i + WINDOW <= n:
        if text[i:i + WINDOW] in hay:
            hit += WINDOW
            i += WINDOW
        else:
            i += 1
    return hit




def load(rel):
    with open(os.path.join(ROOT, rel), encoding='utf-8') as fp:
        return json.load(fp)


def dump(rel, data):
    path = os.path.join(ROOT, rel)
    raw = open(path, encoding='utf-8').read() if os.path.exists(path) else ''
    m = re.search(r'\n( +)\S', raw)
    indent = len(m.group(1)) if m else 2
    out = json.dumps(data, ensure_ascii=False, indent=indent) + ('\n' if raw.endswith('\n') else '')
    src = raw.split('\n')
    out = '\n'.join(r + (' ' if i < len(src) - 1 and src[i].endswith(' ') else '')
                    for i, r in enumerate(out.split('\n')))
    with open(path, 'w', encoding='utf-8') as fp:
        fp.write(out)


def one(args, toc):
    """跑一批：返回 (rows, left)，未 apply 时不落盘。"""
    base = load(BOOK)
    hay, idx = {}, {}
    for rec in base:
        hay[rec['id']] = body(rec)
        idx.setdefault(han(rec.get('title')), rec)
    # 整本的全文串：选本篇目散在一年的几段里，按句窗找即可
    whole = ''.join(hay.values())

    rows, left, drops, files = [], [], {}, {}
    for name in FILES:
        rel = f"{GU_DIR}/{name}"
        files[rel] = load(rel)
        for i, rec in enumerate(files[rel]):
            t = body(rec)
            if not t:
                continue
            best, best_hit = None, 0
            # 逐年算覆盖，取最高的一年作为「出处在哪」
            for rid, hay_y in hay.items():
                h = cover(t, hay_y)
                if h > best_hit:
                    best, best_hit = rid, h
            ratio = best_hit / len(t)
            item = dict(keep_id=best, drop=rec, rel=rel, index=i, ratio=ratio,
                        ratio_whole=cover(t, whole) / len(t))
            (rows if ratio > THRESHOLD else left).append(item)

    print(f"== 《左傳》：扫 {len(FILES)} 卷，判同篇 {len(rows)} 篇、非同篇 {len(left)} 篇")
    for r in rows:
        print(f"   删 {r['rel'].split('/')[-1]}#{r['index']} 《{r['drop'].get('title')}》"
              f" ← 留 {BOOK} {r['keep_id']}  cover={r['ratio']:.3f}")
    for r in left:
        print(f"   留 {r['rel'].split('/')[-1]}#{r['index']} 《{r['drop'].get('title')}》"
              f"  cover={r['ratio']:.3f}（不出《左傳》）")
    if not args.apply:
        return rows, left

    if rows:
        have = {(t['卷次'], t['篇目']) for t in toc}
        for r in rows:
            key = (r['rel'].split('/')[-1], r['drop'].get('title'))
            if key in have:
                # 已登记过，只把「记录」改指整本
                for t in toc:
                    if (t['卷次'], t['篇目']) == key:
                        t['记录'] = f"zuozhuan.json#{r['keep_id']}"
                continue
            toc.append({'卷次': key[0], '篇目': key[1], '作者': r['drop'].get('author'),
                        '记录': f"zuozhuan.json#{r['keep_id']}"})
            have.add(key)

    for r in rows:
        drops.setdefault(r['rel'], set()).add(r['index'])
    for rel in sorted(drops):
        dump(rel, [rec for i, rec in enumerate(files[rel]) if i not in drops[rel]])

    with open(os.path.join(ROOT, 'docs/左传古文观止去重.tsv'), 'w', encoding='utf-8',
              newline='') as fp:
        w = csv.writer(fp, delimiter='\t', lineterminator='\n')
        w.writerow(['保留', '重复', '相似度', '正文前16字', '处理', '选本篇题', '左傳记录id', '选本id'])
        for r in rows:
            w.writerow([f"{BOOK}#{r['keep_id']} 左丘明《{idx_by_id(base, r['keep_id'])}》",
                        f"{r['rel']}#{r['drop'].get('id')} {r['drop'].get('author')}"
                        f"《{r['drop'].get('title')}》",
                        f"{r['ratio']:.3f}", body(r['drop'])[:16],
                        '删选本：正文逐句出《左傳》', r['drop'].get('title'),
                        r['keep_id'], r['drop'].get('id')])
    print('明细写入 docs/左传古文观止去重.tsv')

    for rel in sorted(drops):
        recs = [r for r in rows if r['rel'] == rel]
        rec = pg.merge(rel, dict(fixes=[dict(
            original=f"{r['drop'].get('id')} 《{r['drop'].get('title')}》", corrected='删除',
            note=f"正文逐句出《左傳》{BOOK}#{r['keep_id']}，按「一件作品只留一份正文」删选本摘录；"
                 f"目次仍在 古文观止·选目.json。逐条见 docs/左传古文观止去重.tsv")
            for r in recs], date=args.date, reviewer=args.reviewer))
        rec['note'] = ((rec.get('note') or '').rstrip() +
                       f" {args.date} 删 {len(recs)} 条《左傳》篇目副本（《左傳》按底本整本重出，"
                       f"选本摘录不再保留），逐条见 docs/左传古文观止去重.tsv。").strip()
        pg.write_record(rel, pg.ordered(rec))
    return rows, left


def idx_by_id(base, rid):
    for rec in base:
        if rec['id'] == rid:
            return rec['title']
    return rid


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--apply', action='store_true')
    ap.add_argument('--date', default=date.today().isoformat())
    ap.add_argument('--reviewer', default='codebuddy')
    args = ap.parse_args()

    toc_path = os.path.join(ROOT, TOC)
    toc = json.load(open(toc_path, encoding='utf-8')) if os.path.exists(toc_path) else []
    one(args, toc)
    if args.apply:
        dump(TOC, toc)
        pg.write_index()
        return
    print('\n（预演，未改动文件；加 --apply 落盘）')


if __name__ == '__main__':
    main()
