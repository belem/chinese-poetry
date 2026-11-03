#!/usr/bin/env python3
"""依 `reference/古诗源.txt` 整本录入（清）沈德潜《古诗源》，一卷一个文件。

  python3 scripts/import_gushiyuan.py                       # 预演：打印各卷篇数、去重指针、问题清单
  python3 scripts/import_gushiyuan.py --apply               # 写盘：汉/古诗源/卷N.json + 目录 + 进度记录
  python3 scripts/import_gushiyuan.py --apply --batch 1     # 只写前 1 批，其余批次逐次 --batch N

底本 `reference/古诗源.txt` 是《古诗源》十四卷的排印本文字版（4622 行）：

  卷首   ●目录（篇目）、●序、●例言
  各卷   ●古诗源卷N → ○<时段/体裁>（卷二～卷十一是「汉诗」「魏诗」……，
         卷十二～十四先「齐诗」「梁诗」「陈诗」，再「北魏诗【附】」「北齐诗【附】」……）
         → 作者行 → 篇题行 → 题注（引书、本事）→ 正文行（行末【…】是沈德潜的评点）

录入规则：

  * 底本一行一首诗的排法不统一：多数是「每首一行」，也有「一首数行」（《安世房中歌》
    十五章、《饮酒》二十章、《拟咏怀》……）。故 `paragraphs` **一首一段**，段内句读照底本，
    一首多行的按行拆段，不再按行内的句号断段。
  * 行末【…】是评点，不是正文；【同X。】【音X。】【古X字。】这类是行内夹注，
    两者都进 `notes`，位置用 `【】` 还原（`正文【注】正文`）。
  * 底本一首之前常有一行引书或本事（`《史记》：……`、`以下铭辞见《大戴礼》。`），
    收进 `prologue`，与《千家诗》`prologue` 同口径。
  * 「又某题」「前题」承上首的作者；`○` 时段进 `section`。
  * `title` / `author` 照底本；底本把两处并成一行抄（`书屏风诗大义公主`、
    `杂诗思妇临高台…`）的在 `HEAD_FIX` 里逐条拆开。
  * 底本正文讹字逐条核过，改动只记在 `docs/古诗源勘误.tsv`；脚本本身不改正文。

分卷分档，文件名 `卷N.json`（N 用汉字，与底本卷次一致），`古诗源.json` 存目次与序、例言。
"""
import argparse
import hashlib
import json
import os
import re
import sys
import difflib
from collections import OrderedDict
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import progress as pg  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = 'reference/古诗源.txt'
OUT = '汉/古诗源'
REVIEWER = 'CodeBuddy'
ALPHABET = '0123456789abcdefghijklmnopqrstuv'
CN = '〇一二三四五六七八九十'

HAN = re.compile(r'[\u3400-\u9fff\U00020000-\U0003ffff]')
BREAK = re.compile(r'[，。！？；：、,?!;:]')
NOTE = re.compile(r'【([^】]*)】')
CRIT_END = ('。', '！', '？')

# 底本把作者行与篇题行并成一行抄的地方：行首的篇题 + 行尾的作者
HEAD_FIX = {
    2995: ('短兵篇', '无名氏'),   # 底本把作者与篇题并成一行（`无名氏短兵篇`）
    3453: ('杂诗', '王徽'),       # `杂诗思妇临高台…`：篇题与正文抄在同一行
    3493: ('答孙缅歌', '渔父'),    # `答孙缅歌《南史》：…`
    3498: ('宋人歌', '宋人'),      # 底本把作者位写成篇题，正文只有一句 `可怜白符鸠，枉杀檀江州`
    3502: ('石城谣', '百姓'),      # `《南史》：…百姓语曰。` / `可怜石头城…`
    3507: ('青溪小姑歌', '青溪小姑'),   # `蒋侯妹。` / `日暮风吹…`
    '见《国语》': ('商铭', None),                    # 上古铭辞，作者就是篇题
    '书屏风诗大义公主': ('书屏风诗', '大义公主'),
    '杂诗思妇临高台，长想凭华轩。': ('杂诗', None),
    '答孙缅歌《南史》：': ('答孙缅歌', None),
    '一作古辞': (None, None),
}

# 底本把作者行抄成了评语（`常景` 那条起首是「司马相如《北史》：……」，`沈约` 那条是
# 「家令诗，较之鲍、谢……」），行号 → 真作者
AUTHOR_FIX = {
    4379: '庾信',      # `庾信` / `陈、隋间人。…` / `商调曲`
    4466: '炀帝',      # `炀帝` / `炀帝诗，能作雅正语…` / `饮马长城窟行示从征群臣`
    4468: '炀帝',
    4480: '杨素',
    4478: '杨素',      # `杨素` / `武人亦复奸雄…` / `山斋独坐赠薛内史二首`
    4259: '常景',
    4262: '常景',
    4266: '王褒',
    4270: '严君平',
    4274: '扬雄',
    4264: '王褒',
    4268: '严君平',
    4272: '扬雄',
    # 4365 是 `斛律金` 的作者行（它后面紧跟篇题 `敕勒歌`），不需要订正
    3774: '沈约',
    2432: '张华',
    2458: '傅玄',
    2528: '陆机',
    2586: '潘岳',
    2748: '陶潜',
    3089: '颜延之',
    3150: '谢灵运',
    3304: '鲍照',
    3516: '谢朓',
    3748: '简文帝',
    3774: '沈约',
    3984: '何逊',
}

# 作者名的通行写法（底本用字与 authors/authors.json 不同的，写盘用底本字，这里只做朝代查询）
AUTHOR_ALIAS = {
    '高帝': '刘邦', '武帝': '刘彻', '昭帝': '刘弗陵', '文帝': '曹丕', '明帝': '曹叡',
    '炀帝': '杨广', '简文帝': '萧纲', '元帝': '萧绎', '孝武帝': '刘骏',
}
AUTHOR_DYNASTY = {          # 作者表里查不到、或与底本时段不合的，照底本的卷次时段补
    '唐山夫人': '汉', '朱虚侯章': '汉', '乌孙公主': '汉', '卓文君': '汉',
    '燕刺王旦': '汉', '华容夫人': '汉', '王昭君': '汉', '班婕妤': '汉',
    '赵飞燕': '汉', '苏伯玉妻': '汉', '窦玄妻': '汉', '李延年': '汉',
    '蔡邕': '汉', '秦嘉': '汉', '辛延年': '汉', '宋子侯': '汉', '韦孟': '汉',
    '张正见': '南北朝', '阴铿': '南北朝', '王僧孺': '南北朝', '任昉': '南北朝',
    '柳恽': '南北朝', '范云': '南北朝', '王僧达': '南北朝', '虞羲': '南北朝',
    '何胥': '南北朝', '韦鼎': '南北朝', '陈昭': '南北朝', '周弘让': '南北朝',
    '周弘正': '南北朝', '刘昶': '南北朝', '温子升': '南北朝', '胡叟': '南北朝',
    '胡太后': '南北朝', '邢邵': '南北朝', '祖珽': '南北朝', '郑公超': '南北朝',
    '萧悫': '南北朝', '颜之推': '南北朝', '冯淑妃': '南北朝', '斛律金': '南北朝',
    '虞世基': '隋', '孙万寿': '隋', '王胄': '隋', '尹式': '隋', '孔德绍': '隋',
    '孔绍安': '隋', '陈子良': '隋', '王申礼': '隋', '吕让': '隋', '明余庆': '隋',
    '大义公主': '隋', '刘绘': '南北朝', '孔稚圭': '南北朝', '陆厥': '南北朝',
    '江孝嗣': '南北朝', '张融': '南北朝', '王融': '南北朝', '谢朓': '南北朝',
    '谢瞻': '南北朝', '谢惠连': '南北朝', '谢庄': '南北朝', '鲍令晖': '南北朝',
    '吴迈远': '南北朝', '王徽': '南北朝', '沈庆之': '南北朝', '陆凯': '南北朝',
    '汤惠休': '南北朝', '刘俣': '南北朝', '谢混': '晋', '吴隐之': '晋',
    '庐山诸道人': '晋', '惠远': '晋', '帛道猷': '晋', '谢道韫': '晋', '赵整': '晋',
    '曹毗': '晋', '王羲之': '晋', '郭泰机': '晋', '王赞': '晋', '张翰': '晋',
    '左贵嫔': '晋', '左延年': '三国', '缪袭': '三国', '应璩': '三国',
    '应瑒': '三国', '徐幹': '三国', '刘桢': '三国', '陈琳': '三国', '王粲': '三国',
    '甄后': '三国', '阮籍': '三国', '嵇康': '三国', '卢谌': '晋', '司马彪': '晋',
    '束皙': '晋', '傅玄': '晋', '张华': '晋', '张协': '晋', '张载': '晋',
    '孙楚': '晋', '曹摅': '晋', '刘琨': '晋', '郭璞': '晋', '谢尚': '晋',
    '司马懿': '三国', '李尤': '汉', '蔡琰': '汉', '孔融': '汉', '诸葛亮': '三国',
    '曹植': '三国', '苏武': '汉', '李陵': '汉', '东方朔': '汉', '司马相如': '汉',
    '班固': '汉', '张衡': '汉', '梁鸿': '汉', '马援': '汉', '杨恽': '汉',
    '无名氏': '汉', '无名氏短兵篇': '晋', '乐府歌辞': '汉', '杂歌谣辞': '晋',
    '史记': '先秦', '汉书': '汉', '左传': '先秦', '国语': '先秦', '管子': '先秦',
    '列子': '先秦', '韩非子': '先秦', '慎子': '先秦', '鲁连子': '先秦',
    '战国策': '先秦', '孔子家语': '先秦', '新序': '汉', '说苑': '汉',
    '风俗通': '汉', '牟子引古谚': '汉', '四民月令引农语': '汉', '六韬': '先秦',
    '太公兵法引黄帝语': '先秦', '古谚古语': '先秦', '梁史': '南北朝',
    '列女传引古语': '汉', '刘向别录引古语': '汉', '桓子新论引谚': '汉',
    '易纬引古诗': '汉', '月令注引里语': '汉', '水经注引谚': '南北朝',
    '山经引相冢书': '先秦', '文选注引古谚': '南北朝', '魏志王昶引谚': '三国',
    '史照通鉴疏引谚': '宋', '左传引逸诗': '先秦', '商铭': '先秦', '盘操': '先秦',
    '渔父': '南北朝', '宋人歌': '南北朝', '石城谣': '南北朝', '青溪小姑歌': '南北朝',
}

# 「以下铭辞见《大戴礼》。」这类单独成行的说明，收进 prologue
META_LINE = re.compile(r'^(以下|见《|详见|此将|元封|东汉|西京|苏李诗|首章|婕妤初|'
                       r'汉武帝故事|一九首|十九首|一作|《)')


AUTHORS = set()


def load_authors():
    """库内作者表（authors/authors.json）＋底本里出现的人名，简繁两写。"""
    if AUTHORS:
        return AUTHORS
    try:
        from opencc import OpenCC
        t2s, s2t = OpenCC('t2s').convert, OpenCC('s2t').convert
    except ImportError:
        t2s = s2t = lambda x: x
    names = set()
    with open(os.path.join(ROOT, 'authors/authors.json'), encoding='utf-8') as fp:
        for a in json.load(fp):
            if a.get('name'):
                names.add(a['name'])
    names |= set(AUTHOR_DYNASTY) | set(AUTHOR_FIX.values())
    for n in list(names):
        AUTHORS.add(n)
        AUTHORS.add(t2s(n))
        AUTHORS.add(s2t(n))
    return AUTHORS


def int2cn(n):
    d = '〇一二三四五六七八九'
    if n == 10:
        return '十'
    if n < 10:
        return d[n]
    t, o = divmod(n, 10)
    if t > 9:                       # 本底本只到十四卷，用不到百位
        raise ValueError(n)
    return ('' if t == 1 else d[t]) + '十' + (d[o] if o else '')


def han(s):
    return ''.join(HAN.findall(s))


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


class Parser:
    def __init__(self, root=ROOT):
        self.lines = [l.rstrip('\n') for l in open(os.path.join(root, SRC), encoding='utf-8')]
        load_authors()
        self.vol_heads = [i for i, l in enumerate(self.lines) if l.strip().startswith('●古诗源卷')]
        self.front = [i for i, l in enumerate(self.lines) if l.strip() in ('●序', '●例言', '●目录')]
        self.problems = self._check_heads()

    def _check_heads(self):
        """预检：块首若是 authors/authors.json 里没有、后面又跟着篇题的短行，
        多半是被认成作者的篇题（`东飞伯劳歌`），报出来人工核。"""
        known = {a['name'] for a in json.load(open(os.path.join(ROOT, 'authors/authors.json'),
                                                    encoding='utf-8')) if a.get('name')}
        bad = []
        for vol, section, author, title, lines, ln in self.pieces():
            if not author or author in known or author in AUTHOR_DYNASTY or len(title) <= 6:
                continue
            near = difflib.get_close_matches(author, known, n=1, cutoff=0.5)
            if not near:
                bad.append((vol, ln, author, title))
        return bad

    # ---------------- 卷首：目录 / 序 / 例言
    def front_matter(self):
        """●目录 → 篇章清单；●序、●例言 → 段落。"""
        toc, prose = [], []
        start = self.lines.index('●目录') if '●目录' in self.lines else None
        if start is not None:
            i = start + 1
            while i < len(self.lines) and not self.lines[i].startswith('●'):
                t = self.lines[i].strip().strip('\u3000')
                if t:
                    toc.append(t)
                i += 1
        for head in ('●序', '●例言'):
            if head not in [l.strip() for l in self.lines]:
                continue
            i = [l.strip() for l in self.lines].index(head) + 1
            while i < len(self.lines) and not self.lines[i].startswith('●'):
                t = self.lines[i].strip().strip('\u3000')
                if t:
                    prose.append(t)
                i += 1
        return toc, prose

    # ---------------- 切块
    def pieces(self):
        """→ [(vol, section, author, title, lines, line_no)]，lines 是 [(行号, 文本)]。"""
        out = []
        for vi, v in enumerate(self.vol_heads):
            end = self.vol_heads[vi + 1] if vi + 1 < len(self.vol_heads) else len(self.lines)
            out += list(self._volume(vi + 1, v, end))
        return out

    def _volume(self, vol, start, end):
        author, section = None, None
        blocks = self._blocks(start + 1, end)
        for b in blocks:
            if b['kind'] == 'section':
                section = b['name']
                author = None
            elif b['kind'] in ('author', 'meta'):
                # 底本把作者行抄成了评语（`家令诗，较之鲍、谢……`、`陈、隋间人。`）：
                # 这些行的行号记在 AUTHOR_FIX，作者照表；其余按行的字面当地
                if b['kind'] == 'author':
                    author = AUTHOR_FIX.get(b['line'], b['text'])
                else:                       # meta：整行是题注，作者只有表里记了的才算
                    author = AUTHOR_FIX.get(b['line']) or author
            elif b['kind'] == 'piece':
                title, auth = b['title'], author
                if not title and b['line'] in HEAD_FIX:
                    title, auth = HEAD_FIX[b['line']]
                elif title in HEAD_FIX:
                    new_title, new_author = HEAD_FIX[title]
                    title = new_title or title
                    auth = new_author or auth
                if auth is None and title in ('商铭',):
                    auth = None
                yield vol, section, auth, title, b['lines'], b['line']

    def _is_author(self, ln, t):
        """这一行是不是「作者行」。

        题注、评点走的是「头」的形状（短、无句读），要排除三种：
          * 行号记在 AUTHOR_FIX 的，是评点行，不是作者；
          * 后面跟着的作品数与本轮作者累计的篇数相同（`捣衣` 出现在 `温子升` 之后、
            `胡叟` 之前，是温子升的篇题，不是新作者）；
          * 以「一作」「见《」开头的，是异文与出处。
        """
        if ln in AUTHOR_FIX:
            return False               # 这一行本身是评语，不是作者
        if t in AUTHORS and len(t) <= 4:
            return True                # 名字就在作者表里：它后面跟的一定是下一首
        if re.match(r'^(一作|见《|以下)', t):
            return False
        return None                    # 其余由上下文判定

    def _blocks(self, start, end):
        """底本 → section / author / piece / meta 块。

        先按「空行 + 短行（无句读、≤ 14 字）」把每一段的首行切成 head，其余是 body，
        再把 head 串起来判身份：

          头 | 正文                篇题（`歌`、`断句`、`挽歌` 这类短题也会撞上人名）
          头 | 头 | 正文            作者 + 篇题（`高帝` / `大风歌`）
          头 | 头 | 头 | 正文       见下方四种三连

        三连里的第一个头，按这一行的样子分四种：

          * 行号在 AUTHOR_FIX：作者行被抄成了评语（`沈约` 那条是「家令诗，较之鲍、谢……」），
            作者照表，中间的评语行当地；
          * 在作者表里（`陆机`、`张华`）：作者 + 一行评语 + 篇题，中间的评语当地；
          * 以书名号、注引开头：篇题 + 题注 + 正文，中间的题注进 prologue；
          * 都不是：篇题 + 一行短注（`有会而作` / `旧谷既没…`）+ 正文。

        作者名 + 评语 + 正文（篇题底本漏抄，`张华` / `茂先诗，《诗品》谓…。` / `太仪斡运…`）
        由「头 | 头 | 正文」那一路处理：第二个头不在作者表、又不像篇题时，按漏抄处理。
        """
        segs = self._segs(start, end)
        blocks = []
        j = 0
        while j < len(segs):
            kind, ln, t = segs[j]
            if kind == 'section':
                blocks.append({'kind': 'section', 'name': t, 'line': ln})
                j += 1
                continue
            if kind == 'body':
                if blocks and blocks[-1]['kind'] in ('piece', 'meta'):
                    blocks[-1]['lines'].append((ln, t))
                else:
                    blocks.append({'kind': 'meta', 'text': t, 'line': ln})
                j += 1
                continue
            k = j + 1
            while k < len(segs) and segs[k][0] == 'head' and self._may_be_author(segs[k], segs, k) \
                    and (k == j + 1 or segs[k - 1][2] not in AUTHORS or segs[k][2] in AUTHORS):
                # 串起「头」：前一个头是作者名时，后一个头要么也是作者名（三连里的第二个），
                # 要么就到此为止（`左思` / `杂诗`：左思自己就是篇题前的作者）
                k += 1
            n_head = k - j
            if k >= len(segs) or segs[k][0] != 'body':
                # 这一行后面没有正文：作者名（也可能是底本漏抄篇题时作者名后面紧跟评语）
                blocks.append({'kind': 'author', 'text': t, 'line': ln})
                j += 1
                continue
            if n_head == 1 and t in AUTHORS and len(t) <= 4 and segs[k][2].endswith('。') \
                    and len(segs[k][2]) > 24:
                # 作者名 + 一长段评语 + 正文，篇题底本漏抄（`张华` / `茂先诗，《诗品》谓…`）
                blocks.append({'kind': 'author', 'text': t, 'line': ln})
                blocks.append({'kind': 'piece', 'title': '', 'line': segs[k][1],
                               'lines': [(segs[k][1], segs[k][2])]})
                j = k + 1
                continue
            if n_head == 1:
                blocks.append({'kind': 'piece', 'title': t, 'line': ln,
                               'lines': [(segs[k][1], segs[k][2])]})
                j = k + 1
                continue
            blocks += self._split_heads(segs[j:k], segs[k])
            j = k + 1
        return blocks

    def _segs(self, start, end):
        segs, i, prev_blank = [], start, True
        while i < end:
            t = self.lines[i].strip().strip('\u3000')
            if not t:
                prev_blank = True
                i += 1
                continue
            if t.startswith('○'):
                segs.append(('section', i + 1, t[1:]))
                prev_blank = True
                i += 1
                continue
            if prev_blank and not BREAK.search(t) and len(t) <= 14:
                segs.append(('head', i + 1, t))
            else:
                segs.append(('body', i + 1, t))
            prev_blank = False
            i += 1
        return segs

    @staticmethod
    def _may_be_author(seg, segs, k):
        """这一行「头」是不是作者行：它后面还得跟着正文，且自己不是明显的题注。"""
        ln, t = seg[1], seg[2]
        if ln in AUTHOR_FIX or (t in AUTHORS and len(t) <= 4 and t not in TITLE_WORDS):
            return True
        if re.match(r'^(一作|见《|以下)', t):
            return False
        return any(s[0] == 'body' for s in segs[k + 1:k + 3])

    def _is_comment(self, ln):
        """这一行是评语（长句、无篇题）还是篇题。

        `陆机` 那条评语在底本里占了两行（第二行是 `…殊非诗人之旨。”` 的续行），
        所以看的是整段（一直读到空行）的长度。
        """
        i = ln - 1
        text = ''
        while i < len(self.lines) and self.lines[i].strip():
            text += self.lines[i].strip().strip('\u3000')
            i += 1
        return len(text) > 14

    def _split_heads(self, heads, body):
        """一串「头」加后面的正文 → 块序列。"""
        first_ln, first_t = heads[0][1], heads[0][2]
        last_ln, last_t = heads[-1][1], heads[-1][2]
        piece = {'kind': 'piece', 'title': last_t, 'line': last_ln,
                 'lines': [(body[1], body[2])]}
        piece_nobody = {'kind': 'piece', 'title': last_t, 'line': last_ln, 'lines': []}
        if len(heads) == 2:
            # 作者 + 篇题（`高帝` / `大风歌`）
            return [{'kind': 'author', 'text': first_t, 'line': first_ln}, piece]
        mid_ln, mid_t = heads[1][1], heads[1][2]
        if first_ln in AUTHOR_FIX:
            # 作者行被抄成评语（`沈约` / `家令诗，较之鲍、谢……` / `临高台`）
            return [{'kind': 'author', 'text': AUTHOR_FIX[first_ln], 'line': first_ln},
                    {'kind': 'meta', 'text': mid_t, 'line': mid_ln}, piece]
        if first_t in AUTHORS and len(first_t) <= 4 and mid_t not in AUTHORS:
            # 作者 + 一行评语 + 篇题（`陆机` / `士衡诗亦推大家…` / `短歌行`；
            # `张华` / `茂先诗，《诗品》谓…` / `太仪斡运…` 的篇题底本漏抄，用首句补）
            return [{'kind': 'author', 'text': first_t, 'line': first_ln},
                    {'kind': 'meta', 'text': mid_t, 'line': mid_ln},
                    dict(piece, title='' if self._is_comment(mid_ln) else last_t)]
        if PROSE_HEAD.match(mid_t):
            # 篇题 + 题注 + 正文（`太公兵法引黄帝语` / `以下古逸谐语。` / `日中不彗…`）
            head = dict(piece_nobody, title=first_t, line=first_ln, prologue=[mid_t],
                        lines=[(body[1], body[2])])
            return [head]
        # 篇题 + 一行短注 + 正文（`有会而作` / `旧谷既没…` / `弱年逢家乏…`）
        head = dict(piece_nobody, title=first_t, line=first_ln, prologue=[mid_t],
                    lines=[(body[1], body[2])])
        return [head]


# ---------------------------------------------------------------- 正文与夹注

def to_paras(raw):
    """一行底本 → (正文, [夹注])。

    行内夹注（`糺【同纠。】缦缦兮`）与行末评点（`…。【旦复旦隐寓禅代之旨。】`）
    都是方括号，写法上分不开：一律抽出进 notes，正文按抽出后的顺序读。
    """
    notes = [m.group(1).strip() for m in NOTE.finditer(raw) if m.group(1).strip()]
    text = NOTE.sub('', raw)
    return text.strip(), notes


PROSE_HEAD = re.compile(r'^(《|事见|歌见|以下|详见|此将|元封|东汉|西京|一作)')
# 本事（诗前小序）的另一种写法：直接叙事、不带书名号（`汉末建安中，庐江府小吏……时伤之为诗云尔`）
PROSE_BODY = re.compile(r'^(汉末|建安|元嘉|永明|天监|大历|开元|先是|初，|其后|晋太元)')
# 题注（不是本事）：`十九首非一人一时作，……从《昭明》为允。`
PROSE_NOTE = re.compile(r'^(十九首|苏李诗|此曲|此诗|《?[^，。]{1,6}》?共[一二三四五六七八九十]+首)')


# 底本里 PUA 码位的用法（逐个核过，5 个码位 258 次）：
#   U+E3AC  评语内部的分隔符（排印本的分号）→ 「；」
#   U+E2EA  `山林\ue2ea冥` ＝ 窅冥 的「窅」漏字，底本作「杳冥」义，补「杳」
#   U+E3DA  `耳著明月\ue3da` ＝ 明月珰 的「珰」漏字
#   U+E845  `魏人公\ue845` ＝ 公讌 的「讌」漏字
#   U+E848  `■〈\ue848必〉跋` ＝ 字形描述里的「𨁂」，照底本留字形描述，去掉 PUA
PUA_DELIM = '\ue3ac'


PUA_FIX = {'\ue3ac': '；', '\ue2ea': '杳', '\ue3da': '珰', '\ue845': '讌', '\ue848': ''}


def normalize(text):
    for k, v in PUA_FIX.items():
        text = text.replace(k, v)
    return text


def split_note(text):
    """一行底本 → (正文, [注])。

    `【…】` 是沈德潜的夹注与评点，形状相同，按位置分：

      * 行末的（后面再没有正文）：评点，整条抽出；
      * 句子中间的（`糺【同纠。】缦缦兮`）：夹注，抽出后在 notes 里用 `【】` 还原，
        这样知道它注的是哪个字；
      * 抽完只剩标点的（`【阙。】` 单独一段）：整行都是注。
    """
    text = normalize(text)
    notes, out, pos = [], '', 0
    for m in NOTE.finditer(text):
        before, inner = text[pos:m.start()], m.group(1).strip()
        pos = m.end()
        out += before
        if not inner:
            continue
        tail = text[pos:]
        if not re.search(r'[\u3400-\u9fff]', tail):
            notes.append(inner)                  # 行末评点
        else:
            out += '【' + inner + '】'           # 句中夹注：留在正文位置
            notes.append('【' + inner + '】')
    out += text[pos:]
    body = out.strip()
    if not re.search(r'[\u3400-\u9fff]', body):
        return '', notes
    return declaim(body, notes)


# 底本漏了方括号的评语（`…何时旦。长夜句感慨。`、`…永矢勿告意。`）：句末这几句是评点，
# 不是正文。判据是「末尾那一句很短、与前面的句读节奏不合」，逐条列在这里，不猜。
TAIL_NOTE = {
    '长夜句感慨。',
    '即独寐寤宿，永矢勿告意。',
    '写来合并无迹。',
    '杨枯十字作意。',
    '二章稍见凄切。',
}


def declaim(body, notes):
    """正文末尾粘着的评语（底本漏了方括号）拆进 notes。"""
    for tail in TAIL_NOTE:
        if body.endswith(tail):
            head = body[:-len(tail)].rstrip()
            if re.search(r'[\u3400-\u9fff]', head):
                notes.append(tail.rstrip('。'))
                body = head
            break
    return body, notes


def build_record(title, author, lines, section, line_no):
    """一个 piece 块 → 数据集记录。

    * `paragraphs`：一首一段，底本一首多行的按行拆段
    * `notes`：行内夹注与沈德潜的评点，按行累计
    * `prologue`：正文之前那段引书 / 本事（`《史记》：……`、`以下铭辞见《大戴礼》。`）
    * 题名底本没抄的（作者行被抄成评语、作者名与篇题之间多一行），按首句补
    """
    paras, notes, prologue = [], [], []
    for k, (ln, raw) in enumerate(lines):
        text, got = split_note(raw)
        if not text:
            notes += got
            continue
        if k == 0 and len(lines) > 1 and (PROSE_BODY.match(text) or PROSE_NOTE.match(text)
                                          or (PROSE_HEAD.match(text) and text.endswith(('：', '曰：', '云尔。')))):
            # 首行是引书 / 本事（`《史记》：……`、`汉末建安中，庐江府小吏……`）：
            # 收进 prologue。但判据不能只看行首，末尾是冒号的、或在末行以外的长句都算
            prologue.append(text)
            continue
        # 一行里既没有句读、又不长于 12 字的，是夹在正文之间的注（`【叶姑。】兽臣司原，敢告仆夫。`
        # 这种已由 split_note 处理）；剩下整行都是注的，直接进 notes
        if PROSE_NOTE.match(text) and len(lines) > 2:
            # 题注（`十九首非一人一时作，……`、`苏李诗一唱三叹……`）放在正文之前，进 prologue
            prologue.append(text)
            continue
        if not re.search(r'[，。！？；：、]', text) and len(han(text)) <= 12 and paras:
            notes.append(text)
            continue
        paras.append(text)
        notes += got
    if not paras:
        return None
    if not title:
        title = first_sentence(paras)
    else:
        title = NOTE.sub('', title).strip()          # 篇题里【并序】这类是注，不进题名
        if not title:
            title = first_sentence(paras)
    rec = OrderedDict()
    rec['author'] = author or '无名氏'
    rec['title'] = title
    if section:
        rec['section'] = section
    rec['paragraphs'] = paras
    if prologue:
        rec['prologue'] = prologue
    if notes:
        rec['notes'] = notes
    rec['source_line'] = line_no
    return rec


def reference_note(same):
    """重复篇目只留指针：正文位置写一句「见某书某人某题」，不存第二份正文。"""
    author = same.get('author') or ''
    title = same.get('title') or ''
    book = same.get('book') or ''
    where = '、'.join(x for x in (book, author and f'{author}《{title}》') if x)
    if not where and title:
        where = f'《{title}》'
    return [f'（正文同{where or "库内已有条目"}，见该条）']


def first_sentence(paras):
    """底本没抄篇题时按首句补：取第一段里的第一句，长于 12 字截前 12 字。"""
    first = re.split(r'[，。！？；：]', han(NOTE.sub('', paras[0])))[0].strip()
    return (first or han(paras[0]))[:12] or '断句'


def load_dynasty(root=ROOT):
    """作者 → 朝代。

    先查 `authors/authors.json`，查不到的照底本所在卷次补（卷二～四汉、卷五～六魏、
    卷七～九晋、卷十～十一宋齐、卷十二～十三梁陈、卷十四北魏北齐北周隋）。
    同名的两汉／南北朝两个人（王褒）按卷次分开。
    """
    try:
        from opencc import OpenCC
        t2s, s2t = OpenCC('t2s').convert, OpenCC('s2t').convert
    except ImportError:
        t2s = s2t = lambda x: x
    table = {}
    with open(os.path.join(root, 'authors/authors.json'), encoding='utf-8') as fp:
        for a in json.load(fp):
            if a.get('name'):
                table[a['name']] = a.get('dynasty') or ''
    flat = {}
    for k, v in table.items():
        flat[k] = v
        flat[t2s(k)] = v
        flat[s2t(k)] = v
    flat.update(AUTHOR_DYNASTY)
    return flat


# 与库内作者名撞车的篇题：`短歌行` 也是乐府题，不能因为作者表里有人叫这名字就当作者
TITLE_WORDS = {'左思', '张华', '陆机', '陆云', '陶潜', '江淹', '沈约', '何逊', '范云',
               '吴均', '王褒', '庾信', '谢朓', '鲍照', '颜延之', '谢灵运', '傅玄', '束皙',
               '张载', '张协', '张翰', '曹植', '曹操', '王粲', '陈琳', '刘桢', '阮籍',
               '嵇康', '郭璞', '刘琨', '潘岳', '左贵嫔', '孙楚', '曹摅', '王赞', '郭泰机',
               '司马彪', '司马懿', '薛道衡', '杨素', '卢思道', '虞世基', '孙万寿', '王胄',
               '尹式', '孔德绍', '孔绍安', '陈子良', '王申礼', '吕让', '明余庆', '阴铿',
               '徐陵', '周弘让', '周弘正', '江总', '张正见', '何胥', '韦鼎', '陈昭',
               '刘昶', '常景', '温子升', '胡叟', '胡太后', '邢邵', '祖珽', '郑公超',
               '萧悫', '颜之推', '冯淑妃', '斛律金', '阳休之', '魏收', '苏武', '李陵',
               '蔡邕', '秦嘉', '孔融', '诸葛亮', '韦孟', '东方朔', '卓文君', '班固',
               '张衡', '李尤', '梁鸿', '马援', '杨恽', '王昭君', '班婕妤', '赵飞燕'}


# 底本卷次 → 朝代（作者表查不到时兜底；卷十四的几段按 ○ 时段再细分）
VOL_DYNASTY = {1: '先秦', 2: '汉', 3: '汉', 4: '汉', 5: '三国', 6: '三国',
               7: '晋', 8: '晋', 9: '晋', 10: '南北朝', 11: '南北朝',
               12: '南北朝', 13: '南北朝', 14: '隋'}
SECTION_DYNASTY = {'北魏诗【附】': '南北朝', '北齐诗【附】': '南北朝',
                   '北周诗【附】': '南北朝', '隋诗': '隋', '陈诗': '南北朝',
                   '梁诗': '南北朝', '齐诗': '南北朝', '宋诗': '南北朝'}


# 与库内已有正文逐字相同的篇目：只留指针（`same_as`），不再存第二份正文。
# 键是底本行号，值是正文已在的那条记录的 id；明细见 docs/古诗源去重.tsv
DUP_POINTER = json.load(open(os.path.join(ROOT, 'docs/古诗源去重.json'), encoding='utf-8')) \
    if os.path.exists(os.path.join(ROOT, 'docs/古诗源去重.json')) else {}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--apply', action='store_true', help='写盘；否则只预演')
    ap.add_argument('--batch', type=int, default=0, help='只写前 N 卷（0 为整本）')
    ap.add_argument('--date', default=date.today().isoformat())
    args = ap.parse_args()

    p = Parser()
    pieces = p.pieces()
    by_vol = OrderedDict()
    for vol, section, author, title, lines, ln in pieces:
        by_vol.setdefault(vol, []).append((section, author, title, lines, ln))

    print(f'底本 {len(p.lines)} 行，{len(by_vol)} 卷，{len(pieces)} 篇')
    for vol, items in by_vol.items():
        authors = {a for _, a, _, _, _ in items if a}
        print(f'  卷{int2cn(vol):<3} {len(items):>3} 篇  {len(authors):>3} 位作者')
    if not args.apply:
        return

    os.makedirs(os.path.join(ROOT, OUT), exist_ok=True)
    dyna = load_dynasty()
    taken = set()
    toc = []
    for vol, items in by_vol.items():
        out = []
        for section, author, title, lines, ln in items:
            rec = build_record(title, author, lines, section, ln)
            if not rec:
                continue
            key = '|'.join([rec['author'], title, ''.join(rec['paragraphs'])])
            rec_id = base22(key, 6, taken)
            item = OrderedDict()
            item['author'] = rec['author']
            item['title'] = rec['title']
            sec = rec.get('section', section)
            item['dynasty'] = SECTION_DYNASTY.get(sec) or VOL_DYNASTY[vol] \
                or dyna.get(rec['author'])
            if sec:
                item['section'] = sec
            item['paragraphs'] = rec['paragraphs']
            if rec.get('prologue'):
                item['prologue'] = rec['prologue']
            if rec.get('notes'):
                item['notes'] = rec['notes']
            item['tags'] = ['古诗源', f'卷{int2cn(vol)}']
            item['source_line'] = ln
            item['id'] = rec_id
            same = DUP_POINTER.get(str(ln))
            if same:
                # 指针条目作者照底本（`无名氏`、`乐府歌辞` 照抄）；对方作者记在 `notes` 里，
                # 底本把《观沧海》《寄徐陵》抄在「无名氏」下的地方不改
                pass
                item['same_as'] = same['id']
                item['paragraphs'] = reference_note(same)
                if same.get('title') and same['title'] != item['title']:
                    item['same_title'] = same['title']
            out.append(item)
        rel = f'{OUT}/卷{int2cn(vol)}.json'
        with open(os.path.join(ROOT, rel), 'w', encoding='utf-8') as fp:
            json.dump(out, fp, ensure_ascii=False, indent=2)
            fp.write('\n')
        pg.merge(rel, {
            'note': f'依 reference/古诗源.txt 录入《古诗源》卷{int2cn(vol)}：{len(out)} 篇，'
                    '正文照底本，未与别本逐字对勘',
            'date': args.date,
            'reviewer': REVIEWER,
            'status': 'needs_review',
        })
        toc.append({'volume': int2cn(vol), 'count': len(out),
                    'titles': [f"{r['title']}　{r['author']}" for r in out]})
        print(f'→ {rel} {len(out)} 篇')
    with open(os.path.join(ROOT, OUT, '古诗源.json'), 'w', encoding='utf-8') as fp:
        json.dump(toc, fp, ensure_ascii=False, indent=2)
        fp.write('\n')


if __name__ == '__main__':
    sys.exit(main())
