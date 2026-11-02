#!/usr/bin/env python3
"""`reference/二刻拍案惊奇.txt` → `清/小说/二刻拍案惊奇/erkipaianjingqi.json`。

《二刻拍案惊奇》四十卷（卷二十三〈大姊魂游完宿愿〉与《初刻拍案惊奇》重出，
卷四十〈宋公明闹元宵杂剧〉是杂剧，历来算作小说四十卷、实存三十八篇）。
旧的 `明/小说/三言二拍/erkipaianjingqi.json` 是从识典古籍按版本抓的，
四十卷只到手二十三卷（缺卷 7、13–27、29），且是繁体 OCR；2026-11 整份删掉，
改由本仓库的 `reference/` 文本整本重出，落 `清/小说/二刻拍案惊奇/`（issue #239）。

文件版式：

    书名：二刻拍案惊奇
    作者：凌濛初

    章节数：42
    字数：427259
    ========简介========
    ……
    ========正文========
    序
    ……
    小引
    ……
    卷一 进香客莽看金刚经 出狱僧巧完法会分
    诗曰：
    ……

  * 书头（书名行、著者行、章节数、字数、简介、`========正文========`）不进正文；
  * 卷目行顶格起，作「卷N 上句 下句」，上下句之间一个半角空格，`title` 里写作全角空格；
  * 卷前文字（《序》《小引》）无篇题，挂第一卷的 `prologue`，不另立条目；
  * 一段一行，空行不是段落。

底本自己的毛病，逐类处理，**正文一个字不改**（只改标点、符号与 `YUAN_PAIRS` 里那批「原/元」）：

  * **标点**：竖排点校本的括号一律是半角，成对改成全角（`(其一)`→`（其一）`、`(小生)`→`（小生）`）；
    半角逗号、分号、冒号、叹号、问号、句点按邻接位置改全角（`焚烧;`→`焚烧；`、`了.郎君`→`了。郎君`）；
    重复的点号（`！。` `，，`）删到该有的一个。
    卷四十剧本里四个字挤在一对半角括号里的科白（`(小生)`）先用占位符护住，改完放回。
  * **乱码截**：卷二十三有一行正文（「将庆娘与崔生合了婚。」之后）被一串不相干的字塞满
    （`?掁蛑遬梗醓奚銛麕絪炷锕叩模瑣且是熟分`），这一截整体删掉；
    卷二十七有一处 `向家????家丁`，四个问号是底本替换掉的缺字，写成 `{缺}`。
  * **缺字**：底本用 `〓`（97 行 131 处）与私用区码位（4 处）标自己的缺字，按全库口径
    （AGENTS.md 2b）一律叫 `□`，**字不补**。
  * **讹字（只此一类）**：底本把「元」印成「原」——年号（元祐、元丰、元和、改元、元朝）、
    节日（元宵、元夜、元夕、元日）、科名（三元、状元、贡元、解元、会元）、
    名物（元宝、元气、元命、元阳）、人名（董元广、邵文元、谢元卿、蔡元中、刘八郎名元、
    元自实、元稹、元载）、曲牌（〔朝元歌〕）、「宋、元兵戈」——按词换回「元」，共 24 条。
    「原来」「原籍」「原物」「原告」「原差」这些本来就用对了，占全书「原」字的绝大多数，不动。

    python3 scripts/import_erke_reference.py            # 写文件
    python3 scripts/import_erke_reference.py --check    # 只比对，不写
"""
import argparse
import hashlib
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = 'reference/二刻拍案惊奇.txt'
OUT = '清/小说/二刻拍案惊奇/erkipaianjingqi.json'
AUTHOR = '凌濛初'
DYNASTY = '清'
INTRO_MARK = '========简介========'
BODY_MARK = '========正文========'
UNIT = '卷'

CN = {c: i for i, c in enumerate('零一二三四五六七八九')}
CN['〇'] = 0
VOL_RX = re.compile(r'^卷([〇零一二三四五六七八九十百]+)[\s　]*(\S.*)$')

# 底本「原」「元」不分，把元日、元宵、三元、元气一类的「元」都录成了「原」。
# 同一个字在别处是用对的（原来、原籍、还原），所以不能按字换，只能按词换。
YUAN_PAIRS = (
    # 年号、节日、科名、地名
    ('宋、原兵', '宋、元兵'),                   # 卷 1「五代、宋、元兵戈扰乱」
    ('原时魏国', '元时魏国'),                   # 卷 2「若论画家，只有元时魏国公赵子昂」
    ('原宵', '元宵'), ('原夜', '元夜'), ('原夕', '元夕'), ('原日', '元日'),
    ('原旦', '元旦'), ('原正', '元正'),
    ('上原', '上元'), ('改原', '改元'), ('原年', '元年'), ('原朝', '元朝'),
    ('原顺帝', '元顺帝'), ('原政', '元政'), ('原将', '元将'), ('原帅', '元帅'),
    ('原人', '元人'), ('原世', '元世'),
    ('三原', '三元'), ('二原', '二元'), ('状原', '状元'), ('贡原', '贡元'),
    ('解原', '解元'), ('会原', '会元'),
    ('原气', '元气'), ('原命', '元命'), ('原阳', '元阳'), ('原精', '元精'),
    ('原宝', '元宝'), ('原恶', '元恶'),
    ('原载', '元载'), ('原稹', '元稹'), ('原微之', '元微之'), ('原衡', '元衡'),
    ('原祐', '元祐'), ('原丰', '元丰'), ('原符', '元符'), ('原城', '元城'),
    ('原和', '元和'), ('大原', '大元'), ('原贞', '元贞'),
    # 人名、曲牌：底本的「元」都印成了「原」，按词换
    ('名原，人叫他做刘原八郎', '名元，人叫他做刘八郎'),   # 卷 10 刘八郎名元
    ('刘原八郎', '刘八郎'),
    ('蔡原中', '蔡元中'),                # 卷 26 临安名师蔡元中
    ('邵文原', '邵文元'),                # 卷 33 莱州掖县邵文元
    ('董原广', '董元广'),                # 卷 7 汉州董元广
    ('谢原卿', '谢元卿'),                # 卷 12 谢元卿
    ('文原', '文元'),                    # 卷 33 邵文元又写作「文元」，底本仍作「原」
    ('原自实', '元自实'),                # 卷 24「山东有一人姓元名自实」
    ('朝原歌', '朝元歌'),                # 卷 40 曲牌〔朝元歌〕
)

# 底本用得对的「原」，换字前先护住。
# 人名「姓原名自实」不在护住之列：那是底本把「元自实」的「元」印成了「原」，
# 「原来」「原委委」「原先」「原物」这类本来就该是「原」，靠上下文换不到，不必护。
YES_YUAN = ('太原', '九原', '原原委委', '原白')
# 注：「原」本字（原来、原籍、原物、原告、原差……）在底本里用得对，占了绝大多数；
# 换的只是上头那张表里「本该是元」的词。

# 底本整截乱码：卷二十三「合了婚。」之后到「且是熟分；」之间那一串不相干的字
GARBLE_CUT = ('将庆娘与崔生合了婚。', '且是熟分；', '将庆娘与崔生合了婚。')

# 底本自己标缺的地方，逐处列出（都是底本用问号、半个括号或空段落顶着的）
LACUNA = (
    ('????', '{缺}'),              # 卷二十七「向家????家丁」：四个问号是替换掉的缺字
    ('共僚（音了)', '共僚{缺}'),    # 卷二词末注音只留了个「（音了)」，注文缺
)

# 括号：底本全是半角，成对改全角。卷四十剧本的科白一行只写半个括号，所以按整卷统一改
PAREN = (('(', '（'), (')', '）'))

# 半角标点改全角：底本是竖排点校本，句读该是全角的，半角都是录入残渣。
# 只有一处例外：卷四十剧本的科白 `(小生)` 那种，四个字挤在一对半角括号里，撇号按底本留着。
HALF_PUNCT = {',': '，', ';': '；', ':': '：', '!': '！', '?': '？'}
DUP_PUNCT = (('？？', '？'), ('！。', '！'), ('？。', '？'), ('。。', '。'),
             ('，，', '，'), ('；；', '；'), ('：：', '：'), ('”，。', '”。'))

# 底本标缺字用的符号：〓 与私用区码位
LACUNA_MARKS = ('〓', '\ue3ad', '\ue41d', '\ue433', '\ue434')
MISSING = '□'

HANZI = re.compile(r'[\u4e00-\u9fff]')


def cn2int(s):
    s = s.replace('〇', '零')
    if s.isdigit():
        return int(s)
    if '百' not in s and '十' not in s and len(s) > 1:   # 连写的数序
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


def hanzi_near(s, i, step):
    j = i + step
    return 0 <= j < len(s) and bool(HANZI.match(s[j]))


def fix_punct(line):
    """逗号、分号、冒号、叹号、问号、句点：挨着汉字是句读，改全角。

    括号里的撇号式科白 `(小生)` 先用占位符护住，改完放回。
    """
    saved = []

    def keep(m):
        saved.append(m.group())
        return chr(0xE200 + len(saved) - 1)

    line = re.sub(r'\([^()（）]{1,8}\)', keep, line)      # `(小生)` `(念介)` `(词寄《兰陵王》)`
    out = []
    for i, ch in enumerate(line):
        near = hanzi_near(line, i, -1) or hanzi_near(line, i, 1)
        if ch in HALF_PUNCT and near:
            out.append(HALF_PUNCT[ch])
        elif ch == '.' and hanzi_near(line, i, -1):
            out.append('。')
        else:
            out.append(ch)
    line = ''.join(out)
    while saved:
        line = line.replace(chr(0xE200 + len(saved) - 1), saved.pop())
    return line


def clean(line):
    for start, end, repl in (GARBLE_CUT,):
        i = line.find(start)
        if i >= 0:
            j = line.find(end, i + len(start))
            assert j > 0, f'乱码截没有结尾标记：{end!r}'
            line = line[:i] + repl + line[j + len(end):]
    for wrong, right in LACUNA:
        line = line.replace(wrong, right)
    line = fix_punct(line)
    for wrong, right in DUP_PUNCT:
        line = line.replace(wrong, right)
    # 「太原」「九原」「原原委委」底本用得对，先拿占位符护住，换完再放回
    for ch in YES_YUAN:
        line = line.replace(ch, chr(0xE100 + YES_YUAN.index(ch)))
    for wrong, right in YUAN_PAIRS:
        line = line.replace(wrong, right)
    for i, ch in enumerate(YES_YUAN):
        line = line.replace(chr(0xE100 + i), ch)
    for mark in LACUNA_MARKS:
        line = line.replace(mark, MISSING)
    return line


def parse():
    recs, cur, pre = [], None, []
    in_body = False
    for raw in open(os.path.join(ROOT, SRC), encoding='utf-8'):
        line = raw.strip('\n').replace('\u3000', ' ').strip()
        if not line:
            continue
        if line == INTRO_MARK:                       # 简介区：书名行、著者行、章节数都不进正文
            pre = None
            continue
        if line == BODY_MARK:
            in_body, pre = True, []
            continue
        if not in_body:
            continue
        m = VOL_RX.match(line)
        if m:
            head = re.sub(r'\s+', '\u3000', m.group(2).strip())
            cur = {'num': cn2int(m.group(1)), 'head': head, 'paragraphs': []}
            recs.append(cur)
            continue
        if cur is None:                              # 卷前：《序》《小引》
            if isinstance(pre, list):
                pre.append(clean(line))
            continue
        cur['paragraphs'].append(clean(line))
    # 卷三《西江月》后半「月与佳人共僚{缺}」之后只剩一个句号：前半句底本缺，留着这个句读
    assert isinstance(pre, list) and pre, '卷前《序》《小引》没找到'
    recs[0]['prologue'] = pair_parens(pre)
    for r in recs:
        r['paragraphs'] = pair_parens(r['paragraphs'])
    return recs


def pair_parens(paras):
    """整段（整卷）范围把半角括号换成全角，跨行的科白也能对上。"""
    text = '\n'.join(paras)
    for half, full in PAREN:
        text = text.replace(half, full)
    return text.split('\n')


def build(recs):
    taken, out = set(), []
    nums = [r['num'] for r in recs]
    if nums != list(range(1, len(nums) + 1)):
        raise SystemExit(f'卷次不连续：{nums}')
    for r in recs:
        title = f"第{r['num']}{UNIT}\u3000{r['head']}"
        rec = {'author': AUTHOR, 'title': title, 'dynasty': DYNASTY}
        if r.get('prologue'):
            rec['prologue'] = r['prologue']
        rec['paragraphs'] = r['paragraphs']
        rec['id'] = make_id(AUTHOR, title, rec['paragraphs'], taken)
        out.append(rec)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--check', action='store_true', help='只比对现有文件，不写')
    args = ap.parse_args()
    recs = build(parse())
    text = json.dumps(recs, ensure_ascii=False, indent=2) + '\n'
    dst = os.path.join(ROOT, OUT)
    chars = sum(len(p) for r in recs for p in r['paragraphs'])
    print(f'{len(recs)} 卷，{sum(len(r["paragraphs"]) for r in recs)} 段，{chars} 字'
          f'（序、小引 {len(recs[0]["prologue"])} 段挂在第一卷 prologue）')
    if args.check:
        old = open(dst, encoding='utf-8').read() if os.path.exists(dst) else ''
        print('一致' if old == text else '不一致')
        return 0 if old == text else 1
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    open(dst, 'w', encoding='utf-8').write(text)
    print('→', OUT)
    return 0


if __name__ == '__main__':
    sys.exit(main())
