#!/usr/bin/env python3
"""`reference/隋唐演义1.txt`、`reference/隋唐演义2.txt` → `清/小说/隋唐演义/suitangyanyi.json`。

清褚人获《隋唐演义》一百回。2026-11 依 issue #244 由 repo 内这两份底本整本重出，
库内此前没有这部书（`scripts/import_novel_chapter.py` 里 `suitang` 那一项一直没落地，
见 `docs/隋唐演义重建.md`）。回目切分、发号沿用 `scripts/import_novel_chapter.py` 的通用件。

**底本的版式**（两份都是简体排印本，回目行顶格、前后各一个空行）：

    书名：隋唐演义
    作者：褚人获

    章节数：100
    字数：623210
    ========简介========
    ……
    ========正文========
    第01回 隋主起兵代陈 晋王树功夺嫡
    诗曰：
    繁华消歇似轻云，不朽还须建大勋。
    ……
    消息传入隋朝，隋主便起伐陈之意。高颎、杨素、贺若弼，都上平陈之策。

  * 一份起第 1 回、一份起第 50 回，按回次接起来，断言 1—100 连续；
  * 回目之间是散文、叙述、诗词，一段一行，**长段落按定宽（约 52 字）折行，一行不是一段**；
  * 卷首的诗、词、曲牌名（`诗曰：`／`词曰：`／`调寄“西江月”`）各自占一行，是篇首的韵文，
    不是叙事段；曲牌名一行不是诗的一联，单独作一段；
  * 书头（书名行、著者行、章节数、字数、简介、`========正文========`）不进正文。

**折行的合并**（这是本次整理最要紧的一条）：

  * 一行若以句末、冒号、收引号收尾（`。！？：；…”`），就是一段的末行；
  * 一行若没以这些收尾，只可能是折行：接回下一行。全篇 738 处，接完一段就是一段；
  * 韵文（诗、词）行行独立，不合并 —— 判据是下一行同样是短句（全书诗行 20 字以内），
    或本段处于韵文区段里（见 `poem_lines()`）。

**标点**（issue #244 的重点，规则都列在下面，可逐条核）：

  * `道，`＋引文 → `道：“`（底本 `道：“` 6896 处、`道，`＋引文 2 处，随大流）；
  * 后引号前错点的标点：`？，`→`？`、`！，`→`！`、`。”，`→`。”；
  * 叠标点（`，，` `。。` `？？` 之类）删到该有的一个；
  * 半角标点夹在汉字中间改全角；`**` 是着重号不是字，删掉、字不动；
  * 段内 `——` 只有一处，是「说道：——我们住在宫中」，删掉多出来的破折号；
  * `＼` 是顿号之讹：「姜亭亭＼袁紫烟」→「姜亭亭、袁紫烟」；
  * 底本的 `囗`（U+56D7）是缺字记号，按全库口径改作 `□`，**字不补**；
    底本自己还有「玉囗(马余)」这类「囗＋注音」的写法，注音留着（同《警世通言》体例）。

**底本自身的录入残渣**（拼音首字母顶替整字、码位顶替标点），逐处改，依据写在 `TYPO_FIXES`：

    老ZJ → 老张（卖柴人姓张，见下文「老张持扁挑过桥」）
    先DD这人 → 先打倒这人
    你n］各位 → 你各位            u → 逗号（「做什么用u才遇见」）
    yx → 游巡（游巡郊外／绕宫游巡／陛下游巡万里）
    DQ → 夺取（夺取财宝）          ZJ／ZG 一类同《儒林外史》卷
    *★ 两处（「自**县出兵」）等文字残渣照录不补 —— 认不出本字，留 `**`

    python3 scripts/import_suitang_reference.py            # 写文件
    python3 scripts/import_suitang_reference.py --check    # 只比对，不写
"""
import argparse
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from import_novel_chapter import cn2int, make_id   # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRCS = ['reference/隋唐演义1.txt', 'reference/隋唐演义2.txt']
OUT = '清/小说/隋唐演义/suitangyanyi.json'
AUTHOR = '褚人获'
DYNASTY = '清'
SEP = '\u3000'
INTRO_MARK = '========简介========'
BODY_MARK = '========正文========'
HEAD = re.compile(r'^第([〇零一二三四五六七八九十百0-9]+)回[\s　]*(\S.*)$')

# 一行是不是「段的末行」：以这些都收尾的，后面另起一段
RI = re.compile(r'[。！？：…”]$')
# 断在分号上的也是段末（「配位名雄四岳；」下一行接「是以立像清庙」），分号同样收段
SEG_END = re.compile(r'[。！？：；…”]$')
# 韵文落的引头：`诗曰：`／`词曰：`／`调寄“西江月”`，以及 `正是：`、`后人有诗叹云：`、
# `是绝句一首：` 这类引诗的话头。本书这类话头一律落在段末（冒号收尾），据此切韵文区段。
LEAD = re.compile(r'^(诗曰|词曰|曲曰|赞曰)[：:]$|^(调寄|上调|右调|左调|调安|调按)|'
                  r'^(正是|有诗为证|有诗四句|有诗八句|计开)[：:]$|'
                  r'^(后人有诗|又诗|诗云|词云|词|其[一二三四五]|绝句|律诗|口号|'
                  r'[^，。]{0,14}(诗|词|曲)[一至十二]{0,3}[首绝句律曲]?)[：:]$')
# 韵文的收尾：上一段以诗行收尾时，紧接着的整句短行仍是诗
VERSE_TAIL = re.compile(r'[，。！？]$')
# 韵文行：整句成一个短行。折行切出来的散文残行不是整句，不会被当成诗行
VERSE_FORM = re.compile(r'^[^\s，、]{2,20}[。！？；：…]$')
# 散文里常见的两字词：折行处出这种 2 字「句」，是折行而不是诗
STOP2 = set('了道是和也便却只又更就都还因此但却若故不知谁那里这个些这般如此于是乃'
            '曰其则所以然后已未有可不爲为被将把自与及并且如若使令教叫请欲要能得'
            '见听说想意见说当已一二人你我他')
# 底部词/曲的衬字句：不成句的短行
FILLER = ('去来', '者', '也么哥', '也波', '则个', '咱', '呵')

# 叠标点与错位的标点：先长的后短的
PUNCT_FIXES = (
    ('，，', '，'), ('。。', '。'), ('；；', '；'), ('：：', '：'), ('？？', '？'),
    ('！！', '！'), ('！。', '！'), ('？。', '？'), ('。，', '。'), ('，。', '。'),
    ('，；', '；'), ('；，', '，'), ('，：', '：'), ('：，', '：'),
    ('？，', '？'), ('！，', '！'), ('。”，', '。”'), ('？”，', '？”'), ('！”，', '！”'),
    ('、。', '。'), ('，、', '，'), ('。。”', '。”'),
)

# 底本字面录入残渣：拼音首字母、码位顶替整字、把标点点成了别的东西。逐处改，依据见 docstring
TYPO_FIXES = (
    ('老ZJ', '老张'),
    ('先DD这人', '先打倒这人'),
    ('你n］各位', '你各位'),
    ('做什么用u才遇见', '做什么用，才遇见'),
    ('yx郊外', '游巡郊外'),
    ('偶尔yx', '偶尔游巡'),
    ('绕宫yx', '绕宫游巡'),
    ('不须yx城市', '不须游巡城市'),
    ('陛下yx万里', '陛下游巡万里'),
    ('yx霄汉', '游巡霄汉'),
    ('DQ财宝', '夺取财宝'),
    ('DQ库中所藏之物', '夺库中所藏之物'),
    ('姜亭亭＼袁紫烟', '姜亭亭、袁紫烟'),
    ('道：——我们住在宫中', '道：“我们住在宫中'),   # 多一个破折号，引号一并补上
)
# 底本漏点、点错的地方，逐处补（只补标点，字不动；依据见 docs/隋唐演义重建.md）
LEAD_FIXES = (
    # 卷 43：述说官厅文书，引文里又套引路人转述的话，内层的 `‘` 漏了收引
    ('着地方官拿这个叛党。”故此小弟连夜赶来。”',
     '着地方官拿这个叛党。’故此小弟连夜赶来。’”'),
    # 卷 97：素姑转述罗公远的话，一段里两处引文叠加，只起了头没有收
    ('仙师罗公远曾云：日后有两个女人来此',
     '仙师罗公远曾云：‘日后有两个女人来此'),
    ('正有好处。”', '正有好处。’'),                 # 同上，内层引文的收引
    ('你道奇也不奇。”', '你道奇也不奇。’”'),
)
# 底本用半角括号给难字注音：`(山曾)`、`(土自)`、`(日东)`，改全角，字不动
BRACKET = re.compile(r'\(([^()]{1,4})\)')


def clean_novel(line):
    """底本行 → 段内文字。先改认得出的残渣，再规整标点，最后缺字记号改 □。"""
    for wrong, right in TYPO_FIXES:
        line = line.replace(wrong, right)
    for wrong, right in PUNCT_FIXES:
        line = line.replace(wrong, right)
    line = re.sub(r'(?<=[\u4e00-\u9fff]);(?=[\u4e00-\u9fff])', '；', line)
    line = re.sub(r'(?<=[\u4e00-\u9fff]),(?=[\u4e00-\u9fff])', '，', line)
    line = line.replace('**', '')                       # 着重号：符号不是字，字不动
    line = line.replace('囗', '□')                      # 底本的缺字记号，字不补
    line = line.replace('……', '…')                      # 底本此处作「被擒……」，收成六点一个
    line = line.replace('\u2018', '\u201c')                  # 引号点成了单引号，改回成对的“”（码位写成转义，
    line = line.replace('\u2019', '\u201d')                  # 免得看起来像别的引号）
    for wrong, right in LEAD_FIXES:
        line = line.replace(wrong, right)
    line = BRACKET.sub(lambda m: '（%s）' % m.group(1), line)
    return line


def is_verse_line(line):
    """这一行是不是一段独立的韵文（诗、词、曲）。"""
    if LEAD.match(line):
        return True
    if VERSE_FORM.match(line):
        body = line[:-1]
        if len(body) == 2 and body in STOP2:               # 「去了」「也是」这类折行残句
            return False
        if len(body) >= 14 and line[-1] == '，':           # 长句还在逗号上，是折行
            return False
        return True
    return len(line) <= 3                          # 词曲的衬字行（「者」「去来」）也是韵文



def balance_quotes(paras):
    """引号成对。底本的引号时有点错、时有一两个漏掉，按全库口径补（同 `docs/三言重建.md`）：

      * 一段里 `”` 比 `“` 多：底本把前引号点成了别的（`‘`、`”` 重复），在段首补一个 `“`；
      * 一段里 `“` 比 `”` 多：漏了后引号，在段末补一个 `”`。

    只在「差一处」、且不是引文的下半截（上一段自己也没收）时补，不硬凑整篇。
    """
    out = paras[:]
    for i, p in enumerate(out):
        opens, closes = p.count('“'), p.count('”')
        if opens == closes:
            continue
        if out[i - 1] and out[i - 1].count('“') > out[i - 1].count('”'):
            continue                                    # 上一段还没收引，本段是引文的下半截
        if closes - opens == 1:
            out[i] = '“' + p
        elif opens - closes == 1:
            out[i] = p + '”'
    return out


def fold_verse(paras):
    """把跨行没接上的韵文并成一行：`…急难岂忘` ＋ `亲？` → `…急难岂忘亲？`。"""
    out = []
    for p in paras:
        if out and not RI.search(out[-1]) and is_verse_line(p) and len(out[-1]) <= 30:
            out[-1] += p
        else:
            out.append(p)
    return out


def rejoin(lines):
    """折行接回自然段：一句以 RI 收尾就封段。韵文里「五字＋两字」的行也并回一行。"""
    out, buf = [], ''
    for line in lines:
        buf = (buf + line) if buf else line
        if SEG_END.search(buf):
            out.append(buf)
            buf = ''
    if buf:
        out.append(buf)
    merged = out[:1]
    for p in out[1:]:                              # 上一段以分号收尾、下一段仍是文言的，接成一段
        if merged[-1].endswith('；') and not is_verse_line(p):
            merged[-1] += p
        else:
            merged.append(p)
    return fold_verse(merged)


def split_verse(lines):
    """散文按自然段、韵文逐行成段。

    底本的诗、词、曲一行一联，散文按定宽折行，于是一章里长短行交错。分不清的整批接回自然段
    （宁可多并一段散文，不可把散文切成半句两句）：

      * 先按句末标点把折行接回自然段（`rejoin`）；
      * 引头（`诗曰：`／`正是：`／`后人有诗叹云：`…）自成一段，后面紧跟的诗行逐行成段；
      * 散文里以冒号收尾的引诗话头之后、整句成行的短行算一句诗；`道：` 之后不算（那是对白）；
      * 其余整句短行照旧并回自然段；`…急难岂忘` ＋ `亲？` 这类跨行没接上的，并成一行。
    """
    paras = rejoin(lines)
    out, i, n = [], 0, len(paras)
    while i < n:
        p = paras[i]
        if LEAD.match(p):
            out.append(p)
            i += 1
            while i < n and not LEAD.match(paras[i]) and is_verse_line(paras[i]):
                out.append(paras[i])
                i += 1
            continue
        if is_verse_line(p):
            cue = bool(out) and (out[-1].endswith(('：', ':')) and not out[-1].endswith('道：')
                                 or VERSE_TAIL.match(out[-1]))
            if cue:
                out.append(p)
            elif out:
                out[-1] += p                          # 判不准的，并回上一段散文
            else:
                out.append(p)
            i += 1
            continue
        out.append(p)
        i += 1
    return balance_quotes(fold_verse(out))


def ids_outside_target():
    """库里其余文件的 id（本文件自己不算，免得自己撞自己，同 `import_rulin_waishi.py`）。"""
    taken = set()
    for dirpath, dirs, files in os.walk(ROOT):
        dirs[:] = [d for d in dirs if d not in
                   {'.git', '.github', '.cnb', 'docs', 'reference', 'scripts', 'loader',
                    'authors', 'dynasties', 'rank', 'strains', 'images'}]
        for f in files:
            if not f.endswith('.json'):
                continue
            if os.path.relpath(os.path.join(dirpath, f), ROOT) == OUT:
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


def check(recs):
    """落文件前过一遍：每段都以句末标点收尾，缺字都写成 □，没有私用区与拉丁残渣。"""
    bad = []
    for r in recs:
        for p in r['paragraphs']:
            if not RI.search(p) and not p.endswith(('：', ':')):
                bad.append((r['num'], p[:20]))
            if re.search('[\ue000-\uf8ff]', p) or re.search('[A-Za-z]{2,}', p):
                bad.append((r['num'], p[:20]))
    if bad:
        raise SystemExit(f'待核：{bad[:5]}… 共 {len(bad)} 处')


def parse():
    recs, cur = [], None
    for src in SRCS:
        in_body = False
        for raw in open(os.path.join(ROOT, src), encoding='utf-8'):
            line = raw.strip('\n').replace('\u3000', ' ').strip()
            if not line:
                continue
            if line == INTRO_MARK:
                continue
            if line == BODY_MARK:
                in_body = True
                continue
            m = HEAD.match(line)
            if not in_body:
                if m:                                   # 第 2 份底本没有书头，直接从回目起
                    in_body = True
                else:
                    continue
            if m:
                cur = {'num': cn2int(m.group(1)),
                       'head': re.sub(r'\s+', SEP, m.group(2).strip()),
                       'lines': []}
                recs.append(cur)
                continue
            assert cur is not None, f'{src}: 回目之前有正文 {line[:20]}'
            cur['lines'].append(clean_novel(line))
    return recs


def build(recs, taken):
    nums = [r['num'] for r in recs]
    if nums != list(range(1, len(nums) + 1)):
        raise SystemExit(f'回次不连续：{nums[:8]}… 共 {len(recs)} 条')
    out = []
    for r in recs:
        paras = split_verse(r['lines'])
        assert paras, f'第{r["num"]}回 无正文'
        title = f"第{r['num']}回{SEP}{r['head']}"
        rec = {'author': AUTHOR, 'title': title, 'dynasty': DYNASTY, 'paragraphs': paras}
        rec['id'] = make_id(AUTHOR, title, paras, taken)
        out.append(rec)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--check', action='store_true', help='只比对现有文件，不写')
    args = ap.parse_args()
    recs = build(parse(), ids_outside_target())
    check(recs)
    text = json.dumps(recs, ensure_ascii=False, indent=2) + '\n'
    dst = os.path.join(ROOT, OUT)
    chars = sum(len(p) for r in recs for p in r['paragraphs'])
    print(f'{OUT}: {len(recs)} 回，{sum(len(r["paragraphs"]) for r in recs)} 段，{chars} 字')
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

