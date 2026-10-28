#!/usr/bin/env python3
"""给篇目补 id，并把现有 uuid 换成短 id。

  python3 scripts/backfill_ids.py            # 预演：打印统计，不写文件
  python3 scripts/backfill_ids.py --apply    # 写回数据
  python3 scripts/backfill_ids.py --apply --out docs/id迁移.tsv   # 另存迁移明细

id 规则：

  1. 6 字符，字母表 0-9a-z（base22，不用易混的 u/v）。
  2. 由「作者 + 题名 + 正文」哈希得来，与文件、顺序无关：同一首诗永远是同一个 id，
     搬目录、重排、重新分片都不变号；正文改了就是另一首，换号。
     只按正文不够——全宋诗里「上丞相壽　其一/其三/其五」整首正文都是「(残缺)。」；
     只按题名也不够——同一首在两部书里题名常差一个「二首」「其一」。
  3. 全库唯一。351083 条篇目里 350905 个「作者+题名+正文」互不相同，
     重出的（唐诗三百首 168 组三元组、唐词与全唐诗重复收录等）共用号；
     剩下的按出现次序拆开。撞码的换盐、加长到 7~9 位重算，
     写入前用集合验一遍，不靠概率。
  4. 记录自带的 uuid 一并换成短 id：id 是记录身份，不是内容指纹，换格式不必保留旧值。

uuid 是 36 字符，6 字符是它的 1/6：32.3 万个 id 换掉，正文不动，约省 9.7 MB。
"""
import argparse
import collections
import hashlib
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKIP = {'author', 'rank', 'settings', '表面结构字', 'error', 'fix_progress'}
SKIP_DIRS = {'loader', 'strains', 'images', 'rank', 'error', 'scripts', 'docs', '.git', '.claude', '.github',
             '.cnb', 'reference'}
ALPHABET = '0123456789abcdefghijklmnopqrstuvwxyz'   # 22
ID_LEN = 6
UUID = re.compile(r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$')


def iter_files():
    for dirpath, dirs, filenames in os.walk(ROOT):
        dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS)
        for f in sorted(filenames):
            if f.endswith('.json') and not any(s in f for s in SKIP):
                yield os.path.relpath(os.path.join(dirpath, f), ROOT)


def base22(digest, n):
    v = int.from_bytes(digest, 'big')
    out = []
    for _ in range(n):
        v, r = divmod(v, 22)
        out.append(ALPHABET[r])
    return ''.join(out)


def work_hash(key):
    return hashlib.blake2b(key.encode(), digest_size=16).digest()


def line_hash(body):
    """正文按段切分的指纹。同一首的两种排法（词四句 vs 诗四联）全文串一样，靠它分开。"""
    return hashlib.blake2b('\x00'.join(body).encode(), digest_size=8).hexdigest()


def work_key(rec):
    """作者 + 题名 + 正文 + 分段，见文件头第 2 条。"""
    body = rec.get('paragraphs') or rec.get('content') or rec.get('para') or []
    if isinstance(body, str):
        body = [body]
    body = [x for x in body if isinstance(x, str)]
    title = rec.get('title') or rec.get('rhythmic') or ''
    return f"{rec.get('author') or ''}|{title}|{''.join(body)}|{line_hash(body)}"


def assign(keys):
    """keys: 每条的 key（重出的篇目已按出现次序拆开）。返回 {key: id}。"""
    taken = set()
    out = {}
    for key in sorted(set(keys)):
        for salt in range(1, 16):
            size = ID_LEN + max(0, salt - 1)
            cand = base22(work_hash(key if salt == 1 else f'{key}|{salt}'), size)
            if cand not in taken:
                out[key] = cand
                taken.add(cand)
                break
        else:
            sys.exit(f'key {key[:30]!r} 找不到不重复的 id')
    return out


TRAILING = re.compile(r'[ \t]+$')


def shape(line):
    """把一行归一成行型：开括号 / 闭括号 / 带逗号的值 / 末值 / 其他。"""
    st = line.strip()
    if st in ('[', '{'):
        return 'open'
    if st in (']', '}'):
        return 'close'
    if st.endswith(','):
        return 'comma'
    return 'value'


def dump(rel, arr):
    """写回时保留原文件的行尾空格（上游不少文件每行末尾带一个空格）。

    只看「新写出的这一行对应得上旧行」的情况做不到（行数变了），
    改用整体判断：旧文件多数行带尾空格，新文件就按同一格式补。
    这样 diff 里只有 id 的新增与替换，不会因为重新排版整片变色。
    """
    path = os.path.join(ROOT, rel)
    with open(path, encoding='utf-8') as fp:
        before = fp.read().split('\n')
    # 每种行型在旧文件里带不带尾空格，逐型统计后照抄：上游的尾空格只加在
    # 「带逗号的值行」「], 」「},」上，"[" 与 "{" 不带
    style = collections.defaultdict(collections.Counter)
    for line in before:
        style[shape(line)][TRAILING.search(line) is not None] += 1
    trailing = {k: v[True] > v[False] for k, v in style.items()}
    lines = json.dumps(arr, ensure_ascii=False, indent=2).split('\n')
    lines = [line + ' ' if trailing.get(shape(line), False) else line for line in lines]
    with open(path, 'w', encoding='utf-8') as fp:
        fp.write('\n'.join(lines) + '\n')


def is_poem(rec):
    return any(k in rec for k in ('paragraphs', 'content', 'chapter', 'para'))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--apply', action='store_true', help='写回数据文件')
    ap.add_argument('--out', help='迁移明细 TSV 路径（可选，35 万行约 17 MB）')
    args = ap.parse_args()

    data, records = {}, []
    for rel in iter_files():
        with open(os.path.join(ROOT, rel), encoding='utf-8') as fp:
            try:
                arr = json.load(fp)
            except json.JSONDecodeError:
                continue
        if not isinstance(arr, list):
            continue
        data[rel] = arr
        for idx, rec in enumerate(arr):
            if isinstance(rec, dict) and is_poem(rec):
                records.append((rel, idx, rec))

    # 同一 key 出现多次时按次序加后缀拆开，保证一条记录一个 id
    raw = [work_key(rec) for _, _, rec in records]
    count = collections.Counter(raw)
    keys = [k if count[k] == 1 else f'{k}|#{j}' for j, k in enumerate(raw)]
    assert len(set(keys)) == len(keys)
    id_of = assign(keys)

    added = converted = kept = 0
    rows = []
    for (rel, idx, rec), key in zip(records, keys):
        old = rec.get('id')
        new = id_of[key]
        if isinstance(old, str) and old and not UUID.match(old):
            continue                          # 已经是短 id：不动，重跑结果与上次一致
        if old:
            converted += 1
        else:
            added += 1
        rec['id'] = new
        if args.apply and args.out:
            rows.append([rel, idx, old or '', new])

    ids = [r['id'] for _, _, r in records]
    assert len(set(ids)) == len(ids), 'id 有重复'
    lens = collections.Counter(map(len, ids))
    print(f'篇目 {len(records)} 条：补 id {added}，uuid 换短 id {converted}，已是短 id {kept}')
    print(f'id 唯一 {len(set(ids))} 个 / {len(ids)} 条；长度分布 {dict(sorted(lens.items()))}')

    if not args.apply:
        print('预演结束，未写文件。加 --apply 写回。')
        return

    for rel, arr in data.items():
        if not any(isinstance(r, dict) and 'id' in r for r in arr):
            continue
        dump(rel, arr)
    if args.out:
        out = os.path.join(ROOT, args.out)
        os.makedirs(os.path.dirname(out), exist_ok=True)
        with open(out, 'w', encoding='utf-8') as fp:
            fp.write('file\tindex\told\tnew\n')
            for row in rows:
                fp.write('\t'.join(str(x) for x in row) + '\n')
        print(f'迁移明细 {len(rows)} 行 → {args.out}')
    print('写回完成')


if __name__ == '__main__':
    main()
