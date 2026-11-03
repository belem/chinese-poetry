#!/usr/bin/env python3
"""《古文观止》里与库内整本书逐字相重的篇目：删选本那一份，正文只留整本。

按「一件作品只留一份正文」，选本摘录若在整本里逐字都在，就不该再占一份正文；
但《古文观止》这一层目次记的是「这本书收了哪几篇」，所以不删条目，
`古文观止·选目.json` 里该条的「记录」改指整本的对应位置。

三批：

| 整本 | 选本篇数 | 覆盖率的算法 |
| --- | --- | --- |
| `史书/春秋左氏传/zuozhuan.json` | 34（卷一周文全部 + 卷二前 16 篇） | 六字窗覆盖过一个年 |
| `史书/战国策/zhanguoce.json` | 14（卷四國策文） | 六字窗覆盖过一章 |
| `史书/史记/shiji.json` | 4（卷五、卷十的赞与序，整本里逐字都在） | 六字窗覆盖过全篇 |

《史记》那 4 篇为什么只有 4 篇：`shiji.json` 的十表只有篇题、没有表序正文，
《秦楚之际月表》《高祖功臣侯者年表》两篇的序在整本里找不到，只能留在选本里；
《伯夷列传》一篇是删节，《酷吏列传序》《游侠列传序》《货殖列传序》三篇是列传开头一节，
它们与整本对不上全文、差额也都是 0（选本一字不多），但选本这一层留着的正是「古文观止怎么读这一篇」，
按 AGENTS.md「选本有它自己的用场」，四条列传/序一并留着，只删整本里逐字全在的四篇赞序。

用法：
  python3 scripts/dedupe_guwen_books.py                      # 预演
  python3 scripts/dedupe_guwen_books.py --apply --date YYYY-MM-DD --reviewer <名字>
"""
import argparse
import csv
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
GU = '汇编/古文观止'
TOC = f'{GU}/古文观止·选目.json'
WINDOW = 6
THRESHOLD = 0.10          # 《穀梁传》与《左传》同记一事的那两篇上限 0.053，《左传》诸篇下限 0.90

# 整本：文件、卷、篇题字段。卷一周文/卷二周文查《左传》，卷四查《國策》，卷五查《史記》
BOOKS = {
    'zuozhuan': ('史书/春秋左氏传/zuozhuan.json', ['卷一周文.json', '卷二周文.json']),
    'zhanguoce': ('史书/战国策/zhanguoce.json', ['卷四秦文.json']),
    'shiji': ('史书/史记/shiji.json', ['卷五秦文.json']),
}
ONLY = ('五帝本纪赞', '项羽本纪赞', '孔子世家赞', '外戚世家序')


def han(s):
    return HAN.sub('', T2S.convert(s or ''))


def cover(text, hay):
    n, hit, i = len(text), 0, 0
    while i + WINDOW <= n:
        if text[i:i + WINDOW] in hay:
            hit += WINDOW
            i += WINDOW
        else:
            i += 1
    return hit / len(text) if n else 0.0


def load(rel):
    with open(os.path.join(ROOT, rel), encoding='utf-8') as fp:
        return json.load(fp)


def dump(rel, data):
    path = os.path.join(ROOT, rel)
    raw = open(path, encoding='utf-8').read() if os.path.exists(path) else ''
    m = re.search(r'\n( +)\S', raw)
    indent = len(m.group(1)) if m else 2
    out = json.dumps(data, ensure_ascii=False, indent=indent) + '\n'
    with open(path, 'w', encoding='utf-8') as fp:
        fp.write(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--apply', action='store_true')
    ap.add_argument('--date', default=date.today().isoformat())
    ap.add_argument('--reviewer', default='codebuddy')
    a = ap.parse_args()
    toc = load(TOC)
    rows, plan = [], {}
    for key, (book, vols) in BOOKS.items():
        base = load(book)
        hay = {r['id']: han(''.join(r['paragraphs'])) for r in base}
        for vol in vols:
            rel = f'{GU}/{vol}'
            recs = load(rel)
            for i, rec in enumerate(recs):
                if key == 'shiji' and rec['title'] not in ONLY:
                    continue
                t = han(''.join(rec['paragraphs']))
                if not t:
                    continue
                best, hit = None, 0
                for rid, h in hay.items():
                    c = cover(t, h)
                    if c > hit:
                        best, hit = rid, c
                ratio = hit
                if ratio <= THRESHOLD:
                    continue
                title = [r['title'] for r in base if r['id'] == best][0]
                rows.append(dict(book=book, keep=best, keep_title=title, rel=rel, idx=i,
                                 rec=rec, ratio=ratio))
                plan.setdefault(rel, set()).add(i)
    for r in rows:
        print(f"删 {r['rel'].split('/')[-1]}#{r['idx']} 《{r['rec']['title']}》"
              f" ← 留 {r['book']} {r['keep']} 《{r['keep_title']}》 cover={r['ratio']:.3f}")
    print(f'共 {len(rows)} 篇，涉及 {len(plan)} 个卷文件')
    if not a.apply:
        return
    for rel, drop in plan.items():
        recs = load(rel)
        dump(rel, [r for i, r in enumerate(recs) if i not in drop])
    # 目次：删掉的篇目，「记录」改指整本
    for r in rows:
        for t in toc:
            if t['篇目'] == r['rec']['title'] and t['卷次'] == r['rel'].split('/')[-1]:
                t['记录'] = f"{os.path.basename(r['book'])}#{r['keep']}"
    dump(TOC, toc)
    with open(os.path.join(ROOT, 'docs/古文观止去重.tsv'), 'w', encoding='utf-8', newline='') as fp:
        w = csv.writer(fp, delimiter='\t', lineterminator='\n')
        w.writerow(['整本', '整本篇题', '覆盖率', '卷次', '选本篇目', '选本 id', '处理后'])
        for r in rows:
            w.writerow([f"{r['book']}#{r['keep']}", r['keep_title'], f'{r["ratio"]:.3f}',
                        r['rel'].split('/')[-1], r['rec']['title'], r['rec']['id'],
                        '删选本正文，目次改指整本'])
    print('明细写入 docs/古文观止去重.tsv')
    for rel in plan:
        rec = pg.merge(rel, dict(fixes=[dict(
            original=f"{r['rec']['id']} 《{r['rec']['title']}》", corrected='删除',
            note=f"正文逐字出 {r['book']}#{r['keep']}《{r['keep_title']}》，"
                 f"按「一件作品只留一份正文」删选本摘录；目次仍在 古文观止·选目.json")
            for r in rows if r['rel'] == rel], date=a.date, reviewer=a.reviewer))
        pg.write_record(rel, pg.ordered(rec))
    pg.write_index()


if __name__ == '__main__':
    main()
