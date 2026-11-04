# -*- coding: utf-8 -*-
"""卷三五、三六（詔、冊、令、教、文）九篇：六臣本定字、底本定段，写入 汇编/昭明文选/。

用法（抓取要点见 docs/昭明文选重建.md）：
  1. 把 SBCK300 卷三五、三六的 SSR 章存到 $ZHAOMING_SD（一章一文件，`paragraphList` 原样）；
  2. python3 scripts/anthology/zhaoming_gen36.py           # 只打印对勘报告
     python3 scripts/anthology/zhaoming_gen36.py --apply   # 写回 JSON

底本这两卷切不成「一行一面」（一页里常挤着两三篇的头），所以反面切：
六臣本每段先在底本整卷流里定位（段首 10/8/6 字，段内有异文时退到 5~8 字片断取全局最近匹配），
相邻两段中点作段界，底本每页的结束偏移落在哪一段，这一页就在那一段处断开。
"""
import json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import zhaoming_ref as R
import zhaoming_sd as SD
import zhaoming_variant as V
from opencc import OpenCC

OUT = os.path.join(HERE, '..', '..', '汇编', '昭明文选')
_CC_S2T = OpenCC('s2t')

# 每篇：(卷, 底本起行, 止行(不含), 库内文件, 篇题, 作者, 六臣本章 + 段区间)
# 章后 `#a:b` 是段落下标区间：詔与賢良詔同在六臣本一章里，要按下标切。
SPEC = [
    (35, 15, 16, '诏.json', '詔', '漢武帝', ['1ld5mig26sd9y#2:4']),
    (35, 18, 20, '诏.json', '賢良詔', '漢武帝', ['1ld5mig26sd9y#6:8']),
    (35, 23, 26, '册.json', '冊魏公九錫文', '潘元茂', ['1ld5mig26spx2']),
    (36, 4, 7, '令.json', '宣德皇后令', '任彥昇', ['1j73qwedjopx9_460']),
    (36, 10, 12, '教.json', '為宋公脩張良廟教', '傅季友', ['1j73qwefk3fb1_461']),
    (36, 14, 15, '教.json', '為宋公脩楚元王墓教', '傅季友', ['1j73qwegqf4u4_462']),
    (36, 18, 23, '文.json', '永明九年策秀才文', '王元長', ['1j73qwehmvtbr_463']),
    (36, 25, 30, '文.json', '永明十一年策秀才文', '王元長', ['1j73qwelspq2i_464']),
    (36, 32, 35, '文.json', '天監三年策秀才文', '任彥昇', ['1j73qwerchlq2_465']),
]

# 六臣本 SSR 里没被 t2s 覆盖的旧刻字形/异体，逐字核过（只归字形，不动异文）
EXTRA = {
    '𠃔': '允', '𦕈': '眇', '𮕵': '衷', '㝢': '宇', '𠭇': '畝', '𣅳': '昃',
    '𦇤': '繦', '𣢾': '款', '𤓰': '瓜', '䖍': '虔',
    '㳂': '沿', '䘏': '恤', '𠕋': '冊', '𡨚': '冤', '𨗳': '導', '𨳩': '開',
}

# 本库惯例：这些字沿用简体字形，不转繁体
KEEP = set('里后云于范内宫群禄游凶届干叶况咸余虚辟迹丑贰台才制划克准岳涌周并征')

# 句中读不通、或底本与六臣本各有一讹的地方，逐条对过底本 + 识典古籍（依据见 docs/昭明文选重建.md）
FIX = [
    ('亦在御之而巳', '亦在御之而已'),
    ('是用錫君彤一，彤矢百，玈十，玈矢千', '是用錫君彤弓一，彤矢百，玈弓十，玈矢千'),
    ('若終亩不稅', '若終畝不稅'),
    ('若閑冗卑棄', '若閑冗畢棄'),
    ('子襟不作', '子衿不作'),
    ('屈迹於萬夫', '屈跡於萬夫'),
]

TERM = '。！？；：”'
STRIP = set('，。！？；：、（）()“”‘’ \u3000·…—')
_CACHE = {}


def _s2t(c):
    if c in KEEP:
        return c
    t = _CACHE.get(c)
    if t is None:
        t = _CC_S2T.convert(c)
        _CACHE[c] = t
    return t


def to_trad(s):
    return ''.join(_s2t(c) for c in s)


def norm(s):
    """字形归一：旧刻异体 → 六臣本生僻字 → 简体 → 其余逐字转标准繁体。只归字形，不动异文。"""
    out = []
    for c in s:
        if c in KEEP:
            out.append(c)
            continue
        for table in (V.VAR, EXTRA):
            t = table.get(c)
            if t and t != c:
                c = t
                break
        out.append(c)
    return to_trad(''.join(out))


def cmp_key(s):
    """比对用的键：去标点、繁简归一。"""
    s = ''.join(c for c in s if c not in STRIP)
    return ''.join(OpenCC('t2s').convert(c) for c in s)


def clean(s):
    s = s.replace('■', '□')
    s = re.sub(r'\s+', '', s)
    s = s.replace('‘', '“').replace('’', '”')
    return re.sub(r'·$', '。', s)


def sd_paras(cids):
    out = []
    for cid in cids:
        a, b = 0, None
        if '#' in cid:
            cid, rng = cid.split('#')
            a, b = (int(x) for x in rng.split(':'))
        for pp in SD.load(cid)[a:b]:
            t = clean(SD.body(pp))
            if not t:
                continue
            if len(t) <= 4 and '曰' not in t:          # 篇题下的小字署名
                continue
            if re.match(r'^(六臣|文選卷|六臣註文選卷)', t):   # 卷末页脚
                continue
            out.append(t)
    return out


def locate(sds, ref):
    """六臣本每段在底本整卷流里的位置（全局最近匹配，不「顺次往后找」——一段对偏会带偏后面所有段）。"""
    starts = []
    for x in sds:
        n = cmp_key(x)
        hit = -1
        for L in (10, 8, 6):
            if len(n) >= L:
                k = ref.find(n[:L])
                if k >= 0:
                    hit = k
                    break
        if hit < 0:
            for L in (8, 6, 5):
                for st in range(0, max(1, min(len(n), 40) - L)):
                    k = ref.find(n[st:st + L])
                    if k >= 0:
                        hit = max(0, k - st)
                        break
                if hit >= 0:
                    break
        starts.append(hit if hit >= 0 else (starts[-1] if starts else 0))
    return starts


def seg(vol, lo, hi, cids):
    lines = [clean(l.strip()) for l in R.volume_lines(vol)][lo:hi]
    lines = [l for l in lines if l]
    sds = sd_paras(cids)
    bounds, acc = [], 0
    for l in lines:
        acc += len(cmp_key(l))
        bounds.append(acc)
    ref = ''.join(cmp_key(l) for l in lines)
    starts = locate(sds, ref)
    left = [0] + [(starts[i - 1] + starts[i]) // 2 for i in range(1, len(sds))]
    right = [(starts[i] + starts[i + 1]) // 2 for i in range(len(sds) - 1)] + [len(ref) + 1]
    cuts = [next((i for i in range(len(sds)) if left[i] < e <= right[i]), len(sds) - 1) for e in bounds]
    paras, cur = [], []
    for i, p in enumerate(sds):
        cur.append(p)
        if i in cuts:
            paras.append(''.join(cur))
            cur = []
    if cur:
        if paras:
            paras[-1] += ''.join(cur)
        else:
            paras.append(''.join(cur))
    return lines, sds, paras


def entries():
    files = {}
    for vol, lo, hi, fn, title, author, cids in SPEC:
        _, sds, paras = seg(vol, lo, hi, cids)
        assert sum(map(len, paras)) == sum(map(len, sds)), title
        text = [norm(p) for p in paras]
        for a, b in FIX:
            text = [x.replace(a, b) for x in text]
        text = [re.sub(r'。。', '。', x) for x in text]
        files.setdefault(fn, []).append({'title': title, 'author': author, 'paragraphs': text})
    return files


def main(apply=False):
    for fn, items in entries().items():
        p = os.path.join(OUT, fn)
        old = {}
        if os.path.exists(p):
            old = {x['title']: x for x in json.load(open(p, encoding='utf-8'))}
        out = []
        for it in items:
            o = {'author': it['author'], 'paragraphs': it['paragraphs'], 'title': it['title']}
            if old.get(it['title'], {}).get('id'):
                o['id'] = old[it['title']]['id']
            out.append(o)
        print('%-10s %s' % (fn, [(x['title'], len(x['paragraphs']),
                                 sum(len(y) for y in x['paragraphs'])) for x in out]))
        if apply:
            json.dump(out, open(p, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
            open(p, 'a', encoding='utf-8').write('\n')


if __name__ == '__main__':
    main('--apply' in sys.argv)
