#!/usr/bin/env python3
"""`reference/镜花缘.txt` → `清/小说/镜花缘/jinghuayuan.json`（issue #244）。

旧文件是识典古籍道光十二年刻本的 22 回（该电子本缺回 6、12–88），整份删除后按本底本重出。
底本是简体排印本，一百回齐，版式：

    《镜花缘》 清  李汝珍

    章节数：100
    字数：409515
    ========简介========
    ……
    ========正文========
    第01回 女魁星北斗垂景象 老王母西池赐芳筵
    昔曹大家《女诫》云：“女有四行……

规则：

  * 书头（著者行、章节数、字数、简介、`========正文========`）不进正文；
  * 回目行作「第01回 回目」，回次补零；题名统一记「第N回　回目」（全角空格分隔，与库内其余章回小说同）；
  * 一段一行，空行不是段落；
  * 底本的标点大体齐全，只做两件事：半角标点的全角化、重复标点的收敛；
    底本大量在「某某道：」处断行（1291 处，说话人与引语分开排），是底本的分段方式，
    照底本保留，不并段；
  * 底本有 8 个私用区码位（OCR 没认出来）、3 处半角假名（`ソ` `グ`）、1 处 ASCII 残渣
    （`XX子之福`），按全库口径包成 `{…}`，**字不补**；第 26 回翼民国一节整段是乱码，
    以「叫作‘爱戴高帽」起、到「…出来」止，整截照录，等另找底本对勘（同 `scripts/import_novel_chapter.py`
    的 `GARBLE_CUTS` 记的那一处，那里按通行本校补过，本轮不猜改）；
  * `id` 规则同 `scripts/shidian/convert.py`（author|title|正文 blake2b），改正文才变。

    python3 scripts/import_jinghuayuan_reference.py            # 写文件
    python3 scripts/import_jinghuayuan_reference.py --check    # 只比对，不写
"""
import argparse
import hashlib
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = 'reference/镜花缘.txt'
OUT = '清/小说/镜花缘/jinghuayuan.json'
AUTHOR = '李汝珍'
DYNASTY = '清'

BODY_MARK = '========正文========'
INTRO_MARK = '========简介========'

CN = {c: i for i, c in enumerate('零一二三四五六七八九')}
HEAD = re.compile(r'^第([〇零一二三四五六七八九十百0-9]+)回[\s　]*(\S+)[\s　]+(\S.*)$')

# 底本《前言》末尾的「&#8212;…」分隔线，不是正文
EDITOR_MARKS = re.compile(r'^&#\d+;+\s*')

PUNCT_FIXES = (
    ('，，', '，'), ('。。', '。'), ('；；', '；'), ('：：', '：'), ('，。', '。'), ('。，', '。'),
    ('！。', '！'), ('？。', '？'),
)
HALF_PUNCT = ((';', '；'), (',', '，'), ('!', '！'), (':', '：'), ('?', '？'))


def cn2int(s):
    s = s.replace('〇', '零')
    if s.isdigit():
        return int(s)
    if '百' not in s and '十' not in s and len(s) > 1:
        return int(''.join(str(CN[c]) for c in s if c in CN))
    if '百' in s:
        hi, lo = s.split('百')
        lo = lo.lstrip('零')
        return (CN[hi] if hi else 1) * 100 + (cn2int(lo) if lo else 0)
    if '十' not in s:
        return CN[s]
    hi, lo = s.split('十')
    return (CN[hi] if hi else 1) * 10 + (CN[lo] if lo else 0)


def clean(line):
    for wrong, right in PUNCT_FIXES:
        line = line.replace(wrong, right)
    for half, full in HALF_PUNCT:
        line = re.sub(r'(?<=[\u4e00-\u9fff])' + re.escape(half) + r'(?=[\u4e00-\u9fff])', full, line)
    return line


def wrap_missing(line):
    """缺字与乱码字符包成 {…}，字不补（AGENTS.md 2b）。

    必须在各项替换之后做：`{}` 里的字不再参与替换，也不能被二次包裹。
    """
    return re.sub(r'\{[^}]*\}|[\ue000-\uf8ff]|[\u3040-\u30ff]|[A-Za-z]{2,}',
                  lambda m: m.group() if m.group().startswith('{') else '{%s}' % m.group(), line)


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


def parse():
    recs, cur, in_body = [], None, False
    for raw in open(os.path.join(ROOT, SRC), encoding='utf-8'):
        line = raw.strip('\n').replace('\u3000', ' ').strip()
        if not line:
            continue
        if line == INTRO_MARK:
            continue
        if line == BODY_MARK:
            in_body = True
            continue
        if not in_body or EDITOR_MARKS.match(line):
            continue
        m = HEAD.match(line)
        if m:
            head = re.sub(r'\s+', '\u3000', f'{m.group(2)} {m.group(3)}'.strip())
            cur = {'num': cn2int(m.group(1)), 'head': head, 'paragraphs': []}
            recs.append(cur)
            continue
        cur['paragraphs'].append(wrap_missing(clean(line)))
    return recs


def build(recs, taken):
    nums = [r['num'] for r in recs]
    if nums != list(range(1, len(nums) + 1)):
        raise SystemExit(f'回次不连续：{nums[:8]}… 共 {len(recs)} 条')
    out = []
    for r in recs:
        assert r['paragraphs'], f'第{r["num"]}回 无正文'
        title = f"第{r['num']}回\u3000{r['head']}"
        rec = {'author': AUTHOR, 'title': title, 'dynasty': DYNASTY,
               'paragraphs': r['paragraphs']}
        rec['id'] = make_id(AUTHOR, title, rec['paragraphs'], taken)
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
    print(f'{OUT}: {len(recs)} 回，{sum(len(r["paragraphs"]) for r in recs)} 段，{chars} 字')
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
