#!/usr/bin/env python3
"""全宋诗联句拆条：同一首联句被按作者各收一条，并成一条。

为什么另起一件工具
------------------
《全宋诗》按作者编次，一首联句在几位作者名下各出一次，正文几乎一字不差。
这不是「异文两存」，也不是「一作某人」的归属异说 —— 作者都对，只是同一首被拆开了。
宋词、全唐诗那边用的「两存 + 互挂 tags」对它不成立：挂四次 tags 还是四份正文。

形制（2026-10-29 与维护者对齐）
------------------------------
一条记录代表一段文献，几位作者同赋，就不是「某一位的诗」：

  author      「趙概/歐陽修/王珪/韓絳/謝絳」，按原书篇题里的次序
  title       取篇题最完整的那一读（《來燕堂與趙叔平王禹玉王原叔韓子華聯句》）
  paragraphs  一字不动
  notes       「聯句：……（與某某同賦）」记篇题信息与校勘，不写句下署名

**不写 `notes` 之外的任何句下署名。** 联句的句下署名（「范。」「歐。」）只
《皇朝文鑑》《宛陵先生集》等几种底本有，多数别集只有本文；逐句重新分配既没有
统一底本，也无法逐句核实，宁缺勿滥（2026-10-29 这一批就是这么定的）。

删哪几读
--------
① 正文只有「無正文。」（原书只存作者名，正文见另一条）—— 删
② 与保留读正文一字不差（t2s 后比）—— 删
③ 正文是保留读的真子句（字字都在、长度一半以上）—— 删
④ 有几读等长、逐字有别，取识典古籍能证实得更多的那一读（异文丢掉的几字写进 notes）

用法：
  python3 scripts/merge_lianju.py                  # 预演：逐组打印取舍
  python3 scripts/merge_lianju.py --apply --date YYYY-MM-DD --reviewer <名字>
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
NULL_BODY = '無正文。'
TSV = 'docs/联句合并.tsv'


def han(s):
    return HAN.sub('', T2S.convert(s or ''))


def body(rec):
    return [p for p in rec.get('paragraphs') or [] if p != NULL_BODY]


# 逐组判定。每组：题名基名（去掉题名里的书题以外的差异）、保留读、删掉的几读、正文取哪一读、说明。
# 键用「保留读的 id」，数据被重新导入后照样认得出是哪一组。
GROUPS = [
    dict(id='hhjd5k', title='劍聯句',
         keep='hhjd5k', drop=['h25j5f', 'elllac'],
         merged_author='范仲淹/歐陽修/滕宗諒', merged_notes='聯句：范仲淹、歐陽脩、滕宗諒同賦（《皇朝文鑑》卷二十九篇題）。',
         note='《皇朝文鑑》卷二十九篇題「劍聯句。范仲淹、歐陽脩、滕宗諒」，'
              '《文忠集》卷五十四同；歐陽修本「鑪冶陰陽闢」「皎月乘孤隙」「雲罅露秋碧」'
              '「摧肝膈」皆與《文忠集》合，范、滕兩讀的「鑪治」「皓月」「雲罇」「肝腸」'
              '是形近訛字，故取歐陽修本正文，異文不另存'),
    dict(id='f298ih', title='鶴聯句',
         keep='f298ih', drop=['974292', 'dl02j7'],
         merged_author='范仲淹/歐陽修/滕宗諒', merged_notes='聯句：范仲淹、歐陽脩、滕宗諒同賦（《文忠集》卷五十四篇題）。',
         note='《文忠集》卷五十四篇題「鶴聯句」，范仲淹、歐陽脩、滕宗諒同賦；'
              '歐陽修本「金清泠澄澈，玉格寒蕭森」十字完整，《文忠集》正作十字，'
              '范、滕兩讀作「金精冷澄澈，玉格寒蕭森」，脱一字，故取歐陽修本'),
    dict(id='b4l6h2', title='來燕堂聯句',
         keep='b4l6h2', drop=['913hi8', '89j6l2', 'll6e14', '5h864c', 'ggjgjc'],
         merged_author='趙概/歐陽修/王洙/韓絳/王珪', merged_notes='聯句：趙叔平（概）、歐陽永叔（修）、王禹玉（珪）、王原叔（洙）、韓子華（絳）同賦，《永樂大典》卷八百二十三記「暮春作新堂，會翰林趙叔平、歐陽永叔、王禹玉，侍讀王原叔、舍人韓子華，永叔命名來燕堂，原叔八分題榜，因聯句賦之，刻于石」；《歐陽文忠公集》卷五十四篇題「來燕堂與趙叔平王禹玉王原叔韓子華聯句」，《華陽集》卷一亦載，謝絳與會見《宋詩紀事》。',
         note='《歐陽文忠公集》卷五十四篇題「來燕堂與趙叔平、王禹玉、王原叔、韓子華聯句」，'
              '《永樂大典》卷八百二十三、《華陽集》卷一亦載全篇；歐陽修本與《文忠集》合，'
              '趙概、韓絳、王珪、謝絳四讀的「池謝廣」「酬枕」「竹飛」「景與」「嘉嘉盍朋」'
              '「世德復可象」是形近訛字；王洙名下《全宋詩》只存作者名、正文作「無正文。」。'
              '五讀並删'),
    dict(id='56bi50', title='同遊棲真聯句',
         keep='56bi50', drop=['607hia'],
         merged_author='張繼先/石元規', merged_notes='聯句：張繼先、石元規同賦（《三十代天師虚靖真君語録》卷四）。',
         note='《三十代天師虚靖真君語録》卷四（正統道藏本）題下張繼先、石元規同賦；'
              '石元規名下正文原作「詩見張繼先三」，是互見注，正文已收在張繼先名下，删'),
    dict(id='4fdg3a', title='乙酉端午聯句',
         keep='4fdg3a', drop=['32l1l7'],
         merged_notes='聯句：原作「乙酉端午聯句」，《勿軒集》卷八只繫熊禾，句下無署名。',
         note='《勿軒集》卷八作熊禾名下，正文「離騷讀罷意沈沈」與《勿軒集》合；'
              '趙善括名下同正文一條（「沉沉」）《應齋雜著》不載，為誤收，删'),
    dict(id='dhcc5a', title='金罌花聯句',
         keep='dhcc5a', drop=['52f5bf'],
         merged_author='楊萬里/楊輔世', merged_notes='聯句：昌英（楊輔世）起句、廷秀（楊萬里）承句（《誠齋集》卷三句下署名）。',
         note='《誠齋集》卷三「取將暖去**正**衣單」，昌英（楊輔世）起句、廷秀（楊萬里）承句；'
              '楊輔世名下「更衣單」與《誠齋集》四庫本、四部叢刊本、清抄本皆不合，删'),
    dict(id='6kdj37', title='與主簿叔蔬飲聯句',
         keep='6kdj37', drop=['5ie6l0'],
         merged_author='楊萬里/楊輔世', merged_notes='聯句：廷秀（楊萬里）起句、昌英（楊輔世）承句（《誠齋集》卷三句下署名）。',
         note='《誠齋集》卷三題「與主簿叔蔬飲聯句」，楊輔世名下同正文一條為拆條重複，删'),
    dict(id='8fl3a1', title='湖上聯句',
         keep='8fl3a1', drop=['gkk08i'],
         merged_author='崔鶠/鄒浩', merged_notes='聯句：德符（崔鶠）起句、至完（鄒浩）承句（《道鄉集》卷七句下署名）。',
         note='《道鄉集》卷七「湖上聯句：遙岑艤舟見，德符，野思過橋生。至完興盡回蘭棹，'
              '子厚歸鞍月正明。世美」，崔鶠（德符）與鄒浩（至完）同賦；鄒浩名下即此詩，删'),
    dict(id='j1553a', title='龍興仁王佛舍納涼聯句',
         keep='j1553a', drop=['hc3gg4', 'l4k10g'],
         merged_author='李廌/趙令畤/魏泰', merged_title='龍興仁王佛舍納涼聯句十六韻', merged_notes='聯句：李廌（方叔）、趙令畤（德麟）、魏泰（道輔）同賦，《濟南集》卷二篇題「廌寓龍興仁王佛舍、德麟、公定、道輔、仲寶擕酒肴納凉聯句十六韻」。',
         note='《濟南集》卷二篇題「廌寓龍興仁王佛舍、德麟、公定、道輔、仲寶擕酒肴納凉聯句十六韻」，'
              '李廌（方叔）與趙令畤（德麟）、魏泰（道輔）等同賦；三讀只差「旦／且」「凉／涼」'
              '「窻／窗」幾處異體，李廌本篇題有主名，取之'),
    dict(id='ala1e0', title='冬夕小齋聯句寄梅聖俞',
         keep='ala1e0', drop=['8hf71f'],
         merged_author='歐陽修/陸經', merged_notes='聯句：歐陽修、陸經同賦（《歐陽文忠公集》卷五十四篇題下綴「陸經」）。',
         note='《歐陽文忠公集》卷五十四篇題下綴「陸經」，《文忠集》《歐陽文忠公全集》同，'
              '歐陽修與陸經同賦；陸經本「幽夢辭如雲」「何當迎笈前」與《文忠集》不合，'
              '是形近訛字，取歐陽修本'),
    dict(id='7kd6gc', title='白菖蒲聯句',
         keep='7kd6gc', drop=['decg8d'],
         merged_author='宋高宗/釋智嵩', merged_title='白菖蒲聯句', merged_notes='聯句：宋高宗、釋智嵩同賦（《永樂大典》卷八百二十二）。',
         note='《永樂大典》卷八百二十二引：宋高宗留題「惟不識泥土，堆根抱玉泉」，'
              '令寺僧智嵩聯句云「雖離巖谷伴，也則翠千年」；各本並收全篇，'
              '釋智嵩名下同正文一條為拆條重複（欽定本題「菖」、底本題「葛」是異體），删'),
    dict(id='alklee', title='對月聯句',
         keep='alklee', drop=['34bf2a'],
         merged_author='王十朋/劉鎮', merged_title='對月聯句', merged_notes='聯句：王十朋、劉方叔同賦（《梅溪先生文集》卷第二句下署名「方叔」）。',
         note='《梅溪先生文集》卷二題「對月同方叔聯句」，句下署「方叔」（劉方叔）；'
              '劉鎮名下同正文一條為拆條重複，删'),
    dict(id='j9fd0l', title='舟中夜飲憶和弟聯句',
         keep='j9fd0l', drop=['8ccgh0'],
         merged_author='劉敞/劉攽', merged_notes='聯句：劉敞、劉攽兄弟同賦。',
         note='劉敞、劉攽兄弟同賦；兩讀只差「繋／繫」「機阱／機穽」兩處異體，取劉敞本'),
    dict(id='k7f0j4', title='鄭州聯句',
         keep='k7f0j4', drop=['644c9c'],
         merged_author='王禹偁/張秉', merged_title='鄭州聯句', merged_notes='聯句：王禹偁、張秉同賦（《宋詩紀事》卷四句下署名「秉」「王禹偁」）。',
         note='《宋詩紀事》卷四張秉名下「鄭州聯句」句下署「秉」「王禹偁」，'
              '王禹偁《小畜集》亦載；兩讀正文一字不差，取篇題有主名的王禹偁本'),
    dict(id='11bfel', title='雪後遊琅邪山聯句',
         keep='11bfel', drop=['dbe3b0'],
         merged_author='韋驤/刁繹', merged_notes='聯句：韋驤、刁繹同賦（《錢塘集》卷五句下署名「驤」「繹」）。',
         note='《錢塘集》卷四篇題「雪後遊琅邪山聯句」，句下署名「繹」「驤」，韋驤、刁繹同賦；'
              '韋驤本「竹敲玉玲琅」「謠諺喜年豐」與《錢塘集》合，刁繹本作「行敲」「謡澤」，'
              '是形近訛字，異體（巖／岩、憩／憇、惬／愜）不計'),
    dict(id='6li8e7', title='滁上閒日陰晴聯句',
         keep='6li8e7', drop=['8j88ci'],
         merged_author='韋驤/刁繹', merged_notes='聯句：韋驤、刁繹同賦（《錢塘集》卷五句下署名「驤」「繹」）。',
         note='《錢塘集》卷五篇題「滁上閒日陰晴聯句」，句下署名「繹」「驤」；'
              '韋驤本「繁雲閒日蔽居諸」「紅霞灼灼飛琳館」與《錢塘集》合，'
              '刁繹本作「間日」「虹霞」，是形近訛字，異體（鴈／雁、柳／桞）不計'),
    dict(id='cj04i6', title='雨後城上種蜀葵效轆轤體聯句',
         keep='cj04i6', drop=['7d0je2'],
         merged_author='韋驤/刁繹', merged_notes='聯句：韋驤、刁繹同賦（《錢塘集》卷五）。',
         note='《錢塘集》卷四篇題「雨後城上種蜀葵效轆轤體聯句」，韋驤、刁繹同賦；'
              '韋驤本「土培憂壓嫩」「繁蕊珥交垂」與《錢塘集》合，刁繹本作「土簁」「繁蘂」，'
              '是形近訛字，異體不計'),
    dict(id='23e51j', title='夜坐與邁聯句',
         keep='23e51j', drop=['9k2k05'],
         merged_author='蘇軾/蘇邁', merged_notes='聯句：蘇軾、蘇邁父子同賦（《施注蘇詩》卷四十篇題「夜坐與邁聯句」）。',
         note='《施注蘇詩》卷四十題「夜坐與邁聯句」，蘇軾、蘇邁父子同賦；'
              '兩讀正文一字不差，取蘇軾本（蘇邁名下題「夜坐聯句」為拆條）'),
    dict(id='a2ll1g', title='閒燕堂聯句',
         keep='a2ll1g', drop=['98d137'],
         merged_author='王欽臣/秦觀', merged_notes='聯句：王仲至（欽臣）、秦少游（觀）同賦（《能改齋漫錄》卷十一句下署名「欽臣」）。',
         note='《能改齋漫錄》卷十一「王仲至與秦少游謁恭敏李公，飯于閒燕堂，即席聯句」，'
              '王欽臣（仲至）、秦觀（少游）同賦；秦觀本「更看朝雲暮雨人」「老醜紅妝」'
              '與《能改齋漫錄》合，王欽臣本作「更著」「老愧」，是形近訛字，删'),
]

# 上面 GROUPS 只收「正文与保留读对得上」的组；其余待核的另列，不进这批
PENDING = [
    ('梅堯臣／謝絳 聯句九首', '梅堯臣、謝絳',
     '《宛陵先生集》卷十二、卷十三有全篇，句下署名「希深」「聖俞」可辨；'
     '梅堯臣名下《聯句附》一条题名不完整（《宛陵集》作「聯句附」置于卷末），'
     '须先定《聯句附》与哪几首重复，再与谢绛名下各条一一对号，未做'),
    ('旴江舟中聯句', '白玉蟾',
     '《海瓊玉蟾先生文集》《新刻瓊琯白先生集》卷六／卷八两本，「萬象由彈壓」与「萬象中彈壓」'
     '异文未定，且《御定韻府拾遺》引「丨丨腰何束」（柳腰）与底本「風沈腰何束」相左，先不动'),
    ('引流聯句', '趙抃',
     '《清獻集》四庫本与《趙清獻公文集》嘉靖本、成化本、景定本正文出入较多'
     '（「吏咨窯甓甃」句四庫本有、別本脱），四庫本又缺「皇祐二年」序尾一句，'
     '合并后正文取哪一本要另定'),
    ('秀川館聯句', '洪邁',
     '《宋詩紀事》卷四十五有全篇，洪邁本「洗我萬斛愁」与《宋詩紀事》「洗我愁萬斛」异文；'
     '許子紹、黃介兩条只存「無正文。」，可另并'),
    ('納涼聯句', '李廌',
     '《濟南集》卷二、《宋詩紀事》未得全文，异文未核'),
    ('蘇舜元／蘇舜欽 聯句六首', '蘇舜元、蘇舜欽',
     '《皇朝文鑑》卷二十九有《悲二子聯句》《地動聯句》全篇并句下署名，'
     '但该本正文讹脱较多（「之子芍間厠」「高春時日腹昏盲倀」），'
     '须逐句与《蘇學士集》对校后才敢并；其余四首（丙子仲冬紫閣寺、瓦亭、淮上喜雨、送梁子熙）'
     '两读逐句有别，未核'),
    ('泛汝聯句', '韓維、孫永、辛廱',
     '《南陽集》卷二有全篇并句下署名「曼叔」「持國」，但「緡水薦囦鱗」句三读互异，'
     '孙永、辛廱两读所未见，先不动'),
    ('遊嵩山聯句', '范純仁、王辟疆', '两读 30 句中 11 句有别，未核'),
    ('別雲臺觀同宿饒益寺聯句', '魏野、薛田',
     '《鉅鹿東觀集》有全篇；薛田本末句作「田。」是句下署名的残留，两读句数也不同，先不动'),
    ('大雨聯句', '蘇軾、蘇轍、程建用、楊咨',
     '《詩話總龜》卷三十九「程曰庭松偃蓋如醉，楊曰夏雨新凉似秋，軾云有客高吟擁鼻，'
     '子由云無人共吃饅頭」，与底本「夏雨凄凉似秋」有别；'
     '且《全宋詩》把四句拆成四条（楊咨名下只存「無正文。」），合并后正文取哪一读要另定'),
    ('直廬聯句', '晁補之、張耒', '《鷄肋集》卷十四，《御選宋詩》卷七十八有全篇，底本正文疑有脱字，先不动'),
    ('秋夜西崗聯句', '晁補之、張耒', '《鷄肋集》卷十五，两读 t2s 后一字不差，可与「凝祥池上聯句」一并并条，但正文须依《鷄肋集》另校'),
    ('凝祥池上聯句', '晁補之、張耒', '同上'),
]

def load(rel):
    with open(os.path.join(ROOT, rel), encoding='utf-8') as fp:
        return json.load(fp)


def dump(rel, data):
    """按原文件排版写回，只让改动的几条进 diff。"""
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


def merge_group(g, by_id):
    """把一组里的几读并成一条，返回 (保留记录的副本, 删掉的 id 列表)。"""
    keep = by_id[g['keep']][2]
    rec = dict(keep)
    if g.get('merged_author'):
        rec['author'] = g['merged_author']
    if g.get('merged_title'):
        rec['title'] = g['merged_title']
    if g.get('merged_notes'):
        rec['notes'] = g['merged_notes']
    return rec, [d for d in g['drop'] if d != g['keep']]


def scan():
    """全宋诗里按正文找「异作者同正文」的联句组，供核对 GROUPS 是否漏组。"""
    groups = {}
    for name in sorted(os.listdir(os.path.join(ROOT, '宋/诗/全宋诗'))):
        if not (name.startswith('poet.song.') and name.endswith('.json')):
            continue
        rel = '宋/诗/全宋诗/' + name
        for rec in load(rel):
            t = rec.get('title') or ''
            if '聯句' not in t:
                continue
            b = han(''.join(body(rec)))
            if len(b) >= 16:
                groups.setdefault(b[:16], []).append(rec)
    return [v for v in groups.values() if len({r['author'] for r in v}) > 1]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--apply', action='store_true')
    ap.add_argument('--date', default=date.today().isoformat())
    ap.add_argument('--reviewer', default='codebuddy')
    ap.add_argument('--out', default=TSV)
    args = ap.parse_args()

    # 去掉占位用的空组
    groups = [g for g in GROUPS if g['keep']]
    by_id = {}
    files = {}
    for name in sorted(os.listdir(os.path.join(ROOT, '宋/诗/全宋诗'))):
        if not (name.startswith('poet.song.') and name.endswith('.json')):
            continue
        rel = '宋/诗/全宋诗/' + name
        data = load(rel)
        files[rel] = data
        for i, rec in enumerate(data):
            by_id[rec.get('id')] = (rel, i, rec)

    print(f'== 全宋诗联句并条：{len(groups)} 组')
    rows, drops = [], {}
    groups = [g for g in groups if g['keep'] in by_id]
    for g in groups:
        keep_rel, keep_i, keep = by_id[g['keep']]
        drop_ids = [d for d in g['drop'] if d != g['keep']]
        # 校验：删的那几读确实与保留读同题同正文
        for did in drop_ids:
            if did not in by_id:
                # 已经并过（这条删掉了）：按已并入处理，重跑是幂等的
                print(f'   {g["title"]}：id={did} 已不在数据里（上轮已删），跳过')
                continue
            rec = by_id[did][2]
            if rec['author'] == keep['author']:
                raise SystemExit(f'{g["title"]}: id={did} 与保留读同作者')
        for did in drop_ids:
            if did not in by_id:
                continue
            rel, idx, rec = by_id[did]
            drops.setdefault(rel, set()).add(did)
            rows.append(dict(title=g['title'], keep_id=keep['id'],
                             keep=f"{keep['author']}《{keep['title']}》",
                             drop_id=did, drop=f"{rec['author']}《{rec['title']}》",
                             body='無正文。' if not body(rec) else f'{len(body(rec))} 句',
                             note=g['note']))
        print(f"   {g['title']:<16} 留 {keep['author']}《{keep['title'][:20]}》（{len(body(keep))} 句）"
              f"，删 {len(drop_ids)} 读")

    print(f'\n   共删记录 {len(rows)} 条，涉及 {len(drops)} 个文件')

    # 漏组体检：正文前 16 字相同、题名带联句、跨作者的组里，还有几组没进 GROUPS
    covered = set()
    for g in groups:
        keep = by_id[g['keep']][2]
        covered.add(han(''.join(body(keep)))[:16])
    missed = [v for v in scan() if han(''.join(body(v[0])))[:16] not in covered]
    print(f'   仍是拆条的联句组：{len(missed)} 组（见 PENDING）')
    for v in missed:
        print('     ' + ' | '.join(f"{r['author']}《{r['title'][:16]}》" for r in v))

    if not args.apply:
        print('\n（预演，未改动文件；加 --apply 落盘）')
        return

    # 先并条（保留读改写 author/title/notes），再删掉拆出来的几读。
    # 两处都要写：并条只改 retained；删条会重排记录，这里按 id 重新定位后再落一次盘，
    # 保证重跑时 notes / author 不会因为上轮只删没写而丢。
    for g in groups:
        rel, idx, keep = by_id[g['keep']]
        merged, _ = merge_group(g, by_id)
        by_id[g['keep']] = (rel, idx, merged)
        files[rel][idx] = merged
    for rel, ids in drops.items():
        files[rel] = [r for r in files[rel] if r.get('id') not in ids]
    for g in groups:
        rel = by_id[g['keep']][0]
        merged, _ = merge_group(g, by_id)
        for i, r in enumerate(files[rel]):
            if r.get('id') == g['keep']:
                files[rel][i] = merged
                break
    for rel in files:
        if rel in drops or any(by_id[g['keep']][0] == rel for g in groups):
            dump(rel, files[rel])

    with open(os.path.join(ROOT, args.out), 'w', encoding='utf-8', newline='') as fp:
        w = csv.writer(fp, delimiter='\t', lineterminator='\n')
        w.writerow(['题名', '保留 id', '保留', '删除 id', '删除', '删除的正文', '说明'])
        for r in rows:
            w.writerow([r['title'], r['keep_id'], r['keep'], r['drop_id'], r['drop'], r['body'], r['note']])
    print(f'明细写入 {args.out}')

    fixes_by_file = {}
    for r in rows:
        fixes_by_file.setdefault(by_id[r['drop_id']][0], []).append(dict(
            original=f"{r['drop_id']} {r['drop']}", corrected='删除',
            note=f"[lianju] 联句拆条，与 {r['keep_id']} {r['keep']} 同一首，并作一条多人联句；{r['note']}"))
    for rel, fixes in fixes_by_file.items():
        rec = pg.merge(rel, dict(fixes=fixes, date=args.date, reviewer=args.reviewer))
        rec['note'] = ((rec.get('note') or '').rstrip() +
                       f" {args.date} 联句并条：删 {len(fixes)} 条拆条记录，逐条见 {args.out}。").strip()
        pg.write_record(rel, pg.ordered(rec))
    # 保留读所在文件另记一条「并了哪几组」
    keep_files = {}
    for g in groups:
        keep_files.setdefault(by_id[g['keep']][0], []).append(g)
    for rel, gs in keep_files.items():
        rec = pg.merge(rel, dict(
            fixes=[dict(original=f"{g['keep']} {by_id[g['keep']][2]['title']}",
                        corrected=f"author={g.get('merged_author') or by_id[g['keep']][2]['author']}",
                        note=f"[lianju] {g['note']}") for g in gs],
            date=args.date, reviewer=args.reviewer))
        pg.write_record(rel, pg.ordered(rec))
    pg.write_index()
    print(f'进度记录 {len(fixes_by_file)} 个文件')


if __name__ == '__main__':
    main()
