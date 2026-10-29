#!/usr/bin/env python3
"""新抓的书里机械可修的瑕疵：重复句读、半角标点、ASCII 残渣、行首游离标点。

    python3 clean_new_books.py <json> [--report]

只动能一句话说清的：,, → ,；、、 → 、；行首的「。，；：」并回上一段；
证据不足的字词讹误一律不碰（见 docs/名著增补.md）。
"""
import argparse, json, re, sys

HALF2FULL = {',': '，', ';': '；', ':': '：', '?': '？', '!': '！'}
DUP = re.compile(r'([，。、；：？！])\1+')
LEAD = re.compile(r'^[。，、；：！？]')


def clean_para(p):
    p = p.strip()
    p = DUP.sub(r'\1', p)
    # 半角标点夹在汉字之间（数字、字母后面的不动）
    p = re.sub(r'(?<=[\u4e00-\u9fff])([,;:?!])(?=[\u4e00-\u9fff“”「」])',
               lambda m: HALF2FULL[m.group(1)], p)
    # 行首游离标点：折行把标点甩到了下一段开头
    p = re.sub(r'^[。，、；：]\s*', '', p)
    return p.strip()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('files', nargs='+')
    ap.add_argument('--report', action='store_true')
    a = ap.parse_args()
    for f in a.files:
        rows = json.load(open(f, encoding='utf-8'))
        changed = 0
        for r in rows:
            out = []
            for p in r['paragraphs']:
                q = clean_para(p)
                if q and q != p:
                    changed += 1
                if q:
                    out.append(q)
            r['paragraphs'] = out
        if not a.report:
            with open(f, 'w', encoding='utf-8') as fp:
                json.dump(rows, fp, ensure_ascii=False, indent=2)
                fp.write('\n')
        print(f'{f}: {len(rows)} 条，改 {changed} 段')


if __name__ == '__main__':
    main()
