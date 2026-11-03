#!/usr/bin/env python3
"""题名与作者名的空格归一：只改 `title` / `chapter` / `rhythmic` / `author` 四个字段的空格字符。

判据（issue #258）：**文字之间只留一个半角空格**，作者名与题名同一口径。

  fw_space     全角空格 U+3000、不换行空格、U+2000–200A、U+202F、U+205F、制表符 → 半角空格
  multi_space  连续两个以上的半角空格 → 一个
  lead_trail   首尾空格 → 去掉

唯一的例外是作者名的并列：`光\t威\t裒` 是《全唐詩》里三个人合署，并作半角空格后会读成一个人
（与 `齊己　牟儒` 这一类同形）——那两处保留原样，列在 KEEP 里，`--check` 会一并报告。

正文（`paragraphs`）、`prologue`、`notes` 等字段一个不碰：正文里的空格归乱码修复流程。

  python3 scripts/fix_spaces.py                 # 只报告（--check 同义）
  python3 scripts/fix_spaces.py --apply         # 就地改
  python3 scripts/fix_spaces.py --apply --files-from-diff origin/develop
"""
import argparse
import collections
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from check_structure import iter_files, changed_data_files  # noqa: E402

FIELDS = ('title', 'chapter', 'rhythmic', 'author')
FW_SPACE = re.compile('[\u3000\u00a0\u2000-\u200a\u202f\u205f\t]')
MULTI_SPACE = re.compile(r' {2,}')
LEAD_TRAIL = re.compile(r'^ +| +$')

# 不改的值：原样 → 缘由
KEEP = {
    '光\t威\t裒': '《全唐詩》里光、威、裒三人合署，改成半角空格会被读成一个人名（唐/诗/全唐诗/poet.tang.44000.json）',
}


def normalize(text):
    return LEAD_TRAIL.sub('', MULTI_SPACE.sub(' ', FW_SPACE.sub(' ', text)))


def scan_file(rel):
    """该文件里需要归一的字段值，产出 (index, field, 现值, 改后)。"""
    with open(os.path.join(ROOT, rel), encoding='utf-8') as fp:
        data = json.load(fp)
    items = data if isinstance(data, list) else [data]
    for idx, it in enumerate(items):
        if not isinstance(it, dict):
            continue
        for field in FIELDS:
            text = it.get(field)
            if not isinstance(text, str) or text in KEEP:
                continue
            new = normalize(text)
            if new != text:
                yield idx, field, text, new


def apply_file(rel, fixes):
    """就地换字：只替换那几段值的字面，不重排文件 —— 各文件缩进有的是 2、有的是 4，
    整体 dump 一遍会让 diff 变成整个文件，改动就无从核对了。"""
    path = os.path.join(ROOT, rel)
    with open(path, encoding='utf-8') as fp:
        text = fp.read()
    for _, field, old, new in fixes:
        quoted = json.dumps(f'{field}')                      # 字段名带引号，正文里不会出现
        before = f'{quoted}: {json.dumps(old, ensure_ascii=False)}'
        after = f'{quoted}: {json.dumps(new, ensure_ascii=False)}'
        if before not in text:                               # 同一首诗的重出副本已先一步改掉
            continue
        text = text.replace(before, after, 1)
    with open(path, 'w', encoding='utf-8') as fp:
        fp.write(text)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--apply', action='store_true', help='就地改写；不加只报告')
    ap.add_argument('--files-from-diff', metavar='REF', help='只处理相对 REF 改动的数据文件')
    ap.add_argument('--show', type=int, default=5, help='每类展示的样例数')
    args = ap.parse_args()

    files = changed_data_files(args.files_from_diff) if args.files_from_diff else list(iter_files())
    kinds = collections.Counter()
    stats = collections.Counter()
    touched = []
    for rel in files:
        fixes = list(scan_file(rel))
        if not fixes:
            continue
        touched.append((rel, fixes))
        for _, field, old, _ in fixes:
            stats[field] += 1
            if FW_SPACE.search(old):
                kinds['fw_space'] += 1
            if MULTI_SPACE.search(old):
                kinds['multi_space'] += 1
            if LEAD_TRAIL.search(old):
                kinds['lead_trail'] += 1

    print(f'待改 {len(touched)} 个文件：{dict(stats)}；按检查项 {dict(kinds)}')
    for rel, fixes in touched[:args.show]:
        print(f'  {rel}#{fixes[0][0]} {len(fixes)} 处：{fixes[0][2][:40]!r} → {fixes[0][3][:40]!r}')

    if args.apply and touched:
        for rel, fixes in touched:
            apply_file(rel, fixes)
        print(f'已写入 {len(touched)} 个文件')
    elif touched:
        print('（未加 --apply，未改动任何文件）')
    return 0


if __name__ == '__main__':
    sys.exit(main())
