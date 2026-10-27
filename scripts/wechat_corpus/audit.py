#!/usr/bin/env python3
"""语料重复审计：拿上游 poem-wechat 的集子逐条查本库是否已有。

判定分三层，逐层放宽，每层都记进 audit.tsv，方便人工复核：

  exact   正文逐字相同（繁转简、去标点后比较）→ 收进来就是真重复
  prefix  前 12 字相同但后有出入     → 多半是节选/异文，单独看
  author  作者在本库、标题对不上     → 只是同作者，不算重复

用法：
  python3 scripts/wechat_corpus/audit.py --upstream /path/to/corpus/data \
      --repo . --out docs/wechat_corpus_audit.tsv
"""
import argparse, collections, json, os, re, sys, unicodedata

PUNCT = re.compile(r'[\s\W_]+', re.U)
SKIP_DIRS = {'loader', 'strains', 'images', 'rank', 'error', 'scripts', 'docs',
             '.git', '.claude', '.github'}
# 上游集子 -> 本库同体裁的数据；只在这个范围内判重，跨体裁不算
SAME_GENRE = {
    '唐诗': ('全唐诗/poet.tang.',),
    '古诗非唐': ('全唐诗/poet.song.',),
    '宋词三百首': ('宋词/',),
    '元曲': ('元曲/',),
    '乐府集': ('乐府诗集/',),
}


def norm(s, cc):
    s = cc.convert(unicodedata.normalize('NFKC', s or ''))
    return PUNCT.sub('', s)


def load_upstream(corpus_dir):
    """在 node 里跑上游的 JS，把 11 部带正文的集子摊平成 json。"""
    script = r'''
const fs=require('fs'),path=require('path');
const D=process.argv[1]; const win={};
for(const f of fs.readdirSync(D).filter(f=>f.endsWith('.js'))){
  try{ new Function('window', fs.readFileSync(path.join(D,f),'utf8'))(win); }catch(e){}
}
const tm={}; (win.TEXT_MASTER||[]).forEach(e=>tm[e.id]=e);
const txt=r=>r.text||(r.textRef&&tm[r.textRef]?tm[r.textRef].text:null);
const inner=i=>[1,2,3,4,5,6,7,8,9,10,11,12].flatMap(n=>win['POEMS_'+n]||[]);
const books={'课内':inner(),'古文':win.POEMS_CLASSIC,'乐府集':win.POEMS_YUEFU,
  '节日节气':win.POEMS_SEASONAL_SEASON,'唐诗':win.POEMS_TANGSHI,'古诗非唐':win.POEMS_GUSHI,
  '宋词三百首':win.POEMS_SONGCI,'元曲':win.POEMS_YUANQU,'古文观止':win.POEMS_GUWEN,
  '近现代':win.POEMS_JINXIANDAI,'文选':win.POEMS_ZHAOMING};
const out={};
for(const [k,v] of Object.entries(books))
  out[k]=(v||[]).map(p=>({id:p.id,title:p.title,author:p.author,text:txt(p)}));
process.stdout.write(JSON.stringify(out));
'''
    import subprocess
    r = subprocess.run(['node', '-e', script, corpus_dir], capture_output=True, text=True)
    if r.returncode:
        sys.exit(r.stderr)
    return json.loads(r.stdout)


def load_repo(root):
    out = []
    for dp, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for f in sorted(files):
            if not f.endswith('.json'):
                continue
            p = os.path.join(dp, f)
            try:
                data = json.load(open(p, encoding='utf-8'))
            except Exception:
                continue
            for rec in (data if isinstance(data, list) else [data]):
                if not isinstance(rec, dict):
                    continue
                ps = rec.get('paragraphs')
                if not ps:
                    continue
                flat = []
                stack = list(ps) if isinstance(ps, list) else [ps]
                while stack:
                    x = stack.pop(0)
                    if isinstance(x, str):
                        flat.append(x)
                    elif isinstance(x, list):
                        stack = x + stack
                    elif isinstance(x, dict):
                        stack = (x.get('paragraphs') or []) + stack
                out.append({'file': os.path.relpath(p, root),
                            'title': rec.get('title') or rec.get('rhythmic') or '',
                            'author': rec.get('author') or '',
                            'text': ''.join(flat)})
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--upstream', required=True)
    ap.add_argument('--repo', default='.')
    ap.add_argument('--out', default='docs/wechat_corpus_audit.tsv')
    a = ap.parse_args()
    try:
        from opencc import OpenCC
    except ImportError:
        sys.exit('pip install opencc-python-reimplemented')
    cc = OpenCC('t2s')

    up = load_upstream(a.upstream)
    repo = load_repo(a.repo)
    by_text = collections.defaultdict(list)
    by_pre = collections.defaultdict(list)
    by_auth = collections.defaultdict(set)
    for r in repo:
        n = norm(r['text'], cc)
        if len(n) >= 8:
            by_text[n].append(r)
            by_pre[n[:12]].append(r)
        by_auth[cc.convert(r['author'])].add(cc.convert(r['title']))

    rows = [('集子', '上游题', '上游作者', '判定', '本库文件', '本库题', '本库作者')]
    stat = collections.defaultdict(collections.Counter)
    for book, items in up.items():
        scope = SAME_GENRE.get(book)
        for it in items:
            txt = it.get('text')
            n = norm(txt, cc) if txt else ''
            verdict, hit = 'new', None
            if not n:
                verdict = 'no_text'
            else:
                cands = by_text.get(n, [])
                if scope:
                    cands = [c for c in cands if c['file'].startswith(scope)] or []
                if cands:
                    verdict, hit = 'exact', cands[0]
                elif len(n) >= 12:
                    cands = by_pre.get(n[:12], [])
                    if scope:
                        cands = [c for c in cands if c['file'].startswith(scope)]
                    if cands:
                        verdict, hit = 'prefix', cands[0]
            if verdict == 'new' and cc.convert(it.get('author') or '') in by_auth:
                verdict = 'author'
            stat[book][verdict] += 1
            rows.append((book, it.get('title') or '', it.get('author') or '', verdict,
                         hit['file'] if hit else '', hit['title'] if hit else '',
                         hit['author'] if hit else ''))
        stat[book]['_total'] = len(items)

    os.makedirs(os.path.dirname(a.out) or '.', exist_ok=True)
    with open(a.out, 'w', encoding='utf-8') as fp:
        for row in rows:
            fp.write('\t'.join(str(x).replace('\t', ' ') for x in row) + '\n')

    print(f'{"集子":10s} {"总数":>5s} {"正文全同":>8s} {"前缀同":>7s} {"新收":>6s}')
    for book, c in stat.items():
        print(f'{book:10s} {c["_total"]:5d} {c["exact"]:8d} {c["prefix"]:7d} {c["new"]:6d}')
    print(f'\n明细写入 {a.out}')


if __name__ == '__main__':
    main()
