#!/usr/bin/env python3
"""把「正文逐字相同」的条目剔掉，一件作品只在库里留一份。

两种重复，两种处理：

  1. 与**库中原有**条目重复——新条目删掉，把它的题名挂到原条目的 `sources` 上：
     「这首也见于《乐府诗集》卷三」留住了，正文仍只有一份。
  2. 新目录**内部**重复（《垓下歌》在乐府诗集、古诗源各收一次；古文观止
     把《心術》排了两遍）——后出现的那条直接删。

判重口径：繁体转简、去标点后逐字比较，不足 8 字的不判（短句重名太多）。
「题同文异」不归这里管——那是异文，交给对勘，两存不并。

    python3 scripts/wechat_corpus/dedupe.py           # 只报数
    python3 scripts/wechat_corpus/dedupe.py --apply
"""
import argparse, collections, json, os, re, sys, unicodedata

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
# 选本目录（已按朝代分层，写全路径）
NEW_BOOKS = ['先秦/诗文总集/乐府诗集', '汉/古诗源', '唐/唐诗三百首',
             '先秦/诗文总集/昭明文选', '先秦/古文观止', '先秦/课外经典']
SKIP_DIRS = {'loader', 'strains', 'images', 'rank', 'error', 'scripts', 'docs', '.git', '.github', '.cnb'}
MIN_LEN = 8
PUNCT = re.compile(r'[\s\W_]+', re.U)


def norm(s, cc):
    return PUNCT.sub('', cc.convert(unicodedata.normalize('NFKC', s or '')))


def text_of(rec):
    return ''.join(p for p in rec.get('paragraphs') or [] if isinstance(p, str))


def add_source(root, rel, idx, tag):
    """给第 idx 条加一个 sources 项。只重写这一条，不动整个文件的排布。"""
    path = os.path.join(root, rel)
    text = open(path, encoding='utf-8').read()
    data = json.loads(text)
    rec = data[idx]
    if 'sources' in rec:
        if tag in rec['sources']:
            return False
        rec['sources'].append(tag)
    else:
        rec['sources'] = [tag]
    # 定位这一条：用 title（没有就用 paragraphs 首句）在原文里找出对象起点
    anchor = rec.get('title') or (rec.get('paragraphs') or [''])[0]
    at = text.find(json.dumps(anchor, ensure_ascii=False))
    if at < 0:
        return False
    obj_start = text.rfind('{', 0, at)
    depth, obj_end = 0, None
    for j in range(obj_start, len(text)):
        if text[j] == '{':
            depth += 1
        elif text[j] == '}':
            depth -= 1
            if depth == 0:
                obj_end = j + 1
                break
    if obj_end is None:
        return False
    indent = ' ' * (obj_start - text.rfind('\n', 0, obj_start) - 1)
    block = json.dumps(rec, ensure_ascii=False, indent=4).replace('\n', '\n' + indent)
    open(path, 'w', encoding='utf-8').write(text[:obj_start] + block + text[obj_end:])
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--root', default=ROOT)
    ap.add_argument('--report', default='docs/wechat_corpus_dedupe.tsv')
    ap.add_argument('--apply', action='store_true')
    a = ap.parse_args()
    try:
        from opencc import OpenCC
    except ImportError:
        sys.exit('pip install opencc-python-reimplemented')
    cc = OpenCC('t2s')

    # 原有条目的正文索引。新目录先不进来，否则自己先占了位
    old_index = collections.defaultdict(list)
    for dp, dirs, fnames in os.walk(a.root):
        rel = os.path.relpath(dp, a.root)
        top = '' if rel == '.' else rel.split(os.sep)[0]
        dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS and d not in NEW_BOOKS)
        for f in sorted(fnames):
            if not f.endswith('.json'):
                continue
            data = json.load(open(os.path.join(dp, f), encoding='utf-8'))
            for i, rec in enumerate(data if isinstance(data, list) else []):
                if not isinstance(rec, dict):
                    continue
                n = norm(text_of(rec), cc)
                if len(n) >= MIN_LEN:
                    old_index[n].append((os.path.join(rel, f) if rel != '.' else f,
                                         i, rec.get('sources') or []))

    # 「已占正文」集合：新目录内部不分文件，后出现的删掉；
    # 跨库的也记进来，免得同一首在 A 处挂了 sources、B 处又活下来
    alive = collections.defaultdict(dict)   # book -> {norm: 先出现的题}
    winner = {}                             # norm -> 先出现的位置（新目录或原有条目）
    rows, dropped, updated = [], 0, 0
    # 逐文件处理
    files = collections.defaultdict(list)
    for dp, dirs, fnames in os.walk(a.root):
        rel = os.path.relpath(dp, a.root)
        dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS)
        top = '' if rel == '.' else rel.replace(os.sep, '/')
        if not top:
            continue
        if top not in NEW_BOOKS:
            dirs[:] = []
            continue
        for f in sorted(fnames):
            if f.endswith('.json'):
                files[top].append((os.path.join(rel, f), os.path.join(dp, f)))
    for book in NEW_BOOKS:
        for rel, path in sorted(files.get(book, [])):
            data = json.load(open(path, encoding='utf-8'))
            if not isinstance(data, list):
                continue
            # 先跨库：与原有条目重复的，这条不进来
            kept = []
            for rec in data:
                n = norm(text_of(rec), cc)
                if len(n) < MIN_LEN:
                    kept.append(rec)
                    continue
                if n in old_index or n in winner:
                    if n not in old_index:
                        orel, oi = winner[n]
                        rows.append((rel, rec['title'], rec['author'], 'in-book-dup', orel))
                        dropped += 1
                        continue
                    orel, oi, srcs = old_index[n][0]
                    rows.append((rel, rec['title'], rec['author'], 'existing', f'{orel}#{oi}'))
                    dropped += 1
                    tag = f'{book}／{rec["title"]}'
                    if a.apply and tag not in srcs:
                        add_source(a.root, orel, oi, tag)
                        srcs.append(tag)
                        updated += 1
                    continue
                winner.setdefault(n, (rel, rec['title']))
                kept.append(rec)
            # 再目录内部：本目录里先出现的那条留下
            in_book = alive[book]
            seen_all = set(in_book) | {k for k in winner if book in (winner[k][0],)}
            final, seen_norm = [], set(seen_all)
            for rec in kept:
                n = norm(text_of(rec), cc)
                if len(n) >= MIN_LEN and n in seen_norm:
                    rows.append((rel, rec['title'], rec['author'], 'in-book-dup', in_book[n]))
                    dropped += 1
                    continue
                if len(n) >= MIN_LEN:
                    seen_norm.add(n)
                    in_book[n] = rec['title']
                    winner.setdefault(n, (rel, rec['title']))
                final.append(rec)
            if a.apply and len(final) != len(data):
                if final:
                    json.dump(final, open(path, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
                else:
                    os.remove(path)

    print(f'删除 {dropped} 条，回写 {updated} 条原有案目的 sources')
    per = collections.Counter((r[0].split(os.sep)[0], r[3]) for r in rows)
    for k, v in sorted(per.items()):
        print(f'  {k[0]:10s} {k[1]:12s} {v}')
    if a.apply:
        os.makedirs(os.path.join(a.root, os.path.dirname(a.report)), exist_ok=True)
        with open(os.path.join(a.root, a.report), 'w', encoding='utf-8') as fp:
            fp.write('新文件\t题\t作者\t判定\t本库已有\n')
            for r in rows:
                fp.write('\t'.join(str(x) for x in r) + '\n')
        print('明细写入', a.report)


if __name__ == '__main__':
    main()
