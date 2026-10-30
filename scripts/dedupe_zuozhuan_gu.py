#!/usr/bin/env python3
"""《左传》单行本与《古文观止》里同名的篇目：正文逐字相同即删**选本**那一份。

`先秦/文/zuozhuan.json`（278 条，按纪年排）与 `汇编/古文观止/` 卷一、卷二、补编里
同题的篇目（《郑伯克段于鄢》《石碏谏宠州吁》……）有 31 组对得上题名。其中 11 组两边
正文拆合之后一字不差（`t2s` 归一、去标点后相等），就是同一篇的副本：

```
先秦/文/zuozhuan.json#258   左丘明《郑伯克段于鄢》  541 字   ← 留
汇编/古文观止/卷一周文.json#0  左丘明《鄭伯克段於鄢》  541 字   ← 删
```

## 与 `dedupe_huibian_poet.py` 的取舍相反，为什么

那一批（`docs/汇编与诗去重.md`）删的是**补录**、留选本：`poet.*` 是《历代》拆出来的散录，
没有版本信息，而选本有底本、有编次、有篇题。

这一批反过来：`zuozhuan.json` 是《左传》**整部书的单行本**（一颗纪年一路排下来），
选本的这一篇只是从书里摘的同一段。按「一件作品只留一份正文」，留书、删选本摘录。
《古文观止》这一层目录记的是「古文观止收了哪几篇」——删掉整条会丢这条信息，
所以另在 `汇编/古文观止/古文观止·选目.json` 里留一份目次（篇题、作者、卷次、
对应 `zuozhuan.json` 的记录 id），正文只有单行本那一份。

## 判据：`t2s` 归一之后一字不差，且不短于选本

两书的繁简、用字本有出入（`寘/置`、`焞/炖`、`馀/余`、`翦/剪`、`榖/谷`、`殽/崤`），
所以比较用 `t2s` 归一，标点一律不计。归一之后仍有字差的 7 组两存待对勘，
其中三类各有理由：

| 情形 | 例 |
| --- | --- |
| 选本比单行本多了纪年文字 | 《子鱼论战》（选本多「二十有二年春公伐邾取须句……」72 字）、《吕相绝秦》（多「夏四月戊午」）、《子产坏晋馆垣》（多「公薨之月」） |
| 选本夹了注 | 《郑庄公戒饬守臣》（「序民人一作序人民」）、《介之推不言禄》（「绵上地名」） |
| 两边各取各的 | 《臧哀伯谏纳郜鼎》（单行本多「周内史闻之曰臧孙达其有后于鲁乎」一评）、《蹇叔哭师》（选本多「冬，晋文公卒……」一段） |

另有两组同题不同文，是《古文观止·补》里抄配了别篇的正文，一并两存：
《子产却楚逆女以兵》配的是《徐吾犯之妹美》，《吴许越成》配的是「吴子使来儆师伐齐」那一段。

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
# 通用异体与音同形近字：归一之后仍差这一些，不算出入（沿用 `汇编与诗去重` 的口径）
GENERAL_VARIANTS = {
    '椁': '惇', '馀': '余', '蓺': '艺', '偫': '待', '太': '大', '烝': '蒸',
    '句': '勾', '棰': '箠', '禘': '鐕', '仪': '议',
    # 只有《左传》卷用到的那几处（`寘/置` 等）不放进来：那些是两读都传世的异文，要两存
}
# 一批一本书：单行本（整部书）、要扫的选本卷次、明细表
#
# 后两批（左传补收、国语）是 2026-10-30 第二轮：上一轮只核了题名对得上的，
# 漏了两样 ——《古文观止》有重出篇目（《郑伯克段于鄢》卷一、卷三各一条、《子鱼论战》卷一本、补编一本），
# `--soft` 之外只取「t2s 归一后一字不差」，于是《祭公谏征犬戎》这类只差一个通用字的没被收进来。
BOOKS = [
    dict(book='先秦/文/zuozhuan.json', name='左传', toc=True, out='docs/左传古文观止去重.tsv',
         files=['古文观止·补.json', '卷一周文.json', '卷二周文.json', '卷三周文.json'], soft=True),
    dict(book='先秦/文/guoyu.json', name='国语', toc=True, out='docs/国语古文观止去重.tsv',
         files=['卷三周文.json'], soft=False),
]


def han(s):
    return HAN.sub('', T2S.convert(s or ''))


def canon(text):
    """归一之后再把上面那批通用字抹平，好让「一字之差」与「改字」分开。"""
    return ''.join(GENERAL_VARIANTS.get(c, c) for c in text)


def body(rec, han_only=False):
    """`t2s` 之后的正文字符；`han_only=False` 时另去标点。"""
    p = rec.get('paragraphs')
    joined = p if isinstance(p, str) else ''.join(p or [])
    return T2S.convert(joined) if han_only else han(joined)


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


def one(book, args, toc, done):
    """跑一本书：返回 (rows, left)，未 apply 时不落盘。"""
    base = load(book['book'])
    idx = {}
    for rec in base:
        idx.setdefault(han(rec.get('title')), []).append(rec)

    rows, left, drops, files = [], [], {}, {}
    for name in book['files']:
        rel = f"{GU_DIR}/{name}"
        files[rel] = load(rel)
        for i, rec in enumerate(files[rel]):
            if (rel, i) in done:
                continue
            cands = idx.get(han(rec.get('title')), [])
            if not cands:
                continue
            best = max(cands, key=lambda c: difflib.SequenceMatcher(None, body(c), body(rec)).ratio())
            item = dict(keep=best, drop=rec, rel=rel, index=i,
                        ratio=difflib.SequenceMatcher(None, body(best), body(rec)).ratio())
            ok = (canon(body(best, True)) == canon(body(rec, True)) if book['soft']
                  else body(best, True) == body(rec, True))
            if ok and len(body(best)) >= len(body(rec)):
                drops.setdefault(rel, set()).add(i)
                rows.append(item)
            else:
                left.append(item)

    print(f"== 《{book['name']}》：同名 {len(rows) + len(left)} 组，删 {len(rows)}、两存 {len(left)}")
    for r in rows:
        print(f"   删 {r['rel'].split('/')[-1]}#{r['index']} 《{r['drop'].get('title')}》"
              f" ← 留 {book['book']} {r['keep'].get('id')} 《{r['keep'].get('title')}》  {r['ratio']:.3f}")
    for r in left:
        print(f"   存 {r['rel'].split('/')[-1]}#{r['index']} 《{r['drop'].get('title')}》"
              f" 与单行本 ratio={r['ratio']:.3f}，两存")
    done.update((r['rel'], r['index']) for r in rows)
    if not args.apply:
        return rows, left

    if book['toc'] and rows:
        have = {(t['卷次'], t['篇目']) for t in toc}
        for r in rows:
            key = (r['rel'].split('/')[-1], r['drop'].get('title'))
            if key in have:
                continue
            toc.append({'卷次': key[0], '篇目': key[1], '作者': r['drop'].get('author'),
                        '书': book['name'], '记录': f"{book['book']}#{r['keep'].get('id')}"})
            have.add(key)

    for rel in sorted(drops):
        dump(rel, [rec for i, rec in enumerate(files[rel]) if i not in drops[rel]])
        done.update((rel, i) for i in drops[rel])

    with open(os.path.join(ROOT, book['out']), 'w', encoding='utf-8', newline='') as fp:
        w = csv.writer(fp, delimiter='\t', lineterminator='\n')
        w.writerow(['保留', '重复', '相似度', '正文前16字', '处理'])
        for r in rows + left:
            soft = book['soft'] and canon(body(r['keep'], True)) == canon(body(r['drop'], True))
            w.writerow([f"{book['book']}#{r['keep'].get('id')} {r['keep'].get('author')}《{r['keep'].get('title')}》",
                        f"{r['rel']}#{r['index']} {r['drop'].get('author')}《{r['drop'].get('title')}》",
                        f"{r['ratio']:.3f}", body(r['keep'])[:16],
                        '删选本摘录，留单行本' if r in rows
                        else ('两存：一字之差' if soft else '两存：正文有出入')])
    print(f"明细写入 {book['out']}")

    for rel in sorted(drops):
        recs = [r for r in rows if r['rel'] == rel]
        rec = pg.merge(rel, dict(fixes=[dict(
            original=f"{r['drop'].get('id')} 《{r['drop'].get('title')}》", corrected='删除',
            note=f"与《{book['name']}》单行本 {book['book']}#{r['keep'].get('id')} 正文相同，留单行本；"
                 f"逐条见 {book['out']}") for r in recs], date=args.date, reviewer=args.reviewer))
        rec['note'] = ((rec.get('note') or '').rstrip() +
                       f" {args.date} 删 {len(recs)} 条《{book['name']}》篇目副本，逐条见 {book['out']}。").strip()
        pg.write_record(rel, pg.ordered(rec))
    return rows, left


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--apply', action='store_true')
    ap.add_argument('--date', default=date.today().isoformat())
    ap.add_argument('--reviewer', default='codebuddy')
    ap.add_argument('--book', action='append', help='只跑某本书（子串匹配书名），默认全跑')
    args = ap.parse_args()

    toc_path = os.path.join(ROOT, TOC)
    toc = json.load(open(toc_path, encoding='utf-8')) if os.path.exists(toc_path) else []
    done = set()        # 前面几批已经删掉的记录，后面的书目不必再判
    for book in BOOKS:
        if args.book and not any(b in book['name'] for b in args.book):
            continue
        one(book, args, toc, done)
    if args.apply:
        dump(TOC, toc)
        pg.write_index()
    if not args.apply:
        print('\n（预演，未改动文件；加 --apply 落盘）')


if __name__ == '__main__':
    main()
