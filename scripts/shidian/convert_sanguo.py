#!/usr/bin/env python3
"""《三國志通俗演義》（嘉靖壬午本，識典 CADAL02111749）→ 记录。

版式与其余三部长篇不同：
  * 卷题页后跟本卷「目録」，一回一条短行；
  * 正文有的卷一页一则（页面小标题 H3 就是回目），有的卷整卷压在一页里；
  * 回次全书不带，只能按目録次序编号。

做法：先收每卷目録，再把正文页按顺序对上目録。一页多则的卷（卷四~六、十七、二十、二十三）
在页内找不到回次标记，只能整卷作一条、题名用本卷首则，`tags` 记「该卷目次未切开」。
宁可标出没切的，也不硬按字数劈。
"""
import json, re, sys
sys.path.insert(0, '/tmp/build')
from convert import make_id, norm, cn2int

VOL_RX = re.compile(r'^三國志通俗演義卷之?([〇零一二三四五六七八九十百]+)[，。]?$')
TOC_RX = re.compile(r'^目[録錄]$')
HEADER = re.compile(r'^(晋平陽侯陳壽史傳|後學羅本貫中編次)')


def is_heading(t):
    t = norm(t).lstrip('。')
    if not (4 <= len(t) <= 16):
        return False
    if '。' in t:
        return False
    if re.match(r'^(却説|却说|原來|原来|只見|只见|且説|且说|當下|当下|未知|畢竟|毕竟)', t):
        return False
    return True


def strip_front(ps):
    """去掉卷题、目録行与其后的回目短行、编者题署。"""
    ps = [p.strip() for p in ps]
    i = 0
    while i < len(ps) and (VOL_RX.match(norm(ps[i])) or TOC_RX.match(norm(ps[i])) or HEADER.match(norm(ps[i]))
                           or is_heading(ps[i])):
        i += 1
    return ps[i:]


def collect(raw):
    pages = sorted(raw.values(), key=lambda x: x['index'])
    vols, cur = [], None
    for v in pages:
        name = norm(v['name'])
        m = VOL_RX.match(name)
        if m:
            cur = {'num': cn2int(m.group(1)), 'toc': [], 'items': []}
            vols.append(cur)
        if cur is None:
            continue
        ps = [p.strip() for p in v['paragraphs']]
        # 目録：卷题页里「目録」之后的短行
        try:
            k = next(i for i, p in enumerate(ps) if TOC_RX.match(norm(p)))
            for p in ps[k + 1:]:
                if is_heading(p):
                    cur['toc'].append(norm(p))
                elif cur['toc']:
                    break
        except StopIteration:
            pass
        body = strip_front(ps)
        body = [b for b in body if len(norm(b)) >= 4]
        if sum(len(b) for b in body) >= 200:
            cur['items'].append({'subtitle': (v.get('subtitle') or '').strip(), 'paragraphs': body})
    return vols


def build(raw):
    vols = collect(raw)
    taken, records = set(), []
    n = 0
    for vol in vols:
        items = vol['items']
        if not items:
            continue
        toc = vol['toc']
        multi = len(items) > 1
        for k, it in enumerate(items):
            body = it['paragraphs']
            head = ''
            if multi and k < len(toc):
                head = toc[k]
            elif not multi and toc:
                head = toc[0]
            elif it['subtitle']:
                head = norm(it['subtitle'])
            if not multi and toc and len(toc) > 1:
                head = f"{toc[0]}等"      # 整卷未切开，题名标出来
            n += 1
            title = f'第{n}则　{head}' if head else f'第{n}则'
            rec = {'author': '罗贯中', 'title': title, 'paragraphs': body}
            if not multi and len(toc) > 1:
                rec['tags'] = ['该卷目次未逐则切开']
            records.append(rec)
    for r in records:
        r['id'] = make_id(r['author'], r['title'], r['paragraphs'], taken)
    return records


if __name__ == '__main__':
    raw = json.load(open(sys.argv[1], encoding='utf-8'))
    recs = build(raw)
    with open(sys.argv[2], 'w', encoding='utf-8') as fp:
        json.dump(recs, fp, ensure_ascii=False, indent=2)
        fp.write('\n')
    print(f'{len(recs)} 则，{sum(len("".join(r["paragraphs"])) for r in recs)} 字 → {sys.argv[2]}')
    for r in recs[:3] + recs[-2:]:
        print('  ', r['title'][:40], len(r['paragraphs']), r.get('tags', ''))
