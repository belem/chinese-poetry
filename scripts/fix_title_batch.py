#!/usr/bin/env python3
"""选本与史书这一批的标题勘误：只改题名（`title` / `chapter` / `rhythmic` / `subtitle` /
`section` / `category` / `subcategory` / 目录里的 `篇目`），正文一字不碰。

范围是 issue #258 点名的十一部书：昭明文选、词综、古诗源、古文观止、乐府诗集、花间集、
战国策、隋唐演义、楚辞、安徒生童话、伊索寓言。口径与 `scripts/check_title.py` 相同，
这里只列本批真正查出来的几类：

  space        全角空格 U+3000 → 一个半角空格（隋唐演义 100 回回目，每回两个）
  punct        题名末尾的句读（词综「齐天乐·严县尹席上和李观我韵，」），删
  rhythmic     词综「红见？梅苑。」一条：底本把《梅苑》的出处写进了标题位，词牌按底本行内
               「见？梅苑」这一体例（尉迟杯见？梅苑、洞仙歌见？梅苑……）当作词牌名读不通，
               词牌留空、出处与首句并进题名，首句补足 12 字（同卷其余各首一律如此）
  stray_quote  战国策两条章题末尾多一个 `“`：那是底本每章前的 `○` 后面紧跟引号、
               切题时被带进章题的，正文里也没有与之配对
  ascii_mark   战国策「楼<吾午>约秦魏」：`<…>` 是底本标未编码生僻字的记法，正文里
               同一个人名写作 `{吾午}`，题名跟着改成 `{}`（`scripts/import_zhanguoce_reference.py`
               的 `clean()` 只洗正文，漏了章题）
  hyphen       安徒生童话「古教堂的钟-为席勒纪念册而作」：`-` 是副题分隔，同书另有
               「老栎树的梦——一个圣诞节的童话」，改破折号

  python3 scripts/fix_title_batch.py            # 只报告
  python3 scripts/fix_title_batch.py --apply    # 就地改写
"""
import argparse
import collections
import glob
import json
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

BOOKS = ('汇编/昭明文选', '汇编/词综', '汉/古诗源', '汇编/古文观止', '汇编/乐府诗集',
         '五代十国/词/五代诗词/huajianji', '史书/战国策', '清/小说/隋唐演义',
         '先秦/楚辞', '汇编/安徒生童话', '汇编/伊索寓言')
FIELDS = ('title', 'chapter', 'rhythmic', 'subtitle', 'section', 'category', 'subcategory', '篇目')

FW_SPACE = '\u3000'
TRAILING = re.compile('[。，、；：？！,.;:?!]+$')

# 逐条给定的改动：(文件, 序号, 字段, 现值, 改后)
FIXED = [
    ('汇编/词综/卷二十四.json', 41, 'title',
     '红见？梅苑·粉香尤嫩霜寒可惯怎奈向春',
     '红见？梅苑·粉香尤嫩霜寒可惯怎奈向春心'),   # 首句取满 12 字（同卷其余各首一律 12 字）
    ('史书/战国策/zhanguoce.json', 423, 'title',
     '戰國策·卷二十八 韩三·东孟之会“', '戰國策·卷二十八 韩三·东孟之会'),
    ('史书/战国策/zhanguoce.json', 459, 'title',
     '戰國策·卷三十 燕二·奉阳君千朱讙与赵足“', '戰國策·卷三十 燕二·奉阳君千朱讙与赵足'),
    ('史书/战国策/zhanguoce.json', 105, 'title',
     '戰國策·卷七 秦五·楼<吾午>约秦魏', '戰國策·卷七 秦五·楼{吾午}约秦魏'),
    ('汇编/安徒生童话/antushengtonghua.json', 94, 'title',
     '古教堂的钟-为席勒纪念册而作', '古教堂的钟——为席勒纪念册而作'),
]

# 目次里同一首的题名：`词综.json` 的 `titles` 是「题　作者」的摘记，改题时跟着改
TOC_FIXED = [
    ('汇编/词综/词综.json', '红见？梅苑。·粉香尤嫩霜寒可惯怎奈向春\u3000无名氏',
     '红见？梅苑·粉香尤嫩霜寒可惯怎奈向春心\u3000无名氏'),
]


def files():
    out = []
    for book in BOOKS:
        out += sorted(glob.glob(os.path.join(ROOT, book, '*.json')))
    return out


def load(path):
    with open(path, encoding='utf-8') as fp:
        return json.load(fp)


def normalize(text):
    """全角空格降为一个半角空格，连着的空格并成一个。"""
    return re.sub(' +', ' ', text.replace(FW_SPACE, ' ')).strip()


def planned():
    """这一批要改的全部位置：(相对路径, 序号, 字段, 现值, 改后)。"""
    todo = []
    seen = set()
    for path in files():
        rel = os.path.relpath(path, ROOT)
        data = load(path)
        items = data if isinstance(data, list) else [data]
        for idx, it in enumerate(items):
            if not isinstance(it, dict):
                continue
            for field in FIELDS:
                text = it.get(field)
                if not isinstance(text, str) or not text:
                    continue
                new = text
                if FW_SPACE in new:
                    new = normalize(new)
                if field in ('title', 'rhythmic', 'subtitle', '篇目'):
                    new = TRAILING.sub('', new)
                if new != text:
                    todo.append((rel, idx, field, text, new))
                    seen.add((rel, idx))
    for rel, idx, field, old, new in FIXED:
        if (rel, idx) in seen:
            continue                                  # 通用规则已改过（末字句读），不再重复
        data = load(os.path.join(ROOT, rel))
        items = data if isinstance(data, list) else [data]
        cur = items[idx].get(field)
        done = {new, TRAILING.sub('', new), TRAILING.sub('', old)}   # 已经改过的那一版
        if cur in done:
            continue
        assert cur == old, f'{rel}#{idx}.{field} 现值是 {cur!r}，与脚本记的 {old!r} 不符'
        todo.append((rel, idx, field, old, new))
    for rel, old, new in TOC_FIXED:
        data = load(os.path.join(ROOT, rel))
        for i, it in enumerate(data):
            for j, title in enumerate(it.get('titles', [])):
                if title == old:
                    todo.append((rel, (i, j), 'titles', title, new))
    return todo


def apply_file(path, fixes):
    """只替换那几个字段值的字面，不重排文件。"""
    with open(path, encoding='utf-8') as fp:
        text = fp.read()
    for _, _, field, old, new in fixes:
        if field == 'titles':          # 目次里的字符串数组元素
            before, after = json.dumps(old, ensure_ascii=False), json.dumps(new, ensure_ascii=False)
            if before not in text:
                raise SystemExit(f'{path}: 找不到 {before}')
            text = text.replace(before, after, 1)
            continue
        quoted = json.dumps(field, ensure_ascii=False)
        before = f'{quoted}: {json.dumps(old, ensure_ascii=False)}'
        after = f'{quoted}: {json.dumps(new, ensure_ascii=False)}'
        if before not in text:
            raise SystemExit(f'{path}: 找不到 {before}')
        text = text.replace(before, after, 1)
    with open(path, 'w', encoding='utf-8') as fp:
        fp.write(text)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--apply', action='store_true', help='就地改写；不加只报告')
    ap.add_argument('--show', type=int, default=8, help='每类展示的样例数')
    args = ap.parse_args()

    todo = planned()
    by_file = collections.defaultdict(list)
    for item in todo:
        by_file[item[0]].append(item)
    kinds = collections.Counter()
    for rel, idx, field, old, new in todo:
        if FW_SPACE in old:
            kinds['space'] += 1
        elif old.endswith(tuple('，。？,.')):
            kinds['punct'] += 1
        elif new.endswith('。') or old.startswith('红见'):
            kinds['rhythmic'] += 1
        elif old in {f[3] for f in FIXED}:
            kinds['fixed'] += 1
        else:
            kinds['other'] += 1

    print(f'待改 {len(todo)} 处，涉及 {len(by_file)} 个文件')
    for rel, items in sorted(by_file.items()):
        print(f'  {rel}: {len(items)} 处')
        for _, idx, field, old, new in items[:args.show]:
            print(f'     #{idx} [{field}] {old!r} → {new!r}')
    if args.apply and by_file:
        for rel, items in by_file.items():
            apply_file(os.path.join(ROOT, rel), items)
        print(f'已写入 {len(by_file)} 个文件')
    elif by_file:
        print('（未加 --apply，未改动任何文件）')


if __name__ == '__main__':
    main()
