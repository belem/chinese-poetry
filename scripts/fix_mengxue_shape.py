#!/usr/bin/env python3
"""把 `汇编/蒙学/` 的十一部书从「一部书一条记录」改回「一句一条记录」（issue #258）。

背景：2026-11 重建蒙学时，写成 `{title, author, dynasty, paragraphs: [...]}` 的单条记录，
`paragraphs` 里混着字符串与 `{chapter, paragraphs}` 两种形状；`loader/data_loader.py`
与全库其余 350 万条一样按「文件是一个数组、一条记录一首」取 `tag`，
于是这些书一加载就报 `failed to parse JSON`。

现在改为：

    [{"title": …, "author": …, "dynasty": …, "chapter": …, "paragraphs": […], "id": …,
      "variants": […], "id": {…}}, …]

  * 一句一条记录，正文一行不变；`chapter` 只出现在分卷/分章的书里；
  * 书级的 `abstract` 不再写进每条（那是简介，不是正文），保留在 `汇编/蒙学/README.md`；
  * 夹注异文 `variants` 挪到书末单独一条（`paragraphs: []`），不再挂到某一句上；
  * `id` 沿用 `scripts/backfill_ids.py` 的规则（作者+题名+正文哈希），分卷书把章名并进题名，
    免得三十一章的《五字鑒》都叫「五字鑒」。

  python3 scripts/fix_mengxue_shape.py            # 预演：打印每部书的条数
  python3 scripts/fix_mengxue_shape.py --apply    # 写盘
"""
import argparse
import collections
import hashlib
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'scripts'))

import import_mengxue  # noqa: E402
import twin_collate as tc  # noqa: E402

ALPHABET = '0123456789abcdefghijklmnopqrstuv'
DIR = '汇编/蒙学'


def base22(key, size, taken):
    while True:
        v = int.from_bytes(hashlib.blake2b(key.encode(), digest_size=16).digest(), 'big')
        out = ''
        for _ in range(size):
            v, r = divmod(v, 22)
            out = ALPHABET[r] + out
        if out not in taken:
            taken.add(out)
            return out
        size += 1


def pieces(node, vol=None):
    """→ [(卷 | None, 章 | None, [正文...])]。

    `paragraphs` 里可能直接是句子，也可能套一层 `{chapter, paragraphs}`；
    旧版另有 `content: [{title: 卷, content: [{chapter, paragraphs}]}]` 与
    `[{chapter, paragraphs}]` 两种排法，一并摊平。
    """
    out = []
    body = node.get('paragraphs')
    for p in body if isinstance(body, list) else []:
        if isinstance(p, str):
            out.append((vol, None, [p]))
        elif isinstance(p, dict):
            out.append((vol, p.get('chapter'), p.get('paragraphs') or []))
    for sec in node.get('content') or [] if isinstance(node.get('content'), list) else []:
        if not isinstance(sec, dict):
            continue
        if 'chapter' in sec or 'paragraphs' in sec:
            out.append((vol, sec.get('chapter'), sec.get('paragraphs') or []))
        else:                                             # {title: 卷, content: [...]}
            out.extend(pieces(sec, sec.get('title') or vol))
    return out


def build(rel, taken):
    old = json.load(open(os.path.join(ROOT, rel), encoding='utf-8'))
    head = {k: old[k] for k in ('title', 'author', 'dynasty') if k in old}
    rows = []
    for vol, ch, lines in pieces(old):
        lines = [x for x in lines if isinstance(x, str) and x]
        if not lines:
            continue
        row = dict(head)
        if vol:
            row['volume'] = vol
        if ch:
            row['chapter'] = ch
        row['paragraphs'] = lines
        title = '·'.join(x for x in (old['title'], vol, ch) if x)
        row['id'] = base22(f"{row['author']}|{title}|{''.join(lines)}", 6, taken)
        rows.append(row)
    if old.get('variants'):
        rows.append(dict(head, paragraphs=[], variants=old['variants'],
                         id=base22(f"{head['author']}|{head['title']}|variants", 6, taken)))
    return old, rows


def dump(rel, rows):
    """缩进与全库一致（4 格），一行一个字符串；原来 2 格缩进的书一并对齐。"""
    text = json.dumps(rows, ensure_ascii=False, indent=4) + '\n'
    open(os.path.join(ROOT, rel), 'w', encoding='utf-8').write(text)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--apply', action='store_true', help='写盘；否则只预演')
    args = ap.parse_args()

    taken, total = set(), 0
    plan = []
    for book in import_mengxue.BOOKS + [
            dict(out='liwengduiyun.json'), dict(out='shenglvqimeng.json'), dict(out='longwenbianying.json'),
            dict(out='wenzimengqiu.json'), dict(out='zhuzijiaxun.json')]:
        rel = f"{DIR}/{book['out']}"
        old, rows = build(rel, taken)
        total += len(rows)
        print(f"{book['out']:<22}{len(rows):>5} 条  {sum(len(x['paragraphs']) for x in rows):>6} 句")
        plan.append((rel, rows))

    by_id = collections.Counter(r['id'] for _, rows in plan for r in rows)
    assert all(n == 1 for n in by_id.values()), [k for k, n in by_id.items() if n > 1]
    print(f'\n共 {len(plan)} 部，{total} 条记录')
    if not args.apply:
        return
    for rel, rows in plan:
        dump(rel, rows)
        print('→', rel)


if __name__ == '__main__':
    sys.exit(main())
