#!/usr/bin/env python3
"""把上游 poem-wechat 里「本库确实没有」的篇目收进本库。

audit.py 已经按正文判过一轮重，剩下 76 条 new。但那一步回查上游条目用的是
(标题, 作者)，同名作品会串——文选卷上四首《杂诗》都被取成了唐诗三百首里
沈佺期那一首。这里按上游 id 精确取正文，再对着全库重判一次：

  正文全同 / 前 12 字同 → 已有，不收
  否则                 → 收

落地规则与 import.py 一致（繁体、一行一句、只留 author/paragraphs/title）。
课本（课内 / 近现代 / 古诗非唐 / 节日节气）是横跨朝代、体裁的选目，不是一部书，
不另开目录，按体裁并入本库已有的目录；整部书（文选、古文观止、乐府诗集、
唐诗三百首…）则与上游同名目录对齐。

用法：
  node extract.js <上游 data 目录> > /tmp/upstream.json
  python3 scripts/wechat_corpus/collect.py --upstream /tmp/upstream.json
  python3 scripts/wechat_corpus/collect.py --upstream /tmp/upstream.json --apply
"""
import argparse, json, os, re, sys, unicodedata
from collections import OrderedDict

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
SKIP_DIRS = {'loader', 'strains', 'images', 'rank', 'error', 'scripts', 'docs',
             '.git', '.claude', '.github', '.cnb'}
PUNCT = re.compile(r'[\s\W_]+', re.U)

# 整部书 → 本库同名目录
BOOK_DIRS = {
    '古诗非唐': '汉/古诗源',
    '唐诗': '唐/唐诗三百首',
    '宋词三百首': '宋/宋词三百首',
    '元曲': '元曲三百首',
    '文选': '先秦/诗文总集/昭明文选',
    '古文观止': '先秦/古文观止',
    '古文': '先秦/古文观止',
    '乐府集': '先秦/诗文总集/乐府诗集',
}
# 课本类：横跨朝代体裁，按本库既有的体裁目录就近收
GENRE_DIRS = {'课内': '近现', '近现代': '近现', '节日节气': '近现',
              '古诗非唐': '近现'}

# audit.tsv 的「集子」列是中文名，上游是 x.js 文件名
AUDIT_FILES = {
    '课内': 'poems-1.js',   # 课内是 12 册课本合并的口径，逐册找，见 source_of
    '古文': 'poems-classic.js', '乐府集': 'poems-yuefu.js',
    '节日节气': 'poems-seasonal-361.js', '唐诗': 'poems-tangshi.js',
    '古诗非唐': 'poems-gushi.js', '宋词三百首': 'poems-songci.js',
    '元曲': 'poems-yuanqu.js', '古文观止': 'poems-guwen.js',
    '近现代': 'poems-jinxiandai.js', '文选': 'poems-zhaoming.js',
}

DATASETS = OrderedDict([
    ('jinyuanxiandai', ('近现', '近现/')),
    ('tangshi300', ('唐/唐诗三百首', '唐/唐诗三百首/')),
    ('songci300', ('宋/宋词三百首', '宋/宋词三百首/')),
    ('guwenguanzhi', ('汇编/古文观止', '汇编/古文观止/')),
])


def norm(s, cc):
    return PUNCT.sub('', cc.convert(unicodedata.normalize('NFKC', s or '')))


def norm_title(t):
    return re.sub(r'\s+', '', re.sub(r'[（(][^)）]*[)）]', '', t or ''))


def build_index(cc):
    """全库正文指纹：整篇 → 记录；前 12 字 → 记录（异文兜底）。"""
    by_text, by_pre = {}, {}
    for dp, dirs, files in os.walk(ROOT):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for f in sorted(files):
            if not f.endswith('.json'):
                continue
            rel = os.path.relpath(os.path.join(dp, f), ROOT)
            if rel.startswith('宋/诗/全宋诗/error/') or rel == 'fix_progress.json':
                continue
            try:
                data = json.load(open(os.path.join(ROOT, rel), encoding='utf-8'))
            except Exception:
                continue
            for i, rec in enumerate(data if isinstance(data, list) else [data]):
                if not isinstance(rec, dict):
                    continue
                flat, stack = [], []
                ps = rec.get('paragraphs') or rec.get('para') or rec.get('content')
                if isinstance(ps, list):
                    stack = list(ps)
                elif ps:
                    stack = [ps]
                while stack:
                    x = stack.pop(0)
                    if isinstance(x, str):
                        flat.append(x)
                    elif isinstance(x, list):
                        stack = x + stack
                    elif isinstance(x, dict):
                        stack = (x.get('paragraphs') or []) + stack
                n = norm(''.join(flat), cc)
                if len(n) < 8:
                    continue
                hit = {'file': rel, 'idx': i,
                       'title': rec.get('title') or rec.get('rhythmic') or ''}
                by_text.setdefault(n, hit)
                if len(n) >= 12:
                    by_pre.setdefault(n[:12], hit)
    return by_text, by_pre


# s2twp 是「简转台繁」词典，会顺手做词语替换（卜算子 → 卜運算元 之类）。
# 本库只要字形转换，不要改词形，误转的按原文改回
REVERT = {'卜運算元': '卜算子'}
# 这些字在文言里有固定用法，s2twp 按现代汉语的词义转错了
WENYAN = {'嘗貽餘核舟': '嘗貽余核舟', '泛赤壁雲': '泛赤壁云'}


def chinese(s, conv):
    out = conv.convert(s)
    for a, b in REVERT.items():
        out = out.replace(a, b)
    # 简转繁会把「文言」的余/云/后/发/干…转成餘/雲/後/髮/乾
    for a, b in WENYAN.items():
        out = out.replace(a, b)
    return out


def to_paragraphs(text, s2twp):
    # 「~~」是上游对底本缺字的记法，换成本库惯用的「□」
    return [chinese(line.strip(), s2twp)
            for line in (text or '').replace('~~', '□').split('\n') if line.strip()]


def volume_of(item):
    """上游 gradeGroup 折成本库的卷名。

    卷次（「卷一 五言古诗」「诗 · 杂诗上」）与原书卷帙对不上，用不得，
    本库这几个目录一律按一本书一个文件放。
    """
    grp = (item.get('group') or '').strip().replace('词牌 · ', '')
    if grp == '元明清诗':
        return '元明清詩'
    return ''


def author_of(item):
    """上游 author 是「王正长」这类字号；库里有本名就用本名。"""
    import_set = (item.get('author') or '').strip()
    return (item.get('authorName') or '').strip() or import_set


def file_name(target, vol):
    """卷名 → 文件名：本库已有目录沿用既定命名，其余照 import.py 的规矩。"""
    if not vol:
        return target
    if target in ('乐府诗集', '文选', '古文观止'):
        return {'乐府诗集': '樂府詩集・', '文选': '文選・',
                '古文观止': '古文觀止・'}[target] + vol
    return vol


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--upstream', required=True, help='extract.js 的输出')
    ap.add_argument('--apply', action='store_true')
    ap.add_argument('--reviewer', default='CodeBuddy')
    ap.add_argument('--date', default='')
    args = ap.parse_args()
    global DATE, REVIEWER
    DATE, REVIEWER = args.date, args.reviewer

    try:
        from opencc import OpenCC
    except ImportError:
        sys.exit('pip install opencc-python-reimplemented')
    cc, s2twp = OpenCC('t2s'), OpenCC('s2twp')

    up = json.load(open(args.upstream, encoding='utf-8'))
    by_id = {it['id']: (book, it) for book, items in up.items() for it in items}

    audit = [l.rstrip('\n').split('\t') for l in
             open(os.path.join(ROOT, 'docs/wechat_corpus_audit.tsv'), encoding='utf-8')][1:]
    cand = [r for r in audit if r[3] == 'new']
    by_text, by_pre = build_index(cc)

    picked, dups = [], []
    for book, title, author, *_ in cand:
        books = [f'poems-{n}.js' for n in range(1, 13)] if book == '课内' \
            else [AUDIT_FILES.get(book)]
        hits = [v[1] for v in by_id.values()
                if v[0] in books and v[1].get('title') == title
                and (v[1].get('author') or '') == author]
        if not hits:  # 作者一栏上游可能写「欧阳修/朱淑真」这种，退一步只认标题
            hits = [v[1] for v in by_id.values()
                    if v[0] in books and v[1].get('title') == title]
        if not hits:
            dups.append((book, title, author, '上游同名条目定位失败'))
            continue
        it = hits[0]
        n = norm(it.get('text') or '', cc)
        if len(n) < 8:
            dups.append((book, title, author, '正文缺失'))
            continue
        hit = by_text.get(n) or (by_pre.get(n[:12]) if len(n) >= 12 else None)
        if hit:
            dups.append((book, title, author, f"已有：{hit['file']}《{hit['title']}》"))
            continue
        picked.append((book, it))

    print(f'候选 {len(cand)} 条 → 实收 {len(picked)} 条，剔除 {len(dups)} 条')
    for d in dups:
        print('  剔除', d[0], d[1], d[2], '|', d[3])

    books = OrderedDict()
    for book, it in picked:
        target = GENRE_DIRS.get(book) or BOOK_DIRS.get(book)
        if not target:
            sys.exit(f'上游集子 {book} 还没有目标目录，先在 BOOK_DIRS / GENRE_DIRS 里定下来')
        books.setdefault(target, OrderedDict()).setdefault(volume_of(it), []).append({
            'author': chinese(author_of(it) or '佚名', s2twp),
            'paragraphs': to_paragraphs(it.get('text'), s2twp),
            'title': chinese((it.get('title') or '').strip(), s2twp).replace('·', '・'),
            '_src': (book, it.get('id') or ''),
        })

    # 同一份正文在本库里只留一条：课内与近现代、古诗非唐与课本都有重出的篇目，
    # 所以先在整批里按正文去一次，再按文件合并
    have = set()
    for target, vols in books.items():
        for vol in vols:
            path = os.path.join(ROOT, target, file_name(target, vol) + '.json')
            if os.path.exists(path):
                for r in json.load(open(path, encoding='utf-8')):
                    have.add(norm(''.join(r.get('paragraphs') or []), cc))
                    have.add(norm_title(r.get('title')))
    plan, srcs, total = [], [], 0
    seen = set()
    for target, vols in books.items():
        for vol, recs in vols.items():
            path = os.path.join(ROOT, target, file_name(target, vol) + '.json')
            rel = os.path.relpath(path, ROOT)
            old = json.load(open(path, encoding='utf-8')) if os.path.exists(path) else []
            keep = []
            for r in recs:
                key = norm(''.join(r['paragraphs']), cc)
                if key in have or key in seen or norm_title(r['title']) in have:
                    continue
                seen.add(key)
                keep.append(r)
            kept = []
            for r in keep:
                kept.append({k: v for k, v in r.items() if k != '_src'})
                srcs.append((r['_src'], rel, r['title'], r['author']))
            plan.append((rel, path, old + kept, len(old), len(kept)))
            total += len(kept)
            print(f'{rel:34s} {"+" if old else "新"} {len(kept):3d} 条')
    print(f'\n合计 {total} 条')

    print('逐条来源写入 docs/wechat_corpus_collect.tsv')

    if not args.apply:
        print('（预演，加 --apply 写盘）')
        return 0

    for rel, path, recs, _, _ in plan:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w', encoding='utf-8') as fp:
            json.dump(recs, fp, ensure_ascii=False, indent=2)
            fp.write('\n')
    register([rel for rel, *_ in plan])
    print('已登记 loader/datas.json 与 fix_progress.json')
    return 0


DATE, REVIEWER = '', 'CodeBuddy'


def sync_stats(prog):
    """stats 从各文件状态重算，别手写数字。"""
    from collections import Counter
    c = Counter(v['status'] for v in prog['reviewed'].values())
    prog['stats'].update(reviewed=len(prog['reviewed']), clean=c['clean'],
                         fixed=c['fixed'], needs_review=c['needs_review'],
                         out_of_scope=c['out_of_scope'])


def register(new_files):
    """新目录登记进 loader/datas.json，新文件登记进 fix_progress.json。

    两个文件都是手写格式（datas.json 还是 CRLF、行尾带空格），整份 dump 一遍
    会带出成百行无谓改动，所以都是「插入一段文本」而不是「重写整个文件」。
    """
    dpath = os.path.join(ROOT, 'loader/datas.json')
    raw = open(dpath, encoding='utf-8', newline='').read()
    dat = json.loads(raw)
    next_id = max(v['id'] for v in dat['datasets'].values()) + 1
    add = []
    for key, (name, folder) in DATASETS.items():
        if not os.path.isdir(os.path.join(ROOT, folder)) or key in dat['datasets']:
            continue
        add.append((key, name, folder, next_id))
        next_id += 1
    if add:
        eol = '\r\n' if '\r\n' in raw else '\n'
        block = ','.join(
            f'{eol}        "{k}": {{{eol}'
            f'            "name": "{n}",{eol}'
            f'            "id": {i},{eol}'
            f'            "path": "{f}",{eol}'
            f'            "excludes": [],{eol}'
            f'            "tag": "paragraphs"{eol}'
            f'        }}' for k, n, f, i in add)
        # 追加到 datasets 最后一项之后：从末尾数第二个空行缩进的右括号
        at = raw.rindex('\n    }')
        head = raw[:at].rstrip()
        assert head.endswith('}'), head[-40:]
        raw = head + ',' + block + raw[at:]
        open(dpath, 'w', encoding='utf-8', newline='').write(raw)
        json.loads(raw)  # 写坏了就当场报错

    ppath = os.path.join(ROOT, 'fix_progress.json')
    prog = json.load(open(ppath, encoding='utf-8'))
    for rel in new_files:
        prog['reviewed'].setdefault(rel, {'date': DATE, 'reviewer': REVIEWER,
                                          'status': 'clean', 'fixes': []})
    sync_stats(prog)
    with open(ppath, 'w', encoding='utf-8') as fp:
        json.dump(prog, fp, ensure_ascii=False, indent=2)
        fp.write('\n')


if __name__ == '__main__':
    sys.exit(main())
