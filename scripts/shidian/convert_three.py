#!/usr/bin/env python3
"""识典抓取的三部笔记/小说 → 库内记录，并用全库口径分配 id。

  python3 convert_three.py <raw.json> <out.json> --book liaozhai|taoan|fusheng

口径与 scripts/backfill_ids.py 一致：id = base22(blake2b(作者|题名|正文|分段))，
全库唯一，撞码换盐。所以先把库内每一条的 key 算出来、按 key 排序分配一遍，
再给新记录续号，保证新条目的 id 与重跑 backfill_ids.py 的结果一致。
"""
import argparse, hashlib, json, os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ALPHABET = '0123456789abcdefghijklmnopqrstuvwxyz'
ID_LEN = 6
SKIP = {'author', 'rank', 'settings', '表面结构字', 'error', 'fix_progress'}
SKIP_DIRS = {'loader', 'strains', 'images', 'rank', 'error', 'scripts', 'docs', '.git', '.claude',
             '.github', '.cnb', 'reference'}


def base22(digest, n):
    v = int.from_bytes(digest, 'big'); out = []
    for _ in range(n):
        v, r = divmod(v, 22); out.append(ALPHABET[r])
    return ''.join(out)


def work_hash(key):
    return hashlib.blake2b(key.encode(), digest_size=16).digest()


def line_hash(body):
    return hashlib.blake2b('\x00'.join(body).encode(), digest_size=8).hexdigest()


def body_of(rec):
    b = rec.get('paragraphs') or rec.get('content') or rec.get('para') or []
    if isinstance(b, str):
        b = [b]
    return [x for x in b if isinstance(x, str)]


def work_key(rec):
    title = rec.get('title') or rec.get('rhythmic') or ''
    b = body_of(rec)
    return f"{rec.get('author') or ''}|{title}|{''.join(b)}|{line_hash(b)}"


def norm(s):
    return re.sub(r'\s+', '', s or '')


# ---------------------------------------------------------------- 切分规则

class Liaozhai:
    """青柯亭本（XYXLZZY）：一页一篇，篇名在页面 h3。卷首页 name 形如「聊齋誌異卷一」。"""
    author = '蒲松龄'
    skip = re.compile(r'^(聊齋誌異?目[次錄]|聊齋誌異?卷|序$|跋$|后跋|題詞|續題|聊齋志異題詞)')
    head = re.compile(r'^般陽蒲松|^淄川蒲|^新城王士正|^聊齋誌異$')

    def title(self, sub, vol):
        return f'聊斋志异·卷{vol}·{sub}'

    def clean(self, ps):
        out = []
        for p in ps:
            t = (p or '').strip()
            n = norm(t)
            if norm(t) and self.head.match(n):
                continue
            if len(n) > 3:
                out.append(t)
        return out

    def volume(self, name):
        m = re.search(r'聊齋誌異卷之?([一二三四五六七八九十]+)', norm(name))
        return m.group(1) if m else None


class Taoan:
    """粤雅堂本《陶庵梦忆》（CYYT015）：一页一篇，篇名在 h3；卷首页是「第N卷」。"""
    author = '张岱'
    skip = re.compile(r'^(第[一二三四五六七八九十]+卷|陶菴夢憶[卷跋序]|序$|跋$|自序)')
    head = re.compile(r'^山陰張岱宗子撰')

    def title(self, sub, vol):
        return f'陶庵梦忆·卷{vol}·{sub}'

    def clean(self, ps):
        return [p.strip() for p in ps if len(norm(p)) > 3 and not self.head.match(norm(p))]

    def volume(self, name):
        m = re.search(r'^第([一二三四五六七八九十]+)卷', norm(name))
        return m.group(1) if m else None


CN = '〇一二三四五六七八九十'


class Fusheng:
    """《浮生六记》（中央書局本）：一卷一页，name 形如「卷一 閨房記樂」。"""
    author = '沈复'
    name_rx = re.compile(r'^卷([一二三四五六七八九十]+)\s*(.*)$')

    def records(self, raw):
        out = []
        for v in sorted(raw.values(), key=lambda x: x['index']):
            m = self.name_rx.match(norm(v['name']))
            if not m:
                continue                        # 卷首（题词、序、跋、目次）不进正文
            num, head = m.group(1), m.group(2)
            body = [p.strip() for p in v['paragraphs'] if len(norm(p)) > 3]
            if body in ([], ['缺。']):
                continue                        # 卷五、卷六 底本即「缺」
            body = [p for p in body if norm(p) != '缺。']
            out.append({'author': self.author, 'title': f'浮生六记·卷{num}·{head}', 'paragraphs': body})
        return out


def build(book, raw):
    cls = {'liaozhai': Liaozhai, 'taoan': Taoan, 'fusheng': Fusheng}[book]()
    if isinstance(cls, Fusheng):
        return cls.records(raw)
    out, vol = [], ''
    for v in sorted(raw.values(), key=lambda x: x['index']):
        name = norm(v.get('name') or '')
        sub = norm(v.get('subtitle') or '')
        got = cls.volume(name)
        if got:
            vol = got
        if not sub or cls.skip.match(sub):
            continue
        body = cls.clean(v['paragraphs'])
        if not body:
            continue
        out.append({'author': cls.author, 'title': cls.title(sub, vol), 'paragraphs': body})
    return out


# ---------------------------------------------------------------- 全库 id

def library_keys():
    keys = set()
    for dirpath, dirs, files in os.walk(ROOT):
        dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS)
        for f in sorted(files):
            if not f.endswith('.json') or any(s in f for s in SKIP):
                continue
            rel = os.path.join(dirpath, f)
            try:
                arr = json.load(open(rel, encoding='utf-8'))
            except Exception:
                continue
            if not isinstance(arr, list):
                continue
            for r in arr:
                if isinstance(r, dict) and any(k in r for k in ('paragraphs', 'content', 'chapter', 'para')):
                    keys.add(work_key(r))
    return keys


def assign(new_keys, lib):
    """库内 key 先按排序占号，新 key 接着排；返回 {key: id}。"""
    taken, ids = set(), {}

    def place(k):
        for salt in range(1, 16):
            size = ID_LEN + max(0, salt - 1)
            cand = base22(work_hash(k if salt == 1 else f'{k}|{salt}'), size)
            if cand not in taken:
                taken.add(cand); ids[k] = cand; return

    for k in sorted(lib):
        place(k)
    for k in sorted(new_keys):
        if k not in ids:
            place(k)
    return ids


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('raw'); ap.add_argument('out')
    ap.add_argument('--book', required=True, choices=['liaozhai', 'taoan', 'fusheng'])
    a = ap.parse_args()
    raw = json.load(open(a.raw, encoding='utf-8'))
    recs = build(a.book, raw)
    lib = library_keys()
    keys = [work_key(r) for r in recs]
    clash = [r['title'] for r, k in zip(recs, keys) if k in lib]
    ids = assign(keys, lib)
    for r, k in zip(recs, keys):
        r['id'] = ids[k]
    with open(a.out, 'w', encoding='utf-8') as fp:
        json.dump(recs, fp, ensure_ascii=False, indent=2)
        fp.write('\n')
    chars = sum(len(''.join(r['paragraphs'])) for r in recs)
    print(f'{a.out}: {len(recs)} 篇 {chars} 字；与库内重复 {len(clash)} 条')
    for t in clash[:10]:
        print('   dup:', t)


if __name__ == '__main__':
    main()
