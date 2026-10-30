#!/usr/bin/env python3
"""《千家诗》并进总集时留下的副本：只删「一个字的信息都不带」的那些。

`宋/诗/千家诗/qianjiashi.json` 是选本（五绝/五律/七绝/七律，一条一首，带篇题），
2026-10 按「选本不占目录、占标签」并进总集时，**选本那本书留着、总集里的副本没清**：
同一首在总集里还有一条，而 `qianjiashi.json` 从头到尾没有一个 `tags` ——
选本并进总集这一步没做完。

这一批删的是**总集里那条副本**，与 `docs/汇编与诗去重.md` 相反（那里删补录、留选本）：
`汇编/` 的书是带底本的分卷本，`qianjiashi.json` 只是选本目次，留它做「这本书收了哪些」。

判据（全部满足才删）
--------------------
1. 正文逐字相同（`t2s` 归一、去非汉字后整篇相等）—— 异文一律两存，不删；
2. 组里有 `qianjiashi.json` 那一条，且它带 `chapter`（篇题）；
3. 总集里这一首**只有一条**与选本逐字相同 —— 两条都是总集的（《登鸛雀樓》朱斌／王之渙、
   《答人》太上隱者／太上隱君），删哪条都是替古人定案，一条不动；
4. 那条没挂 `千家诗` tag（挂了的说明并进去了）；
5. 那条最多带 3 个标签 —— 「古诗三百首」「小学古诗」「三年级下册」这类题材与课本标签
   在选本那份上没有，删了就是丢信息，留着。

只有 43 条总集记录是「一个标签都没有」的纯副本，这一批删的就是它们加几条同性质的。
递进数据见 `docs/千家诗去重.tsv` 的 `kind` 列（`删除` / `保留` / `两存`）。

顺带记一件事：`宋/诗/全宋诗/poet.song.255000.json` 整个文件是《千家诗》《宋词三百首》那类
选本并进来的 300 余首，标着「古诗三百首」；本批按第 5 条一条不删，留给选本对齐那条线。

用法：
  python3 scripts/dedupe_qianjiashi.py            # 预演
  python3 scripts/dedupe_qianjiashi.py --apply --date YYYY-MM-DD
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
ANTH = '宋/诗/千家诗/qianjiashi.json'
BOOKS = {'唐/诗/全唐诗': r'poet\.tang\.\d+\.json', '宋/诗/全宋诗': r'poet\.song\.\d+\.json'}
OUT = 'docs/千家诗去重.tsv'
PREFIX = 16
REVIEWER = 'codebuddy'
TAG = '千家诗'
# 选本标签：本库把它们并进总集时打在记录上。这类标签选本那份上没有，但不是「信息」——
# 删副本之后由 `docs/选本对齐.md` 那条线补回总集那条（选本 tag 本来就该在总集那一条上）。
# 其余标签是题材（写景/思乡）与课本（三年级下册/小学古诗），删了就真丢了，留着。
SELECTION = {'千家诗', '唐诗三百首', '水墨唐诗', '宋词三百首', '古诗三百首', '课文', '课本'}
MAX_TAGS = 3


def han(s):
    return HAN.sub('', T2S.convert(s or ''))


def body(rec):
    p = rec.get('paragraphs')
    if isinstance(p, list) and p and all(isinstance(x, str) for x in p):
        return han(''.join(p))
    return ''


def walk(node, rel, path=(), chapter=None):
    """选本是 {type, content:[{chapter, author, paragraphs}]} 的嵌套结构，逐首取出来。"""
    if isinstance(node, dict):
        p = node.get('paragraphs')
        if isinstance(p, list) and p and all(isinstance(x, str) for x in p):
            yield rel, path, node, chapter or node.get('chapter')
            return
        for k, v in node.items():
            if isinstance(v, (list, dict)):
                yield from walk(v, rel, path + (k,), node.get('chapter') or chapter)
    elif isinstance(node, list):
        for i, v in enumerate(node):
            yield from walk(v, rel, path + (i,), chapter)


def load_books():
    out = {}
    for d, pat in BOOKS.items():
        for f in sorted(os.listdir(os.path.join(ROOT, d))):
            if re.fullmatch(pat, f):
                rel = f'{d}/{f}'
                with open(os.path.join(ROOT, rel), encoding='utf-8') as fp:
                    out[rel] = json.load(fp)
    return out


def dump(rel, data):
    """写回，且只让「删掉的记录」进 diff（同 `scripts/dedupe_huibian_poet.py`）。

    按记录块对回来；对不上（末条正好是被删的那条）时退回整写 ——
    `dedupe_songci_full.dump` 在这种情形下会把收尾的 `]` 一起丢掉，别用。
    """
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
            i += 1                        # 老的这条在新输出里没有 = 删掉的
    res.extend(old[i:])
    text = sep.join(res)
    if not valid(text):
        text = out                       # 末条被删时对不齐，整写
    if text != raw:
        with open(path, 'w', encoding='utf-8') as fp:
            fp.write(text)


def valid(text):
    try:
        json.loads(text)
        return True
    except ValueError:
        return False


def tagged(rec):
    return any(TAG in str(t) for t in (rec.get('tags') or []))


def desc(x):
    if x[0] == 'anth':
        return f"{x[1]}#{x[3].get('author') or ''}《{x[5] or x[3].get('chapter') or ''}》"
    return f"{x[1]}#{x[2]} {x[3].get('author') or ''}《{x[3].get('title') or ''}》"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--apply', action='store_true')
    ap.add_argument('--date', default=date.today().isoformat())
    ap.add_argument('--reviewer', default=REVIEWER)
    ap.add_argument('--out', default=OUT)
    args = ap.parse_args()

    with open(os.path.join(ROOT, ANTH), encoding='utf-8') as fp:
        anth = list(walk(json.load(fp), ANTH))
    data = load_books()

    groups = collections.defaultdict(list)
    for rel, recs in data.items():
        for i, rec in enumerate(recs):
            b = body(rec)
            if len(b) >= PREFIX:
                groups[b[:PREFIX]].append(('book', rel, i, rec, b))
    n_anth = 0
    for rel, path, rec, chapter in anth:
        b = body(rec)
        if len(b) < PREFIX:
            continue
        n_anth += 1
        groups[b[:PREFIX]].append(('anth', rel, path, rec, b, chapter))

    rows, drop = [], collections.defaultdict(set)
    stat = collections.Counter()
    for key, items in groups.items():
        books = list({x[3].get('id'): x for x in items if x[0] == 'book'}.values())
        # 选本同一首在一次遍历里会出现两次（嵌套结构），按正文去重
        anths = list({(x[4], x[5]): x for x in items if x[0] == 'anth'}.values())
        if not books or not anths:
            continue
        pairs = [(a, b) for a in anths for b in books if a[4] == b[4]]
        if not pairs:
            stat['选本与总集正文有出入（两存）'] += len(books)
            for x in books:
                rows.append(dict(kind='两存', key=key, keep=desc(anths[0]), drop=desc(x),
                                 note=f'正文有出入（选本 {len(anths[0][4])} 字 / 总集 {len(x[4])} 字）'))
            continue
        a = pairs[0][0]
        if not a[5]:
            stat['选本无篇题（判不了）'] += 1
            continue
        same = [x for x in books if x[4] == a[4]]
        if len(same) != 1:
            stat['总集内多条（归属异说，不动）'] += len(same)
            for x in same:
                rows.append(dict(kind='两存', key=key, keep=desc(a), drop=desc(x),
                                 note='同一首在总集里有多条（之一作某人），删哪条都是替古人定案'))
            continue
        x = same[0]
        tags = list(x[3].get('tags') or [])
        if tagged(x[3]):
            stat['总集那条已挂千家诗 tag（并进去了）'] += 1
            continue
        kept = [t for t in tags if t not in SELECTION]
        if len(kept) > MAX_TAGS:
            stat['总集那条带题材/课本标签（不动）'] += 1
            rows.append(dict(kind='保留', key=key, keep=desc(a), drop=desc(x),
                             note='正文逐字相同，但总集那条带着题材／课本标签：' + '、'.join(kept)))
            continue
        drop[x[1]].add(x[3].get('id'))
        stat['删副本'] += 1
        rows.append(dict(kind='删除', key=key, keep=desc(a), drop=desc(x),
                         note=f'与选本《{a[5]}》逐字相同，删总集里没挂 tag 的副本'))

    print(f'== 《千家诗》{n_anth} 首，与总集互见：')
    for k, v in sorted(stat.items(), key=lambda kv: -kv[1]):
        print(f'   {k:<28} {v}')
    print(f'   拟删 {sum(len(v) for v in drop.values())} 条，涉及 {len(drop)} 个文件')

    with open(os.path.join(ROOT, args.out), 'w', encoding='utf-8', newline='') as fp:
        w = csv.DictWriter(fp, delimiter='\t', lineterminator='\n',
                           fieldnames=['kind', 'key', 'keep', 'drop', 'note'])
        w.writeheader()
        w.writerows(rows)
    print(f'明细写入 {args.out}')

    if not args.apply:
        for r in rows:
            if r['kind'] == '删除':
                print(f"   删 {r['drop'][:70]:<70} ← 留 {r['keep'][:50]}")
        print('（预演，未改动任何文件；加 --apply 落盘）')
        return 0

    for rel, ids in drop.items():
        data[rel] = [r for r in data[rel] if r.get('id') not in ids]
        dump(rel, data[rel])

    by_file = collections.defaultdict(list)
    for r in rows:
        if r['kind'] == '删除':
            by_file[r['drop'].split('#')[0]].append(dict(
                original=r['drop'], corrected='删除',
                note=f"[qianjiashi] {r['note']}；保留 {r['keep']}，见 {args.out}"))
    for rel, fs in by_file.items():
        rec = pg.merge(rel, dict(fixes=fs))
        rec['note'] = ((rec.get('note') or '').rstrip() +
                       f' {args.date} 重复清理：删 {len(fs)} 条与《千家诗》逐字相同的副本，'
                       f'逐条见 {args.out}。').strip()
        pg.write_record(rel, pg.ordered(rec))
    pg.write_index()
    print(f'进度记录 {len(by_file)} 个文件')
    return 0


if __name__ == '__main__':
    sys.exit(main())
