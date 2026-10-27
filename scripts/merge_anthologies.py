#!/usr/bin/env python3
"""把唐诗选本并入 唐/诗/全唐诗/poet.tang.*，去掉 chinese-poetry-api 入库时的重复。

  python3 scripts/merge_anthologies.py            # 预演：只打印匹配报告
  python3 scripts/merge_anthologies.py --apply    # 写回数据，并生成 docs/唐诗去重.tsv

处理方式：
  唐/诗/全唐诗/唐诗三百首.json   每首对上 poet.tang 记录后，把 tags 合并过去，删除整个文件。
                           （此文件是从 poet.tang 抽出的副本，个别作者还归错了。）
  水墨唐诗                 对上的记录加 tag「水墨唐诗」并带上 prologue（赏析），从水墨唐诗中删去；
                           对不上的（全唐诗未收的如杜牧《清明》、节选改写等）留在原文件。
  花间集 / 南唐            以选本为准（有词牌结构）：poet.tang 中同一作者的同一首词删除。
                           作者不同的视为归属异说，两边都保留（与 API 去重规则一致）。

判定同一首：正文（t2s、去标点）相似度 ≥ 0.8，或选本句子全部见于该记录（节选）。
相似度不足但确属同一首的、或字面相近但不是同一首的，写在 FORCE / SKIP 里，附理由。
"""
import argparse
import collections
import difflib
import glob
import json
import os
import re

from opencc import OpenCC

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
cc = OpenCC('t2s')

# 同一人的不同署名（t2s 之后比较）
ALIAS = {'后主煜': '李煜', '南唐嗣主李璟': '李璟', '嗣主璟': '李璟', '张佖': '张泌', '韩竑': '韩翃', '朱庆馀': '朱庆余'}

# (选本文件, 选本标题) -> poet.tang 标题：相似度不足但核对过是同一首（异文较多）
FORCE = {
}
# (选本文件, 选本标题)：字面相近但不该合并
SKIP = set()


def norm(s):
    return re.sub(r'[^㐀-鿿\U00020000-\U0002ffff]', '', cc.convert(s or ''))


def author_key(a):
    a = re.sub(r'\s*[一二三四五六七八九十]+首$', '', cc.convert((a or '').strip()))
    return ALIAS.get(a, a)


def body(p):
    return norm(''.join(p.get('paragraphs') or []))


def sents(p):
    parts = re.split(r'[，。？！；、,.?!;：:]', ''.join(p.get('paragraphs') or []))
    return [s for s in map(norm, parts) if len(s) >= 4]


def load(rel):
    return json.load(open(os.path.join(ROOT, rel), encoding='utf-8'))


def save(rel, data):
    """按原文件的缩进与结尾换行写回，避免整文件 diff。"""
    path = os.path.join(ROOT, rel)
    raw = open(path, encoding='utf-8').read()
    indent = len(re.match(r'\[\n( *)', raw).group(1)) if raw.startswith('[\n') else 2
    with open(path, 'w', encoding='utf-8') as fp:
        fp.write(json.dumps(data, ensure_ascii=False, indent=indent) + ('\n' if raw.endswith('\n') else ''))


class Tang:
    def __init__(self):
        self.files = sorted(glob.glob(os.path.join(ROOT, '唐/诗/全唐诗/poet.tang.*.json')),
                            key=lambda f: int(f.split('.')[-2]))
        self.files = [os.path.relpath(f, ROOT) for f in self.files]
        self.data = {f: load(f) for f in self.files}
        self.recs = [(f, i, p) for f in self.files for i, p in enumerate(self.data[f])]
        self.index = collections.defaultdict(set)
        for k, (_, _, p) in enumerate(self.recs):
            for s in sents(p):
                self.index[s].add(k)

    def matches(self, p):
        """全部够格的候选 (k, ratio, same_author, how)，同作者优先、相似度高者在前。"""
        ss = set(sents(p))
        hits = collections.Counter(k for s in ss for k in self.index.get(s, ()))
        b, a = body(p), author_key(p.get('author'))
        out = []
        for k, n in hits.most_common(20):
            q = self.recs[k][2]
            ratio = difflib.SequenceMatcher(None, b, body(q), autojunk=False).ratio()
            same = author_key(q.get('author')) == a
            how = 'ratio' if ratio >= 0.8 else 'excerpt' if same and n == len(ss) >= 2 else None
            if how:
                out.append((k, ratio, same, how))
        return sorted(out, key=lambda m: (m[2], m[1]), reverse=True)

    def match(self, p):
        m = self.matches(p)
        return m[0] if m else None

    def find_title(self, title, author):
        for k, (_, _, q) in enumerate(self.recs):
            if q.get('title') == title and author_key(q.get('author')) == author_key(author):
                return k
        raise SystemExit(f'FORCE 目标不存在：{author}《{title}》')

    def lookup(self, rel, p):
        key = (rel, p.get('title'))
        if key in SKIP:
            return None
        if key in FORCE:
            return (self.find_title(FORCE[key], p.get('author')), 0.0, True, 'force')
        return self.match(p)


def desc(p):
    return f"{p.get('author')}《{p.get('title')}》"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--apply', action='store_true')
    args = ap.parse_args()
    T = Tang()
    log = []                                 # docs/唐诗去重.tsv 的行
    remove = set()                           # 要删的 poet.tang 记录下标

    # 1. 唐诗三百首.json → tags
    rel = '唐/诗/全唐诗/唐诗三百首.json'
    if os.path.exists(os.path.join(ROOT, rel)):
        for p in load(rel):
            m = T.lookup(rel, p)
            if not m:
                raise SystemExit(f'唐诗三百首对不上：{desc(p)}，请补 FORCE')
            q = T.recs[m[0]][2]
            q['tags'] = list(dict.fromkeys((q.get('tags') or []) + (p.get('tags') or [])))
            note = '' if m[2] else f'选本署名 {p.get("author")} 有误'
            log.append(('唐诗三百首.json', desc(p), T.recs[m[0]][0], desc(q), f'{m[1]:.2f}', '合并 tags', note))

    # 2. 水墨唐诗 → tag + prologue（目录已在后续批次删掉，重跑时跳过）
    rel = '水墨唐诗/shuimotangshi.json'
    keep = []
    for p in (load(rel) if os.path.exists(os.path.join(ROOT, rel)) else []):
        m = T.lookup(rel, p)
        if not m:
            keep.append(p)
            log.append(('水墨唐诗', desc(p), '', '', '', '保留', '全唐诗无对应'))
            continue
        q = T.recs[m[0]][2]
        q['tags'] = list(dict.fromkeys((q.get('tags') or []) + ['水墨唐诗']))
        if p.get('prologue'):
            q['prologue'] = p['prologue']
        note = '' if m[2] else f'选本署名 {p.get("author")}'
        log.append(('水墨唐诗', desc(p), T.recs[m[0]][0], desc(q), f'{m[1]:.2f}', '并入', (m[3] + ' ' + note).strip()))

    # 3. 花间集 / 南唐 → 删 poet.tang 中的重复
    for rel in sorted(glob.glob(os.path.join(ROOT, '五代十国/词/五代诗词/huajianji/*.json'))) + \
            [os.path.join(ROOT, '五代十国/词/五代诗词/nantang/poetrys.json')]:
        rel = os.path.relpath(rel, ROOT)
        book = '花间集' if 'huajianji' in rel else '南唐'
        for p in load(rel):
            if (rel, p.get('title')) in SKIP:
                continue
            ms = T.matches(p)
            dup = [m for m in ms if m[2] and m[3] == 'ratio']     # 同作者的全部副本（乐府、附词各收一次的都删）
            if (rel, p.get('title')) in FORCE:
                dup = [T.lookup(rel, p)]
            for m in dup or ms[:1]:
                f, _, q = T.recs[m[0]]
                if not m[2]:
                    log.append((book, desc(p), f, desc(q), f'{m[1]:.2f}', '保留两边', '作者不同（归属异说）'))
                    continue
                remove.add(m[0])
                log.append((book, desc(p), f, desc(q), f'{m[1]:.2f}', '删除 poet.tang', m[3]))

    for row in log:
        print('\t'.join(row))
    c = collections.Counter((r[0], r[5]) for r in log)
    print('\n'.join(f'{a} {b}: {n}' for (a, b), n in sorted(c.items())))
    if not args.apply:
        return

    drop = collections.defaultdict(set)
    for k in remove:
        drop[T.recs[k][0]].add(T.recs[k][1])
    for f in T.files:
        save(f, [p for i, p in enumerate(T.data[f]) if i not in drop[f]])
    if keep:
        save('水墨唐诗/shuimotangshi.json', keep)
    if os.path.exists(os.path.join(ROOT, '唐/诗/全唐诗/唐诗三百首.json')):
        os.remove(os.path.join(ROOT, '唐/诗/全唐诗/唐诗三百首.json'))
    with open(os.path.join(ROOT, 'docs/唐诗去重.tsv'), 'w', encoding='utf-8') as fp:
        fp.write('来源\t选本记录\tpoet.tang 文件\tpoet.tang 记录\t相似度\t处理\t说明\n')
        fp.writelines('\t'.join(r) + '\n' for r in log)


if __name__ == '__main__':
    main()
