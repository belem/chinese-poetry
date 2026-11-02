"""`reference/伊索寓言.txt` → `汇编/伊索寓言/yisuoyuyan.json`（issue #229）。

伊索是古希腊人，书又没有一个单一主时段，按 `汇编/` 的口径落位（同《格林童话》
《安徒生童话》），不挂 `先秦/`、`明/小说/`。底本是一支电子本，版式如下：

    书名：伊索寓言
    作者：伊索

    章节数：453
    字数：197799
    ========简介========
    ……
    ========正文========
    伊索寓言：内容简介          ← 篇前辅文
    <p>《伊索寓言》（Aesop&rsquo;s Fables）……</p>   ← 一整段 HTML，`<br><br>` 分段
    伊索寓言作者简介
    ……
    原文+寓意                   ← 原文区的版头，不是篇名
    农夫与狼                    ← 篇名：顶格、短、不带句读
    农夫替牛解下犁套，……       ← 正文一段一行
    这故事是说，……             ← 寓意，也是正文的一段
    …
    合集                        ← 合集区的版头
    伊索寓言故事——第1章          ← 合集按章编，篇与篇之间用 80 个半角减号隔开
    狐狸和葡萄
    ……
    -------…

**篇名**认两件事：这一行短、顶格、不带句读，并且**前面空过行**（原文区）或
**紧接在分隔线之后**（合集区）。底本有几篇篇名被按字竖排成了「山 / 震」
「善 / 与 / 恶」，逐行一字，靠「上一行是篇名、这一行只有一个汉字、再下一行就是
正文」把这几行并回一个篇名。

**合集区与原文区有大量重出**：原文区 432 篇、合集区 424 个分隔段，两区对得上大半。按
「一件作品只留一份正文」，两区正文逐字相同的只留原文区那一份（删 412 条，866→454），
合不上的（异文、原文区漏收的）照收，明细记在 `docs/伊索寓言重建.md`。
`合集`、`伊索寓言故事——第N章` 两行是版头，不当篇名，章次记进 `volume`；
第 9、10 章底本另写作「伊索寓言故事和寓意——第9章」「伊索寓言全集 第十章」，一并归一。

**底本的毛病**按下面口径修，规则都是机械的、宁可漏改不乱改：

  * 标点：底本用 HTML 实体写引号，`&ldquo;` → “、`&rdquo;` → ”、`&lsquo;` → ‘、
    `&rsquo;` → ’、`&prime;` → ′、`&hellip;` → ……、`&mdash;` → ——；
    `《伊索寓言》内容简介` 那一段是整块 `<p>`，`<br><br>` 断段、`<br>` 断开，
    去掉标签后按句末标点分句；其余成对的半角括号改全角；紧挨汉字的半角 `,;:.` 改全角；
    重复的点号（`！。` `，，` `。。`）删到该有的一个；制表符、零宽字符、词中间的空格删掉；
  * **「一」当专名号刻在字里**：`一毛一`（毛）、`一团一`（团）、`寡一妇`（妇）、
    `自一由`（由）、`呻一吟`（吟），还刻在词中间（`他一摸一着`、`射一出一支箭`）。
    三张表分工：`DOTTED` 管 `一X一`、`DOTTED_WORDS` 管两字词中间那道、`DOTTED_TRIPLE`
    管连成一串的（`一舔一舔一` → 舔舔）；`DOTTED_EN` 是英文里被刻的（`ha一ve`）。
    `一心一意`、`一瘸一拐`、`一个一个`、`一模一样`、`第一一样`、`一人一时之作`
    本来就这么写，不在表里，不动；
  * **着重号 `*`**：底本把词圈成 `本性*`、`色*泽`、`性*命`，「*」不是字，一律删掉，字不动；
  * **英文与旧译**：`狼和小羊` 一篇按单词折行（一行一词）录了汤森本的英文正文，同一篇的
    旧译中文又从中间插进来，两种文字混排。按「这一行有没有汉字」分段，英文按空格接回、
    中文按底本顺序接回，两段都留、字一个不删 —— 那是底本自己的排法，不是错。
    英文的撇号 `'` 只在英文段里出现，不动（`&prime;` 照转 ′）；
  * **竖排的篇名**：底本有 45 处篇名被按字竖排（`山`/`震`、`善`/`与`/`恶`），逐行一字，
    按「前面是空行或分隔线、这几行都只有一个汉字、再下一行就是长正文」并回一个篇名；
  * **篇名里的版头**：`伊索寓言 驴和狼 原文+寓意` → `驴和狼`、`伊索寓言：狼和小羊` →
    `狼和小羊`；正文中间又排了一遍篇名（`狼和小羊` 一篇里那个小标题）去掉；
  * 底本末尾的篇章名与正文之间、篇末寓意之后常有一个只含制表符的行，不进正文；
  * 两处底本自身就是残段（`伊索寓言 马和驴 故事原文+寓意` 只有寓意、无正文；
    `伊索寓言 驴和狼 原文+寓意` 之后接了两条题解），照录，不补写。

    python3 scripts/import_yisuo_reference.py            # 写 JSON
    python3 scripts/import_yisuo_reference.py --report   # 打印每一处标点 / 折行 / 重出处理
    python3 scripts/import_yisuo_reference.py --check    # 只比对，不写
"""
import argparse
import collections
import hashlib
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = 'reference/伊索寓言.txt'
OUT = '汇编/伊索寓言/yisuoyuyan.json'
BODY_MARK = '========正文========'
SEP_RX = re.compile(r'^-{20,}$')
CHAPTER_RX = re.compile(
    r'^(?:合集|伊索寓言故事——第([0-9一二三四五六七八九十]+)章'
    r'|伊索寓言故事和寓意——第([0-9一二三四五六七八九十]+)章'
    r'|伊索寓言全集 第([0-9一二三四五六七八九十]+)章)$')
# 原文区的版头：不是篇名
PLATE = ('原文+寓意', '伊索寓言：内容简介', '伊索寓言作者简介', '合集')
# 篇前辅文：挂首篇的 prologue
FRONT = ('伊索寓言：内容简介', '伊索寓言作者简介')

ENTITIES = (('&ldquo;', '“'), ('&rdquo;', '”'), ('&lsquo;', '‘'), ('&rsquo;', '’'),
            ('&prime;', '′'), ('&hellip;', '……'), ('&mdash;', '——'), ('&middot;', '·'))
HTML_BR = re.compile(r'<\s*br\s*/?\s*>', re.I)
HTML_TAG = re.compile(r'<\s*/?\s*(p|font|span|div)\s*/?\s*>', re.I)
ZERO_WIDTH = re.compile('[\u200b-\u200f\u2060\ufeff]')
CYRILLIC_GREEK = re.compile(r'[Ѐ-ӿͰ-Ͽ]')
KANA = re.compile(r'[\u3040-\u30ff\u3100-\u312f]')
ASCII_RES = re.compile(r'[A-Za-z]{2,}')
CJK_RUN = re.compile(r'[\u4e00-\u9fff]')
PUA = re.compile(r'[\ue000-\uf8ff]')

SENT_END = '。！？…”’）】》」』…'
LEAD_PUNCT = '，。！？、；：”’）】》」』…'
DUP_PUNCT = (('！。', '！'), ('？。', '？'), ('。，', '。'), ('，。', '，'),
             ('，，', '，'), ('。。', '。'), ('、、', '、'), ('；；', '；'))
HALF_PUNCT = {',': '，', ';': '；', ':': '：', '!': '！', '?': '？'}

# 「一X一」型的圈字：底本把一个字刻成「一字一」。只收逐处核过的；
# 一心一意、一瘸一拐、一个一个、一人一时之作、第一一样、第一个是本来的写法，不在表里。
DOTTED = ('毛', '团', '槍', '舔', '宠', '抽', '出', '摸', '吮', '探', '挺', '叫',
          '具', '滔', '吟', '着', '到', '住', '开', '立', '挂', '夹', '想', '独',
          '喝', '尝', '做', '个', '走', '动', '摇', '闪', '擦', '顶', '挣', '滚',
          '把', '玩', '拔', '洗', '放', '飞', '踢', '钉', '砍', '拍', '推', '挑')
# 中间刻了一道的两字词：寡一妇、自一由、呻一吟……只消掉中间那个「一」
DOTTED_WORDS = ('寡一妇', '自一由', '呻一吟', '胀一破', '摸一着', '摸一到', '夹一住',
                '吹一箫', '露一出来', '漏流一出来', '拉一出来', '掉一出来')
# 三连：底本把两个字各圈了一道，连成一串（一舔一舔一 = 舔舔）。显式列出改法
DOTTED_TRIPLE = {'一舔一舔一': '舔舔', '舔一舔一': '舔舔'}
# 英文里也被刻了一道：ha一ve（英文不按字段处理，逐词点名）
DOTTED_EN = {'ha一ve': 'have', 'won一t': 'won\'t', 'wo一uld': 'would' }

# 兜底：上一段是引导语、本段整段只有收尾引号，说明折行处丢了开引号，补上
# （依据同 scripts/import_sanyan_reference.py）
QUOTE_HEAD = re.compile(r'(说|道|问|答|喊|叫|讲|嘱咐|吩咐)：$')


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


def punct(line, report=None):
    """一行的符号规整：实体、半角标点、重复点号、制表符、残留标签。"""
    before = line
    line = line.replace('\t', '').strip()
    line = ZERO_WIDTH.sub('', line)
    line = HTML_BR.sub('', line)
    line = HTML_TAG.sub('', line)
    for a, b in ENTITIES:
        line = line.replace(a, b)
    line = re.sub(r'(?<=[\u4e00-\u9fff])[.](?=[\u4e00-\u9fff])', '。', line)
    line = re.sub(r'(?<=[\u4e00-\u9fff])[,;:!?]|[,;:!?](?=[\u4e00-\u9fff])',
                  lambda m: HALF_PUNCT[m.group()], line)
    line = line.replace('(', '（').replace(')', '）').replace('[', '［').replace(']', '］')
    for a, b in DUP_PUNCT:
        while a in line:
            line = line.replace(a, b)
    line = re.sub(r'(?<=[\u4e00-\u9fff])\s+(?=[\u4e00-\u9fff])', '', line)
    line = line.strip()
    if line != before and report is not None:
        report.append(('punct', before, line))
    return line


def fix_dotted(text, report=None):
    """「一」当专名号刻在字两边：一毛一→毛，寡一妇→寡妇，摸一到→摸到。

    三连的先改（一舔一舔一 → 舔舔），再改两连的，最后改词中间的。
    """
    before = text
    for triple, fix in DOTTED_TRIPLE.items():
        text = text.replace(triple, fix)
    for word, fix in DOTTED_EN.items():
        text = text.replace(word, fix)
    for word in DOTTED_WORDS:
        core = word.replace('一', '')
        if len(core) == 2:
            text = text.replace(word, core)
    for ch in DOTTED:
        text = text.replace(f'一{ch}一', ch)
    if text != before and report is not None:
        report.append(('dotted', before, text))
    return text


def strip_stars(text, report=None):
    """底本用 `*` 作着重号，圈在字两边或单侧；`*` 不是字，删掉。"""
    if '*' in text:
        if report is not None:
            report.append(('star', text, text.replace('*', '')))
        text = text.replace('*', '')
    return text


def split_sentences(text):
    """按句末标点断句，引号内的句末标点不断。"""
    out, buf, depth = [], '', 0
    for ch in text:
        buf += ch
        if ch in '“「『':
            depth += 1
        elif ch in '”」』':
            depth = max(0, depth - 1)
        elif ch in '。！？…' and depth == 0:
            out.append(buf)
            buf = ''
    if buf.strip():
        out.append(buf)
    return [s.strip() for s in out if s.strip()]


def join_wrapped(lines):
    """把底本折开的句子接回、段落分开。

    底本一个段落有两种排法：一行一段的（寓意、短篇正文）一行就是一句，以句末标点
    收尾；定宽折行的头几行齐刷刷 40 字、末行才是短尾巴。折行块里行行都以「。」断句，
    所以只能看行长：上一行顶到 35 字以上就是被截断的，接回；不到 35 字就是一段的终点。
    英文按词折行的（一行只一两个词、整行不含汉字）另算，见下。
    """
    # 这一篇是英文、中文交错排的（底本把同一篇的汤森本英文与旧译中文你一段我一段地
    # 混在一起）：英文按空格接回，中文按底本顺序接回，各归各的，字一个不删。
    en = [ln for ln in lines if not CJK_RUN.search(ln)]
    if lines and len(en) * 2 >= len(lines):
        segs, cur, cur_en = [], [], None
        for ln in lines:
            is_en = not CJK_RUN.search(ln)
            if cur_en is None or is_en == cur_en:
                cur.append(ln)
            else:
                segs.append((cur_en, cur))
                cur = [ln]
            cur_en = is_en
        segs.append((cur_en, cur))
        out = []
        for is_en, group in segs:
            if is_en:
                text = ' '.join(x.strip() for x in group)
                text = re.sub(r'\s+([,.;:!?])', r'\1', re.sub(r'\s+', ' ', text)).strip()
                out.append(text)
            else:
                out.append(''.join(group))
        return '\n'.join(out)
    # 折行的判据见 docstring：上一行顶到 35 字以上就是被截断的，接回；否则另起一段。
    joined = ''
    for i, ln in enumerate(lines):
        if not joined:
            joined = ln
            continue
        # 上一行以收尾引号结束、这一行又短，是引文说完、另起一句，不算折行
        quoted_end = lines[i - 1][-1] in '”’' and len(ln) < 35
        if len(lines[i - 1]) >= 35 and not quoted_end:
            joined += ln                            # 接回
        else:
            joined += '\n' + ln                     # 上一行就是完整的一段
    return joined


# 篇名里夹带的版头：「伊索寓言：狼和小羊」「伊索寓言 驴和狼 原文+寓意」
TITLE_PREFIX = re.compile(r'^伊索寓言[：:\s]*')
TITLE_SUFFIX = re.compile(r'[\s]*(?:故事)?原文\+寓意[\s]*$')


def clean_title(s):
    t = TITLE_PREFIX.sub('', s.strip())
    t = TITLE_SUFFIX.sub('', t)
    return t.strip() or s.strip()


def is_title(s):
    """篇名行：短、顶格、不带句读。"""
    t = s.strip()
    if not 2 <= len(t) <= 24:
        return False
    if re.search(r'[，。！？；：、“”‘’（）&<>《》]', t):
        return False
    return bool(CJK_RUN.search(t))


def parse(report):
    """底本 → (篇前辅文的段落, [篇名 + 段落 + 章次])。

    原文区（`========正文========` 到「合集」）按空行切块，块首行是篇名；
    合集区按 80 个半角减号切段，段首行是篇名，`伊索寓言故事——第N章` 记章次。
    篇名被按字竖排的（「山 / 震」）逐行一字，靠「上一行是篇名、再下一行是正文」并回。
    """
    raw = open(os.path.join(ROOT, SRC), encoding='utf-8').read().split('\n')
    try:
        start = raw.index(BODY_MARK) + 1
    except ValueError:
        raise SystemExit(f'{SRC}: 找不到 {BODY_MARK}')
    body = [(i + 1, ln) for i, ln in enumerate(raw) if i >= start]

    # ── 切成原始的「块」：原文区按空行，合集区按分隔线 ──────────────────
    region, segs, cur = 'pre', [], []
    vol = None
    for n, ln in body:
        s = ln.strip()
        if SEP_RX.match(s):
            if cur:
                segs.append((region, vol, cur))
                cur = []
            continue

        if not s:
            # 空行断段：原文区靠它分篇，合集区里竖排篇名与正文之间也靠它
            if cur:
                segs.append((region, vol, cur))
                cur = []
            continue
        m = CHAPTER_RX.match(s)
        if m:
            g = next((x for x in m.groups() if x), None)
            vol = _cn2int(g) if g else None
            if region == 'pre':
                # 原文区到此结束，合集区开始：这一行是版头，不是篇名
                if cur:
                    segs.append((region, None, cur))
                cur = []
                region = 'comp'
                continue
            # 合集区里章节版头与下一篇篇名连排：把已经攒下的这一段切出去
            if cur:
                segs.append((region, vol, cur))
                cur = []
            continue
        cur.append((n, s))
    if cur:
        segs.append((region, vol, cur))

    # ── 竖排的篇名先并回：上一段整段只有一个汉字、本段也是 ──────────────
    merged = []
    for item in segs:
        region_, vol_, lines_ = item
        texts = [t for _, t in lines_]
        all_single = all(len(t) == 1 and CJK_RUN.match(t) for t in texts)
        if merged and all_single:
            prev = merged[-1]
            prev_texts = [t for _, t in prev[2]]
            if all(len(t) == 1 and CJK_RUN.match(t) for t in prev_texts):
                merged[-1] = (prev[0], prev[1], prev[2] + lines_)
                continue
        merged.append(item)
    segs = merged

    # ── 逐段解析篇名与正文 ───────────────────────────────────────────
    prologue, stories, pending = [], [], []
    for region_, vol, seg in segs:
        lines = [text for _, text in seg]
        if region_ == 'pre' and lines[0] in PLATE:
            # 版头行：辅文的起头，或原文区的「原文+寓意」分隔
            head = lines.pop(0)
            if head in FRONT:
                pending.append((head, lines))
                continue
            if not lines:
                continue
        if not lines:
            continue
        head, rest = lines[0], lines[1:]
        # 篇名逐行一字：底本把「山震」「善与恶」按字竖排，一行一个字。
        # 条件是这一行只有一个汉字、后面紧跟的几行也是一个汉字，而再下一行是长正文。
        while rest and len(rest[0]) == 1 and CJK_RUN.match(rest[0]) and len(head) <= 8:
            if len(rest) > 1 and len(rest[1]) > 20:
                head += rest.pop(0)
            elif len(rest) > 2 and len(rest[1]) == 1 and len(rest[2]) > 20:
                head += rest.pop(0)
            else:
                break
        stories.append({'head': clean_title(head), 'lines': rest,
                        'volume': vol, 'region': region_})

    for head, lines in pending:
        prologue.append(head)
        cleaned = [punct(x, report) for x in lines]
        # 内容简介那一段是整块 <p>，`<br><br>` 已在 punct 里删掉，这里按残留的分段标记断开
        paras = [seg for seg in '\n'.join(cleaned).split('\n') if seg.strip()]
        for seg in paras:
            prologue.extend(split_sentences(join_wrapped([seg])))
    return prologue, stories


def _cn2int(s):
    digits = '一二三四五六七八九十'
    if s.isdigit():
        return int(s)
    if s == '十':
        return 10
    if s.startswith('十'):
        return 10 + digits.index(s[1]) + 1
    if '十' in s:
        a, b = s.split('十')
        return (digits.index(a) + 1) * 10 + (digits.index(b) + 1 if b else 0)
    return digits.index(s) + 1


def build(prologue, stories, taken, report):
    out = []
    if prologue and stories:
        stories[0]['prologue'] = prologue
    for st in stories:
        text = [fix_dotted(strip_stars(punct(ln, report), report)) for ln in st['lines']]

        chunks = [x for x in join_wrapped(text).split('\n') if x.strip()]
        # 正文中间又排了一遍篇名（底本自带的重复小标题），不是正文，去掉
        bare = st['head'].split('：')[-1]        # 「伊索寓言：狼和小羊」→「狼和小羊」
        chunks = [x for x in chunks if x.strip() not in (st['head'], bare)]
        for prefix in (st['head'], bare):
            chunks = [x[len(prefix):] if x.startswith(prefix) and len(x) > len(prefix)
                      and x[len(prefix)] not in '，。！？”' else x for x in chunks]
        paras = []
        for chunk in chunks:
            paras.extend(split_sentences(chunk))
        # 上一段是引导语、本段整段是引文而漏了开引号 → 补前引号
        for i, p in enumerate(paras):
            if p.endswith('”') and p.count('”') == 1 and '“' not in p \
                    and i and QUOTE_HEAD.search(paras[i - 1]):
                if report is not None:
                    report.append(('quote', p, '“' + p))
                paras[i] = '“' + p
        rec = {'author': '伊索', 'title': st['head'], 'dynasty': '古希腊',
               'paragraphs': paras}
        if st.get('prologue'):
            rec['prologue'] = st['prologue']
        if st['volume']:
            rec['volume'] = st['volume']
        rec['id'] = make_id('伊索', st['head'], paras, taken)
        out.append(rec)
    return out


def dedupe(records, report):
    """一件作品只留一份正文：合集区与原文区逐字相重的，删合集区那一份。

    逐字相同才删 —— 差一个字就是异文，两存（同 docs/重复清理.md 的判据）。
    """
    seen, kept = {}, []
    for r in records:
        key = '\x1f'.join(r['paragraphs'])
        if key and key in seen:
            if report is not None:
                report.append(('dup', f'{r["title"]}（合集第{r.get("volume")}章）',
                               f'与原文区 {seen[key]["title"]} 正文逐字相同，删'))
            continue
        seen[key] = r
        kept.append(r)
    return kept


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--check', action='store_true', help='只比对，不写')
    ap.add_argument('--report', action='store_true', help='打印标点 / 折行 / 重出处理明细')
    args = ap.parse_args()
    report = [] if args.report else None
    taken = existing_ids()
    dst = os.path.join(ROOT, OUT)
    if os.path.exists(dst):
        for r in json.load(open(dst, encoding='utf-8')):
            taken.discard(r.get('id'))
    prologue, stories = parse(report)
    data = build(prologue, stories, taken, report)
    raw = len(data)
    data = dedupe(data, report)
    # 篇名重复的（底本同题两篇）先报警，由人工核
    dup = [t for t, n in collections.Counter(r['title'] for r in data).items() if n > 1]
    text = json.dumps(data, ensure_ascii=False, indent=2) + '\n'
    chars = sum(len(p) for r in data for p in r['paragraphs'])
    print(f'{OUT}: {len(data)} 篇（合并前 {raw}），'
          f'{sum(len(r["paragraphs"]) for r in data)} 段，{chars} 字；'
          f'篇前辅文 {len(prologue)} 段')
    if dup:
        print('  篇名重复（底本同题两篇，未合并）：', dup)
    warn = [(r['title'], p) for r in data for p in r['paragraphs']
            if CYRILLIC_GREEK.search(p) or KANA.search(p) or PUA.search(p)]
    if warn:
        print(f'  仍有西里尔希腊 / 假名 / 私用区残留 {len(warn)} 处')
        for t, p in warn[:10]:
            print('   ', t, p[:40])
    eng = [(r['title'], p) for r in data for p in r['paragraphs'] if ASCII_RES.search(p)]
    if eng:
        print(f'  含英文的段落 {len(eng)} 处（底本原录的英文，不删）')
    if args.report:
        for kind, a, b in (report or [])[:80]:
            print(f'  [{kind}] {a[:44]} ‖ {b[:44]}')
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
