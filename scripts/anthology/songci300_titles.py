#!/usr/bin/env python3
"""《宋词三百首》PR A：篇目与作者，按 repo 内底本 `reference/宋詞三百首` 逐条订正。

篇目口径（2026-11 修订，替代 `retitle_songci300.py` 的「词牌·正文首句」一律式）：

  1. 底本给了小题 → `词牌·小题`（燕山亭·北行见杏花）
  2. 底本只有词牌 → `词牌·正文首句`（首句取本记录正文前 12 个汉字，按本记录自己的简繁）
  3. 底本词牌与本库词牌是同一个调的两种写法 → 用**本库**词牌接小题/首句，不为一字之差改名

小题本身就是这本书给这一首的标识，第 1 条不必再叠首句 —— 这正是 issue #200 问的
「燕山亭·北行見杏花 要不要变成 燕山亭·北行見杏花·裁剪冰綃」的答案：不要。

`rhythmic` 只在一处动：`ci.song.22000.json#1054` 的「老薄幸」是「吕滨老／薄幸」被断错行
（作者写成「吕滨」、词牌成了「老幸」的半截），改回「薄幸」。其余调名的别写一律不动，
理由逐条记在 docs/宋词三百首勘正.tsv 的「说明」列。

作者只改一件事：`authors/authors.json` 里查得到的规范名才算认得，认得的才落库 ——
「吕滨→吕渭老」「鲁逸仲→孔夷」这种把别号并到本名、是库内署名本身的错，改；
「陆睿/陆叡」是异体一对，authors 表里没有「陸叡」，不改；
《生查子》《蝶恋花》那几条是《全宋词》的归属异说，两存，不改。

  python3 scripts/anthology/songci300_titles.py                  # 预演
  python3 scripts/anthology/songci300_titles.py --apply --date YYYY-MM-DD --reviewer <名字>
"""
import argparse
import csv
import json
import os
import re
import sys
import unicodedata

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import progress as pg  # noqa: E402
from anthology.patch_json import patch  # noqa: E402
from opencc import OpenCC  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
BOOK = os.path.join(ROOT, 'reference', '宋詞三百首')
TSV = os.path.join(ROOT, 'docs', '宋词三百首勘正.tsv')
TAG = '宋词三百首'
SEP = '·'
RHYTHM_SEP = re.compile('[・·]')
HAN = re.compile(r'[\u3400-\u9fff\U00020000-\U0003ffff\ue000-\uf8ff□〇]')
AUTHORS = json.load(open(os.path.join(ROOT, 'authors', 'authors.json'), encoding='utf-8'))
S2T, T2S = OpenCC('s2t'), OpenCC('t2s')

# 作者名的两种写法：改的是库内署名本身的错（断行、别号），authors/ 一个字不动。
# 归属异说（同一首《全宋词》两收）不改，见 docs/宋词三百首勘正.md。
AUTHOR_FIX = {
    173: ('吕滨', '吕渭老'),      # 「吕滨老」被断成「吕滨／老」，词牌也跟着成了「老薄幸」
    175: ('鲁逸仲', '孔夷'),      # 鲁逸仲是孔夷别号
}
# `rhythmic` 只在断行这一处动，其余调名别写不动
RHYTHMIC_FIX = {173: '薄幸'}


def author_names():
    out = set()
    for a in (AUTHORS.get('authors') or AUTHORS if isinstance(AUTHORS, dict) else AUTHORS):
        if isinstance(a, dict):
            for k in ('name', 'short_name'):
                if a.get(k):
                    out.add(a[k])
    return out


NAMES = author_names()


def is_simplified(rec):
    """该记录是不是简体一批。

    按正文前 20 个汉字里简繁有别的字判断：`ci.song.23000.json` 是繁体一批，
    但它的作者字段写的是简体（「苏轼」），不能一个文件一个文件地猜。
    """
    txt = ''.join(HAN.findall(''.join(p for p in rec['paragraphs'] if isinstance(p, str))))
    # ci.song.23000.json 里同一批正文一简一繁、作者字段又都是简体，前 20 字看不出简繁时往后多看几段
    probe = txt[:20]
    if sum(S2T.convert(c) != c for c in probe) < 3:
        probe = txt[:120]
    return S2T.convert(probe) != probe


def load_book():
    """底本 → [(目次号, 标题, 作者)]。标题是 `### 词牌[·小题] / 作者` 的前半。"""
    blocks = re.split(r'^### ', open(BOOK, encoding='utf-8').read(), flags=re.M)[1:]
    out = []
    for no, b in enumerate(blocks, 1):
        head = b.split('\n')[0]
        title, author = head.rsplit(' / ', 1)
        out.append((no, title.strip(), author.strip()))
    return out


def split_title(title):
    """底本标题 → (词牌, 小题)。底本把词牌注释并进标题的两条（漁家傲）只取词牌。"""
    title = re.sub(r'\((.+)\)$', lambda m: '' if m.group(1).startswith('漁家傲') else m.group(0), title)
    parts = title.split(SEP, 1)
    return parts[0].strip(), (parts[1].strip() if len(parts) > 1 else '')


def same_rhythm(book, lib):
    """词牌名的同一写法：简繁统一、去标点后相等（木蘭花 / 木兰花、鎖窗寒 / 琐窗寒）。"""
    def norm(s):
        return T2S.convert(''.join(ch for ch in s if not unicodedata.category(ch).startswith('P') and not ch.isspace()))
    a = norm(book)
    return bool(a) and a == norm(lib)


def lib_rhythm(rec):
    return SEP.join(p.strip() for p in RHYTHM_SEP.split(rec['rhythmic']) if p.strip())


def fix_script(text, rec):
    """把底本小题的简繁改成与**本记录正文**一致。

    ci.song.23000.json 里两条正文一简一繁、作者字段又都写简体，不能按文件判；逐字看正文里怎么写：
    正文里就这一个字（「欢」）就用它，自己的写法在正文里没有（「飲」）才按整条简繁推定。
    """
    own = set(HAN.findall(''.join(p for p in rec['paragraphs'] if isinstance(p, str))))
    simp = is_simplified(rec)
    out = []
    for ch in text:
        if ch in own:
            out.append(ch)
        else:
            cand = T2S.convert(ch) if simp else S2T.convert(ch)
            out.append(cand if cand in own or S2T.convert(cand) not in own else S2T.convert(cand))
    return ''.join(out)


def head_text(rec):
    raw = ''.join(p for p in rec['paragraphs'] if isinstance(p, str))
    return ''.join(HAN.findall(raw))[:12]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--apply', action='store_true')
    ap.add_argument('--verbose', action='store_true', help='逐条列出改动')
    ap.add_argument('--date')
    ap.add_argument('--reviewer')
    args = ap.parse_args()

    book = {no: (title, author) for no, title, author in load_book()}
    rows = list(csv.DictReader(open(TSV, encoding='utf-8'), delimiter='\t'))
    files, changed, notes = {}, {}, []
    for r in rows:
        no = int(r['目次'])
        if not r['库位置']:
            continue                      # 库内缺的 11 首归 PR C
        rel, idx = r['库位置'].rsplit('#', 1)
        idx = int(idx)
        if rel not in files:
            files[rel] = json.load(open(os.path.join(ROOT, rel), encoding='utf-8'))
        rec = files[rel][idx]
        old_title = rec.get('title') or ''
        edits = {}

        # 词牌只取本库的写法：木蘭花/玉楼春、玉蝴蝶/玉胡蝶、六么令/六幺令 都是同一调的两种写法，
        # 为一字之差改名不值当；底本的写法在 tsv 的「底本标题」列里留档
        rhythm, sub = split_title(book[no][0])
        rec_rhythm = RHYTHMIC_FIX.get(no) or lib_rhythm(rec)

        body = head_text(rec)
        title = f'{rec_rhythm}{SEP}{fix_script(sub, rec) or body}'
        if title != old_title:
            edits['title'] = title
        if no in RHYTHMIC_FIX and rec['rhythmic'] != RHYTHMIC_FIX[no]:
            edits['rhythmic'] = RHYTHMIC_FIX[no]

        old_author = rec['author']
        new_author = T2S.convert(old_author)
        if no in AUTHOR_FIX:
            assert AUTHOR_FIX[no][0] == old_author, (no, old_author)
            new_author = AUTHOR_FIX[no][1]
        if new_author != old_author:
            if new_author not in NAMES and S2T.convert(new_author) not in NAMES:
                notes.append(f'第 {no} 首：{old_author} → {new_author}，但 authors.json 里查不到这个规范名，跳过')
            else:
                edits['author'] = new_author

        if edits:
            changed.setdefault(rel, []).append((no, idx, rec, edits))

    if args.verbose:
        for rel in sorted(changed):
            print(f'{rel}: {len(changed[rel])} 条')
            for no, idx, rec, edits in changed[rel]:
                bits = [f'{k} {rec.get(k) or "（无）"} → {v}' for k, v in edits.items()]
                print(f'    #{idx} 第{no}首  ' + '；'.join(bits))
    print(f'合计 {sum(len(v) for v in changed.values())} 条记录改动，涉及 {len(changed)} 个文件')
    for n in dict.fromkeys(notes):
        print('  ! ' + n)
    if not args.apply:
        return
    if not (args.date and args.reviewer):
        sys.exit('--apply 需要 --date 与 --reviewer')
    for rel in sorted(changed):
        ops = changed[rel]
        patch(rel, {idx: edits for no, idx, rec, edits in ops})
        fixes = []
        for no, idx, rec, edits in ops:
            if 'title' in edits:
                fixes.append({'original': rec.get('title') or '（无）', 'corrected': edits['title'],
                              'note': f'第 {no} 首；底本 reference/宋詞三百首'})
            if 'author' in edits:
                fixes.append({'original': rec['author'], 'corrected': edits['author'],
                              'note': f'第 {no} 首；库内署名错（断行／别号），authors/ 未动'})
            if 'rhythmic' in edits:
                fixes.append({'original': rec['rhythmic'], 'corrected': edits['rhythmic'],
                              'note': f'第 {no} 首；「吕滨老／薄幸」断错行，词牌被切掉半截'})
        pg.merge(rel, dict(status='fixed', reviewer=args.reviewer, date=args.date, fixes=fixes,
                           note=f'《宋词三百首》篇目按底本统一为「词牌·小题」，无小题的作「词牌·正文首句」：{len(ops)} 条。正文未动。'))
    print(json.dumps(pg.write_index()['stats'], ensure_ascii=False))


if __name__ == '__main__':
    main()
