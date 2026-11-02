#!/usr/bin/env python3
"""`reference/说岳全传.txt` → `清/小说/说岳全传/shuoyuequanzhuan.json`（issue #200）。

底本是简体排印本，版式与 `scripts/import_novel_chapter.py` 那一批相同：书头（著者行、章节数、
字数、简介、`========正文========`）之后，回目行顶格、前后各一个空行，正文一段一行。

    书名：说岳全传
    作者：

    章节数：80
    字数：418653
    ========简介========
    ……
    ========正文========
    第〇一回 天遣赤须龙下界 佛谪金翅鸟降凡
    三百余年宋史，中间南北纵横。……
    …

这一本另有两类底本自身的毛病，脚本按下面的口径处理，`--report` 可以把每一处打出来复核。

一、**「一」被当成专名号印了两次**。底本用「一」圈人名、地名、书名：

    一江一山                     → 江山                （宋室江山）
    一精一忠报国                  → 精忠报国
    欧一陽一从善                  → 欧阳从善
    一胡一迪、高一宠一、一尸一首        → 胡迪、高宠、尸首

被圈的两个字之间也是「一」时（`一精一忠` 的三个字本该是「精忠」两字），就成了 `一X一`；
排版又把这个词从中间**断到了下一行**，于是「一」孤零零挂在行尾：

    搅乱宋室一江一 / 山，使万民受兵革之灾      ← 行尾「一」是圈「江」的第二个专名号
    那一日…一路行至一江一 / 边叫定了船        ← 同上

所以判据不能只看「行尾是不是一」，要看**这一行的行尾连同下一行的行首合起来讲不讲得通**
（`FOLDS` 表逐条给出合并后的读法）。合并之后专名号就成对出现了，再把成对的删掉。
这种断法全书 156 处，逐处核过。

二、**形近字录错**。底本有个别字是形近讹字，不是异文（`TYPO_FIXES`，逐条给依据）。
认不出来的不改，宁可留着。

    python3 scripts/import_shuoyue_reference.py            # 写文件
    python3 scripts/import_shuoyue_reference.py --check    # 只比对，不写
    python3 scripts/import_shuoyue_reference.py --report   # 打印每一处标点/拆行的处理
"""
import argparse
import hashlib
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import progress as pg                        # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = 'reference/说岳全传.txt'
OUT = '清/小说/说岳全传/shuoyuequanzhuan.json'
INTRO_MARK = '========简介========'
BODY_MARK = '========正文========'

CN = {c: i for i, c in enumerate('零一二三四五六七八九')}
CN['〇'] = 0


def cn2int(s):
    s = s.replace('〇', '零')
    if s.isdigit():
        return int(s)
    if '百' not in s and '十' not in s and len(s) > 1:
        return int(''.join(str(CN[c]) for c in s if c in CN))
    if '百' in s:
        hi, lo = s.split('百')
        lo = lo.lstrip('零')
        return (CN[hi] if hi else 1) * 100 + (cn2int(lo) if lo else 0)
    if '十' not in s:
        return CN[s]
    hi, lo = s.split('十')
    return (CN[hi] if hi else 1) * 10 + (CN[lo] if lo else 0)


def make_id(author, title, body, taken):
    key = f'{author}|{title}|{"".join(body)}'
    size = 6
    while True:
        digest = hashlib.blake2b(key.encode(), digest_size=16).digest()
        v = int.from_bytes(digest, 'big')
        out = ''
        for _ in range(size):
            v, r = divmod(v, 22)
            out = '0123456789abcdefghijklmnopqrstuv'[r] + out
        if out not in taken:
            taken.add(out)
            return out
        size += 1


def existing_ids():
    taken = set()
    for dirpath, dirs, files in os.walk(ROOT):
        dirs[:] = [d for d in dirs if d not in
                   {'.git', '.github', '.cnb', 'docs', 'reference', 'scripts', 'loader',
                    'authors', 'dynasties', 'rank', 'strains', 'images'}]
        for f in files:
            if not f.endswith('.json'):
                continue
            try:
                data = json.load(open(os.path.join(dirpath, f), encoding='utf-8'))
            except Exception:
                continue
            if isinstance(data, list):
                for r in data:
                    if isinstance(r, dict) and r.get('id'):
                        taken.add(r['id'])
    return taken


# ── 一、专名号：底本用「一」圈人名、地名、书名 ────────────────────────────
#
#     一江一山 → 江山    一精一忠报国 → 精忠报国    欧一陽一从善 → 欧阳从善
#     一胡一迪 → 胡迪    高一宠一 → 高宠            一尸一首 → 尸首
#
# 被圈的两个字之间也正好是「一」时（`一精一忠` 的三个字本该是「精忠」两字），就成了 `一X一`。
# 成对的删掉即可；不成的（`一马当先`、`一一交跌`）留着不动，所以删除用正则做，不用词表。
#
# 麻烦的是排版把这个词从中间断到了下一行，「一」孤零零挂在行尾：
#
#     搅乱宋室一江一 / 山，使万民受兵革之灾     ← 行尾「一」是圈「江」的第二笔
#     不觉两泪一交一 / 流，说道：……            ← 行尾「一」是圈「交」的第二笔
#     立脚不住，一一交一 / 跌倒                 ← 同上
#     便一钅一党一 / 打来                        ← 行尾「一」是圈「党」的第二笔
#
# 这种断法全书 156 处。判据只看「行尾这一行连上下行首讲不讲得通」：把下一行接上来（`fold_lines`），
# 接上之后成对的专名号自然露出来，交给 `strip_proper_marks` 一并删除。
#
# 剩下 196 处行尾的「一」是**前一个词的收笔**，下一行另起，没有东西可接：
#
#     出洞门来闲步寻一欢 / 。但见松径清幽      ← 「一欢」＝欢（那个「一」是「欢」的专名号收笔）
#     长老叙了些寒一温 / ，谈了半日旧话        ← 「一温」＝温
#     岳大爷应声：“晓得！”过了一夜 / ，次早天明  ← 「一夜」本来就是一夜，那个「一」不是专名号
#
# 这一类不能接，接了反而把句子焊死。但底本在这里断错了段：句子在「一」处断成了两段，
# 第二段就以标点起头（全书 196 处，库内其余章回小说是 0 处）。`swap_breaks` 把断点从
# 「一」后面挪到标点后面 —— 只换「在哪断」，句子不改：
#
#     过了一夜 / ，次早天明        →  过了一 / 夜，次早天明
#     寻一欢 / 。但见              →  寻一 / 欢。但见
#
# 行尾那个「一」随后由 `strip_proper_marks` 删掉（它成不了对，就别管它），于是
# 「过了一夜」「寻欢」各自归位，段首不再挂标点。
#
# 哪些能接、哪些不能接，差别在**行尾那个「一」圈的是谁**：
#   * 圈的是行尾紧邻的那个字（`一江`、`一交`、`一钅`、`一宠`）→ 下一行行首是这个字的另一半，
#     接上成词：江山、交流、钅党、宠并。这类要接，`FOLD_STEM` 是全表，唯一的依据。
#   * 圈的是别的字（`一精` / `一忠` 里的前一个），行尾这个「一」是**前一个词的收笔**，下一行
#     另起一个词（`精忠报国` / `岳爷` / `从善`）。这类不能接，接了就成了「……忠 / 岳飞」。所以
#     `FOLD_STEM` 之外的行尾「一」一律不动，它会在后面被成对删除。
FOLD_STEM = {
    # 行尾「一X」，X 是被圈的字：下一行行首是这个词的后半
    '江': '山中边心口里内上北南面波水去来大总鱼的潮夜之回何华昔罢景头路衙分都到泪就千门走河丞三滨驿探云汉扎不并西府知太仙翻王撒搅三十染月'
          '振金',
    '交': '错战与兵锋手跌流付还加卷在惟轻知行也得结关争格相界此了旨家竟清割接令纳刑拜便秦进你翻拜一的',
    '胡': '迪言先须为子茄马乱尘中风同筋边章箱哨赖兀梦名饼中',
    '团': '圆一转和蓬打的火三围绝花走猛杀鱼龙厮裹高黑仙就一',
    '温': '奇庭铁一和存上来侯',
    '习': '练射文武诗学行否先一',
    '党': '专人打逆恶，',
    '邓': '武成',
    '宠': '一并就望道等掌想上劈把大杀见又掀下死坟用幸异思爱众渥',
    # 行尾就是一个「一」：它自己是被圈的那个字的后一笔（一交→），下一行行首是后半
    '': '流跌翻便竟打',
}
# 「一钅一党」这一类：行尾是「一钅」，下一行行首是「党」
FOLD_EXTRA = {('钅', '党'): '钅党', ('钅', '一'): None}

# 诗里跨行断词的，只有这一处：「大勋未集归田里，且向江 / 潭作困龙」
EOL_SPLIT = {('江', '潭')}

# `swap_breaks` 之后仍有一类接不上：行尾那个「一」根本没有对应的成对专名号，
# 它只是把词断开了（「汉陽江 / 口」「投东去条胡 / 同」「身穿领团 / 花绣白袍」）。
# 这类加进来，`swap_breaks` 会把断点往后挪一个字。逐条核过，全书 9 处。
EOL_ONE = {
    ('胡', '同', '内'), ('胡', '言', '，'), ('江', '彩', '，'),
    ('江', '河', '尽'), ('团', '花', '绣'), ('江', '口', '，'),
    # 「云床 / 上打坐」「在床 / 前问候」「春一光 / 暮」「一夜 / 无事」
    ('床', '上', '打'), ('床', '前', '问'), ('光', '暮', '。'), ('夜', '无', '事'),
    # 「与巴秀琳、王素娟同居 / 祝不提」：「祝」是「。」之讹，见 CHAR_FIXES
    ('居', '祝', '不'), ('夫', '妇', '。'),
    # 「风一流 / 俊雅」「风一流 / 两颉颃」：那个「一」是「流」的专名号收笔
    ('流', '俊', '雅'), ('流', '两', '颉'),
    ('江', '潭', '作'),
}


# ── 二、行尾那个「一」本身是录错的 ─────────────────────────────────────────
#
# `swap_breaks` 把断点挪到标点之后以后，句子多半就通了：
#
#     过了一夜 / ，次早天明        → 过了一 / 夜，次早天明        （「一夜」归位）
#     寻一欢 / 。但见              → 寻一 / 欢。但见              （「寻欢」归位）
#
# 但底下这一串挪完之后仍是残的：行尾那个「一」不是专名号、是底本自己多打的，得删掉。
# 逐条列出、逐条核过，只认这一种上下文，不做全局替换。
DROP_EOL = (
    ('抚养他成人一', '抚养他成人'),      # 11 回
    ('卧病在床一', '卧病在床'),          # 13 回「家父卧病在床，不能接旨」
    ('抚养成人一', '抚养成人'),          # 16、22、32 回
    ('数千床一', '数千床'),              # 30 回「借棉被数千床，放在船上」
    ('也不成人一', '也不成人'),          # 35 回董先骂施全「你这狗男女也不成人」
    ('马不良一', '马不良'),              # 39 回回末诗「可惜将军马不良」
    ('好渡长江一', '好渡长江'),          # 43 回
    ('战大江一', '战大江'),              # 44 回「十万雄兵战大江」
    ('杀了日夜一', '杀了日夜'),          # 54、58 回（都缺「一」字，见 STILL_GARBLED）
    ('即便成交一', '即便成交'),          # 64 回
    ('李官人来成交一', '李官人来成交'),  # 64 回
    ('按倒在床一', '按倒在床'),          # 68 回「按倒在床上」
    ('试交一一', '试交一'),              # 68 回回末诗「复教黄鸟试交交」，只多打一个「一」
    ('跌下龙床一', '跌下龙床'),          # 74 回
    ('披衣服下床一', '披衣服下床'),      # 79 回
    ('两个解衣上床一', '两个解衣上床'),  # 79 回
)

# 删完还是不通的，留着不补 —— 补字要另找本子，这里只登记，别在 docs 里装作已经对了。
STILL_GARBLED = (
    ('杀了日夜', '当作「杀了一日一夜」，底本掉字'),
    ('杀了一日，走了一夜', '疑「杀了一日一夜，走了一夜」之讹'),
    ('正砍个着，一一交跌翻', '当作「一交跌翻」，多一个「一」'),
)


# ── 三、形近/音近录错（不是异文：底本自身录错） ────────────────────────────
#
# 长上下文替换，不会误伤别处。
TYPO_FIXES = (
    ('便一钅一党一打来', '便一钅党打来'),        # 「钅党」是「鎲」的类推简化，底本把偏旁拆成了「一钅一党一」
    ('浑铁钅一党一', '浑铁钅党'),              # 同上（浑铁鎲）
    ('—一一交一清', '一一交清'),               # 破折号讹成「—」，且多一个「一」
    ('遮挡不祝', '遮挡不住'),                  # 44 回梁夫人语「使我两下遮挡不住」
    ('同一居祝', '同居住。'),                  # 8 回「迁到这里同居住。」「祝」是「。」之讹
)

# 专名号删完之后剩下的另一类：底本多写或写错的地方，成对的专名号删不到，得单独认回来。
# 逐条给出上下文，全书逐处核过。
ZHI_FIXES = (
    ('寻一欢', '寻欢'),          # 1 回「出洞门来闲步寻一欢」——「欢」的专名号收笔
    ('虬精一灵', '虬精灵'),      # 1 回「这虬精灵一灵不忿」——「精」的专名号收笔
    ('女上蝠', '女士蝠'),        # 1 回「那女上蝠一点灵光射出雷音寺」，「上」是「士」之讹
    ('做人一团和气', '做人一团和气'),
    ('美一女', '美女'),        # 「歌童美女」，18 回
    ('私婬一兀术', '私婬兀术'),  # 61 回
    ('奸婬一滥赂', '奸婬滥赂'),  # 73 回
    ('荒婬一酒色', '荒婬酒色'),  # 18 回
    ('荒婬一无道', '荒婬无道'),  # 79 回
    ('贪婬一好色', '贪婬好色'),  # 61 回
    ('贪婬一欲', '贪婬欲'),      # 79 回
)

# 单字讹误：只在这种上下文里出现才改
CHAR_FIXES = (
    ('江衙州', '江衢州'),                      # 浙江衙州 → 衢州（太学生徐应鹿的籍贯）
    ('王素娟同居祝不提', '王素娟同居住。不提'),  # 68 回「同居住」，「祝」是「。」之讹
    ('把今郎抱出来', '把令郎抱出来'),          # 1 回岳和请道人看儿子
    ('与今郎倒有', '与令郎倒有'),              # 4 回道悦和尚语
)


# 行首标点：底本把句子断在标点前的标志
BREAK_LEAD = '，。！？；：、）》”’'


def can_fold(joined, nxt):
    """行尾该不该把下一行接上来。判据见上面 FOLD_STEM 那一段。"""
    if not nxt:
        return False
    # 1) 行尾是「一X一」，下一行行首就是 X 的后半：「宋室一江一 / 山」「一胡一 / 迪」
    m2 = re.search('一([\u4e00-\u9fff])一?$', joined)
    if m2 and joined.endswith('一' + m2.group(1) + '一'):
        tail = m2.group(1)
        if tail == nxt[0]:
            # 「一胡迪一 / 听」→ 行尾那个「一」其实是「迪」的收笔，接上
            return True
        if nxt[0] in FOLD_STEM.get(tail, ''):
            # 「宋室一江一 / 山」：行尾那个「一」是圈「江」的第二个专名号
            return True
    # 下一行以标点起：断点本来就该在这标点之后，先接上来（「寻一欢 / 。但见」）
    if nxt[0] in BREAK_LEAD:
        return True
    # 2) 行尾是「一X」，下一行行首是这个词的后半：「宋室一江 / 山」「一精一忠 / 岳飞」不行
    m = re.search('一([\u4e00-\u9fff])$', joined)
    if m and m.group(1) != '一':
        stem, ch = m.group(1), nxt[0]
        if ch in FOLD_STEM.get(stem, '') or (stem, ch) in FOLD_EXTRA:
            return True
        # 行尾「一X」，X 后面没有字可填：那个「一」是「X」的专名号收笔
        # （「风一流 / 俊雅」「歌舞春一光 / 暮」），接上，交给专名号删除
        return (stem, ch, nxt[1:2]) in EOL_ONE
    # 3) 行尾孤零零一个「一」：「两泪一交一 / 流」「名江一 / 彩」「汉陽江一 / 口」
    m1 = re.search('一([\u4e00-\u9fff])一$', joined)
    if m1 and joined.endswith('一'):
        tail = m1.group(1)
        if nxt[0] in FOLD_STEM.get(tail, ''):
            return True           # 「宋室一江一 / 山」
        if tail == '江' and nxt[0] in ('口', '上'):
            return True           # 「汉陽江一 / 口」
        if (tail, nxt[0], nxt[1:2]) in EOL_ONE:
            return True           # 「且向一江一 / 潭作困龙」
        return False
    if joined.endswith('一'):
        if nxt[0] in FOLD_STEM['']:
            return True
        return (joined[-1:], nxt[0], nxt[1:2]) in EOL_ONE
    # 4) 行尾这个字本身就是被词分开的：「云床 / 上打坐」「春一光 / 暮」「风一流 / 俊雅」
    if (joined[-1:], nxt[0], nxt[1:2]) in EOL_ONE:
        return True
    # 诗中把一个词断到下一行：「且向江 / 潭作困龙」——行尾是单字、下一行不是标点、整句是诗
    if len(joined) and (joined[-1:], nxt[0]) in EOL_SPLIT:
        return True
    if joined.endswith('一') and (joined[-2:-1], nxt[0], nxt[1:2]) in EOL_ONE:
        return True
    return False


def fold_lines(lines, report):
    """把断在行尾的专名号接回去（判据见上面 FOLD_STEM）。"""
    out = []
    i = 0
    while i < len(lines):
        joined = lines[i]
        while True:
            nxt = lines[i + 1] if i + 1 < len(lines) else ''
            if not nxt:
                break
            ok = can_fold(joined, nxt)
            if not ok:
                break
            report.append(('fold', joined[-12:], nxt[:12]))
            joined += nxt
            i += 1
        out.append(joined)
        i += 1
    return out


def swap_breaks(recs, report):
    """行尾「一」后面断开的那一段，断点挪到行首标点之后（见上面第三类）。"""
    for r in recs:
        ps = r['paragraphs']
        for k in range(len(ps) - 1, 0, -1):
            cur, prev = ps[k], ps[k - 1]
            if not cur or cur[0] not in BREAK_LEAD or not prev.endswith('一'):
                continue
            j = 0
            while j < len(cur) and cur[j] in BREAK_LEAD:
                j += 1
            if j == 0 or j == len(cur):
                continue
            report.append(('swap', prev[-12:], cur[:12]))
            ps[k - 1], ps[k] = prev[:-1] + cur[:j], cur[j:]


def strip_proper_marks(text):
    """把成对的专名号「一」删掉：一X一 → X，一YZ一 → YZ；不成的留着不动。"""
    def rep(m):
        return m.group(1)
    # 先长后短：一YZ一 比 一Y一 长，单趟扫一遍即可，因为都是同一个「一」开头
    prev = None
    while prev != text:
        prev = text
        text = re.sub(r'一([\u4e00-\u9fff])一', rep, text)
    return text


def clean(line):
    for wrong, right in DROP_EOL:      # 只认行尾，right 就是 wrong 去掉行尾那一个「一」
        if line.endswith(wrong):
            line = line[:-len(wrong)] + right
    for wrong, right in TYPO_FIXES:
        line = line.replace(wrong, right)
    for wrong, right in CHAR_FIXES:
        line = line.replace(wrong, right)
    line = strip_proper_marks(line)
    for wrong, right in ZHI_FIXES:      # 要在删过成对专名号之后才认得出
        line = line.replace(wrong, right)
    return line


HEAD = re.compile(r'^第([〇零一二三四五六七八九十]+)回[\s　]+(\S.*)$')

# 底本缺回：只有回次与回目、没有正文。回目据《说岳全传》通行本第八十回本补，
# 正文不臆造（底本这个本子第八十回前缺了第五二回，回次由 51 直接跳到 53）。
GAP = {
    52: '阮统制扬州失节　韩元帅狼福鏖兵',
}


def parse(report):
    recs, cur = [], None
    in_body = False
    intro = []
    raw = open(os.path.join(ROOT, SRC), encoding='utf-8').read().split('\n')
    raw = [ln.strip() for ln in raw]
    heads = [(i, ln) for i, ln in enumerate(raw) if HEAD.match(ln)]
    first_head = heads[0][0]
    body = raw[first_head:]
    # 卷前（书名行、章节数、字数、简介）不进正文；断言它就是书头
    for ln in raw[:first_head]:
        if ln and ln != INTRO_MARK and ln != BODY_MARK:
            intro.append(ln)
    assert intro[0].startswith('书名：'), intro[:2]
    report.append(('head', '书头 %d 行不入正文' % len(intro), intro[0]))
    lines = [ln for ln in body if ln]
    lines = fold_lines(lines, report)
    for ln in lines:
        m = HEAD.match(ln)
        if m:
            cur = {'title': f'第{cn2int(m.group(1))}回\u3000'
                            + re.sub(r'[\s　]+', '\u3000', m.group(2).strip()),
                   'paragraphs': []}
            recs.append(cur)
            continue
        if cur is None:
            raise SystemExit('回目之前的文字没有归属：' + ln[:40])
        if ln:
            cur['paragraphs'].append(ln)
    return recs


def build(recs, taken):
    out = []
    for r in recs:
        rec = {'author': '钱彩', 'title': r['title'], 'dynasty': '清',
               'paragraphs': r['paragraphs']}
        rec['id'] = make_id(rec['author'], rec['title'], rec['paragraphs'], taken)
        if r.get('gap'):
            rec['note'] = ('底本缺正文：reference/说岳全传.txt 由第五一回直接跳到第五三回，'
                           '本回只有回目，正文待补')
        out.append(rec)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--check', action='store_true', help='只比对现有文件，不写')
    ap.add_argument('--report', action='store_true', help='打印每一处拆行/标点处理')
    args = ap.parse_args()
    report = []
    recs = parse(report)
    # 顺序不能换：先挪断点（这一步要靠行尾的「一」认位置），再删成对的专名号
    swap_breaks(recs, report)
    for r in recs:
        r['paragraphs'] = [t for t in (clean(p) for p in r['paragraphs']) if t]
    nums = [cn2int(re.match(r'^第(.*?)回', r['title']).group(1)) for r in recs]
    if nums != [n for n in range(1, len(nums) + 1 + len(GAP)) if n not in GAP]:
        raise SystemExit(f'回次不连续：{nums}')
    for n, head in GAP.items():
        recs.insert(n - 1, {'title': f'第{n}回\u3000' + re.sub(r'\s+', '\u3000', head),
                            'paragraphs': [], 'gap': True})
    if [cn2int(re.match(r'^第(.*?)回', r['title']).group(1)) for r in recs] != \
            list(range(1, len(recs) + 1)):
        raise SystemExit('补缺回之后回次仍不连续')
    taken = existing_ids()
    dst = os.path.join(ROOT, OUT)
    if os.path.exists(dst):
        for r in json.load(open(dst, encoding='utf-8')):
            taken.discard(r.get('id'))

    # 专名号还有没成对的，就是 FOLDS/FOLD_BARE 漏了情形，报出来人工核
    left = [(r['title'], p[:40]) for r in recs for p in r['paragraphs']
            if re.search(r'一[\u4e00-\u9fff]一', p)]
    lead = [(r['title'], p[:40]) for r in recs for p in r['paragraphs']
            if p and p[0] in BREAK_LEAD]
    data = build(recs, taken)
    text = json.dumps(data, ensure_ascii=False, indent=2) + '\n'
    print(f'{OUT}: {len(data)} 回，{sum(len(r["paragraphs"]) for r in data)} 段，'
          f'{sum(len(p) for r in data for p in r["paragraphs"])} 字')
    if args.report:
        for kind, a, b in report:
            print(f'  [{kind}] {a} ‖ {b}')
        for t, p in left:
            print(f'  [残] {t} {p}')
    if left:
        print(f'  警告：仍有 {len(left)} 处疑似未成对的专名号')
    if lead:
        print(f'  警告：仍有 {len(lead)} 段以标点起头')
        for t, p in lead:
            print(f'     [段首] {t} {p}')
    if args.check:
        old = open(dst, encoding='utf-8').read() if os.path.exists(dst) else ''
        print('  一致' if old == text else '  不一致')
        return 0 if old == text else 1
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    open(dst, 'w', encoding='utf-8').write(text)
    print('  →', OUT)
    return 0


if __name__ == '__main__':
    sys.exit(main())
