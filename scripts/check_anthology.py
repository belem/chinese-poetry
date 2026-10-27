#!/usr/bin/env python3
"""选本对齐：把「选本目录（目次）」与「本库里挂了该选本 tag 的诗」逐条对起来，只报告，不改数据。

本库把选本（唐诗三百首 / 宋词三百首 / 水墨唐诗）并进了 全唐诗 / 宋词，靠 record['tags'] 标注归属。
tag 是爬取时随手打上去的，没有和底本目次比对过，于是有三类问题看不出来：

  混入   挂着 tag，但底本目次里没有（不属于这个选本）
  漏收   底本目次里有，库里没有任何记录挂着 tag
  重覆   同一首在库里有多条记录（多为 樂府 / 非樂府 两套标题各收一次，或 唐代/诗/全唐诗/error 的残卷）

判定只做一件机器能做准的事：按首句的规范形（简繁统一 + Unihan 异体归一）检索对应朝代的记录。
选本是有限的、互不相交的列表，归属判定是 one-to-one 匹配，不是分类 ——
作者朝代、风格相似度、"像不像这个选本"全是噪声源，别用。

为什么不能只比正文：宋人诗里嵌着大量唐诗，不比年代就会把《全宋诗》的记录当成《唐诗三百首》。

  python3 scripts/check_anthology.py                      # 汇总
  python3 scripts/check_anthology.py --out docs/选本对齐.tsv
  python3 scripts/check_anthology.py --only tangshi300
"""
import argparse
import collections
import csv
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import collate  # noqa: E402
import shidian as sd  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ANTH_DIR = os.path.join(ROOT, 'anthologies')
# 选本 → 该选本的诗藏在哪些目录里
ANTH_SOURCES = {
    'tangshi300': ['唐代/诗/全唐诗'],
    'songci300': ['宋代/词/宋词'],
}
# 选本的收诗只可能落在这些文件名前缀里；全唐诗目录下的 poet.song.* 是宋诗，不能算
PREFIX = {'tangshi300': 'poet.tang.', 'songci300': 'ci.song.'}
FLAT = re.compile(r'[，。：；？！、\s]')


def iter_records(dirs, skip_error=True):
    """遍历数据集里的作品记录，产出 (rel, idx, record)。"""
    for dirname in dirs:
        for rel in sorted(os.listdir(os.path.join(ROOT, dirname))):
            if not rel.endswith('.json'):
                continue
            if skip_error and dirname == '唐代/诗/全唐诗' and rel in ('README.md',):
                continue
            rel = os.path.join(dirname, rel)
            try:
                data = sd.load(rel)
            except Exception:
                continue
            if isinstance(data, dict):
                data = [data]
            for idx, rec in enumerate(data):
                if isinstance(rec, dict) and isinstance(rec.get('paragraphs'), list):
                    yield rel, idx, rec


def flat(rec):
    return FLAT.sub('', ''.join(x for x in rec['paragraphs'] if isinstance(x, str)))


def load_anthologies():
    if not os.path.isdir(ANTH_DIR):
        return {}
    out = {}
    for fn in sorted(os.listdir(ANTH_DIR)):
        if fn.endswith('.json'):
            out[fn[:-5]] = json.load(open(os.path.join(ANTH_DIR, fn), encoding='utf-8'))
    return out


def ngrams(text, ns=(4, 5, 6, 8)):
    """用于倒排索引的字片段。"""
    out = set()
    for n in ns:
        for i in range(len(text) - n + 1):
            out.add(text[i:i + n])
    return out


VARIANTS = {}


def _gb(ch):
    try:
        ch.encode('gb2312')
        return True
    except UnicodeEncodeError:
        return False


def load_variants(path):
    """Unihan 异体表（collate.norm_factory 下载的那份）反转成「字 → 同族字集合」。

    collate 的 norm 只往一个方向并（葉→叶，但 黄葉→黄叶 又是另一条边），
    这里把每个连通分量都补齐，两个方向都能收敛到同一族。
    """
    parent = {}

    def find(x):
        parent.setdefault(x, x)
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    vm = json.load(open(path, encoding='utf-8'))
    groups = collections.defaultdict(set)
    for c, r in vm.items():
        groups[r].add(c)
    for r, members in groups.items():
        members.add(r)
        first = min(members)
        for m in members:
            a, b = find(m), find(first)
            if a != b:
                parent[max(a, b)] = min(a, b)
    fam = collections.defaultdict(set)
    for c in list(parent):
        fam[find(c)].add(c)
    for members in fam.values():
        for m in members:
            VARIANTS[m] = members
    return VARIANTS


def keys_of(text):
    """同一段文字的规范形：先 t2s 统一简繁，再逐字并入异体族。"""
    t = sd.T2S.convert(FLAT.sub('', text))
    # 取族里的「常用字」作代表：GB2312 内的优先，其次罕用字最少的
    cb = ''.join(rep_of(c) for c in t)
    return list(dict.fromkeys([t, cb]))


def rep_of(ch):
    fam = VARIANTS.get(ch)
    if not fam or len(fam) == 1:
        return ch
    return min(fam, key=lambda c: (not _gb(c), ord(c)))


def match(entries, records, prefix):
    """目录条目 ↔ 库内记录。

    只看正文会把宋人抄唐诗的句子也算命中（《全宋诗》里嵌着大量唐诗），所以加两道闸：
      1. 年代：唐诗三百首只认 poet.tang.*；宋词三百首只认 ci.song.*
      2. 篇幅/唯一性：检索词取首句规范形的中间片段（开头两个字常被标题吃掉），
         命中后再回查片段是否真在该记录正文里。
    """
    items = []
    for rel, idx, rec in records:
        pre = os.path.splitext(os.path.split(rel)[1])[0]
        if prefix and not pre.startswith(prefix):
            continue
        raw = sd.T2S.convert(flat(rec))
        variants = keys_of(raw)
        items.append((rel, idx, rec, variants, set().union(*(ngrams(v) for v in variants))))
    index = collections.defaultdict(set)
    for i, it in enumerate(items):
        for g in it[4]:
            index[g].add(i)

    result = {}
    for e in entries:
        found = []
        for key in keys_of(e['first_line']):
            for n in (8, 6, 5, 4):
                probe = key[2:2 + n] if len(key) > 2 + n else key[n:]
                if not probe:
                    continue
                ids = set()
                for i in range(len(probe) - 3):
                    ids |= index.get(probe[i:i + 4], set())
                cand = [(items[i][0], items[i][1], items[i][2], items[i][3])
                        for i in sorted(ids) if any(probe in v for v in items[i][3])]
                if cand:
                    found = cand
                    break
            if found:
                break
        result[e['no']] = found
    return result


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--work', default='/tmp/sd_anthology')
    ap.add_argument('--only')
    ap.add_argument('--out')
    args = ap.parse_args()

    anths = load_anthologies()
    if not anths:
        sys.exit(f'没有找到选本目录：{ANTH_DIR}')

    os.makedirs(args.work, exist_ok=True)
    collate.norm_factory(args.work)          # 首次运行会下载 Unihan 异体表
    load_variants(os.path.join(args.work, 'variant_map.json'))
    rows = []
    todo = {k: v for k, v in anths.items() if not args.only or args.only == k}
    if not todo:
        sys.exit(f'没有这个选本目录：{args.only}')
    for name, anth in todo.items():
        records = list(iter_records(ANTH_SOURCES[name]))
        hits = match(anth['entries'], records, PREFIX.get(name, ''))
        mult = collections.defaultdict(list)
        for no, found in hits.items():
            for rel, idx, _, _ in found:
                mult[(rel, idx)].append(no)
        covered = set()
        for e in anth['entries']:
            found = hits[e['no']]
            base = dict(anth=name, no=e['no'], category=e.get('category') or '', first_line=e['first_line'])
            if not found:
                rows.append(dict(base, verdict='missing', author=e.get('author') or '',
                                 title=e.get('title') or '', where='', note='底本目次有此首，库里没有对应记录'))
                continue
            if not any(name in (f[2].get('tags') or []) for f in found):
                rel, idx, rec, _ = found[0]
                rows.append(dict(base, verdict='untagged', author=rec.get('author') or '',
                                 title=rec.get('title') or '', where=f'{rel}#{idx}',
                                 note='目录命中，但记录没挂该选本的 tag'))
            for rel, idx, rec, _ in found:
                covered.add((rel, idx))
                if len(mult[(rel, idx)]) > 1:
                    rows.append(dict(base, verdict='multi', author=rec.get('author') or '',
                                     title=rec.get('title') or '', where=f'{rel}#{idx}',
                                     note=f'同一首命中目录第 {"、".join(map(str, mult[(rel, idx)]))} 条'))

        # 混入：挂了 tag，但底本目次里找不到
        for rel, idx, rec in records:
            if name in (rec.get('tags') or []) and (rel, idx) not in covered:
                rows.append(dict(anth=name, verdict='stray', no='', category='',
                                 first_line=sd.T2S.convert(flat(rec))[:14], author=rec.get('author') or '',
                                 title=rec.get('title') or '', where=f'{rel}#{idx}',
                                 note='挂了 tag，底本目次里找不到'))

    order = {'stray': 0, 'missing': 1, 'untagged': 2, 'multi': 3}
    fields = ['anth', 'verdict', 'no', 'category', 'author', 'title', 'first_line', 'where', 'note']
    rows.sort(key=lambda r: (r['anth'], order[r['verdict']], str(r['no'])))
    counts = collections.Counter((r['anth'], r['verdict']) for r in rows)
    for k, v in sorted(counts.items()):
        print(f'{k[0]:12s} {k[1]:9s} {v}')

    if args.out:
        os.makedirs(os.path.dirname(args.out) or '.', exist_ok=True)
        with open(args.out, 'w', encoding='utf-8', newline='') as fp:
            w = csv.DictWriter(fp, fieldnames=fields, delimiter='\t', extrasaction='ignore')
            w.writeheader()
            w.writerows(rows)
        print(f'→ {args.out} ({len(rows)} rows)')


if __name__ == '__main__':
    main()
