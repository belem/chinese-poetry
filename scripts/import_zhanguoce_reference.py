#!/usr/bin/env python3
"""`reference/二十四史/战国策.txt` → `史书/战国策/zhanguoce.json`。

底本是简体排印本，三十三卷、501 个 `○` 起首的章头；卷题顶格一行，章题以 `○` 起首、
紧接正文，段间不断行，正文逐段带句读：

    卷八 齐一
    ○楚威王战胜于徐州楚威王战胜于徐州，欲逐婴子于齐。……
    卷九 齐二
    ……

文件版式：

  * 一章一条记录（501 条），题名作「戰國策·卷一 东周·秦兴师临周求九鼎」：
    卷次照底本（简体，含「卷一 东周」这样带国别的），章题取底本原题；
  * 章题与正文同在一行，切分靠「题干首字重出」：`○秦兴师临周求九鼎秦兴师临周而求九鼎，`
    题干是「秦兴师临周求九鼎」，第 1 个与题干首字相同的字起是正文；497 章走这条规则；
  * 走不了重出规则的 4 类写死在脚本里：4 处章题独成一行（`HEAD_ONLY`）、
    2 处题头脱字或超过 15 字（`SPLIT`）、1 处题头首二字即正文前二字（`SPLIT_TEXT`）；
  * 底本有 5 处卷题被排进了上一章的行尾（`……是以遣之也。’”卷二 西周`），
    卷二 西周、卷十 齐三、卷十七 楚四、卷十八 赵一、卷二十五 魏四同此，行尾的卷题先摘出来再断章；
  * 底本有一处把下一章的 `○` 排在上一章的行尾（卷一《谓薛公》末），切开后上一章行尾多一个 `○`，去掉；
  * 底本有 3 处叠句号（`……燕赐我也。。`、`……齐其闻之矣。。`、`……大王不好人。。`），收敛成一个；
  * 《楚考烈王无子》末段抄进了两段他书按语（`续：《越绝书》…`「其画策终始，信如此…」），
    不是《战国策》正文，删（`DROP_PARA`）；方括号的 `──`（安平君、李园两处夹注性的破折号）照录；
  * 底本用 `{…}` 与 `<…>` 两种记法标未编码的生僻字：`{殸车}`、`{亦水}`、`{艹陵}`、`{苻廾}`、
    `{股目}` 是全库既定的 `{…}` 写法，照录；`<…>` 的 8 个字头（`<广鼻>`、`<黄重>`、`<吾午>`、
    `<户卯>`、`<鱼卷>`、`<口夭>`、`<马戋>`、`<鸟旗>`）不是全库写法，改写成 `{…}`，字不补；
  * 底本另有 5 个私用区码位（U+E1E2、U+E844×2、U+E859×2），在《东周列国志》同段已定为
    「犴」「周最」的「最」「史鰌」的「鰌」，照那个结论写成 `{犴}`、`{最}`、`{鰌}`；
  * `author` 记「刘向」（西汉末编订，与 `authors/authors.json` 的 dynasty「汉」一致），
    目录里的 `dynasty` 记「先秦」（书中所记之事），与《春秋左氏传》同一口径，理由见 docs；
  * `id` 规则同 `scripts/shidian/convert.py`（author|title|正文 blake2b）。

    python3 scripts/import_zhanguoce_reference.py            # 写文件
    python3 scripts/import_zhanguoce_reference.py --check    # 只比对，不写
"""
import argparse
import hashlib
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = 'reference/二十四史/战国策.txt'
OUT = '史书/战国策/zhanguoce.json'
BOOK = '戰國策'
AUTHOR = '刘向'
DYNASTY = '先秦'
TOTAL_CHAPTERS = 501
TOTAL_JUAN = 33

JUAN_RX = re.compile(r'卷[一二三四五六七八九十]+ \S+$')
END = '刘向书录'

# 章题独成一行：下一行才是正文
HEAD_ONLY = {155, 321, 377, 723}
# 章题用字与正文首字不同，重出规则失效，逐条给定切分
SPLIT = {
    # 底本脱字：`○穰侯攻大梁侯攻大梁，乘北郢`，正文自「侯攻大梁」起
    1007: ('穰侯攻大梁', '侯攻大梁'),
    1232: ('昌国君乐毅为燕昭王合五国之兵而攻齐', '昌国君乐毅为燕昭王合五国之兵而攻齐，'),
}
# 一行里并排两三章时，块内章题仍靠重出规则切；重出规则在 `○卫人迎新妇为人迎新妇`
# 这类「题头首二字即正文前二字」的情形下失效，逐条给定整段前缀（题头 + 正文首句起头）
SPLIT_TEXT = {
    1301: ('卫人迎新妇', '为人迎新妇'),   # 题头 5 字，正文自「为人迎新妇」起
}
# 底本私用区（U+E1E2、U+E844、U+E859）：《东周列国志》同段已定为「犴」「最」「鰌」，字不补，只换成 {} 写法
PUA = {'\ue1e2': '{犴}', '\ue844': '{最}', '\ue859': '{鰌}'}
FIXES = (
    ('。。', '。'),          # 卷九、卷十、卷十九三处叠句号
    ('会“', '会'),          # 卷二十八 韩三《东孟之会》：底本章头 `○东孟之会“东孟之会，` 引号
    ('赵足“', '赵足'),      # 卷三十 燕二《奉阳君千朱讙与赵足》：同上，切题时把引号带进了章题
)
HEAD_MARK = chr(0x25CB)   # 底本每章题前的 `○`
MAX_TITLE = 15              # 题干最长 15 字（`燕王喜使栗腹以百金为赵孝成王寿` 恰 15）
# 底本在《楚考烈王无子》的末段抄进了两段他书按语（`续：《越绝书》…`「其画策终始，信如此…」），
# 不是《战国策》正文，亦非本库体例里的注，删；章的其余段落不动
DROP_PARA = (re.compile(r'^续：《越绝书》'), re.compile(r'^其画策终始，信如此'))


def make_id(author, title, body, taken):
    key = f'{author}|{title}|{"".join(body)}'
    size = 6
    while True:
        digest = hashlib.blake2b(key.encode(), digest_size=16).digest()
        v = int.from_bytes(digest, 'big')
        out = ''
        for _ in range(size):
            v, r = divmod(v, 22)
            out = '0123456789abcdefghijklmnopqrstuv'[r] + out
        if out not in taken:
            taken.add(out)
            return out
        size += 1


def clean(text):
    for wrong, right in FIXES:
        text = text.replace(wrong, right)
    for bad, good in PUA.items():
        text = text.replace(bad, good)
    text = re.sub(r'<([^<>]{1,8})>', r'{\1}', text)     # <广鼻> → {广鼻}
    return text


def cut_tail_volume(text, lineno):
    """摘下卷题：整行是卷题，或卷题被排进了上一章的行尾。返回（行正, 卷题）。"""
    m = JUAN_RX.search(text)
    if not m:
        return text, None
    return text[:m.start()].rstrip(), m.group()


def split_head(raw, lineno):
    """把 `○…` 那一行切成（章题, 正文首段）。

    规则是「题干首字重出」：第 1 个与题干首字相同的字起是正文。
    底本 501 章里有 497 章走这条；走不了的四类逐条列在下面三张表里。
    """
    if lineno in SPLIT_TEXT and raw.startswith(SPLIT_TEXT[lineno][0]):
        head, body_head = SPLIT_TEXT[lineno]
        k = raw.index(body_head, len(head))
        return head, raw[k:]
    if lineno in SPLIT:
        head, _ = SPLIT[lineno]
        k = raw.index(head) + len(head)
        return head, raw[k:]
    if lineno in HEAD_ONLY:
        return raw.rstrip('。'), ''
    c0 = raw[0]
    k = raw.find(c0, 1)
    assert 0 < k <= MAX_TITLE, f'{lineno}: 章题切不开 {raw[:30]}'
    return raw[:k], raw[k:]


def parse(path):
    lines = open(path, encoding='utf-8').read().split('\n')
    # 底本头 40 行是目录，目录里也有「卷一 东周」，正文自最后一处「卷一 东周」起，
    # 止于卷末的《刘向书录》
    start = max(i for i, l in enumerate(lines[:60]) if l.strip().startswith('卷一 东周'))
    stop = lines.index(END, start)
    chapters, juan = [], None
    for i in range(start, stop):
        text = lines[i].strip()
        # 卷题（`卷八 齐一`）或行尾卷题（`……’？”卷二 西周`）先摘出来
        text, tail = cut_tail_volume(text, i)
        if tail:
            juan = tail
        if not text:
            continue
        if text.count(HEAD_MARK):
            # 一行里排了几章：每章以 `○` 起首，章题与正文同在一行
            for piece in text.split(HEAD_MARK)[1:]:
                if not piece.strip():
                    continue
                head, body = split_head(piece, i)
                chapters.append({'juan': juan, 'head': head, 'paras': [body]})
        else:
            assert chapters, f'{i}: 正文出现在卷题之前'
            chapters[-1]['paras'].append(text)
    for ch in chapters:
        ch['paras'] = [clean(p) for p in ch['paras']
                       if p and not any(rx.match(p) for rx in DROP_PARA)]
        assert ch['paras'], f'{ch["juan"]}·{ch["head"]}: 空章'
    # 底本有一处把下一章的 `○` 排在上一章的行尾（`……齐王谁与为其国？”○齐听祝弗……`），
    # 切开后上一章的行尾多出一个 `○`，去掉；章本身已经在下一条里
    for ch in chapters:
        last = ch['paras'][-1]
        if last.endswith(HEAD_MARK):
            ch['paras'][-1] = last[:-1]
    return chapters

def build(chapters):
    assert len(chapters) == TOTAL_CHAPTERS, f'章数 {len(chapters)}'
    order = []
    for ch in chapters:
        if not order or order[-1] != ch['juan']:
            order.append(ch['juan'])
    assert len(order) == TOTAL_JUAN, f'卷数 {len(order)}'
    taken, out = set(), []
    for ch in chapters:
        # 章题与正文同一支笔：`<吾午>` 这类记法在题里也要写成 `{吾午}`
        title = clean(f"{BOOK}·{ch['juan']}·{ch['head']}")
        rec = {'author': AUTHOR, 'title': title, 'dynasty': DYNASTY,
               'paragraphs': ch['paras']}
        rec['id'] = make_id(AUTHOR, title, rec['paragraphs'], taken)
        out.append(rec)
    assert len({r['title'] for r in out}) == len(out), '题名重复'
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--check', action='store_true', help='只比对现有文件，不写')
    args = ap.parse_args()
    recs = build(parse(os.path.join(ROOT, SRC)))
    text = json.dumps(recs, ensure_ascii=False, indent=2) + '\n'
    dst = os.path.join(ROOT, OUT)
    chars = sum(len(p) for r in recs for p in r['paragraphs'])
    print(f'{len(recs)} 章，{sum(len(r["paragraphs"]) for r in recs)} 段，{chars} 字，'
          f'卷 {len({r["title"].split("·")[1] for r in recs})}')
    if args.check:
        old = open(dst, encoding='utf-8').read()
        print('一致' if old == text else '不一致')
        return 0 if old == text else 1
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    open(dst, 'w', encoding='utf-8').write(text)
    print('→', OUT)
    return 0


if __name__ == '__main__':
    sys.exit(main())
