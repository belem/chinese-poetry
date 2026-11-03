# -*- coding: utf-8 -*-
"""卷五一至六十：底本与六臣注本逐段对勘，产出可直接落库的段落。

两边的三层关系：

1. **分卷分篇**：底本每卷前有「卷五三 论三」这样的卷头；六臣本一卷一章，长卷（论一、论三、
   诔上、碑文上、碑文上）在站上被切成一篇文章一章，后续章节没有卷头，要按「下一篇」跟随
   着抓（`$ZHAOMING_SD` 里一章一文件，`sd9_order.json` 是抓取顺序）。
2. **分段**：六臣本 DOM 一行 = 原书一个自然段，最可靠；底本是「一行一面」，注文切不干净时
   一面只剩半句。
3. **字句**：六臣本是宋刊本，字形古（丗/嵗/髙/曺），字句多胜；底本是简体排印李善注本，
   正文常被注文连带切掉。

做法：**以六臣本的段为骨架**，逐段从底本白文里取同一段来校验；底本在这一段明显更全
（六臣本丢了正文）时改用底本的，并把两者都记下来供人工定案。
"""
import json, os, re, sys
from difflib import SequenceMatcher

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import zhaoming_align as AL
import zhaoming_ref as R
import zhaoming_seg as S
import zhaoming_variant as V

SD = os.environ.get('ZHAOMING_SD', '/tmp/zhaoming-sd')


def ref_pieces(vol):
    """底本一卷的篇目：[{title, author, refs: [段落白文...]}]。"""
    out, cur = [], None
    for kind, t in R.paragraphs(vol):
        if kind == 'head':
            if t.startswith('※'):
                if cur:
                    cur['author'] = t[1:].strip()
                continue
            if t.startswith('【'):
                cur = {'title': re.match(r'【([^】]+)】', t).group(1), 'author': '', 'refs': []}
                out.append(cur)
            continue
        if cur is not None:
            cur['refs'].append(t)
    return out


def chapter_ids():
    """抓取顺序（`order.json`）：从「六臣注文選卷第五十一」那一章起，顺着「下一篇」往下抓的
    章节 id。长卷被切开的后续章节没有卷头，靠这个顺序定位它属于哪一卷。"""
    return json.load(open(os.path.join(SD, 'order.json'), encoding='utf-8'))


def _volume_map(order):
    """章节 id → 卷号：有卷头的按卷头，没有的沿用它前面最近一章的卷号。"""
    out, cur = {}, None
    for cid in order:
        v = S.chapter_volume(cid)
        if v is not None:
            cur = v
        out[cid] = cur
    return out


def sd_pieces(vol, order=None):
    """六臣本一卷的篇目：[{title, author, paras, chapter}]，按抓取顺序拼起来。"""
    order = list(order or chapter_ids())
    vmap = _volume_map(order)
    out, cur = [], None
    for cid in order:
        if vmap.get(cid) != vol:
            continue
        for kind, t in S.paragraphs(cid, vol):
            if kind == 'title':
                cur = {'title': t, 'author': '', 'paras': [], 'chapter': cid}
                out.append(cur)
                continue
            if kind == 'para' and cur is not None and _same(cur['title'], t):
                continue
            if kind == 'author' and cur is not None and not cur['author']:
                cur['author'] = t.strip('，,')
            elif kind == 'para' and cur is not None:
                cur['paras'].append(V.norm(t))
    return out


GENRES = {'论一', '论二', '论三', '论四', '论五', '连珠', '箴', '铭', '诔上', '诔下', '哀上', '哀下',
          '碑文上', '碑文下', '墓志', '行状', '吊文', '祭文'}


def _norm_title(x):
    x = AL.flat(x)
    x = re.sub(r'[（(]?并序[）)]?|一首|[上下]二首', '', x)
    x = x.replace('諸侯', '').replace('诸侯', '')
    x = x.replace('新漏刻', '新刻漏').replace('頭纮寺', '頭陀寺').replace('头纮寺', '头陀寺')
    x = x.replace('聽', '听')
    return x


def _same(a, b):
    a, b = _norm_title(a), _norm_title(b)
    return bool(a) and a == b


def same_title(a, b):
    """同一篇：篇题相同，或一方是另一方的开头（「辩亡论上下二首」vs「辨亡论上下二首」）。"""
    a, b = _norm_title(a), _norm_title(b)
    if not a or not b:
        return False
    # 体类名不是篇题（「铭」「诔上」「论五」），只做完全相同的比较
    if AL.flat(a) in GENRES or AL.flat(b) in GENRES:
        return AL.flat(a) == AL.flat(b)
    if a == b:
        return True
    # 简繁、异体只差一字（辯/辨、徵/徴、荊/荆）：先按字面比
    ta, tb = set(a), set(b)
    common = len(ta & tb) / max(1, len(ta | tb))
    if common >= 0.6 and (a.startswith(b) or b.startswith(a) or (len(a) > 3 and a[:3] == b[:3])):
        return True
    # 再按「只差一两个字」比（简繁、异体、切词写法不同：辨命論/辩命论、陶徵士誄/陶徴士誄）
    from difflib import SequenceMatcher
    if len(a) != len(b):
        return False
    diff = sum(1 for x, y in zip(a, b) if x != y)
    return diff <= max(1, len(a) // 4)


# 站上截图与底本写法不同的篇题（底本切词有误字、站上为异体），逐条定案
TITLE_ALIAS = {
    '齐故安陆昭王碑文一首': '齊故安陸昭王碑文一首',
    '新刻漏铭': '新漏刻銘一首',
    '头纮寺碑文': '頭陀寺碑文一首',
    '辩亡论上下二首': '辨亡論上下二首',
    '辩亡论下': '辨亡論下',
    '辩命论': '辨命論一首',
    '陶徵士诔': '陶徴士誄',
    '宋孝武宣贵妃诔': '宋孝武宣貴妃誄',
}


def match(refp, sdp):
    used, out = set(), []
    for item in refp:
        hit = None
        alias = TITLE_ALIAS.get(item['title'])
        for i, s in enumerate(sdp):
            hit_alias = alias and AL.flat(alias) == AL.flat(s['title'])
            if i not in used and (hit_alias or same_title(item['title'], s['title'])):
                hit = i
                break
        if hit is not None:
            used.add(hit)
        out.append((item, sdp[hit] if hit is not None else None))
    return out


def unmatched_ref(refp, pairs):
    """底本有正文、六臣本没配上的篇（通常是对不上篇题）。"""
    got = {id(i) for i, s in pairs if s}
    return [i for i in refp if i['refs'] and id(i) not in got]


def body_of(refs, sd_paras, ratio=0.8):
    """一篇的段落：骨架取六臣本的段，逐段用底本白文核对。

    返回 [(六臣本段, 底本在该段上的白文, 是否改用底本)]。
    """
    flatA = AL.flat(''.join(refs))
    B = [AL.flat(x) for x in sd_paras]
    sb = ''.join(B)
    sm = SequenceMatcher(None, flatA, sb, autojunk=False)
    a2b = {}
    for blk in sm.get_matching_blocks():
        for k in range(blk.size):
            a2b[blk.a + k] = blk.b + k
    bstart, acc = [], 0
    for x in B:
        bstart.append(acc)
        acc += len(x)
    out = []
    covered = set()
    for j, (b, raw) in enumerate(zip(B, sd_paras)):
        lo, hi = bstart[j], bstart[j] + len(b)
        ks = sorted(k for k, v in a2b.items() if lo <= v < hi)
        if not ks:
            # 六臣本这一段一个字都没对上底本：底本这里多半是一整页正文，
            # 这一页还没被任何六臣本段认领过，就用底本的
            left = [k for k in range(len(flatA)) if k not in covered]
            if len(b) * 2 < len(left) and left == list(range(left[0], left[-1] + 1)):
                # 只取紧接上一段之后的那几句，避免整页塞进这里
                pass
            out.append((raw, '', False))
            continue
        covered.update(ks)
        # 底本这一段的白文：取 k 连续的若干段中最长的一串（底本被注文打断时不拼凑）
        spans, cur = [], [ks[0]]
        for k in ks[1:]:
            if k == cur[-1] + 1:
                cur.append(k)
            else:
                spans.append(cur)
                cur = [k]
        spans.append(cur)
        spans.sort(key=len, reverse=True)
        seg = ''.join(flatA[k] for k in spans[0])
        use = len(seg) > len(b) * ratio
        out.append((raw, seg, use))
    return out


def build_volume(vol, order=None):
    """一卷的结果：[{ref_title, sd_title, author, rows:[(sd_text, ref_text, use_ref)]}]。"""
    rp = ref_pieces(vol)
    sp = sd_pieces(vol, order)
    out = []
    for item, sd in match(rp, sp):
        if not item['refs']:
            continue
        rows = body_of(item['refs'], sd['paras']) if sd else [(r, '', False) for r in item['refs']]
        out.append({'ref_title': item['title'], 'sd_title': (sd or {}).get('title'),
                    'author': (sd or {}).get('author') or item['author'],
                    'rows': rows})
    return out


def final_text(rows):
    """一段的定稿：六臣本为准；标记用底本的用底本（底本这段更全）。

    两边都是简体（本库用标准简体字），字形差异已在 `zhaoming_variant.norm` 里归一。
    """
    return [ref if use else sd for sd, ref, use in rows]
