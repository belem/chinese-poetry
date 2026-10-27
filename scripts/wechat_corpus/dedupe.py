#!/usr/bin/env python3
"""把「正文逐字相同」的条目从新补的 7 部里剔掉，一件作品只在库里留一份。

两种重复，两种处理：

  1. 新目录内部重复（乐府诗集与古诗源都收了《垓下歌》，古文观止又把《心術》
     排了两遍）——后出现的那条直接删，信息不丢。
  2. 与库中原有条目重复——新条目删掉，把它的题名追加到原条目的 `sources`，
     这样「这首诗也见于《乐府诗集》卷三」这条信息留下来了，正文仍只有一份。

判重口径：繁体转简体、去掉标点空白后逐字比较；不足 8 字的不判（短句重名太多）。
不处理「题同文异」——那是异文，属于对勘的活儿，不是去重。

    python3 scripts/wechat_corpus/dedupe.py --dry-run     # 只报数
    python3 scripts/wechat_corpus/dedupe.py --apply
"""
import argparse, collections, json, os, re, sys, unicodedata

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
NEW_BOOKS = ['乐府诗集', '古诗源', '唐诗三百首', '元曲三百首', '文选', '古文观止', '课外经典']
SKIP_DIRS = {'loader', 'strains', 'images', 'rank', 'error', 'scripts', 'docs', '.git', '.github'}
MIN_LEN = 8
PUNCT = re.compile(r'[\s\W_]+', re.U)


def norm(s, cc):
    return PUNCT.sub('', cc.convert(unicodedata.normalize('NFKC', s or '')))


def book_of(rel):
    return rel.split(os.sep)[0]


def repo_files(root, only_new):
    for dp, dirs, files in os.walk(root):
        rel_dir = os.path.relpath(dp, root)
        top = '' if rel_dir == '.' else rel_dir.split(os.sep)[0]
        # 根目录要放行，好走到那 7 个目录里去
        if only_new and top and top not in NEW_BOOKS:
            dirs[:] = []
            continue
        dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS)
        for f in sorted(files):
            if f.endswith('.json'):
                yield os.path.relpath(os.path.join(dp, f), root)


def add_source(root, rel, idx, tag):
    """给第 idx 条加一个 sources 项。就地改文本，不动文件里原有的缩进排布。"""
    path = os.path.join(root, rel)
    text = open(path, encoding='utf-8').read()
    data = json.loads(text)
    rec = data[idx]
    if 'sources' in rec:
        rec['sources'].append(tag)
        new = json.dumps(rec, ensure_ascii=False, indent=4)
        # 用整条替换，只动这一条
        old_txt = json.dumps(rec, ensure_ascii=False, indent=4)
    else:
        rec['sources'] = [tag]
        new = json.dumps(rec, ensure_ascii=False, indent=4)
    # 精确定位这一条在原文中的片段：先找它的 title 行起点，再整体替换解析后的对象
    start = text.find(json.dumps(data[idx].get('title'), ensure_ascii=False))
    # 回退到对象起始 '{'
    obj_start = text.rfind('{', 0, start)
    # 找到匹配的收尾 '}'
    depth = 0
    for j in range(obj_start, len(text)):
        if text[j] == '{':
            depth += 1
        elif text[j] == '}':
            depth -= 1
            if depth == 0:
                obj_end = j + 1
                break
    indent = ' ' * (obj_start - text.rfind('\n', 0, obj_start) - 1)
    block = json.dumps(rec, ensure_ascii=False, indent=4).replace('\n', '\n' + indent)
    open(path, 'w', encoding='utf-8').write(text[:obj_start] + block + text[obj_end:])


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

    rows = []
    dropped = updated = 0
    # 原有条目的正文索引：norm -> (rel, index)
    old_index = collections.defaultdict(list)
    for rel in repo_files(a.root, only_new=False):
        if book_of(rel) in NEW_BOOKS:
            continue
        data = json.load(open(os.path.join(a.root, rel), encoding='utf-8'))
        for i, rec in enumerate(data if isinstance(data, list) else []):
            n = norm(''.join(rec.get('paragraphs') or []), cc)
            if len(n) >= MIN_LEN:
                old_index[n].append((rel, i, rec.get('sources') or []))

    for rel in repo_files(a.root, only_new=True):
        path = os.path.join(a.root, rel)
        data = json.load(open(path, encoding='utf-8'))
        if not isinstance(data, list):
            continue
        seen, kept = {}, []
        for rec in data:
            n = norm(''.join(rec.get('paragraphs') or []), cc)
            if len(n) < MIN_LEN:
                kept.append(rec)
                continue
            if n in seen:
                rows.append((rel, rec['title'], rec['author'], 'in-book-dup', seen[n]))
                dropped += 1
                continue
            if n in old_index:
                orel, oi = old_index[n][0][:2]
                rows.append((rel, rec['title'], rec['author'], 'existing', f'{orel}#{oi}'))
                dropped += 1
                if a.apply:
                    tag = f'{book_of(rel)}／{rec["title"]}'
                    if tag not in old_index[n][0][2]:
                        add_source(a.root, orel, oi, tag)
                        updated += 1
                continue
            seen[n] = rec['title']
            kept.append(rec)
        if a.apply and len(kept) != len(data):
            if kept:
                json.dump(kept, open(path, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
            else:
                os.remove(path)

    print(f'删除 {dropped} 条（内部重复 + 与原有重复），回写 {updated} 条原有案目的 sources')
    per = collections.Counter((r[0].split(os.sep)[0], r[3]) for r in rows)
    for k, v in sorted(per.items()):
        print(f'  {k[0]:10s} {k[1]:12s} {v}')
    if a.apply:
        os.makedirs(os.path.dirname(os.path.join(a.root, a.report)), exist_ok=True)
        with open(os.path.join(a.root, a.report), 'w', encoding='utf-8') as fp:
            fp.write('新文件\t题\t作者\t判定\t本库已有\n')
            for r in rows:
                fp.write('\t'.join(str(x) for x in r) + '\n')
        print('明细写入', a.report)


if __name__ == '__main__':
    main()
