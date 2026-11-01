#!/usr/bin/env python3
"""`reference/二十四史/三国志{1,2}.txt` → `史书/三国志/sanguozhi.json`。

底本是〔晉〕陳壽撰、〔南朝宋〕裴松之注的六十五卷本，繁体点校，正文与裴注同为段落、
段前两个全角空格缩进、段落之间空一行。

    1.txt  卷一  魏書一 武帝紀第一   … 卷三十三 蜀書三 後主傳第三
    2.txt  卷三十四 蜀書四 二主妃子傳第四 … 卷六十五 吳書二十 王樓賀韋華傳第二十

文件版式：

    # 三國志〔晉〕陳壽 撰 〔南朝宋〕裴松之 注
    ## 三國志卷一　魏書一　武帝紀第一
    　　太祖武皇帝，沛國譙人也，姓曹，諱操，字孟德，漢相國參之後。〔一〕桓帝世，……
    　　〔一〕　〔曹瞞傳曰〕：太祖一名吉利，小字阿瞞。……
    〔全文完〕

规则：
  * `## 三國志卷N　X書N　篇名第N` 起一条记录，一卷一条，卷次按汉字数序解码；
  * 段前缩进、首尾空白去掉，段内一字不动；空行不是段落，`〔全文完〕` 不进正文；
  * 裴注「〔一〕」起句的段落照录，既不改写成 `note` 字段，也不与正文合并——
    陈寿本文与裴注在底本里只靠「〔N〕」这个标记分别，分开就要重新断句；
  * 卷首的撰者行不入正文，`author` 统一记「陈寿」，`dynasty` 记「晋」（他入晋后撰此书）；
  * 底本卷一首裴注「群生注望，，遐邇怨歎」有一处叠逗号，改作一个（唯一一处正文改动）；
  * `id` 规则同 `scripts/shidian/convert.py`（author|title|正文 blake2b），改正文才变。

    python3 scripts/import_sanguozhi_reference.py            # 写文件
    python3 scripts/import_sanguozhi_reference.py --check    # 只比对，不写
"""
import argparse
import hashlib
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRCS = ('reference/二十四史/三国志1.txt', 'reference/二十四史/三国志2.txt')
OUT = '史书/三国志/sanguozhi.json'
AUTHOR = '陈寿'
DYNASTY = '晋'
END_MARK = '〔全文完〕'
TOTAL_JUAN = 65

FIXES = (
    ('群生注望，，遐邇怨歎', '群生注望，遐邇怨歎'),   # 底本叠逗号
)

CN = {c: i for i, c in enumerate('零一二三四五六七八九')}
CN['〇'] = 0
HEAD_RX = re.compile(r'^三國志卷([〇零一二三四五六七八九十百]+)\u3000(.+)$')


def cn2int(s):
    s = s.replace('〇', '零')
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
            assert m, f'卷名不合版式：{head}'
            cur = {'num': cn2int(m.group(1)),
                   'head': re.sub(r'\u3000+', '\u3000', m.group(2)).strip(),
                   'paragraphs': []}
            recs.append(cur)
            continue
        if line.startswith('#') or line == END_MARK:   # 撰者行、收尾标记
            continue
        if cur is None:
            continue
        for wrong, right in FIXES:
            line = line.replace(wrong, right)
        cur['paragraphs'].append(line)
    return recs


def build(recs):
    taken, out = set(), []
    nums = [r['num'] for r in recs]
    assert nums == list(range(1, TOTAL_JUAN + 1)), f'卷次不连续：{nums[:6]}…'
    for r in recs:
        title = f"三國志卷{r['num']}\u3000{r['head']}"
        rec = {'author': AUTHOR, 'title': title, 'dynasty': DYNASTY,
               'paragraphs': r['paragraphs']}
        rec['id'] = make_id(AUTHOR, title, rec['paragraphs'], taken)
        out.append(rec)
    assert len({r['title'] for r in out}) == len(out), '题名重复'
    assert all(r['paragraphs'] for r in out), '有卷没有正文'
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--check', action='store_true', help='只比对现有文件，不写')
    args = ap.parse_args()
    recs = build([r for src in SRCS for r in parse(os.path.join(ROOT, src))])
    text = json.dumps(recs, ensure_ascii=False, indent=2) + '\n'
    dst = os.path.join(ROOT, OUT)
    chars = sum(len(p) for r in recs for p in r['paragraphs'])
    notes = sum(1 for r in recs for p in r['paragraphs'] if p.startswith('〔'))
    print(f'{len(recs)} 卷，{sum(len(r["paragraphs"]) for r in recs)} 段（裴注 {notes} 段），{chars} 字')
    if args.check:
        old = open(dst, encoding='utf-8').read()
        print('一致' if old == text else '不一致')
        return 0 if old == text else 1
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    open(dst, 'w', encoding='utf-8').write(text)
    print('→', OUT)
    return 0


if __name__ == '__main__':
    sys.exit(main())
