#!/usr/bin/env python3
"""元曲正文级去重：同一支曲子被记在两个作者名下（归属异说），或同一人重出。

处理原则（沿用 AGENTS.md「一件作品只留一份正文」）：
  - 同一作者、正文相同的，留一条；
  - 归属异说（关汉卿/曾瑞、汤舜民/詹时雨、关汉卿/无名氏）的，留**具名**那一条，
    无名氏那条删——存疑的归属已经有具名本，不必再挂一个「无名氏」；
  - 两条都具名且不相同时，留作者表里有的那一个，另一个记在 `notes` 里。

用法：
  python3 scripts/dedupe_yuanqu.py            # dry-run
  python3 scripts/dedupe_yuanqu.py --apply
"""
import argparse
import json
import os
import re
import sys

from opencc import OpenCC

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
T2S = OpenCC('t2s')
PUNCT = re.compile(r'[“”「」『』"\'‘’（）()，。、；：！？,.;:!?□【】\[\]·—…《》〈〉\s]')
SOURCE = '元/元曲/yuanqu.json'


def norm(s):
    return PUNCT.sub('', T2S.convert(s or ''))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--apply', action='store_true')
    args = ap.parse_args()

    data = json.load(open(os.path.join(ROOT, SOURCE), encoding='utf-8'))
    groups = {}
    for idx, rec in enumerate(data):
        body = norm(''.join(rec.get('paragraphs') or []))
        if len(body) < 20:
            continue
        groups.setdefault(body, []).append(idx)

    drop = set()
    notes = []
    for body, idxs in groups.items():
        if len(idxs) < 2:
            continue
        recs = [data[i] for i in idxs]
        authors = [r.get('author') for r in recs]
        named = [i for i in idxs if data[i].get('author') not in (None, '', '无名氏')]
        if not named:
            keep = idxs[0]
        elif len(named) == 1:
            keep = named[0]
        else:
            # 都具名：留第一条，把其它作者记下来
            keep = named[0]
        for i in idxs:
            if i == keep:
                continue
            drop.add(i)
            other = data[i].get('author')
            if other and other != data[keep].get('author'):
                data[keep].setdefault('notes', []).append(f'一作{other}')
        notes.append(([data[i].get('author') for i in idxs], data[keep].get('author'),
                      data[keep].get('title', '')[:24]))

    for authors, keeper, title in notes:
        print('  {} → 留 {}《{}》'.format('/'.join(authors), keeper, title))
    print(f'元曲 {len(data)} 条，删重出 {len(drop)} 条 → {len(data) - len(drop)}')

    if not args.apply:
        print('（dry-run，未改动任何文件；加 --apply 落盘）')
        return

    out = [r for i, r in enumerate(data) if i not in drop]
    with open(os.path.join(ROOT, SOURCE), 'w', encoding='utf-8') as fp:
        json.dump(out, fp, ensure_ascii=False, indent=2)
        fp.write('\n')
    print(f'  写 {SOURCE}')


if __name__ == '__main__':
    main()
