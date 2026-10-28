#!/usr/bin/env python3
"""把 reference/mit_licence_haitang（11407 条，MIT 授权）补录进本库。

路由规则（2026-10 目录改成 14 个朝代目录之后；朝代表沿用 split_dynasty.py）：

  元 + 曲   → 元/元曲/yuanqu.json
  宋 + 诗   → 宋/诗/全宋诗/poet.song.*.json
  宋 + 词   → 宋/宋词/ci.song.*.json
  五代十国 + 词 → 宋/宋词/ci.song.*.json（与 五代十国/词/五代诗词/ 逐字重复的会被判重，落不到这里）
  其余      → <朝代>/诗/poet.<代号> 或 <朝代>/词/ci.<代号>（单文件书直接是 .json）

  「其余」原先写到 历代/，那个目录 2026-10 已拆散（见 docs/历代拆分.md），现在按作者朝代落位：
  朝代取 authors/authors.json 的行，查不到再退回源数据的 dynasty；辽/金 归 宋，周/秦/商/上古 归 先秦。
  体裁按 kind_cn：词进 ci.*；诗、文、赋都进 poet.*（本库 poet.* 本来就是诗文混放）。

作者小传 → authors/authors.json，朝代概述 → dynasties/dynasties.json（独立索引，
不与正文混放；本库原有 authors.tang/authors.song 各自只管一个总集，字段还不同）。

清洗（源数据是数字出版转码，乱码一律不猜）：
  PUA 私用区、无上下文的西里尔/希腊/假名 → □（本库表示底本缺字）
  ── → 中文破折号；\r\n → 单行一句；行首行尾空白清掉；空行去掉
  FIXED 表只收上下文 100% 确定的定点还原，其余一律 □

判重按正文（简繁统一 + 异体归一 + 去标点），命中库中已有条目的不重收。四道关（见 docs/haitang重跑.md）：

  1. 正文完全相同 —— 键取自**清洗后**正文，与写盘同源；拿原始正文建键，
     源里那点拼音夹注、CRLF、半角标点就能让一字不差的条目对不上（2026-10 重跑预演收 1273 条，
     正文相同的占 9742 条）。
  2. 形近异体同等 —— 库写「盪胷」源写「荡胸」这类，判重时折算，不改写盘正文。
  3. 同作者同题、正文相似 ≥ NEAR_DUP —— 底本异文（猿/猨、滚滚/衮衮）都落在这里。
  4. 节含于库章 —— 论语/孟子/中庸库里一条一章、源里一条一节，只能判包含关系。

来源是到处收集的语料，不挂 sources 标记——sources 只留给唐诗三百首这类权威合集。

已有文件里残留的 `"sources": ["haitang"]`：本脚本曾用它标记补录来源，2026-10 起全部清除
（用户口径：sources 只留给权威选本/总集，haitang 不是）。中途出过两次回潮——`split_dynasty.py`
按旧口径拆文件、`dedupe_tang.py` 按旧口径写互见——都已改掉；重跑本脚本不会再把标记写回去，
`--apply` 之前会扫一遍目标文件报出残留条数：

  python3 scripts/haitang/import.py --check-sources   # 只扫，不改

后续补录：源文件随时可能被上游修好（works_3.json 原是裸对象流，2026-10 补上外层方括号，
内容不变），这时用 --only 只重跑那一个文件，判定表写进单独的日志，不覆盖首次导入的那份：

  python3 scripts/haitang/import.py --only works_3 --tsv docs/haitang收录.works_3.tsv

用法：
  python3 scripts/haitang/import.py                  # 预演，打印清单
  python3 scripts/haitang/import.py --apply           # 写盘
  python3 scripts/haitang/import.py --apply --authors --dynasties
  python3 scripts/haitang/import.py --only works_3 --tsv docs/haitang收录.works_3.tsv
"""
import argparse
import json
import os
import re
import sys
import unicodedata

import difflib

from opencc import OpenCC

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import source  # noqa: E402
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import backfill_ids  # noqa: E402  补录的记录也要有 id，规则见该文件文档头

ROOT = source.ROOT
T2S = OpenCC('t2s')
S2T = OpenCC('s2t')

FREE_KINDS = {'诗', '词', '文', '赋'}
PREFIX_LEN = 12             # 包含判重时先用正文前这么多字挑候选
TARGET_SIZE = 1000          # 与库中 poet.*.json / ci.song.*.json 一致

# 同作者同题时，正文相似度达到此值视为同一作品（异文），不重收。
# 低于此值的是同题下的不同篇目（如苏轼多首《洞仙歌》），照收。
NEAR_DUP = 0.9

# 上下文 100% 确定的定点还原（每条都有依据，不做模式推断）
FIXED = {
    '罗睺侯': None,          # 占位：见下方 FIXED_TEXT
}
FIXED_TEXT = [
    # (错误片段, 正确片段, 依据)
    ('罗\ue4bf侯', '罗睺侯', '史书作「罗睺侯」，PUA 位为「睺」'),
    ('\ue3fd焦', '焦', 'PUA 位于「焦」前，删'),
]

PUA = re.compile(r'[\ue000-\uf8ff]')
CYRILLIC_GREEK = re.compile(r'[\u0400-\u04ff\u0370-\u03ff]')
KANA = re.compile(r'[\u3040-\u30ff\u3100-\u312f\u31a0-\u31bf]')
BOX = re.compile(r'[\u2500-\u257f\ufffd]')
ASCII_RES = re.compile(r'[A-Za-z0-9]+')
DASH = re.compile(r'[─—]{2,}')
BLANK = re.compile(r'\r\n|\r|\n')
# 半角标点（转码残留）→ 全角；只转紧邻汉字/引号的那几个，不动数字与英文
HALF_PUNCT = str.maketrans({',': '，', ';': '；', ':': '：', '!': '！', '?': '？'})
# 源里表示「缺字/未识读」的记号：半角的 ?，前后都有字时按缺字处理
# 缺字记号：源里「阖闾弟夫？」「名曰独？」这类，指未识读的字。只认这个上下文——
# 名词性单字 + ? 且紧跟「。」或下一句，不做通用推断，避免把真疑问句（若何？）误改
LONE_Q = re.compile(r'(?<=[\u4e00-\u9fff])[?？](?=[。，；：]|[\u4e00-\u9fff](?![，。；：、]))')
DUP_PUNCT = re.compile(r'([，。；：、！？])\1+')
# 「进来！。」「何？」这类句末连缀，保留最强者
END_CLASH = re.compile(r'([！？])。')
# 源是数字出版转码，夹在汉字之间的「全角括号 + 拼音/注音」是编者加的，本库正文不收：
# 召（shào）滑、酴(tu)醾 (mi）、陂(bēi)田、擘(bāi)——括号后紧跟括号的写法也一并吃掉。
# 只认括号里全是拉丁字母/数字/声调符号的，汉字夹注（「（史记误为厉公）」）不动。
# 源里半角 ( 配全角 ）的混搭不少，两侧括号各认各的。
RUBY = re.compile(r'[（(]\s*[A-Za-z0-9\u00c0-\u024f\u0300-\u036f'
                  r'āáǎàēéěèīíǐìōóǒòūúǔùǖǘǚǜü]+[）)]')


# ---------------------------------------------------------------- 清洗

def clean_text(text):
    """源正文 → 本库正文。只清转码残渣，不改字（除 FIXED_TEXT 里的定点还原）。"""
    if not text:
        return ''
    for wrong, right, _ in FIXED_TEXT:
        text = text.replace(wrong, right)
    text = DASH.sub('——', text)
    text = BLANK.sub('\n', text)
    # 无上下文的乱码一律换缺字记号，不猜
    text = PUA.sub('□', text)
    text = CYRILLIC_GREEK.sub('□', text)
    text = KANA.sub('□', text)
    text = BOX.sub('□', text)
    # 注音夹注先删掉，不能落到下面「字母数字 → □」那一档，否则会把注音写成缺字记号
    text = RUBY.sub('', text)
    text = ASCII_RES.sub(lambda m: '□' if not m.group().isdigit() else '□', text)
    # 半角标点转全角（转码残留），再收拾重复标点
    # 源里用半角 ? 表示「未识读的字」（如「阖闾弟夫？」指夫概），夹在汉字之间时先换缺字记号，
    # 必须在半角转全角之前处理，否则会被当成问号
    text = LONE_Q.sub('□', text)
    text = re.sub(r'[,;:!]', lambda m: m.group().translate(HALF_PUNCT), text)
    text = DUP_PUNCT.sub(r'\1', text)
    text = END_CLASH.sub(r'\1', text)
    lines = [ln.strip() for ln in text.split('\n')]
    return '\n'.join(ln for ln in lines if ln)


def to_paragraphs(text):
    """一行一句；超长段（古文整篇一段）不再切分，交给下端排版。"""
    return [ln for ln in text.split('\n') if ln]


def norm_title(t):
    t = (t or '').strip()
    t = re.sub(r'\s*·\s*', '·', t)          # 「浮生六记· 卷一」→「浮生六记·卷一」
    return re.sub(r'\s+', '', t)


def ci_parts(title):
    """词题「临江仙 · 夜归临皋」→ (rhythmic=临江仙, title=夜归临皋)。"""
    t = norm_title(title)
    if '·' in t:
        head, rest = t.split('·', 1)
        return head, rest
    return t, ''


# 异体字归一：opencc 的 t2s 表不收这些，但库与 haitang 语料各写了其中一种（《望岳》库作
# 「盪胷生曾雲」，源作「荡胸生曾云」）。不归一，同一首的两份正文就差一个字，判重和 diff 都得
# 为这一个字打一架。只收真的单值对应，两边都通行的异体（峯/峰、沈/沉、猿/猨）不在此列——
# 那类要按底本定，不能替作者选字。
VARIANT = str.maketrans({
    '胷': '胸', '胊': '胸',
})


def dedup_key(text):
    """判重键：繁→简、异体归一、去标点空白。"""
    s = T2S.convert(text)
    s = s.translate(VARIANT)
    s = ''.join(ch for ch in s if unicodedata.category(ch)[0] in 'LN')
    return s


# 这些目录名是体裁/朝代，不是书名
NOT_A_BOOK = {'先秦', '汉', '三国', '晋', '南北朝', '隋', '唐', '五代十国', '宋', '元', '明',
              '清', '近现', '当', '汇编', '诗', '词', '文', '全唐诗', '全宋诗', '宋词'}


def book_of(record):
    """一条记录所属的书名。

    题名带「·」的取头一节：「孟子·第一卷·梁惠王上·第七节」→「孟子」。
    库里的《论语》《孟子》《中庸》按章分条，没有 title 只有 chapter，这时返回 ''，
    由 book_of_path 从目录名取（先秦/孟子/mengzi.json → 孟子）。
    """
    t = norm_title(record.get('title') or '')
    return t.split('·')[0] if '·' in t else ''


def book_of_path(rel):
    """目录名 → 书名。库里按章分的书都放在中文书名的目录下。"""
    parts = [p for p in rel.replace(os.sep, '/').split('/') if p]
    if len(parts) >= 2 and parts[-2] not in NOT_A_BOOK:
        return parts[-2]
    return ''


# 形近异体：库与源各写了一种，正文因此差一个字。这类不是异文，是本库该统一的字形。
# 只收「同一个字」的两种写法（猃/𤞤 是《诗经》里同一个「玁狁」），遇到不同字一律不碰。
LOOKALIKE = str.maketrans({
    '𤞤': '猃',
    '玁': '猃',
    '榖': '谷',
})


def norm_text(text):
    """判重前把形近异体折回一种写法。**只用于判重，不改写盘正文。**"""
    return dedup_key(text).translate(LOOKALIKE)


def short_key(author, text):
    """短句（<8 字）光凭正文会与同句撞车，改用「作者 + 正文」联合键。"""
    return (author or '').strip() + '|' + dedup_key(text)


# ---------------------------------------------------------------- 库内探底

def load_json(path):
    with open(path, encoding='utf-8') as fp:
        return json.load(fp)


def write_json(path, data, compact=False):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as fp:
        if compact:
            fp.write('[\n')
            fp.write(',\n'.join(json.dumps(it, ensure_ascii=False, separators=(',', ':'))
                                for it in data))
            fp.write('\n]\n')
        else:
            json.dump(data, fp, ensure_ascii=False, indent=2)
            fp.write('\n')


def indent_of(text):
    """量出这份文件每条记录的缩进单位（单条记录相对于数组的缩进）。"""
    lines = text.split('\n')
    for i, ln in enumerate(lines):
        if ln.strip() == '{':
            base = len(ln) - len(ln.lstrip(' '))
            for nxt in lines[i + 1:]:
                if nxt.strip() and not nxt.strip().startswith('}'):
                    return len(nxt) - len(nxt.lstrip(' ')) - base
            return 2
    return None


def append_json(path, new_items):
    """在既有文件末尾追加条目，原有文本一字不动（只补分隔逗号与结尾括号）。

    新条目按这份文件自己的缩进排（poet.qing.json 是两格、元曲是单行紧凑），
    这样一条新增只产生几行 diff，不会把整份文件重新排一遍。
    """
    if not new_items:
        return
    with open(path, encoding='utf-8') as fp:
        text = fp.read()
    body = text.rstrip()
    assert body.endswith(']'), path
    body = body[:-1].rstrip()
    assert body.endswith('}') or body.endswith(','), path
    if body.endswith(','):
        body = body[:-1].rstrip()
    unit = indent_of(text)
    if unit is None:
        add = ',\n'.join(json.dumps(it, ensure_ascii=False, separators=(',', ':')) for it in new_items)
    else:
        pad = ' ' * unit
        add = pad + (',\n' + pad).join(
            json.dumps(it, ensure_ascii=False, indent=unit).replace('\n', '\n' + pad)
            for it in new_items)
    with open(path, 'w', encoding='utf-8') as fp:
        fp.write(body + ',\n' + add + '\n]\n')


def rewrite_json(path, data):
    """整体重写（仅新建文件），沿用库中 indent=2 的排版。"""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as fp:
        json.dump(data, fp, ensure_ascii=False, indent=2)
        fp.write('\n')


class Library:
    """本库已有正文的索引 + 写盘目标。"""

    def __init__(self):
        self.index = {}         # dedup_key → (relpath, idx)
        self.title_index = {}   # (作者, 规范化题) → [(relpath, idx)]
        self.files = {}         # relpath → list
        self.touched = set()
        self.ids = set()        # 库中已有 id，新记录不与它们撞
        self.book_index = {}    # 书名（「孟子」「论语」）→ [(relpath, idx)]
        self.prefix_index = {}  # dedup_key 前 PREFIX_LEN 字 → [(relpath, idx)]
        self.exact_index = {}   # norm_text（形近异体已折） → (relpath, idx)

    def scan(self):
        for dirpath, dirs, filenames in os.walk(ROOT):
            dirs[:] = sorted(d for d in dirs if not d.startswith('.')
                             and d not in {'reference', 'scripts', 'docs', 'images', 'loader',
                                           'strains', 'rank', 'node_modules'})
            for f in sorted(filenames):
                if not f.endswith('.json'):
                    continue
                rel = os.path.relpath(os.path.join(dirpath, f), ROOT)
                if rel.startswith('reference') or '/error/' in '/' + rel:
                    continue
                try:
                    data = load_json(os.path.join(dirpath, f))
                except (json.JSONDecodeError, UnicodeDecodeError):
                    continue
                if not isinstance(data, list):
                    continue
                if not any(isinstance(it, dict) and 'paragraphs' in it for it in data[:3] or []):
                    continue
                self.files[rel] = data
                for idx, it in enumerate(data):
                    if not isinstance(it, dict):
                        continue
                    if it.get('id'):
                        self.ids.add(it['id'])
                    body = it.get('paragraphs') or it.get('para') or []
                    if isinstance(body, str):
                        body = [body]
                    key = dedup_key(''.join(body))
                    if len(key) >= 8:
                        self.index.setdefault(key, (rel, idx))
                        self.exact_index.setdefault(norm_text(''.join(body)), (rel, idx))
                    elif key:
                        self.index.setdefault(
                            short_key(it.get('author'), ''.join(body)), (rel, idx))
                    t = norm_title(it.get('title') or it.get('rhythmic') or '')
                    if t:
                        self.title_index.setdefault(
                            (T2S.convert((it.get('author') or '').strip()), T2S.convert(t)),
                            []).append((rel, idx))
                    book = book_of(it) or book_of_path(rel)
                    if book and len(key) >= 8:
                        self.book_index.setdefault(book, []).append((rel, idx))
                        self.prefix_index.setdefault(key[:PREFIX_LEN], []).append((rel, idx))
        return self

    def near_dup(self, author, title, key):
        """同作者同题、正文相似度 ≥ NEAR_DUP → (rel, idx, 相似度)，否则 None。

        key 必须是 dedup_key(清洗后正文)，与 scan() 建索引、下面比库正文同一口径。
        拿原始正文的键来比，等于一边简化字一边原文，比例凭空掉一截——
        2026-10 的整体重跑就是这么把 1273 条几乎重复的条目当成新篇目的。
        """
        # 题名/作者都按简体查：库里是「王維・使至塞上」，源里是「王维 / 使至塞上」，
        # 不归一就等于两边各查各的，同一条永远碰不上面。
        a = T2S.convert((author or '').strip())
        t = T2S.convert(norm_title(title))
        cand = self.title_index.get((a, t)) or self.title_index.get((a, t.split('·')[-1]))
        if not cand:
            return None
        key = key.translate(LOOKALIKE)
        best = None
        for rel, idx in cand:
            lq = norm_text(self.body(rel, idx))
            if not lq:
                continue
            r = difflib.SequenceMatcher(None, key, lq).ratio()
            if r >= NEAR_DUP and (best is None or r > best[0]):
                best = (r, rel, idx)
        return best

    def contains_dup(self, book, key):
        """同一部书里，库里那条是否整段包住了源这条（节/章切分不同）→ (rel, idx)。

        按章或按段存的书（论语、孟子、中庸），库是一条一章、源是一条一节，
        正文天然是包含关系而不是相等关系：孟子「梁惠王上·第七节」1313 字，
        库里从「齐宣王问曰」起的两条合起来 1859 字，相似度只有 0.83，
        单看题名与相似度都认不出来，只能按「这一节是不是已经在库里」判。
        """
        if not (book and key):
            return None
        pieces = self.book_index.get(book) or []
        key = key.translate(LOOKALIKE)
        parts = [norm_text(self.body(r, i)) for r, i in pieces]
        # 一、库里那一条就整段包住了源这条
        for n, lq in enumerate(parts):
            if len(lq) >= len(key) and key in lq:
                return pieces[n]
        # 二、源这条跨了库里两条以上（节跨章）：拼整书再判，报被它盖住开头的那一条
        if len(parts) > 1 and key in ''.join(parts):
            head = key[:PREFIX_LEN]
            for n, lq in enumerate(parts):
                if lq[:len(head)] and head.startswith(lq[:min(len(head), len(lq))]):
                    return pieces[n]
        return None

    def body(self, rel, idx):
        it = self.files[rel][idx]
        return ''.join(it.get('paragraphs') or [])

    def add(self, rel, record, style='poet'):
        self.files.setdefault(rel, [])
        self.files[rel].append(record)
        self.touched.add(rel)
        if record.get('id'):
            self.ids.add(record['id'])
        key = dedup_key(''.join(record.get('paragraphs') or []))
        if len(key) >= 8:
            self.index[key] = (rel, len(self.files[rel]) - 1)
        elif key:
            self.index[short_key(record.get('author'), ''.join(record.get('paragraphs') or []))] = (
                rel, len(self.files[rel]) - 1)

# ---------------------------------------------------------------- 路由

# (朝代, 体裁) → 分片文件前缀。None 表示整文件不分片。
FIXED_TARGET = {
    ('宋', '诗'): '宋/诗/全宋诗/poet.song',
    ('唐', '诗'): '唐/诗/全唐诗/poet.tang',
    ('宋', '词'): '宋/宋词/ci.song',
    ('五代十国', '词'): '宋/宋词/ci.song',
}
SINGLE_FILE = {
    ('元', '曲'): '元/元曲/yuanqu.json',
}
YUANQU = SINGLE_FILE[('元', '曲')]
# 其余朝代按「朝代/体裁/poet.*」落位，代号与 split_dynasty.py 的 PREFIX 一致
DYNASTY_PREFIX = {
    '先秦': ('先秦/诗/poet.xianqin', '先秦/词/ci.xianqin'),
    '汉': ('汉/诗/poet.han', '汉/词/ci.han'),
    '三国': ('三国/诗/poet.sanguo', '三国/词/ci.sanguo'),
    '晋': ('晋/诗/poet.jin', '晋/词/ci.jin'),
    '南北朝': ('南北朝/诗/poet.nanbeichao', '南北朝/词/ci.nanbeichao'),
    '隋': ('隋/诗/poet.sui', '隋/词/ci.sui'),
    '唐': ('唐/诗/poet.tang', '唐/词/ci.tang'),
    '五代十国': ('五代十国/诗/poet.wudai', '五代十国/词/ci.wudai'),
    '宋': ('宋/诗/poet.song', '宋/词/ci.song'),
    '元': ('元/诗/poet.yuan', '元/词/ci.yuan'),
    '明': ('明/诗/poet.ming', '明/词/ci.ming'),
    '清': ('清/诗/poet.qing', '清/词/ci.qing'),
    '当': ('当/poet.dang.json', '当/ci.dang.json'),
}
# 没有独立目录的朝代，并入它接续的朝代
DYNASTY_ALIAS = {'辽': '宋', '金': '宋', '周': '先秦', '秦': '先秦', '商': '先秦', '上古': '先秦'}


def dynasty_index():
    """作者 → 朝代。与 split_dynasty.py 同口径：同名多行、朝代互相矛盾的判为朝代不明。"""
    path = os.path.join(ROOT, 'authors', 'authors.json')
    if not os.path.exists(path):
        return {}
    seen = {}
    for a in load_json(path):
        seen.setdefault(T2S.convert(a.get('name') or ''), set()).add(T2S.convert(a.get('dynasty') or ''))
    return {name: (next(iter(ds)) if len(ds) == 1 else None) for name, ds in seen.items()}


def route(rec, dyn_idx, lib=None):
    """→ (文件前缀, 体裁, 是否分片)"""
    dyn, kind = rec.get('dynasty'), rec.get('kind_cn')
    d = dyn_idx.get(T2S.convert((rec.get('author') or '').strip())) or T2S.convert(str(dyn or ''))
    d = DYNASTY_ALIAS.get(d, d)
    if (d, kind) in SINGLE_FILE:
        return SINGLE_FILE[(d, kind)], kind, False
    if d == '元' and kind in ('诗', '词', '文', '赋'):
        # 元人诗词曲只留《元曲》一部总集（docs/目录结构.md）
        return YUANQU, kind, False
    if (d, kind) in FIXED_TARGET:
        return FIXED_TARGET[(d, kind)], kind, True
    # 有些朝代的书是单文件（当/poet.dang.json），有的是分片（宋/诗/全宋诗/poet.song.*.json）：
    # 库里已经有 <prefix>.json 这本，就按单文件处理
    if d not in DYNASTY_PREFIX:
        raise SystemExit('朝代分不清，无法落位：%s / %s（源 dynasty=%s）' % (rec.get('author'), kind, dyn))
    # 词进 ci.*，诗/文/赋都进 poet.*
    prefix = DYNASTY_PREFIX[d][1 if kind == '词' else 0]
    if prefix.endswith('.json'):
        return prefix, kind, False
    if lib is not None and prefix + '.json' in lib.files:
        return prefix + '.json', kind, False
    return prefix, kind, True


def new_id(record, taken):
    """按 backfill_ids 的规则（作者+题名+正文+分段哈希，见该文件文档头）给新记录配 id。

    单独走一遍 assign 会重复计算全库 35 万条，这里只算这一条，撞码就换盐加长。
    """
    key = backfill_ids.work_key(record)
    for salt in range(1, 16):
        size = backfill_ids.ID_LEN + max(0, salt - 1)
        cand = backfill_ids.base22(
            backfill_ids.work_hash(key if salt == 1 else '%s|%d' % (key, salt)), size)
        if cand not in taken:
            return cand
    raise SystemExit('给不出不重复的 id：%s' % key[:40])


# ---------------------------------------------------------------- 主流程

def build_targets(lib, plan):
    """把待收条目按目标文件分组，片名接在库中现有最大序号之后。"""
    groups = {}
    for rec, target, kind, sharded in plan:
        groups.setdefault((target, sharded), []).append((rec, kind))
    # dict 保插入序；同一条目按源数据原有次序进入分组

    out = []
    for (target, sharded), items in groups.items():
        if not sharded:
            out.append((target, items))
            continue
        # 同一前缀（如 唐/诗/全唐诗/poet.tang）的片名连续编号；各书名各算各的
        rx = re.compile(re.escape(target) + r'\.(\d+)\.json$')
        used = [int(m.group(1)) for f in lib.files for m in [rx.match(f)] if m]
        # 库中片名都是 1000 的整数倍，最后一片的序号即现有条数的整千下界
        nxt = (max(used) + TARGET_SIZE) if used else 0
        for i in range(0, len(items), TARGET_SIZE):
            name = '%s.%d.json' % (target, nxt + i // TARGET_SIZE)
            out.append((name, items[i:i + TARGET_SIZE]))
    return out


def write_tsv(rows, path):
    os.makedirs(os.path.dirname(os.path.join(ROOT, path)), exist_ok=True)
    with open(os.path.join(ROOT, path), 'w', encoding='utf-8') as fp:
        fp.write('判定\t体裁\t朝代\t作者\t题名\t去向\t相似度\t正文首40字\n')
        for r in rows:
            # 源正文里有 \r\n，判定表一行一条，换行与制表符都压成空格
            fp.write('\t'.join(re.sub(r'\s+', ' ', x) for x in r) + '\n')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--apply', action='store_true', help='真正写盘（默认只预演）')
    ap.add_argument('--authors', action='store_true', help='同时写 authors/ dynasties/')
    ap.add_argument('--dynasties', action='store_true')
    ap.add_argument('--tsv', default='docs/haitang收录.tsv')
    ap.add_argument('--only', default=None, metavar='works_3',
                    help='只处理一个源文件（如 works_3），默认全部 8 个')
    ap.add_argument('--check-sources', action='store_true',
                    help='只扫全库残留的 sources: [haitang]，不改数据')
    args = ap.parse_args()

    if args.check_sources:
        stale = scan_stale_sources()
        print('残留 sources: [haitang] 共 %d 条，涉及 %d 个文件' % (sum(stale.values()), len(stale)))
        for rel, n in sorted(stale.items()):
            print('  %-46s %d' % (rel, n))
        return

    works = source._load(args.only) if args.only else source.works()
    dyn_idx = dynasty_index()
    lib = Library().scan()
    print('本库已有正文文件 %d 个，判重索引 %d 条' % (len(lib.files), len(lib.index)))

    plan, dup, dropped = [], [], []
    for rec in works:
        title = norm_title(rec.get('title'))
        text = clean_text(rec.get('content') or '')
        paras = to_paragraphs(text)
        body = ''.join(paras)
        key = dedup_key(body)
        if len(key) < 4:
            dropped.append((rec, 'too_short'))
            continue
        # 判重键与写盘正文同源：clean_text → to_paragraphs → dedup_key。
        # 拿未清洗的原文建键，源里那点注音夹注 / CRLF / 半角标点就能让「一字不差」的条目对不上。
        if len(key) >= 8:
            hit = lib.index.get(key) or lib.exact_index.get(key.translate(LOOKALIKE))
            ratio = 1.0
            if hit is None:
                near = lib.near_dup((rec.get('author') or '').strip(), rec.get('title'), key)
                if near:
                    ratio, hit = near[0], (near[1], near[2])
            if hit is None:
                # 按章分的书（论语/孟子/中庸）库里一条一章，源里一条一节，只能判包含
                hit = lib.contains_dup(book_of(rec), key)
        else:
            hit = lib.index.get(short_key(rec.get('author'), body))
            ratio = 1.0
        if hit is not None:
            dup.append((rec, hit[0], hit[1], ratio))
            continue
        target, kind, sharded = route(rec, dyn_idx, lib)
        plan.append((rec, target, kind, sharded, paras))

    print('源 %d 条 → 收 %d，判重 %d，丢弃 %d' % (len(works), len(plan), len(dup), len(dropped)))

    # 逐条判定表：判重的记去向（哪个文件的第几条）与相似度，收录的记目标文件。
    # 相似度 1.0 是正文（清洗后、去标点）逐字相同；< 1 的是靠 near_dup 判的异文。
    rows = []
    for rec, rel, idx, ratio in dup:
        rows.append(('判重', rec.get('kind_cn') or '', rec.get('dynasty') or '',
                     rec.get('author') or '', norm_title(rec.get('title')),
                     '%s#%d' % (rel, idx), '%.3f' % ratio,
                     (rec.get('content') or '')[:40].replace('\n', ' ')))
    for rec, target, kind, sharded, paras in plan:
        rows.append(('收录', kind, rec.get('dynasty') or '', rec.get('author') or '',
                     norm_title(rec.get('title')), target, '', ''.join(paras)[:40]))
    write_tsv(rows, args.tsv)
    print('逐条判定 → %s（%d 行）' % (args.tsv, len(rows)))

    targets = build_targets(lib, [(p[0], p[1], p[2], p[3]) for p in plan])
    paras_of = {id(p[0]): p[4] for p in plan}

    print('\n写入目标：')
    total = 0
    for name, items in targets:
        print('  %-42s %5d' % (name, len(items)))
        total += len(items)
    print('  合计 %d' % total)

    if not args.apply:
        print('\n预演结束。加 --apply 写盘。')
        return

    written = 0
    for name, items in targets:
        existed = os.path.exists(os.path.join(ROOT, name))
        data = lib.files.get(name, [])
        before = len(data)
        for rec, kind in items:
            paras = paras_of[id(rec)]
            title = norm_title(rec.get('title'))
            if kind == '词':
                rhythmic, sub = ci_parts(title)
                item = {'author': rec.get('author') or '', 'paragraphs': paras,
                        'rhythmic': rhythmic}
                if sub:
                    item['title'] = sub
            else:
                item = {'author': rec.get('author') or '', 'paragraphs': paras,
                        'title': title}
            if kind == '曲':
                item = {'dynasty': 'yuan', 'author': rec.get('author') or '',
                        'paragraphs': paras, 'title': title}
            item['id'] = new_id(item, lib.ids)
            lib.ids.add(item['id'])
            data.append(item)
            written += 1
        path = os.path.join(ROOT, name)
        if existed and name in lib.files:
            append_json(path, data[before:])       # 原文本不动，只追加
        else:
            rewrite_json(path, data)               # 新文件

    print('\n已写入 %d 条' % written)

    if args.authors or args.dynasties:
        write_indexes(args.authors, args.dynasties)


def scan_stale_sources():
    """全库扫「sources 里含 haitang」的记录，返回 相对路径 → 条数。"""
    SKIP = {'reference', 'scripts', 'images', '.git', '.github', '.cnb', 'loader'}
    out = {}
    for dirpath, dirs, filenames in os.walk(ROOT):
        dirs[:] = sorted(d for d in dirs if d not in SKIP and not d.startswith('.'))
        for fn in sorted(filenames):
            if not fn.endswith('.json'):
                continue
            rel = os.path.relpath(os.path.join(dirpath, fn), ROOT)
            try:
                items = json.load(open(os.path.join(dirpath, fn), encoding='utf-8'))
            except Exception:
                continue
            if not isinstance(items, list):
                continue
            n = sum(1 for it in items if isinstance(it, dict) and 'haitang' in (it.get('sources') or []))
            if n:
                out[rel] = n
    return out


def write_indexes(do_authors, do_dynasties):
    if do_authors:
        src_a = source.authors()
        out = []
        for a in src_a:
            out.append({
                'name': (a.get('name') or '').strip(),
                'dynasty': (a.get('dynasty') or '').strip(),
                'birth_year': (a.get('birth_year') or '').strip(),
                'death_year': (a.get('death_year') or '').strip(),
                'intro': re.sub(r'\s+', ' ', (a.get('intro') or '')).strip(),
            })
        out.sort(key=lambda x: (x['dynasty'], x['name']))
        write_json(os.path.join(ROOT, 'authors', 'authors.json'), out, compact=False)
        print('authors/authors.json: %d 位' % len(out))

    if do_dynasties:
        src_d = source.dynasties()
        out = []
        for d in src_d:
            out.append({
                'name': (d.get('name') or '').strip(),
                'start_year': d.get('start_year'),
                'end_year': d.get('end_year'),
                'intro': re.sub(r'\s+', ' ', (d.get('intro') or '')).strip(),
            })
        out.sort(key=lambda x: (x['start_year'] is None, x['start_year'] or 0))
        write_json(os.path.join(ROOT, 'dynasties', 'dynasties.json'), out)
        print('dynasties/dynasties.json: %d 个' % len(out))


if __name__ == '__main__':
    main()
