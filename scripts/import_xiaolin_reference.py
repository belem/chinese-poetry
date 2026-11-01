#!/usr/bin/env python3
"""`reference/笑林廣記.txt` → `清/小说/笑林广记/xiaolinguangji.json`。

底本是通行十二卷本（卷一古艷部 … 卷十二謬誤部），繁体点校，篇下正文一段到底。
文件版式：

    # 笑林廣記 〔清〕游戲主人 編
    ## 第一卷‧古艷部
    ### 升官
    一官升職，謂其妻曰：「我的官職比前更大了。」……
    〔全文完〕

规则：
  * `## 第N卷‧X部` 记卷号与部名，`### 篇名` 起一条记录；
  * 正文段前缩进、首尾空白去掉，段内一字不动；空行不是段落；
  * 篇名与部名重名（第二卷〈貓逐鼠〉、第三卷〈取名〉、第六卷〈親嘴〉〈取名〉〈怕冷〉、
    第七卷〈爭坐〉、第十一卷〈通譜〉〈聯宗〉〈貓逐鼠〉）照录，不改题；
  * 底本里跨页处的「`2 \t`」「`3 \t`」是分页行号残渣，不是正文，去掉行号只留文字（共三篇）；
  * 底本的 `──` 是破折号（「把我便──」「親──家公」），`─` 是「一」的错字，一并改正；
  * 底本「不見了扇子，，」有一个重复的逗号，改成一个；
  * 卷首的编撰者行、篇末 `〔全文完〕` 都不进正文，`author` 统一记「遊戲主人」；
  * `id` 规则同 `scripts/shidian/convert.py`（author|title|正文 blake2b），改正文才变。

    python3 scripts/import_xiaolin_reference.py            # 写文件
    python3 scripts/import_xiaolin_reference.py --check    # 只比对，不写
"""
import argparse
import hashlib
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = 'reference/笑林廣記.txt'
OUT = '清/小说/笑林广记/xiaolinguangji.json'
AUTHOR = '遊戲主人'
DYNASTY = '清'
BOOK = '笑林廣記'
END_MARK = '〔全文完〕'

PAGE_NO = re.compile(r'^\d+\s*\t\s*')      # 跨页处的分页行号残渣，如「2 \t」
FIXES = (
    ('──', '——'),                            # 底本用六号横线作破折号
    ('，,', '，'),
    ('，，', '，'),
    ('與他相處─生', '與他相處一生'),
    ('─人衣軟', '一人衣軟'),
)

CN = {c: i for i, c in enumerate('零一二三四五六七八九')}
JUAN_RX = re.compile(r'^第([〇零一二三四五六七八九十百]+)卷[‧·・]\s*(.+)$')


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
    recs, juan, cur = [], None, None
    for raw in open(path, encoding='utf-8'):
        line = raw.strip('\n').replace('\u3000', ' ').strip()
        if not line:
            continue
        if line.startswith('###'):                     # 篇名
            head = line.lstrip('#').strip()
            assert juan is not None, f'篇名在卷名之前：{head}'
            cur = {'juan': juan, 'head': head, 'paragraphs': []}
            recs.append(cur)
            continue
        if line.startswith('##'):                      # 卷名
            head = line.lstrip('#').strip().replace(' ', '')
            m = JUAN_RX.match(head)
            assert m, f'卷名不合版式：{head}'
            juan = {'num': cn2int(m.group(1)), 'head': m.group(2)}
            cur = None
            continue
        if line.startswith('#'):                       # 书名与编撰者行
            continue
        if line == END_MARK or cur is None:
            continue
        line = PAGE_NO.sub('', line)
        for wrong, right in FIXES:
            line = line.replace(wrong, right)
        cur['paragraphs'].append(line)
    return recs


def build(recs):
    taken, out = set(), []
    nums = sorted({r['juan']['num'] for r in recs})
    assert nums == list(range(1, len(nums) + 1)), f'卷次不连续：{nums}'
    for r in recs:
        title = f"{BOOK}·卷{r['juan']['num']}·{r['head']}"
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
    assert all(r['paragraphs'] for r in recs), '有篇目没有正文'
    assert len({r['title'] for r in recs}) == len(recs), '题名重复'
    text = json.dumps(recs, ensure_ascii=False, indent=2) + '\n'
    dst = os.path.join(ROOT, OUT)
    chars = sum(len(p) for r in recs for p in r['paragraphs'])
    print(f'{len(recs)} 篇，{sum(len(r["paragraphs"]) for r in recs)} 段，{chars} 字')
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
