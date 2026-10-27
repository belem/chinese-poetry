#!/usr/bin/env python3
"""把零碎的选本目录并回它所属的总集，去掉目录层级的重复。

  python3 scripts/merge_selections.py            # 预演：打印每条匹配报告
  python3 scripts/merge_selections.py --apply    # 写回数据，并生成 docs/选本并入.tsv

四件事：

  唐诗三百首/   65 首 → 全唐诗/poet.tang.* 的 tags（此前只并过 全唐诗/唐诗三百首.json，
                 那是另一份 366 首的副本；这个目录是上游 poems-tangshi.js 的 65 首）
  水墨唐诗/     余 4 首 → 并入 poet.tang 并带 prologue；总集未收的 3 首按全唐诗的记载补录，
                 目录删掉（四条已全部落在 poet.tang 上）
  宋词三百首/   余 4 首 → 能对上的并入 ci.song.* 的 tags，对不上的留下
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
INSERTED = [
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
    corpora = {
        '全唐诗': tang,
        '全宋诗': corpus('宋/诗/全宋诗/poet.song.*.json'),
        '全宋词': corpus('宋/宋词/ci.song.*.json'),
        '昭明文选': corpus('昭明文选/*.json'),
        '古文观止': corpus('古文观止/*.json'),
        '历代': corpus('历代/*.json'),
        '古诗源': corpus('古诗源/*.json'),
        '课外经典': corpus('课外经典/*.json'),
        '四书五经': corpus('四书五经/*.json'),
        '纳兰性德': Corpus(['纳兰性德/纳兰性德诗集.json']),
    }
    with open(os.path.join(ROOT, 'authors/authors.json'), encoding='utf-8') as fp:
        dynasties = {cc.convert(a['name']): a['dynasty'] for a in json.load(fp)}

    log = []
    tang300_keep = merge_one('唐诗三百首/唐诗三百首.json', tang, '唐诗三百首', log)
    for spec in INSERTED:
        insert_into(tang, spec, '水墨唐诗', log, spec.pop('note'))
    ink_keep = []
    if os.path.exists(os.path.join(ROOT, '水墨唐诗/shuimotangshi.json')):
        ink_keep = merge_one('水墨唐诗/shuimotangshi.json', tang, '水墨唐诗', log)
    ci300_keep = merge_one('宋词三百首/宋词三百首.json', corpora['全宋词'], '宋词三百首', log)
    modern_keep = split_modern('近现/近现.json', corpora, dynasties, log)

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
    save('唐诗三百首/唐诗三百首.json', tang300_keep)
    if ink_keep:
        save('水墨唐诗/shuimotangshi.json', ink_keep)
    elif os.path.exists(os.path.join(ROOT, '水墨唐诗')):
        shutil.rmtree(os.path.join(ROOT, '水墨唐诗'))
    if ci300_keep:
        save('宋词三百首/宋词三百首.json', ci300_keep)
    elif os.path.exists(os.path.join(ROOT, '宋词三百首')):
        shutil.rmtree(os.path.join(ROOT, '宋词三百首'))
    save('近现/近现.json', modern_keep)
    with open(os.path.join(ROOT, 'docs/选本并入.tsv'), 'w', encoding='utf-8', newline='') as fp:
        fp.write('选本文件\t选本记录\t总集位置\t总集记录\t相似度\t处理\t说明\n')
        fp.writelines('\t'.join(r) + '\n' for r in log)


if __name__ == '__main__':
    main()
