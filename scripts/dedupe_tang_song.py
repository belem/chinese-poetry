#!/usr/bin/env python3
"""《全唐诗》↔《全宋诗》作者不同的重出：同一首被两书各收一次，按归属删误收的那条。

两书之间正文前 16 字相同的组 976 个（`t2s` 归一、去非汉字），三种情形分开处理：

  同作者 / 同一人的两种署名   726 组 —— 不在本脚本里：同作者那份是 `dedupe_tang.py` 的事，
                              佛门「释」字头一类的异写，留待下一批按「同人异写」处理。
  作者不同                    250 组 —— 才是这一批。**不是一律删**：
    a. 同一人、两种名讳       《全宋诗》作「張佖」，《全唐诗》作「張泌」；宋太祖／趙匡胤、
                              李從善／韓王從善是尊号与本名。删《全宋诗》那条。
    b. 一人误收进另一人集子   唐彥謙 22 首混入戴表元《剡源集》、朱存《金陵覽古》记在杨备名下。
                              两者都传世、只差几个字，按「诗归本主」删《全宋诗》那条。
    c. 归属异说               《宮詞》王珪／花蕊夫人、《步虛詞》宋徽宗／杜光庭、
                              《金丹詩訣》陳楠／青霞子、宋高宗题画诗与权德舆韦应物白居易孟郊……
                              两说并传，**一条不动**，按「一作某」互挂 `tags`。

删的依据是识典古籍（shidianguji.com）卷页，逐组记在 `docs/全唐诗全宋诗异作者.tsv` 的 `note` 列。

删哪一条
--------
统一删《全宋诗》那条：这一批的组里，《全唐诗》那条题名更全、`notes`/`prologue` 更多，
且《全宋诗》大量是宋人总集（《宋詩紀事》等）转抄后按作者编次的二次文献。例外：
《全宋诗》那条带 `tags`（如「庐山」）而《全唐诗》那条不带时，仍删《全宋诗》——
`tags` 是数据集自己打的，不是底本信息。

用法：
  python3 scripts/dedupe_tang_song.py            # 预演：逐组打印取舍
  python3 scripts/dedupe_tang_song.py --apply --date YYYY-MM-DD --reviewer <名字>
"""
import argparse
import csv
import glob
import json
import os
import re
import sys
from datetime import date

from opencc import OpenCC

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import progress as pg  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
T2S = OpenCC('t2s')
HAN = re.compile(r'[^\u4e00-\u9fff]')
BOOK_TANG = '唐/诗/全唐诗'
BOOK_SONG = '宋/诗/全宋诗'
OUT = 'docs/全唐诗全宋诗异作者.tsv'
PREFIX = 16

# 同一人、两种名讳。右为《全宋诗》的写法，左为《全唐诗》的写法。
ALIAS = {
    ('張泌', '張佖'): '張佖即張泌，《全宋詩》别作佖，《全唐詩》作泌',
    ('趙匡胤', '宋太祖'): '宋太祖趙匡胤，尊号与本名',
    ('韓王從善', '李從善'): '李從善封韓王，《全唐詩》题封爵，《全宋詩》题本名',
    ('江景防', '江景房'): '「防」「房」形近，雍正《開化縣誌》作江景房',
    ('張隱', '張隠'): '「隱」「隠」正俗字，《太平廣記》作張隱',
    ('包佶', '包信'): '「佶」「信」形近，《全宋詩》訛作信',
    ('雍陶', '雍鳴'): '《全宋詩》誤作雍鳴，雍陶《小桃源詩》',
    ('曉巒', '釋楚巒'): '曉巒即釋楚巒，法名前加「釋」',
    ('廖匡齊', '廖齊'): '廖匡齊，宋人避太祖諱省「匡」',
    ('來鵬', '來氏'): '來鵬，唐代女冠，《全宋詩》作來氏',
    ('越溪楊女', '楊氏'): '越溪楊女，《全宋詩》省作楊氏',
    ('李節度姬', '李氏'): '李節度姬，《全宋詩》省作李氏',
    ('李貞白', '朱貞白'): '李貞白，《全宋詩》訛作朱貞白',
    ('韓琮', '韓綜'): '韓琮，《全宋詩》訛作韓綜',
}

# 一人误收进另一人集子：删《全宋诗》那条
MISATTRIB = {
    '唐彥謙': '唐彥謙詩混入戴表元《剡源集》，兩書並收，《全宋詩》誤以爲戴作',
    '朱存': '朱存《金陵覽古》組詩，《六朝事跡編類》一作楊修，兩書並收',
    '花蕊夫人徐氏': '',   # 归属异说，见 keep_both
}

# 归属异说：两说并传，一条不动
KEEP_BOTH = {
    ('花蕊夫人徐氏', '王珪'): '《宮詞》百首，《華陽集》系王珪，《全唐詩》系花蕊夫人，',
    ('杜光庭', '宋徽宗'): '《步虛詞》，《太上黃籙齋儀》系杜光庭，《全宋詩》系宋徽宗，',
    ('青霞子', '陳楠'): '《龍虎元旨歌》，《道藏》託名青霞子，《翠虛篇》系陳楠，',
    ('張果', '陳楠'): '《金虎白龍詩》，《道藏》系張果，《翠虛篇》系陳楠，',
    ('權德輿', '宋高宗'): '宋高宗題畫詩，實為權德輿《勅賜長壽酒》，見《南宋院畫錄》，',
    ('韋應物', '宋高宗'): '宋高宗題畫詩，見《南宋院畫錄》，',
    ('白居易', '宋孝宗'): '宋孝宗題畫詩，見《南宋院畫錄》，',
    ('太宗皇帝', '宋高宗'): '宋高宗書《秋日》，見《南宋院畫錄》，',
}

# 其余组：识典古籍检索也定不了，两存并挂互挂 tags，理由写进 TSV
NEED_REVIEW = {}


# 《全宋诗》还沿用了《全唐诗》里佛徒名号加「釋」的做法：释延寿／延寿、释赞宁／赞宁……
# 数据里不带「釋」的那条在, 带「釋」的那条是同一个人, 按同一人处理。
BUDDHIST = True


def strip_shi(a):
    return (a or '').lstrip('釋释')


# 逐组人工判：识典古籍检不到的、以及要说明保留理由的。《宋》作者 + 《宋》题名前缀 定位，
# 值 = (判定, 说明)；判定 keep 表示两存不动（按「一作某」互挂 tags），drop 表示删《全宋诗》那条。
MANUAL = {
    ('王珪', '宮詞'): ('keep', '《宮詞》百首，《華陽集》卷五系王珪，《全唐詩》卷七百九十八系花蕊夫人；'
                              '《三家宮詞》《兩宋名賢小集》《石倉歷代詩選》皆題王珪，兩說並傳'),
    ('宋徽宗', '步虛詞'): ('keep', '《太上黃籙齋儀》（杜光庭）與《玉音法事》《道門通教必用集》並收，'
                                  '《全宋詩》系宋徽宗，《全唐詩》系杜光庭；兩說並傳'),
    ('陳楠', '金丹詩訣'): ('keep', '《龍虎元旨》（託名青霞子）、《內丹祕訣·金虎白龍詩》（張果）'
                                  '與《翠虛篇》（陳楠）並收，宋人編《翠虛篇》即收此訣；兩說並傳'),
    ('楊皇后', '宮詞  其二一'): ('keep', '《武林舊事》諸本並題楊皇后，與《全唐詩》無名氏《宮詞》同文；'
                                        '宮詞組詩多首互見，兩存'),
    ('黃宣', '應制詠菊'): ('keep', '廣宣即僧廣宣，《全唐詩》題廣宣、《全宋詩》題黃宣，'
                                  '宋人總集（《唐僧弘秀集》系統）作黃宣，兩說並傳，兩存'),
    ('顧逢', '贈僧'): ('keep', '《全唐詩》題羅鄴《贈僧》，《全宋詩》題顧逢《贈僧》，'
                               '識典古籍所見兩宋總集兩說並存，兩存'),
    ('范仲淹', '贈廣宣大師'): ('drop', '《全唐詩》作曹松《贈廣宣大師》，范仲淹集不載，'
                                       '《宋詩紀事》亦未收，為《全宋詩》誤系'),
    ('晏殊', '社日'): ('drop', '《全唐詩》作韋應物《社日寄崔都水及諸弟羣屬》，晏殊《珠玉集》不載，'
                               '《全宋詩》誤系'),
    ('梅堯臣', '自急流口至長蘆江入金陵'): ('drop', '《景定建康志》卷三十七明題杜牧《金陵》，'
                                                  '《全宋詩》誤系梅堯臣'),
    ('強至', '新秋夜月寄故人'): ('drop', '《全唐詩》作權德輿《新秋月夜寄故人》，強至《祠部集》不載，'
                                        '《全宋詩》誤系'),
}


def manual(song, tang):
    sa, st = song[2].get('author'), song[2].get('title') or ''
    for (a, t), v in MANUAL.items():
        if sa == a and st.startswith(t):
            return v
    return None


def han(s):
    return HAN.sub('', T2S.convert(s or ''))


def body(rec):
    return han(''.join(rec.get('paragraphs') or []))


def load(rel):
    with open(os.path.join(ROOT, rel), encoding='utf-8') as fp:
        return json.load(fp)


def dump(rel, data):
    """按原文件排版写回，只让改动的几条进 diff。"""
    path = os.path.join(ROOT, rel)
    raw = open(path, encoding='utf-8').read()
    m = re.search(r'\n( +)\S', raw)
    indent = len(m.group(1)) if m else 2
    out = json.dumps(data, ensure_ascii=False, indent=indent) + ('\n' if raw.endswith('\n') else '')
    src = raw.split('\n')
    out = '\n'.join(r + (' ' if i < len(src) - 1 and src[i].endswith(' ') else '')
                    for i, r in enumerate(out.split('\n')))
    with open(path, 'w', encoding='utf-8') as fp:
        fp.write(out)


def files_of(book):
    pat = os.path.join(ROOT, book, 'poet.*.json')
    fs = [os.path.relpath(f, ROOT) for f in glob.glob(pat)]
    return sorted(fs, key=lambda f: int(re.search(r'\.(\d+)\.json$', f).group(1)))


def corpus():
    data = {}
    recs = []
    for book in (BOOK_TANG, BOOK_SONG):
        for rel in files_of(book):
            data[rel] = load(rel)
            for i, rec in enumerate(data[rel]):
                b = body(rec)
                if len(b) >= PREFIX:
                    recs.append((rel, i, rec, b))
    return data, recs


def groups_of(recs):
    g = {}
    for rel, i, rec, b in recs:
        g.setdefault(b[:PREFIX], []).append((rel, i, rec, b))
    out = []
    for key, items in g.items():
        if not any(rel.startswith(BOOK_TANG + '/') for rel, *_ in items):
            continue
        if not any(rel.startswith(BOOK_SONG + '/') for rel, *_ in items):
            continue
        out.append(items)
    return out


def side(items, book):
    return [x for x in items if x[0].startswith(book + '/')]


def desc(x):
    return f"{x[0]}#{x[1]} {x[2].get('author')}《{x[2].get('title')}》"


def classify(tang, song):
    """返回 (判定, 要删的那条, 说明)。判定：drop / keep_both / alias_skip。"""
    ta = {x[2].get('author') for x in tang}
    sa = {x[2].get('author') for x in song}
    if len(ta) > 1 or len(sa) > 1:
        return 'multi', None, ''
    m = manual(song[0], tang[0]) if len(sa) == 1 and len(ta) == 1 else None
    if m:
        return ('keep_both' if m[0] == 'keep' else 'manual_drop'), song[0], m[1]
    if len(ta) == 1 and len(sa) == 1:
        a, b = next(iter(ta)), next(iter(sa))
        if a == b and (a or '').startswith(('釋', '释')):
            return 'alias', song[0], f'{a}／{strip_shi(a)}，法名前加「釋」'
        if a != b and strip_shi(a) == strip_shi(b) and a != strip_shi(a):
            return 'alias', song[0], f'{a}／{b}，法名前加「釋」'
        a, b = next(iter(ta)), next(iter(sa))
        if a == b:
            return 'same_author', None, ''
        if (a, b) in ALIAS:
            return 'alias', song[0], ALIAS[(a, b)]
        if (a, b) in KEEP_BOTH:
            return 'keep_both', None, KEEP_BOTH[(a, b)]
        if a in MISATTRIB and MISATTRIB[a]:
            return 'misattrib', song[0], MISATTRIB[a]
    return 'review', None, ''


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--apply', action='store_true')
    ap.add_argument('--date', default=date.today().isoformat())
    ap.add_argument('--reviewer', default='codebuddy')
    ap.add_argument('--out', default=OUT)
    args = ap.parse_args()

    data, recs = corpus()
    grps = groups_of(recs)
    print(f'== 《全唐诗》↔《全宋诗》正文前 {PREFIX} 字相同的组：{len(grps)}')

    rows, drops, links = [], {}, []
    stat = {}
    for items in sorted(grps, key=lambda g: (g[0][2].get('author') or '', g[0][2].get('title') or '')):
        tang, song = side(items, BOOK_TANG), side(items, BOOK_SONG)
        kind, victim, why = classify(tang, song)
        stat[kind] = stat.get(kind, 0) + 1
        t, s = tang[0], song[0]
        if kind in ('drop', 'manual_drop') or (kind in ('alias', 'misattrib') and victim):
            drops.setdefault(victim[0], set()).add(victim[2].get('id'))
            row = dict(kind='drop' if kind == 'manual_drop' else kind,
                       keep=desc(t), drop=desc(s), why=why, key=items[0][3][:PREFIX])
            rows.append(row)
            if victim[2].get('id') not in {r.get('id') for r in data[victim[0]]}:
                pass   # 上轮已删：判据不变，明细照旧要写
        elif kind == 'keep_both':
            links.append((t, s, why))
            rows.append(dict(kind=kind, keep=desc(t), drop=desc(s),
                             why=why + '兩存，互掛 tags', key=items[0][3][:PREFIX]))
        elif kind == 'review':
            rows.append(dict(kind=kind, keep=desc(t), drop=desc(s), why='', key=items[0][3][:PREFIX]))
    for k, v in sorted(stat.items(), key=lambda kv: -kv[1]):
        print(f'   {k:<12} {v} 组')
    print(f'   拟删 {sum(len(v) for v in drops.values())} 条，涉及 {len(drops)} 个文件；'
          f'互挂 tags {len(links)} 组')

    if not args.apply:
        for r in rows:
            if r['kind'] in ('drop', 'alias', 'misattrib'):
                print(f"   删 {r['drop'][:60]:<60} ← 留 {r['keep'][:50]}  {r['why']}")
        print('\n（预演，未改动文件；加 --apply 落盘）')
        return

    for rel, ids in drops.items():
        data[rel] = [r for r in data[rel] if r.get('id') not in ids]
    for rel in drops:
        dump(rel, data[rel])

    # 互挂 tags：两说并传的组，给两条各挂一条「一作某《某题》」
    touched = {}
    for t, s, why in links:
        ta, st = t[2].get('author'), t[2].get('title')
        sa, stt = s[2].get('author'), s[2].get('title')
        for own, other in ((t[2], f'{sa}《{stt}》'), (s[2], f'{ta}《{st}》')):
            tags = own.setdefault('tags', [])
            if other not in tags:
                tags.append(other)
        touched.setdefault(t[0], set()).add(t[2].get('id'))
        touched.setdefault(s[0], set()).add(s[2].get('id'))
    tagged = touched
    if links:
        # 已删记录的文件重读过一次，这里要按 id 定位后再写回
        fresh = {}
        for rel in touched:
            fresh[rel] = load(rel)
        for t, s, why in links:
            for own, other in ((t, s), (s, t)):
                if own[2].get('id') in {r.get('id') for r in drops.get(own[0], ())}:
                    continue
                for rec in fresh[own[0]]:
                    if rec.get('id') == own[2].get('id'):
                        tags = rec.setdefault('tags', [])
                        link = f"{other[2].get('author')}《{other[2].get('title')}》"
                        if link not in tags:
                            tags.append(link)
        for rel, d in fresh.items():
            dump(rel, d)

    with open(os.path.join(ROOT, args.out), 'w', encoding='utf-8', newline='') as fp:
        w = csv.writer(fp, delimiter='\t', lineterminator='\n')
        w.writerow(['判定', '正文前16字', '保留', '重复', '处理'])
        for r in rows:
            w.writerow([r['kind'], r['key'], r['keep'], r['drop'], r['why']])
    print(f'明细写入 {args.out}')

    fixes_by_file = {}
    for rel, ids in drops.items():
        for rid in sorted(ids):
            rec = next((r for r in load(rel) if r.get('id') == rid), None)
            if rec is None:
                continue
            fixes_by_file.setdefault(rel, []).append(dict(
                original=f"{rid} {rec.get('author')}《{rec.get('title')}》", corrected='删除',
                note=f'[tangsong] 與《全唐詩》同首而作者不同，依識典古籍定歸屬，删《全宋詩》這條；見 {args.out}'))
    # 只挂了 tags、没删记录的文件也记一条：这批动过它
    for rel, ids in tagged.items():
        if rel in fixes_by_file:
            continue
        fixes_by_file[rel] = [dict(original=f'{rid}', corrected='tags',
                                   note=f'[tangsong] 與《全唐詩》归属异说，另存一份并互挂 tags「一作某《某题》」；见 {args.out}')
                               for rid in sorted(ids)]
    for rel, fixes in fixes_by_file.items():
        entry = dict(fixes=fixes, date=args.date, reviewer=args.reviewer)
        rec = pg.merge(rel, entry)
        ndel = sum(1 for f in fixes if f['corrected'] == '删除')
        msg = (f" {args.date} 删 {ndel} 条与《全唐诗》作者不同的重出" if ndel
               else f" {args.date} 与《全唐诗》归属异说 {len(fixes)} 组，两条并存、互挂 tags")
        rec['note'] = ((rec.get('note') or '').rstrip() + f'{msg}，逐条见 {args.out}。').strip()
        pg.write_record(rel, pg.ordered(rec))
    pg.write_index()
    print(f'进度记录 {len(fixes_by_file)} 个文件')


if __name__ == '__main__':
    main()
