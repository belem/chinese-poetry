#!/usr/bin/env python3
"""目录与重复体检，只报告，不修改任何数据。

检查两类问题，都是「目录结构改不动」的根因：

  dup_body     正文级重复：简繁归一、去标点后前 N 字相同，且两条在同一个目录。
               分开统计「同作者」与「异作者」——同作者的多半是同诗重出；
               异作者要再看题名：同题的（如毕士安/毕仲游同题一首）是归属异说，两条都留；
               不同题的多为误收或联句拆条，需人工判。
               只看目录内部：选本与本纪年体互相收录同一首是正常的，那是编书方式
               （《文选》按体类收诗、《历代》是补录），不算重复。
  dynasty      朝代字段体检：取值不在 dynasties/dynasties.json 的 name 里（如拼音 "yuan"）、
               缺失（有作者却无朝代）、与作者索引冲突。

用法：
  python3 scripts/check_tree.py                     # 打印汇总
  python3 scripts/check_tree.py --out docs/重复体检.tsv    # 输出逐条明细
  python3 scripts/check_tree.py --only dup_body --show 20
  python3 scripts/check_tree.py --prefix 12         # 判重取前多少字（默认 16）
"""
import argparse
import collections
import json
import os
import re
import sys

from opencc import OpenCC

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
T2S = OpenCC('t2s')

SKIP_DIRS = {'loader', 'strains', 'images', 'rank', 'error', 'scripts', 'docs', 'anthologies',
             '.git', '.claude', '.github', '.cnb', 'reference', 'authors', 'dynasties'}
SKIP_FILES = {'fix_progress.json'}
# 数据按朝代分层的顶层目录：朝代/体裁/书名/文件名
DYNASTY_DIRS = {'先秦', '汉', '三国', '晋', '南北朝', '隋', '唐', '五代十国', '宋', '元', '明', '清', '近现', '当'}
HANZI = re.compile(r'[^\u4e00-\u9fff]')
# 这些键里装的不是作品，是作者表 / 目录说明
NON_WORK_KEYS = {'desc', 'name', 'short_description', 'introduction'}


def iter_files():
    for dirpath, dirs, filenames in os.walk(ROOT):
        dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS)
        for f in sorted(filenames):
            if f.endswith('.json') and f not in SKIP_FILES:
                yield os.path.relpath(os.path.join(dirpath, f), ROOT)


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


def norm(s):
    return HANZI.sub('', T2S.convert(s or ''))


def iter_records():
    for rel in iter_files():
        try:
            with open(os.path.join(ROOT, rel), encoding='utf-8') as fp:
                data = json.load(fp)
        except Exception:
            continue
        if isinstance(data, dict):
            data = [data]
        if not isinstance(data, list):
            continue
        for idx, rec in enumerate(data):
            text = text_of(rec)
            if text is None:
                continue
            yield rel, idx, rec, norm(text)


def author_of(rec):
    a = rec.get('author') or ''
    return T2S.convert(re.sub(r'\s*\S*[一二三四五六七八九十]+首$', '', a.strip()))


def title_of(rec):
    for key in ('title', 'chapter', 'rhythmic'):
        if rec.get(key):
            return str(rec[key])
    return ''


def domain_of(rel):
    """判重的作用域：同一部书内部。文件名不同但同属一部书的，算同一作用域：

    目录已按朝代分层（唐/诗/全唐诗、宋/诗/全宋诗、宋/词/宋词…），顶层目录名不再等于书名，
    按「朝代/体裁/书名」三级取书名；
    补录的 331 条曾挂在 元曲/yuanqu.json 尾部，与《全元曲》同文件但不是同一部书；
    它曾用 sources: ["haitang"] 分流成另一部书，该标记已清除，现在整文件算一部书。
    """
    parts = rel.split('/')
    if parts[0] in DYNASTY_DIRS:
        return parts[2] if len(parts) >= 3 and parts[1] in ('诗', '词', '曲', '文') else parts[1]
    head = parts[0]
    if head == '元曲':
        return '全元曲' if rel.endswith('yuanqu.json') else '元曲选本'
    return head


def check_dup(prefix):
    groups = collections.defaultdict(list)
    for rel, idx, rec, body in iter_records():
        if len(body) < prefix:
            continue
        groups[body[:prefix]].append((rel, idx, author_of(rec), title_of(rec),
                                      domain_of(rel)))
    rows = []
    for body, items in groups.items():
        if len(items) < 2:
            continue
        domains = {i[4] for i in items}
        if len(domains) != 1:       # 跨书收录同一首，是编书方式，不算重复
            continue
        authors = {i[2] for i in items if i[2]}
        if len(authors) <= 1:
            kind = '同作者'
        else:
            kind = '异作者·同题' if len({i[3] for i in items}) == 1 else '异作者·异题'
        for item in items[1:]:
            rows.append((body, kind, items[0][:4], item[:4]))
    stats = collections.Counter(r[1] for r in rows)
    return rows, stats


def check_dynasty():
    with open(os.path.join(ROOT, 'dynasties/dynasties.json'), encoding='utf-8') as fp:
        valid = {d['name'] for d in json.load(fp)}
    with open(os.path.join(ROOT, 'authors/authors.json'), encoding='utf-8') as fp:
        by_author = collections.defaultdict(set)
        for a in json.load(fp):
            by_author[T2S.convert(a['name'])].add(a['dynasty'])
    bad_value = collections.Counter()
    conflict = collections.Counter()
    for rel, idx, rec, _ in iter_records():
        d = rec.get('dynasty')
        if d is None:
            continue
        if d not in valid:
            bad_value[(rel, d)] += 1
            continue
        names = by_author.get(author_of(rec))
        if names and d not in names:
            conflict[(rel, author_of(rec), d, '/'.join(sorted(names)))] += 1
    return valid, bad_value, conflict


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out')
    ap.add_argument('--only', choices=['dup_body', 'dynasty'])
    ap.add_argument('--show', type=int, default=5)
    ap.add_argument('--prefix', type=int, default=16)
    args = ap.parse_args()

    rows = stats = None
    if args.only in (None, 'dup_body'):
        rows, stats = check_dup(args.prefix)
        print(f'== dup_body: {len(rows)} 条多余记录（同一部书内，正文前 {args.prefix} 字相同）')
        for k in ('同作者', '异作者·同题', '异作者·异题'):
            print(f'   {k}: {stats.get(k, 0)}')
        per_file = collections.Counter()
        for body, kind, keep, drop in rows:
            per_file[drop[0]] += 1
        for name, n in per_file.most_common(args.show):
            print(f'   {name}: {n}')
        for body, kind, keep, drop in rows[:args.show]:
            print(f'   [{kind}] {keep[0]}#{keep[1]} {keep[2]}《{keep[3]}》')
            print(f'          重复于 {drop[0]}#{drop[1]} {drop[2]}《{drop[3]}》')

    if args.only in (None, 'dynasty'):
        valid, bad_value, conflict = check_dynasty()
        print(f'== dynasty: 非法取值 {sum(bad_value.values())} 条，与作者索引冲突 {sum(conflict.values())} 条')
        for (rel, d), n in bad_value.most_common(args.show):
            print(f'   {rel}: dynasty={d!r} ×{n}')
        for (rel, a, d, expect), n in conflict.most_common(args.show):
            print(f'   {rel}: {a} 记作 {d}，索引作 {expect} ×{n}')

    if args.out and rows is not None:
        import csv
        with open(os.path.join(ROOT, args.out), 'w', encoding='utf-8', newline='') as fp:
            w = csv.writer(fp, delimiter='\t', lineterminator='\n')
            w.writerow(['判定', '正文前16字', '保留', '重复'])
            for body, kind, keep, drop in rows:
                w.writerow([kind, body, f'{keep[0]}#{keep[1]} {keep[2]}《{keep[3]}》',
                            f'{drop[0]}#{drop[1]} {drop[2]}《{drop[3]}》'])
        print(f'明细写入 {args.out}')


if __name__ == '__main__':
    sys.exit(main())
