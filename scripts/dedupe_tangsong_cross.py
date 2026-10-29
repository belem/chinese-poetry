#!/usr/bin/env python3
"""《全唐诗》与《全宋诗》互见于同一作者的同一首：删后收的那一部（宋）。

《全唐诗》末几卷（`poet.tang.5*`）收的是五代八宋的诗人：徐鉉、劉兼、王周、譚用之、孟貫、
李九齡、伍喬、朱存、胡宿、陳摶…… 他们入宋以后的诗，《全宋诗》又收了一遍。两书各自有底本，
但同一首诗的正文一字不差时，就是同一首，不该两处各留一份。

判据（都要）：

  1. 作者署名**一字不差**（简体化后比）；
  2. 正文 `t2s` 去标点后**整篇相同**；
  3. 两边题的题名可以对上（一条题名是另一条的后缀/前缀，或词袋重合 ≥ 0.5）——
     《全唐诗》的「秦淮（以下景物）」与《全宋诗》的「金陵覽古 秦淮」是编法不同，不算冲突。

删哪一本：**删《全宋诗》那条**。这些人物的**编次**在《全宋诗》第一卷（宋初），但正文的**底本**
在《全唐诗》那边更早、更完整（如徐鉉 309 首、《全宋诗》只收 229 首），且《全宋诗》这条下一批
还要按作者对齐（见 docs/全宋诗作者对齐.md）。删重复的一份，不影响「《全宋诗》收了哪些」——
那层信息在 `宋/诗/全宋诗/` 的目录与卷次里。

作者不同的（张冠李戴、归属异说）一律不动，另出报告。

用法：
  python3 scripts/dedupe_tangsong_cross.py                      # 预演
  python3 scripts/dedupe_tangsong_cross.py --apply --date YYYY-MM-DD
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
TANG = '唐/诗/全唐诗/poet.tang.*.json'
SONG = '宋/诗/全宋诗/poet.song.*.json'
OUT = 'docs/唐宋跨书互见.tsv'
REVIEWER = 'codebuddy'


def han(s):
    return HAN.sub('', T2S.convert(s or ''))


def body(rec):
    p = rec.get('paragraphs')
    return han(p if isinstance(p, str) else ''.join(p or []))


def author(rec):
    return T2S.convert(str(rec.get('author') or '').strip())


def title(rec):
    return T2S.convert(str(rec.get('title') or rec.get('rhythmic') or ''))


def tame(t):
    """题名的词袋：去掉卷次、括号里的编注、标点。"""
    t = re.sub(r'（[^）]*）|\([^)]*\)', '', t)
    return collections.Counter(han(re.sub(r'[一二三四五六七八九十]+首$', '', t)))


def tame_ok(a, b):
    ta, tb = title(a), title(b)
    if ta in tb or tb in ta:
        return True
    ca, cb = tame(ta), tame(tb)
    small, big = (ca, cb) if sum(ca.values()) <= sum(cb.values()) else (cb, ca)
    tot = sum(small.values()) or 1
    return sum((small & big).values()) / tot >= 0.5


# 正俗 / 异体 / 通假：这些字在古书里两种写法都通行，判「同一首」时先抹平（写回时不改正文）
VARIANTS = str.maketrans({'徧': '遍', '岗': '冈', '祇': '只', '枑': '■', '萡': '箔', '■': '枑'})


def flat(b):
    return b.translate(VARIANTS)


def load(pat):
    out = []
    for f in sorted(glob.glob(os.path.join(ROOT, pat))):
        if '/error/' in f or not os.path.basename(f).startswith(os.path.basename(pat).split('*')[0]):
            continue
        rel = os.path.relpath(f, ROOT)
        for i, r in enumerate(json.load(open(f, encoding='utf-8'))):
            b = body(r)
            if len(b) >= 16:
                out.append((rel, i, r, b))
    return out


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

    tang = load(TANG)
    song = load(SONG)
    index = collections.defaultdict(list)
    for rel, i, r, b in tang:
        index[b[:16]].append((rel, i, r, b))
    song_data = collections.defaultdict(list)
    for rel, i, r, b in song:
        song_data[rel].append((i, r))

    drop = collections.defaultdict(set)
    rows = []
    for rel, i, r, b in song:
        for trel, ti, tr, tb in index.get(b[:16], []):
            pa, sa = author(tr), author(r)
            mine = f'{pa}《{title(tr)}》', f'{sa}《{title(r)}》'
            if pa != sa:
                rows.append(dict(kind='两存', tang=f'{trel}#{ti} {mine[0]}', song=f'{rel}#{i} {mine[1]}',
                                 note=f'作者不同（{pa}／{sa}）：归属异说或张冠李戴，两存待核'))
                continue
            ratio = difflib.SequenceMatcher(None, flat(tb), flat(b), autojunk=False).ratio()
            if tb != b and not (len(tb) == len(b) and ratio >= 0.97):
                rows.append(dict(kind='两存', tang=f'{trel}#{ti} {mine[0]}', song=f'{rel}#{i} {mine[1]}',
                                 note=f'同作者，正文有出入（{len(tb)} 字 vs {len(b)} 字），两存待核'))
                continue
            if not tame_ok(tr, r):
                rows.append(dict(kind='两存', tang=f'{trel}#{ti} {mine[0]}', song=f'{rel}#{i} {mine[1]}',
                                 note='同作者、正文全同，但题名对不上（组诗拆条），两存'))
                continue
            drop[rel].add(i)
            rows.append(dict(kind='删除', tang=f'{trel}#{ti} {mine[0]}', song=f'{rel}#{i} {mine[1]}',
                             note=f'同一首（{pa}），正文全同，删《全宋诗》那份'))

    n = sum(r['kind'] == '删除' for r in rows)
    print(f'== 《全唐诗》↔《全宋诗》：{len(rows)} 组，删 {n} 条《全宋诗》记录、两存 {len(rows) - n} 组')
    with open(os.path.join(ROOT, args.out), 'w', encoding='utf-8', newline='') as fp:
        w = csv.DictWriter(fp, delimiter='\t', lineterminator='\n',
                           fieldnames=['kind', 'tang', 'song', 'note'])
        w.writeheader()
        w.writerows(rows)
    print(f'明细写入 {args.out}')

    if not args.apply:
        print('（预演，未改动任何文件；加 --apply 落盘）')
        return 0

    for rel, idxs in drop.items():
        # 注意：dump() 是按「记录段」对齐原文的（只适用于顶层就是记录列表的文件）；
        # 全宋诗这些文件是同一格式，但删到最后一条时要保证收尾的 `]` 还在 —— 用 json 重 dump 更稳，
        # 缩进按原文件。
        data = [r for i, (i0, r) in enumerate(song_data[rel]) if i0 not in idxs]
        path = os.path.join(ROOT, rel)
        raw = open(path, encoding='utf-8').read()
        m = re.search(r'\n( +)\S', raw)
        indent = len(m.group(1)) if m else 2
        out = json.dumps(data, ensure_ascii=False, indent=indent) + ('\n' if raw.endswith('\n') else '')
        if out != raw:
            open(path, 'w', encoding='utf-8').write(out)
    by_file = collections.defaultdict(list)
    for r in rows:
        if r['kind'] == '删除':
            rel, idx = r['song'].split('#', 1)
            by_file[rel].append(dict(original=r['song'].split(' ', 1)[1], corrected='删除',
                                     note=f"与《全唐诗》{r['tang'].split(' ', 1)[1]} 同一首（正文全同），删后收的那份"))
    for rel, fixes in by_file.items():
        rec = pg.merge(rel, dict(fixes=fixes))
        rec['note'] = ((rec.get('note') or '').rstrip() +
                       f' {args.date} 重复清理：删 {len(fixes)} 条与《全唐诗》重出的记录，'
                       f'逐条见 {args.out}。').strip()
        pg.write_record(rel, pg.ordered(rec))
    pg.write_index()
    print(f'进度记录 {len(by_file)} 个文件')
    return 0


if __name__ == '__main__':
    sys.exit(main())
