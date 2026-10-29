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
  yuanqu_cover   元曲同一支曲被录了两遍：一条短、一条长，短的接在长的开头。
                 长短两录都是同一支曲，只是长的多录了后面的曲子（套数与组曲）：
                   - 同作者 → 删短的那条（留正文全的）
                   - 异作者 → 两条都留（归属异说），只记账
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
        # 空表也算（all(...) 对空表恒真），否则会被当成「没有正文字段」跳过
        if isinstance(v, list) and all(isinstance(x, str) for x in v):
            return hanzi(''.join(v))
    return ''


def title(rec):
    for k in ('title', 'rhythmic', 'chapter'):
        if rec.get(k):
            return T2S.convert(str(rec[k]))
    return ''


def author(rec):
    """作者的正文用「作者表里的写法」比：元曲里 `王實甫／王德信`、`朱帘秀／珠帘秀`、
    `真氏／真真` 是一人两种署名，写作不同但指的是同一个人。"""
    a = T2S.convert((rec.get('author') or '').strip())
    return {k: v[0] for k, v in ALIAS.items()}.get(a, a)


ALIAS = {  # 别名 → (正名, 依据)
    '王德信': ('王实甫', '《录鬼簿》王实甫名德信'),
    '朱帘秀': ('珠帘秀', '《青楼集》作珠帘秀，朱/珠异写'),
    '真真': ('真氏', '《南村辍耕录》作真氏'),
}


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


def songci_merge(verdicts=None):
    verdicts = verdicts or {}
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
        else:
            key = songci_key(rec)
            what = verdicts.get(key)
            if what == 'new_err':
                drop.add((SONGCI_NEW, j))
                evidence.append(dict(path=SONGCI_NEW, idx=j, keep=f'{rel}#{i}', kind='songci_merge',
                                     title=title(rec),
                                     note='新批那一读古籍无、旧批有；删新批'))
            elif what in ('review', 'keep_new'):
                evidence.append(dict(path=SONGCI_NEW, idx=j, keep=f'{rel}#{i}', kind='songci_variant_open',
                                     title=title(rec),
                                     note=(SONGCI_REVIEW.get(key) or '新批读法有古籍支持') + '；异文两存，两条都留'))
            else:
                evidence.append(dict(path=SONGCI_NEW, idx=j, keep=f'{rel}#{i}', kind='songci_variant_open',
                                     title=title(rec),
                                     note='一字之差，未在识典古籍里核实到只差这一处的读法；两存待核'))
    return data, drop, evidence


# ---------------------------------------------------------------- songshi_dup

SONGSHI = '宋/诗/全宋诗'
# 宋太宗《御製緣識》《御製逍遙咏》是一题多首的组诗，两书互有重出：
# 同一首既收在《逍遥詠 其N》又收在《緣識 其M》，题名不同，`check_tree.py` 把它记成
# 「同作者」的正文重复。识典古籍两处（高丽藏本《御製緣識》、思溪藏本《禦製緣識》）逐字核过，
# 下列各组的差异都是古书里就有的异体（姸/妍、淸/清、撗/横、傅/传、攺/改……）或明显的
# 抄刻讹字（夫失、至石、增境、闻问、后复、语诘），两批其实同一首 → 删《緣識》那一条。
#
# 两侧其实不同、或古书只证了其中一条的，一律两存，不在这里列。
SONGSHI_REL = [
    (545, 730, '遍/徧'), (553, 754, ''), (568, 736, ''), (577, 745, ''),
    (592, 748, '复/后'), (646, 774, '失/夫 石/至 境/增 问/闻 攺/改'),
    (648, 775, ''), (676, 783, ''), (680, 785, ''), (690, 793, '诘/语'),
    (697, 797, ''), (706, 801, ''),
]


def songshi_dup():
    """《全宋诗》宋太宗《逍遥詠》与《緣識》的重出，逐条见 SONGSHI_REL。"""
    rel = f'{SONGSHI}/poet.song.1000.json'
    data = load(rel)
    drop, evidence = set(), []
    for keep, dup, note in SONGSHI_REL:
        rec, kept = data[dup], data[keep]
        drop.add((rel, dup))
        evidence.append(dict(path=rel, idx=dup, keep=f'{rel}#{keep}', kind='songshi_dup',
                             title=title(rec),
                             note=f'与《{title(kept) or key(kept)}》同首（{note or "正文全同"}），'
                                  f'异体 / 讹字按古籍改订；删重复的那条'))
    return {rel: data}, drop, evidence


# ---------------------------------------------------------------- songci_evidence

SONGCI_TSV = 'docs/宋词两批异文.tsv'
# 两批互见就一定是异文吗？不是。cid 那一轮核出 505 组「等长、只差通用字」之后，剩下的
# 一字之差有相当一部分新批是讹字，旧批的读法在古籍里能找到、新批的找不到：
# 《东坡乐府》作「记得歌时」、新批作「公子佳人」；《稼轩词》作「玉纤横笛」、新批作「横管」。
# 所以逐条回检：判断依据是同一句里新旧两读在古籍中的出现情况。
#
#   两读都有古籍 → 异文，两存
#   只有新批有   → 旧批那一读是讹字（或异体），两存，记 keep_new
#   只有旧批有   → 新批是讹字，删新批那条
#   都没有       → needs_review
#
# 证据来自识典古籍逐句检索（`scripts/shidian/search.mjs`，用旧批正文前 10 字当检索词）。
# 因此 `--apply` 需要 `--work <结果目录>`：没有证据时只做「新批是旧批前缀 / 正文全同」
# 这两类无争议的删除（那两类不需要古籍）。
#
# 这个函数把上一轮的判定写进 SONGCI_TSV，apply 时读回，检索不必重跑。
SONGCI_REVIEW = {
    # 两读都有古籍支持（异文），逐条在 TSV 的 evidence 列写明出处
    '陈亚《药名闺情》': '两读并存：《花草稡編》《詞綜》作檀郎，《御選歷代詩餘》作檳榔',
    '苏轼《寄鄂州朱使君寿昌》': '两读并存：《東坡樂府》作雲浪，《御選歷代詩餘》作雪浪',
    '苏轼《杭州交代，林子中席上作》': '两读并存：《東坡樂府》《彊村叢書》作與，《嘉定鎮江志》作對',
    '苏轼《黄州腊八日，饮怀民小阁》': '两读并存：新批「彩鸾」可从（綵鸞，8 种古籍），「同驾」「闲驾」两读俱见',
    '苏轼《为杭守陈述古作》': '两读并存：「且徘徊」与「更徘徊」古籍俱见',
    '苏轼《西湖食荔支》': '两读并存：新批「似」可从',
    '苏轼《玉肌铅粉傲秋霜》': '异体字：秕/粃',
    '辛弃疾《带湖新居将成》': '异体字：鲙/脍',
    '辛弃疾《舟次扬州，和杨济翁、周显先韵》': '两读并存：《稼軒長短句》作高樓，《稼軒詞》作層樓',
    '辛弃疾《赠妓》': '两读并存：「妆晃了巴巴」与「妆晃子巴巴」古籍俱见',
    '辛弃疾《晋臣敷文张灯甚盛，索赋。偶忆旧游，未章因及之》': '异体（鳌/鼇）；新批「金莲」可从',
    '辛弃疾《春兴》': '两读并存：烂熳/烂漫',
    '吴文英《其四·寿毛荷塘》': '未检得：豪/毫',
    '陈允平《西湖十咏·雷峰落照》': '未检得：溯/逆、瞑/暝',
    '刘辰翁《和巽吾相忆寄韵》': '未检得：坠/堕',
    '蒋捷《舟过吴江》': '两读并存：《竹山詞》作度與嬌，《花草稡編》作渡與橋',
    '黄庭坚《游览》': '两读并存：《山谷琴趣》作桃花，《古今圖書集成》作桃枝',
    '乐婉《答施》': '两读并存：肠/断互倒，古籍两读',
    '秦观《碧桃天上栽和露》': '两读并存：回/洄',
    '张继先《其二》': '异体字：柰/奈',
}
# 新批那一读在古籍里一概找不到、旧批找得到的：删新批
SONGCI_NEW_ERR = [
    '苏轼《孤山竹阁送述古》', '苏轼《回文冬闺怨》', '苏轼《离京口作》',
    '李之仪《其五·和人》', '辛弃疾《中秋寄远》',
    '辛弃疾《送徐抚幹衡仲之官三山，时马叔会侍郎帅闽》',
    '吴潜《寒梢砌玉》', '文天祥《和友驿中言别》',
    '周邦彦《中山县圃姑射亭避暑作》', '李清照《庭院深深深几许》', '李清照《大鲜明》',
]


def songci_key(rec):
    return f"{author(rec)}《{title(rec) or '—'}》"


def songci_evidence(work=None):
    """上一轮逐句核过的结论：{('new_err'|'keep_new', 新批文件, 下标)}。

    有 `--work` 时先按该目录里的检索结果重算一遍，再并上人工复核过的清单。
    """
    verdicts = {}
    for key in SONGCI_NEW_ERR:
        verdicts[key] = 'new_err'
    for key in SONGCI_REVIEW:
        verdicts.setdefault(key, 'review')
    if not work:
        return verdicts
    tsv = os.path.join(ROOT, SONGCI_TSV)
    if not os.path.exists(tsv):
        return verdicts
    with open(tsv, encoding='utf-8') as fp:
        for row in csv.DictReader(fp, delimiter='\t'):
            if row.get('verdict'):
                verdicts.setdefault(f"{row['author']}《{row['title'] or '—'}》", row['verdict'])
    return verdicts


# ---------------------------------------------------------------- yuanqu_cover

YUANQU = '元/元曲/yuanqu.json'

def yuanqu_cover():
    """同一支曲被录了两遍：长短两录，短的接在长的开头。

    「前缀」本身不是证据。2026-10 那版一见「短句是长句的开头」就删，误删了一大批
    完整作品：雅词与散曲同用《折桂令》《人月圆》《一枝花》的起句（张可久
    《折桂令·九日》与姚燧《凭阑人》都从「对青山」起）。

    现在只认「同一支曲、长短两录」，三条都要：

      1. 短的是长的开头，且短句每一句都按序在长句里（断句不同不算差别）；
      2. 题名是同一个 —— 书题逐字相同，或长句的书题是「短句书题 + 另一支曲的书题」
         串起来的（`湖上归` / `湖上晚归`、`庄家不识构阑` / `庄家不识勾栏`）；
      3. 长句比短句长三倍以上时，题名放宽到第 2 条的后半 —— 同题组曲的一支另立一条
         （《大德歌·春》之于《大德歌（四首）春》）正文差四倍，那是编法，不是重出。

    同曲牌而题名不同的是两支曲（马致远《四块玉·恬退》与《四块玉·叹世》起句相同），
    不在此列。同作者删短的、留长的；异作者两侧都留 —— 同一支曲署了两个人的名是归属异说。
    """
    data = load(YUANQU)
    bodies = [body(r) for r in data]
    index = {}
    for i, b in enumerate(bodies):
        if len(b) >= 16:
            index.setdefault(b[:16], []).append(i)
    drop, evidence = set(), []
    for i, b in enumerate(bodies):
        if len(b) < 16:
            continue
        for j in index.get(b[:16], []):
            # 短句得是长句的一份录文：只是前 16 字撞上，而中间另有一支曲（《卖花声》四首，
            # 短句录第一、四首），那就不是同一份录文，别人来核
            if i == j or len(bodies[j]) <= len(b) or not bodies[j].startswith(b):
                continue
            rec, keep = data[i], data[j]
            if not same_title(rec, keep) and not (
                    len(bodies[j]) > 3 * len(b) and same_title_pair(rec, keep, data)):
                evidence.append(dict(path=YUANQU, idx=i, keep=f'{YUANQU}#{j}', kind='yuanqu_cover_open',
                                     title=title(rec),
                                     note=f'同曲牌不同曲（{n_han(b)} 字 vs {n_han(bodies[j])} 字，'
                                          f'题名《{title(rec)}》≠《{title(keep)}》），两条都留'))
                continue
            if not span(bodies[j], b):
                continue
            if author(rec) != author(keep):
                evidence.append(dict(path=YUANQU, idx=i, keep=f'{YUANQU}#{j}', kind='yuanqu_cover_open',
                                     title=title(rec),
                                     note=f'同一支曲两录、署名不同（{author(rec)}／{author(keep)}），'
                                          f'归属异说两存（{n_han(b)} 字 vs {n_han(bodies[j])} 字）'))
                continue
            drop.add(i)
            evidence.append(dict(path=YUANQU, id=rec.get('id'), idx=i, keep=f'{YUANQU}#{j}',
                                 kind='yuanqu_cover', title=title(rec),
                                 note=f'同一支曲两录，留正文更全的一条（{n_han(b)} 字 vs {n_han(bodies[j])} 字）'))
            break
    return data, drop, evidence



def suite(rec):
    """套数（不止一支曲）：正文里有【曲牌】，或题名标了「套数」。"""
    text = ''.join(rec.get('paragraphs') or [])
    return '【' in text or '套数' in title(rec)


TUNE = {'黄钟', '正宫', '中吕', '南吕', '仙吕', '双调', '越调', '商调', '大石调', '般涉调',
        '小石调', '商角调', '宫调', '黄钟宫', '黄钟调'}
# 曲牌（只收本库题名里出现过的），长的在前，免得「一枝花」把「一枝花平康」「一枝花湖上归」截断
TUNES = sorted({
    '一枝花', '十二月过尧民歌', '十二月', '尧民歌', '一封书', '人月圆', '凭栏人', '塞鸿秋',
    '大德歌', '天净沙', '寄生草', '小桃红', '山坡羊', '庆东原', '快活年', '折桂令', '挂玉钩',
    '普天乐', '朝天子', '殿前欢', '水仙子', '沉醉东风', '清江引', '满庭芳', '湘妃怨',
    '玄鹤鸣', '甘草子', '白头吟', '白鹤子', '耍孩儿', '解三酲', '青杏子', '醉扶归',
    '醉高歌过摊破喜春来', '醉高歌带摊破喜春来', '醉高歌', '摊破喜春来', '阳春曲',
    '雁儿落兼清江引', '雁儿落带青江引', '雁儿落', '青江引', '金络索挂梧桐', '金络索桂梧桐',
    '金络索', '挂梧桐', '桂梧桐', '金字经', '阅金经', '端正好', '滚绣球', '脱布衫',
    '红绣鞋', '红芍药', '石榴花', '落梅风', '寿阳春', '寿阳曲', '卖花声', '双雁儿',
    '朝元歌', '鹦鹉曲', '黑漆弩', '江南烟雨', '蟾宫曲', '柳营曲', '四块玉', '梧叶儿',
    '剔银灯', '驻马听', '步步娇', '得胜令', '水仙子', '寨儿令', '干荷叶', '风入松',
    '离亭宴煞', '离亭宴', '催拍子', '青哥儿', '后庭花', '煞尾', '黄蔷薇', '菜根谈',
}, key=len, reverse=True)
TUNE_SUFFIX = ('过', '带', '兼')


def tune_parts(rec):
    """把题名拆成 (曲牌集, 书题)：先按书名号与间隔号切，再逐字切，认得的曲牌留下，其余算书题。

    `南吕·一枝花·赠珠帘秀` → ({'南吕','一枝花'}, '赠珠帘秀')
    `南吕・一枝花赠珠帘秀`   → ({'南吕','一枝花'}, '赠珠帘秀')   曲子挤在一段里也认得
    `双调・大德歌（四首）春`  → ({'双调','大德歌'}, '春')
    `中吕・普天乐咏世`        → ({'中吕','普天乐'}, '咏世')
    认不出曲牌的段落都算书题。
    """
    t = title(rec).replace('・', '·')                 # U+30FB 与 U+00B7 两种间隔号
    t = t.replace('《', '·').replace('》', '·')
    t = re.sub(r'（[^）]*）|\([^)]*\)', '', t)
    tunes, story = set(), []
    for part in re.split(r'·+', t):
        part = part.strip()
        if not part:
            continue
        if part in TUNE:
            tunes.add(part)
            continue
        for name in TUNES:                            # 曲牌 + 书题挤在一段
            if name in part:
                tunes.add(name)
                part = part.replace(name, '', 1)
                break
        if part:
            story.append(part)
    return tunes, ''.join(story)


def same_title(a, b):
    """两录是不是同一支曲。

    两录都认得出曲牌的，比书题 —— `一枝花赠朱帘秀` 与 `一枝花·赠珠帘秀` 同一题；
    都没有书题时比曲牌，一方曲牌里含另一方（`醉高歌` 之于 `醉高歌过摊破喜春来`）也算。
    曲牌不同就是两支曲：《四块玉·恬退》与《四块玉·叹世》起句相同，不是一首。
    """
    ta, sa = tune_parts(a)
    tb, sb = tune_parts(b)
    if not ta or not tb:
        return hanzi(title(a)) == hanzi(title(b))
    if sa and sb:
        return sa == sb
    # 一方没写书题的（《鹦鹉曲》之于《正宫・鹦鹉曲》），比曲牌
    return bool(ta & tb)


def span(long, short):
    """短句是不是长句的「一份录文」：短句的每一句都在长句里按序出现。

    只是拿前 16 字找候选，长短两录的断句未必相同（短句把一支曲连写，长句一句一行），
    所以按句切开逐句往后找，全部找到才算。比的是去标点的正文：`歌《金缕》` 与
    `歌金缕` 是同一句。
    """
    l, pos = hanzi(long), 0
    for clause in filter(None, re.split(r'[。？！]', short)):
        k = l.find(hanzi(clause), pos)
        if k < 0:
            return False
        pos = k + len(hanzi(clause))
    return True


def same_title_pair(a, b, data):
    """书题有出入的两录也得能对上。

    长句的书题是「短句书题 + 另一支曲的书题」串起来的（`湖上归` + `晚归`、
    `庄家不识构阑` 与 `庄家不识勾栏` 只差两个字），另一半的书题在本库别处也作过书题。
    《一枝花赠朱帘秀》的 `赠朱帘秀` 之于《一枝花·赠珠帘秀》的 `赠珠帘秀` 本来就该对上，
    走的是 same_title 那条；连开头都对不上、或另半截查无实据的，两条都留。
    只对长句比短句长得多（三倍以上）时启用：同题组曲的一支另立一条（《大德歌·春》之于
    《大德歌四首 春》）题名一样、正文差四倍，那是编法，不是重出。
    """
    _, sa = tune_parts(a)
    _, sb = tune_parts(b)
    others = {tune_parts(x)[1] for x in data} - {sa, sb}
    for k in range(1, len(sb)):                     # 断在哪儿不定，每个位置都试
        if pairs(sa, sb[:k]) and any(pairs(sb[k:], o) for o in others):
            return True
    return False


def pairs(x, y):
    """两串的异文：同长的最多差两个字（`构阑`／`勾栏`）；不同长的，短的是长的开头、
    差的那截不超过两个字（`湖上归` 之于 `湖上晚归`）。"""
    if not x or not y:
        return False
    if len(x) == len(y):
        return sum(p != q for p, q in zip(x, y)) <= 2
    short, long_ = sorted((x, y), key=len)
    return len(long_) - len(short) <= 2 and sum(p != q for p, q in zip(short, long_)) <= 2


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
                                         title=title(rec),
                                         note='选题不同（摘一段当一课），'
                                              '与「选本并进总集」同例，两条都留'))
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


# ---------------------------------------------------------------- guwen_drop

# 《古文观止·补》里与分卷同篇的几条：分卷本把全篇收全了，补本这一份是删节 / 另一种读法。
# 与 guwen_subset 同一路线，但那一条判据是「补篇正文是分卷的前缀」，这里求的是「是子序列」——
# 补本中间删掉整句（《師說》缺「聖人之所以爲聖…吾未見其明也」、《論貴粟疏》缺末段）、
# 或分卷本自身有讹脱（《上書諫獵》「中路而後馳」丢了个「後」），只要补本每一段都还能在分卷里
# 逐字找回来，就是同一篇的两份录文。留分卷本（逐篇对过母本的正文），补本这一份删掉。
#
# 补本与分卷本差出来的字（异文与缺句）只记在 evidence 的说明里，不写进分卷本：
# 分卷本就是母本正文，两份录文的异文留给对勘，不在这一轮范围。
GWEN_DROP_LIST = [
    ('f775h3', '汇编/古文观止/卷八唐文.json', '24dg72',
     '補本每段都在分卷本里；分卷本多出「聖人之所以爲聖…吾未見其明也」与「李氏子蟠…作師說以貽之」两段'),
    ('e65e9f', '汇编/古文观止/卷六漢文.json', 'j7l5db',
     '補本每段都在分卷本里；分卷本多出末段「陛下幸使天下入粟塞下以拜爵…則民大富樂矣」，'
     '另有 亡/无、責/債、仟伯/阡陌、敖/遨、賦/虐 数处异文（分卷本「暑熱」误作「署熱」）'),
    ('hceflj', '汇编/古文观止/卷六漢文.json', 'b43871',
     '補本每段都在分卷本里；分卷本「中路而後馳」脱「後」字，'
     '另有 株/枝、乎蓬蒿馳乎丘墳/豐草騁丘虛 等异文'),
]


# 正俗 / 古今字：古书里两种写法都通行，不算异文。比对前抹平，写回时仍用数据集自己的字形
VARIANTS = str.maketrans({'亡': '无'})


def _flat(s):
    return s.translate(VARIANTS)


def guwen_drop():
    """补本与分卷同篇的几条：删补本，留分卷本。

    判据是「补本的每一段都还能在分卷本里找到对得上的那一段」：补本中间缺整句
    （《師說》缺两段、《論貴粟疏》缺末段）、或分卷本自己脱一个字（《上書諫獵》「中路而後馳」
    少了「後」、《論貴粟疏》「神農之教曰」少了「雖」），都不妨碍它是同一篇的另一份录文。
    正文一字不动，只删补本这一条。
    """
    data = {GUWEN: load(GUWEN)}
    drop, evidence = set(), []
    for rid, vol, vid, note in GWEN_DROP_LIST:
        sup = [i for i, r in enumerate(data[GUWEN]) if r.get('id') == rid]
        if not sup:                 # 已经删过
            continue
        i = sup[0]
        vols = load(vol)
        for k, r in enumerate(vols):
            if r.get('id') == vid:
                j = k
                break
        else:
            raise SystemExit(f'{vol} 找不到 id={vid}，先核对再跑')
        keep, gone = vols[j], data[GUWEN][i]
        kb = _flat(body(keep))
        for para in gone.get('paragraphs') or []:
            pb = _flat(hanzi(para))
            if not pb:
                continue
            # 这一段的头 16 字要能在分卷本里找到（个别字有出入、分卷本脱一个字都还在范围内：
            # 《上書諫獵》「中路而後馳」少了「後」，比对时按比它短的开头找）
            at = max(kb.find(pb[:n]) for n in (16, 12, 8) if kb.find(pb[:n]) >= 0)
            if at < 0 or abs(len(pb) - len(kb[at:at + len(pb) + 4])) > 4:
                raise SystemExit(f'{GUWEN} id={rid} 有一段不在 {vol} id={vid} 里，'
                                 f'不是同一篇的删节本，先核对再跑：{para[:20]}')
        drop.add(i)
        evidence.append(dict(path=GUWEN, idx=i, keep=f'{vol} id={vid}', kind='guwen_drop',
                             title=title(gone), note=note))
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


# ---------------------------------------------------------------- tang_residual

# 《全唐诗》内部去重之后还剩 22 组「同作者」。逐组看过：绝大多数是异文，或是「缺字重录本」
# （后一条题名尾巴上写着「按全唐詩卷X收此詩缺N字今重錄」，正文反而更全），两存。只有下一条
# 同时满足「两组同题」且「正文只差通用的异体 / 正俗字」，已在批次 `cleanup/tang-residual-2`
# 删掉，所以列表留空；重跑时数据若被重新导入，按下面的判据补回来。
#   唐/诗/全唐诗/poet.tang.1000.json#9 秦韜玉《橫吹曲辭 紫騮馬》
#   ← 唐/诗/全唐诗/poet.tang.37000.json#249《紫騮馬》（銙/胯、却/著、躞蹀/踥蹀 皆通用）
TANG_REL = []


def tang_residual():
    out, drop, evidence = {}, set(), []
    for rel, i, (rel2, j), note in TANG_REL:
        for r in (rel, rel2):
            if r not in out:
                out[r] = load(r)
        drop.add((rel, i))
        evidence.append(dict(path=rel, idx=i, keep=f'{rel2}#{j}', kind='tang_residual',
                             title=title(out[rel][i]), note=note))
    return out, drop, evidence


# ---------------------------------------------------------------- small_scope

# 全库扫下来剩下的几处，逐条核过、能定案的。元组里的 rid 是该条自己的 `id`：
# 删除之后同文件的下标整体前移，重跑时按 id 找不到就是已经删过，不再动下标。
SMALL = [
    # 《人之初》《冠必正》是课本选目的「摘一段当一课」：正文是整部蒙学书的开头一小段，
    # 题名取的是首句。整部书已在 汇编/蒙学/ 收全（三字經、弟子規），按「一件作品只留一份正文」删选段。
]

# 已删条目的 id → 正文首句：重跑的校验依据（数据被重新导入时能发现）
SMALL_DONE = {
    # 袁荣法同一首词在 ci.dang.json 里录了两遍（正文、题名、词牌全同），删后一条
    '0h6d98': '今古事。思量大抵如此。中原烽火未曾收',
}


def small_scope():
    out, drop, evidence = {}, set(), []
    for rel, rid, keep, note in SMALL:
        if rel not in out:
            out[rel] = load(rel)
        hits = [i for i, r in enumerate(out[rel]) if r.get('id') == rid]
        if not hits:            # 已经删过（列表留空时也走到这里，什么也不做）
            continue
        i = hits[0]
        if len(hits) > 1:
            raise SystemExit(f'{rel} 有 {len(hits)} 条 id={rid}，先核对再跑')
        head = SMALL_DONE.get(rid)
        if head and head not in ''.join(out[rel][i].get('paragraphs') or '')[:40]:
            raise SystemExit(f'{rel} id={rid} 正文已不是「{head}」，先核对再跑')
        drop.add((rel, i))
        evidence.append(dict(path=rel, idx=i, keep=f'{rel}#{keep}' if keep is not None else '',
                             kind='small_scope', title=title(out[rel][i]), note=note))
    return out, drop, evidence


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('action', nargs='?', default='dedupe', choices=['dedupe', 'songci-diff'])
    ap.add_argument('--work', help='songci-diff / 宋词两批异文：检索结果目录（含 results.jsonl）')
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
    songci, drop, ev = songci_merge(songci_evidence(args.work))
    evidence += ev
    for rel, recs in songci.items():
        idxs = {i for r, i in drop if r == rel}
        if idxs:
            songci[rel] = [r for i, r in enumerate(recs) if i not in idxs]

    songshi, shdrop, ev = songshi_dup()
    evidence += ev
    for rel, recs in songshi.items():
        idxs = {i for r, i in shdrop if r == rel}
        songshi[rel] = [r for i, r in enumerate(recs) if i not in idxs]

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

    # 补本删节 / 异文的几条：与上面同一份 GUWEN，另把异文记进分卷本的 sources
    gd, gddrop, ev = guwen_drop()
    evidence += ev
    guwen = [r for i, r in enumerate(guwen) if i not in gddrop]

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
        for kind in ('songci_merge', 'songci_variant', 'songci_variant_open', 'songshi_dup',
                     'yuanqu_cover', 'sanguo_dup', 'kongzi_subset', 'guwen_subset', 'guwen_drop', 'qingci_attr',
                     'tang_residual', 'small_scope'):
            print(f'\n-- {kind}')
            for e in by_kind.get(kind, [])[:200]:
                print(f"   {e['path']}#{e['idx']} {e['title'][:20]} → 留 {e['keep']}（{e['note']}）")
        print('\n（预演，未改动任何文件；加 --apply 落盘）')
        return

    for rel, recs in songci.items():
        dump(rel, recs)
    for rel, recs in songshi.items():
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
        # 下标会随删记录前移，记 id 而不是行号 —— 记录留着，重建数据后还认得出是哪一条
        fixes_by_file.setdefault(e['path'], []).append(dict(
            original=f"{e.get('id') or '#' + str(e['idx'])} {e['title'][:24]}", corrected='删除',
            note=f"[{e['kind']}] 正文与 {e['keep']} 重出：{e['note']}"))
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
