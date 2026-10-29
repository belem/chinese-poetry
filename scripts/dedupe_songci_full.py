#!/usr/bin/env python3
"""宋词全同重出：正文逐字相同、且是同一件作品的两条记录，删信息少的那条。

`scripts/dedupe_songci_attr.py` 只按「前 16 字相同」分组，组里正文对不齐的一律两存 ——
那是异文，对的。这里处理它管不到的另一种：**正文整篇一字不差**，判据比它更严：

  1. 正文 t2s 归一、去非汉字之后整篇相同（不是只比前 16 字）；
  2. 两条是同一件作品 —— 同一个人（署名一字不差；或经 ALIAS 归并为同一人）、
     同一词牌 / 题名（一条 `rhythmic` 一条 `title` 也算，题名本就互补）；
  3. 只留一条，删信息少的：有 `id`、有题名、有 `tags` 的优先，同分留靠前的一条。

作者不同的一律不动：那是归属异说（李煜／邓肃《长相思》、李清照／魏夫人《临江仙》），
正文全同也两存，交给 `docs/宋词归属异说.md` 那套办法互挂 `tags`。

逐条判定见 docs/宋词全同重出.tsv。

用法：
  python3 scripts/dedupe_songci_full.py                      # 预演
  python3 scripts/dedupe_songci_full.py --apply --date YYYY-MM-DD
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
SONGCI = '宋/宋词'
OUT = 'docs/宋词全同重出.tsv'
REVIEWER = 'codebuddy'

# 同一人的两种署名，只收宋词里出现过的（与 dedupe_songci_attr.ALIAS 同源，逐个核过）
ALIAS = {
    '扬无咎': '杨无咎', '张元幹': '张元干', '曹邍': '曹原', '黄昇': '黄升',
    '毛幵': '毛并', '朱㫹孙': '朱孙', '张': '张鎡', '张仲殊': '仲殊',
}


def han(s):
    return HAN.sub('', T2S.convert(s or ''))


def person(a):
    a = T2S.convert((a or '').strip())
    return ALIAS.get(a, a)


def body(rec):
    return han(''.join(rec.get('paragraphs') or []))


def tunes(rec):
    """词牌的集合，去标点后比较。

    只取 `rhythmic`，不取 `title`：`title` 是这首词的小序（「其一·和人」之类），同一词牌
    下的两首各有小序，比它会把「同词牌的两首」误当成同一首。缺 `rhythmic` 才退回 `title`。
    `凤栖梧・蝶恋花` 这种一个词牌两个名的，按 `・`／`·` 切开算两个名字。
    """
    t = T2S.convert(str(rec.get('rhythmic') or rec.get('title') or ''))
    return {re.sub(r'[^0-9A-Za-z\u4e00-\u9fff]', '', x)
            for x in re.split(r'[・·/]', t)} - {''}


def tune(rec):
    """显示用的词牌：集合里最靠前的一个名字。"""
    t = tunes(rec)
    return min(t) if t else ''


def dump(rel, data):
    """写回，且只让「真正删掉的记录」进 diff。

    这批文件的排版是 `json.dump(indent=2)` 加上不齐的行尾空格，**同一个内容在不同位置
    常常是两种写法**（`"id": "kbf3i0", ` 后面有时带空格、有时不带），按内容或按行号去
    「搬空格」都不稳（`dedupe_duplicates.dump` 按行号搬、`dedupe_songci_attr.render`
    按内容查邻居，各会翻新一部分行）。

    这里按**记录**切：原文按「`\n` + 缩进 + `{`」切成每条记录一段，重新序列化后逐条
    对回来。记录只是删、不改，所以两端各有一次单调对齐（差别只在行尾空格）：

      旧的 i 与新的 j 从记录头 LCP 起逐行比，一边走到底 —— 只在空格不同（`lstrip(' ')`
      相同）就两边都走，内容真不同就旧的那边停下、新的一边往前走（这条老的被删了）

    对得上的段整段照抄原文（行尾空格随原文），删掉的整段不进输出。
    """
    path = os.path.join(ROOT, rel)
    raw = open(path, encoding='utf-8').read()
    m = re.search(r'\n( +)\S', raw)
    indent = len(m.group(1)) if m else 2
    out = json.dumps(data, ensure_ascii=False, indent=indent) + ('\n' if raw.endswith('\n') else '')
    sep = '\n' + ' ' * indent + '{'
    head, *old = raw.split(sep)
    _, *new = out.split(sep)
    if len(new) == len(old):
        text = raw                            # 没删条（重跑），原文一字不动
    else:
        def same(x, y):
            a, b = x.split('\n'), y.split('\n')
            return len(a) == len(b) and all(p.rstrip(' ') == q.rstrip(' ') for p, q in zip(a, b))

        res, i, j = [head], 0, 0
        while j < len(new) and i < len(old):
            if same(old[i], new[j]):
                res.append(old[i])
                i, j = i + 1, j + 1
            else:
                i += 1                        # 老的这条在新输出里没有 = 删掉的
        res.extend(old[i:])                   # 末尾没动过的几条照抄（收尾的 `]` 在最后一条里）
        text = sep.join(res)
    if text != raw:
        with open(path, 'w', encoding='utf-8') as fp:
            fp.write(text)


def score(rec):
    """信息量，按次位比：有题名 > 有 tags > 分句更细（正文的句数）。

    先看题名，是因为题名是这首词唯一的信息增量（周邦彦《花心动》旧批把「双调」这个
    词牌说明写进 tags、新批写进 title）；句数这一项看的是正文质量 —— 新批常常整首一行、
    丢了分句（柳永《雨霖铃》留的是 102 字带分句的那条，不是整首一行的）。
    """
    return (1 if rec.get('title') else 0, len(rec.get('tags') or []),
            len(rec.get('paragraphs') or []))


def files():
    return sorted(f'{SONGCI}/{f}' for f in os.listdir(os.path.join(ROOT, SONGCI))
                  if re.fullmatch(r'ci\.song\..*\.json', f))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--apply', action='store_true')
    ap.add_argument('--date', default=date.today().isoformat())
    ap.add_argument('--reviewer', default=REVIEWER)
    ap.add_argument('--out', default=OUT)
    args = ap.parse_args()

    data = {}
    for rel in files():
        with open(os.path.join(ROOT, rel), encoding='utf-8') as fp:
            data[rel] = json.load(fp)

    groups = collections.defaultdict(list)
    for rel, recs in data.items():
        for i, rec in enumerate(recs):
            groups[body(rec)].append((rel, i))
    groups = {b: v for b, v in groups.items() if len(v) > 1 and len(b) >= 4}

    drop = collections.defaultdict(set)
    rows = []
    for b, keys in sorted(groups.items(), key=lambda kv: kv[1][0]):
        recs = [(k, data[k[0]][k[1]]) for k in keys]
        same_tune = all(tunes(r) & tunes(recs[0][1]) for _, r in recs)
        same_person = len({person(r.get('author')) for _, r in recs}) == 1
        authors = [r.get('author') or '' for _, r in recs]
        if not (same_tune and same_person):
            if not same_person:
                why = f'作者不同（{"／".join(dict.fromkeys(authors))}）：归属异说，两条都留'
            else:
                why = (f'词牌不同（{"／".join(dict.fromkeys(tune(r) for _, r in recs))}）：'
                       f'同一人同正文的异名，两存待核')
            for k, r in recs:
                rows.append(dict(kind='两存', path=k[0], author=r.get('author') or '',
                                 title=r.get('title') or r.get('rhythmic') or '',
                                 keep=f'{keys[0][0]}#{keys[0][1]}', note=why))
            continue
        keep_key, keep = max(recs, key=lambda kr: (score(kr[1]), -keys.index(kr[0])))
        # 同分时 max 取靠前的一条（keys 按文件、下标排），结果与运行次序无关
        for k, r in recs:
            if k == keep_key:
                continue
            drop[k[0]].add(k[1])
            rows.append(dict(kind='删除', path=k[0], author=r.get('author') or '',
                             title=r.get('title') or r.get('rhythmic') or '',
                             keep=f'{keep_key[0]}#{keep_key[1]}',
                             note=f'正文逐字相同、同一人同一词牌，删信息少的一条（留者题名 '
                                  f'《{keep.get("title") or keep.get("rhythmic") or "无"}》）'))

    n_del = sum(r['kind'] == '删除' for r in rows)
    print(f'== 宋词全同重出：{len(groups)} 组正文逐字相同的记录')
    print(f'   删除 {n_del} 条，两存 {len(rows) - n_del} 条')
    for r in rows:
        if r['kind'] == '删除':
            print(f"   [{r['kind']}] {r['path']} {r['author']}《{r['title'][:20]}》 ← 留 {r['keep']}")

    with open(os.path.join(ROOT, args.out), 'w', encoding='utf-8', newline='') as fp:
        w = csv.DictWriter(fp, delimiter='\t', lineterminator='\n',
                           fieldnames=['kind', 'path', 'author', 'title', 'keep', 'note'])
        w.writeheader()
        w.writerows(rows)
    print(f'明细写入 {args.out}')

    if not args.apply:
        print('（预演，未改动任何文件；加 --apply 落盘）')
        return 0

    for rel, idxs in drop.items():
        data[rel] = [r for i, r in enumerate(data[rel]) if i not in idxs]
        dump(rel, data[rel])

    fixes_by_file = collections.defaultdict(list)
    for r in rows:
        if r['kind'] == '删除':
            fixes_by_file[r['path']].append(dict(
                original=f"{r['author']}《{r['title'][:24]}》", corrected='删除',
                note=f"正文与 {r['keep']} 逐字相同（同一人同一词牌），删重复的那条"))
    for rel, fixes in fixes_by_file.items():
        # 只记删了哪几条，不动 date / reviewer / status：那是逐字对勘的进度，
        # 删重不是对勘，改它会让 `fix_progress.json` 把这一文件当成今天刚审过
        rec = pg.merge(rel, dict(fixes=fixes))
        rec['note'] = ((rec.get('note') or '').rstrip() +
                       f' {args.date} 重复清理：删 {len(fixes)} 条正文逐字相同的重出记录，'
                       f'逐条见 {args.out}。').strip()
        pg.write_record(rel, pg.ordered(rec))
    pg.write_index()
    print(f'进度记录 {len(fixes_by_file)} 个文件')
    return 0


if __name__ == '__main__':
    sys.exit(main())
