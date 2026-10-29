#!/usr/bin/env python3
"""《全宋词》归属异说：两条都留，互挂 `tags` 一条「一作某」，正文一字不动。

与《全唐诗》同一个办法（`scripts/dedupe_tang.py` 的「归属异说」一类）：作者不同、
正文前 16 字相同，是宋人笔记里就有的归属异说——柳永／欧阳修《蝶恋花》、仲殊／宝月一组、
晏殊／杜安世《凤衔杯》。删哪一条都是替古人定案，所以只挂互见：

    {"author": "柳永", "title": "凤栖梧·蝶恋花", "tags": ["欧阳修《蝶恋花》"], …}

**先归并同一人的两种署名**。`扬无咎／杨无咎`、`张元幹／张元干`、`曹邍／曹原`、
`黄升／黄昇`、`毛幵／毛并`、`朱孙／朱㫹孙`、`张／张鎡` 这类是同一个人的异写
（异体字、生僻字打不出、繁简误转、同名两人用 `2` 区分），不是归属异说，分开处理：

  dup_*    署名一字不差、同一个人两批数据各收一次：正文全同 → 删一条；有出入 → 两存
  alias_*  同一人的两种署名：正文全同 → 删信息少的那条；有出入 → 两存，挂「一作本名」
  attr*    真·归属异说（不同人）：两存，互挂「一作某人《某题》」

判据「是不是同一个人」不靠猜：名单写在 `ALIAS` 里，理由写在 `ALIAS_NOTE` 里。

正文有出入的组（两批录文抄法不同）还判了一次「哪一份被古籍证实得更多」，
与上一轮 [`宋词两批异文`](../docs/宋词两批异文.md) 同一口径：每组取两份录文的中段、末段
各一句检索（620 条），逐句数「原样被证实」与「本读一处没有、另有一读 ≥2 种书」。
结论是**证据对称的组占绝大多数，两读都传世**，两存不改；只有 `SOURCE_FIX` 里那几处
（另有一批手工核过的）分出了高下，改字之后再互挂。逐组判定见
[`docs/宋词归属异说.md`](../docs/宋词归属异说.md)。

用法：
  python3 scripts/dedupe_songci_attr.py                                  # 预演
  python3 scripts/dedupe_songci_attr.py --apply --date YYYY-MM-DD       # 写回 + TSV + 进度记录
"""
import argparse
import collections
import json
import os
import re
import sys

from opencc import OpenCC

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import progress as pg             # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
T2S = OpenCC('t2s')
HANZI = re.compile(r'[^\u4e00-\u9fff]')
SONGCI = '宋/宋词'
OUT = 'docs/宋词归属异说.tsv'
REVIEWER = 'codebuddy'

# 同一人的两种署名：数据里的写法 → 本库另一处的写法。
#   异体 / 俗写：揚/扬、昇/升、幵/并、幹/干、鎡/镃、㫹/、邍（「原」的俗写）
#   生僻字打不出、缺字：朱㫹孙/朱孙、张/张鎡、韩/韩疁
#   括注字：黄裳（冕仲）/黄裳、黄机（几仲）/黄机
#   同名两人用 2 区分：王炎2/王炎（双溪）、刘镇2/刘镇（叔安）
#   别号 / 俗称：张仲殊/仲殊（仲殊俗姓张）、陆游妾/陆游妾某氏
ALIAS = {
    '扬无咎': '杨无咎', '张元幹': '张元干', '曹邍': '曹原', '黄昇': '黄升',
    '毛幵': '毛并', '朱㫹孙': '朱孙', '张': '张鎡', '张仲殊': '仲殊',
    '陆游妾': '陆游妾某氏', '王炎2': '王炎（双溪）', '黄裳（冕仲）': '黄裳',
    '黄机（几仲）': '黄机', '刘镇（叔安）': '刘镇2', '韩': '韩疁',
}
ALIAS_NOTE = {
    '扬无咎': '揚/扬 异体', '张元幹': '幹/干 繁简', '曹邍': '邍是「原」的俗写',
    '黄昇': '昇/升 异体', '毛幵': '幵/并 形近异写', '朱㫹孙': '生僻字打不出，写作朱孙',
    '张': '缺字，当作张鎡', '张仲殊': '仲殊俗姓张，同一人', '陆游妾': '妾某氏即妾',
    '王炎2': '同名两人，用 2 区分（王炎（双溪）是后者）', '黄裳（冕仲）': '括注字，同一人',
    '黄机（几仲）': '括注字，同一人', '刘镇（叔安）': '同名两人，用 2 区分',
    '韩': '缺字，当作韩疁',
}

# 正文有出入的组里，古籍判出高下的那几处：键 = (文件名, 下标)，值 = [(原, 正, 依据)]。
# 只收「本读在检索到的古籍里一处也没有、另一读 ≥2 种书」的；其余一律两存不改。
SOURCE_FIX = {
    ('ci.song.1000.json', 549): [('眉间已作伤春皱', '眉尖已作伤春皱',
                                  '《東坡詞》《東坡先生全集》《宋名家詞》《御選歷代詩餘》并作「眉尖」')],
    ('ci.song.20000.json', 43): [('间牧童、遥指孤村道', '问牧童、遥指孤村道',
                                  '《增修箋注妙選草堂詩餘》《古今圖書集成·文學典》《詞海評林》并作「問」')],
    ('ci.song.3000.json', 280): [('事如飞弹须园熟', '事如飞弹须圆熟',
                                  '《稼軒長短句》（大德三年廣信書院刊本）《稼軒詞》并作「圓熟」')],
    ('ci.song.15000.json', 772): [('甲生应是在今宵', '申生应是在今宵',
                                   '《新編事文類聚翰墨全書》《日涉編》《秋崖先生小槁》并作「申生」')],
    ('ci.song.17000.json', 55): [('新亭坠泪', '新亭堕泪',
                                  '《錢塘遺事》《古今圖書集成·文學典》《堯山堂外紀》并作「墮淚」'),
                                 ],
    ('ci.song.12000.json', 786): [('归梦绕家山', '归梦到家山',
                                   '《中興以來絶妙詞選》《宋丞相崔清獻公全錄》《全蜀藝文志》并作「到家山」')],
}


def hanzi(s):
    """判重用的规范形：与 check_tree.py 同口径（t2s、去一切非汉字）。"""
    return HANZI.sub('', T2S.convert(s or ''))


def norm_author(a):
    a = T2S.convert((a or '').strip())
    return re.sub(r'\s*\S*[一二三四五六七八九十]+首$', '', a)


def person(a):
    """署名归一：同一人的两种写法折成同一个 key。"""
    a = norm_author(a)
    return ALIAS.get(a, a)


def title_of(rec):
    return str(rec.get('title') or rec.get('rhythmic') or '')


def songci_files():
    return sorted(f'{SONGCI}/{f}' for f in os.listdir(os.path.join(ROOT, SONGCI))
                  if re.fullmatch(r'ci\.song\..*\.json', f))


def groups(data):
    idx = collections.defaultdict(list)
    for rel, recs in data.items():
        for i, rec in enumerate(recs):
            b = hanzi(''.join(rec.get('paragraphs') or []))
            if len(b) >= 16:
                idx[b[:16]].append((rel, i))
    return [[(rel, i) for rel, i in keys] for keys in idx.values() if len(keys) > 1]


def alias_reason(a, b):
    for x in (a, b):
        if x in ALIAS_NOTE:
            return ALIAS_NOTE[x]
    return '异体 / 别写'


def render(raw, data):
    """按原文件的排版写回，只让真正改到的那几行出现在 diff 里。

    这批数据由 `json.dumps(indent=2)` 产出，行尾空格却不齐：多数行多一个空格（老写法），
    少数干净；同一种行（记录末尾的字符串、`"id": …`）在不同位置写法也不同。整份重新
    dump 会把几万行的空格抹平，`tags` 一加 diff 就淹掉正文，所以按内容查原文件的写法：
    内容只出现一种写法就照抄，出现两种就跟「同名行里这一行的邻居」走。
    """
    with_blank, without_blank, prev = collections.Counter(), collections.Counter(), {}
    lines = raw.split('\n')
    for i, line in enumerate(lines):
        if not line.strip():
            continue
        blank = line != line.rstrip(' ')
        (with_blank if blank else without_blank)[line.rstrip(' ')] += 1
        prev[line.rstrip(' ')] = lines[i - 1] if i else ''
    m = re.search(r'\n( +)\S', raw)
    indent = len(m.group(1)) if m else 2
    out = (json.dumps(data, ensure_ascii=False, indent=indent)
           + ('\n' if raw.endswith('\n') else '')).split('\n')
    res = []
    for line in out:
        if not line.strip():
            res.append(line)
            continue
        key = line.rstrip(' ')
        if with_blank[key] and not without_blank[key]:
            res.append(key + ' ')
        elif without_blank[key] and not with_blank[key]:
            res.append(key)
        elif with_blank[key]:
            res.append(key + (' ' if prev.get(key, '').endswith(' ') else ''))
        else:
            # 新写入的行：`"tags": [` 不带空格，里面的字符串与收尾的 `]` 带（照老写法）
            res.append(key + (' ' if not key.rstrip().endswith('[') and key.strip() not in ('{', '}') else ''))
    return '\n'.join(res)


def apply_fix(rec, fixes, log, rel, idx):
    for old, new, why in fixes:
        paras = rec.get('paragraphs') or []
        for k, para in enumerate(paras):
            if old in para:
                paras[k] = para.replace(old, new, 1)
                log.append(dict(path=rel, idx=idx, original=old, corrected=new, note=why))
                break
        else:
            log.append(dict(path=rel, idx=idx, original=old, corrected=None,
                            note=f'{why}（未命中，未改）'))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--apply', action='store_true')
    ap.add_argument('--show', type=int, default=6)
    ap.add_argument('--date', default='')
    ap.add_argument('--reviewer', default=REVIEWER)
    args = ap.parse_args()

    data = {}
    for rel in songci_files():
        with open(os.path.join(ROOT, rel), encoding='utf-8') as fp:
            data[rel] = json.load(fp)

    fix_log, rows, stat = [], [], collections.Counter()
    drop = collections.defaultdict(set)
    for keys in groups(data):
        recs = [data[rel][i] for rel, i in keys]
        looks = [r.get('author') or '' for r in recs]
        same_person = len({person(a) for a in looks}) == 1
        same_body = len({hanzi(''.join(r.get('paragraphs') or [])) for r in recs}) == 1
        same_looks = len({normalize_look(a) for a in looks}) == 1
        if same_person and same_looks:
            kind = 'dup_same' if same_body else 'dup_variant'
        elif same_person:
            kind = 'alias_same' if same_body else 'alias_variant'
        else:
            kind = 'attr_same' if same_body else 'attr'

        for rel, i in keys:
            fixes = SOURCE_FIX.get((rel.split('/')[-1], i))
            if fixes:
                apply_fix(data[rel][i], fixes, fix_log, rel, i)

        if kind in ('dup_same', 'alias_same'):
            # 同一人、正文一字不差：删信息少的那条（没有 tags / 题名更短）
            keys_sorted = sorted(keys, key=lambda k: (-len(data[k[0]][k[1]].get('tags') or []),
                                                      -len(title_of(data[k[0]][k[1]])), k))
            keep = keys_sorted[0]
            if kind == 'alias_same':
                why = f'同一人的两种署名（{alias_reason(*looks[:2])}）'
            else:
                why = '同一个人两批数据各收一次'
            for k in keys_sorted[1:]:
                drop[k[0]].add(k[1])
                rows.append(dict(kind=kind, keep=f'{keep[0]}#{keep[1]}', drop=f'{k[0]}#{k[1]}',
                                 author=data[keep[0]][keep[1]].get('author'),
                                 title=title_of(data[keep[0]][keep[1]]),
                                 note=f'{why}，正文全同 → 删重复的那条'))
            stat[kind] += len(keys_sorted) - 1
            continue

        for i, a in enumerate(keys):
            for b in keys[i + 1:]:
                ra, rb = data[a[0]][a[1]], data[b[0]][b[1]]
                for rec, other in ((ra, rb), (rb, ra)):
                    link = f"{other.get('author')}《{title_of(other)}》"
                    tags = rec.setdefault('tags', [])
                    if link not in tags:
                        tags.append(link)
                    if not rec['tags']:
                        del rec['tags']
        note = {
            'dup_variant': '同一个人两批数据各收一次，正文有出入（异文两存）',
            'alias_variant': f'同一人的两种署名（{alias_reason(*looks[:2])}），正文有出入，两存并挂「一作本名」',
            'attr': f'归属异说（{looks[0]}／{looks[1]}，宋人笔记两说并存），两存互挂「一作某人《某题》」',
            'attr_same': f'作者不同（{looks[0]}／{looks[1]}）、正文全同：归属异说，两存互挂',
        }[kind]
        for i, a in enumerate(keys):
            for b in keys[i + 1:]:
                rows.append(dict(kind=kind, keep=f'{a[0]}#{a[1]}', drop=f'{b[0]}#{b[1]}',
                                 author=data[a[0]][a[1]].get('author'),
                                 title=title_of(data[a[0]][a[1]]), note=note))
                stat[kind] += 1

    print('== 宋词归属异说 / 别名归并')
    for k in ('dup_same', 'dup_variant', 'alias_same', 'alias_variant', 'attr_same', 'attr'):
        if stat.get(k):
            print(f'   {k}: {stat[k]}')
    print(f'   改字 {len(fix_log)} 处')
    for r in rows[:args.show]:
        print(f"   [{r['kind']}] {r['keep']} {r['author']}《{r['title']}》 ←→ {r['drop']}")
    for f in fix_log[:args.show]:
        print(f"   [改字] {f['path']}#{f['idx']} {f['original']} → {f['corrected']}")

    if not args.apply:
        print('（预演，未写回；加 --apply 写回，需配 --date）')
        return 0
    if not args.date:
        ap.error('--apply 需要 --date YYYY-MM-DD')

    for rel, recs in data.items():
        raw = open(os.path.join(ROOT, rel), encoding='utf-8').read()
        out = render(raw, recs)
        if out != raw:
            with open(os.path.join(ROOT, rel), 'w', encoding='utf-8') as fp:
                fp.write(out)

    # 记录：改字进 fixes；删条与挂 tags 只记 note，status 不动（挂 tags 不是逐字对勘）
    by_path = collections.defaultdict(list)
    for f in fix_log:
        by_path[f['path']].append(f)
    for path, items in by_path.items():
        pg.merge(path, dict(fixes=[dict(original=x['original'], corrected=x['corrected'],
                                        note=f"宋词归属异说那一轮核出：{x['note']}") for x in items],
                            date=args.date, reviewer=args.reviewer))
    for rel, idxs in drop.items():
        if not idxs:
            continue
        pg.merge(rel, dict(note=f'删除 {len(idxs)} 条同一人重复的记录（见 {OUT}），status 不动',
                           date=args.date, reviewer=args.reviewer))
    with open(os.path.join(ROOT, OUT), 'w', encoding='utf-8', newline='') as fp:
        w = __import__('csv').DictWriter(fp, delimiter='\t', lineterminator='\n',
                                         fieldnames=['kind', 'keep', 'drop', 'author', 'title', 'note'])
        w.writeheader()
        w.writerows(rows)
    pg.write_index()
    print(f'写回完成，明细 {OUT}')
    return 0


def normalize_look(a):
    return (a or '').strip()


if __name__ == '__main__':
    sys.exit(main())
