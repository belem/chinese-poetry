#!/usr/bin/env python3
"""《宋词三百首》PR C：底本有、库里没有的 11 首，按底本补录。

补录的 11 首见 [`docs/宋词三百首勘正.md`](../宋词三百首勘正.md) 的「库内缺」一节：
逐首用首句和各句 4 字探针在 `宋/宋词/ci.song.*` 里检索过，零命中（识典古籍上都能查到，
是库内真缺，不是配不上）。张炎缺四首（高阳台·西湖春感、解连环·孤雁、月下笛、八声甘州），
周邦彦缺三首（瑞鹤仙、应天长、夜游宫）。

写法与库内其余记录一致：

- `title` 按 [`宋词三百首篇目.md`](宋词三百首篇目.md) 的口径：有小题作「词牌·小题」，没有作「词牌·正文首句」
- 正文一节一段（上下阕分两段），简体，标点用中文全角
- `id` 按 `scripts/backfill_ids.py` 的口径由「作者+题名+正文」哈希发号，避开库里现存 id
- 落在记录数最少的 `ci.song.23000.json`（该文件是宋词末卷，只有 2 条）

  python3 scripts/anthology/songci300_additions.py            # 预演
  python3 scripts/anthology/songci300_additions.py --apply --date YYYY-MM-DD --reviewer <名字>
"""
import argparse
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, 'scripts'))
import backfill_ids as bi  # noqa: E402
import progress as pg  # noqa: E402
from opencc import OpenCC  # noqa: E402

BOOK = os.path.join(ROOT, 'reference', '宋詞三百首')
TARGET = '宋/宋词/ci.song.23000.json'
TAG = '宋词三百首'
SEP = '·'
T2S = OpenCC('t2s')
HAN = re.compile(r'[\u3400-\u9fff\U00020000-\U0003ffff\ue000-\uf8ff□〇]')
# 底本目次号 → 库内没有同文记录的那 11 首
MISSING = [37, 91, 135, 137, 138, 191, 249, 290, 292, 293, 295]
# 底本调名 → 本库调名（同一个调的两种写法，见 docs/宋词三百首篇目.md）
RHYTHM = {137: '应天长'}


def load_book():
    txt = open(BOOK, encoding='utf-8').read()
    blocks = re.split(r'^### ', txt, flags=re.M)[1:]
    out = {}
    for no, b in enumerate(blocks, 1):
        head = b.split('\n')[0]
        title, author = head.rsplit(' / ', 1)
        body = [T2S.convert(x.strip()) for x in b.split('\n')[1:] if x.strip()]
        title = re.sub(r'\((.+)\)$', '', title) if '漁家傲' in title else title
        parts = T2S.convert(title.strip()).split(SEP, 1)
        out[no] = (parts[0].strip(), parts[1].strip() if len(parts) > 1 else '',
                   T2S.convert(author.strip()), body)
    return out


def existing_ids():
    ids = set()
    for dirpath, dirs, files in os.walk(ROOT):
        dirs[:] = sorted(d for d in dirs if d not in bi.SKIP_DIRS)
        for f in sorted(files):
            if not f.endswith('.json') or any(s in f for s in bi.SKIP):
                continue
            try:
                data = json.load(open(os.path.join(dirpath, f), encoding='utf-8'))
            except (json.JSONDecodeError, UnicodeDecodeError):
                continue
            if isinstance(data, list):
                ids.update(r['id'] for r in data if isinstance(r, dict) and r.get('id'))
    return ids


def build():
    book = load_book()
    recs = []
    for no in MISSING:
        rhythm, sub, author, body = book[no]
        rhythm = RHYTHM.get(no, rhythm)
        title = rhythm + SEP + (sub or ''.join(HAN.findall(''.join(body)))[:12])
        recs.append({'author': author, 'paragraphs': body, 'rhythmic': rhythm, 'title': title})
    taken = existing_ids()
    mapping = bi.assign([bi.work_key(r) for r in recs], taken=taken)
    for r in recs:
        r['id'] = mapping[bi.work_key(r)]
        r['tags'] = [TAG]
    return recs


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--apply', action='store_true')
    ap.add_argument('--date')
    ap.add_argument('--reviewer')
    args = ap.parse_args()

    recs = build()
    for r in recs:
        print(f'{r["id"]}  {r["author"]}《{r["title"]}》 {len(r["paragraphs"])} 段 '
              f'{len("".join(r["paragraphs"]))} 字')
    if not args.apply:
        return
    if not (args.date and args.reviewer):
        sys.exit('--apply 需要 --date 与 --reviewer')
    path = os.path.join(ROOT, TARGET)
    data = json.load(open(path, encoding='utf-8'))
    have = {r.get('id') for r in data}
    add = [r for r in recs if r['id'] not in have]
    if not add:
        print('已经补录过，无需再写')
        return
    text = open(path, encoding='utf-8').read()
    # 追加到数组末尾：沿用文件自己的两空格缩进与字段顺序
    new = ',\n'.join('  ' + json.dumps(r, ensure_ascii=False, indent=2).replace('\n', '\n  ') for r in add)
    body = text.rstrip()
    assert body.endswith(']')
    head = body[:body.rindex(']')].rstrip()
    if head.endswith('}'):
        head += ','
    text = head + '\n' + new + '\n]' + ('\n' if text.endswith('\n') else '')
    json.loads(text)
    open(path, 'w', encoding='utf-8').write(text)
    pg.merge(TARGET, dict(status='fixed', reviewer=args.reviewer, date=args.date,
                          fixes=[{'original': '（库内缺）', 'corrected': f'{r["title"]}',
                                  'note': f'{r["author"]}，按底本 reference/宋詞三百首 补录，{r["id"]}'}
                                 for r in add],
                          note='《宋词三百首》底本有、库内没有的 11 首按底本补录（另见 docs/宋词三百首勘正.md）。'))
    print(json.dumps(pg.write_index()['stats'], ensure_ascii=False))


if __name__ == '__main__':
    main()
