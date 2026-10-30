#!/usr/bin/env python3
"""`先秦/文/` 的子史单行本与 `汇编/古文观止` `汇编/课本选目` 的同篇：删选本摘录。

《古文观止》的周文、战国文各卷，本来就是从《左传》《国语》《公羊传》《穀梁传》《礼记》
《战国策》《庄子》这些书里摘出来的；课本选目也一样。同一篇在单行本与选本各有一份正文，
勘误时两边都要改，改漏就漂。

与 [`汇编与诗去重`](汇编与诗去重.md) 相反、与 [`左传古文观止去重`](左传古文观止去重.md) 同一个口径：
`先秦/文/` 是整部书（有卷次、有编次），选本只是从书里摘出的同一段 ——
按「一件作品只留一份正文」，留书、删选本摘录。

判据（三条都要）
----------------
1. 题名对得上（`t2s` 归一后相等，或单行本的题名是「书名·篇名」而选本取篇名）；
2. 作者同一人或选本署「佚名」（《古文观止》卷三把《国语》《礼记》的篇都署了佚名）；
3. 正文 `t2s` 归一后**一字不差，或只差通用字**（`於/于`、`餘/余`、`无/毋`、`篑/蒉`、`亡/忘`），
   且选本不比单行本长 —— 差的是两读都传世的异文，或选本多了纪年文字与夹注，一律两存。

删哪一条：删**选本**那一条。选本目录要记「这本书收了哪几篇」，
删下去的那几篇记进 `汇编/古文观止/古文观止·选目.json`（已有，260 条目次）。

用法：
  python3 scripts/dedupe_xianqin_wen_gu.py            # 预演
  python3 scripts/dedupe_xianqin_wen_gu.py --apply --date YYYY-MM-DD
"""
import argparse
import collections
import csv
import difflib
import glob
import json
import os
import re
import sys
from datetime import date

from opencc import OpenCC

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import progress as pg                       # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
T2S = OpenCC('t2s')
HAN = re.compile(r'[^\u4e00-\u9fff]')
WEN = '先秦/文'
GUI = ('汇编/古文观止', '汇编/课本选目')
OUT = 'docs/先秦文古文观止去重.tsv'
PREFIX = 16
REVIEWER = 'codebuddy'
# 通用字：两读都传世，不算异文
# 只收「一个字两种写法」的通用字。`余/馀`、`知/智`、`共/供`、`陈/阵` 这类是文白两读，
# 归并了会把真异文当同一篇删掉，不收。
VARIANT = {'於': '于', '毋': '无', '蒉': '篑', '忘': '亡', '脩': '修', '彊': '强',
           '舍': '捨', '说': '悦', '反': '返', '队': '坠'}
UNKNOWN = {'佚名', '无名氏', ''}


def han(s):
    return HAN.sub('', T2S.convert(s or ''))


def canon(text):
    return ''.join(VARIANT.get(c, c) for c in text)


def body(rec):
    p = rec.get('paragraphs')
    if isinstance(p, list) and p and all(isinstance(x, str) for x in p):
        return han(''.join(p))
    return ''


def walk(node, rel, path=()):
    if isinstance(node, dict):
        p = node.get('paragraphs')
        if isinstance(p, list) and p and all(isinstance(x, str) for x in p):
            yield rel, path, node
            return
        for k, v in node.items():
            if isinstance(v, (list, dict)):
                yield from walk(v, rel, path + (k,))
    elif isinstance(node, list):
        for i, v in enumerate(node):
            yield from walk(v, rel, path + (i,))


def author_ok(a, b):
    a, b = han(a), han(b)
    return a == b or b in UNKNOWN or a in UNKNOWN


def title_ok(a, b):
    a, b = han(a), han(b)
    if not a or not b:
        return False
    ta = re.split(r'[·・]', a.replace('檀弓', '')) if '·' in a else [a]
    return a == b or b in ta or a.endswith(b)


def desc(x):
    where = x[1] if isinstance(x[1], str) else '/'.join(map(str, x[1]))
    return f"{x[0]}#{where} {x[3].get('author') or ''}《{x[3].get('title') or x[3].get('chapter') or ''}》"


def dump(rel, data):
    """写回，只让删掉的记录进 diff（同 scripts/dedupe_huibian_poet.py）。"""
    path = os.path.join(ROOT, rel)
    raw = open(path, encoding='utf-8').read()
    m = re.search(r'\n( +)\S', raw)
    indent = len(m.group(1)) if m else 2
    out = json.dumps(data, ensure_ascii=False, indent=indent) + ('\n' if raw.endswith('\n') else '')
    sep = '\n' + ' ' * indent + '{'
    head, *old = raw.split(sep)
    _, *new = out.split(sep)

    def same(x, y):
        a, b = x.split('\n'), y.split('\n')
        return len(a) == len(b) and all(p.rstrip(' ') == q.rstrip(' ') for p, q in zip(a, b))

    res, i, j = [head], 0, 0
    while j < len(new) and i < len(old):
        if same(old[i], new[j]):
            res.append(old[i])
            i, j = i + 1, j + 1
        else:
            i += 1
    res.extend(old[i:])
    text = sep.join(res)
    try:
        json.loads(text)
    except ValueError:
        text = out
    if text != raw:
        with open(path, 'w', encoding='utf-8') as fp:
            fp.write(text)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--apply', action='store_true')
    ap.add_argument('--date', default=date.today().isoformat())
    ap.add_argument('--reviewer', default=REVIEWER)
    ap.add_argument('--out', default=OUT)
    args = ap.parse_args()

    data, recs = {}, []
    for f in sorted(glob.glob(os.path.join(ROOT, WEN, '*.json'))):
        rel = os.path.relpath(f, ROOT)
        with open(f, encoding='utf-8') as fp:
            d = json.load(fp)
        if not isinstance(d, list):
            continue
        data[rel] = d
        for i, rec in enumerate(d):
            b = body(rec)
            if len(b) >= PREFIX:
                recs.append(('book', rel, i, rec, b))
    for d in GUI:
        for f in sorted(glob.glob(os.path.join(ROOT, d, '*.json'))):
            rel = os.path.relpath(f, ROOT)
            if rel.endswith('古文观止·选目.json'):
                continue
            with open(f, encoding='utf-8') as fp:
                node = json.load(fp)
            for r, path, rec in walk(node, rel):
                b = body(rec)
                if len(b) >= PREFIX:
                    data.setdefault(rel, node)
                    recs.append(('gui', rel, path, rec, b))

    index = collections.defaultdict(list)
    for x in recs:
        index[x[4][:PREFIX]].append(x)
    # 选本那条按「路径」删：结构里没有 id
    for x in recs:
        pass

    rows, drop = [], collections.defaultdict(set)
    stat = collections.Counter()
    for key, items in index.items():
        books = [x for x in items if x[0] == 'book']
        guis = [x for x in items if x[0] == 'gui']
        if not books or not guis:
            continue
        b = books[0]
        for g in guis:
            if not title_ok(b[3].get('title'), g[3].get('title')):
                stat['题名对不上'] += 1
                continue
            if not author_ok(b[3].get('author'), g[3].get('author')):
                stat['作者不同'] += 1
                continue
            same = canon(b[4]) == canon(g[4])
            ratio = difflib.SequenceMatcher(None, canon(g[4]), canon(b[4])).ratio()
            if not same:
                stat['正文有出入（两存）'] += 1
                rows.append(dict(kind='两存', key=key, keep=desc(b), drop=desc(g),
                                 note=f't2s 与通用字归一后仍有出入（相似度 {ratio:.3f}，'
                                      f'{len(b[4])} / {len(g[4])} 字），两读并存'))
                continue
            if len(g[4]) > len(b[4]):
                stat['选本比单行本长（两存）'] += 1
                rows.append(dict(kind='两存', key=key, keep=desc(b), drop=desc(g),
                                 note='选本多了纪年文字或夹注，删了会丢那一层，两存'))
                continue
            drop[g[1]].add('/'.join(map(str, g[2])) if isinstance(g[2], tuple) else str(g[2]))
            stat['删选本那一条'] += 1
            rows.append(dict(kind='删除', key=key, keep=desc(b), drop=desc(g),
                             note='单行本与选本同篇，归一后一字不差；留整部书，删选本摘录'))

    print('== 先秦/文 与 汇编/古文观止、课本选目：')
    for k, v in sorted(stat.items(), key=lambda kv: -kv[1]):
        print(f'   {k:<18} {v}')
    print(f'   拟删 {sum(len(v) for v in drop.values())} 条，涉及 {len(drop)} 个文件')

    with open(os.path.join(ROOT, args.out), 'w', encoding='utf-8', newline='') as fp:
        w = csv.DictWriter(fp, delimiter='\t', lineterminator='\n',
                           fieldnames=['kind', 'key', 'keep', 'drop', 'note'])
        w.writeheader()
        w.writerows(rows)
    print(f'明细写入 {args.out}')

    if not args.apply:
        for r in rows:
            print(f"   {r['kind']} {r['drop'][:64]:<64} ← 留 {r['keep'][:44]}")
        print('（预演，未改动任何文件；加 --apply 落盘）')
        return 0

    # 选本那边的记录是嵌套结构，删的是「路径」而不是 id，逐文件按路径重写
    for rel, keys in drop.items():
        path = os.path.join(ROOT, rel)
        raw = open(path, encoding='utf-8').read()
        m = re.search(r'\n( +)\S', raw)
        indent = len(m.group(1)) if m else 2
        with open(path, encoding='utf-8') as fp:
            data[rel] = remove(json.load(fp), keys, rel)
        with open(path, 'w', encoding='utf-8') as fp:
            json.dump(data[rel], fp, ensure_ascii=False, indent=indent)
            fp.write('\n' if raw.endswith('\n') else '')

    by_file = collections.defaultdict(list)
    for r in rows:
        if r['kind'] == '删除':
            by_file[r['drop'].split('#')[0]].append(dict(
                original=r['drop'], corrected='删除',
                note=f"[xianqin-wen] {r['note']}；保留 {r['keep']}，见 {args.out}"))
    for rel, fs in by_file.items():
        rec = pg.merge(rel, dict(fixes=fs))
        rec['note'] = ((rec.get('note') or '').rstrip() +
                       f' {args.date} 重复清理：删 {len(fs)} 条与 `先秦/文/` 单行本同篇的摘录，'
                       f'逐条见 {args.out}。').strip()
        pg.write_record(rel, pg.ordered(rec))
    pg.write_index()
    print(f'进度记录 {len(by_file)} 个文件')
    return 0


def remove(node, keys, rel):
    """按「路径」删：选本一句一条的结构里没有 id，路径是 (索引, 索引, …)。"""
    if not isinstance(node, list):
        return node
    out = []
    for i, v in enumerate(node):
        if isinstance(v, (list, dict)) and v and not isinstance(v, str) and 'paragraphs' not in v:
            v = remove(v, {k[len(str(i)) + 1:] for k in keys if k.startswith(f'{i}/')}, rel)
            out.append(v)
        elif str(i) in keys or (isinstance(v, dict) and 'paragraphs' in v and str(i) in keys):
            continue
        else:
            out.append(v)
    return out


if __name__ == '__main__':
    sys.exit(main())
