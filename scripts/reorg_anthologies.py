#!/usr/bin/env python3
"""《古文观止》独立成书、课外经典按篇归回各书。

  python3 scripts/reorg_anthologies.py           # 预演：打印对齐报告
  python3 scripts/reorg_anthologies.py --apply   # 搬目录、拆文件，写 docs/汇编归位.tsv

## 一、《古文观止》→ 汇编/

《古文观止》是清人吴楚材、吴调侯编的选本，跨代收文（周文到明文）。目录是「一部书一个目录」，
跨代的书不按朝代切，所以单开 `汇编/` 一层（乐府诗集、昭明文选 2026-10 也移到了 `汇编/诗文总集/`）。

`先秦/古文观止/卷*.json` 原是从母本 `先秦/蒙学/guwenguanzhi.json` 里抄出来的子集：
227 篇对 222 篇，正文基本逐字相同，但两份并存就会漂——「召公諫厲王弭謗」与「召公諫厲王止謗」、
「裡革斷罟匡君」与「裏革斷罟匡君」、「齊桓公伐楚盟屈完」与「齊桓公伐楚」这类出入就是这么来的。
所以以母本为准：`汇编/古文观止/` 的 12 个卷文件逐篇取自母本，子本里题名或正文对不上的留在
`古文观止·补.json`，并登记进 fix_progress.json 待核。

母本只在 `先秦/蒙学/guwenguanzhi.json`（现 `汇编/蒙学/`）：那里那份是「蒙学」这个主题目录下的一本，
现在书独立成目录，`先秦/蒙学/` 与 `汇编/` 各留一份正文是不对的，母本随书搬到
`汇编/古文观止/古文观止.json`。

## 二、课外经典 → 汇编/课本选目/

`先秦/课外经典/` 的 8 个文件（寓言故事、神话传说、山水游记、志人逸事、治学勤读、人物故事、
诸子论道、蒙学经典）是按主题编的课本选目，不是一个集子名，也不是一部书：一章《山海经》
可以和一段《宋史》编在同一个文件里。

这些篇目大多不是古籍原文的完整一篇，而是课本的改写、节选、拉平了的一段（如《精衛填海》
只取《山海经·北山经》里的一小段），并到《山海经》里会把底本弄脏。因此保留成一份
「课本选目」，归到 `汇编/课本选目/`（跨代、非一书，与《古文观止》同一个去处），
文件名不变。

## 三、登记

逐条写 `docs/汇编归位.tsv`：古文观止 227 篇的对齐结果、课外经典 8 个文件的去向。
"""
import argparse
import difflib
import glob
import json
import os
import re
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from check_tree import norm  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

OLD_GW = '先秦/古文观止'
MOTHER = '汇编/蒙学/guwenguanzhi.json'   # 2026-10 前是 先秦/蒙学/guwenguanzhi.json；该文件现已并成 汇编/古文观止/古文观止.json
NEW_GW = '汇编/古文观止'
OLD_KW = '先秦/课外经典'
NEW_KW = '汇编/课本选目'
OUT = 'docs/汇编归位.tsv'


def load(rel):
    with open(os.path.join(ROOT, rel), encoding='utf-8') as fp:
        return json.load(fp)


def save(rel, data):
    path = os.path.join(ROOT, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    raw = open(path, encoding='utf-8').read() if os.path.exists(path) else ''
    indent = len(re.match(r'\[\n( *)', raw).group(1)) if raw.startswith('[\n') else 2
    with open(path, 'w', encoding='utf-8') as fp:
        fp.write(json.dumps(data, ensure_ascii=False, indent=indent) + ('\n' if raw.endswith('\n') or not raw else ''))


def juan_filename(title):
    """卷一・周文 → 卷一周文.json（沿用原子本的文件名）"""
    return title.replace('・', '').replace(' ', '') + '.json'


def poem(entry):
    """母本的一条 → 本库的记录格式（与 poet.tang.* 一致：author / title / paragraphs）。"""
    author = re.sub(r'^\S+?：', '', entry['author'] or '').strip()
    return {'author': author, 'title': entry['chapter'], 'paragraphs': entry['paragraphs']}


def _subset(short, long):
    """short 的九成以上按顺序出现在 long 里：子本多出的是篇前提要、篇末校记。"""
    sm = difflib.SequenceMatcher(None, long, short, autojunk=False)
    hit = sum(b.size for b in sm.get_matching_blocks())
    return len(short) > 0 and hit >= 0.9 * len(short)


def align():
    """子本 227 篇 → 母本 222 篇。返回 (按卷的母本篇目, 子本对不上的篇目)。"""
    mother = {}
    by_juan = {}
    gw = load(MOTHER)
    for juan in gw['content']:
        by_juan[juan['title']] = []
        for entry in juan['content']:
            by_juan[juan['title']].append(entry)
            mother.setdefault(entry['chapter'], []).append(entry)
            # 题名用字通假的（裡/裏、樑/梁…），另建一个规范化键
            mother.setdefault(norm(entry['chapter']), []).append(entry)

    extra = []
    rows = []
    for rel in sorted(glob.glob(os.path.join(ROOT, OLD_GW, '卷*.json'))):
        for rec in load(os.path.relpath(rel, ROOT)):
            hits = mother.get(rec['title']) or mother.get(norm(rec['title'])) or []
            body = norm(''.join(rec['paragraphs']))
            # 一比全文、二比前缀（节选）、三比相似度；母本不收节选，所以留补
            for how in (lambda h: norm(''.join(h['paragraphs'])) == body,
                        lambda h: body.startswith(norm(''.join(h['paragraphs']))),
                        lambda h: difflib.SequenceMatcher(None, body, norm(''.join(h['paragraphs'])),
                                                          autojunk=False).ratio() >= 0.98):
                same = [h for h in hits if how(h)]
                if same:
                    break
            if same:
                rows.append((os.path.basename(rel), rec['title'], same[0]['chapter'], '正文与母本相同'))
            elif hits and any(_subset(norm(''.join(h['paragraphs'])), body) for h in hits):
                # 子本是母本的超集：篇前提要、篇末校记是《古文观止》原书的评注，两存无益，
                # 以母本为准，子本那一份不再单列
                rows.append((os.path.basename(rel), rec['title'], hits[0]['chapter'], '子本多出评注，并入母本'))
            elif hits:
                extra.append(rec)
                rows.append((os.path.basename(rel), rec['title'], hits[0]['chapter'], '正文有出入，留补'))
            else:
                extra.append(rec)
                rows.append((os.path.basename(rel), rec['title'], '', '母本无此题，留补'))
    return by_juan, extra, rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--apply', action='store_true')
    args = ap.parse_args()

    by_juan, extra, rows = align()
    print(f'《古文观止》母本 {sum(len(v) for v in by_juan.values())} 篇，'
          f'子本 {len(rows)} 篇，其中与母本对不上 {len(extra)} 篇')
    for r in rows:
        if r[3] != '正文与母本相同':
            print('   ', r[1], '→', r[2] or '（母本无）', r[3])

    kw_files = sorted(glob.glob(os.path.join(ROOT, OLD_KW, '*.json')))
    print(f'课外经典 {len(kw_files)} 个文件，{sum(len(load(os.path.relpath(f, ROOT))) for f in kw_files)} 篇')

    if not args.apply:
        print('（预演，未写盘；加 --apply 执行）')
        return

    # 一、古文观止：母本搬成 汇编/古文观止/古文观止.json + 12 个卷文件
    gw = load(MOTHER)
    save(f'{NEW_GW}/古文观止.json', [{
        'author': '吳楚材、吳調侯',
        'title': '古文觀止',
        'paragraphs': gw['abstract'],
        'prologue': '清康熙三十四年（1695）吳楚材、吳調侯編選，收東周至明代文章 222 篇，分 12 卷。',
    }])
    for juan in gw['content']:
        save(f'{NEW_GW}/{juan_filename(juan["title"])}', [poem(e) for e in juan['content']])
    if extra:
        save(f'{NEW_GW}/古文观止·补.json', extra)
    for rel in glob.glob(os.path.join(ROOT, OLD_GW, '*.json')):
        os.remove(rel)
    os.rmdir(os.path.join(ROOT, OLD_GW))
    os.remove(os.path.join(ROOT, MOTHER))

    # 二、课外经典 → 汇编/课本选目/
    os.makedirs(os.path.join(ROOT, NEW_KW), exist_ok=True)
    for rel in kw_files:
        base = os.path.basename(rel)
        shutil.move(rel, os.path.join(ROOT, NEW_KW, base))
    os.rmdir(os.path.join(ROOT, OLD_KW))

    with open(os.path.join(ROOT, OUT), 'w', encoding='utf-8') as fp:
        fp.write('来源\t篇目\t母本篇名\t处理\n')
        for r in rows:
            fp.write('\t'.join(r) + '\n')
        for rel in kw_files:
            fp.write(f'{os.path.basename(rel)}\t（{len(load(os.path.join(NEW_KW, os.path.basename(rel))))} 篇）\t\t'
                     f'整文件移到 {NEW_KW}/\n')
    print(f'明细写入 {OUT}')


if __name__ == '__main__':
    main()
