#!/usr/bin/env python3
"""四书与《道德经》：repo 内底本 → 五部 JSON。

底本：

    reference/論語.txt     `## 學而篇第一` 分篇，空行分段
    reference/孟子.txt     `## 梁惠王上`   分篇，空行分段
    reference/中庸.txt     一篇到底
    reference/大學.txt     一篇到底
    reference/道德經.txt   `### 第一章` 分章，章内按句分行，夹注作「(一作…)」

规则：
  * 只认 `#`/`##`/`###` 三种标题行，`# 論語` 这类书名行跳过，`〔全文完〕` 不进正文；
  * 正文一字不动，不改字、不补字、不并段；问对分段的照底本分成两条；
  * `道德經` 的夹注是校记不是正文，从段落里摘出来放进该条 `note`；
  * 道德经一章一条记录，`title` 作 `道德經（第一章）`（中文数字，同底本）；
  * 四书不带 `id`/`author`（与库内其余经部一致，`chapter` + `paragraphs` 两层）。

    python3 scripts/import_sishu_reference.py            # 写文件
    python3 scripts/import_sishu_reference.py --check    # 只比对，不写
"""
import argparse
import json
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
END_MARK = '〔全文完〕'

# (底本, 输出, book_name 或 None=按 ## 分篇, 固定 chapter 名)
PLAIN = [
    ('reference/中庸.txt', '先秦/中庸/zhongyong.json'),
    ('reference/大學.txt', '先秦/大学/daxue.json'),
]
CHAPTERED = [
    ('reference/論語.txt', '先秦/论语/lunyu.json'),
    ('reference/孟子.txt', '先秦/孟子/mengzi.json'),
]
DAODEJING = ('reference/道德經.txt', '先秦/文/daodejing.json')

GLOSS = re.compile(r'\(([^()]{2,})\)')          # 底本的夹注一律半角圆括号


def lines_of(rel):
    for raw in open(os.path.join(ROOT, rel), encoding='utf-8'):
        line = raw.strip()
        if not line or line == END_MARK or '〔全文完〕' in line:
            continue
        yield line


def plain(rel):
    return [line for line in lines_of(rel) if not line.startswith('#')]


def chaptered(rel):
    chaps, cur = [], None
    for line in lines_of(rel):
        if line.startswith('## '):
            cur = {'chapter': line[3:].strip(), 'paragraphs': []}
            chaps.append(cur)
        elif line.startswith('#'):
            continue
        else:
            assert cur is not None, f'{rel}: 正文出现在篇名之前：{line[:20]}'
            cur['paragraphs'].append(line)
    return chaps


def daodejing(rel):
    book, chaps, cur = '', [], None
    for line in lines_of(rel):
        if line.startswith('### '):
            cur = {'title': line[4:].strip(), 'paragraphs': []}
            chaps.append(cur)
        elif line.startswith('# '):
            book = line[2:].strip()
        elif line.startswith('#'):
            continue
        else:
            gl = GLOSS.findall(line)
            line = GLOSS.sub('', line).strip()
            cur['paragraphs'].append(line)
            if gl:
                cur.setdefault('note', []).extend(gl)
    author = book.split('〔')[1].rstrip('〕') if '〔' in book else ''
    out = []
    for c in chaps:
        rec = {'title': f'道德經（{c["title"]}）', 'author': author,
               'paragraphs': c['paragraphs']}
        if 'note' in c:
            rec['note'] = '；'.join(c['note'])
        out.append(rec)
    return out


def build():
    files = {}
    for rel, out in PLAIN:
        name = os.path.splitext(os.path.basename(rel))[0]
        files[out] = [{'chapter': name, 'paragraphs': plain(rel)}]
    for rel, out in CHAPTERED:
        files[out] = chaptered(rel)
    files[DAODEJING[1]] = daodejing(DAODEJING[0])
    return files


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--check', action='store_true', help='只比对现有文件，不写')
    args = ap.parse_args()
    ok = True
    for out, data in build().items():
        assert all(r['paragraphs'] for r in data), f'{out}: 有记录没有正文'
        text = json.dumps(data, ensure_ascii=False, indent=2) + '\n'
        dst = os.path.join(ROOT, out)
        n = sum(len(r['paragraphs']) for r in data)
        c = sum(len(p) for r in data for p in r['paragraphs'])
        print(f'{out}: {len(data)} 条，{n} 段，{c} 字')
        if args.check:
            same = os.path.exists(dst) and open(dst, encoding='utf-8').read() == text
            ok = ok and same
            print('  一致' if same else '  不一致')
        else:
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            open(dst, 'w', encoding='utf-8').write(text)
    return 0 if ok else 1


if __name__ == '__main__':
    raise SystemExit(main())
