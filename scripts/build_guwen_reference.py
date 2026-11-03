#!/usr/bin/env python3
"""按 repo 内 `reference/古文观止.txt` 重建 `汇编/古文观止/` 的 12 个卷文件与目次。

底本：`reference/古文观止.txt`，1935 行，简体排印本。版式：

    古文观止 清 吴楚材 吴调侯
    卷一 / 周文 / 郑伯克段于鄢 左传 ……        前 260 行是目次：卷次 / 体裁 / 「篇题 出处」
    卷一 周文                                  260 行起是正文，一篇一节
    【郑伯克段于鄢】（隐公元年 《左传》）
    初，郑武公娶于申……                       一段一行，段间空行

正文照录，只作四类处理，每一条都记进 `docs/古文观止勘正.tsv`：

  * **篇题**取通行本的题名：底本目次与正文小节的题名 33 处不一致，逐条判定后取通行本
    （`产告范宣子轻币` → `子产告范宣子轻币`、`颜斶说秦王` → `颜斶说齐王`、
    `触詟说赵太后` → `触龙说赵太后`、`州画像记` → `张益州画像记`……）；
  * **作者**取目次出处栏，再归一到本库 `authors/authors.json` 的写法；《国策》《史记》
    《西汉文》这类不是作者，按通行本署原作者（左丘明 / 刘向 / 司马迁 / 贾谊……）；
  * **字**：底本判读错了的字、脱了字的地方，逐条对通行本改，见 `FIXES`；
  * **标点**：叠标点收敛成一个；行首引号误置、段尾漏收的引号与书名号逐条补，见 `PUNCT_FIXES`。

不做的：不加夹注、不加译文（底本没有）。《左传》34 篇的正文由
`scripts/dedupe_zuozhuan_gu.py` 删掉，只留目次指向 `史书/春秋左氏传/zuozhuan.json`；
卷四國策 14 篇同理，指向 `史书/战国策/zhanguoce.json`。

    python3 scripts/build_guwen_reference.py --check    # 只打印解析结果
    python3 scripts/build_guwen_reference.py            # 写 12 卷 + 目录 + 选目
"""
import argparse
import csv
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = 'reference/古文观止.txt'
OUT = '汇编/古文观止'

VOLS = [('一', '卷一 周文'), ('二', '卷二 周文'), ('三', '卷三 周文'),
        ('四', '卷四 秦文'), ('五', '卷五 秦文'), ('六', '卷六 汉文'),
        ('七', '卷七 六朝、唐文'), ('八', '卷八 唐文'), ('九', '卷九 唐、宋文'),
        ('十', '卷十 宋文'), ('十一', '卷十一 宋文'), ('十二', '卷十二 明文')]
VOL_TITLE = dict(VOLS)
VOL_FILE = {'一': '卷一周文', '二': '卷二周文', '三': '卷三周文', '四': '卷四秦文',
            '五': '卷五秦文', '六': '卷六汉文', '七': '卷七六朝唐文', '八': '卷八唐文',
            '九': '卷九唐宋文', '十': '卷十宋文', '十一': '卷十一宋文', '十二': '卷十二明文'}
DIFFICULTY = {}       # 体裁名，写进目录的 prologue

# 目次出处栏 → 本库作者名。指实不了出处的（《礼记·檀弓》）留「無名氏」。
AUTHOR = {
    '左传': '左丘明', '国语': '左丘明', '公羊传': '公羊高', '谷梁传': '谷梁赤',
    '礼记檀弓': '無名氏',
    '战国策': '刘向', '李斯': '李斯', '屈原': '屈原', '宋玉': '宋玉',
    '史记': '司马迁', '司马迁': '司马迁',
    '汉高祖': '刘邦', '汉文帝': '刘恒', '汉景帝': '刘启', '汉武帝': '刘彻',
    '贾谊': '贾谊', '晁错': '晁错', '邹阳': '邹阳', '司马相如': '司马相如',
    '李陵': '李陵', '路温舒': '路温舒', '杨恽': '杨恽', '汉光武帝': '刘秀',
    '马援': '马援', '诸葛亮': '诸葛亮',
    '李密': '李密', '王羲之': '王羲之', '陶渊明': '陶渊明', '孔稚珪': '孔稚珪',
    '魏征': '魏征', '骆宾王': '骆宾王', '王勃': '王勃', '李白': '李白',
    '李华': '李华', '刘禹锡': '刘禹锡', '杜牧': '杜牧',
    '韩愈': '韩愈', '柳宗元': '柳宗元', '欧阳修': '欧阳修',
    '王禹偁': '王禹偁', '李格非': '李格非', '范仲淹': '范仲淹', '司马光': '司马光',
    '钱公辅': '钱公辅', '李觏': '李觏', '张益': '張方平',
    '苏洵': '苏洵', '苏轼': '苏轼', '苏辙': '苏辙', '曾巩': '曾巩', '王安石': '王安石',
    '宋濂': '宋濂', '刘基': '刘基', '方孝孺': '方孝孺', '王鏊': '王鏊', '王守仁': '王守仁',
    '唐顺之': '唐顺之', '宗臣': '宗臣', '归有光': '归有光', '茅坤': '茅坤',
    '王世贞': '王世贞', '袁宏道': '袁宏道', '张溥': '张溥',
}
# 目次把作者栏切错的三条：题名 + 出处连在一起
SPLIT_AUTHOR = {'上书谏猎司马 相如': ('上书谏猎', '司马相如'),
                '陋室铭刘 禹锡': ('陋室铭', '刘禹锡'),
                '春夜宴桃李园 序李白': ('春夜宴桃李园序', '李白')}
# 篇题：取通行本题名。底本目次里有 12 处题名有讹、排位有错（作者栏串进了题里），另有三条
# 与通行本不同，逐条给定；没列出的照底本。改写的原委见 docs/古文观止重建.md。
TITLE = {
    '产告范宣子轻币': '子产告范宣子轻币',        # 脱「子」
    '里隔断罟匡君': '里革断罟匡君',              # 「隔」→「革」
    '诸稽郢形成于吴': '诸稽郢行成于吴',          # 「形成」→「行成」
    '子重耳对秦客': '公子重耳对秦客',            # 脱「公」
    '杜篑扬觯': '杜蕢扬觯',                      # 「篑」→「蕢」
    '颜斶说秦王': '颜斶说齐王',                  # 目次作「秦王」，正文与《國策》作「齊王」
    '触詟说赵太后': '触龙说赵太后',              # 「詟」→「龙」
    '州画像记': '张益州画像记',                  # 脱「张益」
    '潮洲韩文公庙碑': '潮州韩文公庙碑',          # 「洲」→「州」
    '乞校正陆贽奏议进御扎子': '乞校正陆贽奏议进御札子',   # 「扎」→「札」
    '后日复上宰相书': '后十九日复上宰相书',      # 目次脱「十九」，「日」是「十九日」之误
    '讳辨': '讳辩',                              # 「辨」→「辩」
    '钴鉧沄西小丘记': '钴鉧潭西小丘记',          # 「沄」→「潭」
    '五代史宦官传序': '五代史宦者传论',          # 通行本作「宦者传论」
    '戒兄子严敦书': '诫兄子严敦书',              # 通行本作「诫」
}
# 正文小节题名（底本第二节写法）→ 通行本题名
SECTION_TITLE = {
    '贾谊过秦论上': '过秦论上', '贾谊治安策一': '治安策一', '晁错论贵粟疏': '论贵粟疏',
    '邹阳狱中上梁王书': '狱中上梁王书', '司马相如上书谏猎': '上书谏猎',
    '李陵答苏武书': '答苏武书', '路温舒尚德缓刑书': '尚德缓刑书',
    '杨惲报孙会宗书': '报孙会宗书', '马援诫兄子严敦书': '诫兄子严敦书',
    '戒兄子严敦书': '诫兄子严敦书',
    '诸葛亮前出师表': '前出师表', '诸葛亮后出师表': '后出师表',
    '归去来辞': '归去来兮辞', '驳《复仇议》': '驳复仇议',
    '书《洛阳名园记》后': '书《洛阳名园记》后', '《吴山图》记': '吴山图记',
    '《青霞先生文集》序': '青霞先生文集序', '高祖功臣侯年表': '高祖功臣侯者年表',
    '武帝求茂材异等诏': '武帝求茂才异等诏',
}
# ---- 字：底本讹字、脱字、衍文，逐条对通行本改 ---------------------------------
# 键是通行本篇题；每项 (底本原字, 改用, 依据)。依据里写明对的是哪一部书哪一卷。
FIXES = {
    '郑伯克段于鄢': [
        ('颖考叔', '颍考叔', '底本本篇三处作「颍考叔」，篇末「君子曰」引处误作「颖」；《左传》隐公元年作「颍」'),
    ],
    '臧哀伯谏纳郜鼎': [
        ('戒俱', '戒惧', '形近讹字，《左传》桓公二年作「百官於是乎戒惧」'),
    ],
    '曹刿论战': [
        ('犠牲', '牺牲', '「犠」是「牺」的异体，底本他处均作「牺」'),
    ],
    '阴饴甥对秦伯': [
        ('不惮征纟善以立圉', '不惮征缮以立圉',
         '底本把「缮」拆成「纟」「善」两字，《左传》僖公十五年作「征缮以立圉」'),
    ],
    '子鱼论战': [
        ('虽及胡耇', '虽及胡耉', '「耉」是老寿，底本作「耇」（同形近字）；《左传》石经本、注疏本并作「耉」'),
    ],
    '寺人披见文公': [
        ('夫袪犹在', '夫祛犹在', '《左传》僖公二十四年作「夫祛犹在」，底本「袪」形近而讹'),
    ],
    '展喜犒师': [
        ('县罄', '县磬', '《左传》僖公二十六年作「室如县磬」，底本「罄」形近而讹'),
    ],
    '单子知陈必亡': [
        ('火朝觌矣', '火朝覿矣', '底本本篇两处作「覿」，此一处作「觌」，统一'),
        ('膳宰不致饣气', '膳宰不致饩', '底本把「饩」拆成「饣」「气」两字，《周语中》作「膳宰不致饩」'),
        ('廪人献饣气', '廪人献饩', '同上，《周语中》作「廪人献饩」'),
    ],
    '虞师晋师灭夏阳': [
        ('取之中而厩置之外厩也', '取之中厩而置之外厩也',
         '底本「厩」误置于「而」后，《穀梁传》僖公二年作「取之中厩而置之外厩也」'),
    ],
    '公子重耳对秦客': [
        ('子显以致使于穆公', '子显以致命于穆公',
         '底本衍「使」、脱「命」，《礼记·檀弓下》作「子显以致命于穆公」'),
    ],
    '触龙说赵太后': [
        ('触詟', '触龙', '「詟」是「龙」的形讹，通行本作「触龙说赵太后」；底本目次、正文并误'),
    ],
    '鲁仲连义不帝秦': [
        ('赌其一战', '睹其一战', '形近讹字，《国策·赵策三》作「睹其一战而胜」'),
    ],
    '乐毅报燕王书': [
        ('昌固君乐毅', '昌国君乐毅', '形近讹字，《国策·燕策二》作「昌国君乐毅」'),
        ('故鼎反乎历室', '故鼎反乎磿室', '底本脱「磿」的「石」旁，《史记·乐毅列传》作「故鼎反乎磿室」'),
    ],
    '司马错论伐蜀': [
        ('周，天下之示室也', '周，天下之宗室也', '形近讹字，《国策·秦策一》作「周，天下之宗室也」'),
    ],
    '卜居': [
        ('龟策诚不能知此事', '龟策诚不能知事', '底本衍「此」字，《楚辞·卜居》作「龟策诚不能知事」'),
    ],
    '货殖列传序': [
        ('仓廪实而佑礼节', '仓廪实而知礼节', '底本讹作「佑」，《管子·牧民》《史记·货殖列传》并作「知」'),
        ('衣食足而佑荣辱', '衣食足而知荣辱', '同上'),
    ],
    '报任少卿书': [
        ('推贤进士气为务', '推贤进士为务', '底本衍一「气」字，《汉书·司马迁传》作「推贤进士为务」'),
        ('在阘茸之中', '在闒茸之中', '「闒」是正字，底本作「阘」形近而讹'),
        ('乃欲卯首伸眉', '乃欲卬首伸眉', '形近讹字，《汉书·司马迁传》作「卬首信眉」'),
        ('受榜垂', '受榜箠', '「箠」是榜笞之具，底本作「垂」形近而讹'),
    ],
    '杨恽报孙会宗书': [
        ('奋褎低昂', '奋袖低昂', '「褎」是「袖」的古写，底本他处均作「袖」，统一'),
    ],
    '五人墓碑记': [
        ('蹈死之顾', '蹈死不顾', '底本作「之」，《古文观止》通行本作「蹈死不顾」'),
    ],
}

# 引号：底本是粗校，段首的开引号会排到段尾、会整段漏掉，也会多出一个没有着落的 ”
#   balance      底本断行时把一对引号拆在两段：前段补收尾、后段补开头；段尾多出的 ” 收掉
#   drop_before  段中间那个 “ 是开引号排错了位置，去掉
QUOTE = {
    # 底本把段首的开引号排到了段尾（「……焉。“且夫清道而后行」）
    '上书谏猎': {'drop_before': ['“且夫清道而后行', '“盖明者远见於未萌']},
    # 以下：底本断行时把引号拆开了 —— 段与段之间的成对两半接回去，段尾多出的 ” 收掉
    '敬姜论劳逸': {'balance': True},
    '展禽论祀爰居': {'balance': True},
    '诸稽郢行成于吴': {'balance': True, 'drop_before': ['“夫谚曰']},
    '单子知陈必亡': {'balance': True},
    '襄王不许请隧': {'balance': True},
    '伯夷列传': {'balance': True},
    '管晏列传': {'balance': True},
    '争臣论': {'balance': True},
    '送李愿归盘谷序': {'balance': True},
    '潮州韩文公庙碑': {'balance': True},
    '狱中上梁王书': {'balance': True},
    '尚德缓刑书': {'balance': True},
    '报孙会宗书': {'balance': True},
    '前出师表': {'balance': True},
    '李斯谏逐客书': {'balance': True},
    '宋玉对楚王问': {'balance': True},
}
# 底本判读与通行本不同、但属异文或底本读法，不改；记在此供复核
KEEP = [
    ('屈原列传', '皭然泥而不滓', '底本「皭」的「白」旁作「日」，通行本作「皭」，异体，不改'),
    ('屈原列传', '温蠖', '底本作「温蠖」，一本作「汶汶」，异文并存，不改'),
    ('宋玉对楚王问', '暴鬐於碣石', '「暴」即「曝」，《文选》作「曝」，不改'),
    ('送孟东野序', '咎陶', '咎陶即皋陶，古通，底本读法，不改'),
    ('报任少卿书', '佴之蚕室', '底本作「佴」，《汉书》作「佴」，不改'),
    ('报任少卿书', '彫琢', '「彫」是「雕」的古写，不改'),
    ('贾谊治安策一', '可为痛哭者一', '《汉书·贾谊传》同，不改'),
    ('兰亭集序', '晤言一室之内', '通行本作「悟言」，底本作「晤」，异文，不改'),
    ('兰亭集序', '怏然自足', '底本作「快然」，《晋书·王羲之传》作「快然」，不改'),
]


def fix_text(title, ps, rows):
    """改字：逐条替换，命中与否都记进勘正表。"""
    for orig, corr, why in FIXES.get(title, []):
        hit = 0
        for i, p in enumerate(ps):
            if orig in p:
                ps[i] = p.replace(orig, corr)
                hit += p.count(orig)
        rows.append({'篇目': title, '类别': '字', '底本': orig, '改用': corr,
                     '依据': why, '处数': hit})
    return ps


def fix_quote(title, ps, rows):
    """补、删引号：只动引号，不动字。"""
    q = QUOTE.get(title)
    if not q:
        return ps
    return _fix_quote(title, ps, rows, q)


def balance(ps):
    """底本断行处引号被拆在相邻两段：前段少一个收尾、后段少一个开头，接回去。"""
    for i in range(len(ps) - 1):
        if ps[i].count('“') > ps[i].count('”') and ps[i + 1].count('”') > ps[i + 1].count('“'):
            ps[i] += '”'
            ps[i + 1] = '“' + ps[i + 1]
    return ps


def _fix_quote(title, ps, rows, q):
    if q.get('drop_before'):
        for head in q['drop_before']:
            head = head if head.startswith('“') else head
            for i, p in enumerate(ps):
                if head in ps[i]:
                    rows.append({'篇目': title, '类别': '标点', '底本': head[:12],
                                 '改用': head[1:12], '依据': '开引号排到了段中间，去掉', '处数': 1})
                    ps[i] = ps[i].replace(head, head[1:], 1)
    if q.get('balance'):
        n = 0
        for _ in range(8):
            before = list(ps)
            # (1) 前段多一个开引号、后段多一个收尾：一对引号被拆在两段，接回去
            for i in range(len(ps) - 1):
                if ps[i].count('“') > ps[i].count('”') and ps[i + 1].count('”') > ps[i + 1].count('“'):
                    ps[i] = ps[i].rstrip() + '”'
                    ps[i + 1] = '“' + ps[i + 1].lstrip()
            # (2) 前段张着嘴、后段不接话：前段补收尾
            for i, p in enumerate(ps):
                if p.count('“') > p.count('”') and not p.rstrip().endswith('”'):
                    ps[i] = p.rstrip() + '”'
            # (3) 段尾多出的 ”：这一段自己配平了，收尾没有着落
            for _ in range(6):
                for i, p in enumerate(ps):
                    if p.count('”') > p.count('“') and p.rstrip().endswith('”'):
                        ps[i] = p.rstrip()[:-1]
                        break
            # (4) 段首孤立的 “：这一段话在底本里没有收尾
            for i, p in enumerate(ps):
                if p.count('“') > p.count('”') and p.startswith('“') \
                        and not p.rstrip().endswith(('？', '！', '。', '”')):
                    ps[i] = p[1:].lstrip()
            n += sum(1 for a, b in zip(before, ps) if a != b)
            if before == ps:
                break
        if n:
            rows.append({'篇目': title, '类别': '标点', '底本': '引号与段落错位',
                         '改用': '按段意接回', '依据': '底本断行时把成对的引号拆在两段，只动引号，字不动',
                         '处数': n})
    return ps


def read_source():
    """拆底本：前 260 行是目次，其后是一篇一节的正文。"""
    lines = open(os.path.join(ROOT, SRC), encoding='utf-8').read().split('\n')
    first = next(i for i, l in enumerate(lines) if l.startswith('【'))
    toc, body = lines[:first], lines[first:]
    entries, vol, genre = [], None, None
    for l in toc:
        s = l.strip()
        if re.fullmatch(r'卷[一二三四五六七八九十]+', s):
            vol, genre = s.replace('卷', ''), None
            continue
        if not s or re.fullmatch(r'卷[一二三四五六七八九十]+ ?\S*', s):
            continue
        if s.startswith('古文观止') and vol is None:
            continue
        if re.fullmatch(r'(周文|汉文|战国|秦文|唐文|宋文|明文|六朝[、　 ]*唐文|唐[、　 ]*宋文)', s):
            genre = s.replace('、', '')
            DIFFICULTY[vol] = genre
            continue
        if vol is None:
            continue
        if s in SPLIT_AUTHOR:
            t, auth = SPLIT_AUTHOR[s]
            entries.append(dict(vol=vol, genre=genre, title=t, author=auth,
                                src=s.split()[-1], raw=s))
            continue
        parts = s.split()
        src = parts[-1]
        entries.append(dict(vol=vol, genre=genre, title=' '.join(parts[:-1]),
                            author=AUTHOR.get(src, src), src=src, raw=s))
    secs, vol, cur = [], None, None
    for l in body:
        s = l.strip()
        m = re.fullmatch(r'(卷[一二三四五六七八九十]+) ?\S*', s)
        if m and not s.startswith('【'):
            vol = m.group(1).replace('卷', '')
            continue
        if s.startswith('【'):
            cur = dict(sec_title=re.match(r'^【(.*?)】', s).group(1), vol=vol, ps=[])
            secs.append(cur)
            continue
        if s and cur is not None:
            cur['ps'].append(s)
    return entries, secs


# 底本用私用区码位记未编码的字：U+E848 两处，《捕蛇者说》「挛{宛}」、《治安策》「{炙}戾」，
# 字的两个半边连着排。照全库写法收成 `{…}`（AGENTS.md 2b），字不补。
PUA = {'\ue848': None}


def tidy(p):
    p = p.strip()
    for bad in ('？。', '！。', '。。', '，，', '、、'):   # 底本的手民之误，收敛成一个
        p = p.replace(bad, bad[0])
    p = re.sub(r'([，。、；：？！])\1+', r'\1', p)
    if '\ue848' in p:                       # 私用区码位：与相邻的半个字一起收进 {}
        p = p.replace('大风、挛\ue848宛', '大风{挛宛}').replace('\ue848炙戾', '{炙戾}')
    return p


def guwen_title(e, s):
    """篇题：底本目次 → 通行本；目次本身有讹的按 TITLE，正文小节另写的按 SECTION_TITLE。"""
    return (TITLE.get(e['raw']) or TITLE.get(e['title'])
            or SECTION_TITLE.get(s['sec_title']) or e['title'])


def build():
    entries, secs = read_source()
    assert len(entries) == len(secs) == 222, (len(entries), len(secs))
    rows, books = [], {}
    for e, s in zip(entries, secs):
        title = guwen_title(e, s)
        ps = [tidy(p) for p in s['ps']]
        fix_text(title, ps, rows)
        fix_quote(title, ps, rows)
        assert ps, title
        books.setdefault(e['vol'], []).append(dict(
            author=e['author'], title=title, paragraphs=ps,
            notes=f'底本：reference/古文观止.txt 卷{e["vol"]}《{title}》，{e["src"]}；'
                  f'正文照录，异体字与异文沿底本，底本讹字逐条对通行本改（见 docs/古文观止勘正.tsv）',
            id=''))
    return entries, secs, books, rows


def dump(path, data):
    raw = open(path, encoding='utf-8').read() if os.path.exists(path) else ''
    m = re.search(r'\n( +)\S', raw)
    indent = len(m.group(1)) if m else 2
    out = json.dumps(data, ensure_ascii=False, indent=indent)
    with open(path, 'w', encoding='utf-8') as fp:
        fp.write(out + ('\n' if raw.endswith('\n') or not raw else ''))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--check', action='store_true')
    ap.add_argument('--out', default=os.path.join(ROOT, OUT))
    a = ap.parse_args()
    entries, secs, books, rows = build()
    if a.check:
        for e, s in zip(entries, secs):
            print(e['vol'], TITLE.get(e['raw'], e['title']), '|', s['sec_title'], '|',
                  e['author'], len(s['ps']))
        for r in rows:
            print('FIX', r)
        return
    total = 0
    for vol, title in VOLS:
        recs = books.get(vol, [])
        total += len(recs)
        dump(os.path.join(a.out, VOL_FILE[vol] + '.json'), recs)
        print(VOL_FILE[vol], len(recs), '篇', sum(len(r['paragraphs']) for r in recs), '段')
    print('合计', total, '篇')
    # 勘正明细
    with open(os.path.join(ROOT, 'docs/古文观止勘正.tsv'), 'w', encoding='utf-8', newline='') as fp:
        w = csv.writer(fp, delimiter='\t', lineterminator='\n')
        w.writerow(['篇目', '类别', '底本', '改用', '依据', '处数'])
        seen = set()
        for r in rows:
            key = (r['篇目'], r['类别'], r['底本'], r['改用'])
            if key in seen or not r['处数']:
                continue
            seen.add(key)
            w.writerow([r['篇目'], r['类别'], r['底本'], r['改用'], r['依据'], r['处数']])
        for t, orig, why in KEEP:
            w.writerow([t, '异文（不改）', orig, orig, why, 0])
    print('勘正', len(rows), '条 → docs/古文观止勘正.tsv')
    titles = [r['title'] for v, _ in VOLS for r in books[v]]
    write_meta(titles, entries, books)
    toc = fill_ids(titles, entries, books)
    print('目次', len(toc), '条；卷文件 12 个')


# ---- 目录、目次、版本说明 --------------------------------------------------
VOL_INTRO = {
    '一': '《古文觀止》卷一，周文，收文 18 篇，全出《左傳》。正文归 史书/春秋左氏传/zuozhuan.json，'
         '本册只在 古文观止·选目.json 留条目。',
    '二': '《古文觀止》卷二，周文，收文 16 篇，全出《左傳》。正文归 史书/春秋左氏传/zuozhuan.json，'
         '本册只在 古文观止·选目.json 留条目。',
    '三': '《古文觀止》卷三，周文，收文 22 篇：《國語》11、《公羊傳》3、《穀梁傳》2、《禮記·檀弓》6。',
    '四': '《古文觀止》卷四，秦文，收文 17 篇：《國策》14，李斯、屈原、宋玉各 1。國策 14 篇正文归 '
         '史书/战国策/zhanguoce.json，本册留 3 篇。',
    '五': '《古文觀止》卷五，秦文，收文 15 篇，全出《史記》。其中 11 篇保留正文，'
         '《五帝本紀贊》《項羽本紀贊》《孔子世家贊》《外戚世家序》正文归 史书/史记/shiji.json。',
    '六': '《古文觀止》卷六，汉文，收文 16 篇：《西漢文》13、《東漢文》2、《後漢文》2。',
    '七': '《古文觀止》卷七，六朝、唐文，收文 19 篇：三國至唐。',
    '八': '《古文觀止》卷八，唐文，收文 19 篇，全出韓愈。',
    '九': '《古文觀止》卷九，唐、宋文，收文 22 篇：柳宗元 11，宋人 11。',
    '十': '《古文觀止》卷十，宋文，收文 19 篇：歐陽修 10、蘇洵 4、蘇軾 5。',
    '十一': '《古文觀止》卷十一，宋文，收文 21 篇：蘇軾 13、蘇轍 3、曾鞏 2、王安石 3。',
    '十二': '《古文觀止》卷十二，明文，收文 18 篇：宋濂至張溥。',
}


def write_meta(titles, entries, books, out=os.path.join(ROOT, OUT)):
    """目录.json / 古文观止.json / 古文观止·选目.json。"""
    toc = json.load(open(os.path.join(out, '古文观止·选目.json'), encoding='utf-8')) \
        if os.path.exists(os.path.join(out, '古文观止·选目.json')) else []
    # 目次：卷次 / 篇题 / 作者 / 记录（本册 id 或整本的 id，由后面两步填）
    nun = {}
    rows = []
    for title, e in zip(titles, entries):
        nun[e['vol']] = nun.get(e['vol'], 0) + 1
        rows.append({'卷次': VOL_FILE[e['vol']] + '.json', '篇目': title,
                     '作者': e['author'], '记录': f"{VOL_FILE[e['vol']]}.json#"})
    dump(os.path.join(out, '古文观止·选目.json'), rows)
    # 目录：12 卷各一条空记录
    dump(os.path.join(out, '目录.json'), [
        {'author': '吳楚材、吳調侯', 'title': VOL_TITLE[v], 'paragraphs': [],
         'prologue': VOL_INTRO[v], 'id': ''} for v, _ in VOLS])
    dump(os.path.join(out, '古文观止.json'), [{
        'author': '吳楚材、吳調侯', 'title': '古文觀止', 'paragraphs': [],
        'prologue': '清康熙三十四年（1695）吳楚材、吳調侯編選，收東周至明代文章 222 篇，分十二卷。'
                    '底本為 repo 內 reference/古文观止.txt（簡體排印本，逐段帶句讀）。'
                    '《左傳》34 篇、《國策》14 篇、《史記》4 篇的正文歸整本，'
                    '本冊只在 古文观止·选目.json 留條目；選本保留的 170 篇正文照錄底本。'
                    '體例與勘誤見 docs/古文观止重建.md、docs/古文观止勘正.tsv。',
        'id': ''}])
    return rows


def fill_ids(titles, entries, books, out=os.path.join(ROOT, OUT)):
    """给 170 篇正文与 13 条说明记录发 id（规则同 scripts/backfill_ids.py），回填目次。"""
    sys.path.insert(0, os.path.join(ROOT, 'scripts'))
    import backfill_ids as bi
    seen = set()
    for vol, _ in VOLS:
        recs = json.load(open(os.path.join(out, VOL_FILE[vol] + '.json'), encoding='utf-8'))
        for r in recs:
            key = f"{r['author']}|{r['title']}|{''.join(r['paragraphs'])}"
            d = bi.work_hash(key)
            n = bi.ID_LEN
            while bi.base22(d, n) in seen:
                d = bi.work_hash(key + '#' * n)
                n += 1
            r['id'] = bi.base22(d, n)
            seen.add(r['id'])
        dump(os.path.join(out, VOL_FILE[vol] + '.json'), recs)
    for name in ('目录.json', '古文观止.json'):
        recs = json.load(open(os.path.join(out, name), encoding='utf-8'))
        for r in recs:
            key = f"{r['author']}|{r['title']}|{'|'.join(r['paragraphs'])}|{r.get('prologue', '')}"
            d = bi.work_hash(key)
            n = bi.ID_LEN
            while bi.base22(d, n) in seen:
                d = bi.work_hash(key + '#' * n)
                n += 1
            r['id'] = bi.base22(d, n)
            seen.add(r['id'])
        dump(os.path.join(out, name), recs)
    # 目次里的「记录」：正文还在本册的指本册 id，已归整本的填整本 id
    toc = json.load(open(os.path.join(out, '古文观止·选目.json'), encoding='utf-8'))
    by_title = {}
    for vol, _ in VOLS:
        for r in json.load(open(os.path.join(out, VOL_FILE[vol] + '.json'), encoding='utf-8')):
            by_title[(VOL_FILE[vol] + '.json', r['title'])] = r['id']
    for t in toc:
        t['记录'] += by_title[(t['卷次'], t['篇目'])]
    dump(os.path.join(out, '古文观止·选目.json'), toc)
    return toc


if __name__ == '__main__':
    main()


