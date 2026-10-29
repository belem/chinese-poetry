#!/usr/bin/env python3
"""《全宋词》里与《花间集》《南唐二主词》重出的五代十国词：删 `ci.song.22000.json` 里那一套。

`ci.song.22000.json` 是后补的一批《全宋词》录文，把《花间集》《南唐二主词》里五代十国的词
也收了进来（李煜、李璟、牛峤、毛文锡、顾夐、孙光宪、魏承班、牛希济）。这些人的词在
`五代十国/词/五代诗词/` 有专书，`merge_anthologies.py` 2026-10 只清过 `poet.tang`，
没碰 `ci.song.*`。

判据：

- 正文 `t2s` 去标点后前 16 字相同；
- 作者同一人：**署名一致**（`顾敻/顾夐` 是同一人的两种写法，收在 `ALIAS` 里），
  或《全宋词》那条把五代词人署成了「无名氏」；
- 正文相似度 ≥ 0.90（差的是 `孤/辜`、`荭/葓`、`渌/绿`、`帏/帷` 这类用字）。

满足就删 `ci.song.*` 那条，留 `五代十国/词/五代诗词/` 的专书。

**作者不同的一条不删**（这是这一批最要紧的一条）：`ci.song.1000.json` 把李煜《浣溪沙·风压轻云贴水飞》
收在苏轼名下、邓肃名下的《长相思》与李煜重、无名氏的《捣练子》与李煜重 —— 那是《全宋词》自己的
归属，正文相似度 0.89～0.95，两存（与《全唐诗》《全宋词》归属异说同一口径）。

用法：
  python3 scripts/dedupe_songci_huajian.py                      # 预演
  python3 scripts/dedupe_songci_huajian.py --apply --date YYYY-MM-DD
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
SONGCI = '宋/宋词'
SRC = ['五代十国/词/五代诗词/huajianji', '五代十国/词/五代诗词/nantang']
OUT = 'docs/宋词五代词去重.tsv'
REVIEWER = 'codebuddy'
NONE_AUTHOR = {'', '无名氏', '佚名', '不详'}
# 《全宋词》里的写法 → 五代专书里的写法
ALIAS = {'顾夐': '顾敻'}


def han(s):
    return HAN.sub('', T2S.convert(s or ''))


def body(rec):
    p = rec.get('paragraphs')
    return han(p if isinstance(p, str) else ''.join(p or ''))


def author(rec):
    a = T2S.convert(str(rec.get('author') or '').strip())
    return ALIAS.get(a, a)


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

    files = sorted(f'{SONGCI}/{f}' for f in os.listdir(os.path.join(ROOT, SONGCI))
                   if re.fullmatch(r'ci\.song\..*\.json', f))
    data = {rel: json.load(open(os.path.join(ROOT, rel), encoding='utf-8')) for rel in files}
    src = []
    for d in SRC:
        for f in sorted(glob.glob(os.path.join(ROOT, d, '*.json'))):
            for r in json.load(open(f, encoding='utf-8')):
                if isinstance(r, dict) and body(r):
                    src.append((os.path.relpath(f, ROOT), r))
    index = collections.defaultdict(list)
    for rel, r in src:
        b = body(r)
        if len(b) >= 16:
            index[b[:16]].append((rel, r))

    drop = collections.defaultdict(set)
    rows = []
    for rel, recs in data.items():
        for i, rec in enumerate(recs):
            b = body(rec)
            cands = index.get(b[:16], []) if len(b) >= 16 else []
            if not cands:
                continue
            other_rel, other = max(cands, key=lambda x: difflib.SequenceMatcher(None, b, body(x[1])).ratio())
            ratio = difflib.SequenceMatcher(None, b, body(other)).ratio()
            mine, theirs = author(rec), author(other)
            title = f"{rec.get('author')}《{rec.get('rhythmic') or rec.get('title') or ''}》"
            keep = f"{other_rel} {other.get('author')}《{other.get('title')}》"
            if mine not in NONE_AUTHOR and mine != theirs:
                rows.append(dict(kind='两存', path=rel, title=title, length=len(b), keep=keep,
                                 ratio=f'{ratio:.2f}',
                                 note=f'作者不同（{mine}／{theirs}）：归属异说，两存'))
                continue
            if ratio < 0.90:
                rows.append(dict(kind='两存', path=rel, title=title, length=len(b), keep=keep,
                                 ratio=f'{ratio:.2f}', note='正文出入过大，两存待核'))
                continue
            drop[rel].add(i)
            rows.append(dict(kind='删除', path=rel, title=title, length=len(b), keep=keep,
                             ratio=f'{ratio:.2f}',
                             note=('《全宋词》署无名氏' if mine in NONE_AUTHOR else '同一人') +
                                  '，留五代专书那份'))

    n = sum(r['kind'] == '删除' for r in rows)
    print(f'== 《全宋词》与花间集/南唐：{len(rows)} 条，删 {n} 条、两存 {len(rows) - n} 条')
    with open(os.path.join(ROOT, args.out), 'w', encoding='utf-8', newline='') as fp:
        w = csv.DictWriter(fp, delimiter='\t', lineterminator='\n', fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    print(f'明细写入 {args.out}')

    if not args.apply:
        print('（预演，未改动任何文件；加 --apply 落盘）')
        return 0

    for rel, idxs in drop.items():
        dump(rel, [r for i, r in enumerate(data[rel]) if i not in idxs])
    by_file = collections.defaultdict(list)
    for r in rows:
        if r['kind'] == '删除':
            by_file[r['path']].append(dict(original=r['title'], corrected='删除',
                                           note=f"与 {r['keep']} 同首（相似度 {r['ratio']}），留五代专书"))
    for rel, fixes in by_file.items():
        rec = pg.merge(rel, dict(fixes=fixes))
        rec['note'] = ((rec.get('note') or '').rstrip() +
                       f' {args.date} 重复清理：删 {len(fixes)} 条与花间集/南唐重出的五代词，'
                       f'逐条见 {args.out}。').strip()
        pg.write_record(rel, pg.ordered(rec))
    pg.write_index()
    print(f'进度记录 {len(by_file)} 个文件')
    return 0


if __name__ == '__main__':
    sys.exit(main())
