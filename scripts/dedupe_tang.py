#!/usr/bin/env python3
"""《全唐诗》内部去重：删作者名下的重出，留归属异说，按体类重排的卷不动。

  python3 scripts/dedupe_tang.py            # 预演：打印分类、样例与条数
  python3 scripts/dedupe_tang.py --apply    # 写回数据，并生成 docs/唐诗内部去重.tsv

判重口径：正文简繁归一（t2s）去标点后**前 16 字相同**——与 `scripts/check_tree.py` 同口径，
半首之后有出入的同一首也算重复。差别在于按组处理：一组两条只删一条，一组三条删两条。

三类性质不同，处理也不同：

  同作者重出   作者同一人（含同一人的两种署名，僧貫休／貫休；见 ALIAS）。删「信息少」的那条：
               有集注 tags / prologue、正文更长、不在体类卷里的优先留。正文相似度低于 0.9 的
               当异文两存——「两读皆有依据」的一字之差不在这一轮的范围里。
  编排重出     全组都是体类卷题名（郊廟歌辭…、樂府…，且不带「（一作…）」）——
               那是《全唐诗》按体类排的 900 卷与按作者排的 2200 人各排一遍的样子，
               《全唐詩》另一份录文也是这个排法。删了就失真，一组都不动。
  归属异说     作者不同，又不是纯体类卷题名（太宗／董思恭《詠弓》、明皇帝／梁鍠《傀儡吟》）。
               按「一作某」处理：两条都留，在对方 `tags` 里挂一条互见，正文一字不动。

互见挂 `tags` 而不是 `sources`：`sources` 是「这条正文还见于哪部书」，与 `tags: ["唐诗三百首"]`
这种归属标记同义；「一作某人《某题》」是校记，不是来源。2026-10 起全库不再有 `sources` 的
作者题名互见（`poet.tang.58000.json` 那 1598 条都是本脚本上一版写的，已改挂 `tags`）。

题名不同的同一首（《三臺》与《三臺二首 一》、《清平調》与《清平調詞三首 一》）照删：
《全唐诗》作者名下那一条，信息是全的。

作者别名表与人工判例在 ALIAS / FORCE / SKIP 里，改判先改这里。
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

BOOK = '唐/诗/全唐诗'
OUT = 'docs/唐诗内部去重.tsv'

# 按体类重排的卷：题名以体类开头，对应作者名下另有一份同样正文（或换了个题名）
ROLL = {'郊廟歌辭', '樂府', '雜曲歌辭', '雜歌謠辭', '舞曲歌辭', '琴曲歌辭', '相和歌辭',
        '近代曲辭', '清商曲辭', '橫吹曲辭', '鼓吹曲辭', '新樂府辭'}

# 同一作者的两种署名（t2s 之后比较）。只收确定性高的：法名前加「僧」、单双名混写、形近讹字。
# 同一首的两种题名（题名不同时相似度会掉到 0.9 以下）：按《全唐诗》本书互见处理，照删。
# 只收乐府题与诗题成对、且两边正文确系一首的。
SAME = [
    # 乐府题名 / 作者名下题名（相似度，判据）
    ('相和歌辭 野田黃雀行', '野田黃雀行'),
    ('雜曲歌辭 薊門行', '薊北行二首 一'),
    ('琴曲歌辭 秋思', '秋思'),
    ('琴曲歌辭 綠竹引', '綠竹引'),
    ('雜曲歌辭 鳴雁行', '鳴雁行'),
    ('舞曲歌辭 白紵歌', '渾鴻臚宅聞歌效白紵'),
    ('雜曲歌辭 涼州詞 二', '涼州詞三首 二'),
    ('雜曲歌辭 大酺樂 二', '大酺樂二首 二'),
    ('雜曲歌辭 竹枝 一', '竹枝詞二首 一'),
    ('雜曲歌辭 竹枝 三', '竹枝詞四首 三'),
    ('雜曲歌辭 楊柳枝 二', '楊枝詞二首 一'),
    ('雜曲歌辭 昇平樂 九', '昇平詞十首 九'),
    ('雜曲歌辭 宮中行樂詞 三', '宮中行樂詞八首 三'),
]

ALIAS = {
    '僧貫休': '貫休', '僧皎然': '皎然', '僧齊己': '齊己', '僧子蘭': '子蘭', '僧處默': '處默',
    '僧修睦': '修睦', '僧尚顏': '尚顏', '僧護國': '護國', '僧鸞': '僧鸞',
    '東方虬': '東方虯', '李舒': '李紓', '郭元振': '郭震', '劉皁': '劉皂', '劉氏媛': '劉媛',
    '劉氏雲': '劉雲', '張汯': '張紘', '王勣': '王績', '楊希道': '楊師道',
}
# 同名不同人，不算别名：楊師道/楊希道 已收在上表（《全唐诗》小传作杨希道者即杨师道），
# 而張喬/李嶠《對月》各二首是两人各自的诗，正文撞了也不并。

# (文件, 下标) 判例：同作者但对「保留哪条」有异议时在这里指定保留者
FORCE = {}
# (文件, 下标)：确认不是重复，跳过
SKIP = set()


def norm(s):
    return re.sub(r'[^\u4e00-\u9fff]', '', cc.convert(s or ''))


def author_key(a):
    a = cc.convert((a or '').strip())
    return ALIAS.get(a, a)


def body(rec):
    return norm(''.join(rec.get('paragraphs') or []))


def is_roll(title):
    return (title or '').split(' ')[0] in ROLL


def has_aka(title):
    """题名里带「（一作…）」的是作者名下那条，不是体类卷的编排条目。"""
    return '（' in (title or '') or '(' in (title or '')


def roll_base(title):
    t = title or ''
    if is_roll(t) and ' ' in t:
        t = t.split(' ', 1)[1]
    return norm(t)


def info_score(rec):
    """信息量：集注标签、赏析、正文长度、题名长短。删重时留分高的。"""
    return (len(rec.get('tags') or []) * 2
            + (10 if rec.get('prologue') else 0)
            + len(body(rec)) / 1000.0
            + (1 if not is_roll(rec.get('title')) else 0))


def load(rel):
    with open(os.path.join(ROOT, rel), encoding='utf-8') as fp:
        return json.load(fp)


def save(rel, data):
    path = os.path.join(ROOT, rel)
    raw = open(path, encoding='utf-8').read()
    indent = len(re.match(r'\[\n( *)', raw).group(1)) if raw.startswith('[\n') else 2
    with open(path, 'w', encoding='utf-8') as fp:
        fp.write(json.dumps(data, ensure_ascii=False, indent=indent) + ('\n' if raw.endswith('\n') else ''))


def corpus():
    files = sorted(glob.glob(os.path.join(ROOT, BOOK, 'poet.tang.*.json')),
                   key=lambda f: int(f.split('.')[-2]))
    files = [os.path.relpath(f, ROOT) for f in files]
    data = {f: load(f) for f in files}
    recs = [(f, i, data[f][i]) for f in files for i in range(len(data[f]))]
    return files, data, recs


def groups_of(recs, prefix=16):
    g = collections.defaultdict(list)
    for f, i, rec in recs:
        b = body(rec)
        if len(b) >= prefix:
            g[b[:prefix]].append((f, i, rec))
    return {k: v for k, v in g.items() if len(v) > 1}


def same_tune(t1, t2):
    return (t1, t2) in SAME or (t2, t1) in SAME


def classify(grp):
    if len({author_key(r.get('author')) for _, _, r in grp}) == 1:
        return 'same_author'
    if all(is_roll(r.get('title')) and not has_aka(r.get('title')) for _, _, r in grp):
        return 'roll_editorial'
    return 'attribution'


def short_copy(keep, x):
    """x 的正文是 keep 的开头（节选、题拟残句），作者是否同一人都算同一首。"""
    kb, b = body(keep[2]), body(x[2])
    return len(b) < 0.6 * len(kb) and kb.startswith(b[:max(8, len(b) - 4)])


def desc(x):
    f, i, r = x
    return f'{os.path.basename(f)}#{i} {r.get("author")}《{r.get("title")}》'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--apply', action='store_true')
    args = ap.parse_args()

    files, data, recs = corpus()
    before = len(recs)
    grps = groups_of(recs)
    drop = collections.defaultdict(set)
    log = []
    stats = collections.Counter()

    for key, grp in sorted(grps.items(), key=lambda kv: (-len(kv[1]), kv[0])):
        kind = classify(grp)

        if kind == 'roll_editorial':
            stats['保留（编排重出）'] += len(grp) - 1
            for x in grp[1:]:
                log.append(('保留（编排重出）', desc(grp[0]), desc(x), '保留原样'))
            continue

        keep = max(grp, key=lambda x: (info_score(x[2]), -len(x[0]), -x[1]))
        gone = [x for x in grp if x != keep]

        if kind == 'attribution':
            stats['保留（归属异说）'] += len(gone)
            for x in gone:
                link = f'{keep[2].get("author")}《{keep[2].get("title")}》'
                if link not in (x[2].get('tags') or []):
                    x[2]['tags'] = (x[2].get('tags') or []) + [link]
                back = f'{x[2].get("author")}《{x[2].get("title")}》'
                if back not in (keep[2].get('tags') or []):
                    keep[2]['tags'] = (keep[2].get('tags') or []) + [back]
                log.append(('保留（归属异说）', desc(keep), desc(x), '两条都留，互挂 tags'))
            continue

        kb = body(keep[2])
        for x in grp:
            if x is keep:
                continue
            ratio = difflib.SequenceMatcher(None, kb, body(x[2]), autojunk=False).ratio()
            if ratio < 0.9 and not short_copy(keep, x) and not same_tune(keep[2].get('title'), x[2].get('title')):
                stats['保留（异文）'] += 1
                log.append(('保留（异文）', desc(keep), f'{desc(x)}（相似度 {ratio:.2f}）', '正文有出入，两读皆有依据'))
                continue
            drop[x[0]].add(x[1])
            stats['删除（同诗重出）'] += 1
            log.append(('删除（同诗重出）', desc(keep), f'{desc(x)}（相似度 {ratio:.2f}）', '保留信息多的一条'))


    print(f'正文前 16 字相同的组 {len(grps)} 个，原有 {before} 条，删 {sum(len(v) for v in drop.values())} 条：')
    for k in ('删除（同诗重出）', '保留（编排重出）', '保留（归属异说）', '保留（异文）'):
        print(f'   {k}: {stats[k]}')
    for kind in ('删除（同诗重出）', '保留（归属异说）', '保留（异文）'):
        rows = [r for r in log if r[0] == kind][:4]
        for r in rows:
            print(f'   [{kind}] {r[1]} ← {r[2]}')

    if not args.apply:
        print('（预演，未写盘；加 --apply 写回）')
        return

    # 互见已改挂 tags：旧版写进 sources 的那 1598 条，重跑时顺手归位
    moved = 0
    for rel, recs in data.items():
        for r in recs:
            srcs = r.get('sources') or []
            links = [s for s in srcs if '《' in s]
            if not links:
                continue
            r['sources'] = [s for s in srcs if s not in links]
            if not r['sources']:
                del r['sources']
            tags = r.setdefault('tags', [])
            for s in links:
                if s not in tags:
                    tags.append(s)
                    moved += 1
    if moved:
        print(f'旧版写进 sources 的互见改挂 tags：{moved} 条')
        # 改挂后 tags 与 sources 撞车的，tags 里那条是多余的（同一条互见写了两遍）
        dup = 0
        for recs in data.values():
            for r in recs:
                srcs = set(r.get('sources') or [])
                if not srcs:
                    continue
                keep = [t for t in r.get('tags') or [] if t not in srcs]
                if len(keep) != len(r.get('tags') or []):
                    dup += len(r.get('tags')) - len(keep)
                    r['tags'] = keep or None
                    if r['tags'] is None:
                        del r['tags']
        if dup:
            print(f'  tags 与 sources 重复的 {dup} 条一并去掉')

    for rel in files:
        if rel in drop:
            data[rel] = [r for i, r in enumerate(data[rel]) if i not in drop[rel]]
    save_all(files, data)

    with open(os.path.join(ROOT, OUT), 'w', encoding='utf-8') as fp:
        fp.write('判定\t保留\t重复\t处理\n')
        for row in log:
            fp.write('\t'.join(row) + '\n')
    print(f'明细写入 {OUT}（{len(log)} 行）')


def save_all(files, data):
    """只写真正变了的文件，缩进与结尾换行照旧。"""
    for rel in files:
        path = os.path.join(ROOT, rel)
        with open(path, encoding='utf-8') as fp:
            if json.load(fp) == data[rel]:
                continue
        save(rel, data[rel])


if __name__ == '__main__':
    main()
