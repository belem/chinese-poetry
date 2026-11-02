#!/usr/bin/env python3
"""`reference/二十四史/春秋左氏传.txt` → `史书/春秋左氏传/zuozhuan.json`。

底本是简体排印本，经文（`【经】`）、传文（`【传】`）、无经之传三者都逐段带句读，
段间空一行；卷（公）与年两级标题各占一行：

    ========正文========
    隐公
    隐公元年
    【经】元年春王正月。三月，公及邾仪父盟于蔑。……
    【传】元年春，王周正月。不书即位，摄也。
    ……
    隐公二年
    ……

文件版式：

  * 一条记录一个「公+年」，255 年 255 条；题名作「左傳·隐公·隐公元年」（书名简称用繁体「左傳」，
    公与年照底本作简体）；
  * 底本在注家的「经/传」标记里另有体例，故不拆经、传两类，也不拆段：经文那一段以「【经】」起头，
    传文各段以「【传】」起头或直接起句，段内一字不动；
  * 底本有 7 处年下只剩抓取残渣（19 个佚题标签 `中秋`／`怀古`／…／`王维名句`，落在桓四、庄二、
    庄五、庄十五、庄十七、哀十九、哀廿二这几年的年号之下），这些年的经、传本身在底本里就整段丢了。
    照录为先删残渣，再把 `□□□□□□` 留在原处占位（与全库 `□` 表缺字的用法一致），不臆补经文；
    行内被切断的 4 处（庄十九、昭十六、昭十九、昭二十）同样用 `□□` 补在断处，断成两段的
    那一段不并回（并回就改了底本的段序）；
  * 还有一处底本自身的错字：`将归Ｖ请少待之` 的全角 `Ｖ` 是衍文，删（底本与 repo 内
    `works_8.json` 是同一份 crawled 原文）；`{轻金}而乘于他车`、`夫{山乙}无备` 的 `{…}`
    是未编码生僻字的既定写法（`〔占戈〕` 一类），照录；
  * 底本另有三类字形问题本批照录、记在 docs 里待对勘：`ぶ` 实为「㔻」（ぶ郑、ぶ豹、高无ぶ…）、
    `ⅰⅱ…ⅷ` 实为卦画（ⅵⅰ 即䷍䷀）、`\ue26a` 是私用区空字（「淫乐之」下缺一字）；
  * `author` 记「左丘明」，`dynasty` 记「先秦」（作者朝代，`authors/authors.json` 记「周」）；
  * `id` 规则同 `scripts/shidian/convert.py`（author|title|正文 blake2b）。

    python3 scripts/import_zuozhuan_reference.py            # 写文件
    python3 scripts/import_zuozhuan_reference.py --check    # 只比对，不写
"""
import argparse
import hashlib
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = 'reference/二十四史/春秋左氏传.txt'
OUT = '史书/春秋左氏传/zuozhuan.json'
BOOK = '左傳'
AUTHOR = '左丘明'
DYNASTY = '先秦'
TOTAL_YEARS = 255
END = '〔全文完〕'

DUKES = ('隐公', '桓公', '庄公', '闵公', '僖公', '文公',
         '宣公', '成公', '襄公', '昭公', '定公', '哀公')
YEAR_RX = re.compile(r'^(' + '|'.join(DUKES) + r')([元一二三四五六七八九十]+年)$')

# 底本年下的佚题标签（抓取残渣）。整段连续出现，19 个一组，共 7 处
JUNK_TAGS = set('中秋 怀古 爱国 立志 田园 学问 七夕 送别 边塞 思乡离愁 友谊爱情 '
                '端午诗句 事理哲理 白居易诗句 诗经名句 李白诗句 杜甫诗句 毛泽东名句 王维名句'.split())

FIXES = (
    ('将归Ｖ请少待之', '将归请少待之'),          # 底本混入的全角拉丁字母，作衍文删
    ('「必祁大夫。。」', '「必祁大夫。」'),        # 襄廿一叠句号
    ('亦自杀也，而葬于絰', '亦自杀也，而葬于絰□□'),   # 庄十九行末被切断
    ('起亦以知郑志。」子', '起亦以知郑志。」子□□'),   # 昭十六行末被切断
    ('龙斗于时门之外洧渊。国人请为', '龙斗于时门之外洧渊。国人请为□□'),   # 昭十九行末被切断
    ('使华寅乘贰车。及公宫，鸿', '使华寅乘贰车。及公宫，鸿□□'),   # 昭二十行末被切断
)
LOST = ('□' * 6, '底本此年经、传整段失落，只余抓取残渣')


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


def parse(path):
    text = open(path, encoding='utf-8').read()
    body = text[text.index('========正文========'):]
    recs, duke, cur = [], None, None
    for raw in body.split('\n'):
        line = raw.strip()
        if not line or line.startswith('========'):
            continue
        if line in DUKES:
            duke = line
            continue
        m = YEAR_RX.match(line)
        if m:
            assert m.group(1) == duke, f'年号与公不合：{line}（当前 {duke}）'
            cur = {'duke': duke, 'year': m.group(2), 'paragraphs': [],
                   'junk': False}
            recs.append(cur)
            continue
        if line in JUNK_TAGS:
            # 残渣出现在年号之后，属本年：底本在庄三、庄六、庄十六、庄十八、哀二十、
            # 哀廿三、桓五这几年的年号下多插了一串佚题标签，正文仍在其后
            cur['junk'] = True
            continue
        assert cur is not None, f'正文出现在年号之前：{line[:30]}'
        for wrong, right in FIXES:
            line = line.replace(wrong, right)
        if line == END:                               # 底本行尾的收尾标记
            continue
        cur['paragraphs'].append(line)
    return recs


def build(recs):
    taken, out = set(), []
    dukes = []
    for r in recs:
        if not dukes or dukes[-1] != r['duke']:
            dukes.append(r['duke'])
    assert tuple(dukes) == DUKES, f'公次不合：{dukes}'
    assert len(recs) == TOTAL_YEARS, f'年数 {len(recs)}'
    for r in recs:
        if r['junk'] and not r['paragraphs']:
            r['paragraphs'] = [LOST[0]]
        assert r['paragraphs'], f"空年：{r['duke']}{r['year']}"
        title = f"{BOOK}·{r['duke']}·{r['duke']}{r['year']}"
        rec = {'author': AUTHOR, 'title': title, 'dynasty': DYNASTY,
               'paragraphs': r['paragraphs']}
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
    nojing = sum(1 for r in recs if not r['paragraphs'][0].startswith('【经】'))
    print(f'{len(recs)} 年，{sum(len(r["paragraphs"]) for r in recs)} 段，{chars} 字，'
          f'无经之年 {nojing}')
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
