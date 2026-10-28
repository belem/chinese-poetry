#!/usr/bin/env python3
"""把 清/词/纳兰词/（212 首选本）并入 清/词/ci.qing.json 的纳兰性德名下。

同一批操作此前在宋词三百首上做过：选本与本集正文逐字相重的，删选本那一份，
在本集记录上加 `tags` 标记该选本；选本独有的，作为本集的新记录补进去。
纳兰词 111 条在 ci.qing.json 里，其中 83 条正文已在纳兰词.json 中，只差题名/分词。

用法：
  python3 scripts/merge_nalan.py            # dry-run
  python3 scripts/merge_nalan.py --apply
"""
import argparse
import difflib
import json
import os
import re
import sys

from opencc import OpenCC

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
T2S = OpenCC('t2s')
PUNCT = re.compile(r'[“”「」『』"\'‘’（）()，。、；：！？,.;:!?□【】\[\]·—…《》〈〉\s]')
TAG = '纳兰词'

CI = '清/词/ci.qing.json'
NALAN = '清/词/纳兰词/纳兰词.json'


def norm(s):
    return PUNCT.sub('', T2S.convert(s or ''))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--apply', action='store_true')
    args = ap.parse_args()

    ci = json.load(open(os.path.join(ROOT, CI), encoding='utf-8'))
    nalan = json.load(open(os.path.join(ROOT, NALAN), encoding='utf-8'))

    # ci.qing 自己就有纳兰的重复条目（正文逐字相同、题名一个有题目一个没有），先并一条
    seen = {}
    dedup = []
    for rec in ci:
        key = (rec.get('author'), norm(''.join(rec.get('paragraphs') or [])))
        if rec.get('author') == '纳兰性德' and key in seen:
            keeper = seen[key]
            for k, v in rec.items():
                if k in ('author', 'paragraphs'):
                    continue
                keeper.setdefault(k, v)
            continue
        if rec.get('author') == '纳兰性德':
            seen[key] = rec
        dedup.append(rec)
    if len(dedup) != len(ci):
        print(f'ci.qing 纳兰重出：{len(ci)} → {len(dedup)} 条')
    ci = dedup

    by_body = {}
    for rec in ci:
        if rec.get('author') == '纳兰性德':
            by_body.setdefault(norm(''.join(rec.get('paragraphs') or [])), rec)

    # 两边都是 paragraphs，题名都是「词牌·题目」；
    # 同一次修订常有一两个字出入（兰/阑、斯/撕、飚/飙），所以正文全同之外再按
    # 「词牌相同 + 相似度 ≥0.9」认同一首，避免同一首被记成两条。
    by_rhythm = {}
    for rec in ci:
        if rec.get('author') == '纳兰性德':
            by_rhythm.setdefault(rec.get('rhythmic'), []).append(
                (norm(''.join(rec.get('paragraphs') or [])), rec))

    def find_target(body, rhythmic):
        if body in by_body:
            return by_body[body]
        best, best_r = None, 0.9
        for other, rec in by_rhythm.get(rhythmic, []):
            r = difflib.SequenceMatcher(None, body, other).ratio()
            if r > best_r:
                best, best_r = rec, r
        return best

    merged = 0
    added = 0
    for rec in nalan:
        body = norm(''.join(rec.get('paragraphs') or []))
        title = rec['title']
        rhythmic = title.partition('·')[0]
        target = find_target(body, rhythmic)
        if target is not None:
            tags = target.setdefault('tags', [])
            if TAG not in tags:
                tags.append(TAG)
            merged += 1
            continue
        # 选本独有：补进 ci.qing.json，题名拆成 词牌·题目
        rhythmic, _, sub = title.partition('·')
        item = {
            'author': '纳兰性德',
            'paragraphs': rec['paragraphs'],
            'rhythmic': rhythmic,
            'sources': ['nalan'],
            'tags': [TAG],
        }
        if sub:
            item['title'] = sub
        ci.append(item)
        by_body[body] = item
        added += 1

    print(f'纳兰词 {len(nalan)} 首：并入 ci.qing 已有记录 {merged}，新增 {added}')
    left = [r['title'] for r in nalan if not find_target(norm(''.join(r['paragraphs'])), r['title'].partition('·')[0])]
    print(f'  逐条自检：仍未对上的 {len(left)} 条 {"（应为 0）" if left else ""}')
    for t in left[:10]:
        print('   ', t)
    if not args.apply:
        print('（dry-run，未改动任何文件；加 --apply 落盘）')
        return

    with open(os.path.join(ROOT, CI), 'w', encoding='utf-8') as fp:
        json.dump(ci, fp, ensure_ascii=False, indent=2)
        fp.write('\n')
    print(f'  写 {CI}  {len(ci)} 条')
    for p in (NALAN, os.path.join(ROOT, '清/词/纳兰词/README.md')):
        if os.path.exists(p):
            os.remove(p)
    d = os.path.join(ROOT, '清/词/纳兰词')
    if os.path.isdir(d) and not os.listdir(d):
        os.rmdir(d)
    print('  删 清/词/纳兰词/')


if __name__ == '__main__':
    main()
