#!/usr/bin/env python3
"""《全宋诗》里「同一人、两卷各收一次」的重出：题名可能不同，正文照样要逐字核。

`scripts/dedupe_quanmingshi.py` 只认同人同题、整篇逐字相同的；`scripts/dedupe_quanmingshi_anth.py`
只认选本那批。剩下这一类两条散在两个卷里、题名各异（组诗的《其N》与单篇、《詠懷 其一》与《感懷》、
释子的《偈頌》与《頌古》），要靠正文判：

1. 正文 `t2s` 归一去非汉字后**等长**；
2. 只有一处出入（差一到两个字，相邻的算一处），且那一字之差在识典古籍查得出是异体（两读皆有）
   或讹字（只有一读）；或整篇逐字相同。

差的字查不出的、多字出入的、长度不同的一律两存 —— 组诗拆条、编次不同、异文都在这一类里。
作者真的不同的也不动（那是归属异说），只有郊廟朝會歌辭这一种署名例外：那是乐辞的汇编署名，
不是作者，同一首乐章在几种仪式歌辞里各收一次，正文逐字相同即同一首。

逐条见 docs/全宋诗散卷重出.tsv。

用法：
  python3 scripts/dedupe_quanmingshi_pairs.py            # 预演
  python3 scripts/dedupe_quanmingshi_pairs.py --apply --date YYYY-MM-DD \
      --evidence <results.jsonl> --qmap <qmap.json>
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
HAN = re.compile(r'[^\u4e00-\u9fff\u3400-\u4dbf]')
BOOK = '宋/诗/全宋诗'
OUT = 'docs/全宋诗散卷重出.tsv'
REVIEWER = 'codebuddy'
# 郊庙朝会歌辞是乐辞的汇编署名，不是作者（见模块说明）
RITUAL = {'郊廟朝會歌辭', '郊庙朝会歌辞'}


def han(s):
    return HAN.sub('', T2S.convert(s or ''))


def body(rec):
    return han(''.join(rec.get('paragraphs') or []))


def load(rel):
    with open(os.path.join(ROOT, rel), encoding='utf-8') as fp:
        return json.load(fp)


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
    if len(new) == len(old):
        return

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


def windows(text):
    """识典古籍结果页里所有 6 字窗口（供逐字投票）。"""
    body = text.split('生成语料表格并进行分析。', 1)[-1]
    out = set()
    for para in body.split('\n'):
        p = para.replace('\n', '').strip()
        if not p or p.startswith('《') or re.fullmatch(r'\d+|上一页|下一页|对结果不满意，欢迎提供反馈意见', p):
            continue
        n = han(p)
        if len(n) < 4:
            continue
        for k in range(0, len(n) - 3):
            out.add(n[k:k + 6])
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--apply', action='store_true')
    ap.add_argument('--date', default=date.today().isoformat())
    ap.add_argument('--reviewer', default=REVIEWER)
    ap.add_argument('--evidence', help='识典古籍 results.jsonl')
    ap.add_argument('--qmap', help='记录键 → 检索式（dict 或 [[键, 式], …]）')
    ap.add_argument('--out', default=OUT)
    args = ap.parse_args()

    d = os.path.join(ROOT, BOOK)
    rels = [f'{BOOK}/{f}' for f in sorted(
        (f for f in os.listdir(d) if re.fullmatch(r'poet\.song\.\d+\.json', f)),
        key=lambda f: int(f.split('.')[2]))]
    data = {rel: load(rel) for rel in rels}
    index = collections.defaultdict(list)
    for rel in rels:
        for i, rec in enumerate(data[rel]):
            b = body(rec)
            if len(b) >= 16:
                index[b[:16]].append((rel, i, rec, b))

    res, qmap = {}, {}
    if args.evidence and os.path.exists(args.evidence):
        with open(args.evidence, encoding='utf-8') as fp:
            res = {r['q']: r['text'] for r in map(json.loads, fp) if not r.get('err')}
    if args.qmap:
        raw = json.load(open(args.qmap, encoding='utf-8'))
        qmap = dict(raw) if isinstance(raw, dict) else {x[0]: x[1] for x in raw}

    rows, drop = [], collections.defaultdict(set)
    for key, grp in index.items():
        if len(grp) < 2:
            continue
        auths = {r.get('author') for _, _, r, _ in grp}
        ritual = auths <= RITUAL and grp[0][3] == grp[1][3]
        if len(auths) > 1 and not ritual:
            continue        # 归属异说，两存
        if any(r.get('author') == '宋太宗' for _, _, r, _ in grp):
            continue        # 组诗重出，2026-10 已按识典古籍逐组核过
        a, b = grp[0], grp[1]
        desc = (f"{a[0].split('/')[-1]}#{a[1]} {a[2].get('author')}《{a[2].get('title')}》",
                f"{b[0].split('/')[-1]}#{b[1]} {b[2].get('author')}《{b[2].get('title')}》")
        if a[3] == b[3]:
            drop[a[0]].add(a[1])
            rows.append(dict(kind='删除（逐字相同）', keep=desc[1], drop=desc[0], diff='',
                             note='郊廟朝會歌辭里同一首乐章两处各收一次，正文逐字相同' if ritual
                             else '同一人两卷各收一次，正文逐字相同'))
            continue
        if len(a[3]) != len(b[3]):
            rows.append(dict(kind='两存（多字出入）', keep=desc[1], drop=desc[0],
                             diff=f'{len(a[3])}/{len(b[3])}', note='长度不同：组诗拆条或编次不同'))
            continue
        sm = difflib.SequenceMatcher(None, a[3], b[3], autojunk=False)
        ops = [(t, i1, i2, j1, j2) for t, i1, i2, j1, j2 in sm.get_opcodes() if t != 'equal']
        merged = []
        for op in ops:                       # 相邻的一字之差（明/名、玄/虚 挨着）算一处
            if merged and op[1] - merged[-1][2] <= 2 and op[3] - merged[-1][4] <= 2:
                merged[-1] = (merged[-1][0], merged[-1][1], op[2], merged[-1][3], op[4])
            else:
                merged.append(op)
        ops = merged
        if len(ops) > 1:
            rows.append(dict(kind='两存（多字出入）', keep=desc[1], drop=desc[0],
                             diff='; '.join(f'{a[3][i1:i2]}/{b[3][j1:j2]}' for _, i1, i2, j1, j2 in ops),
                             note='多处出入：异文，两存'))
            continue
        _, i1, i2, j1, j2 = ops[0]
        da, db = a[3][i1:i2], b[3][j1:j2]
        qs = qmap.get(f'{a[0]}#{a[1]}')
        W = set()
        for q in (qs if isinstance(qs, list) else [qs] if qs else []):
            if q in res:
                W |= windows(res[q])
        hit = set()
        for who, seg in (('前', a[3][max(0, i1 - 4):i2 + 4]), ('后', b[3][max(0, j1 - 4):j2 + 4])):
            # 差异两侧各带 4 字的片段，从 8 字往短试；任一段落在古籍结果的 6 字窗口里即算这一读有书证
            for L in range(min(len(seg), 8), 3, -1):
                if any(seg[k:k + L] in W for k in range(0, len(seg) - L + 1)):
                    hit.add(who)
                    break
        if W and len(hit) == 2:
            drop[a[0]].add(a[1])
            rows.append(dict(kind='删除', keep=desc[1], drop=desc[0], diff=f'{da}/{db}',
                             note='一字之差，两读皆见于识典古籍：异体，删重复的一条'))
        elif W and len(hit) == 1:
            drop[a[0]].add(a[1])
            bad = '前一条' if '前' in hit else '后一条'
            rows.append(dict(kind='删除', keep=desc[1], drop=desc[0], diff=f'{da}/{db}',
                             note=f'一字之差，古籍只证了{bad}那一读；删重复的一条，讹字另行记 needs_review'))
        else:
            rows.append(dict(kind='两存（异文未证）', keep=desc[1], drop=desc[0], diff=f'{da}/{db}',
                             note='一字之差，古籍查不出是哪一读，两存'))

    n = sum(len(v) for v in drop.values())
    print(f'== {BOOK} 散卷重出：逐组核 {len(rows)} 组，删 {n} 条')
    for k in ('删除（逐字相同）', '删除', '两存（异文未证）', '两存（多字出入）'):
        print(f'   {k}: {sum(1 for r in rows if r["kind"] == k)}')

    if not args.apply:
        print('（预演，未写盘；加 --apply 写回）')
        return

    for rel in rels:
        if rel in drop:
            data[rel] = [r for i, r in enumerate(data[rel]) if i not in drop[rel]]
            dump(rel, data[rel])

    with open(os.path.join(ROOT, args.out), 'w', encoding='utf-8', newline='') as fp:
        w = csv.DictWriter(fp, delimiter='\t', lineterminator='\n',
                           fieldnames=['kind', 'keep', 'drop', 'diff', 'note'])
        w.writeheader()
        w.writerows(rows)
    print(f'明细写入 {args.out}')

    by_file = collections.defaultdict(list)
    for r in rows:
        if not r['kind'].startswith('删除'):
            continue
        base, idx = r['drop'].split('#')
        by_file[f'{BOOK}/{base}'].append({'original': f"#{idx} {r['drop'].split(' ', 1)[1]}",
                                          'corrected': '删除',
                                          'note': f"{r['note']}；保留 {r['keep']}" +
                                                  (f"（{r['diff']}）" if r['diff'] else '')})
    for rel, fixes in sorted(by_file.items()):
        rec = pg.merge(rel, dict(fixes=fixes))
        rec['note'] = ((rec.get('note') or '').rstrip() +
                       f' {args.date} 重复清理：删 {len(fixes)} 条散卷重出，逐条见 {args.out}。').strip()
        pg.write_record(rel, pg.ordered(rec))
    pg.write_index()
    print(f'进度记录 {len(by_file)} 个文件')


if __name__ == '__main__':
    main()
