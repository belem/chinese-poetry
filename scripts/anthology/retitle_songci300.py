#!/usr/bin/env python3
"""《宋词三百首》的篇目改名：`rhythmic` 只写词牌时，`title` 补成「词牌·正文首句」。

不改 `rhythmic`，只填 / 换 `title`。选本里的词只写词牌（`浣溪沙`、`木兰花`、`贺新郎`）
分不清是哪一首，编目、检索、去重都对不上；首句是这本书自己用的标识。

首句取**底本正文**的前 12 个汉字（识典古籍朱祖谋集解本，`anthologies/songci300.json` 的
`first_line` 就是它），去掉标点直接接在词牌后面。底本这条 `first_line` 若只有半句
（第 232 首陸叡《瑞鶴仙》，底本分章把「溼雲黏」切到了上一章），补到 12 字。

  python3 scripts/anthology/retitle_songci300.py                     # 预演
  python3 scripts/anthology/retitle_songci300.py --apply --date YYYY-MM-DD --reviewer <名字>
"""
import argparse
import glob
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import progress as pg  # noqa: E402
from anthology.patch_json import patch  # noqa: E402
from opencc import OpenCC  # noqa: E402

S2T, T2S = OpenCC('s2t'), OpenCC('t2s')

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TAG = '宋词三百首'
SEP = '·'
RHYTHM_SEP = re.compile(r'[・·]')     # 词牌自身的两种写法之间用 ・（U+30FB），篇目分隔用·（U+00B7）
# 底本 first_line 不足 12 字的补足（底本分章把首句切到了上一章）。
HEAD_FIX = {232: '溼雲黏雁影望征路愁迷離緒難整'}

HAN = re.compile(r'[\u3400-\u9fff\U00020000-\U0003ffff\ue000-\uf8ff□〇]')
BOOK_FILE = None      # 底本逐章正文（识典古籍抓取结果），由 load_book() 定位


def load_book(spec):
    """读底本逐章正文：{目次号: [(lineType, content), …]}。

    8=作者 9=题名 2=副题/词序 1=正文，见 scripts/shidian/chapter.mjs 的说明。
    `spec` 可以是 chapter.mjs 的输出目录，也可以是事先拼好的 JSON（{号: 行列表}）。
    """
    if spec.endswith('.json'):
        return {int(k): [tuple(x) for x in v] for k, v in json.load(open(spec, encoding='utf-8')).items()}
    out = {}
    for no, fn in enumerate(sorted(glob.glob(os.path.join(spec, '*.json'))), 1):
        raw = open(fn, encoding='utf-8').read()
        i = raw.find('"paragraphList":')
        j = raw.index('[', i)
        depth = 0
        for k in range(j, len(raw)):
            if raw[k] == '[':
                depth += 1
            elif raw[k] == ']':
                depth -= 1
                if depth == 0:
                    break
        lines = []
        for p in json.loads(raw[j:k + 1]):
            for ln in json.loads(p['content']).get('lines', []):
                lines.append((ln.get('lineType'), ln.get('content')))
        out[no] = lines
    return out


BOOK = {}


def is_simplified(rec):
    """该记录正文是不是简体。库内宋词两批数据各用一种字形，不能一个文件一个文件地猜。"""
    txt = ''.join(p for p in rec['paragraphs'] if isinstance(p, str))
    return S2T.convert(txt) != txt

# 目次条目 → 库内记录：正文首句对得上的唯一一条（挂着 tag 的优先，两批数据各收一次时取与底本更近的一条）
PLAN = {
    1: ('宋/宋词/ci.song.22000.json', 961),
    2: ('宋/宋词/ci.song.22000.json', 37),
    3: ('宋/宋词/ci.song.0.json', 40),
    4: ('宋/宋词/ci.song.0.json', 961),
    5: ('宋/宋词/ci.song.22000.json', 38),
    6: ('宋/宋词/ci.song.22000.json', 962),
    7: ('宋/宋词/ci.song.22000.json', 963),
    8: ('宋/宋词/ci.song.22000.json', 964),
    9: ('宋/宋词/ci.song.22000.json', 39),
    10: ('宋/宋词/ci.song.0.json', 973),
    11: ('宋/宋词/ci.song.0.json', 975),
    12: ('宋/宋词/ci.song.0.json', 591),
    13: ('宋/宋词/ci.song.0.json', 976),
    14: ('宋/宋词/ci.song.22000.json', 142),
    15: ('宋/宋词/ci.song.0.json', 978),
    16: ('宋/宋词/ci.song.0.json', 977),
    17: ('宋/宋词/ci.song.0.json', 979),
    18: ('宋/宋词/ci.song.22000.json', 52),
    19: ('宋/宋词/ci.song.22000.json', 53),
    20: ('宋/宋词/ci.song.0.json', 980),
    21: ('宋/宋词/ci.song.22000.json', 965),
    22: ('宋/宋词/ci.song.0.json', 478),
    23: ('宋/宋词/ci.song.22000.json', 948),
    24: ('宋/宋词/ci.song.22000.json', 966),
    25: ('宋/宋词/ci.song.22000.json', 967),
    26: ('宋/宋词/ci.song.22000.json', 968),
    27: ('宋/宋词/ci.song.0.json', 984),
    28: ('宋/宋词/ci.song.22000.json', 969),
    29: ('宋/宋词/ci.song.22000.json', 970),
    30: ('宋/宋词/ci.song.22000.json', 971),
    31: ('宋/宋词/ci.song.22000.json', 43),
    32: ('宋/宋词/ci.song.0.json', 685),
    33: ('宋/宋词/ci.song.22000.json', 972),
    34: ('宋/宋词/ci.song.0.json', 988),
    35: ('宋/宋词/ci.song.22000.json', 974),
    36: ('宋/宋词/ci.song.22000.json', 975),
    37: ('宋/宋词/ci.song.22000.json', 23),
    38: ('宋/宋词/ci.song.0.json', 964),
    39: ('宋/宋词/ci.song.0.json', 963),
    40: ('宋/宋词/ci.song.22000.json', 44),
    41: ('宋/宋词/ci.song.0.json', 965),
    42: ('宋/宋词/ci.song.22000.json', 976),
    43: ('宋/宋词/ci.song.0.json', 967),
    44: ('宋/宋词/ci.song.0.json', 968),
    45: ('宋/宋词/ci.song.22000.json', 977),
    46: ('宋/宋词/ci.song.0.json', 969),
    47: ('宋/宋词/ci.song.0.json', 971),
    48: ('宋/宋词/ci.song.0.json', 970),
    49: ('宋/宋词/ci.song.22000.json', 978),
    50: ('宋/宋词/ci.song.22000.json', 979),
    51: ('宋/宋词/ci.song.22000.json', 980),
    52: ('宋/宋词/ci.song.22000.json', 981),
    53: ('宋/宋词/ci.song.22000.json', 982),
    54: ('宋/宋词/ci.song.22000.json', 983),
    55: ('宋/宋词/ci.song.22000.json', 984),
    56: ('宋/宋词/ci.song.1000.json', 133),
    57: ('宋/宋词/ci.song.22000.json', 985),
    58: ('宋/宋词/ci.song.22000.json', 986),
    59: ('宋/宋词/ci.song.22000.json', 987),
    60: ('宋/宋词/ci.song.22000.json', 46),
    61: ('宋/宋词/ci.song.22000.json', 988),
    62: ('宋/宋词/ci.song.22000.json', 989),
    63: ('宋/宋词/ci.song.22000.json', 990),
    64: ('宋/宋词/ci.song.22000.json', 47),
    65: ('宋/宋词/ci.song.22000.json', 991),
    66: ('宋/宋词/ci.song.22000.json', 992),
    67: ('宋/宋词/ci.song.22000.json', 993),
    68: ('宋/宋词/ci.song.22000.json', 994),
    69: ('宋/宋词/ci.song.1000.json', 317),
    70: ('宋/宋词/ci.song.22000.json', 995),
    71: ('宋/宋词/ci.song.22000.json', 996),
    72: ('宋/宋词/ci.song.1000.json', 442),
    73: ('宋/宋词/ci.song.22000.json', 55),
    74: ('宋/宋词/ci.song.22000.json', 997),
    75: ('宋/宋词/ci.song.22000.json', 8),
    76: ('宋/宋词/ci.song.22000.json', 998),
    77: ('宋/宋词/ci.song.22000.json', 999),
    78: ('宋/宋词/ci.song.22000.json', 1000),
    79: ('宋/宋词/ci.song.22000.json', 3),
    80: ('宋/宋词/ci.song.22000.json', 1001),
    81: ('宋/宋词/ci.song.22000.json', 1002),
    82: ('宋/宋词/ci.song.2000.json', 704),
    83: ('宋/宋词/ci.song.2000.json', 664),
    84: ('宋/宋词/ci.song.22000.json', 1003),
    85: ('宋/宋词/ci.song.3000.json', 730),
    86: ('宋/宋词/ci.song.22000.json', 1004),
    87: ('宋/宋词/ci.song.3000.json', 747),
    88: ('宋/宋词/ci.song.3000.json', 751),
    89: ('宋/宋词/ci.song.22000.json', 1005),
    90: ('宋/宋词/ci.song.22000.json', 1006),
    91: ('宋/宋词/ci.song.22000.json', 1007),
    92: ('宋/宋词/ci.song.22000.json', 65),
    93: ('宋/宋词/ci.song.1000.json', 119),
    94: ('宋/宋词/ci.song.3000.json', 855),
    95: ('宋/宋词/ci.song.22000.json', 1008),
    96: ('宋/宋词/ci.song.22000.json', 1009),
    97: ('宋/宋词/ci.song.22000.json', 1010),
    98: ('宋/宋词/ci.song.4000.json', 155),
    99: ('宋/宋词/ci.song.22000.json', 1011),
    100: ('宋/宋词/ci.song.22000.json', 1012),
    101: ('宋/宋词/ci.song.22000.json', 1013),
    102: ('宋/宋词/ci.song.22000.json', 28),
    103: ('宋/宋词/ci.song.22000.json', 69),
    104: ('宋/宋词/ci.song.22000.json', 1014),
    105: ('宋/宋词/ci.song.22000.json', 1015),
    106: ('宋/宋词/ci.song.22000.json', 1016),
    107: ('宋/宋词/ci.song.22000.json', 1017),
    108: ('宋/宋词/ci.song.22000.json', 59),
    109: ('宋/宋词/ci.song.22000.json', 60),
    110: ('宋/宋词/ci.song.22000.json', 1018),
    111: ('宋/宋词/ci.song.22000.json', 1019),
    112: ('宋/宋词/ci.song.22000.json', 1020),
    113: ('宋/宋词/ci.song.22000.json', 1021),
    114: ('宋/宋词/ci.song.22000.json', 1022),
    115: ('宋/宋词/ci.song.22000.json', 62),
    116: ('宋/宋词/ci.song.22000.json', 63),
    117: ('宋/宋词/ci.song.22000.json', 64),
    118: ('宋/宋词/ci.song.22000.json', 1023),
    119: ('宋/宋词/ci.song.22000.json', 1024),
    120: ('宋/宋词/ci.song.22000.json', 70),
    121: ('宋/宋词/ci.song.22000.json', 1025),
    122: ('宋/宋词/ci.song.4000.json', 444),
    123: ('宋/宋词/ci.song.22000.json', 1026),
    124: ('宋/宋词/ci.song.22000.json', 1027),
    125: ('宋/宋词/ci.song.22000.json', 1028),
    126: ('宋/宋词/ci.song.22000.json', 1029),
    127: ('宋/宋词/ci.song.22000.json', 1030),
    128: ('宋/宋词/ci.song.22000.json', 1031),
    129: ('宋/宋词/ci.song.22000.json', 74),
    130: ('宋/宋词/ci.song.3000.json', 943),
    131: ('宋/宋词/ci.song.22000.json', 30),
    132: ('宋/宋词/ci.song.22000.json', 76),
    133: ('宋/宋词/ci.song.22000.json', 1032),
    134: ('宋/宋词/ci.song.22000.json', 78),
    135: ('宋/宋词/ci.song.22000.json', 79),
    136: ('宋/宋词/ci.song.22000.json', 80),
    137: ('宋/宋词/ci.song.22000.json', 1033),
    138: ('宋/宋词/ci.song.22000.json', 1034),
    139: ('宋/宋词/ci.song.22000.json', 1035),
    140: ('宋/宋词/ci.song.22000.json', 1036),
    141: ('宋/宋词/ci.song.22000.json', 82),
    142: ('宋/宋词/ci.song.22000.json', 83),
    143: ('宋/宋词/ci.song.22000.json', 1037),
    144: ('宋/宋词/ci.song.22000.json', 1038),
    145: ('宋/宋词/ci.song.22000.json', 1039),
    146: ('宋/宋词/ci.song.22000.json', 1040),
    147: ('宋/宋词/ci.song.22000.json', 87),
    148: ('宋/宋词/ci.song.22000.json', 1041),
    149: ('宋/宋词/ci.song.22000.json', 148),
    150: ('宋/宋词/ci.song.22000.json', 1042),
    151: ('宋/宋词/ci.song.22000.json', 1043),
    152: ('宋/宋词/ci.song.22000.json', 1044),
    153: ('宋/宋词/ci.song.22000.json', 1045),
    154: ('宋/宋词/ci.song.22000.json', 1046),
    155: ('宋/宋词/ci.song.22000.json', 1047),
    156: ('宋/宋词/ci.song.22000.json', 1048),
    157: ('宋/宋词/ci.song.22000.json', 1049),
    158: ('宋/宋词/ci.song.22000.json', 1050),
    159: ('宋/宋词/ci.song.22000.json', 88),
    160: ('宋/宋词/ci.song.22000.json', 89),
    161: ('宋/宋词/ci.song.22000.json', 1051),
    162: ('宋/宋词/ci.song.22000.json', 1052),
    163: ('宋/宋词/ci.song.22000.json', 1053),
    164: ('宋/宋词/ci.song.22000.json', 1054),
    165: ('宋/宋词/ci.song.22000.json', 1055),
    166: ('宋/宋词/ci.song.22000.json', 1056),
    167: ('宋/宋词/ci.song.22000.json', 1057),
    168: ('宋/宋词/ci.song.22000.json', 1058),
    169: ('宋/宋词/ci.song.22000.json', 1059),
    170: ('宋/宋词/ci.song.22000.json', 1060),
    171: ('宋/宋词/ci.song.22000.json', 1061),
    172: ('宋/宋词/ci.song.22000.json', 1062),
    173: ('宋/宋词/ci.song.22000.json', 1063),
    174: ('宋/宋词/ci.song.22000.json', 1064),
    175: ('宋/宋词/ci.song.22000.json', 1065),
    176: ('宋/宋词/ci.song.22000.json', 1066),
    177: ('宋/宋词/ci.song.22000.json', 1067),
    178: ('宋/宋词/ci.song.9000.json', 874),
    179: ('宋/宋词/ci.song.9000.json', 802),
    180: ('宋/宋词/ci.song.22000.json', 1068),
    181: ('宋/宋词/ci.song.22000.json', 92),
    182: ('宋/宋词/ci.song.22000.json', 1069),
    183: ('宋/宋词/ci.song.22000.json', 1070),
    184: ('宋/宋词/ci.song.22000.json', 1071),
    185: ('宋/宋词/ci.song.22000.json', 96),
    186: ('宋/宋词/ci.song.22000.json', 1072),
    187: ('宋/宋词/ci.song.22000.json', 1073),
    188: ('宋/宋词/ci.song.22000.json', 1074),
    189: ('宋/宋词/ci.song.22000.json', 27),
    190: ('宋/宋词/ci.song.22000.json', 97),
    191: ('宋/宋词/ci.song.22000.json', 1075),
    192: ('宋/宋词/ci.song.22000.json', 1076),
    193: ('宋/宋词/ci.song.22000.json', 1077),
    194: ('宋/宋词/ci.song.22000.json', 1078),
    195: ('宋/宋词/ci.song.22000.json', 100),
    196: ('宋/宋词/ci.song.22000.json', 1079),
    197: ('宋/宋词/ci.song.22000.json', 101),
    198: ('宋/宋词/ci.song.22000.json', 1080),
    199: ('宋/宋词/ci.song.22000.json', 1081),
    200: ('宋/宋词/ci.song.22000.json', 1082),
    201: ('宋/宋词/ci.song.22000.json', 1083),
    202: ('宋/宋词/ci.song.22000.json', 1084),
    203: ('宋/宋词/ci.song.22000.json', 1085),
    204: ('宋/宋词/ci.song.22000.json', 1086),
    205: ('宋/宋词/ci.song.22000.json', 1087),
    206: ('宋/宋词/ci.song.22000.json', 1088),
    207: ('宋/宋词/ci.song.22000.json', 1089),
    208: ('宋/宋词/ci.song.22000.json', 1090),
    209: ('宋/宋词/ci.song.22000.json', 1091),
    210: ('宋/宋词/ci.song.22000.json', 1092),
    211: ('宋/宋词/ci.song.22000.json', 1093),
    212: ('宋/宋词/ci.song.22000.json', 1094),
    213: ('宋/宋词/ci.song.22000.json', 1095),
    214: ('宋/宋词/ci.song.22000.json', 104),
    215: ('宋/宋词/ci.song.22000.json', 1096),
    216: ('宋/宋词/ci.song.22000.json', 105),
    217: ('宋/宋词/ci.song.22000.json', 1097),
    218: ('宋/宋词/ci.song.22000.json', 1098),
    219: ('宋/宋词/ci.song.22000.json', 1099),
    220: ('宋/宋词/ci.song.22000.json', 1100),
    221: ('宋/宋词/ci.song.22000.json', 1101),
    222: ('宋/宋词/ci.song.22000.json', 1102),
    223: ('宋/宋词/ci.song.22000.json', 1103),
    224: ('宋/宋词/ci.song.22000.json', 1104),
    225: ('宋/宋词/ci.song.22000.json', 1105),
    226: ('宋/宋词/ci.song.22000.json', 1106),
    227: ('宋/宋词/ci.song.22000.json', 1107),
    228: ('宋/宋词/ci.song.22000.json', 108),
    229: ('宋/宋词/ci.song.22000.json', 1108),
    230: ('宋/宋词/ci.song.22000.json', 1109),
    231: ('宋/宋词/ci.song.16000.json', 171),
    232: ('宋/宋词/ci.song.22000.json', 1110),
    233: ('宋/宋词/ci.song.15000.json', 806),
    234: ('宋/宋词/ci.song.22000.json', 1111),
    235: ('宋/宋词/ci.song.22000.json', 1112),
    236: ('宋/宋词/ci.song.22000.json', 1113),
    237: ('宋/宋词/ci.song.22000.json', 114),
    238: ('宋/宋词/ci.song.23000.json', 0),
    239: ('宋/宋词/ci.song.22000.json', 1114),
    240: ('宋/宋词/ci.song.22000.json', 1115),
    241: ('宋/宋词/ci.song.22000.json', 1116),
    242: ('宋/宋词/ci.song.22000.json', 1117),
    243: ('宋/宋词/ci.song.22000.json', 116),
    244: ('宋/宋词/ci.song.22000.json', 1118),
    245: ('宋/宋词/ci.song.22000.json', 1119),
    246: ('宋/宋词/ci.song.22000.json', 1120),
    247: ('宋/宋词/ci.song.22000.json', 1121),
    248: ('宋/宋词/ci.song.22000.json', 1122),
    249: ('宋/宋词/ci.song.22000.json', 119),
    250: ('宋/宋词/ci.song.22000.json', 120),
    251: ('宋/宋词/ci.song.22000.json', 1123),
    252: ('宋/宋词/ci.song.22000.json', 1124),
    253: ('宋/宋词/ci.song.22000.json', 121),
    254: ('宋/宋词/ci.song.22000.json', 1125),
    255: ('宋/宋词/ci.song.22000.json', 1126),
    256: ('宋/宋词/ci.song.22000.json', 122),
    257: ('宋/宋词/ci.song.22000.json', 1127),
    258: ('宋/宋词/ci.song.22000.json', 1128),
    259: ('宋/宋词/ci.song.22000.json', 1129),
    260: ('宋/宋词/ci.song.22000.json', 1130),
    261: ('宋/宋词/ci.song.22000.json', 1131),
    262: ('宋/宋词/ci.song.22000.json', 1132),
    263: ('宋/宋词/ci.song.22000.json', 1133),
    264: ('宋/宋词/ci.song.22000.json', 1134),
    265: ('宋/宋词/ci.song.22000.json', 125),
    266: ('宋/宋词/ci.song.22000.json', 1135),
    267: ('宋/宋词/ci.song.22000.json', 1136),
    268: ('宋/宋词/ci.song.22000.json', 1137),
    269: ('宋/宋词/ci.song.22000.json', 1138),
    270: ('宋/宋词/ci.song.22000.json', 1139),
    271: ('宋/宋词/ci.song.22000.json', 1140),
    272: ('宋/宋词/ci.song.22000.json', 134),
    273: ('宋/宋词/ci.song.22000.json', 1141),
    274: ('宋/宋词/ci.song.22000.json', 1142),
    275: ('宋/宋词/ci.song.22000.json', 137),
    276: ('宋/宋词/ci.song.22000.json', 138),
    277: ('宋/宋词/ci.song.22000.json', 139),
    278: ('宋/宋词/ci.song.22000.json', 1143),
    279: ('宋/宋词/ci.song.22000.json', 1144),
    280: ('宋/宋词/ci.song.6000.json', 674),
    281: ('宋/宋词/ci.song.22000.json', 1145),
    282: ('宋/宋词/ci.song.22000.json', 1146),
    283: ('宋/宋词/ci.song.22000.json', 1147),
    284: ('宋/宋词/ci.song.22000.json', 1148),
}

# 底本词牌名的两种写法：底本沿用的别调名，落库时用本库词牌。
TITLE_FIX = {
    238: ('浣溪沙·門隔花深夢舊游', '浣溪沙'),
}


# 同一首选本收一次、库里两批数据各收一次（`ci.song.0.json` 一批简体、`ci.song.22000.json` 一批），
# 两批都挂着「宋词三百首」。PLAN 只落到其中一条，另一条同名的也得改，否则同一首仍有「词牌」和「词牌·首句」
# 两副面孔。值是该首在目次里的编号，标题取 PLAN 那条的词牌 + 首句。
DUPLICATES = {
    ('宋/宋词/ci.song.0.json', 962): 36,
    ('宋/宋词/ci.song.0.json', 966): 42,
    ('宋/宋词/ci.song.0.json', 972): 8,
    ('宋/宋词/ci.song.0.json', 974): 6,
    ('宋/宋词/ci.song.0.json', 981): 21,      # 以下几条两批首句有一字出入，按目次编号认的
    ('宋/宋词/ci.song.0.json', 982): 25,
    ('宋/宋词/ci.song.0.json', 983): 26,
    ('宋/宋词/ci.song.0.json', 985): 28,
    ('宋/宋词/ci.song.0.json', 986): 137,
    ('宋/宋词/ci.song.0.json', 987): 17,
    ('宋/宋词/ci.song.22000.json', 45): 45,
    ('宋/宋词/ci.song.22000.json', 973): 34,
    ('宋/宋词/ci.song.23000.json', 1): 74,
}

def head_text(no, rec):
    """首句前 12 个汉字（去标点），取库内正文、按本文件自己的简繁写法，与该首其余文字一致。

    底本正文是繁体，本库这两批数据一个文件简体、一个文件繁体，所以首句从**库内正文**取，
    只借底本补第 232 首那种底本分章切掉的开头（HEAD_FIX）。
    """
    raw = HEAD_FIX.get(no) or ''.join(p for p in rec['paragraphs'] if isinstance(p, str))
    head = ''.join(HAN.findall(raw))[:12]
    if HEAD_FIX.get(no):
        head = S2T.convert(head) if not is_simplified(rec) else T2S.convert(head)
    return head


def new_title(no, rec, head_from=None):
    """「词牌·正文首句」。词牌用记录自己的 rhythmic（本库词牌名），首句取底本正文。"""
    if no in TITLE_FIX:
        # 底本 / 目录已给出小题的，小题里往往带着词牌（「浣溪沙·门隔花深梦旧游」），只取小题
        return TITLE_FIX[no][0]

    def fix(rhythm):
        # 「凤栖梧・蝶恋花」「青门引・青门饮」这类是同一调的两种写法，分隔符换成·
        return SEP.join(part.strip() for part in RHYTHM_SEP.split(rhythm) if part.strip())

    return fix(rec['rhythmic']) + SEP + head_text(no, head_from or rec)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--book', required=True, help='底本逐章正文：chapter.mjs 的输出目录或拼好的 JSON')
    ap.add_argument('--apply', action='store_true')
    ap.add_argument('--date')
    ap.add_argument('--reviewer')
    args = ap.parse_args()

    global BOOK
    BOOK = load_book(args.book)
    files = {}
    changed = {}
    untagged = []
    for no in sorted(PLAN):
        rel, idx = PLAN[no]
        if rel not in files:
            files[rel] = json.load(open(os.path.join(ROOT, rel), encoding='utf-8'))
        data = files[rel]
        rec = data[idx]
        if TAG not in (rec.get('tags') or []):
            untagged.append(f'第 {no} 首 {rel}#{idx}')
        title = new_title(no, rec)
        if title != rec.get('title'):
            changed.setdefault(rel, []).append((no, idx, rec.get('title'), title))
            rec['title'] = title

    # 同一首的另一副本（两批数据各收一次）也改成同一个篇目，词牌取那条自己的
    for (rel, idx), no in sorted(DUPLICATES.items()):
        if rel not in files:
            files[rel] = json.load(open(os.path.join(ROOT, rel), encoding='utf-8'))
        rec, primary = files[rel][idx], files[PLAN[no][0]][PLAN[no][1]]
        if TAG not in (rec.get('tags') or []):
            continue
        title = new_title(no, rec, head_from=primary)
        if title != rec.get('title'):
            changed.setdefault(rel, []).append((no, idx, rec.get('title'), title))

    for rel, ops in sorted(changed.items()):
        print(f'{rel}: {len(ops)} 处')
        for no, idx, old, new in ops[:4]:
            print(f'    #{idx} {old or "（无）"} → {new}')
    print(f'合计 {sum(len(v) for v in changed.values())} 首改名，涉及 {len(changed)} 个文件')
    if untagged:
        # 选本第 3 首范仲淹《渔家傲》在库里另有同文副本（ci.song.0.json#40）没挂 tag，
        # 这是选本对齐的事（scripts/check_anthology.py），不在这里补 tag，只提示。
        print(f'{len(untagged)} 首落在没挂「宋词三百首」tag 的记录上（只改名，不补 tag）：')
        for x in untagged:
            print('    ' + x)
    if not args.apply:
        return
    if not (args.date and args.reviewer):
        sys.exit('--apply 需要 --date 与 --reviewer')

    for rel in sorted(changed):
        # 只替换 title 那一段，不重排整个文件（这些文件各有一种行尾空格的习惯）
        patch(rel, {idx: {'title': new} for no, idx, old, new in changed[rel]})
        # 只记一条批次说明：227 条逐条并进 fixes 会把该文件原有的修复史淹掉
        note = (f'《宋词三百首》篇目统一成「词牌·正文首句」：{len(changed[rel])} 首'
                + (f'（其中 {sum(1 for no, idx, o, n in changed[rel] if o)} 首覆盖了原来的小题）' if any(o for no, idx, o, n in changed[rel]) else '')
                + '。选本里只写词牌分不清是哪一首，同一首还有两个副本各写一种，故一律改。'
                  '只改 `title`，`rhythmic` 与正文一字未动；首句取本记录正文前 12 字、按该记录自己的简繁写法，'
                  '底本（识典古籍朱祖谋集解本）只用来核对是同一首。逐条映射见本脚本的 `PLAN` / `DUPLICATES`。')
        pg.merge(rel, dict(status='fixed', reviewer=args.reviewer, date=args.date, note=note))
    print(json.dumps(pg.write_index()['stats'], ensure_ascii=False))


if __name__ == '__main__':
    main()
