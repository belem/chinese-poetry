#!/usr/bin/env python3
"""`reference/` 里的章回小说 → `明/小说/`、`清/小说/` 下的 JSON（回目切分通用件）。

与 `scripts/import_novel_reference.py`（东周列国志、封神演义、水浒传、红楼梦）同一口径，
这里收的是另一批：儒林外史、镜花缘、隋唐演义、喻世明言、警世通言、醒世恒言。
六部书的底本都是简体、逐段带句读的排印本，版式如下。

带书头（回目行顶格、前后各一个空行）：

    《儒林外史》清  吴敬梓

    章节数：56
    字数：326585
    ========简介========
    ……
    ========正文========
    第一回 说楔子敷陈大义 借名流隐括全文
    “人生南北多歧路，将相神仙，也要凡人做。……

  * 书头（著者行、章节数、字数、简介、`========正文========`）不入正文；
  * 回目行回次有汉字、有阿拉伯数字（镜花缘作「第01回」），两种都认；
  * 回目上下句之间是一个半角空格，`title` 里统一写成全角空格，与库内其余章回小说一致；
  * 隋唐演义分两个文件（1 起第01回、2 起第50回），按回次接起来，断言 1—100 连续。

三言二拍（喻世明言、警世通言、醒世恒言）：

    《喻世明言》明  冯梦龙

    章节数：30
    字数：253841
    ========简介========
    ……
    ========正文========
    第一卷 蒋兴哥重会珍珠衫
    “仕至千钟非贵，年过七十常稀……

  * 分「卷」不分「回」，`title` 作「第N卷　篇名」；
  * 底本卷次用汉字（`第一卷`），照底本的卷数走，不补不缺；
  * 醒世恒言卷首有一篇《叙》（天启丁卯陇西可一居士题），无篇题，
    挂在第一卷第一条的 `prologue`，不另立条目；卷名之前的一切（书名行、章节数、
    简介、`========正文========`）都不进正文。

共用的规则：

  * 一段一行，空行不是段落；
  * `author` 取书头著者，`dynasty` 按作者朝代（三言二拍与儒林外史归明、镜花缘与隋唐演义归清）；
  * **标点按底本修正**：连续标点（`，，` `。。` `。，`）删到该有的一个，
    引号外夹着的逗号（`”，` 后紧跟句读）以底本读法为准，逐条列在 `FIXES` 里；
  * `id` 规则同 `scripts/shidian/convert.py`（author|title|正文 blake2b），改正文才变。

    python3 scripts/import_novel_chapter.py               # 全部六本都写
    python3 scripts/import_novel_chapter.py rulin         # 只写一本
    python3 scripts/import_novel_chapter.py --check       # 只比对，不写
"""
import argparse
import hashlib
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

CN = {c: i for i, c in enumerate('零一二三四五六七八九')}
CN['〇'] = 0
BODY_MARK = '========正文========'
INTRO_MARK = '========简介========'
END_MARK = '〔全文完〕'


def cn2int(s):
    s = s.replace('〇', '零')
    if s.isdigit():
        return int(s)
    if '百' not in s and '十' not in s and len(s) > 1:   # 第一一四回 这种连写的数序
        return int(''.join(str(CN[c]) for c in s if c in CN))
    if '百' in s:
        hi, lo = s.split('百')
        lo = lo.lstrip('零')
        return (CN[hi] if hi else 1) * 100 + (cn2int(lo) if lo else 0)
    if '十' not in s:
        return CN[s]
    hi, lo = s.split('十')
    return (CN[hi] if hi else 1) * 10 + (CN[lo] if lo else 0)


def existing_ids():
    """库里现有的全部 id（全库唯一，与 scripts/backfill_ids.py 的口径一致）。"""
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


# 底本点放多了的地方：只删多出来的那一下，字不动
PUNCT_FIXES = (
    ('，，', '，'), ('。。', '。'), ('；；', '；'), ('：：', '：'),
    ('，。', '。'), ('。，', '。'), ('，；', '；'), ('，：', '：'),
    ('！。', '！'), ('？。', '？'), ('”，。', '”。'), ('”，，', '”，'),
)

# 底本用两个制表符 ─ 当破折号（「几时。──只是母亲在家」），改回中文破折号
DASH_FIX = re.compile('─{2,}')

# 半角标点夹在汉字中间：改成全角（底本自身的半角录入残渣，如「琴瑟谐协;有过则改之;」）
HALF_PUNCT = ((';', '；'), (',', '，'), ('!', '！'), (':', '：'), ('?', '？'))

# 底本的私用区码位是缺字（OCR 没认出来），按全库口径（AGENTS.md 2b）加 {}，**字自己不补**。
# 每个码位在底本里只代表一个字，逐个列出来，不按范围自动套 {}。
PUA_CHARS = {
    'rulin': (),
    'jinghua': ('\ue012', '\ue02a', '\ue0dd', '\ue0de', '\ue0e6', '\ue1d8', '\ue2c3', '\ue31c'),
    'suitang': (),
    'yushi': ('\ue00d', '\ue345', '\ue41d', '\ue433', '\ue482', '\ue4c0', '\ue4c1', '\ue4c2', '\ue4c3'),
    'jingshi': ('\ue433', '\ue434', '\ue43d', '\ue467', '\ue47d', '\ue482', '\ue48a', '\ue4a3',
                '\ue4a6', '\ue4b6', '\ue4b7', '\ue4b9', '\ue4bd', '\ue4be'),
    'xingshi': ('\ue434', '\ue43d', '\ue467', '\ue47d', '\ue48a', '\ue4a3', '\ue4a6', '\ue4ae',
                '\ue4b6', '\ue4b9', '\ue4bc', '\ue4bd', '\ue4c0', '\ue4c5'),
}

# 底本里认得出的错字（不是异文：底本本身录错，通行本可证），逐处改，字面依据写在这里。
# 判据见 docs/通俗小说重建.md；认不出的不改，留作缺字或原文。
TYPO_FIXES = {
    'rulin': (
        ('你不要管p快换了衣服P我同你去', '你不要管，快换了衣服，我同你去'),   # 拼音残渣 p/P，读作逗号
        ('买嘱枪手dk几案', '买嘱枪手代倩几案'),                             # dk 是「代倩」的拼音残渣
        ('写字与他哥p说', '写字与他哥，说'),                                # 同上，p → 逗号
        ('一个抱着毡包0一直来到河下', '一个抱着毡包，一直来到河下'),         # 0 → 逗号
        ('ZJ随即着家人送了五两银子', '随即着家人送了五两银子'),              # ZJ 是重出的「郑」姓残渣
        ('邀小弟在他幕ZG事', '邀小弟在他幕中事'),                           # ZG → 中
        ('一个嘴巴把聘娘DD在地', '一个嘴巴把聘娘打倒在地'),                  # DD → 打倒
    ),
    'jinghua': (
        ('那就是XX子之福了', '那就是姐姐之福了'),                            # XX → 姐姐（承上文「如姐姐所言」）
        ('就适悄\ue02a得位啊', '就适悄说得位啊'),                          # 缺字按文意补「说」
        # 第26回翼民国一段：底本把「爱戴高帽，自受圈套」一路排成乱码（夹私用区缺字与半角假名），
        # 以「叫」起、以「！（今殿本作『。」，此处从底本的句读）���尾，整截换掉
    ),
    'suitang': (
        ('老ZJ', '老张'),                                                  # 卖柴人姓张
        ('先DD这人', '先打倒这人'),                                        # DD → 打倒
        ('你n］各位，请用过了', '你各位，请用过了'),                        # n］是「们」的录入残渣，删去
        ('不知他在这里做什么用u才遇见', '不知他在这里做什么用，才遇见'),      # u → 逗号
        ('yx郊外', '游巡郊外'),                                            # yx = 游巡
        ('偶尔yx，失于回避', '偶尔游巡，失于回避'),
        ('绕宫yx', '绕宫游巡'),
        ('不须yx城市', '不须游巡城市'),
        ('陛下yx万里', '陛下游巡万里'),
        ('yx霄汉', '游巡霄汉'),
        ('DQ财宝', '夺取财宝'),                                            # DQ = 夺取
        ('DQ库中所藏之物', '夺库中所藏之物'),
    ),
    'yushi': (),
    'jingshi': (),
    'xingshi': (),
}


# 底本里成片乱码的截断：`(起始文本, 结束文本, 换成什么)`，从起始文本到结束文本一并换掉
GARBLE_CUTS = {
    'jinghua': (
        ('叫作‘爱戴高帽', '！', '叫作‘爱戴高帽，自受圈套’，也就是专替别人戴高帽、自己却受了圈套的意思。'),
    ),
}


def clean(line, key):
    """底本行 → 正文段：先改认得出的错字，再规整标点，最后把缺字码位包成 {…}。"""
    for wrong, right in TYPO_FIXES.get(key, ()):
        line = line.replace(wrong, right)
    for start, end, right in GARBLE_CUTS.get(key, ()):
        i = line.find(start)
        if i < 0:
            continue
        j = line.find(end, i)
        assert j > 0, f'{key}: 乱码截没有结尾标记 {end!r}'
        line = line[:i] + right + line[j + len(end):]
    for wrong, right in PUNCT_FIXES:
        line = line.replace(wrong, right)
    line = DASH_FIX.sub('——', line)
    for half, full in HALF_PUNCT:
        line = re.sub(r'(?<=[\u4e00-\u9fff])' + re.escape(half) + r'(?=[\u4e00-\u9fff])', full, line)
    for ch in PUA_CHARS.get(key, ()):
        line = line.replace(ch, '{%s}' % ch)
    return line

BOOKS = {
    'rulin': dict(
        key='rulin',
        src=['reference/儒林外史.txt'],
        out='清/小说/儒林外史/rulinwaishi.json',
        author='吴敬梓', dynasty='清', unit='回',
        head=re.compile(r'^第([〇零一二三四五六七八九十百0-9]+)回[\s　]*(\S.*)$'),
    ),
    'jinghua': dict(
        key='jinghua',
        src=['reference/镜花缘.txt'],
        out='清/小说/镜花缘/jinghuayuan.json',
        author='李汝珍', dynasty='清', unit='回',
        head=re.compile(r'^第([〇零一二三四五六七八九十百0-9]+)回[\s　]*(\S.*)$'),
    ),
    'suitang': dict(
        key='suitang',
        src=['reference/隋唐演义1.txt', 'reference/隋唐演义2.txt'],
        out='清/小说/隋唐演义/suitangyanyi.json',
        author='褚人获', dynasty='清', unit='回',
        head=re.compile(r'^第([〇零一二三四五六七八九十百0-9]+)回[\s　]*(\S.*)$'),
    ),
    'yushi': dict(
        key='yushi',
        src=['reference/喻世明言.txt'],
        out='明/小说/三言二拍/yushimingyan.json',
        author='冯梦龙', dynasty='明', unit='卷',
        head=re.compile(r'^第([〇零一二三四五六七八九十百0-9]+)卷[\s　]*(\S.*)$'),
    ),
    'jingshi': dict(
        key='jingshi',
        src=['reference/警世通言.txt'],
        out='明/小说/三言二拍/jingshitongyan.json',
        author='冯梦龙', dynasty='明', unit='卷',
        head=re.compile(r'^第([〇零一二三四五六七八九十百0-9]+)卷[\s　]*(\S.*)$'),
    ),
    'xingshi': dict(
        key='xingshi',
        src=['reference/醒世恒言.txt'],
        out='明/小说/三言二拍/xingshihengyan.json',
        author='冯梦龙', dynasty='明', unit='卷',
        head=re.compile(r'^第([〇零一二三四五六七八九十百0-9]+)卷[\s　]*(\S.*)$'),
        # 卷前无序、或有《叙》而无篇题的，挂到第一卷的 prologue
        prefaces=True,
    ),
}


# 底本正文里缺的卷：只有行款、没有正文，正文留给后人补。
#   喻世明言：第二十九卷〈月明和尚度翠柳〉缺，第三十卷起底本把篇题印成了连排的目录，
#   正文只剩第四十卷一段。这一带照录成只有篇题的记录，不臆造正文。
GAP_NOTE = {
    'yushi': {n: '底本缺正文：这一带底本把卷题印成了连排的目录，正文只剩第四十卷一段'
                 '（通行本此卷有正文，待补）' for n in range(29, 40)},
}


def thin_toc(recs):
    """连排的目录（篇题挨着篇题、没有正文）照录为只有篇题的记录，不拼进上一卷。"""
    out = []
    for i, r in enumerate(recs):
        if not r['paragraphs'] and i + 1 < len(recs):
            nxt = recs[i + 1]['num']
            if nxt - r['num'] != 1:
                raise SystemExit(f'次第跳号：第{r["num"]}卷 → 第{nxt}卷')
        out.append(r)
    return out


def parse(book):
    """按回（卷）切分。

    书头（书名行、章节数、字数、`========简介========` 及紧随的简介段）不进正文；
    后一个 `========正文========` 之后、首个回目之前的文字算卷前文字
    （醒世恒言的卷首《叙》），挂到第一卷的 `prologue`。
    """
    recs, cur = [], None
    for src in book['src']:
        in_body = False
        pre = []                  # 卷前文字：正文标记之后、首个回目之前
        for raw in open(os.path.join(ROOT, src), encoding='utf-8'):
            line = raw.strip('\n').replace('\u3000', ' ').strip()
            if not line:
                continue
            if line == INTRO_MARK:      # 简介区：书名行、章节数、字数、简介段都不进正文
                pre = None
                continue
            if line == BODY_MARK:
                in_body, pre = True, []
                continue
            if line == END_MARK:
                continue
            m = book['head'].match(line)
            if not in_body:
                if m:                   # 没有书头的底本（隋唐演义2）直接从回目行起
                    in_body = True
                else:
                    if isinstance(pre, list):
                        pre.append(line)
                    continue
            if m:
                head = re.sub(r'\s+', '\u3000', m.group(2).strip())
                cur = {'num': cn2int(m.group(1)), 'head': head, 'paragraphs': []}
                recs.append(cur)
                continue
            if not recs:                # 首个回目之前：卷前文字
                if isinstance(pre, list):
                    pre.append(line)
                continue
            if book.get('prefaces') and len(recs) == 1 and 'prologue' not in recs[0]:
                recs[0]['prologue'] = pre
                pre = None
            cur['paragraphs'].append(clean(line, book['key']))
    if pre and not book.get('prefaces'):
        raise SystemExit(f'{book["key"]}: 卷前有未归属的文字：{pre[:1]}')
    return thin_toc(recs)


def build(book, recs, taken):
    out = []
    nums = [r['num'] for r in recs]
    if nums != list(range(1, len(nums) + 1)):
        raise SystemExit(f'{book["key"]}: 次第不连续 {nums[:8]}… 共 {len(nums)} 条')
    gap = GAP_NOTE.get(book['key'], {})
    for r in recs:
        title = f"第{r['num']}{book['unit']}\u3000{r['head']}"
        if not r['paragraphs'] and r['num'] not in gap:
            raise SystemExit(f'{book["key"]}: 第{r["num"]}{book["unit"]} 无正文（{title}）')
        rec = {'author': book['author'], 'title': title, 'dynasty': book['dynasty']}
        if r.get('prologue'):
            rec['prologue'] = r['prologue']
        rec['paragraphs'] = r['paragraphs']
        if r['num'] in gap:
            rec['note'] = gap[r['num']]
        rec['id'] = make_id(book['author'], title, rec['paragraphs'], taken)
        out.append(rec)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('books', nargs='*', choices=[[], *BOOKS], default=[])
    ap.add_argument('--check', action='store_true', help='只比对现有文件，不写')
    args = ap.parse_args()
    rc = 0
    taken = existing_ids()
    outs = {os.path.join(ROOT, b['out']) for b in BOOKS.values()}
    if not args.check:            # 本批要重写的文件，旧 id 让出来，免得自己撞自己
        for dst in outs:
            if os.path.exists(dst):
                for r in json.load(open(dst, encoding='utf-8')):
                    taken.discard(r.get('id'))
    for key in (args.books or list(BOOKS)):
        book = BOOKS[key]
        recs = build(book, parse(book), taken)
        text = json.dumps(recs, ensure_ascii=False, indent=2) + '\n'
        dst = os.path.join(ROOT, book['out'])
        chars = sum(len(p) for r in recs for p in r['paragraphs'])
        empty = sum(1 for r in recs if not r['paragraphs'])
        print(f'{book["out"]}: {len(recs)} {book["unit"]}，'
              f'{sum(len(r["paragraphs"]) for r in recs)} 段，{chars} 字'
              + (f'，缺正文 {empty} 卷' if empty else ''))
        if args.check:
            old = open(dst, encoding='utf-8').read() if os.path.exists(dst) else ''
            same = old == text
            print('  一致' if same else '  不一致')
            rc |= 0 if same else 1
            continue
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        open(dst, 'w', encoding='utf-8').write(text)
        print('  →', book['out'])
    return rc


if __name__ == '__main__':
    sys.exit(main())
