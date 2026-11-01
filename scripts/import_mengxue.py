#!/usr/bin/env python3
"""依 repo 内 `reference/*.txt` 逐部重新生成 `汇编/蒙学/` 的九部蒙学书。

  python3 scripts/import_mengxue.py            # 预演：打印各书的条数、字数与勘误
  python3 scripts/import_mengxue.py --apply    # 写盘并更新 docs/progress 记录

底本一律是繁体、每行一句、`#`/`##`/`###` 分卷（或不分卷）。生成时：

  * 一行 `paragraphs` 一条正文，一仍底本的排法 —— 蒙学书是韵语，断句就是原文的一部分，
    不做跨行合并；
  * 夹注（`(一作「某某」)`、`(唐人作「律召調陽」)`）不进正文，异文写进 `variants`；
  * `〔全文完〕` 是版式标记，不是正文，跳过；
  * `title`/`author` 照书；`dynasty` 是该书成书或作者所属的朝代（与 authors/authors.json 对齐）；
  * `id` 由「作者 + 题名 + 正文」哈希得来，规则同 `scripts/backfill_ids.py`。

底本里能定案的讹字写在本文件的 `FIXES` 里，由脚本改，改了什么、依据什么写在 `docs/蒙学重建.md`。
底本未改，`FIXES` 只在生成时生效 —— 底本要不要跟着改，留给维护者定。
"""
import argparse
import hashlib
import json
import os
import re
import sys
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import progress as pg  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIR = '汇编/蒙学'
REVIEWER = 'CodeBuddy'
ALPHABET = '0123456789abcdefghijklmnopqrstuv'

END_MARK = re.compile(r'^〔.+〕$')                      # 〔全文完〕
NOTE = re.compile(r'\s*[（(]([^）)]*)[）)]\s*$')        # 行末夹注
SEP = '\u3000'

# 每部书：底本、输出文件名、题名、作者、朝代、分卷层数（0 = 不分卷，1 = 一节一章，2 = 卷 + 章）
BOOKS = [
    dict(src='百家姓.txt', out='baijiaxing.json', title='百家姓', author='佚名', dynasty='宋', depth=0),
    dict(src='三字經.txt', out='sanzijing.json', title='三字經', author='王應麟', dynasty='宋', depth=0),
    dict(src='千字文.txt', out='qianziwen.json', title='千字文', author='周興嗣', dynasty='南北朝', depth=0),
    dict(src='弟子規.txt', out='dizigui.json', title='弟子規', author='李毓秀', dynasty='清', depth=1),
    dict(src='五字鑒.txt', out='wuzijian.json', title='五字鑒', author='李廷機', dynasty='明', depth=1),
    dict(src='急就章.txt', out='jijiuzhang.json', title='急就章', author='史游', dynasty='汉', depth=1),
    dict(src='李氏蒙求.txt', out='lishimengqiu.json', title='李氏蒙求', author='李瀚', dynasty='唐', depth=0),
    dict(src='幼學瓊林.txt', out='youxueqionglin.json', title='幼學瓊林', author='程登吉', dynasty='明', depth=1),
    dict(src='增廣賢文.txt', out='zengguangxianwen.json', title='增廣賢文', author='佚名', dynasty='明', depth=1),
]
ABSTRACTS = {
    'youxueqionglin': '《幼學瓊林》是中國古代兒童的啓蒙讀物，作者程允升。初爲明代西昌人程登吉（字允升）編著，'
                      '本名《幼學須知》，又稱《成語考》、《故事尋源》，清人鄒聖脈作了增補，改名爲《幼學瓊林》，'
                      '也叫《幼學故事瓊林》。',
    'zengguangxianwen': '《增廣賢文》爲中國古代兒童啓蒙書目，又名《昔時賢文》、《古今賢文》，作者未詳，'
                        '清代同治年間儒生周希陶曾重訂。底本另附《補遺增廣》一卷，本文件一併收入、分卷保存。',
}

# 底本讹字 → 正字。key 是「文件名 + 原行首十字」，只改第一次出现处；依据见 docs/蒙学重建.md。
FIXES = {
    # 《千字文》底本「劍號巨闕」写作「劒號巨闕」：「劒」是「劍」的异体字，
    # 底本通篇用正体，只此处误作异体，统一作「劍」。见 docs/蒙学重建.md。
    '千字文.txt': [('劒號巨闕', '劍號巨闕', '「劒」是「劍」的异体，底本通篇用正体「劍」，此处误作异体，统一作「劍」')],
}

CN_NUM = '〇一二三四五六七八九十'


def base22(key, size, taken):
    while True:
        digest = hashlib.blake2b(key.encode(), digest_size=16).digest()
        v = int.from_bytes(digest, 'big')
        out = ''
        for _ in range(size):
            v, r = divmod(v, 22)
            out = ALPHABET[r] + out
        if out not in taken:
            taken.add(out)
            return out
        size += 1


def cn2int(s):
    """一 十 十一 二十一 → 1 10 11 21。"""
    cn = {c: i for i, c in enumerate(CN_NUM)}
    cn['零'] = 0
    if '十' not in s:
        return int(''.join(str(cn[c]) for c in s))
    hi, _, lo = s.partition('十')
    return (cn[hi] if hi else 1) * 10 + (cn[lo] if lo else 0)


def split_note(line):
    """`閏餘成歲，律呂調陽。(唐人作「律召調陽」)` → (正文, 夹注)。"""
    m = NOTE.search(line)
    if not m:
        return line.strip(), None
    body = line[:m.start()].strip()
    note = m.group(1).strip()
    # 夹注本身带句读时（「綵，又作『采』、『彩』」）截到第一个「，」之前，只留异文
    return body, note


def parse(path, fix_rows):
    """→ [{'vol': 卷名, 'ch': 章名, 'lines': [(正文, 夹注)]}]；`vol`/`ch` 为 None 表示不分卷。"""
    secs, cur_vol = [], None
    for idx, raw in enumerate(open(path, encoding='utf-8')):
        line = raw.strip('\n').replace('\u3000', ' ').strip()
        if not line:
            continue
        # 《千字文》底本没有 `#` 书名行，首行「千字文〔梁〕敕員外散騎侍郎 周興嗣 次韻」是题款
        if idx == 0 and ' #' not in line and re.match(r'^\S{2,6}〔', line):
            continue
        # 「○ 第一章」是《急就章》底本的行款，不是 Markdown 标题，但起章节作用
        if not line.startswith('#') and re.match(r'^[○〇]\s*第[〇零一二三四五六七八九十]+章$', line):
            line = '## ' + line
        if line.startswith('#'):
            level = len(line) - len(line.lstrip('#'))
            head = re.sub(r'\s+', ' ', line.lstrip('#').strip())
            if level == 1:
                continue                                  # 书名 / 著者行：题名另给，跳过
            if '撰' in head or '著' in head:           # 「急就章 〔漢〕史游 撰」是著者行
                continue
            m = re.match(r'^[○〇]?\s*第([〇零一二三四五六七八九十]+)章$', head)
            if m:                                      # 「○ 第一章」是底本的行款，章次进题名
                secs.append({'vol': None, 'ch': f'第{cn2int(m.group(1))}章', 'lines': [], 'fixed': []})
            elif head.startswith('○'):                 # 只有「○」的装饰行，不是标题
                continue
            else:
                secs.append({'vol': None, 'ch': head, 'lines': [], 'fixed': []})
            continue
        if END_MARK.match(line):
            continue
        if not secs:                                      # 卷首无标题：整卷一章
            secs.append({'vol': None, 'ch': '正文', 'lines': [], 'fixed': []})
        body, note = split_note(line)
        for old, new, why in fix_rows:
            if old in body:
                body = body.replace(old, new, 1)
                secs[-1]['fixed'].append(dict(original=old, corrected=new, note=why))
                break
        secs[-1]['lines'].append((body, note))
    return secs


def build(book):
    src = os.path.join(ROOT, 'reference', book['src'])
    secs = parse(src, FIXES.get(book['src'], []))
    body, paras, variants, fixes = [], [], [], []
    for rec in secs:
        lines = []
        for text, note in rec['lines']:
            lines.append(text)
            if note:                                   # 夹注是异文，不是正文
                variants.append(dict(chapter=rec['ch'], line=text, note=note))
        body.extend(lines)
        fixes.extend(rec['fixed'])
        if book['depth'] == 0:
            paras.extend(lines)
        else:
            paras.append({'chapter': rec['ch'], 'paragraphs': lines})

    rec = {'title': book['title'], 'author': book['author'], 'dynasty': book['dynasty']}
    abstract = ABSTRACTS.get(book['out'][:-5])
    if abstract:
        rec['abstract'] = abstract
    rec['paragraphs'] = paras
    if variants:
        rec['variants'] = variants
    return rec, body, fixes


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--apply', action='store_true', help='写盘；否则只预演')
    ap.add_argument('--date', default=date.today().isoformat())
    args = ap.parse_args()

    taken, total_ch, records = set(), 0, []
    for book in BOOKS:
        rec, body, fixes = build(book)
        rec['id'] = base22(f"{rec['author']}|{rec['title']}|{''.join(body)}", 6, taken)
        chars = sum(len(p) for p in body)
        total_ch += chars
        print(f"{book['out']:<22}{rec['title']:<6}{rec['author']:<4}{len(body):>5} 句 {chars:>6} 字"
              f"{'  勘误 %d 处' % len(fixes) if fixes else ''}")
        records.append((book, rec, fixes))

    print(f'\n共 {len(records)} 部，{sum(len(r[1]["paragraphs"]) for r in records)} 个分卷/章，{total_ch} 字')
    if not args.apply:
        return

    for book, rec, fixes in records:
        rel = f"{DIR}/{book['out']}"
        path = os.path.join(ROOT, rel)
        text = json.dumps(rec, ensure_ascii=False, indent=2) + '\n'
        if not os.path.exists(path) or open(path, encoding='utf-8').read() != text:
            open(path, 'w', encoding='utf-8').write(text)
        lines = rec['paragraphs'] if book['depth'] == 0 else [x for c in rec['paragraphs'] for x in c['paragraphs']]
        entry = {
            'note': f"2026-11 依 repo 内 reference/{book['src']} 整本重新生成（issue #207）："
                    f"{len(rec['paragraphs'])} 个分卷/章、{len(lines)} 句、{sum(map(len, lines))} 字；"
                    "正文照底本逐行成段，行末夹注另收 variants；底本已逐字复核（韵语字数、对句、"
                    "夹注异文、繁体字形），讹字见 fixes，未与别的刻本对勘",
            'date': args.date,
            'reviewer': REVIEWER,
            'status': 'needs_review',
        }
        if fixes:
            entry['fixes'] = fixes
        pg.merge(rel, entry)
        print('→', rel)


if __name__ == '__main__':
    sys.exit(main())
