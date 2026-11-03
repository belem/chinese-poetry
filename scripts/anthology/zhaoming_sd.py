# -*- coding: utf-8 -*-
"""识典古籍《昭明文選》六臣注本（SBCK300）SSR 页的白文抽取。

一行 = 正文 + 注文：lineType 1 = 正文行，2 = 注文行（也混着校记、音注），3/8/9 = 空行与标题。
正文与注文在一段里交错排（正文行之间夹着注文短行），所以按「注文块」切：
若某串连续的类型 2 行后面紧跟的仍是类型 1，则该块是夹在正文里的注文/校记，跳过；
若后面不再有类型 1（或已到段尾），则该块起即是本段的注文，此后整段丢弃。
"""
import json, os

D = os.environ.get('ZHAOMING_SD', '/tmp/zhaoming-sd')


def load(v):
    """读识典 SSR 缓存的一章：{章节 id: [paragraph, ...]}。抓取要点见 docs/昭明文选重建.md。"""
    return json.load(open(os.path.join(D, v + '.json'), encoding='utf-8'))

def lines_of(pp):
    return [(l['lineType'], l['content']) for l in json.loads(pp['content'])['lines']]

def body(pp):
    L = lines_of(pp)
    nums = [i for i, (t, _) in enumerate(L) if t in (1, 2)]
    drop = set()
    i = 0
    while i < len(nums):
        if L[nums[i]][0] == 2:
            j = i
            while j + 1 < len(nums) and L[nums[j + 1]][0] == 2:
                j += 1
            nxt = L[nums[j + 1]][0] if j + 1 < len(nums) else None
            if nxt != 1:                      # 注文块之后不再有正文 → 整段丢弃
                for k in range(i, len(nums)):
                    drop.add(nums[k])
                break
            i = j + 1
        else:
            i += 1
    return ''.join(c for i, (t, c) in enumerate(L) if t == 1 and i not in drop)

def raw(pp):
    return ''.join(c for ty, c in lines_of(pp) if ty in (1, 8, 9))
