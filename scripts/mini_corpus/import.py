#!/usr/bin/env python3
"""把补充语料的集子正文按 poem-source 的规则落到本库。

规则（与库中既有数据一致）：
  * 繁体、竖排改横排的一行一句；每条只留 作者 / 段落 / 标题 三个字段，
    全用繁体。简体正文用 opencc s2twp 转换，只转字不改字。
  * 选本（乐府、古诗、唐诗三百首、元散曲、昭明文选、古文观止、课外经典）另建目录，
    一律用 book.title 的繁体原名作文件名，按朝代落到对应目录；不并入 全唐诗/宋词，避免与现行去重口径打架。
    与库中已有作品重复的，只记不写，清单进 docs/mini_corpus.tsv。
    元曲三百首由 scripts/merge_yuanqu.py 直接并入 元/元曲/yuanqu.json，不在此列。
  * 补充语料的译文、出处、学段、难度等展示字段不落库。

用法：
  python3 scripts/mini_corpus/import.py --corpus /tmp/mini_corpus.json [--dry-run]
"""
import argparse
import json
import os
import re
import sys
from collections import Counter

import opencc
from opencc import OpenCC

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
S2TW = OpenCC('s2twp')

# 补充语料文件 → (本库目录, 是否按 gradeGroup 分卷)
BOOKS = {
    'poems-yuefu.js': ('汇编/乐府诗集', True),
    'poems-gushi.js': ('汉/古诗源', True),
    'poems-tangshi.js': ('唐/唐诗三百首', False),
    'poems-zhaoming.js': ('汇编/昭明文选', True),
    'poems-guwen.js': ('先秦/古文观止', True),
    'poems-classic.js': ('先秦/课外经典', True),
}
TEXT_DIRS = ('唐/诗/全唐诗', '宋/诗/全宋诗', '宋/宋词', '元/元曲')


def norm_title(t):
    return re.sub(r'\s+', '', re.sub(r'[（(][^)）]*[)）]', '', t or ''))


def load_corpus_index():
    """本库已有作品：标题 → 出处，用于判重（只报不写）。"""
    idx = {}
    for top in TEXT_DIRS:
        for dirpath, _, filenames in os.walk(os.path.join(ROOT, top)):
            for f in sorted(filenames):
                if not f.endswith('.json'):
                    continue
                try:
                    with open(os.path.join(dirpath, f), encoding='utf-8') as fp:
                        data = json.load(fp)
                except (json.JSONDecodeError, UnicodeDecodeError):
                    continue
                for it in data if isinstance(data, list) else [data]:
                    if not isinstance(it, dict):
                        continue
                    for key in ('title', 'rhythmic'):
                        t = it.get(key)
                        if t:
                            idx.setdefault(norm_title(t), os.path.relpath(
                                os.path.join(dirpath, f), ROOT))
    return idx


def want(item):
    """补充语料条目是否值得落库：去掉标题带「（一）」之类的重出副本与摘句。"""
    title = item.get('title') or ''
    if not title or re.search(r'（[一二三四五六七八九十]+）$', title):
        return False
    text = (item.get('text') or '').strip()
    return bool(text)


def to_paragraphs(text):
    # 「~~」是补充语料对底本缺字的记法，换成本库惯用的「□」；
    # 简转繁会把引文里的「云」误转成「雲」，这几处按原文改回
    out = []
    for line in text.replace('~~', '□').split('\n'):
        line = line.strip()
        if line:
            line = S2TW.convert(line)
            line = line.replace('《詩》雲', '《詩》云').replace('舁夫雲', '舁夫云')
            out.append(line)
    return out


def build(corpus, idx, log):
    books = {}
    for src, (book, by_volume) in BOOKS.items():
        items = corpus.get(src) or []
        volumes = {}
        for it in items:
            if not want(it):
                continue
            title = (it.get('title') or '').strip()
            paras = to_paragraphs(it['text'])
            if not paras:
                continue
            dup = idx.get(norm_title(S2TW.convert(title)))
            if dup:
                log.append((book, title, it.get('author') or '', it.get('dynasty') or '', dup))
                continue
            rec = {
                'author': S2TW.convert((it.get('author') or '').strip() or '佚名'),
                'paragraphs': paras,
                'title': S2TW.convert(title).replace('·', '・'),
            }
            volume = ''
            if by_volume:
                volume = it.get('gradeGroup') or it.get('group') or ''
            if src == 'poems-zhaoming.js' and '·' not in volume:
                # 补充语料这类条目卷名只写了文体；「赋」「其他」两类与上面重名，
                # 给「赋」加前缀，避免两卷写进同一个文件
                volume = ('赋上' if volume == '赋' else '') + (volume or '其他')
            volumes.setdefault(volume, []).append(rec)
        if volumes:
            books[book] = volumes
    return books


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--corpus', required=True, help='extract.js 的输出')
    ap.add_argument('--dry-run', action='store_true')
    args = ap.parse_args()

    with open(args.corpus, encoding='utf-8') as fp:
        corpus = json.load(fp)
    idx = load_corpus_index()
    log = []
    books = build(corpus, idx, log)

    written = 0
    for book, volumes in books.items():
        folder = os.path.join(ROOT, book)
        if not args.dry_run:
            os.makedirs(folder, exist_ok=True)
        for volume, recs in volumes.items():
            name = re.sub(r'[\\/:*?"<>|\s]+', '', volume)
            name = book if name == '' else name
            path = os.path.join(folder, name + '.json')
            print(f'{os.path.relpath(path, ROOT):48s} {len(recs):4d} 条')
            written += len(recs)
            if not args.dry_run:
                with open(path, 'w', encoding='utf-8') as fp:
                    json.dump(recs, fp, ensure_ascii=False, indent=2)
                    fp.write('\n')
    print(f'\n共写入 {written} 条，{sum(len(v) for v in books.values())} 卷；重复跳过 {len(log)} 条')

    if not args.dry_run and log:
        os.makedirs(os.path.join(ROOT, 'docs'), exist_ok=True)
        with open(os.path.join(ROOT, 'docs/mini_corpus.tsv'), 'w', encoding='utf-8') as fp:
            fp.write('集子\t作品\t作者\t朝代\t本库已有\n')
            for row in log:
                fp.write('\t'.join(row) + '\n')
    return 0


if __name__ == '__main__':
    sys.exit(main())
