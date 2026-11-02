#!/usr/bin/env python3
"""`reference/儒林外史.txt` → `清/小说/儒林外史/rulinwaishi.json`（issue #244）。

旧文件整份删除后按本底本重出。与上一版（`scripts/import_novel_chapter.py` 的 `rulin`）
同一份底本，差别在于**标点按读法重校**，不只做机械清洗：

  * 底本缺的句读补上。最长的一类是「某某道“……”」后无冒号（全本 63 处），
    一律补作「某某道：“……”」；对话引号收尾后直接接叙述（「……坐下。”他便问道」）也补句号。
    补的每一类都列在 `FIXES` / `RULES` 里，可逐条核。
  * 底本点多了的（`，，` `。。` `！。`）、半角标点、制表符当破折号，一并规整。
  * 底本自身的录入残渣（拼音首字母、私用区缺字）按上下文改正或标缺字，同上一版。

版式：

    《儒林外史》 清  吴敬梓

    章节数：56
    字数：326585
    ========简介========
    ……
    ========正文========
    第一回 说楔子敷陈大义 借名流隐括全文
    “人生南北多歧路，……

  * 书头（著者行、章节数、字数、简介、`========正文========`）不进正文；
  * 一段一行，空行不是段落；
  * 题名 `第N回　回目`（回目上下句之间一个全角空格）；
  * `id` 规则同 `scripts/shidian/convert.py`（author|title|正文 blake2b），改正文才变。

    python3 scripts/import_rulin_waishi.py            # 写文件
    python3 scripts/import_rulin_waishi.py --check    # 只比对，不写
"""
import argparse
import hashlib
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = 'reference/儒林外史.txt'
OUT = '清/小说/儒林外史/rulinwaishi.json'
AUTHOR = '吴敬梓'
DYNASTY = '清'

BODY_MARK = '========正文========'
INTRO_MARK = '========简介========'

CN = {c: i for i, c in enumerate('零一二三四五六七八九')}
HEAD = re.compile(r'^第([〇零一二三四五六七八九十百0-9]+)回[\s　]*(\S.*)$')

# 底本字面录入残渣：拼音首字母、数字顶替标点、重出的人名。逐处改，字面依据见 docs/通俗小说重建.md
TYPO_FIXES = (
    ('你不要管p快换了衣服P我同你去', '你不要管，快换了衣服，我同你去'),   # p/P → 逗号
    ('买嘱枪手dk几案', '买嘱枪手代倩几案'),                             # dk 是「代倩」
    ('写字与他哥p说', '写字与他哥，说'),                                # p → 逗号
    ('一个抱着毡包0一直来到河下', '一个抱着毡包，一直来到河下'),         # 0 → 逗号
    ('ZJ随即着家人送了五两银子', '随即着家人送了五两银子'),              # ZJ 是重出的「郑」
    ('邀小弟在他幕ZG事', '邀小弟在他幕中事'),                           # ZG → 中
    ('一个嘴巴把聘娘DD在地', '一个嘴巴把聘娘打倒在地'),                  # DD → 打倒
)

# 标点规整（先改错字，再规整标点）
PUNCT_FIXES = (
    ('，，', '，'), ('。。', '。'), ('；；', '；'), ('：：', '：'),
    ('，。', '。'), ('。，', '。'), ('，；', '；'), ('，：', '：'),
    ('！。', '！'), ('？。', '？'), ('”。', '。'), ('”，。', '”。'), ('”，，', '”，'),
)

# 底本用两个制表符 ─ 当破折号（「几时。──只是母亲在家」）
DASH_FIX = re.compile('─{2,}')

# 半角标点夹在汉字中间：改成全角
HALF_PUNCT = ((';', '；'), (',', '，'), ('!', '！'), (':', '：'), ('?', '？'))

# ── 补句读：底本漏点的地方，按读法补上 ────────────────────────────────
# 1) 「说道“」：说话人之后的冒号缺失（底本 63 处）。只有「道」承前是说话动词才算 ——
#    「叫“三哥”」「叫“老爹”」是称名不是对白，单字「叫」后不加冒号（底本这 9 处照录）
SAY_COLON = re.compile(r'((?<!叫)道|说道|问道|答道|喊道|叫道|嚷道|喝道|回道|应道|骂道|笑道|哭道)[“「]')
# 2) 底本把冒号点成逗号：「禀道，“」「问道，“」
SAY_COMMA = re.compile(r'([说道问答喊叫])[，,](?=[“「])')
# 3) 整段引语收尾接叙述：`。”他便问道` / `。”说著`，补句号。后引号后面紧跟汉字
#    且没有句读的才算；`。”` 已经是句末，不再叠句号
SPEECH_END = re.compile(r'([”」])(?![，。！？；：、”』」\s])(?=[\u4e00-\u9fff])')


def PUNCT_FIXES_LOOP(line):
    """重复标点可能叠出来（`”。` 补句号后再叠一个），反复做到不再变化。"""
    while True:
        before = line
        for wrong, right in PUNCT_FIXES:
            line = line.replace(wrong, right)
        if line == before:
            return line


def fix_punct(line):
    line = SPEECH_END.sub(r'\1。', line)        # 先补错位的地方，别把旧错当成对的
    line = PUNCT_FIXES_LOOP(line)
    line = SAY_COMMA.sub(r'\1：', line)
    line = SAY_COLON.sub(r'\1：', line)
    return line


def clean(line):
    for wrong, right in TYPO_FIXES:
        line = line.replace(wrong, right)
    for wrong, right in PUNCT_FIXES:
        line = line.replace(wrong, right)
    line = DASH_FIX.sub('——', line)
    for half, full in HALF_PUNCT:
        line = re.sub(r'(?<=[\u4e00-\u9fff])' + re.escape(half) + r'(?=[\u4e00-\u9fff])', full, line)
    return fix_punct(line)


def cn2int(s):
    s = s.replace('〇', '零')
    if s.isdigit():
        return int(s)
    if '百' not in s and '十' not in s and len(s) > 1:
        return int(''.join(str(CN[c]) for c in s if c in CN))
    if '百' in s:
        hi, lo = s.split('百')
        lo = lo.lstrip('零')
        return (CN[hi] if hi else 1) * 100 + (cn2int(lo) if lo else 0)
    if '十' not in s:
        return CN[s]
    hi, lo = s.split('十')
    return (CN[hi] if hi else 1) * 10 + (CN[lo] if lo else 0)


def existing_ids():
    """库里其余文件的全部 id（新文件自己不算，免得自己撞自己）。"""
    taken = set()
    for dirpath, dirs, files in os.walk(ROOT):
        dirs[:] = [d for d in dirs if d not in
                   {'.git', '.github', '.cnb', 'docs', 'reference', 'scripts', 'loader',
                    'authors', 'dynasties', 'rank', 'strains', 'images'}]
        for f in files:
            if not f.endswith('.json'):
                continue
            rel = os.path.relpath(os.path.join(dirpath, f), ROOT)
            if rel == OUT:
                continue
            try:
                data = json.load(open(os.path.join(dirpath, f), encoding='utf-8'))
            except Exception:
                continue
            if isinstance(data, list):
                for r in data:
                    if isinstance(r, dict) and r.get('id'):
                        taken.add(r['id'])
    return taken


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


def parse():
    recs, cur, in_body = [], None, False
    for raw in open(os.path.join(ROOT, SRC), encoding='utf-8'):
        line = raw.strip('\n').replace('\u3000', ' ').strip()
        if not line:
            continue
        if line == INTRO_MARK:
            continue
        if line == BODY_MARK:
            in_body = True
            continue
        if not in_body:
            continue
        m = HEAD.match(line)
        if m:
            head = re.sub(r'\s+', '\u3000', m.group(2).strip())
            cur = {'num': cn2int(m.group(1)), 'head': head, 'paragraphs': []}
            recs.append(cur)
            continue
        cur['paragraphs'].append(clean(line))
    return recs


def build(recs, taken):
    nums = [r['num'] for r in recs]
    if nums != list(range(1, len(nums) + 1)):
        raise SystemExit(f'回次不连续：{nums[:8]}… 共 {len(recs)} 条')
    out = []
    for r in recs:
        assert r['paragraphs'], f'第{r["num"]}回 无正文'
        title = f"第{r['num']}回\u3000{r['head']}"
        rec = {'author': AUTHOR, 'title': title, 'dynasty': DYNASTY,
               'paragraphs': r['paragraphs']}
        rec['id'] = make_id(AUTHOR, title, rec['paragraphs'], taken)
        out.append(rec)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--check', action='store_true', help='只比对现有文件，不写')
    args = ap.parse_args()
    recs = build(parse(), existing_ids())
    text = json.dumps(recs, ensure_ascii=False, indent=2) + '\n'
    dst = os.path.join(ROOT, OUT)
    chars = sum(len(p) for r in recs for p in r['paragraphs'])
    print(f'{OUT}: {len(recs)} 回，{sum(len(r["paragraphs"]) for r in recs)} 段，{chars} 字')
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
