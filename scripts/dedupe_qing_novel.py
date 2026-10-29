#!/usr/bin/env python3
"""`清/诗/poet.qing.json` 里混进的整部章回小说：删补录那一套，留 `清/小说/` 的版本校本。

`poet.qing.json` 是《历代》按作者朝代拆出来的补录（正文来自 海棠诗社语料），里面混着
《红楼梦》120 回、《聊斋志异》3 篇——整部书的另一份录文，简繁、用字都与 `清/小说/` 那套不同。

两套不是同一份底本：《左传》三本／程甲本一系的通行本与庚辰本本身就有异文
（`着/著`、`蹋/踏`、`淅淅`的位置、整句的有无），所以**不能逐字判重**，按条目对齐、核过就删：

  pair       同一条回目/篇题（回次、篇名对得上），且正文长度相近（±25%）
  body       正文长度差在 ±25% 以内、`t2s` 去标点后相似度 ≥ 0.95

判为「同一回」的删 `poet.qing.json` 那条——`清/小说/` 是依识典古籍某个具体版本抓的、
带版本交代（见 `docs/新增名著.md`），补录那套没有底本信息。
对不上的（如庚辰本缺回、回次不齐的）两存，记进 TSV。

用法：
  python3 scripts/dedupe_qing_novel.py                    # 预演
  python3 scripts/dedupe_qing_novel.py --apply --date YYYY-MM-DD
"""
import argparse
import collections
import csv
import difflib
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
QING = '清/诗/poet.qing.json'
OUT = 'docs/清诗小说去重.tsv'
REVIEWER = 'codebuddy'

# 书题 → `清/小说/` 里的正文
BOOKS = {
    '红楼梦': '清/小说/红楼梦/hongloumeng.json',
    '聊斋志异': '清/小说/聊斋志异/liaozhaizhiyi.json',
}
CN = {'零': 0, '一': 1, '二': 2, '三': 3, '四': 4, '五': 5, '六': 6, '七': 7, '八': 8, '九': 9}


def han(s):
    return HAN.sub('', T2S.convert(s or ''))


def body(rec):
    p = rec.get('paragraphs')
    return han(p if isinstance(p, str) else ''.join(p or []))


def number(s):
    """`第一百一十七回` → 117。"""
    s = s.split('回')[0]
    total, cur = 0, 0
    for ch in s:
        if ch in CN:
            cur = CN[ch]
        elif ch == '十':
            total += (cur or 1) * 10
            cur = 0
        elif ch == '百':
            total += cur * 100
            cur = 0
    return total + cur


def loose(s):
    """再抹一层正俗 / 异体：`着/著`、`蹋/踏`、`与/與`（t2s 已转）之外的常见异写，
    比「同一回」时不该算差异。只用于相似度，不改正文。"""
    table = str.maketrans({'着': '著', '蹋': '踏', '徃': '往', '群': '羣', '须': '鬚'})
    return s.translate(table).replace('紈絝', '纨袴').replace('规谈', '规训')


def best_ratio(a, b):
    """补录那一回是对方的一节（或反过来）时，按等长窗口比一次。

    庚辰本十七、十八回未分回，作一条；补录那套按程甲本分回，十七回只到「再看下回分解」，
    跟整条比相似度只有 0.63。所以取「以对方的一半为窗、滑着比」，取最大的一窗。
    """
    la, lb = loose(a), loose(b)
    if len(lb) <= len(la) * 1.6:
        return difflib.SequenceMatcher(None, la, lb, autojunk=False).ratio(), len(la), len(la)
    best, span = 0.0, len(la)
    step = max(1, len(la) // 8)
    for start in range(0, max(1, len(lb) - len(la) + 1), step):
        sm = difflib.SequenceMatcher(None, la, lb[start:start + len(la)], autojunk=False)
        if sm.ratio() > best:
            best, span = sm.ratio(), sum(b.size for b in sm.get_matching_blocks())
    return best, span, len(la)


def seq_of(rec):
    """(回次 / 篇题, 正文)——`红楼梦·第一百一十七回·…` 取 117，`聊斋志异·卷六·狼三则（其一）` 取篇题。"""
    title = str(rec.get('title') or '')
    book = title.split('·')[0]
    if book == '红楼梦':
        m = re.search(r'第([零一二三四五六七八九十百]+)回', title)
        return book, number(m.group(1)) if m else None
    parts = title.split('·')
    return book, parts[-1] if len(parts) > 1 else None


def novel_seq(rec, book):
    title = str(rec.get('title') or '')
    if book == '红楼梦':
        m = re.search(r'第(\d+)回', title)
        return int(m.group(1)) if m else None
    return title.split('·')[-1]


def dump(rel, data):
    """写回，且只让「删掉的记录」进 diff（同 scripts/dedupe_songci_full.py）。"""
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

    qing = json.load(open(os.path.join(ROOT, QING), encoding='utf-8'))
    books = {b: json.load(open(os.path.join(ROOT, rel), encoding='utf-8')) for b, rel in BOOKS.items()}
    index = {b: {novel_seq(r, b): r for r in recs} for b, recs in books.items()}

    drop, rows = set(), []
    for i, rec in enumerate(qing):
        title = str(rec.get('title') or '')
        if title.split('·')[0] not in BOOKS:
            continue
        book, seq = seq_of(rec)
        other = index[book].get(seq)
        b = body(rec)
        if other is None:
            rows.append(dict(kind='两存', book=book, title=title, length=len(b), keep='',
                             ratio='', note='《' + book + '》里没有这一回/这一篇（底本不齐），无对应'))
            continue
        ob = body(other)
        ratio, matched, span = best_ratio(b, ob)
        near = abs(matched - len(b)) <= max(20, 0.25 * len(b))
        if not (near and ratio >= 0.90):
            rows.append(dict(kind='两存', book=book, title=title, length=len(b),
                             keep=f'{BOOKS[book]}#{(other.get("title") or "")[:12]}',
                             ratio=f'{ratio:.3f}', note='回次对得上但正文出入过大，两存待核'))
            continue
        drop.add(i)
        rows.append(dict(kind='删除', book=book, title=title, length=len(b),
                         keep=f'{BOOKS[book]}#{other.get("title")}", '.rstrip('", '),
                         ratio=f'{ratio:.3f}',
                         note=f'与《{other.get("title")}》同一回（相似度 {ratio:.3f}），'
                              f'补录那套无底本，留版本校本'))

    n = sum(r['kind'] == '删除' for r in rows)
    print(f'== `poet.qing.json` 里的章回小说：{len(rows)} 条，删 {n} 条、两存 {len(rows) - n} 条')
    for b in BOOKS:
        print(f'   《{b}》删 {sum(1 for r in rows if r["kind"] == "删除" and r["book"] == b)} 条')

    with open(os.path.join(ROOT, args.out), 'w', encoding='utf-8', newline='') as fp:
        w = csv.DictWriter(fp, delimiter='\t', lineterminator='\n',
                           fieldnames=['kind', 'book', 'title', 'length', 'keep', 'ratio', 'note'])
        w.writeheader()
        w.writerows(rows)
    print(f'明细写入 {args.out}')

    if not args.apply:
        print('（预演，未改动任何文件；加 --apply 落盘）')
        return 0

    dump(QING, [r for i, r in enumerate(qing) if i not in drop])
    fixes = [dict(original=r['title'], corrected='删除',
                  note=f"与 {r['keep']} 同一回（相似度 {r['ratio']}），整部书见 清/小说/")
             for r in rows if r['kind'] == '删除']
    rec = pg.merge(QING, dict(fixes=fixes))
    rec['note'] = ((rec.get('note') or '').rstrip() +
                   f' {args.date} 重复清理：删 {len(fixes)} 条章回小说副本（《红楼梦》《聊斋志异》），'
                   f'逐条见 {args.out}。').strip()
    pg.write_record(QING, pg.ordered(rec))
    pg.write_index()
    print('进度记录 1 个文件')
    return 0


if __name__ == '__main__':
    sys.exit(main())
