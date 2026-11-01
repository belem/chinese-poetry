#!/usr/bin/env python3
"""`reference/笑府.txt` → `明/小说/笑府/xiaofu.json`。

底本繁体点校，十三卷，篇下正文一段到底，中间夹「又」起的异说段。文件版式：

    # 笑府〔明〕馮夢龍 編
    ### 笑府序 墨憨齋主人題
    古今來莫非話也……布袋和尚，吾師乎，吾師乎。
    ## 卷一‧古艷部
    墨憨子曰：古艷云者。……集古艷部。          ← 卷首小引，无 `###` 头
    ### 富翁帶巾
    財主命牧童曬巾。……此牛自知分量勝卻主翁多許。

规则：
  * `## 第N卷‧X部` 记卷号与部名；`### 篇名` 起一条记录；
  * 卷名与下一个 `###` 之间的正文是卷首小引（「墨憨子曰：……集X部。」），卷卷都有，
    底本没给它标题：挂到本卷第一条的 `prologue` 字段，不另立一条。
    序（`### 笑府序 墨憨齋主人題`，在卷一之前）同样落在卷一的 `prologue` 前面；
  * 空行不是段落；篇下多段（笑话后附评语、`又`一说的异文）逐段照录，段内一字不动；
  * 题名带卷号：`笑府·卷N·篇名`，与《笑林廣記》同一套口径，一则一条；
  * 重名（〈又〉之类）靠卷号与篇名区分；同卷同名的按底本编次加「其二」「其三」；
  * 卷首编撰者行、篇末 `〔全文完〕` 都不进正文，`author` 统一记「冯梦龙」；
  * `id` 规则同 `scripts/backfill_ids.py`（author|title|正文+分段 blake2b，base22）。

    python3 scripts/import_xiaofu_reference.py            # 写文件
    python3 scripts/import_xiaofu_reference.py --check    # 只比对，不写
"""
import argparse
import hashlib
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = 'reference/笑府.txt'
OUT = '明/小说/笑府/xiaofu.json'
AUTHOR = '冯梦龙'
BOOK = '笑府'
END_MARK = '〔全文完〕'

ALPHABET = '0123456789abcdefghijklmnopqrstuvwxyz'   # base22，与 backfill_ids.py 一致
ID_LEN = 6
CN = {c: i for i, c in enumerate('零一二三四五六七八九')}
SEP = '‧·・\u2027'                                   # 底本用 U+2027，库内另两种分隔符一并收


def cn2int(s):
    s = s.replace('〇', '零')
    if s == '十':
        return 10
    if '十' in s:
        hi, lo = s.split('十')
        return (CN[hi] if hi else 1) * 10 + (CN[lo] if lo else 0)
    return CN[s] if len(s) == 1 else int(''.join(str(CN[c]) for c in s))


def parse_juan(s):
    """`卷一‧古艷部` → (1, '古艷部')；「第」字可有可无。不合版式返回 None。"""
    s = (s[1:] if s.startswith('第') else s).replace(' ', '')
    if not s.startswith('卷'):
        return None
    s, num = s[1:], ''
    while s and (s[0] in CN or s[0] == '十'):
        num += s[0]
        s = s[1:]
    if not num or not s or s[0] not in SEP:
        return None
    return cn2int(num), s[1:].strip()


def base22(digest, n):
    v = int.from_bytes(digest, 'big')
    out = []
    for _ in range(n):
        v, r = divmod(v, 22)
        out.append(ALPHABET[r])
    return ''.join(out)


def line_hash(body):
    return hashlib.blake2b('\x00'.join(body).encode(), digest_size=8).hexdigest()


def make_id(author, title, body, taken):
    key = f'{author}|{title}|{"".join(body)}|{line_hash(body)}'
    for salt in range(1, 16):
        size = ID_LEN + max(0, salt - 1)
        digest = hashlib.blake2b((key if salt == 1 else f'{key}|{salt}').encode(), digest_size=16).digest()
        cand = base22(digest, size)
        if cand not in taken:
            taken.add(cand)
            return cand
    raise SystemExit('id 冲突：' + key[:40])


def parse(path):
    """返回 (序段, 卷列表)，卷为 {'num','head','prologue':[段],'items':[...]}。"""
    preface, juans, juan, cur = [], [], None, None
    for raw in open(path, encoding='utf-8'):
        line = raw.strip('\n').replace('\u3000', ' ').strip()
        if not line or line == END_MARK or line.startswith('# '):
            continue
        if line.startswith('###'):                     # 篇名
            head = line.lstrip('#').strip()
            if juan is None:                           # 卷一之前的《笑府序》
                cur = {'head': head, 'paragraphs': []}
                preface.append(cur)
            else:
                cur = {'head': head, 'paragraphs': []}
                juan['items'].append(cur)
            continue
        if line.startswith('##'):                      # 卷名
            parsed = parse_juan(line.lstrip('#').strip())
            assert parsed, f'卷名不合版式：{line}'
            juan = {'num': parsed[0], 'head': parsed[1], 'prologue': [], 'items': []}
            juans.append(juan)
            cur = None
            continue
        if juan is None:                               # 序的正文
            preface[-1]['paragraphs'].append(line) if preface else preface.append(
                {'head': '笑府序', 'paragraphs': [line]})
        elif cur is None:                              # 卷首小引
            juan['prologue'].append(line)
        else:
            cur['paragraphs'].append(line)
    return preface, juans


def build(preface, juans):
    taken, out = set(), []
    nums = [j['num'] for j in juans]
    assert nums == list(range(1, len(nums) + 1)), f'卷次不连续：{nums}'
    assert all(j['items'] for j in juans), '有卷没有篇目'
    assert all(i['paragraphs'] for j in juans for i in j['items']), '有篇目没有正文'
    preface_paras = [p for rec in preface for p in rec['paragraphs']]
    for j in juans:
        pro = (preface_paras + j['prologue']) if j['num'] == 1 else j['prologue']
        seen = {}
        for k, it in enumerate(j['items']):
            head = it['head']
            seen[head] = seen.get(head, 0) + 1
            if seen[head] > 1:                         # 同卷同名（底本作〈又〉），按编次拆开
                head = f'{head}（其{seen[head]}）'
            title = f"{BOOK}·卷{j['num']}·{head}"
            rec = {'author': AUTHOR, 'title': title}
            if k == 0 and pro:                         # 卷首小引挂本卷第一条
                rec['prologue'] = pro
            rec['paragraphs'] = it['paragraphs']
            rec['id'] = make_id(AUTHOR, title, rec['paragraphs'], taken)
            out.append(rec)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--check', action='store_true', help='只比对现有文件，不写')
    args = ap.parse_args()
    recs = build(*parse(os.path.join(ROOT, SRC)))
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
