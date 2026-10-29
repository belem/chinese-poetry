#!/usr/bin/env python3
"""全库重复体检：同一首作品被两份数据各收一次的，逐条列出来给人判。

与 `scripts/check_tree.py` 同一判重口径（`t2s` 归一、去非汉字、正文前 16 字相同），
差别只在**报告什么**：

  check_tree  只在同一部书内部判重，跨书互见单独计数不列出 —— 那是给「目录结构」看的。
  本脚本      跨书互见才是重点：`清/诗/poet.qing.json` 里混进整部《幽梦影》、
              《全宋词》里混进整部《花间集》，这类「一书变两套正文」正是一份份副本躺在两个目录里。

用法：

  python3 scripts/dedupe_corpus.py report                 # 打印各类计数与样例
  python3 scripts/dedupe_corpus.py report --out docs/重复体检.tsv
  python3 scripts/dedupe_corpus.py pair A B               # 只列 A、B 两目录之间的互见

`pair` 用来做批次：一次挑一对书（如 `清/诗/poet.qing.json` 与 `清/幽梦影`），
判完写进该批的 TSV，再动下一个。全库一次清完会以偏概全 —— 选本收总集里的作品是编书方式，
不是重复，得逐书看规矩。
"""
import argparse
import collections
import csv
import os
import re
import sys

from opencc import OpenCC

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
T2S = OpenCC('t2s')
HAN = re.compile(r'[^\u4e00-\u9fff]')
SKIP_DIRS = {'loader', 'strains', 'images', 'rank', 'error', 'scripts', 'docs', 'anthologies',
             '.git', '.claude', '.github', '.cnb', 'reference', 'authors', 'dynasties'}
SKIP_FILES = {'fix_progress.json'}
NON_WORK_KEYS = {'desc', 'name', 'short_description', 'introduction'}
DYNASTY_DIRS = {'先秦', '汉', '三国', '晋', '南北朝', '隋', '唐', '五代十国', '宋', '元', '明', '清', '近现', '当'}


def han(s):
    return HAN.sub('', T2S.convert(s or ''))


def text_of(rec):
    if not isinstance(rec, dict) or NON_WORK_KEYS <= set(rec):
        return None
    for key in ('paragraphs', 'para', 'content'):
        v = rec.get(key)
        if isinstance(v, str):
            return v
        if isinstance(v, list) and v and all(isinstance(x, str) for x in v):
            return ''.join(v)
    return None


def walk(node, rel, path=()):
    """递归找出含正文字段的作品（蒙学这类是 content[].paragraphs 的嵌套结构）。"""
    if isinstance(node, dict):
        text = text_of(node)
        if text is not None:
            yield rel, path, node, han(text)
            return
        for k, v in node.items():
            if isinstance(v, (list, dict)):
                yield from walk(v, rel, path + (k,))
    elif isinstance(node, list):
        for i, v in enumerate(node):
            yield from walk(v, rel, path + (i,))


def iter_files():
    for dirpath, dirs, filenames in os.walk(ROOT):
        dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS and not d.startswith('.'))
        for f in sorted(filenames):
            if f.endswith('.json') and f not in SKIP_FILES:
                yield os.path.relpath(os.path.join(dirpath, f), ROOT)


def iter_records(files=None):
    import json
    for rel in iter_files():
        if files and not any(rel == f or rel.startswith(f.rstrip('/') + '/') for f in files):
            continue
        try:
            with open(os.path.join(ROOT, rel), encoding='utf-8') as fp:
                data = json.load(fp)
        except Exception:
            continue
        yield from walk(data, rel)


def domain_of(rel):
    """一部书：`唐/诗/全唐诗`、`宋/诗/全宋诗` 这种「朝代/体裁/书名」三级，其余取前两级或一级。"""
    parts = rel.split('/')
    if parts[0] in DYNASTY_DIRS:
        return '/'.join(parts[:3]) if len(parts) >= 3 and parts[1] in ('诗', '词', '曲', '文') else '/'.join(parts[:2])
    return parts[0]


def title_of(rec):
    for key in ('title', 'chapter', 'rhythmic'):
        if rec.get(key):
            return str(rec[key])
    return ''


def author_of(rec):
    return T2S.convert(re.sub(r'\s*\S*[一二三四五六七八九十]+首$', '', (rec.get('author') or '').strip()))


def groups(files=None, prefix=16):
    g = collections.defaultdict(list)
    for rel, path, rec, body in iter_records(files):
        if len(body) >= prefix:
            g[body[:prefix]].append((rel, path, rec, body))
    return g


def report(args):
    g = groups()
    rows, stat = [], collections.Counter()
    for body, items in g.items():
        if len(items) < 2:
            continue
        doms = collections.Counter(domain_of(i[0]) for i in items)
        kind = '同书' if len(doms) == 1 else '跨书'
        stat[kind] += len(items) - 1
        stat[' / '.join(sorted(doms))] += len(items) - 1
        for i in items:
            rows.append(dict(kind=kind, body16=body, domains=' / '.join(sorted(doms)),
                             path=i[0], author=author_of(i[2]), title=title_of(i[2]),
                             length=len(i[3])))
    print(f'== 重复 {sum(1 for _ in rows)} 条记录，按性质：')
    for k, n in stat.most_common():
        if ' / ' not in k:
            print(f'   {k}: {n}')
    print('== 跨书互见最多的几对：')
    for k, n in stat.most_common(25):
        if ' / ' in k:
            print(f'   {n:5d}  {k}')
    if args.out:
        with open(os.path.join(ROOT, args.out), 'w', encoding='utf-8', newline='') as fp:
            w = csv.DictWriter(fp, delimiter='\t', lineterminator='\n', fieldnames=list(rows[0]))
            w.writeheader()
            w.writerows(rows)
        print(f'明细写入 {args.out}')
    return rows


def pair(args):
    a, b = args.a, args.b
    g = groups([a, b])
    n = 0
    for body, items in g.items():
        sides = {i[0] for i in items}
        if not any(x == a or x.startswith(a.rstrip('/') + '/') for x in sides):
            continue
        if not any(x == b or x.startswith(b.rstrip('/') + '/') for x in sides):
            continue
        n += 1
        print(f'--- {body[:24]}')
        for rel, path, rec, bd in items:
            print(f'   {rel}#{"/".join(map(str, path))} {author_of(rec)}《{title_of(rec)}》 {len(bd)} 字')
    print(f'共 {n} 组')
    return n


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('action', choices=['report', 'pair'])
    ap.add_argument('a', nargs='?')
    ap.add_argument('b', nargs='?')
    ap.add_argument('--out')
    args = ap.parse_args()
    if args.action == 'pair':
        if not (args.a and args.b):
            ap.error('pair 需要两个目录')
        return pair(args)
    report(args)
    return 0


if __name__ == '__main__':
    sys.exit(main())
