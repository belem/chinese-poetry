#!/usr/bin/env python3
"""把 reference/mit_licence_haitang（11407 条，MIT 授权）补录进本库。

路由规则（按源数据 dynasty + kind_cn）：

  宋 + 诗   → 唐代/诗/全唐诗/poet.song.*.json      （本库《全宋诗》就放在这里）
  宋 + 词   → 宋代/词/宋词/ci.song.*.json
  唐五代 + 诗/词 → 唐代/诗/全唐诗/poet.tang.*.json / 宋代/词/宋词/（五代词归 唐五代/词/五代诗词/）
  元 + 曲   → 元代/元曲/yuanqu.json
  其余（周秦汉晋南北朝隋唐文、历代诗、历代赋）→ 历代/<体裁>.json

作者小传 → authors/authors.json，朝代概述 → dynasties/dynasties.json（独立索引，
不与正文混放；本库原有 authors.tang/authors.song 各自只管一个总集，字段还不同）。

清洗（源数据是数字出版转码，乱码一律不猜）：
  PUA 私用区、无上下文的西里尔/希腊/假名 → □（本库表示底本缺字）
  ── → 中文破折号；\r\n → 单行一句；行首行尾空白清掉；空行去掉
  FIXED 表只收上下文 100% 确定的定点还原，其余一律 □

判重按正文（简繁统一 + 去标点），命中库中已有条目的不重收，只把来源题名挂到
原条目的 sources 上。

用法：
  python3 scripts/haitang/import.py                  # 预演，打印清单
  python3 scripts/haitang/import.py --apply           # 写盘
  python3 scripts/haitang/import.py --apply --authors --dynasties
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

ROOT = source.ROOT
T2S = OpenCC('t2s')
S2T = OpenCC('s2t')

FREE_KINDS = {'诗', '词', '文', '赋'}
TARGET_SIZE = 1000          # 与库中 poet.*.json / ci.song.*.json 一致

# 同作者同题时，正文相似度达到此值视为同一作品（异文），只挂 sources 不重收。
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


def append_json(path, new_items):
    """在既有文件末尾追加条目，原有文本一字不动（只补分隔逗号与结尾括号）。"""
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
    sep = ',\n'
    add = sep.join(json.dumps(it, ensure_ascii=False, separators=(',', ':')) for it in new_items)
    with open(path, 'w', encoding='utf-8') as fp:
        fp.write(body + sep + add + '\n]\n')


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
        key = dedup_key(''.join(record.get('paragraphs') or []))
        if len(key) >= 8:
            self.index[key] = (rel, len(self.files[rel]) - 1)
        elif key:
            self.index[short_key(record.get('author'), ''.join(record.get('paragraphs') or []))] = (
                rel, len(self.files[rel]) - 1)

    def attach_source(self, rel, idx, title):
        it = self.files[rel][idx]
        src = it.setdefault('sources', [])
        if title not in src:
            src.append(title)


# ---------------------------------------------------------------- 路由

# (朝代, 体裁) → 分片文件前缀。None 表示整文件不分片。
FIXED_TARGET = {
    ('宋', '诗'): '唐代/诗/全唐诗/poet.song',
    ('唐', '诗'): '唐代/诗/全唐诗/poet.tang',
    ('宋', '词'): '宋代/词/宋词/ci.song',
    ('五代十国', '词'): '宋代/词/宋词/ci.song',
}
SINGLE_FILE = {
    ('元', '曲'): '元代/元曲/yuanqu.json',
}
# 历代/ 下按体裁分文件，各自从 0 起编
FREE_PREFIX = {
    '诗': '历代/poet',
    '词': '历代/ci',
    '文': '历代/wen',
    '赋': '历代/fu',
}


def route(rec):
    """→ (文件前缀 或 单一文件路径, 体裁, 是否为分片)"""
    dyn, kind = rec.get('dynasty'), rec.get('kind_cn')
    if (dyn, kind) in SINGLE_FILE:
        return SINGLE_FILE[(dyn, kind)], kind, False
    if (dyn, kind) in FIXED_TARGET:
        return FIXED_TARGET[(dyn, kind)], kind, True
    # 其余（周秦汉晋南北朝隋唐文、历代诗、历代赋）按体裁进 历代/
    return FREE_PREFIX.get(kind, '历代/other'), kind, True


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
        # 同一前缀（如 唐代/诗/全唐诗/poet.tang）的片名连续编号；同目录的 poet.song 各算各的
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
            fp.write('\t'.join(x.replace('\t', ' ').replace('\n', ' ')
                              for x in r) + '\n')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--apply', action='store_true', help='真正写盘（默认只预演）')
    ap.add_argument('--authors', action='store_true', help='同时写 authors/ dynasties/')
    ap.add_argument('--dynasties', action='store_true')
    ap.add_argument('--tsv', default='docs/haitang收录.tsv')
    args = ap.parse_args()

    works = source.works()
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
        target, kind, sharded = route(rec)
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

    # 挂 sources
    for rec, rel, idx in dup:
        lib.attach_source(rel, idx, norm_title(rec.get('title')))

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
            item['sources'] = ['haitang']
            data.append(item)
            written += 1
        path = os.path.join(ROOT, name)
        if existed and name in lib.files:
            append_json(path, data[before:])       # 原文本不动，只追加
        else:
            rewrite_json(path, data)               # 新文件

    # 只挂了 sources 的文件也要回写
    for rel in sorted(lib.touched):
        if rel in lib.files and not any(n == rel for n, _ in targets):
            rewrite_json(os.path.join(ROOT, rel), lib.files[rel])

    print('\n已写入 %d 条' % written)

    if args.authors or args.dynasties:
        write_indexes(args.authors, args.dynasties)


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
