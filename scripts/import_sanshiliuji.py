#!/usr/bin/env python3
"""依 repo 内的 reference/三十六計.txt 重新生成《三十六计》正文。

  python3 scripts/import_sanshiliuji.py            # 预演：打印 37 条记录的题名与字数
  python3 scripts/import_sanshiliuji.py --apply    # 写 先秦/文/sanshiliuji.json ＋ progress 记录

底本的体例：`### 第一計‧勝戰計‧瞞天過海` 这样的三级标题下，先一段原文，再一段
`【按語】…`；《總說》前置，末有 `〔全文完〕` 标记。生成时一段按语一条 `paragraphs`，
一条记录一计：

  {"title": "三十六计·勝戰計·瞞天過海", "author": "无名氏",
   "paragraphs": ["備周則意怠…", "【按语】陰謀作為…"], "id": "…"}

底本有两处瑕疵，脚本里都处理了，不必手工补：
  * 第十九计「釜底抽薪」丢了 `###`，标题裸成一行正文，`parse` 按形制认回来；
  * 末行 `〔全文完〕` 是版式标记，不是正文，跳过。

书名写简体、门名计名一仍底本（`勝戰計·瞞天過海`）：底本是繁体，正文一字未动，
只把 `‧` 统一成 `·`（库里标点的既有口径）、`【按語】` 的「語」写作「语」
（这是库里的标记语，不是底本内容）。
"""
import argparse
import hashlib
import json
import os
import re
import sys
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import progress as pg  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = 'reference/三十六計.txt'
OUT = '先秦/文/sanshiliuji.json'
REVIEWER = 'CodeBuddy'

HEAD = re.compile(r'^###\s*(.+?)\s*$')
BARE = re.compile(r'^第\S{1,4}計[‧·]\S{2,4}[‧·].+$')
TITLE = re.compile(r'^第(.+?)計[‧·]\s*(.+?)[‧·]\s*(.+)$')


def BARE_HEAD(line):
    """标题有时丢了 `###`（底本的第十九计），裸成一行正文；按标题认。"""
    return line if BARE.match(line) and '，' not in line else None


def parse(text):
    """→ [(题名, [正文段, 按语段])]"""
    items, cur = [], None
    for line in text.split('\n'):
        line = line.strip()
        if not line:
            continue
        if line.startswith('## ') and not line.startswith('### '):
            continue                    # 书名标题
        if line.startswith('〔') and line.endswith('〕'):
            continue                    # 〔全文完〕这类版式标记
        m = HEAD.match(line)
        head = m.group(1).replace('‧', '·') if m else BARE_HEAD(line)
        if head:
            if head == '總說':
                cur = ('三十六计·总说', [])
            else:
                t = TITLE.match(head)
                if not t:
                    raise ValueError(f'认不出标题体例：{head}')
                cur = (f'三十六计·{t.group(2)}·{t.group(3)}', [])
            items.append(cur)
            continue
        if cur is None:
            raise ValueError(f'标题之前有正文：{line}')
        cur[1].append(line)
    return items


def convert(body):
    """标题、繁简一律不动，只把按语标记的「語」按库里的字形写成「语」。"""
    return [para.replace('【按語】', '【按语】') for para in body]


def base36(n):
    alphabet = '0123456789abcdefghijklmnopqrstuvwxyz'
    s = ''
    while n:
        n, r = divmod(n, 36)
        s = alphabet[r] + s
    return s


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--apply', action='store_true', help='写盘；否则只预演')
    args = ap.parse_args()

    text = open(os.path.join(ROOT, SRC), encoding='utf-8').read()
    items = parse(text)
    if len(items) != 37:
        sys.exit(f'底本应有《总说》＋36 计共 37 条，实得 {len(items)} 条')

    data = []
    for title, body in items:
        if len(body) != 2 or not body[1].startswith('【按語】'):
            sys.exit(f'{title}：应为「原文 + 按语」两段，实得 {len(body)} 段')
        char = sum(len(p) for p in body)
        print(f'{title}\t{char} 字')
        data.append({'author': '无名氏', 'paragraphs': convert(body), 'title': title})

    print(f'\n共 {len(data)} 条，{sum(sum(len(p) for p in d["paragraphs"]) for d in data)} 字')
    if not args.apply:
        return

    path = os.path.join(ROOT, OUT)
    # id 由题名定，重跑不变：题名的 sha1 取前段转 36 进制，宽 5
    for d in data:
        digest = hashlib.sha1(d['title'].encode('utf-8')).hexdigest()
        d['id'] = base36(int(digest[:10], 16))[:5]
    with open(path, 'w', encoding='utf-8') as fp:
        json.dump(data, fp, ensure_ascii=False, indent=2)
        fp.write('\n')

    pg.merge(OUT, {
        'note': f'2026-11 依 repo 内 {SRC} 整本重写（原先只有 36 条计的原文，'
                '无《总说》、无按语）；原文一字未改，仅「‧」→「·」、「按語」→「按语」',
        'date': date.today().isoformat(),
        'reviewer': REVIEWER,
        'status': 'needs_review',
    })
    print(f'\n已写入 {OUT}，progress 记录已更新')


if __name__ == '__main__':
    main()
