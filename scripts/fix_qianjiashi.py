#!/usr/bin/env python3
"""把《千家詩》从「选本目录嵌套」改成「一首一条」，并对齐底本 `reference/千家詩.txt`。

原文件的形状是 `{title, author, paragraphs: [{type, content: [{chapter, author, paragraphs}]}]}`，
`loader/data_loader.py` 按「文件是数组、一条记录一首」取 `tag`，加载即 `KeyError: 'paragraphs'`。
现在改成全库通用的 `[{author, title, paragraphs, section, id}, ...]`，并照底本重排：

  * 卷次（五言絕句 / 五言律詩 / 七言絕句 / 七言律詩）写进 `section`，不再靠嵌套层表示；
  * 底本「其一／其二」或重出的篇题，照底本分成各自独立的条目（旧稿按 section 序号取正文，
    与底本整体错位一格，`攜妓納涼晚際遇雨其一／其二` 落到了《中秋》《中秋月》的位置）；
  * 篇题、作者一律照底本，正文照底本；旧稿的夹注、旧稿多出的两首明人七律不在底本里，
    多出的两首仍留在 `明/诗/poet.ming.json`。

  python3 scripts/fix_qianjiashi.py            # 预演：只对账，不写盘
  python3 scripts/fix_qianjiashi.py --apply
"""
import argparse
import hashlib
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ALPHABET = '0123456789abcdefghijklmnopqrstuv'
SRC = 'reference/千家詩.txt'
REL = '宋/诗/千家诗/qianjiashi.json'
SECTIONS = {'五言絕句': '五言絕句', '五言律詩': '五言律詩', '七言絕句': '七言絕句', '七言律詩': '七言律詩'}
NOTE = re.compile(r'\s*[（(]([^）)]*)[）)]\s*$')          # 行末夹注
END_MARK = re.compile(r'^〔.+〕$')


def build_id(key, taken):
    size = 6
    while True:
        v = int.from_bytes(hashlib.blake2b(key.encode(), digest_size=16).digest(), 'big')
        out = ''
        for _ in range(size):
            v, r = divmod(v, 22)
            out = ALPHABET[r] + out
        if out not in taken:
            taken.add(out)
            return out
        size += 1


def parse(path):
    """→ [{section, author, chapter, lines}]，一仍底本的次序与篇题。"""
    out, section = [], None
    for raw in open(path, encoding='utf-8'):
        line = raw.strip()
        if not line:
            continue
        if line.startswith('### '):
            head = line[4:].strip()
            title, _, author = head.partition('/')
            out.append(dict(section=section, chapter=title.strip(), author=author.strip(), lines=[]))
        elif line.startswith('## '):
            section = line[3:].strip()
            assert section in SECTIONS, section
        elif line.startswith('# ') or END_MARK.match(line):
            continue
        else:
            assert out, f'正文出现在首个篇题之前：{line}'
            body, note = line, None
            m = NOTE.search(line)
            if m:
                body, note = line[:m.start()].strip(), m.group(1).strip()
            out[-1]['lines'].append((body, note))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--apply', action='store_true')
    args = ap.parse_args()

    poems = parse(os.path.join(ROOT, SRC))
    old = json.load(open(os.path.join(ROOT, REL), encoding='utf-8'))
    old_flat = [(sec['type'], it) for sec in old['paragraphs'] for it in sec['content']]
    if not args.apply:
        print(f'底本 {len(poems)} 首，旧稿 {len(old_flat)} 首')
        for i, (poem, (sec, it)) in enumerate(zip(poems, old_flat)):
            if poem['chapter'] != it['chapter']:
                print(f'  第 {i + 1} 首错位：底本《{poem["chapter"]}》/ 旧稿《{it["chapter"]}》')
        return

    taken, rows, variants, seen = set(), [], [], {}
    for poem in poems:
        lines = [b for b, _ in poem['lines']]
        assert lines, poem
        for body, note in poem['lines']:
            if note:
                variants.append(dict(chapter=poem['chapter'], line=body, note=note))
        title = poem['chapter']
        n = seen[title] = seen.get(title, 0) + 1
        row = dict(author=poem['author'], title=title, section=poem['section'], paragraphs=lines)
        row['id'] = build_id(f"{row['author']}|{title}|{''.join(lines)}|{n}", taken)
        rows.append(row)
    if variants:
        rows.append(dict(title='千家詩', author=old['author'], paragraphs=[], variants=variants,
                         id=build_id(f"{old['author']}|千家詩|variants", taken)))

    n = sum(len(p['lines']) for p in poems)
    print(f'{len(rows)} 条记录，{n} 句，夹注 {len(variants)} 条')
    open(os.path.join(ROOT, REL), 'w', encoding='utf-8').write(
        json.dumps(rows, ensure_ascii=False, indent=4) + '\n')


if __name__ == '__main__':
    sys.exit(main())
