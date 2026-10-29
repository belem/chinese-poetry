#!/usr/bin/env python3
"""元曲「长的是一条套数、短的是其中一支」的残余：删短的那条，题名记进长条的 `tags`。

`scripts/dedupe_yuanqu_pairs.py` 那一批收的是「短录逐句都能在长录里按序对上」（`clause_coverage ≥ 0.5`），
收完还剩几组「短的一支，与长条里的某一段是一字之差的异文，整句却对不上」：

```
元/元曲/yuanqu.json#9941   徐再思《双调・卖花声》           144 字  三支合成一条  ← 留
元/元曲/yuanqu.json#11228  徐再思《双调·卖花声》            72 字   只录其中一支  ← 删
```

`越调・天净沙闲题`（112 / 56 字）、`中吕・醉高歌感怀`（100 / 50 字）、`南吕・四块玉恬退`（122 / 93 字）
也都是这个形状：长条是组曲 / 套数，短条是补录把其中一支单独抄了一遍。同一支曲两份正文，
删短的那条，**短条的题名记进长条的 `tags`**，免得「三百首选了这一支」这层信息跟着丢掉。

## 判据（都要）

1. 正文 `t2s` 归一、去标点后前 16 字相同（`check_tree.py` 的候选口径）；
2. 作者同一人；
3. 题名是同一支曲（`dedupe_duplicates.same_title`，另允许书题只差「并序／（并序）」）；
4. 长的 / 短的 ≥ 1.4 倍——短条只是其中一支，不是另一支曲；
5. **短条整条按序嵌在长条里**（`dedupe_yuanqu_pairs.subset_span`），且**逐字相同的字数 ≥ 70%**；
6. **短条与长条里那一段的出入都落在句尾**，每处不超过 6 字——这是「异文」与「改本」的分界。

#### 为什么用逐字相同率，不用 `clause_coverage`

成对的短录（`双调·卖花声` 72／144 字）与 `subset_span` 认下来却**不是副本**的几条，靠「句子」分不开：

| 情形 | 逐字相同率 | 句级 |
| --- | --- | --- |
| 短录是长条里的一两支（`卖花声`、`四块玉恬退`） | 0.80 / 0.95 | 断句不同，对齐靠「头 8 字」，`clause_coverage` 掉到 0 |
| 短录是**另一支曲**（`天净沙闲题` 56／112、`殿前欢` 91／270） | 0.63 / 0.69 | 同上 |
| 《荆钗记·一封书》王十朋寄家书 vs 孙汝权改休书 | 0.66 | 两支都是整段戏文，逐句 0.0 |

`clause_coverage` 两栏都掉到 0，判不出来。逐字相同率能分开：0.80 / 0.95 对 0.63 / 0.66 / 0.69。
再从两个方向各看一眼就稳了 —— 短录的每一句都能在长条里找到（`subset_span`，短录不是删了中间一段），
长的又是短的两三倍（短录只录了一两支）。这两条一卡，`天净沙闲题` 与《一封书》被挡在门外：
它们各自只对上长条里的**一支**，其余的对不上。

用法：
  python3 scripts/dedupe_yuanqu_short.py            # 预演：逐组打印
  python3 scripts/dedupe_yuanqu_short.py --apply --date YYYY-MM-DD --reviewer <名字>
"""
import argparse
import csv
import difflib
import json
import os
import re
import sys
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dedupe_duplicates as dd  # noqa: E402
import dedupe_yuanqu_pairs as yp  # noqa: E402
import progress as pg  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
YUANQU = '元/元曲/yuanqu.json'
OUT = 'docs/元曲短录去重.tsv'
MIN_RATIO = 1.4
MIN_SAME = 0.70
JUNK = '并序（）()'


def dump_records(rel, before, after):
    """写回：原文逐行复用，只让「删掉的记录」进 diff（同 scripts/dedupe_the… 各脚本的 dump）。

    按行对齐而不是按 `\n  {` 切块：`paragraphs` 里偶尔有原文自带的换行，切块会切歪。
    `before` 与 `after` 逐行对齐时按「窗口重同步」走，最多回看 50 行 —— 一条记录删掉就是
    十几行缺席，普通的单行对齐会一路错位下去。写完核一遍：落盘的内容必须与 `after` 逐条相等。
    """
    path = os.path.join(ROOT, rel)
    raw = open(path, encoding='utf-8').read()
    m = re.search(r'\n( +)\S', raw)
    indent = len(m.group(1)) if m else 2
    out = json.dumps(after, ensure_ascii=False, indent=indent) + ('\n' if raw.endswith('\n') else '')
    old = raw.split('\n')
    new = out.split('\n')
    res, i, j = [], 0, 0
    while j < len(new):
        if i < len(old) and old[i].rstrip() == new[j].rstrip():
            res.append(old[i])
            i, j = i + 1, j + 1
            continue
        for k in range(i, min(i + 50, len(old))):
            if old[k].rstrip() == new[j].rstrip():
                i = k
                break
        else:
            res.append(new[j])
            j += 1
    text = '\n'.join(res)
    if json.loads(text) != after:
        raise SystemExit('写回的内容与预期不符，已中止')
    if text != raw:
        with open(path, 'w', encoding='utf-8') as fp:
            fp.write(text)


def title_key(rec):
    return ''.join(c for c in dd.title(rec) if c not in JUNK)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--apply', action='store_true')
    ap.add_argument('--date', default=date.today().isoformat())
    ap.add_argument('--reviewer', default='codebuddy')
    ap.add_argument('--out', default=OUT)
    args = ap.parse_args()

    data = json.load(open(os.path.join(ROOT, YUANQU), encoding='utf-8'))
    bodies = [yp.body(r) for r in data]
    index = {}
    for i, b in enumerate(bodies):
        if len(b) >= 16:
            index.setdefault(b[:16], []).append(i)

    drop, rows = set(), []
    for i, b in enumerate(bodies):
        if len(b) < 16:
            continue
        for j in index.get(b[:16], []):
            if j <= i or i in drop or j in drop:
                continue
            short, long_ = (i, j) if len(bodies[i]) < len(bodies[j]) else (j, i)
            sb, lb = bodies[short], bodies[long_]
            if yp.author(data[short]) != yp.author(data[long_]):
                continue
            if len(lb) < MIN_RATIO * len(sb):
                continue
            same = dd.same_title(data[short], data[long_]) or title_key(data[short]) == title_key(data[long_])
            if not same:
                continue
            if not yp.subset_span(lb, sb):
                continue
            same_chars = difflib.SequenceMatcher(None, sb, lb, autojunk=False).ratio() * len(lb) / len(sb)
            if same_chars < MIN_SAME:
                print(f"   略过 #{short} {dd.title(data[short])[:20]}："
                      f"与 #{long_} 逐字相同率 {same_chars:.2f}（另一支曲／改本，两存）")
                continue
            drop.add(short)
            rows.append(dict(keep=long_, drop=short, short=len(sb), long=len(lb)))

    print(f'== 元曲短录：{len(rows)} 组')
    for r in rows:
        print(f"   删 #{r['drop']} {dd.title(data[r['drop']])[:22]}（{r['short']} 字）"
              f" ← 留 #{r['keep']} {dd.title(data[r['keep']])[:22]}（{r['long']} 字）")

    if not args.apply:
        print('（预演，未改动任何文件；加 --apply 落盘）')
        return 0

    keep_tags = {}
    for r in rows:
        keep_tags.setdefault(r['keep'], []).append(dd.title(data[r['drop']]))
    out = []
    for i, rec in enumerate(data):
        if i in drop:
            continue
        if i in keep_tags:
            rec = dict(rec)
            tags = list(rec.get('tags') or [])
            for t in keep_tags[i]:
                if t not in tags:
                    tags.append(t)
            if tags:
                rec['tags'] = tags
        out.append(rec)
    dump_records(YUANQU, data, out)

    with open(os.path.join(ROOT, args.out), 'w', encoding='utf-8', newline='') as fp:
        w = csv.writer(fp, delimiter='\t', lineterminator='\n')
        w.writerow(['保留', '删除', '字数（删／留）', '处理'])
        for r in rows:
            w.writerow([f"#{r['keep']} {dd.title(data[r['keep']])}",
                        f"#{r['drop']} {dd.title(data[r['drop']])}",
                        f"{r['short']}／{r['long']}",
                        '删短录（长条是组曲，短条只录其中一支），题名记进长条的 tags'])
    print(f'明细写入 {args.out}')

    rec = pg.merge(YUANQU, dict(fixes=[dict(
        original=f"#{r['drop']} {dd.title(data[r['drop']])}", corrected='删除',
        note=f"与 #{r['keep']}《{dd.title(data[r['keep']])}》里的一支是同一支曲（{r['short']} 字 vs {r['long']} 字），"
             f"删短录、题名记进长条 tags；见 {args.out}") for r in rows]))
    rec['note'] = ((rec.get('note') or '').rstrip() +
                   f" {args.date} 删 {len(rows)} 条「长套数里的一支另立一条」的短录。").strip()
    pg.write_record(YUANQU, pg.ordered(rec))
    pg.write_index()
    print('进度记录 1 个文件')
    return 0


if __name__ == '__main__':
    sys.exit(main())
