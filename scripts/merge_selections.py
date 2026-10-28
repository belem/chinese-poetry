#!/usr/bin/env python3
"""把零碎的选本目录并回它所属的总集，去掉目录层级的重复。

  python3 scripts/merge_selections.py            # 预演：打印每条匹配报告
  python3 scripts/merge_selections.py --apply    # 写回数据，并生成 docs/选本并入.tsv

四件事：

  唐/唐诗三百首/ 55 首 → 全唐诗/poet.tang.* 的 tags，目录删除（2026-10）。这是上游
                 poems-tangshi.js 的 65 首，与 全唐诗/唐诗三百首.json 那份 366 首、
                 汇编/蒙学/tangshisanbaishou.json 那份 320 首都不是同一份选本
  水墨唐诗/     余 4 首 → 并入 poet.tang 并带 prologue；总集未收的 3 首按全唐诗的记载补录，
                 目录删掉（四条已全部落在 poet.tang 上）
  宋词三百首/   280 首全部对上 ci.song.*，加 tags 后目录删除（2026-10）
  近现/     按作者朝代拆：唐宋元明清的课本选目并回对应总集，真近现代的留下

判定同一首沿用 merge_anthologies 的口径，再加两条：选本带序（题名有「並序」）时
去掉第一段再比；选本题名是节选时按总集全本记。作者不同的一律两存。
"""
import argparse
import collections
import difflib
import glob
import json
import os
import re
import shutil
import uuid

from opencc import OpenCC

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
cc = OpenCC('t2s')

# 选本题名会带这些注记，比对题名时要剥掉；乐府类目前缀也不进题名比对
TITLE_NOISE = re.compile(r'[・·（(].*$')
TITLE_PREFIX = re.compile(r'^(?:雜曲歌辭|相和歌辭|樂府|鼓吹曲辭|橫吹曲辭|清商曲辭|琴曲歌辭|郊廟歌辭|近代曲辭|新樂府辭|舞曲歌辭|雜歌謠辭)')
# 选本第一段短于全篇四分之一，视为序（如「賊退示官吏・並序」），去序后再比
PREFACE_MAX = 0.2

# 作者朝代 → 依次尝试并进哪几部书（索引里没有朝代的作者不动）
DYN_PLAN = {
    '先秦': ['历代', '课外经典', '四书五经'],
    '周': ['历代', '课外经典', '四书五经'],
    '汉': ['历代', '昭明文选', '古诗源'],
    '三国': ['历代', '昭明文选'],
    '晋': ['历代', '昭明文选', '古诗源'],
    '南北朝': ['历代', '昭明文选'],
    '隋': ['历代', '古诗源'],
    '唐': ['全唐诗'],
    '五代十国': ['全唐诗'],
    '宋': ['全宋诗', '全宋词'],
    '元': ['全唐诗', '历代'],
    '明': ['历代', '课外经典', '昭明文选', '古文观止'],
    '清': ['历代', '纳兰性德', '课外经典'],
}


# 总集未收、但全唐诗确有记载的几条：按总集的记载补录，选本只贡献 pos/子目/prologue。
# 收录依据只认总集本身的书名/题名/传世名句，不采信选本的改写。
INSERT_AUTHOR = {
    '贺知章': '賀知章',   # poet.tang 用繁体作者名
}
# 不是唐人的补录条目落到他所属朝代的诗集：与全唐诗共用一套 Corpus，写回时各归各的文件
INTO = {
    '曹植': '三国/诗/poet.sanguo.json',
}
INSERTED = [
    # 唐/唐诗三百首/（上游 poems-tangshi.js 的 65 首，2026-10 并入）
    {
        'author': '王昌齡', 'title': '長信秋詞五首 三', 'pos': '三',
        'paragraphs': ['奉帚平明金殿開，且將團扇暫裴回。', '玉顏不及寒鴉色，猶帶昭陽日影來。'],
        'note': '全唐诗王昌龄卷收有《長信秋詞五首》，其三即「奉帚平明金殿開」一首。不取总集里已出的两条'
                '（《相和歌辭 長信怨 二》作「暫將團扇共裴回」，poet.tang.58000 那条无「暫」字、不成句）',
    },
    {
        'author': '曹植', 'title': '白馬篇', 'pos': '樂府',
        'paragraphs': ['白馬飾金羈，連翩西北馳。', '借問誰家子，幽并遊俠兒。', '少小去鄉邑，揚聲沙漠垂。',
                       '宿昔秉良弓，楛矢何參差。', '控弦破左的，右發摧月支。', '仰手接飛猱，俯身散馬蹄。',
                       '狡捷過猴猿，勇剽若豹螭。', '邊城多警急，虜騎數遷移。', '羽檄從北來，厲馬登高堤。',
                       '長驅蹈匈奴，左顧陵鮮卑。', '棄身鋒刃端，性命安可懷。', '父母且不顧，何言子與妻。',
                       '名編壯士籍，不得中顧私。', '捐軀赴國難，視死忽如歸。'],
        'note': '全唐诗只收李白《白馬篇》，曹植此篇在《文選》樂府，故补录进《三国/诗/poet.sanguo.json》'
                '（那里已有一条，正文缺一逗且作「不得中顾私」，此处按《文選》李善本补）',
    },
    # 水墨唐诗（2026-10 并入）
    {
        'author': '杜甫', 'title': '绝句三首', 'pos': '二首 二',
        'paragraphs': ['二十一人同入蜀，惟殘一人出駱谷。', '自說二女嚙臂時，迴頭却向秦雲哭。'],
        'note': '全唐诗杜甫卷收有「二十一人同入蜀」一首（《三絕句 二》之外别为一绝）',
    },
    {
        'author': '賀知章', 'title': '曉發', 'pos': '一',
        'paragraphs': ['故鄉杳無際，江臯聞曙鐘。', '始見沙上鳥，猶埋雲外峰。'],
        'note': '全唐诗贺知章卷收《曉發》',
    },
    {
        'author': '杜牧', 'title': '清明',
        'paragraphs': ['清明時節雨紛紛，路上行人欲斷魂。', '借問酒家何處有，牧童遥指杏花村。'],
        'note': '全唐诗杜牧卷收《清明》，即「牧童遥指杏花村」一首',
    },
]


def insert_target(corpus, author, p):
    """补录到哪个文件：作者所在文件；作者未被收录时按文件里的编号顺序插到相邻位置。"""
    want = author_key(author)
    for f, i, q in corpus.recs:
        if author_key(q.get('author')) == want:
            return f, None
    return corpus.files[-1], None


# 异体字：繁简转换处理不了，比对时一并抹平（写回仍用数据集自己的字形）
VARIANTS = str.maketrans('臯皐睾槩槪歎嘆爲為牀床', '皋皋皋概概叹叹为为床床')


def norm(s):
    return re.sub(r'[^\u4e00-\u9fff\U00020000-\U0002ffff]', '', cc.convert(s or '')).translate(VARIANTS)


def author_key(a):
    a = re.sub(r'\s*[一二三四五六七八九十]+首$', '', cc.convert((a or '').strip()))
    return a.split('/')[0]


def title_key(t):
    return TITLE_PREFIX.sub('', cc.convert(TITLE_NOISE.sub('', t or '')).strip())[:4]


def body(p):
    return norm(''.join(p.get('paragraphs') or []))


def sents(p):
    parts = re.split(r'[，。？！；、,.?!;：:]', ''.join(p.get('paragraphs') or []))
    return [s for s in map(norm, parts) if len(s) >= 4]


def body_without_preface(p):
    """第一段短得不像正文时视为序，去掉后再比。"""
    ls = p.get('paragraphs') or []
    if len(ls) > 1:
        head, rest = norm(ls[0]), norm(''.join(ls[1:]))
        if head and rest and len(head) < PREFACE_MAX * (len(head) + len(rest)):
            return rest
    return norm(''.join(ls))


def is_truncated(p):
    t = p.get('title') or ''
    return '节选' in t or '節選' in t


def load(rel):
    with open(os.path.join(ROOT, rel), encoding='utf-8') as fp:
        data = json.load(fp)
    return data if isinstance(data, list) else [data]


def _scan_array(raw):
    """顶层数组每条记录的 (起, 止) 位置。"""
    open_at = raw.index('[') + 1
    close_at = raw.rindex(']')
    spans, depth, in_str, esc, start, i = [], 0, False, False, None, open_at
    while i < close_at:
        ch = raw[i]
        if in_str:
            if esc:
                esc = False
            elif ch == '\\':
                esc = True
            elif ch == '"':
                in_str = False
            i += 1
            continue
        if ch == '"':
            in_str = True
        elif ch in '{[':
            if depth == 0:
                start = i
            depth += 1
        elif ch in '}]':
            if ch == '}' and depth == 1:
                spans.append((start, i + 1))
                start = None
            depth -= 1
        i += 1
    return open_at, close_at, spans


def _reserialize(rec, text):
    """按原文这条记录的排版重新序列化。

    只替换真正改过的记录：原文每层的缩进宽度、每行的行尾空格都从原文量出来照抄，
    否则改一条会让整份文件（乃至二十万行）都显示为改动。
    """
    lines = text.split('\n')
    if len(lines) <= 2:                      # 单行紧凑格式（元曲）
        return json.dumps(rec, ensure_ascii=False, separators=(',', ':'))
    widths, closing, trail = [], None, set()
    for line in lines:
        s = line.strip()
        if not s:
            continue
        pad = len(line) - len(line.lstrip(' '))
        if s == '}':
            closing = pad
        elif pad not in widths:
            widths.append(pad)
        if line != line.rstrip(' '):
            trail.add(s)
    out = ['{']
    for line in json.dumps(rec, ensure_ascii=False, indent=2).split('\n')[1:]:
        s = line.strip()
        if s == '}':
            out.append(' ' * (closing or 0) + s)
            continue
        depth = (len(line) - len(line.lstrip(' '))) // 2
        out.append(' ' * widths[min(depth, len(widths) - 1)] + s + (' ' if s in trail else ''))
    return '\n'.join(out)


def save(rel, data):
    """只改被并动的记录，其余字节原样保留；末尾新增的记录按最后一条的排版补进去。"""
    path = os.path.join(ROOT, rel)
    with open(path, encoding='utf-8') as fp:
        raw = fp.read()
    old = load(rel)
    flat = data if isinstance(data, list) else [data]
    open_at, close_at, spans = _scan_array(raw)
    out, cur, changed = [raw[:open_at]], open_at, False
    for i, (a, b) in enumerate(spans):
        out.append(raw[cur:a])
        if i < len(flat) and (i >= len(old) or old[i] is not flat[i]):
            out.append(_reserialize(flat[i], raw[a:b]))
            changed = True
        else:
            out.append(raw[a:b])
        cur = b
    out.append(raw[cur:])
    text = ''.join(out)
    extra = flat[len(spans):]
    if extra:
        # 新记录接在数组末尾：照最后一条的排版缩进一级，分隔符与右括号也照抄
        block = raw[spans[-1][0]:spans[-1][1]] if spans else raw[open_at:close_at]
        head = raw[:spans[-1][1]] if spans else raw[:open_at]
        closer = raw[spans[-1][1]:] if spans else raw[close_at:]
        sep = ',\n' + ' ' * _closing(block)
        added = ',\n' + ' ' * _closing(block) + sep.join(_reserialize(r, block) for r in extra)
        text = head + added + '\n' + closer.lstrip(' \n')
        changed = True
    json.loads(text)
    if changed:
        with open(path, 'w', encoding='utf-8') as fp:
            fp.write(text)


def _closing(block):
    """一条记录的缩进宽度：取最后一行「}」前面的空格数。"""
    lines = block.split('\n')
    if len(lines) <= 2:
        return 0
    for line in reversed(lines):
        if line.strip() == '}':
            return len(line) - len(line.lstrip(' '))
    return 0


class Corpus:
    """一部总集的正文索引。"""

    def __init__(self, files):
        self.files = files
        self.data = {f: load(f) for f in files}
        self.recs = [(f, i, p) for f in files for i, p in enumerate(self.data[f])]
        self.index = collections.defaultdict(set)
        for k, (_, _, p) in enumerate(self.recs):
            for s in sents(p):
                self.index[s].add(k)

    def add(self, f, p):
        self.recs.append((f, len(self.data[f]), p))
        self.data[f].append(p)

    def match(self, p):
        """最可能的对应记录 (k, ratio, same_author, how)，没有则 None。"""
        ss = set(sents(p))
        hits = collections.Counter(k for s in ss for k in self.index.get(s, ()))
        b, a = body_without_preface(p), author_key(p.get('author'))
        best = None
        for k, n in hits.most_common(20):
            q = self.recs[k][2]
            c = body(q)
            ratio = difflib.SequenceMatcher(None, b, c, autojunk=False).ratio()
            same = author_key(q.get('author')) == a
            same_title = title_key(q.get('title')) == title_key(p.get('title'))
            if is_truncated(p) and same and len(b) >= 0.5 * len(c) and ratio >= 0.4:
                how = 'excerpt'        # 选本只是总集的一部分
            elif ratio >= 0.8:
                how = 'ratio'
            elif same and n == len(ss) >= 2 and ratio >= 0.6:
                how = 'sentences'
            elif same and same_title and ratio >= 0.5:
                how = 'title'          # 选本带序、或异文过半，但同作者同题
            else:
                how = None
            if not how:
                continue
            if best is None or (same, ratio) > (best[2], best[1]):
                best = (k, ratio, same, how)
        return best


def insert_into(corpus, p, tag, log, note=''):
    """总集未收、但全唐诗另有记载的条目：按总集记载补录一条，选本只贡献 pos/子目/prologue。"""
    for f, i, r in corpus.recs:                    # 已经补录过就不再补，重跑幂等
        if author_key(r.get('author')) == author_key(p.get('author')) and body(r) == body(p):
            r['tags'] = list(dict.fromkeys((r.get('tags') or []) + [tag]))
            if p.get('prologue'):
                r['prologue'] = p['prologue']
            log.append([p.get('_src', tag), desc(p), f'{f}#{i}', desc(r), '1.00', f'已在 {tag}', note])
            return r
    f, _ = insert_target(corpus, p.get('author'), p)
    rec = dict(p)                            # p 里的正文已经是总集记载
    rec.pop('_src', None)
    rec.pop('note', None)
    rec.setdefault('id', str(uuid.uuid4()))
    rec['tags'] = [tag] + [t for t in (p.get('tags') or []) if t != tag]
    corpus.add(f, rec)
    log.append([p.get('_src', '水墨唐诗'), desc(rec), f'{f}#{len(corpus.data[f]) - 1}', desc(rec),
                '新增', f'创编 {tag}', note])
    return rec


def _attach_or_insert(corpus, q, tag, log):
    """同一首在此前已按总集记载补录过时，挂 tag 补 prologue，不再新增一条。"""
    same = [k for k, (_, _, r) in enumerate(corpus.recs)
            if author_key(r.get('author')) == author_key(q.get('author'))
            and body(r) == body(q)]
    if same:
        f, i, r = corpus.recs[same[0]]
        r['tags'] = list(dict.fromkeys((r.get('tags') or []) + [tag]))
        if q.get('prologue'):
            r['prologue'] = q['prologue']
        log.append([q['_src'], desc(q), f'{f}#{i}', desc(r), '1.00', f'并入 tags 重复补录', ''])
        return r
    return insert_into(corpus, q, tag, log)


def merge_one(rel, corpus, tag, log):
    """把选本每一条并进 corpus 的 tags；对不上但总集另有记载的按总集补录。"""
    keep = []
    for p in load(rel):
        m = corpus.match(p)
        if m:
            f, i, q = corpus.recs[m[0]]
            q['tags'] = list(dict.fromkeys((q.get('tags') or []) + [tag]))
            if p.get('prologue'):
                q['prologue'] = p['prologue']
            note = '' if m[2] else f'选本署名 {p.get("author")}'
            log.append([rel, desc(p), f'{f}#{i}', desc(q), f'{m[1]:.2f}', f'并入 tags {m[3]}', note])
            continue
        p['_src'] = rel
        if p.get('author') in INSERT_AUTHOR:
            _attach_or_insert(corpus, dict(p, author=INSERT_AUTHOR[p['author']]), tag, log)
            continue
        p.pop('_src', None)
        keep.append(p)
        log.append([rel, desc(p), '', '', '', '保留', '总集未收'])
    return keep


def desc(p):
    return f'{p.get("author")}《{p.get("title")}》'


# 唐/唐诗三百首/ 的底本是分卷选本：同一题下几首被抄成一条（長干曲四首、塞下曲四首），
# 而目次 anthologies/tangshi300.json 是逐首记的。并的时候按组铺到目次的连续编号上，
# 一条对上 n 首就连占 n 个号，组内对不上的号由后续条目补上。
TANG300_GROUP = {
    '長干曲四首': '長干曲', '塞下曲四首': '塞下曲', '詠懷古蹟': '詠懷古蹟',
    '遣悲懷': '遣悲懷', '回鄉偶書': '回鄉偶書', '贈別': '贈別', '揚州三首': '揚州',
}


def is_tagged(rec, tag):
    return tag in (rec.get('tags') or [])


def insert_record(corpus, spec, tag, log, tsv_src, into=None):
    """按给定正文补录一条（正文与总集记载相同，不采信选本的改写）。

    into 指定落到哪一部书：不是唐人的（曹植《白馬篇》）落到他自己的诗集里。
    """
    for f, i, r in corpus.recs:                     # 已补录过就不再补，重跑幂等
        if author_key(r.get('author')) == author_key(spec.get('author')) and body(r) == norm(''.join(spec['paragraphs'])):
            r['tags'] = list(dict.fromkeys((r.get('tags') or []) + [tag]))
            log.append([tsv_src, desc(spec), f'{f}#{i}', desc(r), '1.00', f'已在 {tag}', ''])
            return r
    f, _ = into or insert_target(corpus, spec.get('author'), spec)
    rec = {'author': spec['author'], 'title': spec['title'], 'paragraphs': list(spec['paragraphs']),
           'pos': spec.get('pos', ''), 'tags': [tag], 'id': str(uuid.uuid4())}
    if not rec['pos']:
        rec.pop('pos')
    corpus.add(f, rec)
    log.append([tsv_src, desc(spec), f'{f}#{len(corpus.data[f]) - 1}', desc(rec), '新增', f'补录 {tag}',
                spec.get('note', '')])
    return rec


def interleave(*seqs):
    """按组交错：a1 b1 a2 b2……用于把分卷选本的一首一首排回目次顺序。"""
    out = []
    for i in range(max(len(x) for x in seqs)):
        for s in seqs:
            if i < len(s):
                out.append(s[i])
    return out


GAP = 40  # 拆同一题下的几首时，相邻两首之间允许的空档（换行、异文、错字都会留口子）


def seqs_of(poems, corpus, tag):
    """选本一条里若连着装了几首（長干曲四首、塞下曲四首），拆成那几首。

    认法：同作者、正文整首见于本诗的总集记录，按在本诗里的位置排；字头相接的算同一段
    （换行、异文造成的小缺口不管）。只看正文，不靠题名——「塞下曲四首」在总集里叫
    「和張僕射塞下曲」。
    """
    by_author = collections.defaultdict(list)
    for _, _, r in corpus.recs:
        by_author[author_key(r.get('author'))].append(r)
    out = []
    for p in poems:
        b = body(p)
        hits = []
        for r in by_author.get(author_key(p.get('author')), []):
            q = body(r)
            if q and q in b:
                hits.append((b.index(q), r))
        hits.sort(key=lambda x: x[0])
        chains = []                          # 每一段：[(位置, 记录), ...]
        for at, r in hits:
            if chains and at - (chains[-1][-1][0] + len(body(chains[-1][-1][1]))) <= GAP:
                chains[-1].append((at, r))
            else:
                chains.append([(at, r)])
        out.append([r for _, r in (chains[0] if chains else [])] or [p])
    return out


def plan_tang300(poems, corpus, entries, tag):
    """把选本条目铺到目次的连续编号上：[(编号, 目次条目 or None, 选本记录)]。

    先按题名前 4 字对目次；对不上的拿选本正文的每一句去试目次记的首句。
    两条都落空才顺延一位占个空号，由 merge_tang300 按目次首句兜底。
    """
    by_title = collections.defaultdict(list)
    for e in entries:
        by_title[title_key(e['title'])].append(e['no'])
    slots, used_title = [0] * len(poems), set()
    for k, p in enumerate(poems):
        base = (p.get('title') or '').split('・')[0]
        if title_key(p['title']) in by_title and (base not in TANG300_GROUP
                                                  or title_key(p['title']) not in used_title):
            used_title.add(title_key(p['title']))
            slots[k] = by_title[title_key(p['title'])][0]
            continue
        for e in entries:                   # 目次只记了首句，拿选本的每一句去试
            if any(norm(e['first_line'])[:6] in s for s in sents(p)):
                slots[k] = e['no']
                break

    # 分卷的几首（長干曲、塞下曲……）：那几首紧跟在同题条目后面依次占号
    for k, p in enumerate(poems):
        if (p.get('title') or '').split('・')[0] in TANG300_GROUP:
            base = slots[k - 1] if k else 0
            if base:
                slots[k] = base + 1

    # 已知的号必须递增；倒挂的（目次里这一首在前）放弃这个号，改让兜底规则处理
    last = 0
    for k, n in enumerate(slots):
        if n and n > last:
            last = n
        elif n:
            slots[k] = 0

    # 对不上目次的：塞进前后两个已知号之间的空隙（按序排）；空隙不够、或前面已经没有
    # 可以顺延的号，就按选本自己并，不去占目次的号——占错了比没有更糟
    plan, last = [], 0
    for k, p in enumerate(poems):
        if slots[k]:
            last = slots[k]
            plan.append([slots[k], entries[slots[k] - 1], p])
            continue
        nxt = next((m for m in slots[k + 1:] if m), None)
        first = next((m for m in slots[k:] if m), 0)      # 后面第一个已知号
        if not last and first <= 1:                        # 排在那之前，前面没有号可用
            plan.append([None, None, p])
            continue
        ahead = last or first - 1
        if (nxt is None or nxt - ahead > 1) and 0 <= ahead < len(entries):
            plan.append([ahead + 1, entries[ahead], p])
        else:
            plan.append([None, None, p])
    return plan


def merge_tang300(rel, corpus, tag, entries, log):
    """唐/唐诗三百首/：能对上总集的挂 tag，目录里探明的按总集记载补录。

    编号只用来核对（评审时看选本这一首铺在目次哪一号）；一条里装着几首的（長干曲四首、
    塞下曲四首）按 seqs_of 拆开逐首并，拆出来的那几首本来就已在总集里。
    """
    poems = load(rel)
    plan = plan_tang300(poems, corpus, entries, tag)
    seqs = {id(p): s for p, s in zip(poems, seqs_of(poems, corpus, tag))}
    for no, entry, p in plan:
        where = f'目次第 {no} 首《{entry["title"]}》' if entry else '目次未收'
        parts = seqs[id(p)]
        for q in parts:
            if q is not p and is_tagged(q, tag):    # 拆出来的那首本就在总集里，挂过 tag 了
                continue
            if not body(q):                         # 总集只有题注、没有正文
                log.append([rel, desc(p), '', '', '', '保留', '总集只有题注、没有正文，选本这一条无从对勘'])
                break
            m = corpus.match(q)
            if m:
                f, i, rec = corpus.recs[m[0]]
                rec['tags'] = list(dict.fromkeys((rec.get('tags') or []) + [tag]))
                note = '' if m[2] else f'选本署名 {q.get("author")}'
                if len(parts) > 1:
                    note = (note + '；' if note else '') + f'选本此条含 {len(parts)} 首，按正文拆作{where}'
                log.append([rel, desc(q), f'{f}#{i}', desc(rec), f'{m[1]:.2f}', f'并入 tags {m[3]}', note])
                continue
            if q is not p:                          # 拆出来的那一首总集里没有
                log.append([rel, desc(q), '', '', '', '保留', f'总集未收（{where}）'])
                continue
            cand = [r for _, _, r in corpus.recs
                    if entry and title_key(r.get('title')) == title_key(entry['title'])
                    and norm(entry['first_line'])[:6] in body(r)]
            if cand:                                # 选本这一首与目次对不上，按目次取总集的同一首
                rec = cand[0]
                rec['tags'] = list(dict.fromkeys((rec.get('tags') or []) + [tag]))
                at = next(f'{f}#{i}' for f, i, r in corpus.recs if r is rec)
                log.append([rel, desc(p), at, desc(rec), '-', '并入 tags 按目次',
                            f'选本这一条与{where}正文不同，按目次取总集同一首'])
                continue
            if not entry and any(author_key(r.get('author')) == author_key(p.get('author'))
                                 and body(r) == body(p) for _, _, r in corpus.recs):
                continue                            # 已补录过，不重复
            spec = dict(p, title=entry['title'] if entry else p['title'])
            insert_record(corpus, dict(spec, author=INSERT_AUTHOR.get(spec.get('author'), spec.get('author'))),
                          tag, log, rel)
            if not entry:                           # 补录的条目里已经发过一条日志了
                continue
            log.append([rel, desc(p), '', '', '', '补录', f'{where}总集未收，按选本补录'])
    return []


def split_modern(rel, corpora, dynasties, log):
    """近现/ 里其实是唐宋元明清的课本选目，并回它所属的总集。"""
    keep = []
    for p in load(rel):
        order = DYN_PLAN.get(dynasties.get(author_key(p.get('author'))), [])
        hit = None
        for target in order:
            m = corpora[target].match(p)
            if m:
                hit = (target, m)
                break
        if not hit:
            keep.append(p)
            if order:
                log.append([rel, desc(p), '', '', '', '保留', '、'.join(order) + ' 都未收'])
            continue
        target, m = hit
        f, i, q = corpora[target].recs[m[0]]
        note = '' if m[2] else f'选本署名 {p.get("author")}'
        log.append([rel, desc(p), f'{f}#{i}', desc(q), f'{m[1]:.2f}', f'并入 {target}', note])
    return keep


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--apply', action='store_true')
    args = ap.parse_args()

    def corpus(*pattern):
        return Corpus(sorted(os.path.relpath(f, ROOT) for f in glob.glob(os.path.join(ROOT, pattern[0]))))

    tang = corpus('唐/诗/全唐诗/poet.tang.*.json')
    tang.files.append('三国/诗/poet.sanguo.json')     # 补录非唐人作品时落在这里
    tang.data['三国/诗/poet.sanguo.json'] = load('三国/诗/poet.sanguo.json')
    tang.recs.extend(('三国/诗/poet.sanguo.json', i, p)
                     for i, p in enumerate(tang.data['三国/诗/poet.sanguo.json']))
    corpora = {
        '全唐诗': tang,
        '全宋诗': corpus('宋/诗/全宋诗/poet.song.*.json'),
        '全宋词': corpus('宋/宋词/ci.song.*.json'),
        '昭明文选': corpus('汇编/昭明文选/*.json'),
        '古文观止': corpus('汇编/古文观止/*.json'),
        '历代': corpus('*/诗/poet.*.json'),
        '古诗源': corpus('*/古诗源/*.json'),
        '课外经典': corpus('汇编/课本选目/*.json'),
        '四书五经': corpus('先秦/论语/*.json'),
        '纳兰性德': corpus('清/*/纳兰*/*.json'),
    }
    with open(os.path.join(ROOT, 'authors/authors.json'), encoding='utf-8') as fp:
        dynasties = {cc.convert(a['name']): a['dynasty'] for a in json.load(fp)}

    log = []
    # 全唐诗/唐诗三百首.json 那份 366 首的副本早已删掉（见 docs/唐诗去重.tsv），此处只在它还在时才跑
    tang300_keep = merge_one('唐诗三百首/唐诗三百首.json', tang, '唐诗三百首', log) \
        if os.path.exists(os.path.join(ROOT, '唐诗三百首/唐诗三百首.json')) else []
    if not os.path.exists(os.path.join(ROOT, '唐诗三百首/唐诗三百首.json')):
        log.append(['唐诗三百首/唐诗三百首.json', '（整份 366 首）', '', '', '', '已并入',
                    '这份副本 2026-10 已删，366 首全部在 poet.tang.* 上挂 tags，见 docs/唐诗去重.tsv'])
    tt300 = ('唐/唐诗三百首/唐诗三百首.json')
    if os.path.exists(os.path.join(ROOT, tt300)):
        with open(os.path.join(ROOT, 'anthologies/tangshi300.json'), encoding='utf-8') as fp:
            entries = json.load(fp)['entries']
        merge_tang300(tt300, tang, '唐诗三百首', entries, log)
        for spec in INSERTED[:2]:                  # 目录里探明的两首按总集记载补录
            insert_record(tang, spec, '唐诗三百首', log, tt300, INTO.get(spec.get('author')))
    for spec in INSERTED[2:]:
        insert_into(tang, spec, '水墨唐诗', log, spec.pop('note'))
    ink_keep = []
    if os.path.exists(os.path.join(ROOT, '水墨唐诗/shuimotangshi.json')):
        ink_keep = merge_one('水墨唐诗/shuimotangshi.json', tang, '水墨唐诗', log)
    # 宋词三百首 目录已整体并入 ci.song.*（280 首全部对上，2026-10），此处保留为重跑时的兜底
    ci300_keep = merge_one('宋词三百首/宋词三百首.json', corpora['全宋词'], '宋词三百首', log) \
        if os.path.exists(os.path.join(ROOT, '宋词三百首/宋词三百首.json')) else []
    # 近现/ 已在 2026-10 拆完（见 docs/选本并入.md），文件不在了就跳过
    modern_keep = split_modern('近现/近现.json', corpora, dynasties, log) \
        if os.path.exists(os.path.join(ROOT, '近现/近现.json')) else None

    c = collections.Counter((r[0], r[5]) for r in log)
    for k, n in sorted(c.items()):
        print(f'{k[0]} {k[1]}: {n}')
    for r in log:
        if not r[5].startswith('并入 tags ratio'):
            print('  ', '\t'.join(r))
    if not args.apply:
        return

    for name in ('全唐诗', '全宋词'):
        for f in corpora[name].files:
            save(f, corpora[name].data[f])
    save('三国/诗/poet.sanguo.json', tang.data['三国/诗/poet.sanguo.json'])
    if tang300_keep or os.path.isdir(os.path.join(ROOT, '唐诗三百首')):
        save('唐诗三百首/唐诗三百首.json', tang300_keep)
    if os.path.isdir(os.path.join(ROOT, '唐/唐诗三百首')):
        shutil.rmtree(os.path.join(ROOT, '唐/唐诗三百首'))
    if ink_keep:
        save('水墨唐诗/shuimotangshi.json', ink_keep)
    elif os.path.exists(os.path.join(ROOT, '水墨唐诗')):
        shutil.rmtree(os.path.join(ROOT, '水墨唐诗'))
    if ci300_keep:
        save('宋词三百首/宋词三百首.json', ci300_keep)
    elif os.path.exists(os.path.join(ROOT, '宋词三百首')):
        shutil.rmtree(os.path.join(ROOT, '宋词三百首'))
    if modern_keep is not None:
        save('近现/近现.json', modern_keep)
    with open(os.path.join(ROOT, 'docs/选本并入.tsv'), 'w', encoding='utf-8', newline='') as fp:
        fp.write('选本文件\t选本记录\t总集位置\t总集记录\t相似度\t处理\t说明\n')
        fp.writelines('\t'.join(r) + '\n' for r in log)


if __name__ == '__main__':
    main()
