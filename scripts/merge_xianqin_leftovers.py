#!/usr/bin/env python3
"""处理 reorg_xianqin.py 之后 poet.xianqin 里仅剩的几条。

reorg_xianqin.py 判重按「简繁归一、去标点后逐字相同」，剩下 4 条都过不了这一关：

  楚辞·九歌·其八·河伯      与 chuci.json 同名篇有出入（本是同篇，异文）
  楚辞·九章·其一·惜诵     同上
  楚辞·九章·其六·思美人    同上
  《诗经·卫风·竹竿》/《大雅·烝民》 已判为全同，随 reorg 删掉

本脚本把三首楚辞的异文挂到 chuci.json 对应篇目的 `variants` 字段（不动正文，
「一件作品一份正文」），然后把 poet.xianqin.json 删掉——剩下的只有《越人歌》，
它是楚辞体的先声，补进 chuci.json 作独立篇目。

用法：
  python3 scripts/merge_xianqin_leftovers.py            # dry-run
  python3 scripts/merge_xianqin_leftovers.py --apply
"""
import argparse
import json
import os
import re
import sys

from opencc import OpenCC

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
T2S = OpenCC('t2s')
PUNCT = re.compile(r'[“”「」『』"\'‘’（）()，。、；：！？,.;:!?□【】\[\]·—…《》〈〉\s]')

SOURCE = '先秦/诗/poet.xianqin.json'
CHUCI = '先秦/楚辞/chuci.json'

# poet.xianqin 题名 → (chuci.json 里的 section, title)
CHUCI_MAP = {
    '楚辞·九歌·其八·河伯': ('九歌', '河伯'),
    '楚辞·九章·其一·惜诵': ('九章', '惜诵'),
    '楚辞·九章·其六·思美人': ('九章', '思美人'),
}


def norm(s):
    return PUNCT.sub('', T2S.convert(s or ''))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--apply', action='store_true')
    args = ap.parse_args()

    left = json.load(open(os.path.join(ROOT, SOURCE), encoding='utf-8'))
    chuci = json.load(open(os.path.join(ROOT, CHUCI), encoding='utf-8'))
    by_key = {(r['section'], r['title']): r for r in chuci}

    plan = []
    for rec in left:
        title = rec.get('title')
        if title in CHUCI_MAP:
            key = CHUCI_MAP[title]
            plan.append(('variant', rec, key))
        elif title == '越人歌':
            plan.append(('new', rec, None))
        else:
            raise SystemExit(f'没料到的条目，先补规则：{title}')

    for kind, rec, key in plan:
        if kind == 'variant':
            target = by_key[key]
            same = norm(''.join(target['content'])) == norm(''.join(rec['paragraphs']))
            print(f'variant {rec["title"]} → chuci《{key[1]}》 正文字数 '
                  f'{sum(len(x) for x in rec["paragraphs"])} / '
                  f'{sum(len(x) for x in target["content"])}'
                  f'{"（实为全同，应删）" if same else ""}')
        else:
            print(f'new     {rec["title"]} → chuci.json 新篇目（{rec["author"]}）')

    if not args.apply:
        print('（dry-run，未改动任何文件；加 --apply 落盘）')
        return

    for kind, rec, key in plan:
        if kind == 'variant':
            target = by_key[key]
            if norm(''.join(target['content'])) == norm(''.join(rec['paragraphs'])):
                continue                      # 实际全同，正文只留专书那份
            variants = target.setdefault('variants', [])
            variants.append({'content': rec['paragraphs']})
        else:
            chuci.append({
                'title': rec['title'],
                'section': '附',
                'author': rec['author'],
                'content': rec['paragraphs'],
                'note': '楚辞体先声，古歌辞，非屈原作',
            })

    with open(os.path.join(ROOT, CHUCI), 'w', encoding='utf-8') as fp:
        json.dump(chuci, fp, ensure_ascii=False, indent=2)
        fp.write('\n')
    print(f'  写 {CHUCI}  {len(chuci)} 篇')

    os.remove(os.path.join(ROOT, SOURCE))
    print(f'  删 {SOURCE}')
    # 空目录一并删掉
    d = os.path.dirname(os.path.join(ROOT, SOURCE))
    if not os.listdir(d):
        os.rmdir(d)
        print(f'  删空目录 {os.path.dirname(SOURCE)}/')


if __name__ == '__main__':
    main()
