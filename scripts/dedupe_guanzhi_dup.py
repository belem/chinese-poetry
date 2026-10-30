#!/usr/bin/env python3
"""《古文观止》一本之内同题两见：给选本留一份目次，删重出的那一条正文。

`汇编/古文观止/` 按卷分文件，同一篇被排进两处的有 20 组：
《古文观止·补》19 篇与正编各卷重（《归去来兮辞》《滕王阁序》《报任安书》……），
《郑伯克段于鄢》卷一（《左传》原文）与卷三（《穀梁传》的经解）各一条。

## 为什么删正文、留目次

《古文观止》是一部给人读的选本，同一篇排两遍是重出。删掉重出的那一份，正文只有一处；
而「这本书收了哪几篇」这层信息不能跟着丢，所以整部书的目次另存
`汇编/古文观止/古文观止·选目.json`：卷次、篇题、作者、对应正文记录的 id。删掉的篇目也记进去。

## 20 组里一条都没删，为什么

**删的判据**只有一条：重复那条**逐字**见于保留那条（`covered`），且不到它的一半 ——
那就是「同篇的一节」。20 组过这条线的只有两条：

| 组 | 补编那条 | 正编那条 | 逐字见于 | 判断 |
| --- | --- | --- | --- | --- |
| 齊桓下拜受胙 | 90 字 | 102 字 | 是（正编多「夏，会于葵丘，寻盟，且修好，礼也」） | 但**不到一半**这条不满足（90×2 > 102） |
| 祁奚請免叔向 | 172 字 | 334 字 | 是 | 补编那本**丢了开头一段**（栾盈出奔楚…），留着就是那段正文的唯一出处 |

其余 18 组各取各的，删了就是丢正文：

- **补编摘正文、正编还多出序或评**：《归去来兮辞》补编 339 字是正文，正编 537 字多「余家贫，耕植不足以自给……乙巳岁十一月也」一整段序；
  《送杨寘序》补编多出「夫疾生乎忧者也……疾之忘也宜哉」13 字；《谏太宗十思疏》《滕王阁序》《潮州韩文公庙碑》
  正编夹着「望国一作」「一作思国」这类注。《宫之奇谏假道》补编 294 字止于「晋不更举矣，冬，晋灭虢」，
  正编 428 字多出卜偃对童谣、灭虢执虞公一节。
- **题同而文不同，根本不是一篇**：《六国论》（苏辙 vs 苏洵）、《沧浪亭记》（归有光 vs 苏舜钦）、
  《子产却楚逆女以兵》（补编配的是《徐吾犯之妹美》）、《吴许越成》（补编配的是「吴子使来儆师伐齐」一段）、
  卷三《郑伯克段于鄢》是《穀梁传》的经解，与卷一《左传》本两回事。
- 《屈原列传》《报任安书》《治安策》《徐文长传》《青霞先生文集序》是补编的节本，正文各自独立。

**这一批实际只做了一件事**：把《古文观止》的目次整理成一份
[`古文观止·选目.json`](../汇编/古文观止/古文观止·选目.json)（84 条，卷次 / 篇题 / 作者 / 记录 id），
顺带记下这 20 组同题 —— 日后要删哪一条，得先有这份目次兜着「这本书收了哪几篇」。

用法：
  python3 scripts/dedupe_guanzhi_dup.py            # 预演：逐组打印
  python3 scripts/dedupe_guanzhi_dup.py --apply --date YYYY-MM-DD --reviewer <名字>
"""
import argparse
import csv
import json
import os
import re
import sys
from datetime import date
from difflib import SequenceMatcher

from opencc import OpenCC

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import progress as pg  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
T2S = OpenCC('t2s')
HAN = re.compile(r'[^\u4e00-\u9fff]')
GU_DIR = '汇编/古文观止'
MASTER = '古文观止.json'
TOC = '汇编/古文观止/古文观止·选目.json'
OUT = 'docs/古文观止重出.tsv'


def han(s):
    return HAN.sub('', T2S.convert(s or ''))


def body(rec):
    p = rec.get('paragraphs')
    return han(p if isinstance(p, str) else ''.join(p or ''))


def load(rel):
    with open(os.path.join(ROOT, rel), encoding='utf-8') as fp:
        return json.load(fp)


def dump(rel, data):
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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--apply', action='store_true')
    ap.add_argument('--date', default=date.today().isoformat())
    ap.add_argument('--reviewer', default='codebuddy')
    ap.add_argument('--out', default=OUT)
    args = ap.parse_args()

    vols = sorted(f for f in os.listdir(os.path.join(ROOT, GU_DIR))
                  if f.endswith('.json') and f not in (MASTER, os.path.basename(TOC)))
    groups = {}
    for name in vols:
        for i, rec in enumerate(load(f'{GU_DIR}/{name}')):
            groups.setdefault(han(rec.get('title')), []).append(dict(rel=f'{GU_DIR}/{name}', index=i, rec=rec))

    rows, drops = [], {}
    for key, items in sorted(groups.items()):
        if len(items) < 2 or not key:
            continue
        items.sort(key=lambda x: -len(body(x['rec'])))
        keep = items[0]
        for other in items[1:]:
            kb, ob = body(keep['rec']), body(other['rec'])
            # 删的判据：重复那条**逐字**见于保留那条（`covered`），且不到它的一半。
            # 只比相似度不行 —— 补编摘的常是正文、正编多出的是序，那一段缺席，相似度会掉到 0.77
            # （《归去来兮辞》补编 339 字 vs 正编 537 字正是这样）
            dup = ob in kb and len(ob) * 2 <= len(kb) + 1
            rows.append(dict(keep=keep, drop=other, dup=dup, short=len(ob), long=len(kb)))
            if dup:
                drops.setdefault(other['rel'], set()).add(other['index'])

    n = sum(r['dup'] for r in rows)
    print(f'== 《古文观止》一本之内同题 {len(rows)} 组：删 {n}、两存 {len(rows) - n}')
    for r in rows:
        tag = '删' if r['dup'] else '存'
        print(f"   {tag} {r['drop']['rel'].split('/')[-1]}#{r['drop']['index']} 《{r['drop']['rec'].get('title')}》"
              f"（{r['short']}） ← {r['keep']['rel'].split('/')[-1]}#{r['keep']['index']}"
              f"（{r['long']}）")

    if not args.apply:
        print('（预演，未改动任何文件；加 --apply 落盘）')
        return 0

    # 目次：整部书写一份，删掉的记进去
    toc = []
    seen = set()
    for name in vols:
        for i, rec in enumerate(load(f'{GU_DIR}/{name}')):
            key = (name, rec.get('title'))
            if key in seen:
                continue
            seen.add(key)
            toc.append({'卷次': name, '篇目': rec.get('title'), '作者': rec.get('author'),
                        '记录': f'{GU_DIR}/{name}#{rec.get("id")}'})
    for name in sorted(drops):
        data = load(name)
        dump(name, [rec for i, rec in enumerate(data) if i not in drops[name]])

    with open(os.path.join(ROOT, TOC), 'w', encoding='utf-8') as fp:
        json.dump(toc, fp, ensure_ascii=False, indent=2)
        fp.write('\n')

    with open(os.path.join(ROOT, args.out), 'w', encoding='utf-8', newline='') as fp:
        w = csv.writer(fp, delimiter='\t', lineterminator='\n')
        w.writerow(['保留', '重复', '字数（重复／保留）', '处理'])
        for r in rows:
            w.writerow([f"{r['keep']['rel']}#{r['keep']['index']} {r['keep']['rec'].get('title')}",
                        f"{r['drop']['rel']}#{r['drop']['index']} {r['drop']['rec'].get('title')}",
                        f"{r['short']}／{r['long']}",
                        '删重出那条（是保留那条的一节），目次见 古文观止·选目.json' if r['dup']
                        else '两存：同题不同文或各取各的'])
    print(f'明细写入 {args.out}；目次 {len(toc)} 条写入 {TOC}')

    for name in sorted(drops):
        recs = [r for r in rows if r['dup'] and r['drop']['rel'] == name]
        rec = pg.merge(name, dict(fixes=[dict(
            original=f"{r['drop']['rec'].get('id')} 《{r['drop']['rec'].get('title')}》", corrected='删除',
            note=f"《古文观止》一本之内重出，是 {r['keep']['rel']} 那条的一节；目次见 {TOC}") for r in recs],
            date=args.date, reviewer=args.reviewer))
        rec['note'] = ((rec.get('note') or '').rstrip() +
                       f" {args.date} 删 {len(recs)} 条《古文观止》重出篇目。").strip()
        pg.write_record(name, pg.ordered(rec))
    pg.write_index()
    return 0


if __name__ == '__main__':
    sys.exit(main())
