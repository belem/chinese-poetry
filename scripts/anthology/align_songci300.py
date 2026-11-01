#!/usr/bin/env python3
"""《宋词三百首》：按 reference/宋詞三百首 补挂 tag、补录缺篇。

底本 312 首逐首配到库内记录（`songci300_ref.pairs()`），然后做四件事：

1. **挂 tag**：底本有、库里同文记录没挂 `宋词三百首` 的，补挂（不改动已有的其它 tag）。
2. **改篇目**：库内篇目与底本对不上的，按底本改，形制仍用本库的「词牌·正文首句」——
   - 底本给了小题的，`title` = `词牌·小题`，不再追加首句（燕山亭·北行見杏花 就到这里）
   - 底本只有词牌、库里原来是别的小题（赤壁怀古、乙卯正月二十日夜记梦）的，改成 `词牌·正文首句`
   - 首句按**本记录自己的简繁写法**取正文前 12 字，与 `retitle_songci300.py` 一致
3. **改作者**：底本署名与库内规范名不同的（徽宗皇帝 / 趙佶 → 赵佶；王安國 → 王安国），
   统一到 `authors/authors.json` 里的名字。底本与库内是两个不同的人的（《蝶恋花·欲减罗衣寒未去》
   底本署趙令畤、库里是晏几道），不改，只报告。
4. **补录**：底本有、库里完全没有的 11 首，按底本正文补入 `宋/宋词/ci.song.22000.json`，
   简化后与库内体例一致，挂 tag。

`authors/authors.json` 一个字不动 —— 作者名从这里取，不往里写。

  python3 scripts/anthology/align_songci300.py                 # 预演，打印逐条计划
  python3 scripts/anthology/align_songci300.py --apply --date YYYY-MM-DD --reviewer <名字>
"""
import argparse
import collections
import json
import os
import re
import sys
from difflib import SequenceMatcher

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import progress as pg  # noqa: E402
import songci300_ref as R  # noqa: E402
from anthology.patch_json import patch  # noqa: E402
from backfill_ids import assign, work_key  # noqa: E402
from opencc import OpenCC  # noqa: E402

S2T, T2S = OpenCC('s2t'), OpenCC('t2s')

def han(s):
    return ''.join(HAN_FIRST.findall(s))


def norm_name(s):
    return T2S.convert((s or '').strip())
HAN_FIRST = re.compile(r'[\u3400-\u9fff\U00020000-\U0003ffff]')
CJK = re.compile(r'[\u3400-\u9fff\U00020000-\U0003ffff]+')
SEP = '·'
AUTHORS = json.load(open(os.path.join(R.ROOT, 'authors', 'authors.json'), encoding='utf-8'))

# 底本署名 → 本库作者名。只列「同一个人、写法不同」的；底本与库内是两个人的不在此列，走报告。
AUTHOR_FIX = {
    '徽宗皇帝': '赵佶', '宋徽宗': '赵佶',
    '李煜': '李煜',
    '僧揮': '僧挥', '僧挥': '僧挥',
    '呂濱老': '吕滨老', '吕滨老': '吕滨老',
    '万俟詠': '万俟咏',
    '王安國': '王安国',
}

# 底本有、库内没有的 11 首补进这个文件（与上一轮据识典古籍补入的 193 首同一处）
ADD_TO = '宋/宋词/ci.song.22000.json'
# 目次（anthologies/songci300.json）目次号 → 库内记录，由 --dump-anth 生成，随脚本一起入库
ANTH_MAP = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'songci300_anth_map.json')


def author_names():
    """authors.json → {名字集合}，用于把底本署名对到本库规范名。"""
    names = set()
    if isinstance(AUTHORS, dict):
        for v in AUTHORS.values():
            if isinstance(v, dict):
                for k in ('name', 'author'):
                    if v.get(k):
                        names.add(v[k])
            elif isinstance(v, str):
                names.add(v)
    return names


def norm_author(ref_author, lib_author, names):
    """底本署名 → 本库作者名；同一个人写不同字时返回规范名，否则返回 None（不改）。"""
    ra, la = ref_author.strip(), (lib_author or '').strip()
    if not ra or not la or ra == la:
        return None
    if ra in AUTHOR_FIX and AUTHOR_FIX[ra] == la:
        return None
    simp = T2S.convert(ra)
    if simp == la:
        return None
    if ra in AUTHOR_FIX:
        return AUTHOR_FIX[ra]
    if simp in names and simp != la:
        return simp
    return None


def is_simplified(rec):
    txt = ''.join(p for p in rec['paragraphs'] if isinstance(p, str))
    return S2T.convert(txt) != txt


def head_of(rec, n=12):
    return han(''.join(p for p in rec['paragraphs'] if isinstance(p, str)))[:n]


def clean_note(note):
    """底本小题里的注释（`眼兒媚·萍鄉道中乍晴，臥輿中……` 这类）去掉句末标点。"""
    note = re.sub(r'[（(].*?[)）]', '', note)          # 底本正文里混进来的词牌释义
    return note.strip().rstrip('。，、；：')


def target_title(entry, rec):
    """「词牌·首句」或「词牌·小题」。词牌用记录自己的改法（・→·），小题用底本的。"""
    rhythm = SEP.join(p.strip() for p in re.split(r'[・·]', rec.get('rhythmic') or '') if p.strip())
    note = clean_note(entry['note'])
    if note:
        return rhythm + SEP + note
    return rhythm + SEP + head_of(rec)


def body_simplified(entry):
    """底本正文 → 简体文本，按底本分段原样保留。"""
    return [T2S.convert(p) for p in entry['paras']]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--apply', action='store_true')
    ap.add_argument('--date')
    ap.add_argument('--reviewer')
    ap.add_argument('-v', '--verbose', action='store_true', help='打印逐条计划（默认只打印统计）')
    ap.add_argument('--dump-anth', help='生成 目次号→库内记录 的对照表（配 anthologies/songci300.json 用）')
    ap.add_argument('--dump', help='把逐首配对结果写成 JSON，供人工判署名')
    args = ap.parse_args()

    names = author_names()
    plan = R.pairs()
    cache = {}

    def records(rel):
        if rel not in cache:
            cache[rel] = json.load(open(os.path.join(R.ROOT, rel), encoding='utf-8'))
        return cache[rel]

    if args.dump_anth:
        return dump_anth_map(args.dump_anth)

    keep, edits, last = set(), {}, []
    retag, retitle, reauthor, missing, report = [], [], [], [], []

    for p in plan:
        e = p['ref']
        target = R.is_target(p)
        if target is None:
            missing.append(p)
            continue
        for _, r in p['hits']:
            keep.add((r['rel'], r['idx']))
        last.append((e, [(round(s_, 3), r) for s_, r in p['hits']]))
        rec = records(target['rel'])[target['idx']]
        ops = edits.setdefault((target['rel'], target['idx']), {})
        if R.TAG not in (rec.get('tags') or []):
            ops['tags'] = list(rec.get('tags') or []) + [R.TAG]      # 只加标记，补丁时按坐标插入
            ops['_newtags'] = True
            retag.append((target, e))
        # 篇目不动：由 scripts/anthology/songci300_titles.py 按底本处理过（简繁跟本记录正文）
        if rec.get('author') and norm_name(e['author']) != norm_name(rec['author']):
            report.append(dict(no=e['no'], ref=e['author'], lib=rec['author'],
                               title=clean_note(e['title']), where=target))

    keep |= set(R.EXTRA_TAGGED)
    untag = []
    for rel, data in cache.items():
        for idx, rec in enumerate(data):
            if R.TAG in (rec.get('tags') or []) and (rel, idx) not in keep:
                untag.append((rel, idx, rec))
    for rel, idx, rec in untag:
        edits.setdefault((rel, idx), {})['tags'] = [t for t in rec['tags'] if t != R.TAG]

    verbose = args.verbose or not args.apply
    print(f'改篇目 {len(retitle)} 条，补挂 tag {len(retag)} 条，摘 tag {len(untag)} 条，改作者 {len(reauthor)} 条')
    for t, old, new in (retitle if verbose else retitle[:8]):
        print(f'    篇目 {t["rel"]}#{t["idx"]}: {old or "（无）"} → {new}')
    for rel, idx, rec in untag:
        print(f'    摘 tag {rel}#{idx} {rec.get("author")}《{(rec.get("title") or "")[:20]}》'
              f' —— {R.EXTRA_TAGGED.get((rel, idx), "底本里的篇目配不到它，且正文不是底本任何一首")}')
    for a in report:
        print(f'    ? 第 {a["no"]} 首 {a["ref"]}《{a["title"][:14]}》 库内署「{a["lib"]}」—— 署名不同，未改')

    print(f'补录 {len(missing)} 首（插入 {ADD_TO}）')
    new_records = []
    for p in missing:
        e = p['ref']
        body = body_simplified(e)
        new_records.append(dict(author=norm_author(e['author'], e['author'], names) or e['author'], body=body, entry=e))
        if verbose:
            print(f'    第 {e["no"]} 首 {e["author"]}《{clean_note(e["title"])[:22]}》 {han(body[0])[:14]}')

    if args.dump:
        json.dump([dict(no=e['no'], author=e['author'], title=clean_note(e['title']),
                        where=f'{t["rel"]}#{t["idx"]}' if t else None, lib_author=t['author'] if t else None,
                        hits=[(s_, f'{r["rel"]}#{r["idx"]}', r['author'], r['title'], r['plain'][:40]) for s_, r in hs],
                        body=p['body']) for p, (e, hs) in zip(plan, last) for t in [R.is_target(p)]],
                  open(args.dump, 'w'), ensure_ascii=False, indent=1)

    if not args.apply:
        return
    if not (args.date and args.reviewer):
        sys.exit('--apply 需要 --date 与 --reviewer')

    # 先补录（那次会把 ADD_TO 整份重新序列化），再在它上面打补丁 —— 顺序颠倒会让补丁落在旧偏移上

    # 补录：追加到 ADD_TO 末尾，id 由「作者+题名+正文」哈希，与全库不撞
    if new_records:
        existing = [work_key(x) for x in records(ADD_TO)]
        keys = existing + [work_key(dict(author=r['author'], title=title_of(r), paragraphs=r['body']))
                           for r in new_records]
        ids = assign(keys)
        taken = {x.get('id') for rel in cache for x in cache[rel] if isinstance(x, dict)}
        add = []
        for r in new_records:
            rec = dict(author=r['author'], paragraphs=r['body'], rhythmic=r['entry']['rhythmic'],
                       title=title_of(r), tags=[R.TAG])
            rec['id'] = ids[work_key(dict(author=rec['author'], title=rec['title'], paragraphs=rec['paragraphs']))]
            assert rec['id'] not in taken
            taken.add(rec['id'])
            add.append(rec)
        dump_append(ADD_TO, add)
        cache.pop(ADD_TO, None)

    # 补录那条记录本身在补录后才存在，它的字段补丁一并写进新记录
    for rel in sorted({k[0] for k in edits}):
        if rel == ADD_TO and new_records:      # 刚追加过，偏移变了，重读
            cache.pop(rel, None)
        print(f'    patch {rel} ...')
        n = len(records(rel))
        ops = {idx: {k: v for k, v in ops_.items() if not k.startswith('_')}
               for (r, idx), ops_ in edits.items() if r == rel and idx < n}
        if ops:
            try:
                patch(rel, ops)
            except SystemExit as e:
                print(f'    补丁失败 {rel}: {e}')
                raise

    # 进度记录
    touched = []
    for k in edits:
        if k[0] not in touched:
            touched.append(k[0])
    if new_records and ADD_TO not in touched:
        touched.append(ADD_TO)
    # anthologies/songci300.json 是另一份来源（识典古籍朱祖谋集解本，284 首）的目次；
    # 篇名改过、tag 补过之后，把它的 title 也对到库里同一条记录上（只改 title，不动 no/author/first_line）
    # 目次 title 的同步交给 PR A 那条线，这里不动 anthologies/songci300.json

    for rel in sorted(touched):
        mine = {idx: ops for (r, idx), ops in edits.items() if r == rel}
        fixes, kinds = [], collections.Counter()
        for idx in sorted(mine):
            for k in mine[idx]:
                kinds[k] += 1
        if kinds.get('title'):
            fixes.append(dict(original=f'{os.path.basename(rel)} 共 {kinds["title"]} 条',
                              corrected='篇目改为「词牌·小题」或「词牌·正文首句」',
                              note='按 reference/宋詞三百首 逐首对齐：底本给了小题的用小题（燕山亭·北行見杏花 不再叠首句），'
                                   '底本只给词牌的用「词牌·正文首句」；词牌一律用本库写法。逐条映射见 '
                                   'scripts/anthology/align_songci300.py 与本轮 PR 说明。'))
        if kinds.get('tags'):
            fixes.append(dict(original=f'{os.path.basename(rel)} 共 {kinds["tags"]} 条',
                              corrected='补挂「宋词三百首」tag',
                              note='底本目次里有这一首、库里同文记录没挂 tag 的，补齐；只加标记，正文不动。'))
        if kinds.get('author'):
            fixes.append(dict(original=f'{os.path.basename(rel)} 共 {kinds["author"]} 条',
                              corrected='作者统一到 authors.json 的规范名',
                              note='底本署「徽宗皇帝」这类与库内规范名不同的，统一到 authors.json 里的名字；'
                                   'authors.json 本身一个字未动。'))
        if rel == ADD_TO and new_records:
            fixes.append(dict(original=f'{ADD_TO} 末尾',
                              corrected=f'补录 {len(new_records)} 首',
                              note='底本有、库内无同文：' + '、'.join(
                                  f'{r["author"]}《{clean_note(r["entry"]["title"])[:12]}》' for r in new_records)))
        if fixes:
            pg.merge(rel, dict(status='fixed', reviewer=args.reviewer, date=args.date, fixes=fixes))
            print(f'    记录 {rel}: {len(fixes)} 条')
    print(json.dumps(pg.write_index()['stats'], ensure_ascii=False))


def dump_anth_map(out):
    """`anthologies/songci300.json` 的 284 条目次 → 库内记录，写成 {目次号: '文件#下标'}。

    目次是另一份底本（识典古籍朱祖谋集解本）抽的，与 `reference/宋詞三百首` 不是同一部书：
    目次 284 条、reference 312 条，中间还差着十几处。配法是拿目次的 title+first_line 当一首词
    去 `pairs()` 里找同一条库内记录 —— 两边都落到同一条，才记下来。
    """
    path = os.path.join(R.ROOT, 'anthologies', 'songci300.json')
    entries = json.load(open(path, encoding='utf-8'))['entries']
    recs = R.load_recs()
    plain = {n: r['plain'] for n, r in enumerate(recs)}
    inv = {}
    for n, r in enumerate(recs):
        h = r['plain']
        for k in range(0, max(1, len(h) - 5), 5):
            inv.setdefault(h[k:k + 6], set()).add(n)
    out_map, miss = {}, 0
    for e in entries:
        head = R.plain(e['first_line'])
        cand = set()
        for k in range(0, max(1, len(head) - 5), 2):
            cand |= inv.get(head[k:k + 6], set())
        # 目次只存了首句 12 字：在正文里找它，比整首相似度（会被篇幅差异拉低）可靠
        best, bi = 0, None
        for n in cand:
            body = plain[n]
            pos = body.find(head)
            s_ = len(head) / len(body) if pos >= 0 else SequenceMatcher(None, head, body, autojunk=False).ratio() * 0.5
            if s_ > best:
                best, bi = s_, n
        if bi is None or best < 0.05:      # 首句 12 字占整首 6%~20%，找到即 0.06 以上
            miss += 1
            continue
        out_map[str(e['no'])] = f"{recs[bi]['rel']}#{recs[bi]['idx']}"
    with open(out, 'w', encoding='utf-8') as fp:
        json.dump(out_map, fp, ensure_ascii=False, indent=1, sort_keys=True)
        fp.write('\n')
    print(f'目次对照表：{len(out_map)} 条配到库内记录，{miss} 条配不上 → {out}')


def sync_anthology(retitles):
    """把 `anthologies/songci300.json` 条目的 title 对到库内同一首的记录上。

    这份目次是另一份来源（识典古籍朱祖谋集解本，284 首）抽出来的，title 里还是
    「宴山亭」「元夕」这类原书小题；篇目统一之后，凡是改过的记录都在 `retitles` 里，
    按 (文件, 下标) 找回去看它在目次里是哪一条，把 title 一并改掉。
    """
    path = os.path.join(R.ROOT, 'anthologies', 'songci300.json')
    data = json.load(open(path, encoding='utf-8'))
    if not os.path.exists(ANTH_MAP):
        print(f'    {ANTH_MAP} 不存在，目次篇目未同步（先跑 --dump-anth 生成）')
        return 0
    fb = json.load(open(ANTH_MAP, encoding='utf-8'))
    changed = 0
    for e in data['entries']:
        key = fb.get(str(e['no'])) or fb.get('zzm:' + e['source'].split('/')[-1].split('?')[0])
        if not key:
            continue
        where = tuple(key.split('#', 1))
        t = retitles.get((where[0], int(where[1])))
        if t and t != e.get('title'):
            print(f'    目次第 {e["no"]} 首 {e.get("title")} → {t}')
            e['title'] = t
            changed += 1
    if changed:
        data['note'] = (data.get('note') or '') + \
            '　2026-11-01：篇目与本库记录对齐（「词牌·小题」/「词牌·正文首句」），见 scripts/anthology/align_songci300.py。'
        with open(path, 'w', encoding='utf-8') as fp:
            json.dump(data, fp, ensure_ascii=False, indent=1)
            fp.write('\n')
    print(f'anthologies/songci300.json 改篇目 {changed} 条')
    return changed


def title_of(r):
    """补录记录的篇目：词牌·小题，或 词牌·正文首句（与库内同一条规则）。"""
    e = r['entry']
    rhythm = SEP.join(p.strip() for p in re.split(r'[・·]', e['rhythmic']) if p.strip())
    note = clean_note(e['note'])
    if note:
        return rhythm + SEP + note
    return rhythm + SEP + han(r['body'][0])[:12]


def dump_append(rel, recs):
    """把若干条记录追加到顶层数组末尾，既有记录一字不动。

    做法是纯文本操作：定位最后一个 `}`，在它后面接 `,\n` 加新记录，再收尾。
    不去猜末条记录的缩进 —— 这些文件是历次抓取拼起来的，末条记录的行内缩进
    （`"id": …` 前可能是 2 格或 4 格）、`}` 前后有没有尾空，一处一个样，写死模板必错。
    """
    path = os.path.join(R.ROOT, rel)
    text = open(path, encoding='utf-8').read()
    close = text.rindex(']')
    before = text[:close]
    last_brace = before.rindex('}')
    items = []
    for r in recs:
        fields = [f'    "{k}": {json.dumps(v, ensure_ascii=False)}'
                  for k, v in r.items() if k in ('author', 'paragraphs', 'rhythmic', 'title', 'tags', 'id')]
        items.append('{\n' + ',\n'.join(fields) + '\n  }')
    text = before[:last_brace + 1] + ',\n  ' + ',\n  '.join(items) + '\n' + text[close:].lstrip()
    open(path, 'w', encoding='utf-8').write(text)
    json.load(open(path, encoding='utf-8'))
    print(f'    追加 {len(recs)} 条到 {rel}（现 {len(json.loads(text))} 条）')


def _record_spans(text):
    """顶层数组里每条记录的 (起, 止)。"""
    spans, depth, in_str, esc, begin = [], 0, False, False, None
    for i, ch in enumerate(text):
        if in_str:
            if esc:
                esc = False
            elif ch == '\\':
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch in '[{':
            depth += 1
            if ch == '{' and depth == 2:
                begin = i
        elif ch in ']}':
            if ch == '}' and depth == 2:
                spans.append((begin, i + 1))
            depth -= 1
    return spans




if __name__ == '__main__':
    main()
