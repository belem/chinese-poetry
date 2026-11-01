#!/usr/bin/env python3
"""`reference/三國演義.txt` → `明/小说/三国演义/sanguoyanyi.json`。

底本是 120 回通行本（首回「宴桃園豪傑三結義　斬黃巾英雄首立功」，
末回「薦杜預老將獻新謀　降孫皓三分歸一統」），繁体点校，回目间用全角空格、
每段前两个全角空格缩进。

文件版式：

    ## 三國演義 〔明〕羅貫中 著
    ## 第一回 宴桃園豪傑三結義　斬黃巾英雄首立功
    　　滾滾長江東逝水，浪花淘盡英雄……
    〔全文完〕

规则：
  * `## 第N回 …` 起一条记录，回次按汉字数序解码（第一百二十回 = 120）；
  * 段前缩进、首尾空白去掉，段内一字不动；空行不是段落；
  * 卷首的著者行不入正文，`author` 统一记「罗贯中」；
  * 篇末 `〔全文完〕` 是文件自己的收尾标记，不是正文，删掉；
  * `id` 规则同 `scripts/shidian/convert.py`（author|title|正文 blake2b），改正文才变。

    python3 scripts/import_sanguo_reference.py            # 写文件
    python3 scripts/import_sanguo_reference.py --check    # 只比对，不写
"""
import argparse
import hashlib
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = 'reference/三國演義.txt'
OUT = '明/小说/三国演义/sanguoyanyi.json'
AUTHOR = '罗贯中'
DYNASTY = '明'
END_MARK = '〔全文完〕'

CN = {c: i for i, c in enumerate('零一二三四五六七八九')}
CN['〇'] = 0
HEAD_RX = re.compile(r'^第([〇零一二三四五六七八九十百]+)回[\s　]*(.+)$')


def cn2int(s):
    s = s.replace('〇', '零')
    if '百' not in s and '十' not in s and len(s) > 1:   # 第一一四回 这种连写的数序
        return int(''.join(str(CN[c]) for c in s if c in CN))
    if '百' in s:
        hi, lo = s.split('百')
        lo = lo.lstrip('零')
        return (CN[hi] if hi else 1) * 100 + (cn2int(lo) if lo else 0)
    if '十' not in s:
        return CN[s]
    hi, lo = s.split('十')
    return (CN[hi] if hi else 1) * 10 + (CN[lo] if lo else 0)


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


def parse(path):
    recs, cur = [], None
    for raw in open(path, encoding='utf-8'):
        line = raw.strip('\n').replace('\u3000', ' ').strip()
        if not line:
            continue
        if line.startswith('##'):
            head = line.lstrip('#').strip().replace(' ', '\u3000')
            m = HEAD_RX.match(head)
            if m:
                cur = {'num': cn2int(m.group(1)), 'head': re.sub(r'\u3000+', '\u3000', m.group(2)).strip(),
                       'paragraphs': []}
                recs.append(cur)
            continue                                   # 著者行等非回目标题不入正文
        if cur is None:
            continue
        if line == END_MARK:
            continue
        cur['paragraphs'].append(line)
    return recs


def build(recs):
    taken, out = set(), []
    nums = [r['num'] for r in recs]
    assert nums == list(range(1, len(nums) + 1)), f'回次不连续：{nums[:5]}…'
    for r in recs:
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
    recs = build(parse(os.path.join(ROOT, SRC)))
    text = json.dumps(recs, ensure_ascii=False, indent=2) + '\n'
    dst = os.path.join(ROOT, OUT)
    chars = sum(len(p) for r in recs for p in r['paragraphs'])
    print(f'{len(recs)} 回，{sum(len(r["paragraphs"]) for r in recs)} 段，{chars} 字')
    if args.check:
        old = open(dst, encoding='utf-8').read()
        print('一致' if old == text else '不一致')
        return 0 if old == text else 1
    open(dst, 'w', encoding='utf-8').write(text)
    print('→', OUT)
    return 0


if __name__ == '__main__':
    sys.exit(main())
