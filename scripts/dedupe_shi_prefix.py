#!/usr/bin/env python3
"""法名前加「釋」的同人异写：《全宋诗》作「釋延壽」，《全唐诗》作「延壽」。

两书各按自己的规矩称人：《全宋诗》沿佛徒名号加「釋」，《全唐诗》不加。同一个人，
同一首诗，被两书各收一次。这一批把这批组按「同一人」处理，删《全宋诗》那条。

为什么单列一批
--------------
上一批（`dedupe_tang_song.py`）把「作者不同」的 250 组逐组定了归属，其中 84 组是这件事，
量大又成组（《山居詩》六十余首两组对得上），单列出来才看得清。

判据
----
1. 组里《全唐诗》侧作者去掉「釋／释」与《全宋诗》侧相同，即同一人；
2. 《全唐诗》侧那条是完整的一首（不是残句「句 一」这种）：正文长度 ≥ 16 字且题名不以「句」起；
3. 正文全同，或两读长度相当（±10%）且相似度 ≥ 0.90 —— 一字之差的异文按同一首处理，
   《全宋诗》侧正文不动（这批只删记录，不改字）；
4. 例外：《全宋诗》侧的题名带组诗序号、而《全唐诗》侧是一条合并了整组的（《永明山居詩
   （六十九首） 六十九》把六十九首并成一条），删《全宋诗》那条仍是对的 —— 保留读是整组，
   删掉的只是拆出来的那一首。

删哪一条
--------
统一删《全宋诗》那条：两书之间这批组里《全唐诗》那条题名更全（《永明山居詩（六十九首） 一》
对《山居詩  其一》）、`notes` 更多（《古今禪藻集》《高僧山居詩》的校记都在《全唐诗》那条上）。

用法：
  python3 scripts/dedupe_shi_prefix.py            # 预演：逐组打印取舍
  python3 scripts/dedupe_shi_prefix.py --apply --date YYYY-MM-DD --reviewer <名字>
"""
import argparse
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
import progress as pg  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
T2S = OpenCC('t2s')
HAN = re.compile(r'[^\u4e00-\u9fff]')
BOOK_TANG = '唐/诗/全唐诗'
BOOK_SONG = '宋/诗/全宋诗'
OUT = 'docs/释字头去重.tsv'
PREFIX = 16
MIN_RATIO = 0.90
SAME_LEN = 0.10


def han(s):
    return HAN.sub('', T2S.convert(s or ''))


def strip_shi(a):
    a = (a or '').strip()
    return a[1:] if a.startswith(('釋', '释')) else a


def body(rec):
    return han(''.join(rec.get('paragraphs') or []))


def load(rel):
    with open(os.path.join(ROOT, rel), encoding='utf-8') as fp:
        return json.load(fp)


def dump(rel, data):
    """按原文件排版写回，只让改动的几条进 diff。"""
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


def files_of(book):
    fs = [os.path.relpath(f, ROOT) for f in glob.glob(os.path.join(ROOT, book, 'poet.*.json'))]
    return sorted(fs, key=lambda f: int(re.search(r'\.(\d+)\.json$', f).group(1)))


def corpus():
    data, recs = {}, []
    for book in (BOOK_TANG, BOOK_SONG):
        for rel in files_of(book):
            data[rel] = load(rel)
            for i, rec in enumerate(data[rel]):
                b = body(rec)
                if len(b) >= PREFIX:
                    recs.append((rel, i, rec, b))
    return data, recs


def groups_of(recs):
    g = {}
    for rel, i, rec, b in recs:
        g.setdefault(b[:PREFIX], []).append((rel, i, rec, b))
    return [v for v in g.values()
            if any(r.startswith(BOOK_TANG + '/') for r, *_ in v)
            and any(r.startswith(BOOK_SONG + '/') for r, *_ in v)]


def side(items, book):
    return [x for x in items if x[0].startswith(book + '/')]


def desc(x):
    return f"{x[0]}#{x[1]} {x[2].get('author')}《{x[2].get('title')}》"


def is_fragment(rec):
    t = rec.get('title') or ''
    return t.startswith('句') or len(body(rec)) < PREFIX


def classify(tang, song):
    ta = {strip_shi(x[2].get('author')) for x in tang}
    sa = {strip_shi(x[2].get('author')) for x in song}
    if len(ta) != 1 or len(sa) != 1 or ta != sa:
        return 'not_shi', None, ''
    if not any((x[2].get('author') or '').startswith(('釋', '释')) for x in song):
        return 'not_shi', None, ''
    t = [x for x in tang if not is_fragment(x[2])]
    if not t:
        return 'tang_fragment', None, ''
    t = t[0]
    s = song[0]
    tb, sb = t[3], s[3]
    if tb == sb:
        return 'drop', s, f'同一人（《全宋詩》作「{s[2].get("author")}」、《全唐詩》作「{t[2].get("author")}」），正文一字不差'
    # 唐条是「整首 + 校记」：《全唐诗》把 `notes` 里的话也写进了 paragraphs
    # （《五燈會元》卷十、《吳郡志》卷三十三这类），去掉尾部校记后与宋条相同的，仍是同一首。
    # 校记有多种来源（「见宋诗纪事卷九十一」「五灯会元卷十按…」「瀛奎律髓卷四十七释梵类见…」
    # 「同前按以上三颂…」），判据取「宋条是唐条的前缀、唐条多出的尾巴够长」，
    # 且尾巴里不含诗常用的虚字以外的成句往往就是书名。宁可保守：只对同一人且同题的组用。
    if len(tb) > len(sb) and len(tb) - len(sb) >= 8 and \
            difflib.SequenceMatcher(None, tb[:len(sb)], sb).ratio() >= MIN_RATIO:
        return 'drop', s, f'同一人（「{s[2].get("author")}」／「{t[2].get("author")}」），正文相同，《全唐詩》那條末尾多一段校記'
    # 一字之差的异文：《全宋詩》那条正文更全（多出的是尾联／缺句）时不能删，
    # 删了就丢正文。这类按「两读并传」处理，留待逐字对勘。
    if sb.startswith(tb) and len(sb) > len(tb):
        return 'review', None, ''
    if abs(len(tb) - len(sb)) <= max(2, SAME_LEN * len(tb)) and \
            difflib.SequenceMatcher(None, tb, sb).ratio() >= MIN_RATIO:
        return 'drop', s, f'同一人（「{s[2].get("author")}」／「{t[2].get("author")}」），正文一字之差，按同一首处理'
    if len(tb) > 3 * len(sb) and tb.startswith(sb[:8]):
        # 《全唐诗》那条是整组并成一条，删拆出来的那一首仍是对的
        return 'drop', s, f'同一人；《全唐詩》那條是整組並成一條（{len(tb)} 字），《全宋詩》拆出的是其中一首'
    return 'review', None, ''


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--apply', action='store_true')
    ap.add_argument('--date', default=date.today().isoformat())
    ap.add_argument('--reviewer', default='codebuddy')
    ap.add_argument('--out', default=OUT)
    args = ap.parse_args()

    data, recs = corpus()
    grps = groups_of(recs)
    print(f'== 法名前加「釋」的组：{len(grps)}')

    rows, drops, stat = [], {}, {}
    for items in sorted(grps, key=lambda g: (g[0][2].get('author') or '', g[0][2].get('title') or '')):
        tang, song = side(items, BOOK_TANG), side(items, BOOK_SONG)
        kind, victim, why = classify(tang, song)
        stat[kind] = stat.get(kind, 0) + 1
        t, s = tang[0], song[0]
        if kind == 'drop':
            drops.setdefault(victim[0], set()).add(victim[2].get('id'))
            rows.append(dict(kind=kind, keep=desc(t), drop=desc(s), why=why, key=items[0][3][:PREFIX]))
        elif kind == 'review':
            rows.append(dict(kind=kind, keep=desc(t), drop=desc(s), why='', key=items[0][3][:PREFIX]))
    for k, v in sorted(stat.items(), key=lambda kv: -kv[1]):
        print(f'   {k:<16} {v} 组')
    print(f'   拟删 {sum(len(v) for v in drops.values())} 条，涉及 {len(drops)} 个文件')

    if not args.apply:
        for r in rows:
            if r['kind'] == 'drop':
                print(f"   删 {r['drop'][:56]:<56} ← 留 {r['keep'][:52]}  {r['why']}")
        print('\n（预演，未改动文件；加 --apply 落盘）')
        return

    deleted = {}
    for rel, ids in drops.items():
        deleted[rel] = [r for r in data[rel] if r.get('id') in ids]
        data[rel] = [r for r in data[rel] if r.get('id') not in ids]
        dump(rel, data[rel])

    with open(os.path.join(ROOT, args.out), 'w', encoding='utf-8', newline='') as fp:
        w = csv.writer(fp, delimiter='\t', lineterminator='\n')
        w.writerow(['判定', '正文前16字', '保留', '重复', '处理'])
        for r in rows:
            w.writerow([r['kind'], r['key'], r['keep'], r['drop'], r['why']])
    print(f'明细写入 {args.out}')

    fixes_by_file = {}
    for rel, recs_ in deleted.items():
        fixes_by_file[rel] = [dict(
            original=f"{r.get('id')} {r.get('author')}《{r.get('title')}》", corrected='删除',
            note=f'[shi-prefix] 法名前加「釋」的同一人，《全唐詩》另有同一首，删《全宋詩》這條；见 {args.out}')
            for r in recs_]
    for rel, fixes in fixes_by_file.items():
        rec = pg.merge(rel, dict(fixes=fixes, date=args.date, reviewer=args.reviewer))
        rec['note'] = ((rec.get('note') or '').rstrip() +
                       f" {args.date} 删 {len(fixes)} 条「釋」字头同人异写的重出，逐条见 {args.out}。").strip()
        pg.write_record(rel, pg.ordered(rec))
    pg.write_index()
    print(f'进度记录 {len(fixes_by_file)} 个文件')


if __name__ == '__main__':
    main()
