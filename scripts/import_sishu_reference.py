#!/usr/bin/env python3
"""`reference/` 里的五部经书 → `先秦/` 下的五个 JSON：论语、孟子、大学、中庸、道德经。

    python3 scripts/import_sishu_reference.py            # 预演：条数 + 与库内旧文的逐字差异
    python3 scripts/import_sishu_reference.py --apply    # 写盘，并输出 docs/四书勘正.tsv
    python3 scripts/import_sishu_reference.py --check    # 只比对现有文件与底本是否一致

底本版式：

    reference/論語.txt     `## 學而篇第一` 一篇，一行一章
    reference/孟子.txt     `## 梁惠王上` 一篇，一行一章
    reference/大學.txt     不分章，一行一段
    reference/中庸.txt     不分章，一行一段
    reference/道德經.txt   `### 第一章` 一章，一行一句；行内全角空格是断句标记

底本是繁体点校本，句读用「，。；：？！」和「「」『』」；库内旧正文是简体 + 弯引号
（“”‘’）。生成时只做字形层面的归一，正文一字不改：

    繁体 → 简体      opencc t2s，再按 VOLCAB 把「余/后/干/发/云/斗/丑/冲/谷/只/尽/占/仆/
                    佣/卷/据/扎/梁/了/面/里/表/才/叶/于/台/几/宁/御/系/岳/周/雕/涂/
                    愿/并/泄/闲」等一对多的字收回底本词义对应的那个简体（如「餘」→余 而非
                    「馀」、「後」→后、「雲」→云、「穀」→谷、「隻」→只、「盡」→尽、
                    「捲」→卷、「據」→据、「嶽」→岳、「繫」→系、「彫」→雕、「塗」→途）
    异体归一         揜→掩、鼈→鳖、彫→雕、嶽→岳、啓→启、脩→修、菑→灾、並→并、敎→教
    引号              “ ” ‘ ’ → 「 」 『 』

  * `〔全文完〕` 与卷首撰者行不进正文；底本行末夹注（`(一作「…」)`）另收 `variants`；
  * 道德经照底本一句一段，`、` 连写的并列语不拆；
  * id 由「作者 + 题名 + 正文」哈希得来（规则同 `scripts/backfill_ids.py`），正文改了自然换号；
  * 与库内旧正文的每一处不同都写进 `docs/四书勘正.tsv`，逐字可复核。
"""
import argparse
import collections
import hashlib
import json
import os
import re
import sys
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import progress as pg  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REVIEWER = 'CodeBuddy'
ALPHABET = '0123456789abcdefghijklmnopqrstuv'
END_MARK = re.compile(r'^〔.+〕$')
NOTE_RX = re.compile(r'\s*[（(]([^（()）]*[「『][^（()）]*)[）)]\s*$')   # 行末夹注（一作「…」）
CN_NUM = '〇一二三四五六七八九十'
SENT_END = '。！？”’'
# 旧正文是简体爬取稿、断句与底本不同步的两部：对勘归到句子层面
SENT_NORM = {'mengzi', 'daodejing'}

BOOKS = [
    dict(key='lunyu', src='論語.txt', out='先秦/论语/lunyu.json',
         author='孔子及弟子', title='论语', dynasty='先秦', depth=2,
         chapter='篇', chapter_title=None),
    dict(key='mengzi', src='孟子.txt', out='先秦/孟子/mengzi.json',
         author='孟子', title='孟子', dynasty='先秦', depth=2,
         chapter='篇', chapter_title=None),
    dict(key='daxue', src='大學.txt', out='先秦/大学/daxue.json',
         author='曾子', title='大学', dynasty='先秦', depth=0,
         chapter=None, chapter_title='大学'),
    dict(key='zhongyong', src='中庸.txt', out='先秦/中庸/zhongyong.json',
         author='子思', title='中庸', dynasty='先秦', depth=0,
         chapter=None, chapter_title='中庸'),
    dict(key='daodejing', src='道德經.txt', out='先秦/文/daodejing.json',
         author='老子', title='道德经', dynasty='先秦', depth=1,
         chapter='章', chapter_title=None),
]

# 一对多的简体字：opencc 的默认选择有四处不合本书的用字习惯，改取的依据：
#   「餘」→ 余（不用「馀」，与库内其余书一致）、「後」→ 后、「雲」→ 云、「穀」→ 谷、
#   「隻」→ 只、「盡」→ 尽、「捲」→ 卷、「據」→ 据、「嶽」→ 岳、「繫」→ 系、
#   「彫」→ 雕（「岁寒，然后知松柏之后雕也」，库内旧文与底本字形都对得上「雕」）、
#   「塗」→ 涂（「塗有餓莩」即「涂有饿莩」，道路）、「願」→ 愿（底本「願」一律作「愿」）、
#   「瞭」→ 了（「眸子瞭焉」不从「了」，保留「瞭」，见下面 KEEP）；
#   其余按 opencc 默认。
VOLCAB = {
    '餘': '余', '後': '后', '乾': '干', '穀': '谷', '雲': '云', '鬥': '斗', '醜': '丑',
    '衝': '冲', '隻': '只', '儘': '尽', '佔': '占', '僕': '仆', '傭': '佣', '捲': '卷',
    '據': '据', '紮': '扎', '樑': '梁', '麵': '面', '裡': '里', '裏': '里', '錶': '表',
    '纔': '才', '葉': '叶', '瀋': '沈', '週': '周', '髮': '发', '幹': '干', '瞭': '了',
}
# 底本的破折号写作两个「─」（U+2500，制表符区）。它落在 `check_structure.py` 的
# box_drawing 里，会被当成 GBK 错位的乱码；正文里用「——」替代，底本不改。
DASH = (('──', '——'),)
# 底本用古字/异体，库内一律换通行简体字。这里收的是 opencc t2s 不处理、或者处理得
# 与本库用字不合的；「鞹/鞟」「匵/椟」「鮀/𬶍」这类是底本用字，照底本，不入此表。
VARIANT = {
    '揜': '掩', '鼈': '鳖', '彫': '雕', '嶽': '岳', '啓': '启', '脩': '修', '菑': '灾',
    '並': '并', '敎': '教', '隣': '邻', '衆': '众', '眞': '真', '卽': '即', '旣': '既',
    '兪': '俞', '叚': '假', '凂': '浼', '峯': '峰', '牀': '床', '敍': '叙', '箇': '个',
    '旂': '旗', '衞': '卫', '鄕': '乡', '飮': '饮', '飱': '飧', '鍊': '炼', '煑': '煮',
}
# 保留字形：opencc 会改、但底本这一处用的就是本字
KEEP = set('瞭')
# 标点：底本用「」『』，库内旧文用弯引号；底本夹注里的全角冒号分号也一并归一
QUOTE = str.maketrans({'「': '“', '」': '”', '『': '‘', '』': '’',
                       '﹕': '：', '﹔': '；', '︰': '：'})


def t2s(text):
    import opencc
    conv = opencc.OpenCC('t2s').convert
    out = []
    for ch in text:
        if ch in KEEP:
            out.append(ch)
        elif ch in VOLCAB:
            out.append(VOLCAB[ch])
        elif ch in VARIANT:
            out.append(VARIANT[ch])
        else:
            out.append(conv(ch))
    return ''.join(out)


def normalize(text):
    """底本一行 → 库内一行：繁简、异体、引号、破折号。"""
    for wrong, right in DASH:
        text = text.replace(wrong, right)
    return t2s(text).translate(QUOTE)


def line_hash(body):
    return hashlib.blake2b('\x00'.join(body).encode(), digest_size=8).hexdigest()


def work_key(rec):
    """id 的键：作者 + 题名 + 正文（不分段），与 `scripts/backfill_ids.py` 一致。"""
    return f"{rec['author']}|{rec['title']}|{''.join(rec['paragraphs'])}"


def assign(keys, taken=()):
    """同 `scripts/backfill_ids.py`：按 key 字典序发号，与库里现存顺序无关，重跑幂等。"""
    taken = set(taken)
    out = {}
    for key in sorted(set(keys)):
        for salt in range(1, 16):
            size = 6 + max(0, salt - 1)
            raw = key if salt == 1 else f'{key}|{salt}'
            cand = _base22(hashlib.blake2b(raw.encode(), digest_size=16).digest(), size)
            if cand not in taken:
                out[key] = cand
                taken.add(cand)
                break
        else:
            sys.exit(f'key {key[:30]!r} 找不到不重复的 id')
    return out


def _base22(digest, size):
    v = int.from_bytes(digest, 'big')
    out = ''
    for _ in range(size):
        v, r = divmod(v, 22)
        out = ALPHABET[r] + out
    return out


def cn2int(s):
    cn = {c: i for i, c in enumerate(CN_NUM)}
    cn['零'] = 0
    if '十' not in s:
        return int(''.join(str(cn[c]) for c in s))
    hi, _, lo = s.partition('十')
    return (cn[hi] if hi else 1) * 10 + (cn[lo] if lo else 0)


def split_note(line):
    m = NOTE_RX.search(line)
    if not m:
        return line, None
    return line[:m.start()].strip(), m.group(1).strip()


def parse(book):
    """→ [{'chapter': 章名, 'lines': [正文…], 'notes': [(正文, 夹注)…]}]"""
    path = os.path.join(ROOT, 'reference', book['src'])
    if book['chapter'] is None:                       # 大学、中庸：不分章
        lines, notes = [], []
        for raw in open(path, encoding='utf-8'):
            line = raw.strip().replace('\u3000', '').strip()
            if not line or line.startswith('#') or END_MARK.match(line):
                continue
            body, note = split_note(line)
            lines.append(normalize(body))
            if note:
                notes.append(normalize(note))
        return [{'chapter': book['chapter_title'], 'lines': lines, 'notes': notes}]

    secs, cur = [], None
    lvl = '###' if book['depth'] == 1 else '##'
    for raw in open(path, encoding='utf-8'):
        line = raw.strip().replace('\u3000', '').strip()
        if not line:
            continue
        if line.startswith('#'):
            head = line.lstrip('#').strip()
            if len(line) - len(line.lstrip('#')) != len(lvl):
                continue                              # 书名行
            if '撰' in head or '著' in head:
                continue                              # 著者行
            m = re.match(r'^第([〇零一二三四五六七八九十]+)章$', head)
            name = normalize(f"第{cn2int(m.group(1))}章" if m and book['chapter'] == '章' else head)
            cur = {'chapter': name, 'lines': [], 'notes': []}
            secs.append(cur)
            continue
        if END_MARK.match(line):
            continue
        if cur is None:
            continue
        body, note = split_note(line)
        cur['lines'].append(normalize(body))
        if note:
            cur['notes'].append(normalize(note))
    return secs


def book_title(book, chapter):
    """题名：论语「论语学而篇第一」、孟子「孟子·梁惠王上」、道德经「道德经（第N章）」。"""
    if book['key'] == 'lunyu':
        return f'{book["title"]}{chapter}'
    if book['key'] == 'mengzi':
        return f'{book["title"]}·{chapter}'
    if book['depth'] == 1:
        return f'{book["title"]}（{chapter}）'
    return book['title']


def build(book):
    """→ [{'author','title','dynasty','chapter'?, 'paragraphs', 'note'?}]，未发 id。"""
    recs = []
    for s in parse(book):
        rec = {'author': book['author'], 'title': book_title(book, s['chapter']),
               'dynasty': book['dynasty']}
        if book['chapter'] is not None:               # 论语、孟子、道德经：分篇/分章
            rec['chapter'] = s['chapter']
        rec['paragraphs'] = s['lines']
        if s['notes']:
            rec['note'] = '；'.join(f'底本夹注：{n}' for n in s['notes'])
        recs.append(rec)
    return recs


def load_old(rel, ref=None):
    """读库内旧正文；`ref` 给了就从 git 的那个版本读（对勘表要按旧稿算）。"""
    if ref:
        import subprocess
        out = subprocess.run(['git', 'show', f'{ref}:{rel}'], cwd=ROOT,
                             capture_output=True, text=True, check=True).stdout
        return json.loads(out)
    path = os.path.join(ROOT, rel)
    if not os.path.exists(path):
        return []
    return json.load(open(path, encoding='utf-8'))


def old_texts(old, depth):
    """旧正文摊平成一串段（道德经是一章一条）。"""
    out = []
    for rec in old:
        body = rec['paragraphs']
        if depth == 2:
            out.extend(body)
        else:
            out.extend(body)
    return out


def diff_rows(key, new_lines, old_lines, normalize_sent=True):
    """逐段对勘：段内按字给出「库内旧文 → 底本正文」，段次对不上的整段单列。

    `normalize_sent` 的两部（孟子、道德经）旧稿是简体爬取稿：断句、引号的成对方式都与底本
    不同步，先按句末标点重分句，免得一句之差把后文整片算成错位；两边重复出现的句子先各留
    一份，再去掉表里重复的行。
    """
    import difflib

    if normalize_sent:
        old_lines, new_lines = sent_split(old_lines), sent_split(new_lines)

    rows, seen = [], set()

    def add(row):
        k = (row[1], row[2])
        if k in seen:
            return
        seen.add(k)
        rows.append(row)

    sm = difflib.SequenceMatcher(None, old_lines, new_lines, autojunk=False)
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == 'equal':
            continue
        if tag == 'replace' and i2 - i1 == j2 - j1:
            for a, b in zip(old_lines[i1:i2], new_lines[j1:j2]):
                s = difflib.SequenceMatcher(None, a, b, autojunk=False)
                for t, x1, x2, y1, y2 in s.get_opcodes():
                    if t == 'equal' or (a[x1:x2], b[y1:y2]) in KNOWN:
                        continue
                    add([key, a[x1:x2] or '∅', b[y1:y2] or '∅',
                         kind(a[x1:x2], b[y1:y2]), b[max(0, y1 - 10):y2 + 10]])
            continue
        if i1 == i2 or j1 == j2:                      # 整段的增删，逐段单列
            head = '旧文此处多出/错位' if j1 == j2 else '底本此处多出/错位'
            for a in old_lines[i1:i2]:
                add([key, a[:40] + ('…' if len(a) > 40 else ''), '∅', '段次', head])
            for b in new_lines[j1:j2]:
                add([key, '∅', b[:40] + ('…' if len(b) > 40 else ''), '段次', head])
    return rows


def sent_split(lines):
    """粗分句：太短的片段（只有收尾引号之类）并回前一句，免得对勘表里全是碎渣。"""
    out = []
    for p in lines:
        buf = ''
        for ch in p:
            buf += ch
            if ch in SENT_END:
                out.append(buf)
                buf = ''
        if buf:
            out.append(buf)
    merged = []
    for x in out:
        if merged and len(x.strip('”’」』')) < 4:
            merged[-1] += x
        else:
            merged.append(x)
    return merged


PUNCT = set('，。；：？！、“”‘’（）「」『』…─—·')


# 底本自用的异体，与库内用字相差一个字形的，对勘表里不必再报（正文照底本）
KNOWN = {
    ('乎', '矣'),          # 底本「難乎有恒矣」，断句错位导致的假差异，见 docs/四书校对.md
}


def kind(old, new):
    null = ('∅', '')
    if old in null or new in null:
        return '段次'
    if old in PUNCT or new in PUNCT:
        return '句读'
    if len(old) == len(new) and t2s(old) == new:
        return '字形（繁简/异体）'
    if len(old) > len(new):
        return '库内多字'
    if len(old) < len(new):
        return '底本多字'
    return '讹字/异文'


ORDER = ('author', 'title', 'dynasty', 'chapter', 'paragraphs', 'note', 'id')
SKIP_DIRS = {'author', 'rank', 'settings', '表面结构字', 'error', 'fix_progress', 'loader', 'strains',
             'images', 'rank', 'error', 'authors', 'dynasties', 'anthologies', 'scripts', 'docs',
             '.git', '.claude', '.github', '.cnb', 'reference'}


def all_ids():
    """库里现存全部记录的 id（发号时避开，免得与别的书撞码）。"""
    out = set()
    for dirpath, dirs, files in os.walk(ROOT):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for f in files:
            if not f.endswith('.json') or 'fix_progress' in f:
                continue
            try:
                data = json.load(open(os.path.join(dirpath, f), encoding='utf-8'))
            except ValueError:
                continue
            items = data if isinstance(data, list) else [data]
            for r in items:
                if isinstance(r, dict) and isinstance(r.get('id'), str):
                    out.add(r['id'])
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--apply', action='store_true', help='写盘；否则只预演')
    ap.add_argument('--check', action='store_true', help='只比对现有文件与底本是否一致')
    ap.add_argument('--date', default=date.today().isoformat())
    ap.add_argument('--tsv', default='docs/四书勘正.tsv')
    ap.add_argument('--ref', help='对勘表按 git 的这个版本算「旧文」（如 develop），缺省按工作区现存文件')
    args = ap.parse_args()

    per_book, total_rows = [], 0
    for book in BOOKS:
        new = build(book)
        old = load_old(book['out'], args.ref)
        new_lines = [p for r in new for p in r['paragraphs']]
        old_lines = old_texts(old, book['depth'])
        rows = diff_rows(book['key'], new_lines, old_lines, book['key'] in SENT_NORM)
        per_book.append((book, new, old, rows))
        total_rows += len(rows)

    for book, new, old, rows in per_book:
        n = sum(len(r['paragraphs']) for r in new)
        chars = sum(len(p) for r in new for p in r['paragraphs'])
        kinds = collections.Counter(r[3] for r in rows)
        print(f"{book['out']:<24}{len(new):>4} 条 {n:>4} 段 {chars:>6} 字"
              f"  旧 {len(old):>4} 条  差异 {len(rows):>4}（{dict(kinds)}）")
    print(f'\n共 {total_rows} 处差异')

    if args.check:
        ok = True
        for book, new, _, _ in per_book:
            for r in new:                             # 存量文件里已有 id，比对时沿用
                r.setdefault('id', None)
            stored = {r['title']: r.get('id') for r in load_old(book['out'])}
            for r in new:
                r['id'] = stored.get(r['title'])
            path = os.path.join(ROOT, book['out'])
            recs = [{k: r[k] for k in ORDER if r.get(k) is not None} for r in new]
            same = os.path.exists(path) and open(path, encoding='utf-8').read() == dump(recs)
            print(('一致  ' if same else '不一致') + '  ' + book['out'])
            ok = ok and same
        return 0 if ok else 1
    if not args.apply:
        for book, new, old, rows in per_book:
            print(f'\n== {book["out"]}')
            for r in rows[:25]:
                print('  ', '\t'.join(r))
            if len(rows) > 25:
                print(f'   …… 另 {len(rows) - 25} 处，写盘后见 {args.tsv}')
        return 0

    taken, records = set(), []
    for book, new, old, rows in per_book:
        taken |= {r.get('id') for r in old if r.get('id')}
    taken |= all_ids()                                 # 全库 id 不许撞
    ids = assign([work_key(r) for _, new, _, _ in per_book for r in new], taken)
    tsv = ['书\t库内旧文\t底本正文\t类型\t上下文']
    for book, new, old, rows in per_book:
        for r in new:
            r['id'] = ids[work_key(r)]
            r = {k: r[k] for k in ORDER if k in r}
            records.append((book, r))
        tsv.extend('\t'.join(r) for r in rows)
    for book in BOOKS:
        recs = [r for b, r in records if b is book]
        open(os.path.join(ROOT, book['out']), 'w', encoding='utf-8').write(dump(recs))
        print('→', book['out'], len(recs), '条')
    open(os.path.join(ROOT, args.tsv), 'w', encoding='utf-8').write('\n'.join(tsv) + '\n')
    print('→', args.tsv, len(tsv) - 1, '行')
    return 0


def dump(recs):
    return json.dumps(recs, ensure_ascii=False, indent=2) + '\n'


if __name__ == '__main__':
    sys.exit(main())
