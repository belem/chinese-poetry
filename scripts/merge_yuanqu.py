#!/usr/bin/env python3
"""把 元代/元曲三百首/ 并入 元代/元曲/yuanqu.json，去掉重复正文。

  python3 scripts/merge_yuanqu.py            # 预演：只打印匹配报告
  python3 scripts/merge_yuanqu.py --apply    # 写回数据，并生成 docs/元曲去重.tsv

处理方式（与 scripts/merge_anthologies.py 同一口径）：

  * 曲题 + 曲牌对得上 元代/元曲/yuanqu.json 里已有的同一首：
      - 正文一字不差 → 不重复收，选本这条删掉。
      - 曲题对得上、正文有出入 → 两存（异文是版本问题，不归这里判），记 variant。
      - 曲题对得上、正文覆盖率 < 0.9（同一组曲在库里并作一条，如寿阳曲八首）
        → 两存会留下重复的同一首，选本这条不收，记 dropped，留给对勘。
  * 元曲/ 里根本没有的（王磐、汤式等不在《全元散曲》范围内）→ 移进 元代/元曲/，
    按作者并入相邻位置；题名照库里的写法「宫调・曲牌・题」，正文随库中转成简体
    （只转字形、不改字）。

判定同一首：曲题去掉宫调前缀、间隔号与题名后，与条目题相同或互为前缀
（选本「十二月过尧民歌・别情」↔ 库中「中吕・十二月过尧民歌别情」），
再比对正文覆盖率；覆盖率 ≥ 0.9 才算对上。
"""
import argparse, collections, glob, json, os, re, unicodedata

from opencc import OpenCC

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
cc = OpenCC('t2s')

PUNCT = re.compile(r'[\s\W_]+', re.U)
TAG = re.compile(r'[\s*]')
GONGDIAO = ('黄钟', '正宫', '仙吕', '南吕', '中吕', '大石调', '小石调', '般涉调',
            '商调', '商角调', '越调', '双调')
# 同一人在两处的署名
ALIAS = {'王德信': '王实甫', '王实普': '王实甫'}


def norm(s):
    return PUNCT.sub('', cc.convert(unicodedata.normalize('NFKC', s or '')))


def author_key(a):
    a = re.sub(r'[（(][^)）]*[)）]|[《》]', '', a or '').strip()
    return ALIAS.get(a, a)


def title_key(t):
    """去掉宫调前缀、间隔号与题名，只留曲牌串，用于比对。"""
    t = TAG.sub('', cc.convert(t or ''))
    parts = [p for p in re.split(r'[・·]', t) if p and p not in GONGDIAO]
    return norm(''.join(parts))


def coverage(sel_body, full_body):
    """选本正文有多少字按顺序出现在条目里（容忍条目里的窜入文字）。"""
    pos = hit = 0
    for ch in sel_body:
        j = full_body.find(ch, pos)
        if j >= 0:
            hit += 1
            pos = j + 1
    return hit / max(len(sel_body), 1)


def load(rel):
    raw = open(os.path.join(ROOT, rel), encoding='utf-8').read()
    return json.loads(raw), raw


def dumps(rec):
    """按库中原样序列化：`,` `:` 后不带空格，`<` 不转义\u003c。"""
    return json.dumps(rec, ensure_ascii=False, separators=(',', ':')).replace('\\u003c', '<')


def save(rel, repo, original):
    """元代/元曲/yuanqu.json 是一行一条的紧凑排布（个别条目展开成多行）。
    只重写落在改动位置上的那几行，其余原样保留，免得整文件 diff。

    做法：老条目按原文行块的顺序排好，新收的条目插在「它前面那个老条目」
    的行块之后；逗号最后统一补，只有最后一个块不带。"""
    lines = original.rstrip('\n').split('\n')
    head, body, tail = lines[0], lines[1:-1], lines[-1]
    blocks = collections.defaultdict(collections.deque)   # 老条目 → 第几个行块
    chunks, block = [], []
    for line in body:
        block.append(line)
        if line.rstrip().endswith('}') or line.rstrip().endswith('},'):
            text = ''.join(x.strip() for x in block)
            rec = json.loads(text[:-1] if text.endswith(',') else text)
            blocks[(rec['author'], rec['title'], tuple(rec['paragraphs']))].append(len(chunks))
            chunks.append(block)
            block = []

    slots = collections.defaultdict(list)   # 锚点（前一个老条目的块序号）→ 新收的条目
    anchor = -1
    for rec in repo:
        key = (rec['author'], rec['title'], tuple(rec['paragraphs']))
        if blocks[key]:
            anchor = blocks[key].popleft()
        else:
            slots[anchor].append(dumps(rec))

    out = []    # (行, 是否行块收尾)
    for i, chunk in enumerate(chunks):
        out.extend((line.rstrip(), False) for line in chunk[:-1])
        out.append((chunk[-1].rstrip(), True))
        out.extend((line, True) for line in slots.get(i, []))
    out.extend((line, True) for line in slots.get(-1, []))

    # 补逗号：只补在「后面还有内容」的行块收尾行上，最后一行不带
    fixed = []
    for i, (line, is_end) in enumerate(out):
        # 行块的收尾行统一补逗号，只有最后一个不带；中间的 `{` `[` 原样不动
        if is_end:
            fixed.append(line.rstrip(',') + (',' if i < len(out) - 1 else ''))
        else:
            fixed.append(line)
    with open(os.path.join(ROOT, rel), 'w', encoding='utf-8') as fp:
        fp.write('\n'.join([head] + fixed + [tail]) + '\n')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--apply', action='store_true')
    ap.add_argument('--report', default='docs/元曲去重.tsv')
    a = ap.parse_args()

    repo, raw = load('元代/元曲/yuanqu.json')
    by_author = collections.defaultdict(list)
    for i, r in enumerate(repo):
        by_author[author_key(r['author'])].append(i)

    rows, changed, to_add, delete_files = [], [], [], []
    for f in sorted(glob.glob(os.path.join(ROOT, '元代/元曲三百首/*.json'))):
        rel = os.path.relpath(f, ROOT)
        sel = json.load(open(f, encoding='utf-8'))
        keep = []
        for rec in sel:
            body = norm(''.join(rec['paragraphs']))
            tk = title_key(rec['title'])
            best, best_cov = None, 0.0
            for i in by_author.get(author_key(rec['author']), []):
                ck = title_key(repo[i]['title'])
                if not ck or not (ck == tk or ck.startswith(tk) or tk.startswith(ck)):
                    continue
                cov = coverage(body, norm(''.join(repo[i]['paragraphs'])))
                if cov > best_cov:
                    best, best_cov = i, cov
            if best is not None:
                found = (f'元代/元曲/yuanqu.json#{best}', repo[best]['title'])
                same = body == norm(''.join(repo[best]['paragraphs']))
                if best_cov == 1.0 and same:
                    rows.append((rel, rec['title'], rec['author'], 'merged') + found + ('1.00',))
                elif best_cov == 1.0 and [cc.convert(p) for p in rec['paragraphs']] == repo[best]['paragraphs'][:len(rec['paragraphs'])]:
                    # 只差繁简字形，正文同一份：并进去，选本题挂到库中条目的 sources
                    rows.append((rel, rec['title'], rec['author'], 'merged') + found + ('1.00',))
                    if a.apply:
                        tag = f'元曲三百首／{rec["title"]}'
                        repo[best].setdefault('sources', [])
                        if tag not in repo[best]['sources']:
                            repo[best]['sources'].append(tag)
                elif best_cov >= 0.9:
                    rows.append((rel, rec['title'], rec['author'], 'variant') + found + (f'{best_cov:.2f}',))
                    keep.append(rec)
                else:
                    rows.append((rel, rec['title'], rec['author'], 'dropped') + found + (f'{best_cov:.2f}',))
                continue
            new = {'dynasty': 'yuan', 'author': rec['author'],
                   'paragraphs': [cc.convert(p) for p in rec['paragraphs']],
                   'title': cc.convert(rec['title'])}
            rows.append((rel, rec['title'], rec['author'], 'moved', '', new['title'], ''))
            to_add.append(new)
        if len(keep) != len(sel):
            changed.append((rel, len(sel), len(keep)))
            if a.apply:
                if keep:
                    json.dump(keep, open(f, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
                else:
                    delete_files.append(f)

    if a.apply:
        for f in delete_files:
            os.remove(f)
        for new in to_add:
            pos = max([i for i, r in enumerate(repo) if r['author'] == new['author']] or [len(repo)])
            repo.insert(pos + 1, new)
        save('元代/元曲/yuanqu.json', repo, raw)
        os.makedirs(os.path.join(ROOT, 'docs'), exist_ok=True)
        with open(os.path.join(ROOT, a.report), 'w', encoding='utf-8') as fp:
            fp.write('选本文件\t选本题\t作者\t判定\t本库条目\t本库题\t正文覆盖率\n')
            for r in rows:
                fp.write('\t'.join(str(x) for x in r) + '\n')

    per = collections.Counter(r[3] for r in rows)
    for k in ('merged', 'variant', 'dropped', 'moved'):
        print(f'{k:8s} {per.get(k, 0):3d}')
    for rel, n, k in changed:
        print(f'  {rel}: {n} → {k}')
    print(f'明细写入 {a.report}' if a.apply else '（预演，未写数据）')


if __name__ == '__main__':
    main()
