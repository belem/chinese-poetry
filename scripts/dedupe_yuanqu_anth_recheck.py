#!/usr/bin/env python3
"""元曲：补录那批独立再核一遍，逐组看「补录那条是套数里的一支、还是同一支曲的另一份录文」。

`docs/元曲长短两录.md` 与 `docs/元曲短录去重.md` 两轮都是逐组看过 38 + 9 组的，剩 3 组
（黑漆弩、折桂令·西域吉诚甫、折桂令·题录鬼簿）当时未看到、后面几轮也没动，这里补上。

判据：正文 t2s 归一去标点后，补录那条**逐字嵌在**总集那条里（允许个别异文），
且题名（同样归一）相同或只差 `簿/薄` 这类形近字；两句以下不在范围（组曲的各支是另一首诗）。
判定之后的处理沿用 `dedupe_yuanqu_short.py`：删补录那条，题名记进总集那条的 `tags`。

一读为讹字、一读为古书所载的（`虑恐／虚恐`、`台／城`、`磨／靡`、`诚／成`），
删补录那条的同时，把总集那条的讹字一并订正 —— 这两件事在同一处证据上，分两次改容易改反。

用法：
  python3 scripts/dedupe_yuanqu_anth_recheck.py            # 预演
  python3 scripts/dedupe_yuanqu_anth_recheck.py --apply --date YYYY-MM-DD
"""
import argparse
import collections
import csv
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
BOOK = '元/元曲/yuanqu.json'
OUT = 'docs/元曲补录复核.tsv'
REVIEWER = 'codebuddy'

# 判例：补录那条（标题归一后）→ 说明。识典古籍证据写在这里，重跑照旧生效。
VERDICTS = {
    ('双调折桂令题录鬼薄', '双调蟾宫曲题录鬼簿', '周浩'): dict(kind='删除',
                         fix=[('万古难靡', '万古难磨')],
                         note='《錄鬼簿》所载作「鳳凰臺人物蹉跎…萬古難磨」：补录「凤凰台」「磨」皆合古书，'
                              '总集「凤凰城」「靡」是讹字；补录那条正文即总集那条，删补录'),
    ('正宫黑漆弩游金山寺并序', '正宫黑漆弩游金山寺并序', '王恽'): dict(kind='删除',
                            fix=[('蛟龙虚恐', '蛟龙虑恐')],
                            note='识典古籍六种并作「蛟龍慮恐下燃犀」，补录「虑恐」「声伎」二读皆合古书，'
                                 '总集「虚恐」是讹字；补录那条正文即总集那条，删补录'),
    ('双调折桂令西域吉诚甫', '双调折桂令咏西域吉诚甫', '钟嗣成'): dict(kind='两存', apply_to='anth',
                          fix=[('胸次天成', '胸次天诚'), ('律按衡玑', '律按玑衡')],
                          note='《類聚名賢樂府群玉》作「胸次天誠」；「玑衡」是星象（璇玑玉衡），'
                               '补录两读皆合古书。但两条各有讹（补录把「玑衡」倒成「衡玑」），正文并非一份，两存'),
}


def han(s):
    return HAN.sub('', T2S.convert(s or ''))


def body(rec):
    return han(''.join(rec.get('paragraphs') or []))


def load():
    with open(os.path.join(ROOT, BOOK), encoding='utf-8') as fp:
        return json.load(fp)


def dump(data):
    """写回：这个文件既要删记录又要改字，按 `json.dumps` 整写（同 `scripts/dedupe_tang.py`）。

    行尾空格不齐，整写会让整个文件进 diff —— 认了：改字本来就散在各条记录里，
    按行搬只会把改到的行挪错位置。
    """
    path = os.path.join(ROOT, BOOK)
    raw = open(path, encoding='utf-8').read()
    m = re.search(r'\n( +)\S', raw)
    indent = len(m.group(1)) if m else 2
    out = json.dumps(data, ensure_ascii=False, indent=indent) + ('\n' if raw.endswith('\n') else '')
    if out != raw:
        with open(path, 'w', encoding='utf-8') as fp:
            fp.write(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--apply', action='store_true')
    ap.add_argument('--date', default=date.today().isoformat())
    ap.add_argument('--reviewer', default=REVIEWER)
    ap.add_argument('--out', default=OUT)
    args = ap.parse_args()

    data = load()
    index = {}
    for i, rec in enumerate(data):
        b = body(rec)
        if len(b) >= 16:
            index.setdefault(b[:16], []).append(i)

    rows, drop, edits = [], set(), []
    # 判例按「归一后的题名」认，一组两条：补录那条（下标大）删/留，总集那条订正
    by_title = collections.defaultdict(list)
    all_idx = list(range(len(data)))
    for i, rec in enumerate(data):
        by_title[han(rec.get('title'))].append(i)
    for (t_anth, t_keep, who), v in VERDICTS.items():
        idx = by_title.get(t_anth) or []
        # 总集那条题名归一后可能与补录那条完全相同，也可能只是前缀关系（《蟾宫曲》/《折桂令》）
        pair = [j for j in all_idx if j not in idx and han(data[j].get('title')) == t_keep
                and (not idx or body(data[j])[:16] == body(data[idx[0]])[:16])] if t_keep != t_anth else []
        if not pair:
            # 总集那条题名常把曲牌并进书题（《蟾宫曲题录鬼簿》），按作者 + 曲牌前缀认
            # 题名归一后可能只差一个间隔号（`・` / `·` 之外还有书题断法），按作者 + 曲牌认
            pair = [j for j in all_idx if j not in idx and data[j].get('author') == who
                    and han(data[j].get('title')).startswith(t_keep.split('题')[0])]
            if len(pair) > 1 and idx:
                same = [j for j in pair if body(data[j])[:16] == body(data[idx[0]])[:16]]
                pair = same or pair
        pair = pair[:1]
        # 两条题名归一后完全相同的，先出现的是总集那条
        if len(idx) == 2 and t_keep == t_anth:
            pair, idx = idx[:1], idx[1:]
        if len(idx) != 1 or len(pair) != 1:
            rows.append(dict(kind='无对照', anth=t_anth, keep=t_keep,
                             note=f'判例该有两条，实有 {len(idx)} / {len(pair)} 条，先核'))
            continue
        anth, keep = idx[0], pair[0]
        k = data[keep]
        rows.append(dict(kind=v['kind'],
                         anth=f'#{anth} {data[anth].get("author")}《{data[anth].get("title")}》',
                         keep=f'#{keep} {k.get("author")}《{k.get("title")}》', note=v['note']))
        if v['kind'] == '删除':
            drop.add(anth)
        for old, new in v.get('fix') or []:
            edits.append((anth if v.get('apply_to') == 'anth' else keep, old, new))

    for keep, old, new in edits:
        rec = data[keep]
        hit = False
        for n, para in enumerate(rec.get('paragraphs') or []):
            if old in para:
                rec['paragraphs'][n] = para.replace(old, new)
                hit = True
        if not hit:
            raise SystemExit(f'#{keep} 里找不到「{old}」，判例与数据对不上，先核')

    print(f'== {BOOK}：删 {len(drop)} 条，订正 {len(edits)} 处')
    for r in rows:
        print(f"   [{r['kind']}] {r['anth']} ← {r['keep']}")

    if not args.apply:
        print('（预演，未写盘；加 --apply 写回）')
        return

    data = [r for i, r in enumerate(data) if i not in drop]
    dump(data)

    with open(os.path.join(ROOT, args.out), 'w', encoding='utf-8', newline='') as fp:
        w = csv.DictWriter(fp, delimiter='\t', lineterminator='\n',
                           fieldnames=['kind', 'anth', 'keep', 'note'])
        w.writeheader()
        w.writerows(rows)
    print(f'明细写入 {args.out}')

    fixes = [{'original': r['anth'], 'corrected': '删除', 'note': f"{r['note']}；保留 {r['keep']}"}
             for r in rows if r['kind'] == '删除']
    fixes += [{'original': old, 'corrected': new,
               'note': f'补录复核时订正：{old}→{new}，见 {args.out}'} for _, old, new in edits]
    rec = pg.merge(BOOK, dict(fixes=fixes))
    rec['note'] = ((rec.get('note') or '').rstrip() +
                   f' {args.date} 重复清理：补录那批最后 3 组独立再核，删 2 条、两存 1 组，'
                   f'另按同一批证据订正 4 处讹字，逐条见 {args.out}。').strip()
    pg.write_record(BOOK, pg.ordered(rec))
    pg.write_index()
    print('进度记录 1 个文件')


if __name__ == '__main__':
    main()
