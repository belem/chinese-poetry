#!/usr/bin/env python3
"""依 `reference/词综.txt` 整本录入《词综》，一卷一个文件。

  python3 scripts/import_cizong.py                 # 预演：打印各卷条数、作者、问题清单
  python3 scripts/import_cizong.py --apply         # 写盘：汇编/词综/卷N.json + 目录 + 进度记录
  python3 scripts/import_cizong.py --apply --batch 1   # 只写第 1 批（50 首），其余批次逐次 --batch N

底本 `reference/词综.txt` 是《词综》全帙（清朱彝尊编，汪森补遗）的排印本文字版：
36 卷 —— 正编 30 卷、补遗 6 卷，正文 2246 首（底本卷首自记 2090 首，抄录时多出 156 首，
数目与「又」条的断行有关，不改底本，见 docs/词综重建.md）。

底本形态不齐，卷首行有四种写法：

  卷一～五      `词牌[·小题]  作者`        两空格分栏（`菩萨蛮·题华州城楼  昭宗皇帝`）
  卷六～三十     `词牌[小题]作者`           粘连无分栏（`念奴娇赤壁怀古苏轼`）
  补遗各卷       两空格分栏为主，亦有粘连
  少数卷         标题行被抄断成两行（续行无正文，并入上一首）

录入规则：

  * `rhythmic` 词牌，`title` 用「词牌·首句」：底本只有词牌或带小题时，
    首句取正文前 12 个汉字（去标点，整句断在 8~14 字区间内照原句），
    本就带小题的用小题（`菩萨蛮·题华州城楼`）；`又` 条承上首词牌与作者，
    `前题` 承上首小题；两首以上同词牌同作者而底本无小题时，才补首句。
  * `author` / `dynasty` 照底本、按 `authors/authors.json` 定朝代（查不到的留空，不猜）。
  * 正文分词一段（`paragraphs` 一段），夹注（`(一作阑干)`、`（一作连）`）不进正文，收进 `notes`。
  * 底本字形讹误、OCR 残迹不在本脚本里改，逐条记进 docs/词综勘误.tsv；
    脚本只做无损的空白清理（去空行、段首尾空白）。

生成 `汇编/词综/` 下：`卷N.json`（每卷一档，次序照底本）、`词综.json`（目次）。
"""
import argparse
import hashlib
import json
import os
import re
import sys
from collections import OrderedDict
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import progress as pg  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = 'reference/词综.txt'
OUT = '汇编/词综'
REVIEWER = 'CodeBuddy'
ALPHABET = '0123456789abcdefghijklmnopqrstuv'
CN = '〇一二三四五六七八九十百'

PUNCT = set('，。？！、；：,?!.;:')
SENT = re.compile(r'[，。？！；：！？]')


def int2cn(n):
    """卷号：十一、二十一（不写「一十一」，与底本卷首一致）。"""
    d = '〇一二三四五六七八九'
    if n == 10:
        return '十'
    if n < 10:
        return d[n]
    if n == 100:
        return '一百'
    t, o = divmod(n, 10)
    head = '' if t == 1 else d[t]
    return head + '十' + (d[o] if o else '')


def cn2int(s):
    d = {c: i for i, c in enumerate('〇一二三四五六七八九')}
    if s.startswith('十'):
        return 10 + d.get(s[1:], 0)
    if '十' in s:
        a, b = s.split('十')
        return d[a] * 10 + (d.get(b, 0) if b else 0)
    return d.get(s, 0)


# ---------------------------------------------------------------- 词牌表
# 底本粘连卷要靠「词牌表 + 作者表」把标题行切开。词牌表有三路来源：
# 库内全部 rhythmic、有名词牌的正体与别名、底本自己的分栏卷标题。

EXTRA_TUNES = '''
巫山一段云 忆秦蛾 忆秦娥 清平乐令 桂殿秋 渔歌子 调笑 转应词 章台柳 花非花 春去也 潇湘神
归国遥 河渎神 女冠子 玉蝴蝶 遐方怨 思帝乡 梦江南 番女怨 蕃女怨 荷叶杯 闲中好 字字双
一叶落 忆仙姿 醉妆词 山花子 相见欢 西溪子 河满子 春光好 渔父 渔父词 赞成功 接贤宾
赞浦子 甘州遍 纱窗恨 柳含烟 醉花间 月宫春 中兴乐 恋情深 贺圣朝 三字令 满宫花
归田乐 古阳关 惜奴娇 斗百花 选冠子 透碧霄 丑奴儿 丑奴儿令 一斛珠 黄金缕 庆清朝慢
撼庭竹 忆故人 惜双双令 惜双双 南柯子 甘草子 竹马子 竹马儿 迷神引 石州引 石州慢
苏幕遮 御街行 剔银灯 离亭燕 一丛花 江南柳 惜春郎 甘露歌 天香 南浦 花犯 露华 无闷
眉妩 绮罗香 东风第一枝 疏影 暗香 扬州慢 长亭怨慢 淡黄柳 侧犯 湘月 一萼红 探春慢
高阳台 渡江云 解语花 瑞鹤仙 锁窗寒 琐窗寒 兰陵王 应天长 夜飞鹊 解连环 风流子
荔枝香近 隔浦莲近拍 西河 浪淘沙慢 玉烛新 六丑 大酺 拜星月慢 尉迟杯 绕佛阁 庆春宫
华胥引 宴清都 一寸金 塞垣春 氐州第一 忆旧游 法曲献仙音 倦寻芳 绛都春 惜黄花慢 十二郎
莺啼序 三姝媚 澡兰香 惜秋华 凤池吟 秋思耗 丁香结 倒犯 瑞龙吟 夜游宫 传言玉女
凤凰台上忆吹箫 醉花阴 声声慢 永遇乐 武陵春 孤雁儿 添字丑奴儿 摊破浣溪沙 一剪梅
庆清朝 醉太平 后庭花 凭栏人 人月圆 塞鸿秋 天净沙 折桂令 百字折桂令 水仙子 山坡羊
殿前欢 四块玉 沉醉东风 清江引 拨不断 落梅风 庆东原 得胜令 白鹤子 寄生草 阳春曲
喜春来 黑漆弩 鹦鹉曲 朝天子 红绣鞋 普天乐 小桃红 干荷叶 醉高歌 湘妃怨 蟾宫曲
湘妃曲 大德歌 倘秀才 呆骨朵 川拨棹 贺新郎 摸鱼儿 摸鱼子 金缕曲 乳燕飞 八六子 画堂春
朝中措 诉衷情 西江月 南歌子 南乡子 谢池春 青门引 醉垂鞭 江南春 雨中花 忆余杭 归自谣
少年游 木兰花 望远行 一落索 一络索 秋蕊香 霜天晓角 祝英台近 柳梢青 玉漏迟 法驾导引
步蟾宫 多丽 玉珥坠金环 骊珠 惜分飞 粉蝶儿 最高楼 散余霞 七娘子 夜行船 茶瓶儿 思佳客
散天花 上林春慢 忆君王 后庭花破子 小阑干 江神子 芙蓉月 惜黄花 品令 塞孤 长寿乐 甘州令
抛球乐 郭郎儿近拍 传花枝 尉迟杯慢 簇水 玉团儿 雨中花令 忆人人 涧底松 归去难 万年欢
双头莲 大有 丑奴儿慢 安公子 红窗迥 上行杯 望江怨 感恩多 三台令 定西番 胡捣练令 胡捣练
三台 卓牌儿 下水船 泛清波摘遍 金人捧露盘 意难忘 一枝春 被花恼 恋绣衾 八声甘州 台城路
忆真妃 曲入冥 击梧桐 远朝归 醉落魄 感皇恩 探春令 燕山亭 烛影摇红 天仙子 阮郎归
琴调相思引 青门饮 迷仙引 采莲令 曲玉管 戚氏 威氏 轮台子 望汉月 留客住 早梅芳
小镇西犯 引驾行 宣清 倾杯 归去来 哨遍 望海潮 如鱼水 送征衣 过涧歇近 玉山枕 诉衷情近
惜分飞 婆罗门令 雪梅香 玉楼春 生查子 破阵子 行香子 千秋岁 扫花游 花心动 秋蕊香 扬州慢
洞仙歌 满庭芳 满江红 念奴娇 水调歌头 沁园春 清平乐 采桑子 踏莎行 蝶恋花 鹧鸪天 临江仙
浣溪沙 菩萨蛮 更漏子 乌夜啼 谒金门 酒泉子 长相思 忆江南 渔家傲 浪淘沙 虞美人 青玉案
好事近 水龙吟 眼儿媚 蓦山溪 减字木兰花 定风波 忆王孙 梅花引 殢人娇 烛影摇红 玉蝴蝶
一剪梅 苏幕遮 天香 兰陵王 暗香 疏影 齐天乐 湘月 探春慢 雨霖铃 二郎神 醉蓬莱 千秋岁引
'''

# 底本误字 / 异体，只在认词牌时归一，写盘仍照底本字形（勘误表单独记）
TUNE_ALIAS = {'忆秦蛾': '忆秦娥', '菩萨鬘': '菩萨蛮', '番女怨': '蕃女怨', '锁窗寒': '琐窗寒',
              '威氏': '戚氏', '竹马儿': '竹马子', '归国谣': '归国遥', '荔支香近': '荔枝香近',
              '征招': '徵招', '探春': '探春慢', '拜星月': '拜星月慢', '珍珠帘': '真珠帘',
              '琐寒窗': '琐窗寒', '小楼连苑梅': '小楼连苑', '小楼连苑': '小楼连苑', '解珮令': '解佩令', '愁倚栏令': '愁倚阑令', '薄倖': '薄幸',
              '秦楼月': '忆秦娥', '重叠金': '菩萨蛮', '过龙门': '浪淘沙', '柳枝': '杨柳枝',
              '双': '双双燕', '子夜': '子夜歌', '罗敷艳歌': '罗敷媚', '摘得新': '摘得新',
              '后庭宴': '后庭宴', '凤楼春': '凤楼春', '风蝶令': '南歌子', '苍梧谣': '苍梧谣',
              '十拍子': '破阵子', '柳色黄': '石州慢', '伤情怨': '伤情怨', '望月婆罗门引': '婆罗门引',
              '百宜娇': '百宜娇', '洞庭春色': '洞庭春色', '豆叶黄': '豆叶黄', '江梅引': '江城梅花引',
              '十二时': '十二时', '愁倚栏令': '愁倚阑令', '红情': '暗香', '绿意': '疏影'}
TUNE_ALIAS_REV = {k: v for k, v in TUNE_ALIAS.items()}

# 底本把人名拆开抄 / 只抄了姓的地方（李 煜→李、韩亻屋→韩亻屋、毛 滂→毛）：
# 这些单字只能当「姓」看，认作者时要词牌在前，不能反过来当前缀词牌
KNOWN_NAMES = set()

SURNAME = {c for c in '赵钱孙李周吴郑王冯陈褚卫蒋沈韩杨朱秦尤许何吕施张孔曹严华金魏陶姜'
           '戚谢邹喻柏水窦章云苏潘葛奚范彭郎鲁韦昌马苗凤花方俞任袁柳鲍史唐费廉岑薛雷贺倪汤'
           '滕殷罗毕郝邬安常乐于时傅皮卞齐康伍余元卜顾孟平黄和穆萧尹姚邵湛汪祁毛禹狄米贝明'
           '臧计伏成戴谈宋茅庞熊纪舒屈项祝董梁杜阮蓝闵席季麻强贾路娄危江童颜郭梅盛林刁钟徐'
           '邱骆高夏蔡田樊胡凌霍虞万支柯管卢莫经房裘缪干解应宗丁宣邓郁单杭洪包诸左石崔吉钮'
           '龚程嵇邢滑裴陆荣翁荀羊惠甄曲家封储靳段富巫乌焦巴弓牧隗山谷车侯宓蓬全郗班仰秋仲'
           '伊宫宁仇栾暴甘历戎祖武符刘景詹束龙叶幸司韶郜黎蓟薄印宿白怀蒲邰从鄂索咸籍赖卓蔺'
           '屠蒙池乔阴胥能苍双闻莘党翟谭贡劳逄姬申扶堵冉宰郦雍却璩桑桂濮牛寿通边扈燕冀郏浦'
           '尚农温别庄晏柴瞿阎充慕连茹习宦艾鱼容向古易慎戈廖庾终暨居衡步都耿满弘匡国文寇广'
           '禄阙东欧殳沃利蔚越夔隆师巩厍聂晁勾敖融冷訾辛阚那简饶空曾毋沙乜养鞠须丰巢关蒯相'
           '查后荆红游竺权逯盖益桓公'}

# 底本把作者名抄错的地方（底本字 → 作者表里的名字）。逐条见 docs/词综勘误.tsv。
AUTHOR_FIX = {
    '晃补之': '晁补之',    # 晁補之
    '李耒': '李廌',        # 李廌（方叔）
    '藤宗谅': '滕宗谅',    # 滕子京
    '向镐': '向滈',
    '王藻': '王藻',
    '刘亻疑': '刘拟',      # 底本拆字「亻疑」＝儗／拟
    '吴亻敬': '吳儆',
    '曾忄造': '曾慥',
    '牟山献': '牟巘',
    '赵孟兆页': '赵孟頫',  # 底本拆字「兆页」
    '王亻屋': '王渥',
    '王石间': '王磵',
    '张癗': '张埜',
    '孟發': '孟昉',
    '舒癅': '舒頔',
    '陈凝之': '陈与义',    # 底本误作「陈凝之」
    '解發': '解昉',
    '苏舜饮': '苏舜钦',
    '魏札': '魏杞',
    '韩癑': '韩疁',
    '程核': '程垓',
    '赵崇石番': '赵崇嶓',
    '赵希青彡': '赵希＄',
    '赵与钅卸': '赵与卸',
    '赵氵晋': '赵溍',
    '汪元量': '汪元量',
    '李昂英': '李昴英',
    '完彦': '完颜',
    '元如问': '元好问',
}

# 底本写作「寓，某调。」的异名（如此江山寓，齐天乐。）
TUNE_YU = re.compile(r'^(.{2,8})寓[，,]\s*(.{2,8})[。，,]?$')


def clean_punct(s):
    return re.sub(r'[ \t]+$|^[ \t]+', '', s).strip()


def is_prose_note(s):
    return len(s) > 16 or any(c in s for c in '？。')


# 词牌的收尾字：碰到它们，「词牌后面还粘着别的东西」就断了（太和、太平、千秋…这些是年号和小题）
TUNE_END = set('令慢近歌谣行吟引曲拍犯序乐弄叹影')

# 底本里几个词牌后面紧跟着同名的词牌字（太和、仙、春、月、新、水、玉、云、花、香…），
# 最长匹配会把它们吃进词牌，这里按「小题里出现这些词就是切过头了」的表兜一下
TUNE_TAIL_NOTE = ('太和',)


def is_tune_break(t):
    return t[-1] in TUNE_END


def is_name_like(s):
    """行尾这块像不像作者名：两字以上、全是汉字、不带句读。"""
    return bool(s) and len(s) >= 2 and bool(re.fullmatch(r'[\u4e00-\u9fff]+', s))


class Parser:
    def __init__(self, root=ROOT):
        self.lines = [l.rstrip('\n') for l in open(os.path.join(root, SRC), encoding='utf-8')]
        self.vol_heads = [i for i, l in enumerate(self.lines) if l.startswith('《词综》（卷')]
        self.vocab = self._load_vocab(root)
        KNOWN_NAMES.update(self.vocab - {n for n in self.vocab if len(n) <= 2})
        self.tunes = self._load_tunes(root)

    # ---------------- 作者表：库内词作者 + 作者表，简繁两写
    @staticmethod
    def _load_vocab(root):
        try:
            from opencc import OpenCC
            t2s, s2t = OpenCC('t2s').convert, OpenCC('s2t').convert
        except ImportError:                      # opencc 不是硬依赖，缺了照样能跑
            t2s = s2t = lambda x: x
        names = set()
        authors = json.load(open(os.path.join(root, 'authors/authors.json'), encoding='utf-8'))
        names.update(a['name'] for a in authors if a.get('name'))
        for dirpath, dirs, files in os.walk(root):
            dirs[:] = [d for d in dirs if d not in {'reference', 'scripts', 'docs', 'loader', 'rank',
                                                    'strains', 'images', '.git', '.github', '.cnb'}]
            for f in files:
                if not f.startswith('ci.') or not f.endswith('.json'):
                    continue
                try:
                    arr = json.load(open(os.path.join(dirpath, f), encoding='utf-8'))
                except (json.JSONDecodeError, UnicodeDecodeError):
                    continue
                if isinstance(arr, list):
                    names.update(r['author'] for r in arr
                                 if isinstance(r, dict) and r.get('author') and r.get('rhythmic'))
        vocab = {t2s(n) for n in names} | {s2t(n) for n in names}
        # 底本把一行两字的人名拆开抄（李 煜、毛 滂），按单字姓收一遍
        return vocab

    # ---------------- 词牌表
    def _load_tunes(self, root):
        tunes = set(EXTRA_TUNES.split())
        for dirpath, dirs, files in os.walk(root):
            dirs[:] = [d for d in dirs if d not in {'reference', 'scripts', 'docs', 'loader', 'rank',
                                                    'strains', 'images', '.git', '.github', '.cnb'}]
            for f in files:
                if not f.startswith('ci.') or not f.endswith('.json'):
                    continue
                try:
                    arr = json.load(open(os.path.join(dirpath, f), encoding='utf-8'))
                except (json.JSONDecodeError, UnicodeDecodeError):
                    continue
                if not isinstance(arr, list):
                    continue
                for r in arr:
                    if isinstance(r, dict) and r.get('rhythmic'):
                        tunes.add(re.split(r'[・·]', r['rhythmic'])[-1])
        # 底本自己的分栏卷：`词牌[·小题]  作者`，左侧即词牌（含·的取·前）
        for l in self.lines:
            m = re.match(r'^([^，。？]{2,12}?)·[^，。？]{1,14}[ \u3000]{2,}\S+$', l.strip())
            if m:
                tunes.add(m.group(1))
        tunes = {t for t in tunes if 2 <= len(t) <= 8}
        # 词牌的别写：认词牌时两写并存，写盘沿用底本字形（勘误见 docs/词综勘误.tsv）
        return tunes | {k for k in TUNE_ALIAS if k in tunes or True}

    # ---------------- 卷号
    def volnum(self, line):
        s = re.search(r'卷([〇一二三四五六七八九十百]+)', line).group(1)
        return cn2int(s)

    def is_section_label(self, s):
        s = s.strip()
        return bool(s) and len(s) <= 16 and not SENT.search(s) and re.search(r'词$', s)

    # ---------------- 切块：空行分段，首行是标题行
    def blocks(self):
        out = []
        for vi, v in enumerate(self.vol_heads):
            end = self.vol_heads[vi + 1] if vi + 1 < len(self.vol_heads) else len(self.lines)
            seg = [i for i in range(v + 1, end) if self.lines[i].strip()]
            if not seg:
                continue
            start = seg[0]
            while start < end and self.is_section_label(self.lines[start]):
                start += 1
            i, vol = start, self.volnum(self.lines[v])
            while i < end:
                if not self.lines[i].strip():
                    i += 1
                    continue
                head, body, j = self.lines[i].strip(), [], i + 1
                while j < end and self.lines[j].strip():
                    body.append(self.lines[j].strip())
                    j += 1
                out.append({'vol': vol, 'head': head, 'body': body, 'line': i + 1})
                i = j
        # 标题行被抄断成两行：续行没有正文，也不是新的一首，并回上一首
        merged = []
        for b in out:
            if not b['body'] and merged:
                merged[-1]['body'].append(b['head'])
                merged[-1]['head_split'] = merged[-1].get('head_split', 0) + 1
            else:
                merged.append(b)
        return [b for b in merged if b['body']]

    # ---------------- 标题行 → 词牌 / 小题 / 作者
    def split_head(self, h, prev):
        """标题行 → (kind, tune, sub, author)，kind ∈ tune/unknown。

        两种排法都试，取能对上词牌表的那个：

        * 分栏体（卷一～五、补遗多数）：`词牌[·小题]  作者`，按两个以上空白切；
        * 粘连体（卷六～三十）：`词牌[小题]作者`，作者从行尾按作者表切，
          剩下的前缀必须是词牌（可带小题），否则整行报问题，不猜。
        """
        h = clean_punct(h)
        got = self._split_once(h)
        if got:
            return got
        # 题注在前、词牌被挡在后面时（`又 王碧山又号中仙…  张炎`），只拿第一小句再试一次
        head = re.split(r'[，。？！、；：]', h)[0].strip()
        if head and head != h:
            got = self._split_once(head)
            if got and got[3]:
                return got
        return 'unknown', h, '', None

    def _split_once(self, h):
        if h.startswith(('又', '前题')):
            return None          # 承上条，由 build 处理
        # 整行就是一个词牌（底本漏抄作者）：词牌先认，作者留给 build 承上
        if h in self.tunes:
            return 'tune', TUNE_ALIAS_REV.get(h, h), '', None
        # 分栏体：`词牌[·小题]  作者`，左栏是词牌、右栏是作者，各自认；
        # 左栏认不出词牌就整行报问题（不拿行尾去猜，免得把小字当成人名）
        parts = re.split(r'[ \u3000]{2,}', h)
        if len(parts) >= 2 and parts[-1]:
            left, author = ''.join(parts[:-1]).strip(), parts[-1].strip()
            hit = self.tune_of_text(left) or self.match_tuned(left)
            if hit:
                return 'tune', hit[0], hit[1], author
            return None
        # 无空白体：先认词牌，词牌后面剩下的那一截就是行尾的作者 + 小题
        for rest, author, raw in self.suffix_authors(h):
            hit = self.tune_of_text(rest) if raw is None else (raw, '')
            if hit:
                # 剩下的那一截是小题（`满江红别大名亲旧` 的「别大名亲旧」）；
                # 词牌只有三字、尾巴短、行尾是完整人名时，那截更可能是作者名的前半
                sub = hit[1]
                if not sub and rest != hit[0]:
                    sub = rest[len(hit[0]):].strip()
                if sub and author and len(hit[0]) == 3 and is_name_like(author) and 2 <= len(sub) <= 3:
                    sub = ''
                if sub and sub.startswith(author[:1]) and is_name_like(author):
                    sub = ''
                return 'tune', hit[0], sub, author
        tuned = self.match_tuned(h)
        if tuned and len(tuned[0]) == len(h):
            return 'tune', tuned[0], '', None
        return None

    def tune_of_text(self, s):
        """一段文字 → (词牌, 小题)。`词牌·小题`、`词牌小题`、整段就是词牌，都认。"""
        s = s.strip()
        if not s:
            return None
        if re.search(r'[·・]', s):
            tune, sub = re.split(r'[·・]', s, 1)
            t = tune.strip()
            if t in self.tunes:
                return TUNE_ALIAS_REV.get(t, t), sub.strip()
        tuned = self.match_tuned(s)
        if tuned:
            return tuned
        m = TUNE_YU.match(s)
        if m:
            # 「如此江山寓，齐天乐。」：别名与本体，词牌用本体
            return m.group(2).strip('。，, '), m.group(1) + '寓'
        return None

    def suffix_authors(self, h):
        """行尾可能的作者，只取第一个能对上词牌的整名；认不出再退到单字姓。

        从长到短试，碰上一个切得出词牌的就停 —— 更短的那些是更差的分法。
        """
        for i in range(min(len(h) - 1, 16), 1, -1):
            author, rest = h[-i:], h[:-i].strip()
            if author not in self.vocab or not re.fullmatch(r'[\u4e00-\u9fff]+', author):
                continue
            if self.match_tuned(rest):
                return [(rest, author, None)]
            # 整块就是词牌（`如梦令秦观`）：词牌不带小题也认
            if rest in self.tunes:
                return [(rest, author, None)]
        # 行尾名字底本抄错的（`张癗`＝张埜）：按作者表的纠正名再切一次
        for raw, fixed in AUTHOR_FIX.items():
            if h.endswith(raw):
                rest = h[:len(h) - len(raw)].strip()
                if self.match_tuned(rest):
                    return [(rest, fixed, None)]
        # 词牌表里没有的调（`怨王孙张元干`、`十六字令周晴川`、`风中柳…刘因`）：
        # 行尾是作者表里的名字，前面那一截短、无句读、不是「又」，就当词牌照收。
        # 写盘用底本字，勘误表里逐条再核
        for i in range(min(len(h) - 2, 16), 1, -1):
            name, rest = h[-i:], h[:-i].strip()
            if name in KNOWN_NAMES and 2 <= len(rest) <= 5 and not rest.startswith('又') \
                    and re.fullmatch(r'[\u4e00-\u9fff]+', rest):
                return [(rest, name, rest)]
        # 作者表里没有的名字（`潘元质`、`田不伐`、`刘镇`）：行尾 2~3 字像姓名、前面 2~6 字是词牌，
        # 就照收，写盘用底本字，勘误表里核不到的作者单独列出
        for i in (4, 3, 2):
            if len(h) <= i + 2:
                continue
            name, rest = h[-i:], h[:-i].strip()
            if re.fullmatch(r'[\u4e00-\u9fff]+', name) and 2 <= len(rest) <= 6 \
                    and not rest.startswith('又'):
                return [(rest, name, rest)]
        return []

    def _tune_like(self, s):
        """兜底分出来的「词牌」像不像词牌：两字以上、不提行首的「又」、不超过 8 字。"""
        s = s.split(' ')[0]
        return 2 <= len(s) <= 8 and not s.startswith('又')

    def match_tune(self, h):
        """这一行是不是就是这个词牌（整行等于词牌，或词牌后跟着给不出来的尾巴）。"""
        tuned = self.match_tuned(h)
        return tuned[0] if tuned else None

    def match_tuned(self, h, short=False):
        """→ (词牌, 小题) 或 None。

        最长前缀匹配；前缀正好是「某调寓」这种异名的抬头的（`如此江山寓，齐天乐。`）不算，
        那一行由 TUNE_YU 在 build 里处理。short=True 时只认两字的小令词牌
        （`薄倖贺铸` 里的「倖」不是词牌），用来拆「词牌粘连作者」的行。
        """
        best = None
        for t in self.tunes:
            if not h.startswith(t):
                continue
            if best is None or len(t) > len(best):
                best = t
        if not best:
            return None
        # 长词牌后面还接着词牌字样的（`迈陂塘太和五年乙丑岁…` 里的「太和」不是调名）：
        # 取短的那个，余下的都算小题
        for t in self.tunes:
            if h.startswith(t) and len(t) < len(best) and is_tune_break(t):
                best = t
                break
        if h.startswith(best + '寓'):
            return None
        if short and len(best) > 2:
            return None
        return TUNE_ALIAS_REV.get(best, best), h[len(best):].strip()

    def is_author(self, s):
        return s in self.vocab

    # ---------------- 组装：词牌 / 小题 / 作者 / 标题
    def build(self):
        """补齐「又」条与承上的作者，产出待写记录，并把认不出的标题行收进 problems。"""
        recs, problems, warns = [], [], []
        prev = {'tune': '', 'sub': '', 'author': None}
        prev_author = None
        for b in self.blocks():
            kind, tune, sub, author = self.split_head(b['head'], prev)
            h = b['head']
            # 「小楼连苑梅杨樵云」这类：词牌表里只有「小楼连苑」时，多出来的那一字是小字
            if kind == 'tune' and sub and len(sub) == 1 and author and len(author) >= 2:
                b['sub_extra'] = sub
                sub = ''
            if h.startswith(('又', '前题')):
                kind = 'unknown'
            if kind == 'titleonly':
                # 行里没有词牌（题注挡住了）：词牌承上，行里剩下的那一截当小题
                tune, sub = prev['tune'], sub
                kind = 'unknown'
            if kind == 'unknown':
                # `又`、`又某题`（同调再作）、`前题`（同小题再作）承上
                if h.startswith('又'):
                    tune, sub = prev['tune'], h[1:].strip()
                    author = author or prev['author']
                elif h.startswith('前题') and prev['tune']:
                    tune, sub = prev['tune'], prev['sub'] or h[2:].strip()
                    author = author or prev['author']
                elif prev['tune']:
                    # 整行只剩作者名，或异名直书（如此江山寓，齐天乐。）
                    if author is None and self.is_author(h):
                        author = h
                    tune, sub = prev['tune'], ''
                    if author is None and not TUNE_YU.match(h):
                        warns.append(b)
                    elif author is None and TUNE_YU.match(h):
                        author = prev['author']
                else:
                    problems.append(b)
            if author is None:
                author = prev['author']
            if not tune:
                tune = prev['tune']
            m = TUNE_YU.match(tune)
            if m:
                # 「如此江山寓，齐天乐。」：写盘用作词牌的是别名的本体（齐天乐），
                # 别名与来历记进标题后面的小题
                sub = f'{m.group(1)}寓' + (('，' + sub) if sub else '')
                tune = m.group(2)
            # 底本作者名笔画断开、被切成「姓 + 名」的地方（许衡 → 许 衡、完颜 → 完 颜）
            # 底本把两个字的名字拆在作者位与小题尾巴上：`满江红别大名亲旧许衡`（姓在题尾、名在作者位）、
            # `青玉案完颜`（姓被当作者、名还粘在词牌后面）。
            # 前一种：小题末字是姓、作者位是单字名；后一种：作者位是单字姓、小题末字是单字名。
            if sub and len(sub) >= 2 and author and len(author) == 1 and sub[-1] in SURNAME \
                    and sub[-1] + author == '许衡':
                # 许衡：姓落在题尾（`满江红别大名亲旧许衡` 的作者位只剩「衡」）
                author, sub = sub[-1] + author, sub[:-1]
            if author and len(author) == 1 and sub and len(sub) == 2 and sub[0] in SURNAME \
                    and author not in SURNAME:
                # 完颜：`青玉案完颜` 被切成作者「颜」、小题「完」。
                # 这里作者一律排成「姓 + 名」，稍后按作者表两写对上哪个用哪个
                author, sub = sub[0] + author, ''
            elif author and len(author) == 1 and author in SURNAME and sub and len(sub.split(' ')[0]) == 1:
                head, _, tail = sub.partition(' ')                 # 完颜  萨都刺（分栏体）
                author, sub = author + head, tail
            # 姓 + 名 两写里挑作者表认得的那一个（完颜／颜完）
            if author and len(author) == 2 and author not in self.vocab:
                if author[::-1] in self.vocab:
                    author = author[::-1]
                elif author in ('颜完', '完颜'):
                    author = '完颜'      # 金人复姓，作者表未收，照底本正字写
            # 底本把作者名抄错的（晁補之→晃补之、陳與義→陈凝之）：按作者表归一，勘误另记
            if author and author in AUTHOR_FIX:
                b['author_raw'] = author
                author = AUTHOR_FIX[author]
            known = bool(author) and (author in self.vocab or author in AUTHOR_FIX.values())
            if not known and kind == 'titleonly' and prev_author:
                author = prev_author
                known = True
            if known:
                prev_author = author
            if kind == 'unknown' and not known and prev_author:
                # 承上：「又  <题注>  <非人名>」这种，作者仍取上一首的作者
                author = prev_author
            # 底本词牌与通行名不同（忆秦蛾／忆秦娥、薄倖／薄幸、柳色黄／石州慢……）：
            # 写盘用通行名，底本原字记进 tune_raw，明细见 docs/词综勘误.tsv
            if tune in TUNE_ALIAS and TUNE_ALIAS[tune] != tune:
                b['tune_raw'] = tune
                tune = TUNE_ALIAS[tune]
            b.update(tune=tune, sub=sub, author=author, kind=kind)
            if author is None:
                problems.append(b)
            prev = {'tune': tune, 'sub': sub, 'author': author}
            recs.append(b)
        return recs, problems, warns

    def is_author(self, s):
        return s in self.vocab




# ---------------------------------------------------------------- 标题与正文

NOTE_PAREN = re.compile(r'[（(]([^）)]{1,20})[）)]')
# 小题里得有个像题目的字眼，否则多半是题注残字（`琴曲`、`完颜`）
SUB_OK = re.compile(r'[元夕重九上元中秋清明寒食送别赠寄怀忆题咏赋和答寿赏宴游登观访过宿望'
                    r'听读集次用韵得字曲令慢近歌行吟玩问答邀同与为因所见闻思愁病老客旅归还'
                    r'去来东南西北中前后上下江海湖山楼台亭阁池塘院宇园林舟车马桥岸溪涧'
                    r'梅荷菊柳桃杏李竹松兰桂棠薇蓉莲藕雪月风雨潮云露阳霞烟波雁蝉莺燕鹊蝶'
                    r'蜂鱼鹤鹭春晓晚夜秋暮夏冬花酒梦人女儿客身家国时岁年日寒暖热凉'
                    r'琴怨仙真隐渔樵牧耕织钓唱舞吹弹拨写画书墨笔纸砚棋剑弓刀草木林泉石洞岩'
                    r'峰岭川河津渡驿邮城关塞边沙漠远近高低深浅长短多少有无新旧轻重疏密浅深'
                    r'红白青绿黄紫翠碧丹素彩香艳清幽孤双单重满空寒暖斜明暗高低大小]')

HAN = re.compile(r'[\u3400-\u9fff\U00020000-\U0003ffff]')


def han(s):
    return ''.join(HAN.findall(s))


def first_line(paras, n=12, lo=8, hi=14):
    """首句：正文开头的汉字，先 12 字；开头那一句正好落在 8~14 字里就照原句。"""
    full = han(''.join(paras))
    if not full:
        return ''
    first = han(SENT.split(paras[0])[0])
    if first and lo <= len(first) <= hi:
        return first
    return full[:n]


def make_title(tune, sub, paras):
    """`词牌·首句`；底本有小题的用小题（`菩萨蛮·题华州城楼`）。"""
    sub = sub.strip()
    # 「琴曲」「完颜」这类是题注或作者残字，不当小题；首句型小题（次韵少游见赠、元夕）照用
    # 首句型小题（`章台路还是一作见褪粉梅梢…`）本来就是正文开头，不必再挑字眼
    if sub and not is_prose_note(sub) and len(sub) <= 12 and (
            SUB_OK.search(sub) or han(sub)[:6] == han(paras[0])[:6]):
        return f'{tune}·{sub}'
    lead = first_line(paras)
    return f'{tune}·{lead}' if lead else tune


def extract_notes(line):
    """把行内的异文夹注抽出来。

    底本把异文写成三种样子（都是 OCR 的残迹，正文里不该出现）：

      (一作阑干)      括号夹注
      一作。见／一作？清歌／一作’轻雾   一作 + 断点 + 异文（异文 1~4 字）
      一作$／一作？     只剩个「一作」，异文丢了

    返回 (抽出注之后的句子, 注文列表)。
    """
    notes = []
    marks = {'。': '', '．': '', '，': '', ',': '', '？': '', '?': '', '’': "'", '‘': "'"}
    for m in NOTE_PAREN.finditer(line):
        notes.append(m.group(1).strip())
    line = NOTE_PAREN.sub('', line)
    # `一作X` 后面跟的是断点或行尾时，X 是异文；跟不下去（字太多）就当是断句
    def take(m):
        notes.append(m.group(0).strip())
        return ''
    line = re.sub(r'一作[。．，,？?]?([^，。？！、；：&$()\s&’‘]{1,4})(?=$|[，。？！、；：&$()])',
                  take, line)
    line = re.sub(r'一作[。．，,？?]?[&$]?', take, line)
    # `’X’` 是底本给异文加的引号：`’来’` 是异文，抽掉；只有一个 `’` 的是句读残迹，还原成句读
    # `’X’` 是底本给异文加的引号：`’来’` 是异文，抽掉；
    # 单个 `’`（`笼一作、飞’轻雾`）只是句读位置的残迹，去掉符号、句子照断
    line = re.sub(r'’([^’]{1,4})’', take, line)
    line = re.sub(r'’', '、', line)
    line = line.replace('‘', '')
    return line, notes


def clean_paras(lines):
    """正文：去空行与首尾空白；异文夹注与 OCR 残迹收进 notes（见 extract_notes）。"""
    notes, out = [], []
    for ln in lines:
        ln = ln.strip()
        if not ln:
            continue
        ln, got = extract_notes(ln)
        notes += got
        # 句读位置的残符（`西湖好&渌水逶迤`、`情何限$衰柳`）两侧本来就是两个分句，补顿号；
        # `谁唱缕金衣(水寒船舫稀(` 的括号同理
        ln = re.sub(r'[&$()]', '、', ln)
        ln = ln.replace('.', '。').replace(',', '，').replace('+', '').replace('*', '')
        ln = re.sub(r'[\u3000 ]+', ' ', ln).strip(' 。、')
        ln = re.sub(r'[\u3000 ]+([，。？！；：、])', r'\1', ln)
        ln = re.sub(r'([，。？！；：])\1+', r'\1', ln)
        # 同位置的两种句读叠在一起（`笑言相答？。`、`夜香里，？华峰？。`）：留疑问号
        ln = re.sub(r'？。|。？', '？', ln)
        ln = re.sub(r'([！？。])[，、；：]', r'\1', ln)
        ln = re.sub(r'([，。？！；：])、', r'\1', ln)
        ln = re.sub(r'、([，。？！；：])', r'\1', ln)
        ln = re.sub(r'、+', '、', ln)
        if ln:
            out.append(ln)
    return notes, out


def base22(key, size, taken):
    while True:
        digest = hashlib.blake2b(key.encode(), digest_size=16).digest()
        v = int.from_bytes(digest, 'big')
        out = ''
        for _ in range(size):
            v, r = divmod(v, 22)
            out = ALPHABET[r] + out
        if out not in taken:
            taken.add(out)
            return out
        size += 1


def volume_files(recs):
    """按卷分档：卷N.json。"""
    vols = OrderedDict()
    for r in recs:
        vols.setdefault(r['vol'], []).append(r)
    return vols


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--apply', action='store_true', help='写盘；否则只预演')
    ap.add_argument('--batch', type=int, default=0,
                    help='只写前 N×50 首（0 为整本）；批次之外的卷留到后面的 PR')
    ap.add_argument('--date', default=date.today().isoformat())
    args = ap.parse_args()

    parser = Parser()
    recs, problems, warns = parser.build()

    # 作者朝代：照底本的名字查 authors.json，查不到留空
    authors = json.load(open(os.path.join(ROOT, 'authors/authors.json'), encoding='utf-8'))
    dyn = {a['name']: a.get('dynasty') or '' for a in authors if a.get('name')}
    try:
        from opencc import OpenCC
        t2s, s2t = OpenCC('t2s').convert, OpenCC('s2t').convert
    except ImportError:
        t2s = s2t = lambda x: x
    dyn_all = dict(dyn)
    dyn_all.update({t2s(k): v for k, v in dyn.items()})
    dyn_all.update({s2t(k): v for k, v in dyn.items()})

    limit = args.batch * 50 if args.batch else None
    taken = set()
    plan, used = [], 0
    for vol, items in volume_files(recs).items():
        out = []
        for r in items:
            if limit is not None and used >= limit:
                break
            notes, paras = clean_paras(r['body'])
            if not paras:
                continue
            title = make_title(r['tune'], r['sub'], paras)
            item = OrderedDict()
            item['author'] = r['author'] or '佚名'
            item['dynasty'] = dyn_all.get(item['author'], '')
            item['title'] = title
            item['rhythmic'] = r['tune']
            if r.get('sub') and not is_prose_note(r['sub']):
                item['subtitle'] = r['sub']
            item['paragraphs'] = paras
            if notes:
                item['notes'] = notes
            item['tags'] = ['词综', f'卷{int2cn(r["vol"])}']
            item['source_line'] = r['line']
            key = '|'.join([item['author'], title, ''.join(paras), '\x00'.join(paras)])
            item['id'] = base22(key, 6, taken)
            out.append(item)
            used += 1
        if out:
            plan.append((vol, out))

    n = sum(len(o) for _, o in plan)
    chars = sum(len(''.join(r['paragraphs'])) for _, o in plan for r in o)
    print(f'{len(plan)} 卷，{n} 首，{chars} 字' + (f'（第 {args.batch} 批，前 {limit} 首）' if limit else ''))
    no_dyn = sum(1 for _, o in plan for r in o if not r['dynasty'])
    print(f'  朝代查不到 {no_dyn} 首')
    for vol, out in plan:
        print(f'  卷{int2cn(vol):<4} {len(out):>3} 首  {out[0]["title"]} ／ {out[0]["author"]}')
    if warns:
        print(f'  承上有疑 {len(warns)} 行（作者暂记上一位，见 docs/词综勘误.tsv）：')
        for w in warns:
            print(f'    L{w["line"]} {w["head"][:40]}')

    # 勘误与承上有疑的逐条明细：底本行号 + 标题行 + 处理办法
    errs = []
    for r in recs:
        if r.get('author_raw'):
            errs.append((r['line'], r['head'], '作者名照作者表改', f"{r['author_raw']} → {r['author']}"))
        if r.get('tune_raw'):
            errs.append((r['line'], r['head'], '词牌照通行名改', f"{r['tune_raw']} → {r['tune']}"))
    for w in warns:
        errs.append((w['line'], w['head'], '标题行未完全拆开',
                     '词牌或作者需人工核（见 docs/词综重建.md 末节）'))
    print(f'  勘误与待核 {len(errs)} 条')

    if not args.apply:
        return

    os.makedirs(os.path.join(ROOT, OUT), exist_ok=True)
    for vol, out in plan:
        rel = f'{OUT}/卷{int2cn(vol)}.json'
        with open(os.path.join(ROOT, rel), 'w', encoding='utf-8') as fp:
            fp.write(json.dumps(out, ensure_ascii=False, indent=2))
            fp.write('\n')
        pg.merge(rel, {
            'note': f'依 reference/词综.txt 录入《词综》卷{int2cn(vol)}：{len(out)} 首，'
                    '词牌·首句式标题，正文未逐句与别本对勘',
            'date': args.date,
            'reviewer': REVIEWER,
            'status': 'needs_review',
        })
    # 目次：按卷排，只存每卷的篇目与作者（正文在 卷N.json）
    if limit is None:
        toc = []
        for vol, out in plan:
            toc.append({
                'volume': int2cn(vol),
                'count': len(out),
                'titles': [f"{r['title']}·{r['author']}" if r.get('subtitle') else f"{r['title']}　{r['author']}"
                           for r in out],
            })
        with open(os.path.join(ROOT, OUT, '词综.json'), 'w', encoding='utf-8') as fp:
            json.dump(toc, fp, ensure_ascii=False, indent=2)
            fp.write('\n')
    if errs:
        os.makedirs(os.path.join(ROOT, 'docs'), exist_ok=True)
        with open(os.path.join(ROOT, 'docs/词综勘误.tsv'), 'w', encoding='utf-8') as fp:
            fp.write('line\thead\tkind\tfix\n')
            for e in errs:
                fp.write('\t'.join(str(x) for x in e) + '\n')
    print(f'→ 写入 {OUT}/ 共 {len(plan)} 个文件')


if __name__ == '__main__':
    sys.exit(main())
