#!/usr/bin/env python3
"""`reference/二十四史/史記{1,2}.txt` → `史书/史记/shiji.json`。

底本是〔漢〕司馬遷撰的一百三十卷本，繁体点校，只有白文（无三家注）、
段间空一行。

    1.txt  卷一   五帝本紀第一     … 卷六十四 司馬穰苴列傳第四
    2.txt  卷六十五 孫子吳起列傳第五 … 卷一百三十 太史公自序第七十

文件版式：

    # 史記〔漢〕司馬遷
    ## 卷一‧五帝本紀第一
    黃帝者，少典之子，姓公孫，名曰軒轅。……
    〔全文完〕

规则：
  * `## 卷N…篇名第N` 起一条记录，一卷一条，卷次按汉字数序解码（`百〇一` 这种写法也有）；
  * 卷十三—卷二十二这十卷「表」在底本里只有篇题、没有表格正文，照录为空 `paragraphs`，
    不臆造表格（`scripts/check_structure.py` 对此类卷会报空正文，属已知）；
  * 段前缩进、首尾空白去掉，段内一字不动；`〔全文完〕` 不进正文；
  * 底本卷三十一「為騶伐魯，，至與魯盟乃去」有一处叠逗号，改作一个（唯一一处正文改动）；
  * `author` 记「司马迁」，`dynasty` 记「汉」；
  * `id` 规则同 `scripts/shidian/convert.py`（author|title|正文 blake2b）。

    python3 scripts/import_shiji_reference.py            # 写文件
    python3 scripts/import_shiji_reference.py --check    # 只比对，不写
"""
import argparse
import hashlib
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRCS = ('reference/二十四史/史記1.txt', 'reference/二十四史/史記2.txt')
OUT = '史书/史记/shiji.json'
AUTHOR = '司马迁'
DYNASTY = '汉'
END_MARK = '〔全文完〕'
TOTAL_JUAN = 130

FIXES = (
    ('為騶伐魯，，至與魯盟乃去', '為騶伐魯，至與魯盟乃去'),   # 底本叠逗号（卷三十一 吳太伯世家）
)
EMPTY_JUAN = set(range(13, 23))       # 十表：底本只有篇题

CN = {c: i for i, c in enumerate('零一二三四五六七八九')}
CN['〇'] = 0


def cn_fixed(n):
    """卷号的写法（底本用「百〇一」一路，不用「一百零一」）。"""
    d = '零一二三四五六七八九'
    if n < 10:
        return d[n]
    if n < 20:
        return '十' + (d[n % 10] if n % 10 else '')
    if n < 100:
        return d[n // 10] + '十' + (d[n % 10] if n % 10 else '')
    if n == 100:
        return '百'
    if n < 110:
        return '百〇' + d[n - 100]
    hi, lo = divmod(n - 100, 10)
    return '百' + ('一' if hi == 1 else d[hi]) + '十' + (d[lo] if lo else '')


# 卷十四、十五的卷号与篇名连写（`卷十四十二諸侯年表第二`），
# 故在 1..130 各卷号的写法里取最长匹配
HEAD_RX = re.compile(r'^卷(.+)$')
# 底本百位以上两种写法并存：卷一百作「一百」，卷百〇一作「百〇一」
JUAN_FORMS = {}
for _n in range(1, 131):
    for _f in {cn_fixed(_n), '一' + cn_fixed(_n) if _n >= 100 else cn_fixed(_n)}:
        JUAN_FORMS[_f] = _n
# 「百」是「百〇一」「百三十」的前缀：卷号后要么紧跟「‧」，要么紧跟篇名首字。
# 十四、十五两卷篇名与卷号连写（`卷十四十二諸侯年表第二`），靠「剩余部分不含数字」排歧。
def split_juan(rest):
    cands = [f for f in JUAN_FORMS if rest.startswith(f)]
    assert cands, f'卷名缺卷号：{rest}'
    # 篇名本身也带序号（「…列傳第四十」），故只看紧跟卷号的那一个字符：
    # 是「‧」说明卷号到此为止，是数字说明卷号还没读完。
    def score(f):
        tail = rest[len(f):]
        return (1 if tail[:1] in CN else 0, -len(f))
    return min(cands, key=score)


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
            body = line.lstrip('#').strip().replace(' ', '\u3000')
            m = HEAD_RX.match(body)
            assert m, f'卷名不合版式：{body}'
            rest = m.group(1)
            form = split_juan(rest)
            num, head = JUAN_FORMS[form], rest[len(form):]
            cur = {'num': num,
                   'head': head.strip('\u2027\u3000'),
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
        title = f"史記卷{r['num']}\u3000{r['head']}"
        rec = {'author': AUTHOR, 'title': title, 'dynasty': DYNASTY,
               'paragraphs': r['paragraphs']}
        rec['id'] = make_id(AUTHOR, title, rec['paragraphs'], taken)
        out.append(rec)
    assert len({r['title'] for r in out}) == len(out), '题名重复'
    empty = {i + 1 for i, r in enumerate(out) if not r['paragraphs']}
    assert empty == EMPTY_JUAN, f'空卷与预期不符：{sorted(empty)}'
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--check', action='store_true', help='只比对现有文件，不写')
    args = ap.parse_args()
    recs = build([r for src in SRCS for r in parse(os.path.join(ROOT, src))])
    text = json.dumps(recs, ensure_ascii=False, indent=2) + '\n'
    dst = os.path.join(ROOT, OUT)
    chars = sum(len(p) for r in recs for p in r['paragraphs'])
    empty = sum(1 for r in recs if not r['paragraphs'])
    print(f'{len(recs)} 卷，{sum(len(r["paragraphs"]) for r in recs)} 段，{chars} 字，十表空卷 {empty}')
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
