#!/usr/bin/env python3
"""重复清理：一件作品只留一份正文。

判重口径见 docs/重复体检.md（正文 t2s 归一、去非汉字、同 16 字）。那份报告只报告，
这个脚本处理其中**能自动定案**的几类，其余（归属异说、组诗拆条、异文）不动：

  songci_merge   宋词分两批抓取：`ci.song.22000.json` 与其余 ci.song.*（0–21000）是同一批词
                 各自来源的录文。旧批该有的 title 多半是 None，断句也逐句一行；
                 新批整首一行、带真正的 title。两者前面 16 字相同即为同一首：
                   - 新批正文是旧批正文的前缀（或相等）→ 删新批那条（旧批更全）
                   - 断句不同而正文一字不差的 → 删新批那条（新批丢分句信息）
                   - 正文有出入 → 两条都留（异文），只记账
  yuanqu_cover   元曲一条短句是另一条的开头（同一支曲的残句 / 只录了第一支）：
                   - 同作者 → 删短句
                   - 异作者 → 两条都留，短句挂 tags 互见（沿用《全唐诗》「一作某」的办法）
  sanguo_dup     三国/诗/poet.sanguo.json 里简繁各录了一遍（曹植《白马篇》与《白馬篇》）：
                   - 同题同作者、正文 t2s 后相同 → 删没有 tags 的那条
  kongzi_subset  汇编/课本选目、汇编/古文观止 里「一条正文是另一条的真子集」的选段：
                   - 同题同作者 → 删短的那条（选段是长篇的摘录）
                   - 异题/异作者 → 只记账（蒙学经典里三字经摘段、揠苗/拔苗两种题名）
  qingci_attr    清/词/ci.qing.json 里纳兰性德名下的一条与佟世南同词重出（误归）：
                   - 正文 t2s 后相同 → 删纳兰名下那条（纳兰词集中无此词）

用法：
  python3 scripts/dedupe_duplicates.py                 # 预演，打印逐类明细
  python3 scripts/dedupe_duplicates.py --apply         # 写回数据 + docs/重复清理.tsv
"""
import argparse
import csv
import json
import os
import re
import sys
from datetime import date

from opencc import OpenCC

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import progress as pg  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
T2S = OpenCC('t2s')
HAN = re.compile(r'[^\u4e00-\u9fff]')
REVIEWER = 'codebuddy'
# 一行 JSON：缩进 + 可选 `"键": ` + 值 + 可选逗号。值是字符串、`[`、`{`、`}`、`]` 之一
LINE = re.compile(r'(?m)^( *)(?:"(?:[^"\\]|\\.)*": )?("(?:[^"\\]|\\.)*"|[\[\]{}])(,?)$')
LINEQ = re.compile(r'^( *)(?:[^:\n]*: )?(?P<v>"(?:[^"\\]|\\.)*"|[\[\]{}])(,?)$')


def load(rel):
    with open(os.path.join(ROOT, rel), encoding='utf-8') as fp:
        return json.load(fp)


def dump(rel, data):
    """按原文件的排版写回，只让「删掉的那几条」出现在 diff 里。

    这批数据文件的缩进是 `json.dump(indent=2)` 的产物，行尾却有两种：ci.song.22000/23000
    两张干净，其余每个值后面多一个空格，个别行（0 号那批的容器开行）又不带。
    逐行照原文件的行尾空格搬一遍，比归纳排版规则可靠。
    """
    path = os.path.join(ROOT, rel)
    raw = open(path, encoding='utf-8').read()
    m = re.search(r'\n( +)\S', raw)
    indent = len(m.group(1)) if m else 2
    out = json.dumps(data, ensure_ascii=False, indent=indent) + ('\n' if raw.endswith('\n') else '')
    src = raw.split('\n')
    out = '\n'.join(r + (' ' if i < len(src) - 1 and src[i].endswith(' ') else '')
                    for i, r in enumerate(out.split('\n')))
    with open(path, 'w', encoding='utf-8') as fp:
        fp.write(out)


def hanzi(s):
    return HAN.sub('', T2S.convert(s or ''))


def body(rec):
    for k in ('paragraphs', 'para', 'content'):
        v = rec.get(k)
        if isinstance(v, str):
            return hanzi(v)
        if isinstance(v, list) and all(isinstance(x, str) for x in v):
            return hanzi(''.join(v))
    return ''


def title(rec):
    for k in ('title', 'rhythmic', 'chapter'):
        if rec.get(k):
            return T2S.convert(str(rec[k]))
    return ''


def author(rec):
    return T2S.convert((rec.get('author') or '').strip())


def same_poem(a, b, max_ratio=0.03, max_shift=0):
    """篇幅相同（或相差不超过 max_shift 字）、逐字比只有极少数不同 → (True, 不同字数)。"""
    if abs(len(a) - len(b)) > max_shift or not a:
        return False, 0
    if len(a) != len(b):
        return True, abs(len(a) - len(b))
    diff = sum(1 for x, y in zip(a, b) if x != y)
    return diff <= max(1, int(len(a) * max_ratio)), diff


def fuzzy(s):
    """更松的归一：再抹掉一切非「汉字 + 异体字区」的字符。

    《三国/诗》里那条繁体抄本用「遊／並」等异体，t2s 转不掉，去掉标点后仍与简体本
    差着几个字；判「是不是同一首」时这点差别不该算数，所以再剔一遍非基本区字符。
    """
    return ''.join(ch for ch in T2S.convert(s or '') if '\u3400' <= ch <= '\u4dbf'
                   or '\u4e00' <= ch <= '\u9fff' or '\uf900' <= ch <= '\ufaff')


# ---------------------------------------------------------------- songci_merge

SONGCI_NEW = '宋/宋词/ci.song.22000.json'


def songci_merge():
    rels = [f'宋/宋词/{f}' for f in sorted(os.listdir(os.path.join(ROOT, '宋/宋词')))
            if re.fullmatch(r'ci\.song\..*\.json', f)]
    data = {rel: load(rel) for rel in rels}
    index = {}
    for rel in rels:
        if rel == SONGCI_NEW:
            continue
        for i, rec in enumerate(data[rel]):
            b = body(rec)
            if len(b) >= 16:
                index.setdefault(b[:16], []).append((rel, i))
    drop, evidence = set(), []
    for j, rec in enumerate(data[SONGCI_NEW]):
        b = body(rec)
        cands = index.get(b[:16], []) if len(b) >= 16 else []
        if not cands:
            continue
        rel, i = cands[0]
        old = body(data[rel][i])
        if old.startswith(b):
            drop.add((SONGCI_NEW, j))
            evidence.append(dict(path=SONGCI_NEW, idx=j, keep=f'{rel}#{i}', kind='songci_merge',
                                 title=title(rec), note='新批正文是旧批的前缀（旧批更全）'))
        elif b == old:
            drop.add((SONGCI_NEW, j))
            evidence.append(dict(path=SONGCI_NEW, idx=j, keep=f'{rel}#{i}', kind='songci_merge',
                                 title=title(rec), note='正文相同，旧批保留分句'))
    return data, drop, evidence


# ---------------------------------------------------------------- yuanqu_cover

YUANQU = '元/元曲/yuanqu.json'


def yuanqu_cover():
    """一条正文是另一条正文的前缀 —— 但「前缀」本身不是证据。

    2026-10 那版一见「短句是长句的开头」就删，误删了一大批完整作品：雅词与散曲同用
    《折桂令》《人月圆》《一枝花》的起句（张可久《折桂令·九日》与姚燧《凭阑人》都从
    「对青山」起），同题组曲的第一支单列一条（白朴《大德歌·春》之于《大德歌四首》）。
    现在只有同时满足下面两条才删：

      1. 长句本身不止这一支曲：正文里出现套数标记 `【曲牌】`，或是一条标了「套数」的组曲；
      2. 短句的题名也是同一支曲的题名（去掉标点后包含短句题名，或相反）。

    异作者一条都不动：同一支曲被元明人选进不同书里署了两个人的名，是归属异说，
    与《全唐诗》一样两存，不再拿「一作某人」去挂长句。
    """
    data = load(YUANQU)
    bodies = [body(r) for r in data]
    index = {}
    for i, b in enumerate(bodies):
        if len(b) >= 16:
            index.setdefault(b[:16], []).append(i)
    drop, evidence = set(), []
    for i, b in enumerate(bodies):
        if len(b) < 20:
            continue
        for j in index.get(b[:16], []):
            if i == j or len(bodies[j]) <= len(b) or not bodies[j].startswith(b):
                continue
            rec, keep = data[i], data[j]
            if author(rec) != author(keep) or not suite(data[j]) or not same_title(rec, keep):
                evidence.append(dict(path=YUANQU, idx=i, keep=f'{YUANQU}#{j}', kind='yuanqu_cover_open',
                                     title=title(rec),
                                     note=f'前缀重合但不构成重出（长句 {n_han(bodies[j])} 字 / 短句 {n_han(b)} 字，'
                                          f'{"异作者" if author(rec) != author(keep) else "同作者"}），两条都留'))
                continue
            drop.add(i)
            evidence.append(dict(path=YUANQU, idx=i, keep=f'{YUANQU}#{j}', kind='yuanqu_cover',
                                 title=title(rec),
                                 note=f'同作者套数已含此支（{n_han(b)} 字 vs {n_han(bodies[j])} 字）'))
    return data, drop, evidence


def suite(rec):
    """套数（一支曲不止首句那一段）：正文里有【曲牌】，或题名标了「套数」。"""
    text = ''.join(rec.get('paragraphs') or [])
    return '【' in text or '套数' in title(rec)


def same_title(a, b):
    """两支曲的题名是否同一题：去标点后一个包含另一个，且短的那个够长（≥4 字）。"""
    ta, tb = title(a).replace('・', '·'), title(b).replace('・', '·')
    if not ta or not tb:
        return False
    short, long_ = sorted((ta, tb), key=len)
    return len(short) >= 4 and short in long_


def n_han(s):
    return len(s)


# ---------------------------------------------------------------- sanguo_dup

SANGUO = '三国/诗/poet.sanguo.json'


def sanguo_dup():
    """简繁两次转录同录一首：等长、只差异体字与缺字 → 留正文完整的那条。

    原先按「有没有 tags」取舍，结果留下了带 `唐诗三百首` 标签的繁体本，而它把
    「借問誰家子」后的问号作缺字（`□`）、全篇句末句读一概没有，正文反而更差。
    现在按正文质量取：`□` 少、标点齐的优先，tags 只作末位参考。
    """
    data = load(SANGUO)
    groups = {}
    for i, rec in enumerate(data):
        b = fuzzy(''.join(rec.get('paragraphs') or []))
        if len(b) >= 16:
            groups.setdefault(b[:16], []).append(i)
    drop, evidence = set(), []
    for k, idxs in groups.items():
        if len(idxs) < 2:
            continue
        def quality(i):
            text = ''.join(data[i].get('paragraphs') or [])
            return (text.count('□'), -sum(c in '，。？！' for c in text), text.count('，'))
        idxs = sorted(idxs, key=lambda i: (quality(i), not data[i].get('tags'), -i))
        keep = idxs[0]
        keep_body = fuzzy(''.join(data[keep].get('paragraphs') or []))
        for i in idxs[1:]:
            # 同一首的两种转录：长度相同、只差个别字（凌／陵、□ 与「，」这类）即算重出
            same, diff = same_poem(keep_body, fuzzy(''.join(data[i].get('paragraphs') or [])), max_shift=2)
            if not same:
                continue
            drop.add(i)
            evidence.append(dict(path=SANGUO, idx=i, keep=f'{SANGUO}#{keep}', kind='sanguo_dup',
                                 title=title(data[i]),
                                 note=f'简繁两种转录同录一首（{diff} 字之差：异体与缺字），'
                                      f'留正文完整、标点齐的一条'))
    return data, drop, evidence


# ---------------------------------------------------------------- kongzi_subset

KONGZI = ['汇编/课本选目/寓言故事.json', '汇编/课本选目/蒙学经典.json']
GUWEN = '汇编/古文观止/古文观止·补.json'
GUWEN_VOL = re.compile(r'汇编/古文观止/卷.*\.json')


def kongzi_subset():
    data = {rel: load(rel) for rel in KONGZI}
    drop, evidence = set(), []
    for rel in KONGZI:
        recs = data[rel]
        for i, rec in enumerate(recs):
            b = body(rec)
            if len(b) < 16:
                continue
            for j, other in enumerate(recs):
                ob = body(other)
                if i == j or len(ob) <= len(b) or not ob.startswith(b):
                    continue
                if title(rec) != title(other) or author(rec) != author(other):
                    evidence.append(dict(path=rel, idx=i, keep=f'{rel}#{j}', kind='kongzi_subset_open',
                                         title=title(rec), note='同文异题/异作者，两条都留，待人工判'))
                    break
                drop.add((rel, i))
                evidence.append(dict(path=rel, idx=i, keep=f'{rel}#{j}', kind='kongzi_subset',
                                     title=title(rec), note='选段，长篇已另收'))
                break
    return data, drop, evidence


def guwen_subset():
    """《古文观止·补》里正文被卷*收全的那几条（补是后补的散篇，与分卷重出）。"""
    data = load(GUWEN)
    vols = []
    for f in sorted(os.listdir(os.path.join(ROOT, '汇编/古文观止'))):
        if GUWEN_VOL.fullmatch(f'汇编/古文观止/{f}'):
            for i, rec in enumerate(load(f'汇编/古文观止/{f}')):
                vols.append((f, i, rec))
    drop, evidence = set(), []
    for i, rec in enumerate(data):
        b = body(rec)
        if len(b) < 16:
            continue
        for f, j, other in vols:
            if body(other).startswith(b):
                drop.add(i)
                evidence.append(dict(path=GUWEN, idx=i, keep=f'汇编/古文观止/{f}#{j}', kind='guwen_subset',
                                     title=title(rec), note='同篇，分卷本更全'))
                break
    return data, drop, evidence


# ---------------------------------------------------------------- qingci_attr

QINGCI = '清/词/ci.qing.json'


def qingci_attr():
    data = load(QINGCI)
    groups = {}
    for i, rec in enumerate(data):
        b = body(rec)
        if len(b) >= 16:
            groups.setdefault(b[:16], []).append(i)
    drop, evidence = set(), []
    for k, idxs in groups.items():
        if len(idxs) < 2:
            continue
        nalan = [i for i in idxs if '纳兰' in author(data[i])]
        others = [i for i in idxs if '纳兰' not in author(data[i])]
        if not nalan or not others:
            continue
        keep = others[0]
        # 只差一字（「知人肠断时」/「知君肠断时」）也是同一首的两种转录
        same, _ = same_poem(body(data[keep]), body(data[nalan[0]]))
        if not same:
            continue
        for i in nalan:
            drop.add(i)
            evidence.append(dict(path=QINGCI, idx=i, keep=f'{QINGCI}#{keep}', kind='qingci_attr',
                                 title=title(data[i]),
                                 note=f'与{author(data[keep])}同词重出，纳兰词集不载，判为误归'))
    return data, drop, evidence


# ---------------------------------------------------------------- songci_diff

def songci_diff(work):
    """两批录文里等长、只差个别字的那几组：逐处判「哪一份抄错了」。

    宋词的两批（`ci.song.22000.json` 与其余各卷）是同一批词的两个来源，不是「一首词存两处」，
    所以判据要反过来：拿旧批那一份去识典古籍检索，看古籍里有没有「与旧批等长、只差这一处」
    的读法 —— 有，两读都是异文；没有，也判不了，因为新批的读法同样可能传世。

    这里只做核对并记账，不改正文：505 组里一处也找不到独立证据（2026-10-28 查过 932 条检索），
    结论是两存，交给 `宋词全库对勘`。
    """
    import collections
    import difflib
    import glob

    try:
        from opencc import OpenCC
        s2t = OpenCC('s2t')
    except ImportError:
        sys.exit('需要 OpenCC：pip install opencc-python-reimplemented')
    res_path = os.path.join(work, 'results.jsonl')
    if not os.path.exists(res_path):
        sys.exit(f'{res_path} 不存在：先用 scripts/shidian/search.mjs 检索')
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import shidian as sd

    res = {}
    for line in open(res_path, encoding='utf-8'):
        r = json.loads(line)
        if sd.RESULT_MARKER in (r.get('text') or '') and not r.get('err'):
            res[r['q']] = r['text']
    by_len = collections.defaultdict(list)
    for text in res.values():
        for raw, norm, book, src in sd.snippets(text):
            by_len[len(norm)].append((norm, book, src))
    print(f'检索 {len(res)} 条，整理出 {sum(map(len, by_len.values()))} 条等长片段', file=sys.stderr)

    rels = [f'宋/宋词/{f}' for f in sorted(os.listdir(os.path.join(ROOT, '宋/宋词')))
            if re.fullmatch(r'ci\.song\..*\.json', f)]
    data = {rel: load(rel) for rel in rels}
    new = data[SONGCI_NEW]
    index = {}
    for rel in rels:
        if rel == SONGCI_NEW:
            continue
        for i, rec in enumerate(data[rel]):
            b = body(rec)
            if len(b) >= 16:
                index.setdefault(b[:16], []).append((rel, i))

    rows, stat = [], collections.Counter()
    for j, rec in enumerate(new):
        b = body(rec)
        cands = index.get(b[:16], []) if len(b) >= 16 else []
        if not cands:
            continue
        rel, i = cands[0]
        old = body(data[rel][i])
        stat['pairs'] += 1
        if len(old) != len(b):
            stat['unequal'] += 1
            continue
        stat['equal'] += 1
        diffs = [k for k in range(len(old)) if old[k] != b[k]]
        if not diffs:
            stat['identical'] += 1
            continue
        ev = {}
        for norm, book, src in by_len[len(old)]:
            d = [k for k in range(len(old)) if old[k] != norm[k]]
            if len(d) == 1 and d[0] in diffs:
                ev.setdefault(d[0], collections.Counter())[f'{old[d[0]]}→{norm[d[0]]}'] += 1
        if ev:
            stat['with_evidence'] += 1
        rows.append(dict(new_idx=j, author=author(rec), rhythmic=title(rec),
                         old=f'{rel}#{i}', diffs=''.join(f'{old[k]}→{b[k]}@' for k in diffs),
                         evidence='; '.join(f'{old[p]}→{c}' for p, cnt in ev.items() for c in cnt)))
    with open(os.path.join(ROOT, 'docs/宋词两批异文.tsv'), 'w', encoding='utf-8', newline='') as fp:
        w = csv.DictWriter(fp, delimiter='\t', lineterminator='\n',
                           fieldnames=['new_idx', 'author', 'rhythmic', 'old', 'diffs', 'evidence'])
        w.writeheader()
        w.writerows(rows)
    print(json.dumps(dict(stat), ensure_ascii=False))
    print(f'明细写入 docs/宋词两批异文.tsv（{len(rows)} 行；evidence 空 = 古籍里找不到只差这一处的读法）')


# ---------------------------------------------------------------- main

def apply_drop(data, drop):
    """{rel: [records]} → 就地删掉 drop 里的下标，返回每个文件的新数组。"""
    for rel, recs in data.items():
        idxs = {i for r, i in drop if r == rel}
        if idxs:
            data[rel] = [r for i, r in enumerate(recs) if i not in idxs]
    return data


# ---------------------------------------------------------------- small_scope

# 全库扫下来剩下的几处，逐条核过、能定案：
SMALL = [
    # 袁荣法同一首词在 ci.dang.json 里录了两遍（正文、题名、词牌全同）
    ('当/ci.dang.json', 49, None, '同首重出，删后一条'),
    # 《百家姓》在汇编/蒙学 与 课本选目 各一份，正文全同
    ('汇编/课本选目/蒙学经典.json', 2, None, '与 汇编/蒙学/baijiaxing.json 重出的那条已删，这里只剩校验'),
    # 《古文观止·补》后补的篇与分卷重出的四条已删，这里只剩校验
]


# ---------------------------------------------------------------- tang_residual

# 《全唐诗》2026-10 那一轮内部去重之后，还剩 22 组「同作者」。逐组看过：绝大多数是异文，
# 或「缺字重录本」（后一条题名尾巴上写着「按全唐詩卷X收此詩缺N字今重錄」，正文更全），两存；
# 只有下一条同时满足「两组同题」且「正文只差通用的异体 / 正俗字」：
TANG_REL = [
    ('唐/诗/全唐诗/poet.tang.1000.json', 9, ('唐/诗/全唐诗/poet.tang.37000.json', 249),
     '銙/胯、却/著（着）皆通用，《樂府詩集》两种刻本各作一读；两条同题同作者，留一条'),
]


def tang_residual():
    out, drop, evidence = {}, set(), []
    for rel, i, (rel2, j), note in TANG_REL:
        for r in (rel, rel2):
            if r not in out:
                out[r] = load(r)
        rec = out[rel][i]
        drop.add((rel, i))
        evidence.append(dict(path=rel, idx=i, keep=f'{rel2}#{j}', kind='tang_residual',
                             title=title(rec), note=note))
    return out, drop, evidence


# 每条的正文首句（校验用）：重跑时下标漂移就报错，不会删错记录
SMALL_HEAD = {
    ('当/ci.dang.json', 49): '今古事。思量大抵如此。',
    ('汇编/课本选目/蒙学经典.json', 2): '天地玄黃，宇宙洪荒。',
    ('汇编/古文观止/古文观止·补.json', 5): '齊桓晉文之事',
}


def small_scope():
    out, drop, evidence = {}, set(), []
    for rel, i, keep, note in SMALL:
        if rel not in out:
            out[rel] = load(rel)
        rec = out[rel][i]
        head = SMALL_HEAD.get((rel, i))
        if head and head not in ''.join(rec.get('paragraphs') or '')[:40]:
            raise SystemExit(f'{rel}#{i} 已不是「{head}」，下标漂移，先核对再跑')
        drop.add((rel, i))
        evidence.append(dict(path=rel, idx=i, keep=f'{rel}#{keep}' if keep is not None else '',
                             kind='small_scope', title=title(rec), note=note))
    return out, drop, evidence


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('action', nargs='?', default='dedupe', choices=['dedupe', 'songci-diff'])
    ap.add_argument('--work', help='songci-diff：检索工作目录（含 results.jsonl）')
    ap.add_argument('--apply', action='store_true')
    ap.add_argument('--out', default='docs/重复清理.tsv')
    args = ap.parse_args()

    if args.action == 'songci-diff':
        if not args.work:
            ap.error('songci-diff 需要 --work')
        songci_diff(os.path.expanduser(args.work))
        return

    evidence = []

    # 宋词：新批文件整体按条删
    songci, drop, ev = songci_merge()
    evidence += ev
    for rel, recs in songci.items():
        idxs = {i for r, i in drop if r == rel}
        if idxs:
            songci[rel] = [r for i, r in enumerate(recs) if i not in idxs]

    yuan, ydrop, ev = yuanqu_cover()
    evidence += ev
    yuan = [r for i, r in enumerate(yuan) if i not in ydrop]

    sanguo, sdrop, ev = sanguo_dup()
    evidence += ev
    sanguo = [r for i, r in enumerate(sanguo) if i not in sdrop]

    kong, kdrop, ev = kongzi_subset()
    evidence += ev
    for rel, recs in kong.items():
        idxs = {i for r, i in kdrop if r == rel}
        kong[rel] = [r for i, r in enumerate(recs) if i not in idxs]

    guwen, gdrop, ev = guwen_subset()
    evidence += ev
    guwen = [r for i, r in enumerate(guwen) if i not in gdrop]

    tang, tdrop, ev = tang_residual()
    evidence += ev
    for rel, recs in tang.items():
        idxs = {i for r, i in tdrop if r == rel}
        tang[rel] = [r for i, r in enumerate(recs) if i not in idxs]

    small, mdrop, ev = small_scope()
    evidence += ev
    for rel, recs in small.items():
        idxs = {i for r, i in mdrop if r == rel}
        small[rel] = [r for i, r in enumerate(recs) if i not in idxs]

    qing, qdrop, ev = qingci_attr()
    evidence += ev
    qing = [r for i, r in enumerate(qing) if i not in qdrop]

    by_kind = {}
    for e in evidence:
        by_kind.setdefault(e['kind'], []).append(e)
    print('== 重复清理预演')
    for kind, items in sorted(by_kind.items()):
        print(f'   {kind}: {len(items)}')
    total_drop = sum(len(v) for k, v in by_kind.items() if not k.endswith('open'))
    print(f'   共删记录 {total_drop} 条，待人工判 {sum(len(v) for k, v in by_kind.items() if k.endswith("open"))} 条')

    if not args.apply:
        for kind in ('songci_merge', 'yuanqu_cover', 'sanguo_dup', 'kongzi_subset', 'guwen_subset', 'qingci_attr', 'tang_residual', 'small_scope'):
            print(f'\n-- {kind}')
            for e in by_kind.get(kind, [])[:200]:
                print(f"   {e['path']}#{e['idx']} {e['title'][:20]} → 留 {e['keep']}（{e['note']}）")
        print('\n（预演，未改动任何文件；加 --apply 落盘）')
        return

    for rel, recs in songci.items():
        dump(rel, recs)
    dump(YUANQU, yuan)
    dump(SANGUO, sanguo)
    for rel, recs in kong.items():
        dump(rel, recs)
    dump(GUWEN, guwen)
    for rel, recs in tang.items():
        dump(rel, recs)
    for rel, recs in small.items():
        dump(rel, recs)
    dump(QINGCI, qing)

    with open(os.path.join(ROOT, args.out), 'w', encoding='utf-8', newline='') as fp:
        w = csv.writer(fp, delimiter='\t', lineterminator='\n')
        w.writerow(['类别', '文件', '下标', '题名', '保留', '说明'])
        for e in evidence:
            w.writerow([e['kind'], e['path'], e['idx'], e['title'], e['keep'], e['note']])
    print(f'明细写入 {args.out}')

    # 进度记录：每个被删过记录的文件各记一条
    today = date.today().isoformat()
    fixes_by_file = {}
    for e in evidence:
        if e['kind'].endswith('open'):
            continue
        fixes_by_file.setdefault(e['path'], []).append(dict(
            original=f"# {e['idx']} {e['title'][:24]}", corrected=None,
            note=f"[{e['kind']}] 删此条，正文与 {e['keep']} 重出：{e['note']}"))
    for rel, fixes in fixes_by_file.items():
        rec = pg.merge(rel, dict(fixes=fixes, date=today, reviewer=REVIEWER))
        rec['note'] = ((rec.get('note') or '').rstrip() +
                       f' {today} 重复清理：{len(fixes)} 条记录涉及同正文重出（删重复 / 挂 tags 互见），'
                       f'逐条见 docs/重复清理.tsv。').strip()
        # 只记删掉了哪几条，不代表这一文件已逐字对勘，状态不动
        pg.write_record(rel, pg.ordered(rec))
    pg.write_index()
    print(f'进度记录 {len(fixes_by_file)} 个文件')


if __name__ == '__main__':
    main()
