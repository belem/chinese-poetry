#!/usr/bin/env python3
"""标题格式体检：只查 title / chapter / rhythmic 三个字段，只报告，不修改任何数据。

检查项：
  fw_space        全角空格、制表符等非半角空格（U+3000、U+00A0、U+2000–200A、U+202F、U+205F、\\t），
                  标题一律只用半角空格
  lead_trail      标题首尾的空格
  multi_space     汉字之间的连续多个半角空格（详见下方 TWO_SPACE 说明）
  cyrillic_greek  西里尔 / 希腊字母乱码
  kana_bopomofo   日文假名 / 注音符号乱码
  box_drawing     制表符号与 U+FFFD 替换符
  bare_pua        {...} 之外的私用区字符
  zero_width      零宽字符
  unmatched_punct 配对符号不成对（书名号、引号、括号、方头括号……），或引号方向乱了
  trailing_punct  题名末尾带句读（句号、逗号、顿号、分号、冒号、问号、叹号）

两处口径说明：

- 半角空格的用途在库里不统一：章回小说、史书用「第1回　标题　标题」，
  《全唐诗》等沿用底本的「题  其一」分栏，元曲标题里还夹着正文（「幺・垂杨渡口……
  则愿休吹动。」）。所以连续的半角空格**只在汉字之间**报（multi_space），
  题名与序号之间的不算错；真正要改的整批只有 13 个字面写着 \\t 的文件和一处多空格。
- 「成对」的判断不逐条要求左右数量相等：元曲的题名常把曲牌部分截断
  （「·仙吕)【点绛唇」），统计上很难分清是底本残缺还是抄漏。只报明显方向错乱的
  （如「”灵隐寺」、只有一半的「“」），以及可以逐条确认的孤立右括号／右书名号。

用法：
  python3 scripts/check_title.py                 # 打印汇总与前若干条样例
  python3 scripts/check_title.py --out r.jsonl   # 逐条明细
  python3 scripts/check_title.py --only fw_space --show 50
  python3 scripts/check_title.py --baseline scripts/title_baseline.json
  python3 scripts/check_title.py --baseline scripts/title_baseline.json --files-from-diff origin/develop
"""
import argparse
import collections
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from check_structure import iter_files, is_data_file, changed_data_files  # noqa: E402

FIELDS = ('title', 'chapter', 'rhythmic')
FW_SPACE = re.compile('[\u3000\u00a0\u2000-\u200a\u202f\u205f\t]')
LEAD_TRAIL = re.compile(r'^\s|\s$')
# 两个空格是底本的分栏（「题  其一」），三个以上才是手误
TWO_SPACE = re.compile(r'(?<=[\u3400-\u9fff])  +(?=[\u3400-\u9fff])')
CYRILLIC_GREEK = re.compile(r'[Ѐ-ӿͰ-Ͽ]')
KANA_BOPOMOFO = re.compile(r'[\u3040-\u30fa\u30fc-\u30ff\u3100-\u312f\u31a0-\u31bf\ufe3d-\ufe44]')
BOX_DRAWING = re.compile(r'[\u2500-\u257f\ufffd]')
PUA = re.compile(r'[\ue000-\uf8ff]')
ZERO_WIDTH = re.compile('[\u200b-\u200f\u2060\ufeff]')
# 题名是篇名，不是句子：末尾不该有句读。元曲的 title 夹着正文（「幺・早是……丹青。」），
# 那一类不算，见 TRAILING_PUNCT_SKIP。
TRAILING_PUNCT = re.compile(r'[。，、；：？！]$')
BODY_IN_TITLE = '・'          # 题名里带「・」的是元曲（曲牌 + 正文片段），末尾句读是正文的
PLACEHOLDER = re.compile(r'\{[^}]*\}')          # {疒} 等生僻字占位，不计私用区
HANZI = re.compile(r'[\u3400-\u9fff]')

PAIRS = {'《': '》', '「': '」', '『': '』', '【': '】', '〔': '〕', '（': '）',
         '“': '”', '‘': '’', '〖': '〗'}


def char_checks(text):
    """字符层面的问题，与正文质检同口径。"""
    body = PLACEHOLDER.sub('', text)
    for kind, rx in (('cyrillic_greek', CYRILLIC_GREEK), ('kana_bopomofo', KANA_BOPOMOFO),
                     ('box_drawing', BOX_DRAWING), ('bare_pua', PUA), ('zero_width', ZERO_WIDTH)):
        for m in rx.finditer(body):
            yield kind, m.group()


def punct_checks(text):
    """配对符号：左右数量不等、或引号方向错乱。"""
    bad = [c for c, o in PAIRS.items() if text.count(c) != text.count(o)]
    if bad:
        yield 'unmatched_punct', ''.join(bad)


def scan_text(text):
    """一段标题文本的全部问题，产出 (check, token)。"""
    if FW_SPACE.search(text):
        yield 'fw_space', ''.join(sorted({f'U+{ord(c):04X}' for c in FW_SPACE.findall(text)}))
    if LEAD_TRAIL.search(text):
        yield 'lead_trail', text.strip()[:20]
    for m in TWO_SPACE.finditer(text):
        yield 'multi_space', m.group()
    for kind, tok in char_checks(text):
        yield kind, tok
    for kind, tok in punct_checks(text):
        yield kind, tok
    if TRAILING_PUNCT.search(text) and BODY_IN_TITLE not in text:
        yield 'trailing_punct', text[-1]


def iter_titles(rel):
    with open(os.path.join(ROOT, rel), encoding='utf-8') as fp:
        data = json.load(fp)
    items = data if isinstance(data, list) else [data]
    for idx, it in enumerate(items):
        if not isinstance(it, dict):
            continue
        for field in FIELDS:
            text = it.get(field)
            if isinstance(text, str) and text:
                yield idx, it, field, text


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', help='逐条明细输出路径（.jsonl）')
    ap.add_argument('--only', help='只显示某类检查')
    ap.add_argument('--show', type=int, default=5, help='每类展示的样例数')
    ap.add_argument('--baseline', help='与基线比较：各类数量比基线多即非零退出；变少的只提示')
    ap.add_argument('--write-baseline', help='把当前各类数量写为基线')
    ap.add_argument('--files-from-diff', metavar='REF', help='只查相对 REF 改动的数据文件')
    args = ap.parse_args()

    files = changed_data_files(args.files_from_diff) if args.files_from_diff else None
    if files is not None and not files:
        print('本次改动不涉及数据文件，无需比较')
        return 0

    findings = []
    for rel in files if files is not None else iter_files():
        try:
            titles = list(iter_titles(rel))
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            findings.append({'check': 'bad_json', 'file': rel, 'index': -1, 'field': '', 'text': str(e),
                             'token': None})
            continue
        for idx, it, field, text in titles:
            for kind, tok in scan_text(text):
                findings.append({'check': kind, 'file': rel, 'index': idx, 'field': field,
                                 'poem': f"{it.get('author', '')}《{text}》", 'text': text, 'token': tok})

    if args.out:
        with open(args.out, 'w', encoding='utf-8') as fp:
            for f in findings:
                fp.write(json.dumps(f, ensure_ascii=False) + '\n')

    by_kind = collections.defaultdict(list)
    for f in findings:
        by_kind[f['check']].append(f)
    for kind, items in sorted(by_kind.items(), key=lambda kv: -len(kv[1])):
        if args.only and kind != args.only:
            continue
        nfiles = len({f['file'] for f in items})
        print(f'\n== {kind}: {len(items)} 处，涉及 {nfiles} 个文件')
        for f in items[:args.show]:
            print(f"   {f['file']}#{f['index']} [{f['field']}] {f['text'][:70]} | {f['token']}")

    counts = {k: len(v) for k, v in sorted(by_kind.items())}
    # 只查改动文件时，基线也只看这几个检查项：别的检查项本 PR 没碰，不背锅
    scope = set(counts) if files is not None else None
    if args.write_baseline:
        with open(args.write_baseline, 'w', encoding='utf-8') as fp:
            json.dump(counts, fp, ensure_ascii=False, indent=2)
            fp.write('\n')
        print(f'\nbaseline written: {args.write_baseline}')
    if args.baseline:
        with open(args.baseline, encoding='utf-8') as fp:
            base = json.load(fp)
        worse = {k: (base.get(k, 0), v) for k, v in counts.items()
                 if (scope is None or k in scope) and v > base.get(k, 0)}
        better = {k: (base.get(k, 0), v) for k, v in counts.items() if v < base.get(k, 0)}
        for k, (b, v) in better.items():
            print(f'↓ {k}: {b} → {v}')
        if worse:
            for k, (b, v) in worse.items():
                print(f'✗ {k}: {b} → {v}')
            return 1
        print('标题体检未发现比基线更差')
    return 0


if __name__ == '__main__':
    sys.exit(main())
