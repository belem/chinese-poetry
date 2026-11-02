"""`reference/格林童话.txt`、`reference/安徒生童话.txt` → `汇编/` 下两部童话集的 JSON（issue #229）。

两部书都是汉译本，作者不是中国人，也没有一个朝代可挂，按 `汇编/` 的口径落位
（「跨代、又没有单一主时段的书放 `汇编/`」）。不放进 `明/小说/`、`清/小说/`：那两层挂的是
明清人的小说，童话既不是明清，也不是小说。

两部底本出自同一支电子本（同一套书头、同一套 `&ldquo;` 实体），版式如下：

    书名：格林童话
    作者：格林兄弟

    章节数：209
    字数：501936
    ========简介========
    ……
    ========正文========
    《格林童话》作者简介          ← 篇前的辅文，不是童话
    ……
    正文                          ← 格林童话辅文与童话之间的分隔行
    青蛙王子
    在遥远的古代，……（一段一行，长段落按定宽折行）

  * 书头（书名行、著者行、章节数、字数、简介、`========正文========`）不进正文；
  * 篇名行：**前面空过一行**，且这一行短（≤ `HEAD_MAX` 字）、顶格、不带句读。底本里的歌谣
    一行只有四五字（「小小的荨麻」），也短也不带句读，但它前面没有空行，靠空行就分得开；
  * 篇前的辅文（作者简介、内容简介、译者前言、译者简介、校对说明、目录梗概）挂在首篇的
    `prologue` 里，不另立条目（同《二刻拍案惊奇》把《序》《小引》挂第一卷的做法）；
    篇末的发表年、校对署名、译者评注不是童话正文，一概不收；
  * 安徒生底本另有卷题行（`卷1`…`卷4`），是选集的分卷，合并成一份正文后去掉，
    卷次记在各篇的 `volume` 里；
  * 一段一行，空行不是段落。底本按定宽折行，折行处接回（上一行不以句末标点收尾，或下一行
    以标点起头），接回后再按句末标点分句成段。

**底本的毛病**按下面口径修，规则都是机械的、宁可漏改不乱改：

  * 标点：底本用 HTML 实体写引号，`&ldquo;` → `“`、`&rdquo;` → `”`、`&lsquo;` → `‘`、
    `&rsquo;` → `’`、`&hellip;` → `……`、`&mdash;` → `——`（`&middot;` → `·`）；
    其余成对的半角括号改全角；紧挨汉字的半角 `,;:!?` 与 `.` 改全角；重复的点号
    （`！。` `，，` `。。`）删到该有的一个；
  * **「一」当专名号／着重号印了单字**。底本把「毛」印成「一毛一」、「抽屉」印成「一抽一屉」，
    连词中间的也照印（「他从后面的一个一抽一屉里爬进去」）。这是错字，不是异文：照录下来，
    娃读到「一毛一帚」只会当它是一把帚。只改 `DOTTED` 里点名的、逐处核过的成对写法 ——
    「一天一天」「一步一步」「一模一样」「一五一十」「一颗一颗」本来就这么写，不在表里，不动；
  * 底本用 `*` 作着重号，把词圈成 `色*彩`、`绿色*的`；「*」不是字，只是排版符号，
    一律删掉，字不动（`色*彩` → `色彩`）；
  * 其余残留：制表符、零宽字符、`<br>` 一类标签去掉；安徒生底本的篇末评注（发表年、
    译者注、校对署名）本来就在正文里，2026-11 / PR 见到的一批里已从 `reference/` 整段删掉，
    脚本不再处理；剩下的 ASCII 是正文里的年号、外文专名与《识字课本》一节的一字母，
    照录不动；
  * **格林童话底本 `reference/格林童话.txt` 里「弗雷德里克和凯瑟琳」整篇排了两遍**
    （3014—3072 行是前一篇的完整复制）。2026-11 已删掉重复的那一遍，两份正文逐字相同。

    python3 scripts/import_tonghua_reference.py            # 两本都写
    python3 scripts/import_tonghua_reference.py grimm      # 只写一本
    python3 scripts/import_tonghua_reference.py --report   # 打印每一处标点 / 折行处理
    python3 scripts/import_tonghua_reference.py --check    # 只比对，不写
"""
import argparse
import collections
import hashlib
import html
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BODY_MARK = '========正文========'
HEAD_MAX = 24                                 # 篇名行最长字数（安徒生底本最长篇名 20 字）
HEAD_SKIP = ('原文', '异文', '译自')            # 不是篇名的那类短行
# 电子本的校对署名与篇末评注的起头：从这里往后的整段都不收
EDITOR_NOTE = re.compile(r'[（(]aisitair|漪然校对|漪然录入')
# 校对署名自成一段时整段丢掉
DROP_LINE = ('（漪然录入）', '（漪然校对）', '漪然录入）', '漪然校对）')

# 引号、破折号、省略号：底本一律写成 HTML 实体
ENTITIES = (('&ldquo;', '“'), ('&rdquo;', '”'), ('&lsquo;', '‘'), ('&rsquo;', '’'),
            ('&hellip;', '……'), ('&mdash;', '——'), ('&middot;', '·'), ('&nbsp;', '　'))
HTML_TAG = re.compile(r'<\s*/?\s*(br|p|font|span|div)\s*/?\s*>', re.I)
ZERO_WIDTH = re.compile('[\u200b-\u200f\u2060\ufeff]')
# 句末标点：折行处上一行以这些收尾，说明是完整的句子，不必接回
SENT_END = '。！？…”’）】》」』…'
# 段首标点：下一行以这些起头，说明是上一句的尾巴被折下来，要接回。
# 「。！？」不算：定宽折行不会把句号折到下一行开头，句号在行首只会是下一句引文起头的笔误
LEAD_PUNCT = '，、；：”’）】》」』…'
# 「第一一夜」「第十一一夜」「第二十一一夜」「第三十一一夜」：底本在数词里多印了一个「一」。
NUM_NIGHT = re.compile(r'第(一|十一|二十一|三十一)一(?=夜)')

DUP_PUNCT = (('！。', '！'), ('？。', '？'), ('。，', '。'), ('，。', '，'),
             ('，，', '，'), ('。。', '。'), ('、、', '、'), ('；；', '；'))
HALF_PUNCT = re.compile(r'(?<=[\u4e00-\u9fff])[,;:!?]|[,;:!?](?=[\u4e00-\u9fff])')
HALF_PERIOD = re.compile(r'(?<=[\u4e00-\u9fff])\.(?=[\u4e00-\u9fff])')
ASCII_RES = re.compile(r'[A-Za-z0-9]+')
CYRILLIC_GREEK = re.compile(r'[Ѐ-ӿͰ-Ͽ]')
PUA = re.compile(r'[\ue000-\uf8ff]')

# 「一X一」型的叠字错印：底本把一个字印成「一字一」（专名号式的圈字）。
# 只收逐处核过的成对写法；表里没有的（一天一天、一模一样、唯一的一个、上一上一下一下）
# 本来就这么写，不动。左边是底本写法，右边是改正。
DOTTED = (
    '一毛一', '一抽一', '一团一', '一尸一', '一槍一', '一出一', '一舔一', '一模一',
    '一母一', '一摸一', '一宠一', '一捅一', '一揉一', '一搓一', '一党一', '一弟一',
    '一姐一', '一偶一', '一隐一', '一杆一', '一供一', '一洞一',
    # 底本还有几类：「硬一梆一梆」「白一里一透一红」「一屁一股」「花一瓣一」「吸一吮一」
    '一梆一', '一里一', '一屁一', '一瓣一', '一吮一', '一一一',
)

# ── 两本的差异都在这里 ──────────────────────────────────────────────────
BOOKS = {
    'grimm': dict(
        key='grimm',
        src='reference/格林童话.txt',
        out='汇编/格林童话/gelintonghua.json',
        title='格林童话', author='格林兄弟', dynasty='德国',
        book='格林童话',
        # 篇前的辅文标题，以及辅文与童话之间的分隔行「正文」
        front=re.compile(r'^(《格林童话》.+简介|正文)$'),
        preface_titles=('《格林童话》作者简介', '《格林童话》简介'),
        # 底本把「灰姑娘」写成「格林童话 灰姑娘」
        title_fix=(('格林童话 灰姑娘', '灰姑娘'), ('格林童话灰姑娘', '灰姑娘')),
        empty_ok=(),
        note=None,
    ),
    'andersen': dict(
        key='andersen',
        src='reference/安徒生童话.txt',
        out='汇编/安徒生童话/antushengtonghua.json',
        title='安徒生童话', author='安徒生', dynasty='丹麦',
        book='安徒生童话',
        front=re.compile(r'^(《安徒生童话》.+|安徒生作品目录|安徒生生平简介|校对说明)$'),
        preface_titles=('安徒生作品目录', '安徒生生平简介', '《安徒生童话》简介', '《安徒生童话》译者前言',
                        '《安徒生童话》译者简介', '校对说明'),
        title_fix=(),
        # 底本有篇无正文的，照立条目、`note` 里说明（目前没有）
        empty_ok=(),
        note='底本分四卷（卷1—卷4），本文件合并为一份正文，卷次见各篇 `volume`',
    ),
}

# 安徒生底本的卷题行（底本原作「第1卷」，与库内「卷N」的体例不合，已改作「卷1」）
VOLUME_RX = re.compile(r'^卷([1-9])$')


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


# 篇末的标记行：发表年「（１８４４年）」、译者署名「漪然录入）」「（aisitair扫描漪然校对）」、
# 电子本的「</p>」残片与版头「（叶君健」；用了它就不必再建一张书头行表
MARK_RX = re.compile(r'[）)]$|录入|校对|扫描|</|^[（(]')


def is_mark_line(s):
    """篇末标记行：整行都是「（１８４４年）」「漪然校对）」「（aisitair扫描 漪然校对）」这类。"""
    t = s.strip()
    return bool(MARK_RX.search(t)) and len(t) <= 30 and not re.search(r'[，。！？；：]', t)


def is_title(s):
    """篇名行：短、顶格、不带句读（`blank` 只管与上一篇之间的空行，另在两处判）。"""
    if not 2 <= len(s) <= HEAD_MAX:
        return False
    if re.search(r'[，。！？；：、“”‘’（）&<>]', s):
        return False
    if any(k in s for k in HEAD_SKIP):
        return False
    return bool(re.search(r'[\u4e00-\u9fff]', s))


def punct(line, report):
    """底本一行的符号规整：实体、半角标点、重复点号、制表符、残留标签。"""
    before = line
    line = line.replace('\t', '').strip()
    line = ZERO_WIDTH.sub('', line)
    line = HTML_TAG.sub('', line)
    for a, b in ENTITIES:
        line = line.replace(a, b)
    line = line.replace('　', ' ')                 # &nbsp; 兜底（实体表里已换成全角空格）
    line = re.sub(r'(?<=\d)[.．](?=\d)', '．', line)   # 小数点是真小数点，后面再统一
    line = HALF_PERIOD.sub('。', line)
    line = HALF_PUNCT.sub(lambda m: {',': '，', ';': '；', ':': '：', '!': '！', '?': '？'}[m.group()], line)
    line = line.replace('(', '（').replace(')', '）').replace('[', '［').replace(']', '］')
    for a, b in DUP_PUNCT:
        while a in line:
            line = line.replace(a, b)
    line = re.sub(r'(?<=[\u4e00-\u9fff])\s+(?=[\u4e00-\u9fff])', '', line)   # 词中间的空格是排版残留
    line = line.strip()
    if line != before and report is not None:
        report.append(('punct', before, line))
    return line


def fix_dotted(line):
    """底本两类「一」的衍文，「一X一」的圈字与连写的「一一」。

    * `一X一` → `X`：底本把单字圈成了专名号（「一毛一帚」），只改 DOTTED 里点名的整对写法；
    * `一一` → `一`：底本还在「过了一一夜」「揉一一揉」「一一夜」这类地方多印一个「一」。
      这一条是全书一律删一个，与上面那张表不同 —— 表里没有的成对写法（「一天一天」
      「一模一样」「一五一十」「一颗一颗」）本来就这么写，不能按「删一个」处理。
    """
    for pair in DOTTED:
        line = line.replace(pair, pair[1] if pair != '一一一' else '一')
    line = line.replace('一一', '一')
    # 「第一一夜」「第十一一夜」「第二十一一夜」「第三十一一夜」：数词里的「一」多印了一个
    return NUM_NIGHT.sub(r'第\1夜', line)


def split_sentences(text):
    """按句末标点断句，引号内的句末标点不断（对话成句）。"""
    out, buf, depth = [], '', 0
    for ch in text:
        buf += ch
        if ch in '“‘':
            depth += 1
        elif ch in '”’':
            depth = max(0, depth - 1)
        elif ch in '。！？…' and depth == 0:
            out.append(buf)
            buf = ''
    if buf:
        out.append(buf)
    return [s for s in out if s]


def reflow(lines):
    """底本按定宽折行：把被折开的句子接回，再按句末标点分句成段。"""
    joined = ''
    for ln in lines:
        if not joined:
            joined = ln
        elif joined[-1] in LEAD_PUNCT or joined[-1] not in SENT_END:
            joined += ln                       # 上一行没说完（或下一行以标点起头），接回
        else:
            joined += '\n' + ln                # 上一行是整句，另起段
    out = []
    for para in joined.split('\n'):
        out.extend(split_sentences(para))
    return out


def parse(book, report):
    """底本 → (篇前辅文的段落, [篇名 + 折行的正文])。

    认篇名只看两件事：这一行短、没有句读（`is_title`），并且**上一篇的正文末尾空过行**
    （`blank`）。底本里的歌谣一行只有四五个字，与篇名一样短，但它前面没有空行。
    不判「上一行是否说完」，也不看篇末的标记行 —— 这两条都与「空行」重复，多一层
    判断只多一种错法（真踩过一次：两条判据打架，正文被当成篇名，整篇收了两遍）。
    """
    raw = [ln.rstrip('\n') for ln in open(os.path.join(ROOT, book['src']), encoding='utf-8')]
    in_body = False
    recs, cur, vol = [], None, None
    blank = False
    for raw_line in raw:
        line = raw_line.strip()
        if not in_body:
            in_body = line == BODY_MARK
            continue
        if not line:
            blank = True
            continue
        # 卷题行（安徒生底本）
        m = VOLUME_RX.match(line)
        if m:
            vol = int(m.group(1))
            # 卷题行本身就是分篇的界线：它前面是空行，后面紧接下一篇，别再跟空行较劲
            blank = True
            continue
        if book['front'].match(line) or line in book['preface_titles']:
            # 篇前的辅文：起一个新块，块内文字进 prologue
            cur = {'head': line, 'paragraphs': [], 'front': True, 'volume': vol}
            recs.append(cur)
            blank = True                      # 「正文」这类分隔行之后紧接的就是首篇篇名
            continue
        here, blank = blank, False
        if here and is_title(line) and (cur is None or len(cur['paragraphs']) > 0 or cur['front']):
            head = line
            for a, b in book['title_fix']:
                head = head.replace(a, b)
            head = fix_dotted(head)            # 「第一一夜」→「第一夜」
            cur = {'head': head, 'paragraphs': [], 'front': False, 'volume': vol}
            recs.append(cur)
            continue
        if cur is None:
            raise SystemExit(f'{book["key"]}: 第一个篇名之前的文字没有归属：{line[:40]}')
        line = punct(line, report)
        # 篇末的译者评注：底本的评注都收在「（aisitair扫描漪然校对）」之前的那一段里，
        # 从这个署名起往后的都不是童话正文（有的还带着下一行未换行的篇名），整段丢掉
        if EDITOR_NOTE.search(line):
            continue
        if line in DROP_LINE:
            continue                            # 「（漪然录入）」这类单独成段的校对署名
        cur['paragraphs'].append(line)
    # 辅文按篇名归并：开头的辅文块（可能几块连排）合成 prologue，篇末的辅文丢弃
    prose, stories, seen_story = [], [], False
    for r in recs:
        if r['front']:
            if not seen_story and r['head'] not in ('正文',):
                prose.append(r)
            continue
        seen_story = True
        stories.append(r)
    prologue = []
    for r in prose:
        prologue.append(r['head'])
        prologue.extend(reflow(r['paragraphs']))
    return prologue, stories


def build(book, prologue, stories, taken, report):
    out = []
    for r in stories:
        paras = [fix_dotted(p) for p in reflow(r['paragraphs'])]
        title = r['head']
        if not paras and title not in book['empty_ok']:
            raise SystemExit(f'{book["key"]}: 篇目没有正文：{title}')
        rec = {'author': book['author'], 'title': title, 'dynasty': book['dynasty'],
               'paragraphs': paras}
        if r['volume']:
            rec['volume'] = r['volume']
        if not paras:
            rec['note'] = ('底本此处只有篇名与一条注记，正文缺；'
                           'reference/' + os.path.basename(book['src']) +
                           ' 该篇之后直接接下一篇，待另找译本补')
        rec['id'] = make_id(book['author'], title, paras, taken)
        out.append(rec)
    return prologue, out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('books', nargs='*', choices=[[], *BOOKS])
    ap.add_argument('--check', action='store_true', help='只比对，不写')
    ap.add_argument('--report', action='store_true', help='打印标点与折行处理明细')
    args = ap.parse_args()
    keys = args.books or list(BOOKS)
    rc, taken = 0, existing_ids()
    for key in keys:
        book = BOOKS[key]
        dst = os.path.join(ROOT, book['out'])
        if os.path.exists(dst):
            for r in json.load(open(dst, encoding='utf-8')):
                taken.discard(r.get('id'))
        report = [] if args.report else None
        prologue, stories = parse(book, report)
        prologue, data = build(book, prologue, stories, taken, report)
        dup = [t for t, n in collections.Counter(r['title'] for r in data).items() if n > 1]
        if dup:
            raise SystemExit(f'{key}: 篇名重复 {dup}（底本同题两篇，先人工核）')
        text = json.dumps(data, ensure_ascii=False, indent=2) + '\n'
        chars = sum(len(p) for r in data for p in r['paragraphs'])
        print(f'{book["out"]}: {len(data)} 篇，{sum(len(r["paragraphs"]) for r in data)} 段，{chars} 字'
              f'；篇前辅文 {len(prologue)} 段')
        warnings = [(r['title'], p) for r in data for p in r['paragraphs']
                    if ASCII_RES.search(p) or CYRILLIC_GREEK.search(p) or PUA.search(p)]
        if warnings:
            print(f'  仍有 ASCII / 西里尔希腊 / 私用区残留 {len(warnings)} 处')
            for t, p in warnings[:10]:
                print('   ', t, p[:40])
        if args.report:
            for kind, a, b in (report or [])[:60]:
                print(f'  [{kind}] {a[:40]} ‖ {b[:40]}')
        if args.check:
            old = open(dst, encoding='utf-8').read() if os.path.exists(dst) else ''
            print('  一致' if old == text else '  不一致')
            rc |= 0 if old == text else 1
            continue
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        open(dst, 'w', encoding='utf-8').write(text)
        print('  →', book['out'])
    return rc


if __name__ == '__main__':
    sys.exit(main())
