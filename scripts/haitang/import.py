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

判重按正文（简繁统一 + 去标点），命中库中已有条目的不重收。来源是到处收集的语料，
不挂 sources 标记——sources 只留给唐诗三百首这类权威合集。

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


def dedup_key(text):
    """判重键：繁→简、去标点空白。"""
    s = T2S.convert(text)
    s = ''.join(ch for ch in s if unicodedata.category(ch)[0] in 'LN')
    return s


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
                    elif key:
                        self.index.setdefault(
                            short_key(it.get('author'), ''.join(body)), (rel, idx))
                    t = norm_title(it.get('title') or it.get('rhythmic') or '')
                    if t:
                        self.title_index.setdefault(
                            ((it.get('author') or '').strip(), t), []).append((rel, idx))
        return self

    def near_dup(self, author, title, key):
        """同作者同题、正文相似度 ≥ NEAR_DUP → 库中那条 (rel, idx)，否则 None。"""
        t = norm_title(title)
        cand = self.title_index.get((author, t)) or self.title_index.get((author, t.split('·')[-1]))
        if not cand:
            return None
        best = None
        for rel, idx in cand:
            lq = dedup_key(self.body(rel, idx))
            if not lq:
                continue
            r = difflib.SequenceMatcher(None, key, lq).ratio()
            if r >= NEAR_DUP and (best is None or r > best[0]):
                best = (r, rel, idx)
        return (best[1], best[2]) if best else None

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
        fp.write('判定\t体裁\t朝代\t作者\t题名\t去向\t正文首40字\n')
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
        if len(key) >= 8:
            hit = lib.index.get(key)
            if hit is None:
                hit = lib.near_dup((rec.get('author') or '').strip(), rec.get('title'), key)
        else:
            hit = lib.index.get(short_key(rec.get('author'), body))
        if hit is not None:
            dup.append((rec, hit[0], hit[1]))
            continue
        target, kind, sharded = route(rec, dyn_idx, lib)
        plan.append((rec, target, kind, sharded, paras))

    print('源 %d 条 → 收 %d，判重 %d，丢弃 %d' % (len(works), len(plan), len(dup), len(dropped)))

    # 逐条判定表：判重的记去向（哪个文件的第几条），收录的记目标文件
    rows = []
    for rec, rel, idx in dup:
        rows.append(('判重', rec.get('kind_cn') or '', rec.get('dynasty') or '',
                     rec.get('author') or '', norm_title(rec.get('title')),
                     '%s#%d' % (rel, idx),
                     (rec.get('content') or '')[:40].replace('\n', ' ')))
    for rec, target, kind, sharded, paras in plan:
        rows.append(('收录', kind, rec.get('dynasty') or '', rec.get('author') or '',
                     norm_title(rec.get('title')), target, ''.join(paras)[:40]))
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
