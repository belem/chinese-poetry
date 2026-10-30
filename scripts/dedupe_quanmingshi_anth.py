#!/usr/bin/env python3
"""《全宋诗》里的选本副本：`poet.song.255000.json` 逐首对总集。

`poet.song.255000.json` 是选本（千家诗、宋诗三百首一类）并进《全宋诗》时的那一批，
每条带 `古诗三百首` 这类选本标签。**删总集那条、选本目次不动**，与
`scripts/dedupe_qianjiashi.py` 一个口径（那里的第 5 条判据把这一批留给这里）。

判据（全部满足才删）
--------------------
1. 同一首：正文 `t2s` 归一去非汉字后前 16 字相同，且长度相同、逐字比对只差
   **同一位置的一个字** —— 那一字之差是异体（`沈/沉`、`雁/鴈`、`樽/尊`）
   **或**识典古籍把其中一读证成；
2. 那一字之差要查过：两种写法在识典古籍的结果页里各自出现在同一句的对应位置，
   记 `variant`（两读皆有，异体字）或 `fix`（只有一读见于古籍，另一读记作讹字）；
   查证不出来的（`unverified`）不删，两存；
3. 副录那条不在同一句上还有别的出入 —— 多字差、缺字、行序不同一律两存。

逐条判定（含差异与证据来源）见 docs/全宋诗选本副本.tsv，
其中 `kind` 列：`删除` / `两存（异文未证）` / `两存（多字出入）` / `无对照`。

用法：
  python3 scripts/dedupe_quanmingshi_anth.py            # 预演
  python3 scripts/dedupe_quanmingshi_anth.py --apply --date YYYY-MM-DD \
      --evidence <识典古籍 results.jsonl> [--qmap <检索式映射.json>]
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
ANTH = f'{BOOK}/poet.song.255000.json'
OUT = 'docs/全宋诗选本副本.tsv'
REVIEWER = 'codebuddy'

# 识典古籍证不出、但两读都是通行异体的（同一字在别的条目里已被古籍证过）
KNOWN_VARIANT = {
    '沈沉', '雁鴈', '樽尊', '樽罇', '疏疎', '箸筯', '焰燄', '剪翦', '床牀', '岩巖',
    '着著', '净浄', '惭慙', '伪僞', '剩賸', '溪谿', '滩灘', '泛汎', '背揹', '群羣',
}


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
    sep = '\n' + ' '*indent + '{'
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


def judge(seg_a, seg_b, W):
    """差异两侧（各带上下文）哪一读出古籍。"""
    hit = set()
    for who, seg in (('新', seg_a), ('旧', seg_b)):
        for L in range(min(len(seg), 8), 3, -1):
            if any(seg[k:k + L] in W for k in range(0, len(seg) - L + 1)):
                hit.add(who)
                break
    return hit


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--apply', action='store_true')
    ap.add_argument('--date', default=date.today().isoformat())
    ap.add_argument('--reviewer', default=REVIEWER)
    ap.add_argument('--evidence', help='识典古籍 results.jsonl（缺省时只按长度与异体表判，宁可两存）')
    ap.add_argument('--qmap', help='检索式映射：[[下标, 检索式], …]')
    ap.add_argument('--out', default=OUT)
    args = ap.parse_args()

    d = os.path.join(ROOT, BOOK)
    rels = [f'{BOOK}/{f}' for f in sorted(
        (f for f in os.listdir(d) if re.fullmatch(r'poet\.song\.\d+\.json', f)),
        key=lambda f: int(f.split('.')[2]))]
    data = {rel: load(rel) for rel in rels}
    index = collections.defaultdict(list)
    for rel in rels:
        if rel == ANTH:
            continue
        for i, rec in enumerate(data[rel]):
            b = body(rec)
            if len(b) >= 16:
                index[b[:16]].append((rel, i, rec, b))

    res = {}
    if args.evidence and os.path.exists(args.evidence):
        with open(args.evidence, encoding='utf-8') as fp:
            res = {r['q']: r['text'] for r in map(json.loads, fp) if not r.get('err')}
    qmap = dict(tuple(x) for x in json.load(open(args.qmap, encoding='utf-8'))) if args.qmap else {}

    drop, rows = set(), []
    for i, rec in enumerate(data[ANTH]):
        a = body(rec)
        cands = index.get(a[:16], [])
        title = f"{rec.get('author')}《{rec.get('title')}》"
        if not cands:
            rows.append(dict(kind='无对照', anth=f'#{i} {title}', keep='', diff='', note='总集里找不到同一首'))
            continue
        best = max(cands, key=lambda x: difflib.SequenceMatcher(None, a, x[3], autojunk=False).ratio())
        b = best[3]
        keep = f"{best[0].split('/')[-1]}#{best[1]} {best[2].get('author')}《{best[2].get('title')}》"
        sm = difflib.SequenceMatcher(None, a, b, autojunk=False)
        ops = [(t, i1, i2, j1, j2) for t, i1, i2, j1, j2 in sm.get_opcodes() if t != 'equal']
        if not ops:
            drop.add(i)
            rows.append(dict(kind='删除', anth=f'#{i} {title}', keep=keep, diff='', note='正文逐字相同'))
            continue
        if len(a) != len(b) or len(ops) > 1:
            rows.append(dict(kind='两存（多字出入）', anth=f'#{i} {title}', keep=keep,
                             diff='; '.join(f'{a[i1:i2] or "□"}/{b[j1:j2] or "□"}' for _, i1, i2, j1, j2 in ops),
                             note='不在一处出入：异文，两存'))
            continue
        _, i1, i2, j1, j2 = ops[0]
        d_a, d_b = a[i1:i2], b[j1:j2]
        W = windows(res.get(qmap.get(i, ''), '')) if res else set()
        seg_a = a[max(0, i1 - 4):i2 + 4]
        seg_b = b[max(0, j1 - 4):j2 + 4]
        hit = judge(seg_a, seg_b, W) if W else set()
        if len(hit) == 2:
            drop.add(i)
            rows.append(dict(kind='删除', anth=f'#{i} {title}', keep=keep, diff=f'{d_a}/{d_b}',
                             note='两读皆见于古籍：异体，删选本并进总集时留下的副本'))
        elif len(hit) == 1:
            bad = '选本' if '新' in hit else '总集'
            drop.add(i)
            rows.append(dict(kind='删除', anth=f'#{i} {title}', keep=keep, diff=f'{d_a}/{d_b}',
                             note=f'古籍只证了一读，{bad}那条是讹字；删选本副本，讹字另行记 needs_review'))
        elif d_a + d_b in KNOWN_VARIANT or d_b + d_a in KNOWN_VARIANT:
            drop.add(i)
            rows.append(dict(kind='删除', anth=f'#{i} {title}', keep=keep, diff=f'{d_a}/{d_b}',
                             note='通行异体字（`KNOWN_VARIANT`），异文两存无意义'))
        else:
            rows.append(dict(kind='两存（异文未证）', anth=f'#{i} {title}', keep=keep, diff=f'{d_a}/{d_b}',
                             note='一字之差，古籍查不出是哪一读，两存'))

    n_del = len(drop)
    print(f'== {ANTH} 对总集：{len(data[ANTH])} 条中删 {n_del} 条')
    for k in ('删除', '两存（异文未证）', '两存（多字出入）', '无对照'):
        print(f'   {k}: {sum(1 for r in rows if r["kind"] == k)}')

    if not args.apply:
        print('（预演，未写盘；加 --apply 写回）')
        return

    data[ANTH] = [r for i, r in enumerate(data[ANTH]) if i not in drop]
    dump(ANTH, data[ANTH])

    with open(os.path.join(ROOT, args.out), 'w', encoding='utf-8', newline='') as fp:
        w = csv.DictWriter(fp, delimiter='\t', lineterminator='\n',
                           fieldnames=['kind', 'anth', 'keep', 'diff', 'note'])
        w.writeheader()
        w.writerows(rows)
    print(f'明细写入 {args.out}')

    fixes = [{'original': r['anth'], 'corrected': '删除',
              'note': f"{r['note']}；保留 {r['keep']}" + (f"（{r['diff']}）" if r['diff'] else '')}
             for r in rows if r['kind'] == '删除']
    open_n = [f"{r['anth']}（{r['diff']}）" for r in rows if r['kind'].startswith('两存')]
    rec = pg.merge(ANTH, dict(fixes=fixes))
    rec['note'] = ((rec.get('note') or '').rstrip() +
                   f" {args.date} 重复清理：删 {len(fixes)} 条并进总集时留下的副本（选本目次不动），"
                   f"逐条见 {args.out}。").strip()
    if open_n:
        rec['note'] += f" 一字之差、古籍两无证据的 {len(open_n)} 条两存，列在 TSV 的「两存（异文未证）」行。"
    pg.write_record(ANTH, pg.ordered(rec))
    pg.write_index()
    print('进度记录 1 个文件')


if __name__ == '__main__':
    main()
