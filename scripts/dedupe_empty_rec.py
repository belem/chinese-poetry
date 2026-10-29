#!/usr/bin/env python3
"""《全唐诗》里正文只有「。」的空记录：删掉。

`poet.tang.50000.json`–`poet.tang.57000.json` 是从《全唐诗补逸》《全唐诗续补遗》一路
爬下来的敦煌残卷与逸句，其中 182 条只剩一个句号：

```json
{"author": "崔湜", "paragraphs": ["。"], "title": "", "id": "dkl841"}
```

`paragraphs: ["。"]` 是原书卷次里只有作者名、诗题与正文都没爬下来的位置 —— 保留它，
下游按「条」取数据时会拿到一首空诗。

判据：`''.join(paragraphs)` 去掉标点后为空，且 `notes` 里没有正文字句可还原。
172 条的题名也是空的；题名在、正文空的 10 条同样是空记录（`塞上聽彈胡笳作（幷序）`
只剩题，正文在《全唐诗》别本，这批不补，只删空壳）。

用法：
  python3 scripts/dedupe_empty_rec.py            # 预演：列出全部空记录
  python3 scripts/dedupe_empty_rec.py --apply --date YYYY-MM-DD --reviewer <名字>
"""
import argparse
import csv
import glob
import json
import os
import re
import sys
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import progress as pg  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BOOK = '唐/诗/全唐诗'
OUT = 'docs/全唐诗空记录.tsv'
HAN = re.compile(r'[^\u4e00-\u9fff]')


def load(rel):
    with open(os.path.join(ROOT, rel), encoding='utf-8') as fp:
        return json.load(fp)


def dump(rel, data):
    path = os.path.join(ROOT, rel)
    raw = open(path, encoding='utf-8').read()
    m = re.search(r'\n( +)\S', raw)
    indent = len(m.group(1)) if m else 2
    out = json.dumps(data, ensure_ascii=False, indent=indent) + ('\n' if raw.endswith('\n') else '')
    src = raw.split('\n')
    out = '\n'.join(r + (' ' if i < len(src) - 1 and src[i].endswith(' ') else '')
                    for i, r in enumerate(out.split('\n')))
    with open(path, 'w', encoding='utf-8') as fp:
        fp.write(out)


def files_of():
    fs = [os.path.relpath(f, ROOT) for f in glob.glob(os.path.join(ROOT, BOOK, 'poet.*.json'))]
    return sorted(fs, key=lambda f: int(re.search(r'\.(\d+)\.json$', f).group(1)))


def is_empty(rec):
    return not HAN.sub('', ''.join(rec.get('paragraphs') or []))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--apply', action='store_true')
    ap.add_argument('--date', default=date.today().isoformat())
    ap.add_argument('--reviewer', default='codebuddy')
    ap.add_argument('--out', default=OUT)
    args = ap.parse_args()

    data, empty = {}, {}
    for rel in files_of():
        data[rel] = load(rel)
        hits = [r for r in data[rel] if is_empty(r)]
        if hits:
            empty[rel] = hits
    n = sum(len(v) for v in empty.values())
    print(f'== 正文只有「。」的空记录：{n} 条，涉及 {len(empty)} 个文件')
    for rel, recs in empty.items():
        titled = sum(1 for r in recs if (r.get('title') or '').strip())
        print(f'   {rel.split("/")[-1]:<22}{len(recs):>4} 条（题名不空 {titled}）')

    if not args.apply:
        for rel, recs in empty.items():
            for r in recs[:3]:
                print(f"     删 {r.get('author')}《{r.get('title')}》 {r.get('id')}")
        print('\n（预演，未改动文件；加 --apply 落盘）')
        return

    fixes = {}
    for rel, recs in empty.items():
        data[rel] = [r for r in data[rel] if not is_empty(r)]
        dump(rel, data[rel])
        fixes[rel] = [dict(original=f"{r.get('id')} {r.get('author')}《{r.get('title')}》",
                           corrected='删除',
                           note='[empty] 正文只有「。」，底本此处只存作者名、诗题与正文皆未录，删空壳')
                       for r in recs]

    with open(os.path.join(ROOT, args.out), 'w', encoding='utf-8', newline='') as fp:
        w = csv.writer(fp, delimiter='\t', lineterminator='\n')
        w.writerow(['文件', '作者', '题名', 'id', '处理'])
        for rel, recs in empty.items():
            for r in recs:
                w.writerow([rel, r.get('author'), r.get('title'), r.get('id'), '删（正文只有「。」）'])
    print(f'明细写入 {args.out}')

    for rel, items in fixes.items():
        rec = pg.merge(rel, dict(fixes=items, date=args.date, reviewer=args.reviewer))
        rec['note'] = ((rec.get('note') or '').rstrip() +
                       f" {args.date} 删 {len(items)} 条正文只有「。」的空记录，逐条见 {args.out}。").strip()
        pg.write_record(rel, pg.ordered(rec))
    pg.write_index()
    print(f'进度记录 {len(fixes)} 个文件')


if __name__ == '__main__':
    main()
