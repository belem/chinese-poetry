#!/usr/bin/env python3
"""`reference/初刻拍案惊奇.txt` → `清/小说/初刻拍案惊奇/chukepaiangjiqi.json`。

明凌濛初撰，四十卷。底本是简体排印本，版式与 `scripts/import_novel_chapter.py` 那一批同：

    书名：初刻拍案惊奇
    作者：凌濛初

    章节数：40
    字数：395570
    ========简介========
    ……
    ========正文========
    卷一 转运汉遇巧洞庭红 波斯胡指破鼍龙壳
    日日深杯酒满，朝朝小圃花开。
    ……

  * 书头（书名行、著者行、章节数、字数）不入正文；`========简介========` 之后的一段是底本的简介，
    底本没给它标题，挂到第一卷的 `prologue`（与《醒世恒言》卷首《叙》同一口径），不另立条目；
  * 分「卷」不分「回」，卷次用汉字，`title` 作「第N卷　篇名」；
  * 一段一行，空行不是段落；卷目行顶格起，与正文同段起首的「卷一…」不撞（正文另有一层缩进）。

底本自身的录入残渣，逐处列在下面，**只改认得出的，认不出的照录**：

  * `又送酒??内房中去`（卷十八）—— `??` 是「铺」（「??床」：铺设床铺）。
  * `银XX斜背解鸣`（卷二十五）—— 底本残渣，这句诗落到此处的正确读法待核，**不改**；
  * `\ue3ab翏曲倒悬`（卷四）—— 私用区码位是缺字，按全库口径（AGENTS.md 2b）包成 `{}`，字不补；
  * 「只见箱笼一空，，道」的一对逗号、「服用的东西，那几件旧衣旧裳」一类，按标点规整删多出来的那一下。

id 规则同 `scripts/backfill_ids.py`（作者+题名+正文+分段 blake2b 取 22 进制），改正文才变。

    python3 scripts/import_chuke_paian.py            # 写 清/小说/初刻拍案惊奇/chukepaiangjiqi.json
    python3 scripts/import_chuke_paian.py --check    # 只比对现有文件是否与底本一致
"""
import argparse
import hashlib
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = 'reference/初刻拍案惊奇.txt'
OUT = '清/小说/初刻拍案惊奇/chukepaiangjiqi.json'
AUTHOR, DYNASTY = '凌濛初', '明'
UNIT = '卷'
BODY_MARK = '========正文========'
INTRO_MARK = '========简介========'

CN = {c: i for i, c in enumerate('零一二三四五六七八九')}
CN['〇'] = 0


def cn2int(s):
    if s.isdigit():
        return int(s)
    s = s.replace('〇', '零')
    if '十' not in s:
        return CN[s]
    hi, lo = s.split('十')
    return (CN[hi] if hi else 1) * 10 + (CN[lo] if lo else 0)


# ── 底本残渣：认得出的改，认不出的照录 ──────────────────────────────────────

# 底本用 `??` 顶了认不出的字。只有一处，按文意读作「铺」（铺设床铺），另一处 XX 未改
TYPO_FIXES = (
    ('又送酒??内房中去', '又送酒铺内房中去'),                            # 卷十八
)

# 点重了的标点，删到该有的一个
PUNCT_FIXES = (
    ('，，', '，'), ('。。', '。'), ('，。', '。'), ('。，', '。'),
    ('；，', '；'), ('，；', '；'), ('：，', '：'), ('，：', '：'),
    ('！。', '！'), ('？。', '？'), ('”，。', '”。'), ('”，，', '”，'),
)

# 私用区码位是缺字，包成 {…}，字不补
PUA = ('\ue3ab',)                                                   # 卷四「{…}翏曲倒悬」

# 已经能定案、但**不改**的：只登记在 notes 里，供后人核准
OPEN_ISSUES = (
    ('银XX斜背解鸣', '卷二十五「银XX斜背解鸣」的 `XX` 是底本残渣，疑当作「釭」（银釭），待核'),
)


def clean(line):
    for wrong, right in TYPO_FIXES:
        line = line.replace(wrong, right)
    for wrong, right in PUNCT_FIXES:
        line = line.replace(wrong, right)
    for ch in PUA:
        line = line.replace(ch, '{%s}' % ch)
    return line


def parse():
    recs, cur, in_body, intro = [], None, False, []
    in_intro = False
    head = re.compile(r'^卷([一二三四五六七八九十]+)\s+(\S.*)$')
    for raw in open(os.path.join(ROOT, SRC), encoding='utf-8'):
        line = raw.rstrip('\n').replace('\u3000', ' ').strip()
        if not line:
            continue
        if not in_body:
            if line == INTRO_MARK:
                in_intro = True
            elif line == BODY_MARK:
                in_body, in_intro = True, False
            elif in_intro:
                intro.append(line)                    # 书头（书名行、著者行、章节数、字数）不进正文
            continue
        if line == INTRO_MARK:
            continue
        m = head.match(line)
        if m:
            cur = {'num': cn2int(m.group(1)),
                   'head': re.sub(r'\s+', '\u3000', m.group(2).strip()), 'paragraphs': []}
            recs.append(cur)
            continue
        if cur is None:
            raise SystemExit(f'正文之前出现了无归属的文字：{line[:30]!r}')
        cur['paragraphs'].append(clean(line))
    return recs, intro


def base22(digest, n):
    v = int.from_bytes(digest, 'big')
    out = []
    for _ in range(n):
        v, r = divmod(v, 22)
        out.append('0123456789abcdefghijklmnopqrstuvwxyz'[r])
    return ''.join(out)


def line_hash(body):
    return hashlib.blake2b('\x00'.join(body).encode(), digest_size=8).hexdigest()


def make_id(author, title, body, taken):
    key = f'{author}|{title}|{"".join(body)}|{line_hash(body)}'
    for salt in range(1, 16):
        size = 6 + max(0, salt - 1)
        digest = hashlib.blake2b((key if salt == 1 else f'{key}|{salt}').encode(), digest_size=16).digest()
        cand = base22(digest, size)
        if cand not in taken:
            taken.add(cand)
            return cand
    raise SystemExit('id 冲突：' + key[:40])


def existing_ids(dst):
    """库里其余文件的 id（本次要重写的文件除外）。"""
    taken = set()
    for dirpath, dirs, files in os.walk(ROOT):
        dirs[:] = [d for d in dirs if d not in
                   {'.git', '.github', '.cnb', 'docs', 'reference', 'scripts', 'loader',
                    'authors', 'dynasties', 'rank', 'strains', 'images'}]
        for f in files:
            if not f.endswith('.json'):
                continue
            path = os.path.join(dirpath, f)
            if os.path.relpath(path, ROOT) == dst:
                continue
            try:
                data = json.load(open(path, encoding='utf-8'))
            except (json.JSONDecodeError, UnicodeDecodeError):
                continue
            if isinstance(data, list):
                for r in data:
                    if isinstance(r, dict) and r.get('id'):
                        taken.add(r['id'])
    return taken


def build(recs, intro, taken):
    nums = [r['num'] for r in recs]
    if nums != list(range(1, len(nums) + 1)):
        raise SystemExit(f'卷次不连续 {nums[:8]}… 共 {len(recs)} 条')
    out = []
    for r in recs:
        assert r['paragraphs'], f'第{r["num"]}卷无正文'
        title = f'第{r["num"]}{UNIT}\u3000{r["head"]}'
        rec = {'author': AUTHOR, 'title': title, 'dynasty': DYNASTY}
        if r['num'] == 1:
            rec['prologue'] = intro    # 底本的简介（一段），挂在第一卷，与《醒世恒言》卷首《叙》同一口径
        rec['paragraphs'] = r['paragraphs']
        rec['id'] = make_id(AUTHOR, title, rec['paragraphs'], taken)
        out.append(rec)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--check', action='store_true', help='只比对现有文件，不写')
    args = ap.parse_args()
    dst = os.path.join(ROOT, OUT)
    parsed, intro = parse()
    recs = build(parsed, intro, existing_ids(OUT))
    text = json.dumps(recs, ensure_ascii=False, indent=2) + '\n'
    chars = sum(len(p) for r in recs for p in r['paragraphs'])
    print(f'{OUT}: {len(recs)} 卷，{sum(len(r["paragraphs"]) for r in recs)} 段，{chars} 字')
    for bad, note in OPEN_ISSUES:
        hit = any(bad in p for r in recs for p in r['paragraphs'])
        print(('  待核：' if hit else '  已消：') + note)
    if args.check:
        old = open(dst, encoding='utf-8').read() if os.path.exists(dst) else ''
        print('  一致' if old == text else '  不一致')
        return 0 if old == text else 1
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    open(dst, 'w', encoding='utf-8').write(text)
    print('  →', OUT)
    return 0


if __name__ == '__main__':
    sys.exit(main())
