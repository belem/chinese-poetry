#!/usr/bin/env python3
"""collate_one.py — 单条记录的对勘（补 collate.py 批量之外的零散核对）

  python3 scripts/shidian/collate_one.py --file '宋/宋词/ci.song.23000.json' --index 0 --work /tmp/w

做三件事：拼出该条正文（去标点，繁简按 t2s 比）、按 2-4 个 5-6 字窗口去识典古籍检索、
把命中的 book/bookName 与差异逐字列出来。只读，不写数据文件；结论由人（或 AI）判定后
再用 scripts/progress.py record 登记。

检索走 scripts/shidian/search.mjs（需要 playwright chromium）。
"""
import argparse, json, os, re, subprocess, sys, unicodedata

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SHIDIAN = os.path.dirname(os.path.abspath(__file__))

try:
    from opencc import OpenCC
    t2s = OpenCC('t2s').convert
except ImportError:                       # 没装就按原样比，字符集内仍是精确比较
    t2s = lambda s: s

PUNCT = re.compile(r'[\s，。、；：？！「」『』（）()《》〈〉·—…,.;:?!"\'-]')


def load_record(rel, index):
    path = os.path.join(ROOT, rel)
    data = json.load(open(path, encoding='utf-8'))
    if isinstance(data, dict):            # 千家诗这类 {「data」/「chapters」} 结构
        for key in ('chapters', 'data', 'poems'):
            if key in data:
                data = data[key]
                break
    return data[index]


def flat(text):
    return PUNCT.sub('', text)


def windows(text, n=6, k=3):
    t = flat(text)
    if len(t) <= n + 1:
        return [t]
    step = max(1, (len(t) - n) // (k - 1)) if k > 1 else 1
    return [t[i:i + n] for i in range(0, len(t) - n + 1, step)][:k]


def html_grep(url, needles):
    import urllib.parse, urllib.request
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    try:
        s = urllib.request.urlopen(req, timeout=60).read().decode('utf-8', 'replace')
    except Exception as e:
        return [], f'error: {e}'
    meta = re.search(r'name="description" content="([^"]*)"', s)
    lines = []
    for m in re.finditer(r'"content":"([^"]{4,300})"', s):
        txt = m.group(1)
        if any(t2s(txt).find(n) >= 0 for n in needles):
            book = re.search(r'"bookName":"([^"]*)"', s[m.end():m.end() + 5000])
            lines.append((txt, book.group(1) if book else '?'))
    return lines, None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--file', required=True)
    ap.add_argument('--index', type=int, default=0)
    ap.add_argument('--window', default='')
    ap.add_argument('--work', default='/tmp/collate_one')
    args = ap.parse_args()

    rec = load_record(args.file, args.index)
    paras = rec.get('paragraphs') or [rec.get('content', '')]
    body = ''.join(paras)
    print(f"# {rec.get('author','')}《{rec.get('title') or rec.get('rhythmic','')}》")
    for p in paras:
        print('   ', p)

    ws = [args.window] if args.window else windows(body)
    os.makedirs(args.work, exist_ok=True)
    qf = os.path.join(args.work, 'queries.json')
    json.dump(ws, open(qf, 'w'), ensure_ascii=False)
    out = os.path.join(args.work, 'results.jsonl')
    if os.path.exists(out):
        os.remove(out)
    subprocess.run(['node', os.path.join(SHIDIAN, 'search.mjs'), qf, out], check=False)

    for w in ws:
        print(f"\n== 检索「{w}」")
        url = 'https://www.shidianguji.com/zh/search/' + __import__('urllib.parse').parse.quote(w)
        lines, err = html_grep(url, [w])
        if err:
            print('  ', err)
            continue
        seen = set()
        for txt, book in lines:
            key = (txt[:20], book)
            if key in seen:
                continue
            seen.add(key)
            flag = '✓' if t2s(txt).find(w) >= 0 else '≠'
            print(f"  {flag} [{book}] {txt}")


if __name__ == '__main__':
    main()
