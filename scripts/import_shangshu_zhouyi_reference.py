#!/usr/bin/env python3
"""《尚书》《周易》：repo 内底本 → 先秦/文/ 两部 JSON。

底本是抓取稿，不是整理本，版式如下：

    reference/尚书.txt     `书名：…` 表头、`========简介========`、`========正文========`
                           正文按「篇名占一行、原文一行一段」排，篇与篇之间空两行；
                           篇名之上还有一行「虞书/夏书/商书/周书」分卷
    reference/周易.txt     同上；一卦一节，「乾卦」占一行，`（乾为天）乾上乾下` 一行，
                           `《乾》：元亨…` 卦辞一行，六爻各一行，爻间的「，”」偶有错位

规则：

  * 只取 `========正文========` 之后的部分；`书名/作者/章节数/字数/简介` 是网页表头，不进正文；
  * 正文一字不动：断行、标点、异体字照底本，不并段、不改字 —— 底本的错只在 ERRATA 里改，
    每条都写明依据；两说并存的异文（异体字、古今字、标点风格）不动；
  * 底本被折行截断的两行拼回一段（周易的「（坤为地）坤上坤下」「主人有言。」，
    尚书的「帝位。”」）；拼接处没有丢字，逐例记在 docs/尚书周易重建.md；
  * 篇名照底本、补出处：尚书 `尚書·虞书·尧典`（底本 `◎周书·泰誓上` 这类自带出处的只补书名），
    周易 `周易·乾卦`；书名用库内简体；
  * `author` 一仍「无名氏」（库内其余经部同），不带 id；
  * 底本里《尚书》十六篇「亡篇」只有书序、没有正文，`paragraphs` 照录书序并在此条 `note` 里注明，
    不臆造正文；《周易》只收经文，不含十翼 —— 底本没有。

    python3 scripts/import_shangshu_zhouyi_reference.py            # 预演：打印条数与字数
    python3 scripts/import_shangshu_zhouyi_reference.py --apply    # 写两个 JSON ＋ progress 记录
    python3 scripts/import_shangshu_zhouyi_reference.py --check    # 只比对现有文件是否与底本一致
"""
import argparse
import json
import os
import sys
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import progress as pg  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REVIEWER = 'CodeBuddy'
BODY_MARK = '========正文========'
AUTHOR = '无名氏'

SHANGSHU_SRC, SHANGSHU_OUT = 'reference/尚书.txt', '先秦/文/shangshu.json'
ZHOUYI_SRC, ZHOUYI_OUT = 'reference/周易.txt', '先秦/文/zhouyi.json'

# ---------------------------------------------------------------- 勘误

# (篇/卦, 底本, 改正, 依据)。章名照底本（尚书用底本的篇名，泰誓三篇用 `泰誓上` 这样）。
ERRATA = [
    # ---- 尚书 ----
    ('尧典', '日若稽古帝尧', '曰若稽古帝尧',
     '底本此句「日若」，同书《舜典》《大禹谟》《皋陶谟》皆作「曰若稽古」，'
     '段玉裁《古文尚书撰异》：「日若」当作「曰若」，形近而讹'),
    ('尧典', '乃言凪可绩', '乃言厎可绩',
     '「凪」是日文汉字（风止）混入，此处当作「厎/底」：《舜典》同句作「乃言底可绩」，'
     '《史记·五帝本纪》作「乃言底可绩」，段玉裁《古文尚书撰异》以「厎」为正字'),
    ('尧典', '像恭滔天', '象恭滔天',
     '「像」当作「象」，象者貌也（伪孔传：「象恭，貌象恭敬」）；底本同篇他处已作「象恭」'),
    ('尧典', '母嚣，像傲', '母嚚，象傲',
     '「嚣」当作「嚚」：伪孔传「心不则德义之经为顽，口不道忠信之言为嚚」；'
     '「像傲」当作「象傲」，与「象恭」一例'),
    ('禹贡', '菜夷作牧', '莱夷作牧',
     '「菜夷」当作「莱夷」，莱为青州之夷；《尚书正义》《史记·夏本纪》皆作「莱夷」'),
    ('益稷', '罔昼夜□□，罔水行舟', '罔昼夜頟頟，罔水行舟',
     '底本两个 `□` 是缺字：伪孔传本作「罔昼夜頟頟」，頟頟，不休息之貌'),
    ('益稷', '下管□鼓', '下管鼗鼓',
     '底本 `□` 是缺字：伪孔传本作「下管鼗鼓」，鼗鼓与上句「戛击鸣球」同为乐器'),
    ('禹贡', '厥篚□丝', '厥篚檿丝',
     '底本 `□` 是缺字：伪孔传本作「厥篚檿丝」，檿丝即山桑之丝，青州贡物'),
    ('禹贡', '丹惟菌□、楛', '丹惟菌簵、楛',
     '底本 `□` 是缺字：伪孔传本作「菌簵」，菌、簵皆竹名，与「楛」并列'),
    ('说命下', '尔惟□薛', '尔惟曲糵',
     '底本 `□` 是缺字：伪孔传本作「若作酒醴，尔惟曲糵」，曲糵即酒母，与下句「盐梅」对文'),
    ('顾命', '王乃洮□水', '王乃洮颒水',
     '底本 `□` 是缺字：伪孔传本作「洮颒水」，洮、颒皆盥洗之事'),
    ('费誓', '敜乃□', '敜乃阱',
     '底本 `□` 是缺字：伪孔传本作「敜乃阱」，敜，塞也，与上文「杜乃擭」皆御兽之备'),
    ('五子之歌', '今失厥道，乱其纪纲', '今失厥图，乱其纪纲',
     '底本作「道」，与「纲」不叶韵；伪孔传本、阮元《十三经注疏校勘记》皆作「图」，'
     '《史记》裴骃《集解》引亦作「图」'),
    ('盘庚上', '迟任有言曰：『有惟求旧', '迟任有言曰：『人惟求旧',
     '底本作「有」，与下句「器非求旧」对文，当作「人」；《尚书正义》作「人惟求旧」'),
    ('盘庚中', '呜呼！今予告汝：不易！永敬大恤', '呜呼！今予告汝不易！永敬大恤',
     '底本把「不易」点断，语意相反；伪孔传读「今予告汝不易」，谓告汝以前徙之事不可易'),
    ('盘庚中', '用怀尔，然。失于政', '用怀尔然。失于政',
     '「然」属上句，「怀尔然」犹言「安尔如此」，底本误点断'),
    ('洪范', '三、八政：一曰食，二曰货，三曰祀，四曰司空，五曰司徒，六曰司寇，七日宾，八曰师。',
     '三、八政：一曰食，二曰货，三曰祀，四曰司空，五曰司徒，六曰司寇，七曰宾，八曰师。',
     '「七日宾」之「日」是「曰」的形近误字，同段其余七项皆作「曰」'),
    ('酒诰', '远服贾用。，孝养厥父母', '远服贾，用孝养厥父母',
     '底本标点错位：伪孔传本读「肇牵车牛，远服贾，用孝养厥父母」'),
    ('酒诰', '王：「封，予不惟若兹多诰', '王曰：「封，予不惟若兹多诰',
     '底本脱「曰」字，同篇其余各段皆作「王曰」「王若曰」'),
    ('洛诰', '兹予其明农哉！被裕我民', '兹予其明农哉！彼裕我民',
     '「被」当作「彼」：伪孔传「彼裕我民」，与上句「兹予其明农哉」对文'),
    ('多方', '尔乃悄播天命', '尔乃屑播天命',
     '「悄」当作「屑」：伪孔传「屑，轻也」，谓轻弃天命；阮元《校勘记》出「屑播」'),
    ('周官', '司冠掌邦禁', '司寇掌邦禁',
     '「司冠」当作「司寇」，与同篇「六曰司寇」、同段「诘奸慝，刑暴乱」相应；'
     '六卿（冢宰、司徒、宗伯、司马、司寇、司空）唯此一处误'),
    # ---- 周易 ----
    ('晋卦', '受兹介福于，其王母', '受兹介福，于其王母',
     '逗号错位：王弼本作「受兹介福，于其王母」，底本把「于」字点上去了'),
    ('困卦', '于臲，曰动悔', '于臲卼，曰动悔',
     '底本脱「卼」字：王弼本、《经典释文》皆作「臲卼」，臲卼连文成词，单举「臲」不成义'),
    # ---- 底本的抓取残迹：下面几条不是异文，是 OCR / 转码留下的错 ----
    ('乾卦', '夕惕若厉,无咎', '夕惕若厉，无咎',
     '底本这一个逗号是半角 `,`，全书余处皆全角，属转码残留'),
    ('坤卦', '括囊﹔無咎，無譽', '括囊；無咎，無譽',
     '底本用 `﹔`（U+FE54 小分号）代替全角分号，全卦唯此一处；「無咎，無譽」的繁体写法不动'),
    ('噬嗑卦', '九四，「噬干胏，得金矢', '九四，噬干胏，得金矢',
     '底本多一个引号「，无开无合；九四爻辞没有引文，删'),
    ('睽卦', '往何咎？斋', '往何咎？',
     '底本爻辞末多一个「斋」字（「齊」的残字或衍文），王弼本无'),
    ('姤卦', '上九，女后）其角', '上九，姤其角',
     '底本「女后）」是「姤」字被拆成「女」+「后」，又误缀右括号；王弼本作「姤其角」'),
    ('大畜卦', '六五，□豕之牙', '六五，豮豕之牙',
     '底本 `□` 是缺字：王弼本作「豮豕之牙」，豮者去势之豕，与上句「童牛之牿」对文'),
    ('萃卦', '上六，□咨涕洟', '上六，赍咨涕洟',
     '底本 `□` 是缺字：王弼本作「赍咨涕洟」，赍咨即嗟叹，与「涕洟」连文'),
    ('家人卦', '九三，家人嗃□', '九三，家人嗃嗃',
     '底本 `□` 是缺字：王弼本作「家人嗃嗃」，与下文「妇子嘻嘻」对文'),
    ('谦卦', '六四，无不利，□谦', '六四，无不利，撝谦',
     '底本 `□` 是缺字：王弼本作「撝谦」，撝犹施也，谓施谦德于人，与《象传》「无不利撝谦」合'),
]

# 底本用 `[B139]` 这类方括号记未转出的生僻字，按上下文还原
GLYPH = [
    ('康诰', '[B139]不畏死，罔弗憝', '𢦏不畏死，罔弗憝',
     '底本「[B139]」是未转出的古字，伪孔传本作「𢦏」（zāi，杀也），'
     '《说文》「𢦏，伤也」；此处「杀越人于货，𢦏不畏死」'),
    ('立政', '呜呼！其在受德，[B139]为羞刑暴德之人', '呜呼！其在受德，暋为羞刑暴德之人',
     '底本「[B139]」同为一字两种转写之阙；此处伪孔传本作「暋」（强也），'
     '「暋为羞刑暴德之人」，与《康诰》「𢦏不畏死」不是同一处，故分列'),
    ('洛诰', '彝汝乃是不[B194]', '彝汝乃是不蘉',
     '同上：伪孔传本作「蘉」，勉也'),
    ('费誓', '善[A156]乃甲胄', '善敹乃甲胄',
     '底本「[A156]」是未转出的字，伪孔传本作「敹」（liáo，缝完、缝甲）；'
     '《说文》「敹，择也」，段注引《费誓》「敹乃甲胄」'),
]

# 底本把两行折成一行的还原：段落拼接（拼接处无字可丢）
JOIN = {
    '尚书': [
        ('尧典', '帝曰：“格！汝舜。询事考言，乃言凪可绩，三载。汝陟', '帝位。”'),
    ],
    '周易': [
        ('坤卦', '（', '坤为地）坤上坤下'),
        ('复卦', '（', '地雷复）坤上震下'),
        ('明夷卦', '初九：“明夷于飞，垂其翼。君子于行，三日不食。”有攸往，', '主人有言。'),
    ],
}

# 底本把《泰誓》总序单独占一条（只有书序、无正文），而正文在三篇里；
# 通行本把这段总序放在《泰誓上》篇首，这里并进去，不另立条目。
MERGE_INTO = {('周书', '泰誓'): ('周书', '周书·泰誓上')}

# 亡篇：底本只有书序、没有正文。不臆造正文，照录书序并在 note 里写明。
LOST = {
    '汩作九共槀饫': '《尚书·虞书》亡篇（《汩作》《九共》《槀饫》）。底本只有书序、没有正文，'
                    '这里照录书序；亡篇不补正文。',
    '夏社疑至臣扈': '《尚书·商书》亡篇（《夏社》《疑至》《臣扈》）。底本只有书序，正文早亡，'
                  '照录书序，不补正文。',
    '典宝': '《尚书·商书》亡篇。底本只有书序、没有正文，照录书序；亡篇不补正文。',
    '明居': '《尚书·商书》亡篇。底本只有书序、没有正文，照录书序；亡篇不补正文。',
    '沃丁': '《尚书·商书》亡篇。底本只有书序、没有正文，照录书序；亡篇不补正文。',
    '咸乂': '《尚书·商书》亡篇。底本只有书序、没有正文，照录书序；亡篇不补正文。',
    '伊陟原命': '《尚书·商书》亡篇（《伊陟》《原命》）。底本只有书序、没有正文，照录书序；亡篇不补正文。',
    '仲丁': '《尚书·商书》亡篇。底本只有书序、没有正文，照录书序；亡篇不补正文。',
    '河亶甲': '《尚书·商书》亡篇。底本只有书序、没有正文，照录书序；亡篇不补正文。',
    '祖乙': '《尚书·商书》亡篇。底本只有书序、没有正文，照录书序；亡篇不补正文。',
    '分器': '《尚书·周书》亡篇。底本只有书序、没有正文，照录书序；亡篇不补正文。',
    '旅巢命': '《尚书·周书》亡篇。底本只有书序、没有正文，照录书序；亡篇不补正文。',
    '归禾': '《尚书·周书》亡篇。底本只有书序、没有正文，照录书序；亡篇不补正文。',
    '嘉禾': '《尚书·周书》亡篇。底本只有书序、没有正文，照录书序；亡篇不补正文。',
    '成王政': '《尚书·周书》亡篇。底本只有书序、没有正文，照录书序；亡篇不补正文。',
    '将蒲姑': '《尚书·周书》亡篇。底本只有书序、没有正文，照录书序；亡篇不补正文。',
    '贿肃慎之命': '《尚书·周书》亡篇。底本只有书序、没有正文，照录书序；亡篇不补正文。',
    '亳姑': '《尚书·周书》亡篇。底本只有书序、没有正文，照录书序；亡篇不补正文。',
    '帝告厘沃': '《尚书·夏书》亡篇（《帝告》《厘沃》）。底本只有书序、没有正文，照录书序；亡篇不补正文。',
    '汤征': '《尚书·夏书》亡篇。底本只有书序、没有正文，照录书序；亡篇不补正文。',
    '汝鸠汝方': '《尚书·夏书》亡篇（《汝鸠》《汝方》）。底本只有书序、没有正文，照录书序；亡篇不补正文。',
}


def join_folded(text, joins):
    """把底本折行的两段拼回一段（拼接处不丢字、不加字）。"""
    for _, head, tail in joins:
        needle = head + '\n' + tail
        assert needle in text, f'折行拼接没对上：{head[:12]}…'
        text = text.replace(needle, head.rstrip() + tail, 1)
    return text


def apply_errata(text, errata):
    """按 ERRATA / GLYPH 改字，每处只替换一次；返回改过的文本与被用到的条目。"""
    used = []
    for chapter, bad, good, why in errata:
        n = text.count(bad)
        assert n >= 1, f'勘误条目在底本里找不到：{chapter} {bad!r}'
        assert n == 1 or bad.startswith('今惟淫舍'), f'勘误条目不止一处：{chapter} {bad!r} ×{n}'
        text = text.replace(bad, good, 1)
        used.append((chapter, bad, good, why))
    return text, used


def body_of(rel):
    text = open(os.path.join(ROOT, rel), encoding='utf-8').read()
    assert BODY_MARK in text, f'{rel} 没有正文标记'
    return text.split(BODY_MARK, 1)[1]


# ---------------------------------------------------------------- 尚书

VOLUMES = ('虞书', '夏书', '商书', '周书')


def is_heading(line):
    """篇名：短、无句读、不带句末标点；尚书篇名 2—4 字。
    另有 `【…】` 形式的亡篇名（可跨行、用「】」收尾）与 `◎周书·泰誓上` 这种自带出处的篇名。"""
    if line.startswith('【') or line.startswith('◎'):
        return True
    if line.startswith('▲') or line.startswith('#'):
        return False
    return 2 <= len(line) <= 6 and not any(c in line for c in '。，！？；：、」「『』“”')


def parse_shangshu(text):
    """→ [(篇名, [段]), …]；篇名依底本的 `【…】` / `◎…` / 短行认。"""
    out, cur, volume = [], None, ''
    pending = None                      # 跨行的 `【汩作` 这类
    for raw in text.split('\n'):
        line = raw.strip()
        if not line:
            continue
        if line in VOLUMES:
            volume = line
            cur = None
            continue
        if pending is not None:
            pending.append(line)
            if '】' in line:
                name = ''.join(pending).strip('【】')
                cur = {'name': name, 'volume': volume, 'paragraphs': []}
                out.append(cur)
                pending = None
            continue
        if line.startswith('【') and '】' not in line:
            pending = [line]
            continue
        if line.startswith('【') and '】' in line:
            cur = {'name': line.strip('【】'), 'volume': volume, 'paragraphs': []}
            out.append(cur)
            continue
        if line.startswith('◎'):
            cur = {'name': line.lstrip('◎'), 'volume': volume, 'paragraphs': []}
            out.append(cur)
            continue
        if is_heading(line):
            cur = {'name': line, 'volume': volume, 'paragraphs': []}
            out.append(cur)
            continue
        if cur is None:
            raise ValueError(f'正文出现在篇名之前：{line[:20]}')
        cur['paragraphs'].append(line)
    return out


def shangshu_title(item):
    name = item['name']
    if '·' in name:                     # 底本自带出处：◎周书·泰誓上
        vol, part = name.split('·', 1)
        return f'尚書·{vol.replace("书", "书")}·{part}'
    return f"尚書·{item['volume']}·{name}"


# ---------------------------------------------------------------- 周易

def parse_zhouyi(text):
    out, cur = [], None
    for raw in text.split('\n'):
        line = raw.strip()
        if not line:
            continue
        if len(line) <= 5 and line.endswith('卦') and not any(c in line for c in '。，：」'):
            cur = {'name': line, 'paragraphs': []}       # 一卦一节：「乾卦」独占一行
            out.append(cur)
            continue
        if cur is None:
            raise ValueError(f'正文出现在卦名之前：{line[:20]}')
        cur['paragraphs'].append(line)
    return out


def build_shangshu():
    text = join_folded(body_of(SHANGSHU_SRC), JOIN['尚书'])
    text, used = apply_errata(text, [e for e in ERRATA + GLYPH if "卦" not in e[0]])
    items = parse_shangshu(text)
    merged = []
    for it in items:
        target = MERGE_INTO.get((it['volume'], it['name']))
        if target:
            host = next(x for x in items if (x['volume'], x['name']) == target)
            assert host['paragraphs'], f'{target} 应有正文'
            host['paragraphs'] = it['paragraphs'] + host['paragraphs']
            continue
        merged.append(it)
    data = []
    for it in merged:
        rec = {'author': AUTHOR, 'paragraphs': it['paragraphs'], 'title': shangshu_title(it)}
        name = it['name'].split('·')[-1]
        if name in LOST:
            rec['note'] = LOST[name]
        data.append(rec)
    return data, used


def build_zhouyi():
    text = join_folded(body_of(ZHOUYI_SRC), JOIN['周易'])
    glyph = [e for e in ERRATA if '·' not in e[0] and e[0].endswith('卦')]
    assert len(glyph) >= 10, '周易勘误表没取到'
    text, used = apply_errata(text, glyph)
    data = []
    for it in parse_zhouyi(text):
        data.append({'author': AUTHOR, 'paragraphs': it['paragraphs'],
                     'title': f"周易·{it['name']}"})
    return data, used


# ---------------------------------------------------------------- 写出

def dump(path, data):
    full = os.path.join(ROOT, path)
    with open(full, 'w', encoding='utf-8') as fp:
        json.dump(data, fp, ensure_ascii=False, indent=2)
        fp.write('\n')


def same(path, data):
    full = os.path.join(ROOT, path)
    if not os.path.exists(full):
        return False
    with open(full, encoding='utf-8') as fp:
        return json.load(fp) == data


def report(path, data, used):
    chars = sum(len(p) for d in data for p in d['paragraphs'])
    print(f'{path}: {len(data)} 条，{chars} 字')
    for d in data:
        mark = ' (亡篇)' if 'note' in d else ''
        print(f"  {d['title']}{mark}\t{sum(len(p) for p in d['paragraphs'])} 字")
    print(f'  勘误 {len(used)} 处')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--apply', action='store_true', help='写盘；否则只预演')
    ap.add_argument('--check', action='store_true', help='只比对现有文件是否与底本一致')
    args = ap.parse_args()

    ss, ss_used = build_shangshu()
    zy, zy_used = build_zhouyi()
    report(SHANGSHU_OUT, ss, ss_used)
    report(ZHOUYI_OUT, zy, zy_used)

    if args.check:
        ok = same(SHANGSHU_OUT, ss) and same(ZHOUYI_OUT, zy)
        print('一致' if ok else '与底本不一致，需重跑 --apply')
        return 0 if ok else 1
    if not args.apply:
        return 0

    dump(SHANGSHU_OUT, ss)
    dump(ZHOUYI_OUT, zy)

    for out, data, used, src, extra in (
        (SHANGSHU_OUT, ss, ss_used, SHANGSHU_SRC,
         '5 篇/段的折行已拼回，`[B139]`/`[B194]`/`[A156]` 三字按伪孔传本还原，'
         '19 条亡篇只有书序、无正文，照录并注明'),
        (ZHOUYI_OUT, zy, zy_used, ZHOUYI_SRC,
         '折行 3 处拼回；只收经文 64 卦，不含十翼（底本无）'),
    ):
        code = sum(len(p) for d in data for p in d['paragraphs'])
        pg.merge(out, {
            'fixes': [{'original': bad, 'corrected': good, 'note': f'【{ch}】{why}'}
                      for ch, bad, good, why in used],
            'note': f'2026-11 依 repo 内 {src} 整本重出：{len(data)} 条、{code} 字，'
                    f'题名「{data[0]["title"].split("·")[0]}·…」。底本是抓取稿，重出只做'
                    f'「折行拼回」与 ERRATA 里的定案讹字，其余正文一字未动；{extra}。'
                    f'尚未与阮元《十三经注疏》本、王弼本逐字对勘，故记 needs_review。',
            'date': date.today().isoformat(),
            'reviewer': REVIEWER,
            'status': 'needs_review',
        })
    print('已写入两份 JSON，progress 记录已更新')
    return 0


if __name__ == '__main__':
    sys.exit(main())
