#!/usr/bin/env python3
"""《宋词三百首》底本（`reference/宋詞三百首`）的解析与配库。

底本是 `### 词牌·小题 / 作者` + 分段正文的纯文本，312 首；库内宋词分散在
`宋/宋词/ci.song.*.json` 十来个文件里，同一首还常有两条（简体一批、繁体一批）。

配法：底本正文（繁体）→ t2s → 与每条记录正文算 difflib 相似度，取最高的一条。
相似度阈值取 0.72：宋词两批数据的来源不同，同一首常有三五处异文，实测同一首最低 0.83、
不是同一首最高 0.42，阈值落在中间的空档。

本模块只读，不写数据文件。改名 / 改字脚本都从这里的 `pairs()` 取配对结果。
"""
import glob
import json
import os
import re
from collections import defaultdict
from difflib import SequenceMatcher

from opencc import OpenCC

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
REF = os.path.join(ROOT, 'reference', '宋詞三百首')
TAG = '宋词三百首'
T2S = OpenCC('t2s')
S2T = OpenCC('s2t')
HAN = re.compile(r'[\u3400-\u9fff\U00020000-\U0003ffff]')
MIN_RATIO = 0.6


def han(s):
    return ''.join(HAN.findall(s))


def plain(s):
    return han(T2S.convert(s))


def parse_ref():
    """底本 → [{no, title, rhythmic, note, author, paras}]。"""
    out, cur = [], None
    for line in open(REF, encoding='utf-8'):
        s = line.strip()
        if not s:
            continue
        if s.startswith('### '):
            head = s[4:].strip()
            title, author = (head.rsplit(' / ', 1) if ' / ' in head else (head, ''))
            rhythmic, _, note = title.strip().partition('·')
            cur = dict(no=len(out) + 1, title=title.strip(), rhythmic=rhythmic.strip(),
                       note=note.strip(), author=author.strip(), paras=[])
            out.append(cur)
        elif s.startswith('#') or s == '〔全文完〕':
            continue
        elif cur is not None:
            cur['paras'].append(s)
    return out


def load_recs():
    recs = []
    for f in sorted(glob.glob(os.path.join(ROOT, '宋/宋词/ci.song.*.json'))):
        for i, x in enumerate(json.load(open(f, encoding='utf-8'))):
            if not isinstance(x, dict):
                continue
            body = ''.join(p for p in (x.get('paragraphs') or []) if isinstance(p, str))
            recs.append(dict(rel=os.path.relpath(f, ROOT), idx=i, author=x.get('author'),
                             rhythmic=x.get('rhythmic'), title=x.get('title'),
                             tags=x.get('tags') or [], raw=body, plain=plain(body)))
    return recs


def _index(recs):
    inv = defaultdict(set)
    for n, r in enumerate(recs):
        h = r['plain']
        for k in range(0, max(1, len(h) - 5)):
            inv[h[k:k + 6]].add(n)
    return inv


def pairs(ref=None, recs=None):
    """底本每首 → 库内最相近的 1~3 条记录，附相似度。

    候选先按**首句 6 字**取（`find_longest_match` 从整首看，最容易把一首词配到
    词牌、句数都相同的一类词上去，`千秋岁` 曾配到 `西河`）；首句取不到候选时再退到
    整首扫锚点。候选里作者相同（繁简、异体归一后）的优先——宋词两批数据来源不同，
    同一首正文常有三五处出入，正文相似度不足以判断时，作者是最硬的锚。
    """
    ref = ref or parse_ref()
    recs = recs or load_recs()
    inv = _index(recs)
    out = []
    for e in ref:
        body = plain(''.join(e['paras']))
        # 首句有异文（栏/阑、抬/擡）就落空，所以锚点铺满整首，每首隔 5 字取一个 6 字窗
        cand = set()
        for k in range(0, max(1, len(body) - 5), 5):
            cand |= inv.get(body[k:k + 6], set())
        scored = sorted(((SequenceMatcher(None, body, recs[n]['plain'], autojunk=False).ratio(), n)
                         for n in cand), reverse=True)
        who = T2S.convert(e['author'])
        same = sorted(((s_, recs[n]) for s_, n in scored
                       if same_author(T2S.convert(recs[n]['author'] or ''), who)),
                      key=lambda x: -x[0])
        diff = ([(s_, recs[n]) for s_, n in scored if s_ >= MIN_RATIO
                 and not same_author(T2S.convert(recs[n]['author'] or ''), who)]
                if len(same) < 2 else [])
        merged = {}
        for s_, r in same + diff:
            merged.setdefault(r['plain'], (s_, r))
        out.append(dict(ref=e, body=body,
                        hits=sorted(merged.values(), key=lambda x: -x[0])[:4]))
    return out


def same_author(lib, ref):
    """库内作者与底本署名是不是同一个人的写法。底本多写全名，库内或只留字号：
    岳飞/岳飛、蔡幼学/蔡幼學、吕滨/吕渭老、鲁逸仲/孔夷、晏几道/晏幾道。"""
    if not lib or not ref:
        return False
    return lib == ref or lib in ref or ref in lib or SAME_PERSON.get(lib) == ref or SAME_PERSON.get(ref) == lib


def best(p):
    return p['hits'][0][1] if p['hits'] else None


# 底本全名 ↔ 库内所用的字号/异写。只用于配对（判断「是不是同一个人写的」），不据此改作者。
SAME_PERSON = {
    '吕滨': '呂渭老',
    '鲁逸仲': '孔夷',
}

# 底本词牌名 → 本库词牌名。只在底本与库内是同一调的不同写法时用；
# 底本给的是别名（宴山亭 = 燕山亭、木兰花 = 玉楼春），库里用哪个就留哪个，不因为选本换了名字就跟着换。
RHYTHMIC_SAME = {
    '宴山亭': '燕山亭', '燕山亭': '宴山亭',
    '木兰花': '玉楼春', '玉楼春': '木兰花',
    '臨江仙慢': '临江仙',
    '杏花天影': '杏花天',
}


# 底本 311 首与 `anthologies/songci300.json`（识典古籍朱祖谋集解本，284 首）多出来的那批，
# 属前一轮 `retitle_songci300.py` 按另一份底本挂的 tag，本轮的底本里没有。
EXTRA_TAGGED = {
    ('宋/宋词/ci.song.22000.json', 1126): '底本 311 首里没有这一首',
}


def wanted(p=None):
    """底本每首配到的库内记录（frozenset of (rel, idx)），用于判断哪些记录的 tag 该留。"""
    keep = set()
    for p in (p or pairs()):
        for _, r in p['hits']:
            keep.add((r['rel'], r['idx']))
    return keep


def is_target(p):
    """底本这一首该落在哪一条：优先已挂 tag 的同文记录（同一首两批各收一份时，改已挂 tag 的那条）。"""
    hits = p['hits']
    if not hits:
        return None
    tagged = [r for _, r in hits if TAG in r['tags']]
    if tagged:
        return tagged[0]
    uniq = {}
    for s_, r in hits:
        uniq.setdefault(r['plain'], (s_, r))
    return max(uniq.values(), key=lambda x: x[0])[1]


def full_body_ratio(ref_body, rec_plain):
    from difflib import SequenceMatcher
    return SequenceMatcher(None, ref_body, rec_plain, autojunk=False).ratio()
