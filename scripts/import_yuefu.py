#!/usr/bin/env python3
"""依 `reference/樂府詩集/樂府詩集.txt` 整本重出《樂府詩集》，一卷一个文件。

  python3 scripts/import_yuefu.py            # 预演：打印各卷条数、字数与问题
  python3 scripts/import_yuefu.py --apply    # 写盘并更新 docs/progress 记录

底本是识典古籍（shidianguji.com）SBCK309「樂府詩集　精校·四部叢刊景上海涵芬樓藏汲古閣刊本」
的渲染正文。抓取时渲染层已把底本的异体字（朙/𦶎/髙/竝/畱…）归一到通行繁体，与库内其余书的
用字口径一致；`paragraphList` 那一份保留底本原字形，因此正文取渲染层，结构（卷/类目/小类/篇题）
也取渲染层，两者同源。

快照格式（行首标记即层级）：

    # 樂府詩集卷1        卷（郭茂倩原书 100 卷）
    ## 郊廟歌辭          十二大类
    ### 漢郊祀歌         小类（多是母题名，形如「漢郊祀歌十九首」去掉首数）
    #### 練時日          篇题
    ##### 正德舞歌       篇题下的分首（只有舞曲歌辞的几卷用到）
    正文一行一段

生成规则：

  * `title` = 篇题；篇题下的「同前」还原成母题（同一小类内向前回溯），「N首」不进题名，记在 `notes`；
  * `author`：篇题下第一行若是短姓名（无句读、≤8 字）就取作作者，同一小类内向后继承；
    作者不明写 `佚名`（底本有些乐章本来就不署作者）；
  * 题下注（「一曰…」「某書曰…」）不进 `paragraphs`，收进 `notes`；
  * `dynasty` 按作者查 `authors/authors.json`，查不到的留空（不猜）；
  * `id` 由「作者 + 题名 + 正文 + 分段」哈希得来，规则同 `scripts/backfill_ids.py`。

底本自身的讹字、错位不在这里改 —— 勘误走另一批提交，逐条记进 `docs/progress/`。
"""
import argparse
import hashlib
import json
import os
import re
import sys
from collections import OrderedDict
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import progress as pg  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = 'reference/樂府詩集/樂府詩集.txt'
OUT = '汇编/乐府诗集'
REVIEWER = 'CodeBuddy'
ALPHABET = '0123456789abcdefghijklmnopqrstuv'

CN = '〇一二三四五六七八九十百'


def cn2int(s):
    d = {c: i for i, c in enumerate('〇一二三四五六七八九')}
    if s == '一百':
        return 100
    if s.startswith('十'):
        return 10 + d.get(s[1:], 0)
    if '十' in s:
        a, b = s.split('十')
        return d[a] * 10 + (d.get(b, 0) if b else 0)
    return d.get(s, 0)


def int2cn(n):
    d = '〇一二三四五六七八九'
    if n <= 10:
        return '十' if n == 10 else d[n]
    if n < 20:
        return '十' + d[n - 10]
    if n == 100:
        return '一百'
    t, o = divmod(n, 10)
    return d[t] + '十' + (d[o] if o else '')


PUNCT = re.compile(r'[，。？！、；：]')
HEAD_PUNCT = re.compile(r'^[“「『]')


def is_author(s):
    """短姓名：≤8 字、无句读、不以引号起。"""
    s = s.strip()
    return 0 < len(s) <= 8 and not PUNCT.search(s) and not HEAD_PUNCT.match(s) and '曰' not in s


def is_note(s):
    """题下注：`一曰…`、`某書（志/傳/録）曰：…`、`樂府解題曰…`。

    注在底本里就是正文前的一段散文，篇幅常比正文还长；它们不是作品正文，收进 notes。
    判据只看开头六到十字：书名 + 「曰/云」+ 冒号。
    """
    s = s.strip()
    if s.startswith('一曰'):
        return True
    return bool(re.match(r'^[^，。：；]{2,10}(曰|云)[：:]', s))


# ---------------------------------------------------------------- 解析底本

def parse(path):
    """→ OrderedDict{卷号: [{'cls','sub','title','kid','lines':[(tag,text)]}]}"""
    vols = OrderedDict()
    vol = None
    cur = None
    for raw in open(path, encoding='utf-8'):
        line = raw.rstrip('\n')
        if not line.strip():
            continue
        if line.startswith('# '):
            m = re.match(r'^# 樂府詩集卷([' + CN + r'\d]+)$', line)
            if not m:
                continue
            g = m.group(1)
            vol = int(g) if g.isdigit() else cn2int(g)
            vols[vol] = []
            cur = None
            continue
        if line.startswith('##### '):
            cur = {'cls': cur['cls'] if cur else None, 'sub': cur['sub'] if cur else None,
                   'title': line[6:].strip(), 'kid': True, 'lines': []}
            vols[vol].append(cur)
            continue
        if line.startswith('#### '):
            cur = {'cls': cur['cls'] if cur else None, 'sub': cur['sub'] if cur else None,
                   'title': line[5:].strip(), 'kid': False, 'lines': []}
            vols[vol].append(cur)
            continue
        if line.startswith('### '):
            cur = {'cls': cur['cls'] if cur else None, 'sub': line[4:].strip(),
                   'title': None, 'kid': False, 'lines': []}
            vols[vol].append(cur)
            continue
        if line.startswith('## '):
            cur = {'cls': line[3:].strip(), 'sub': None, 'title': None, 'kid': False, 'lines': []}
            vols[vol].append(cur)
            continue
        if cur is None:
            continue
        cur['lines'].append(line)
    return vols


# ---------------------------------------------------------------- 组装记录

def build_volume(vol, nodes):
    """一卷 → [记录]。

    底本一卷里有两种排法：
      * 小类下还分篇题（### 漢郊祀歌 → #### 練時日）：按篇题成条，小类记进 subcategory；
      * 小类本身就是篇名（### 白雪歌，下面直接是作者与正文）：整小类成一条。
    类目（## ）下、小类之前的散文（如「郊廟歌辭」总序）单独成条。
    """
    recs = []

    def poem(title, sub, lines, kid, inher=None):
        lines = [x for x in lines if x.strip()]
        notes = []
        if lines and is_author(lines[0]) and not re.match(r'^[一二三四五六七八九十百]+首$', lines[0]):
            author = lines.pop(0).strip()
        else:
            author = inher
        while lines and is_note(lines[0]):
            notes.append(lines.pop(0))
        t = re.sub(r'\s+', '', title)
        m = re.search(r'([一二三四五六七八九十百]+)首$', t)
        if m:
            t = t[:m.start()]
        return {'sub': sub, 'rawtitle': t, 'author': author, 'notes': notes,
                'paras': lines, 'kid': kid}

    # 先按「小类」分段
    blocks = []          # [(cls, sub, [nodes])]；sub 为 None 表示类目散文块
    for n in nodes:
        if n['title'] is None and n['sub'] is None:
            blocks.append((n['cls'], None, [n]))
            continue
        if n['title'] is None:
            blocks.append((n['cls'], n['sub'], [n]))
            continue
        # 篇题节点：接到当前块
        for i in range(len(blocks) - 1, -1, -1):
            if blocks[i][1] is not None:
                blocks[i][2].append(n)
                break

    for cls, sub, group in blocks:
        if sub is None:
            body = [x for n in group for x in n['lines'] if x.strip()]
            if body:
                recs.append({'cls': cls, 'sub': None, 'title': cls, 'author': None,
                             'notes': [], 'paras': body})
            continue
        children = [n for n in group if n['title'] is not None]
        if not children:
            body = [x for n in group for x in n['lines'] if x.strip()]
            if body:
                recs.append({'cls': cls, 'sub': None, 'title': sub, 'author': None,
                             'notes': [], 'paras': body})
            continue
        # 小类下、第一个篇题之前的文字：作为小类总注，挂到第一条
        head = group[0]
        pre = [x for x in head['lines'] if x.strip()]
        last = None
        last_author = None
        # 小类标题下的第一行若是短姓名，就是这一小类的作者，向下继承
        if pre and is_author(pre[0]):
            last_author = pre.pop(0).strip()
        seen_titles = []
        for idx, n in enumerate(children):
            lines = (pre if idx == 0 else []) + n['lines']
            r = poem(n['title'], sub, lines, n['kid'], last_author)
            seen_titles.append(r)
            # 母题（#### ）下直接跟着分首（##### ）时，作者写在母题下面，向下继承
            if not n['kid'] and r['author']:
                last_author = r['author']
            elif n['kid']:
                if r['author']:
                    last_author = r['author']
                elif last_author:
                    r['author'] = last_author
            # 底本把作者粘在篇题尾巴上（「晉正德大豫舞歌荀勖」，其下直接是分首，没有作者行）：
            # 这种题里带分首的，从题尾拆出作者
            if r['author'] is None:
                titles = {x.get('rawtitle') or '' for x in seen_titles if x.get('rawtitle')}
                for cut in range(len(r['rawtitle']) - 2, 1, -1):
                    head, tail = r['rawtitle'][:cut], r['rawtitle'][cut:]
                    if head in titles and 1 <= len(tail) <= 4 and is_author(tail):
                        r['rawtitle'] = head
                        r['author'] = tail.strip()
                        last_author = r['author']
                        break
            if r['rawtitle'].startswith('同前'):
                r['rawtitle'] = (last or '') + r['rawtitle'][2:]
            else:
                last = r['rawtitle']
            recs.append({'cls': cls, **r})

    for r in recs:
        r['vol'] = vol
        r['title'] = r.get('rawtitle') or r.get('title')
    return recs


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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--apply', action='store_true', help='写盘；否则只预演')
    ap.add_argument('--date', default=date.today().isoformat())
    args = ap.parse_args()

    authors = json.load(open(os.path.join(ROOT, 'authors/authors.json'), encoding='utf-8'))
    dyn = {a['name']: a.get('dynasty') for a in authors if a.get('name')}
    # 底本用繁体，作者表用简体：按 t2s 后的名字查朝代
    try:
        from opencc import OpenCC
        t2s = OpenCC('t2s').convert
    except ImportError:
        t2s = lambda x: x
    dyn_s = {t2s(k): v for k, v in dyn.items()}

    def dynasty_of(name):
        return dyn.get(name) or dyn_s.get(t2s(name)) or ''

    vols = parse(os.path.join(ROOT, SRC))
    taken = set()
    plan = []
    for vol, nodes in vols.items():
        recs = build_volume(vol, nodes)
        out = []
        for r in recs:
            paras = [p for p in r['paras'] if p.strip()]
            if not paras:
                continue
            item = OrderedDict()
            item['author'] = r['author'] or '佚名'
            item['dynasty'] = dynasty_of(r['author']) if r['author'] else ''
            item['title'] = r['title']
            if r['cls']:
                item['category'] = r['cls']
            if r['sub'] and r['sub'] != r['title']:
                item['subcategory'] = r['sub']
            if r['notes']:
                item['notes'] = r['notes']
            item['paragraphs'] = paras
            key = '|'.join([item['author'], item['title'], ''.join(paras), '\x00'.join(paras)])
            item['id'] = base22(key, 6, taken)
            out.append(item)
        plan.append((vol, out))

    total = sum(len(o) for _, o in plan)
    chars = sum(len(''.join(r['paragraphs'])) for _, o in plan for r in o)
    print(f'{len(plan)} 卷，{total} 条，{chars} 字')
    no_author = sum(1 for _, o in plan for r in o if r['author'] == '佚名')
    print(f'  佚名 {no_author} 条（底本未署作者）')
    for vol, out in plan:
        n = len(out)
        c = sum(len(''.join(r['paragraphs'])) for r in out)
        print(f'  卷{int2cn(vol):<4} {n:>4} 条 {c:>6} 字  {out[0]["title"] if out else "-"}')

    if not args.apply:
        return

    os.makedirs(os.path.join(ROOT, OUT), exist_ok=True)
    for vol, out in plan:
        rel = f'{OUT}/卷{int2cn(vol)}.json'
        path = os.path.join(ROOT, rel)
        text = '[\n' + ',\n'.join(json.dumps(r, ensure_ascii=False, indent=2).replace('\n', '\n') for r in out) + '\n]\n'
        open(path, 'w', encoding='utf-8').write(text)
        lines = [p for r in out for p in r['paragraphs']]
        pg.merge(rel, {
            'note': f'2026-11 依 reference/樂府詩集/樂府詩集.txt（識典古籍 SBCK309 四部叢刊本）'
                    f'整本重出：{len(out)} 條、{len(lines)} 段、{sum(map(len, lines))} 字，'
                    '篇目次序照底本；正文未與別的刻本逐句對勘',
            'date': args.date,
            'reviewer': REVIEWER,
            'status': 'needs_review',
        })
    print(f'→ 写入 {OUT}/ 共 {len(plan)} 个文件')


if __name__ == '__main__':
    sys.exit(main())
