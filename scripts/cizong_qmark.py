#!/usr/bin/env python3
"""《词综》正文里的问号逐条定案。

  python3 scripts/cizong_qmark.py              # 预演：分类、条数、样例
  python3 scripts/cizong_qmark.py --apply      # 写回 汇编/词综/卷N.json 的正文，出 docs/词综问号.tsv

底本 `reference/词综.txt` 的句读是抄录时补的，末句多印成「？」。2133 处里有相当一部分本来就是
问句（`谁理商声帘外悄？`、`春去人间无路？`），不能一刀切成句号；另一些是陈述句末被印成了问号。
本脚本只按句子的形态判，不作书证：

  1. **疑问形态**（保留问号）：句末或句中有疑问词——谁、何、几、那/哪、怎、岂、安、焉、谁、
     宁、肯（「肯把菱花扑碎」）… 以及「…否」「…无」「…未」「…不」「…多少」「…几许」这类句式；
     还有对仗两句一疑一答、上句问下句答的（「何处合成愁？离人心上秋。」），上句保留问号。
  2. **陈述形态**（问号→句号）：句子里没有疑问词，句末也没有「否/无/未/不/多少/几许」这类收尾。
  3. **韵脚句**：词的一句末若是同样没有疑问词的陈述句，问号改句号；改与不改都不动韵脚字。

判的是**标点**，不动正文一个字。标题取正文首句，改完按新句读重算（`_retitle`）：
开头那一句本来就落在 8~14 字里的，标题跟着换成新句；只剩标点、判不准的记 `待核`，不改。

这一轮是**按句子形态**判，不是逐句对勘刻本：`？` 与 `。` 的分别按上表的口径定，
所以份量只在「有没有疑问词」上。逐句对上原刻本的句读，等 `docs/词综重建.md` 里说的对勘那一步。
"""
import argparse
import csv
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import import_cizong as ic  # noqa: E402

ROOT = ic.ROOT
OUT = ic.OUT
DOC = 'docs/词综问号.tsv'

# 句中出现这些字眼，句末的问号是正经问号（`问君能有几多愁？`、`谁理商声帘外悄？`）。
# 「几」「肯」「无」「未」这类单字太泛（`几度相思`、`肯把菱花扑碎`、`无绪`），不单列
INTERROG = ('谁', '何', '哪', '怎', '岂', '焉得', '多少', '几许', '甚时', '如何', '若何', '争知',
            '知否', '得否', '在否', '谁知', '几时', '几度', '几番', '能有几',
            '争忍', '肯为', '肯把', '肯念', '肯忘', '肯负', '肯相', '肯与', '肯来', '肯向',
            '肯信', '肯听', '肯教', '肯放', '肯同', '肯自', '肯将', '肯惜', '肯惜', '肯笑')
# 句末是这些收尾的，也是问句（`一笑相逢且开口？`、`今宵且住？`）
TAIL_Q = ('否', '未', '多少', '几许', '何', '谁', '那', '怎', '如何', '安在',
          '几', '几时休', '几时', '几度', '几番', '无')
# 这些说法里带「无」「未」「不」却不是问句（`无绪，无绪`、`不如归去`），剔掉再判
NEG_NOT_Q = ('不如归去', '无可奈何', '无计', '无绪', '无数', '无穷', '无端', '无限', '无据',
             '无凭', '无绪', '未有', '不知', '不见', '不管', '不禁', '不道', '不成', '不似',
             '未消', '未减', '未是', '未了', '不到', '不尽', '无数', '无人', '无语', '无尘',
             '无觅处', '无处', '无路', '未老', '未肯', '不觉', '不堪', '不语', '不言')


def sent_text(s):
    """一个句段去掉标点后的汉字。"""
    return ''.join(ic.HAN.findall(s))


def is_question(seg_text):
    """句段（不含末尾问号）像不像问句。→ True/False/None（None = 判不准）"""
    t = seg_text
    if not sent_text(t):
        return None
    probe = t
    for w in NEG_NOT_Q:
        probe = probe.replace(w, '□' * len(w))
    # 「谁与」作「与谁」讲（`谁与共秋醉`）不是疑问：只认「谁与」后面接单字的说法
    probe = re.sub(r'谁与.', '□□□', probe)
    # 「无人」「无计」这类否定词不是疑问收尾，但与「谁/何」同句时不影响判断

    if any(w in probe for w in INTERROG):
        return True
    if t.endswith(TAIL_Q):
        return True
    return False


def split_marks(para):
    """正文 → [(句段, 末尾标点)]，句段不含标点。"""
    out = []
    for m in re.finditer(r'([^，。？！、；：]*)([，。？！、；：]?)', para):
        if m.group(1) or m.group(2):
            out.append([m.group(1), m.group(2)])
    return out


def fix_para(para, log, line):
    """一句一句地判：问号该留的留，该改句号的改。返回 (新正文, 是否改动)。"""
    segs = split_marks(para)
    changed = False
    for i, (txt, mark) in enumerate(segs):
        if mark != '？':
            continue
        q = is_question(txt)
        if q is None:
            log.append((line, txt, '', '待核', '句段只有标点'))
            continue
        if q:
            log.append((line, txt, '？', '留', '疑问词或疑问收尾'))
            continue
        # 陈述句末的问号：改句号（句末），句中则改逗号
        new = '。' if i == len(segs) - 1 else '，'
        # 词的分句之间本来就多断在顿号、逗号处，句末这个位置改句号最稳
        segs[i][1] = '。'
        log.append((line, txt, '？', '。', '无疑问词、非疑问收尾'))
        changed = True
    return ''.join(t + m for t, m in segs), changed


def _retitle(title, paras):
    """正文句读变了，标题里的首句跟着重算（只换 `·` 后面那一截）。"""
    tune, _, sub = title.partition('·')
    if not sub:
        return title
    lead = ic.first_line(paras)
    if not lead:
        return title
    return f'{tune}·{sub}' if sub == lead else f'{tune}·{lead}'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--apply', action='store_true')
    args = ap.parse_args()

    log, touched, n_q, n_fix = [], set(), 0, 0
    for f in sorted(os.listdir(os.path.join(ROOT, OUT))):
        if not re.fullmatch(r'卷.+\.json', f):
            continue
        path = os.path.join(ROOT, OUT, f)
        arr = json.load(open(path, encoding='utf-8'))
        dirty = False
        for r in arr:
            paras = r.get('paragraphs')
            if not paras:
                continue
            new = []
            for p in paras:
                if '？' not in p:
                    new.append(p)
                    continue
                n_q += p.count('？')
                got, ch = fix_para(p, log, r['source_line'])
                if ch:
                    n_fix += p.count('？') - got.count('？')
                new.append(got)
            if new != paras:
                r['paragraphs'] = new
                r['title'] = _retitle(r['title'], new)
                dirty = True
        if dirty:
            touched.add(f)
            if args.apply:
                with open(path, 'w', encoding='utf-8') as fp:
                    fp.write(json.dumps(arr, ensure_ascii=False, indent=2))
                    fp.write('\n')

    keep = sum(1 for x in log if x[3] == '留')
    print(f'正文带问号的句子 {n_q} 处：'
          f'本来就是问句、留 {keep} 处；陈述句末印成问号、改 {n_fix} 处；'
          f'待核 {sum(1 for x in log if x[3] == "待核")} 处')
    print(f'受影响的卷文件 {len(touched)} 个')
    if not args.apply:
        for x in [y for y in log if y[3] == '。'][:8]:
            print('  例：', x[1], '→ 。')
        for x in [y for y in log if y[3] == '留'][:8]:
            print('  留：', x[1], '？')
        return
    with open(os.path.join(ROOT, DOC), 'w', encoding='utf-8') as fp:
        fp.write('line\tsentence\tbefore\tafter\tnote\n')
        for row in log:
            fp.write('\t'.join(str(x) for x in row) + '\n')
    print(f'→ 写回 {len(touched)} 个卷文件，明细 {DOC}')


if __name__ == '__main__':
    sys.exit(main())
