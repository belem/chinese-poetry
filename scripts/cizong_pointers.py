#!/usr/bin/env python3
"""《词综》与库内诗、词总集逐首对照：逐字相重的只留指针，本册不再存第二份正文。

  python3 scripts/cizong_pointers.py                 # 预演：分类、样例、条数
  python3 scripts/cizong_pointers.py --apply         # 写回：总集挂 tags、词综侧留指针、写 docs/词综去重.tsv

《词综》是清人选本，所收都是唐宋金元人现成的词，与库内总集大量重出。按 issue #295
「重复篇目只留指针」：

  * 逐字相重 → 选本这一条只留作者、词牌、题名与指向总集的 `pointer`；总集那条记录挂
    `tags: ["词综", "卷N"]`，勘误、检索都以总集为准。
  * 库里有、正文差一两个字 → 是底本讹字还是异文，本脚本不判，两存（总集不动、选本留正文），
    等逐句对勘时再定，见 docs/词综重建.md。

对照口径沿用 `scripts/merge_selections.py`：正文按 `opencc.t2s` 抹平繁简、去标点与空白后
**逐字**比较，一字不差才算重出，不做相似度容错 —— 选本与总集的异文是版本差异，不是重复。

对照范围是全库的诗、词总集：唐五代的词多只收在《全唐诗》（李白《菩萨蛮》即在
`poet.tang.*`），只看词文件会漏掉半个唐五代。`宋/诗/全宋诗/error/` 与 `小说/` 不进对照。

同一首在库里有两处（《花间集》与宋词各一条、《全唐诗》与《花间集》各一条）时两处都挂
tags，`pointer` 指第一条。明细逐条写进 docs/词综去重.tsv，可随时重跑（幂等）。
"""
import argparse
import collections
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import progress as pg  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = '汇编/词综'
TAG = '词综'
REVIEWER = 'CodeBuddy'
DOC = 'docs/词综去重.tsv'

# 对照的范围：各朝代的诗、词总集（整库扫，见文件头）
SOURCES = ('唐', '五代十国', '宋', '元', '明', '清', '当', '近现')
SKIP_DIRS = {'reference', 'scripts', 'docs', 'loader', 'rank', 'strains', 'images', '小说'}

PUNCT = re.compile(r'[，。？！；：、,.?!;:·\s“”‘’（）()「」〈〉《》—－\-…　]')
CN2INT = {c: i for i, c in enumerate('〇一二三四五六七八九')}
CN2INT['十'] = 10
for _i in range(11, 37):
    _t, _o = divmod(_i, 10)
    CN2INT[('' if _t == 1 else '〇一二三四五六七八九'[_t]) + '十'
           + ('' if not _o else '〇一二三四五六七八九'[_o])] = _i


def han(s):
    return PUNCT.sub('', s)


def render(raw, data):
    """按原文件的排版写回，只让真正加进 `tags` 的那几行出现在 diff 里。

    库里的 JSON 排版不齐（宋词 `ci.song.*` 每行尾多一个空格、全唐诗三层缩进、
    其余是 `json.dumps(indent=2)`），整份重新 dump 会把几万行的空白抹平。照
    `scripts/dedupe_songci_attr.render` 的老办法：按内容查原文件里这一行的写法，
    只出现过一种就照抄，两种都出现过就看邻居那一行带不带行尾空格。
    """
    with_blank, without_blank, prev = collections.Counter(), collections.Counter(), {}
    lines = raw.split('\n')
    for i, line in enumerate(lines):
        if not line.strip():
            continue
        key = line.rstrip(' ')
        (with_blank if line != key else without_blank)[key] += 1
        prev[key] = lines[i - 1] if i else ''
    m = re.search(r'\n( +)\S', raw)
    indent = len(m.group(1)) if m else 2
    out = (json.dumps(data, ensure_ascii=False, indent=indent)
           + ('\n' if raw.endswith('\n') else '')).split('\n')
    res = []
    for line in out:
        if not line.strip():
            res.append(line)
            continue
        key = line.rstrip(' ')
        if with_blank[key] and not without_blank[key]:
            res.append(key + ' ')
        elif without_blank[key] and not with_blank[key]:
            res.append(key)
        elif with_blank[key]:
            res.append(key + (' ' if prev.get(key, '').endswith(' ') else ''))
        else:
            # 新写入的行：`"tags": [` 不带空格，里面的字符串与收尾的 `]` 带（照老写法）
            res.append(key + (' ' if not key.rstrip().endswith('[') and key.strip() not in ('{', '}') else ''))
    return '\n'.join(res)


def load_sources():
    """→ [(路径, [记录, …])]，全库的诗、词总集。"""
    files = []
    for d in SOURCES:
        path = os.path.join(ROOT, d)
        if not os.path.isdir(path):
            continue
        for dirpath, dirs, names in os.walk(path):
            dirs[:] = sorted(x for x in dirs if x not in SKIP_DIRS and not x.startswith('.'))
            if 'error' in dirpath:
                continue                      # 上游判为有问题的记录，不进对照
            for n in sorted(names):
                if n.endswith('.json'):
                    files.append(os.path.relpath(os.path.join(dirpath, n), ROOT))
    out = []
    for rel in files:
        try:
            arr = json.load(open(os.path.join(ROOT, rel), encoding='utf-8'))
        except (json.JSONDecodeError, UnicodeDecodeError):
            continue
        if isinstance(arr, list):
            out.append((rel, arr))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--apply', action='store_true', help='写盘；否则只预演')
    ap.add_argument('--date', default='')
    args = ap.parse_args()

    try:
        from opencc import OpenCC
        t2s = OpenCC('t2s').convert
    except ImportError:
        t2s = lambda x: x

    sources = load_sources()
    index = collections.defaultdict(list)        # 正文 → [(路径, 序号)]
    for rel, arr in sources:
        for i, rec in enumerate(arr):
            if not isinstance(rec, dict) or not rec.get('paragraphs'):
                continue
            body = han(t2s(''.join(rec['paragraphs'])))
            if body:
                index[body].append((rel, i))
    print(f'对照 {len(sources)} 个文件，{sum(len(a) for _, a in sources)} 条，'
          f'正文去重后 {len(index)} 种')

    vols = sorted((f for f in os.listdir(os.path.join(ROOT, OUT)) if f.startswith('卷')),
                  key=lambda f: CN2INT.get(f[1:-5], 99))
    hits, near = [], []
    for fn in vols:
        rel = f'{OUT}/{fn}'
        for i, rec in enumerate(json.load(open(os.path.join(ROOT, rel), encoding='utf-8'))):
            body = han(t2s(''.join(rec.get('paragraphs') or [])))
            if not body:
                continue                              # 已经是指针
            where = index.get(body)
            if where:
                hits.append((rel, i, rec, where))
    n = sum(len(json.load(open(os.path.join(ROOT, OUT, f), encoding='utf-8'))) for f in vols)
    print(f'词综 {n} 首：逐字相重 {len(hits)}、库里没有或正文有出入 {n - len(hits)}')

    if not args.apply:
        for rel, i, rec, where in hits[:5]:
            print(f'  重 {rel}#{i} {rec["author"]}《{rec["title"]}》 → {where[0][0]}#{where[0][1]}')
        return

    # 1) 总集挂 tags。同一首在库里可能有多条（《花间集》与宋词两处都收），逐条挂上，
    #    免得 pointer 只指一处、另一处永远查不到选本来历
    wanted = collections.defaultdict(list)        # 路径 → [(序号, 卷次)]
    for rel, i, rec, where in hits:
        vol = (rec.get('tags') or ['', ''])[1] if len(rec.get('tags') or []) > 1 else ''
        for srel, si in where:
            wanted[srel].append((si, vol))
    for rel, items in wanted.items():
        arr = json.load(open(os.path.join(ROOT, rel), encoding='utf-8'))
        for si, vol in items:
            tags = arr[si].setdefault('tags', [])
            for t in (TAG, vol):
                if t and t not in tags:
                    tags.append(t)
        with open(os.path.join(ROOT, rel), encoding='utf-8') as fp:
            raw = fp.read()
        with open(os.path.join(ROOT, rel), 'w', encoding='utf-8') as fp:
            fp.write(render(raw, arr))
        # 这次只加了 tags、没审正文：文件已有审查结论就别动它（记录表示「最新一次审查」）
        if not pg.load_one(rel):
            pg.merge(rel, {'note': f'挂《词综》tags（{len(items)} 条），正文未改',
                           'date': args.date, 'reviewer': REVIEWER, 'status': 'needs_review'})

    # 2) 选本侧留指针
    rows = []
    for fn in vols:
        rel = f'{OUT}/{fn}'
        arr = json.load(open(os.path.join(ROOT, rel), encoding='utf-8'))
        out = []
        for rec in arr:
            body = han(t2s(''.join(rec.get('paragraphs') or [])))
            where = index.get(body) if body else None
            if where:
                srel, si = where[0]
                out.append(collections.OrderedDict([
                    ('author', rec.get('author')),
                    ('dynasty', rec.get('dynasty')),
                    ('title', rec.get('title')),
                    ('rhythmic', rec.get('rhythmic')),
                    ('pointer', f'{srel}#{si}'),
                    ('tags', rec.get('tags')),
                    ('source_line', rec.get('source_line')),
                    ('id', rec.get('id')),
                ]))
                rows.append(((rec.get('tags') or ['', ''])[1], srel, si,
                             rec.get('author'), rec.get('title')))
            else:
                out.append(rec)
        with open(os.path.join(ROOT, rel), 'w', encoding='utf-8') as fp:
            fp.write(json.dumps(out, ensure_ascii=False, indent=2))
            fp.write('\n')
    with open(os.path.join(ROOT, DOC), 'w', encoding='utf-8') as fp:
        fp.write('卷\t总集\tsharp\tauthor\ttitle\n')
        for r in rows:
            fp.write('\t'.join(str(x) for x in r) + '\n')
    print(f'→ 留指针 {len(rows)} 首，总集挂 tags {sum(len(a) for a in wanted.values())} 处，'
          f'明细见 {DOC}')


if __name__ == '__main__':
    sys.exit(main())
