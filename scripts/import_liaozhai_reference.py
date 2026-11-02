#!/usr/bin/env python3
"""`reference/聊斋志异.txt` → `清/小说/聊斋志异/liaozhaizhiyi.json`（issue #244）。

旧文件是识典古籍青柯亭本的 27 篇（该电子本整卷压页，只取到四卷），整份删除后按本底本重出。
底本是简体排印本、每篇一段到底，**不分卷**，版式：

    《聊斋志异》 清  蒲松龄

    章节数：497
    字数：487677
    ========简介========
    ……
    ========正文========
    前言
    一
    《聊斋志异》曾被认为是文言小说之集大成者。……
    ……
    考城隍
    予姊丈之祖宋公，讳焘，邑廪生。……

规则：

  * 书头（著者行、章节数、字数、简介、`========正文========`）不进正文；
  * 正文起首是整理者蓝翎的一篇《前言》（分段作「一」「二」「三」「四」），不是蒲松龄的文字，
    整篇不收；篇末的 `编者附记`、`&#8212;…` 分隔线一并不收；
  * 篇题顶格、长度不超过 12 字、不以句末标点收尾、后接长段正文 —— 按这个版式切篇；
  * 底本没有卷次，题名就不带卷号，只作篇名（同名篇「雹神」「三生」「龙」「阎罗」「白莲教」「义犬」
    各两见，是《聊斋》原本就有的重出篇目，照录，`id` 由正文定）；
  * 电子书每若干篇插一段网站目录（`古典文学` `|` `外国文学` …`投资金融`），不是正文，整段去掉；
  * 底本的私用区码位是缺字（OCR 没认出来），按全库口径（AGENTS.md 2b）包成 `{…}`，**字不补**。
    全本 49 个码位、37 种字形；`《小翠》`「夫人往责女」一节整段是坏字（半角符号与缺字混排），
    照录不动，等另找底本对勘；
  * `id` 规则同 `scripts/shidian/convert.py`（author|title|正文 blake2b），改正文才变。

    python3 scripts/import_liaozhai_reference.py            # 写文件
    python3 scripts/import_liaozhai_reference.py --check    # 只比对，不写
"""
import argparse
import hashlib
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = 'reference/聊斋志异.txt'
OUT = '清/小说/聊斋志异/liaozhaizhiyi.json'
AUTHOR = '蒲松龄'
DYNASTY = '清'

BODY_MARK = '========正文========'
FIRST_STORY = '考城隍'      # 底本正文的第一篇小说，用来把整理者前言切掉
INTRO_MARK = '========简介========'

# 电子书插入的网站目录：`古典文学` `|` `外国文学` … `投资金融`，每行一个
NAV_WORDS = {'古典文学', '外国文学', '传记纪实', '古典诗词', '世界名著', '四大名著', '历史', '宗教',
             '哲学', '军事', '自然人文', '经济管理', '投资金融', '|'}
# 篇末编者的话与分隔线，不是小说正文
EDITOR_MARKS = re.compile(r'^(编者附记|&#\d+;+\s*)')

# 篇题：顶格、不超过 12 字、不以句末标点收尾、后接长段正文（底本每篇一段到底）
HEAD_MAX = 12

# 底本点多了的地方
PUNCT_FIXES = (
    ('，，', '，'), ('。。', '。'), ('！。', '！'), ('？。', '？'), ('，。', '。'), ('。，', '。'),
)


def clean(line):
    for wrong, right in PUNCT_FIXES:
        line = line.replace(wrong, right)
    return line


def make_id(author, title, body, taken):
    key = f'{author}|{title}|{"".join(body)}'
    size = 6
    while True:
        digest = hashlib.blake2b(key.encode(), digest_size=16).digest()
        v = int.from_bytes(digest, 'big')
        out = ''
        for _ in range(size):
            v, r = divmod(v, 22)
            out = '0123456789abcdefghijklmnopqrstuv'[r] + out
        if out not in taken:
            taken.add(out)
            return out
        size += 1


def existing_ids():
    """库里其余文件的全部 id（新文件自己不算，免得自己撞自己）。"""
    taken = set()
    for dirpath, dirs, files in os.walk(ROOT):
        dirs[:] = [d for d in dirs if d not in
                   {'.git', '.github', '.cnb', 'docs', 'reference', 'scripts', 'loader',
                    'authors', 'dynasties', 'rank', 'strains', 'images'}]
        for f in files:
            if not f.endswith('.json'):
                continue
            rel = os.path.relpath(os.path.join(dirpath, f), ROOT)
            if rel == OUT:
                continue
            try:
                data = json.load(open(os.path.join(dirpath, f), encoding='utf-8'))
            except Exception:
                continue
            if isinstance(data, list):
                for r in data:
                    if isinstance(r, dict) and r.get('id'):
                        taken.add(r['id'])
    return taken


def read_lines():
    """正文区的行：去书头、去网站目录、去编者附记。"""
    out, in_body = [], False
    for raw in open(os.path.join(ROOT, SRC), encoding='utf-8'):
        line = raw.strip('\n').replace('\u3000', ' ').strip()
        if line == INTRO_MARK:
            continue
        if line == BODY_MARK:
            in_body = True
            continue
        if not in_body or not line or line in NAV_WORDS or EDITOR_MARKS.match(line):
            continue
        out.append(line)
    return out


def is_head(lines, i):
    s = lines[i]
    if not s:
        return False
    nxt = next((x for x in lines[i + 1:] if x), '')
    return (len(s) <= HEAD_MAX and not re.search(r'[。！？；：，”』」]$', s)
            and len(nxt) > 30)


def story_start(heads, lines):
    """正文起首是整理者蓝翎的《前言》：`前言` 标题、`一` `二` `三` `四` 四个小标题、
    篇末 `蓝` `翎` 署名，一直排到第一篇小说的篇题 `考城隍`。整段不收。

    版式上分不开小标题和篇题（都是顶格的短行）：小标题后面是整节议论，篇题后面是本篇正文，
    而《聊斋》的短篇只有 31 字（《耳中人》），按长短判会切错。所以认底本那行字：
    第一篇的篇题是 `考城隍`，认不出来就不切（宁可把前言留在库里，也不要吃掉一篇小说）。
    """
    if not lines or lines[0] != '前言':
        return heads[0] if heads else 0
    for i in heads:
        if lines[i] == FIRST_STORY:
            return i
    return heads[0] if heads else 0


def parse():
    lines = read_lines()
    heads = [i for i in range(len(lines)) if is_head(lines, i)]
    if not heads:
        raise SystemExit('没有找到篇题，底本版式变了？')
    # 篇题之前是整理者前言，整段不收
    start = story_start(heads, lines)
    heads = [i for i in heads if i >= start]
    recs = []
    for k, pos in enumerate(heads):
        end = heads[k + 1] if k + 1 < len(heads) else len(lines)
        body = [clean(x) for x in lines[pos + 1:end] if x]
        recs.append({'title': lines[pos], 'paragraphs': body})
    # 私用区缺字包 {}，一个字不补
    for r in recs:
        r['paragraphs'] = [re.sub(r'[\ue000-\uf8ff]', lambda m: '{%s}' % m.group(), p)
                           for p in r['paragraphs']]
    return recs


def build(recs, taken):
    out = []
    for r in recs:
        assert r['paragraphs'], f'{r["title"]} 无正文'
        rec = {'author': AUTHOR, 'title': r['title'], 'dynasty': DYNASTY,
               'paragraphs': r['paragraphs']}
        rec['id'] = make_id(AUTHOR, r['title'], rec['paragraphs'], taken)
        out.append(rec)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--check', action='store_true', help='只比对现有文件，不写')
    args = ap.parse_args()
    recs = build(parse(), existing_ids())
    text = json.dumps(recs, ensure_ascii=False, indent=2) + '\n'
    dst = os.path.join(ROOT, OUT)
    chars = sum(len(p) for r in recs for p in r['paragraphs'])
    print(f'{OUT}: {len(recs)} 篇，{sum(len(r["paragraphs"]) for r in recs)} 段，{chars} 字')
    if args.check:
        old = open(dst, encoding='utf-8').read() if os.path.exists(dst) else ''
        print('  一致' if old == text else '  不一致')
        return 0 if old == text else 1
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    open(dst, 'w', encoding='utf-8').write(text)
    print('  →', OUT)
    return 0


if __name__ == '__main__':
    sys.exit(main())
