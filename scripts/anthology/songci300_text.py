#!/usr/bin/env python3
"""《宋词三百首》PR B：正文勘误，逐处注明依据。

判据沿用 [`docs/宋词对勘.md`](../宋词对勘.md)：只改「本库读法在任何古籍里都找不到」的字，
异文、异体、别写一律不动。这一批处理的都是「多一个字 / 少一个字 / 明显是形近、音近误录」，
每一处的证据写在 `FIXES` 里（识典古籍的检索串写进注释，可复现）。

  python3 scripts/anthology/songci300_text.py            # 预演，逐条列出
  python3 scripts/anthology/songci300_text.py --apply --date YYYY-MM-DD --reviewer <名字>
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import progress as pg  # noqa: E402
import anthology.patch_json as pj  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# (文件, 记录下标, 段号, 原文, 改为, 依据)
FIXES = [
    ('宋/宋词/ci.song.22000.json', 46, 1, '朝云信断知何处□应作襄王春梦去', '朝云信断知何处，应作襄王春梦去',
     '晏几道《临江仙》：底本、《小山词》（四库全书本）、《元献遗文》、《宋名家词》、《花草稡编》、'
     '《御选历代诗馀》卷三十一、《词综》卷五 都作「知何處，應作襄王春夢去」，无缺字；库内的 □ 是早年'
     '断句留下的残渣'),
    ('宋/宋词/ci.song.22000.json', 76, 1, '花底深朱户。何处□半黄梅子', '花底深朱户。何处半黄梅子',
     '贺铸《感皇恩》：底本、《乐府雅词》（四部丛刊本）、《花庵词选》、《宋词三百首》集解本、《御选历代诗馀》'
     '都作「花底深朱户何處，半黄梅子」，同 #46，□ 是断句残渣'),
    ('宋/宋词/ci.song.22000.json', 1001, 0, '韵霜余已失长淮阔', '霜余已失长淮阔',
     '苏轼《木兰花令》：底本、《东坡词》（四库全书本）、《东坡先生全集》卷七十四、《重编东坡先生外集》、'
     '《宋名家词·东坡词》、《御选历代诗馀》卷三十一 都起于「霜餘」；库内首字「韵」是上一行诗题的落款，'
     '误入正文'),
    ('宋/宋词/ci.song.22000.json', 1099, 0, '犹自学', '犹自学当年游历。',
     '史达祖《喜迁莺》：底本、《词谱》卷六、《御定词谱》、《词综》卷十七、《古今词选》卷八 都作'
     '「猶自學、當年游歷」。库内正文在「犹自学」处被截断，下一段才起于「当年游历」，这里把断口接上'),
    ('宋/宋词/ci.song.22000.json', 1099, 1, '当年游历。怕万一误玉人，夜寒帘隙。', '怕万一误玉人、夜寒窗际帘隙。',
     '同上，并补「窗际」二字：底本、《词综》卷十七（汪氏裘杼楼本）、《御定词谱》卷六、《词谱》卷六 都作'
     '「誤玉人、夜寒窗際簾隙」；《词源》卷下引本无「窗际」，两读，按底本与多数本子补'),
    ('宋/宋词/ci.song.22000.json', 1095, 0, '沽酒垆前', '沽酒楼前',
     '俞国宝《风入松》：底本、《词洁》卷三、《花草稡编》卷八、《西湖志摘粹补遗》卷十、'
     '《古今图书集成·山川典》 都作「沽酒樓前」；「垆」是「楼」的形近误录'),
    ('宋/宋词/ci.song.22000.json', 1095, 0, '暖风十里廲人天', '暖风十里丽人天',
     '同上：「十里麗人天」是「暖风十里丽人天」的名句，《草堂诗馀正集》《草堂诗馀前集》《花草稡编》'
     '《古今词话·词辨》《御选历代诗馀》都作「麗」；库内「廲」是「麗」的形近误录'),
]


def _patch_paragraphs(rel, edits):
    """逐段换掉 paragraphs，不动文件自己的排版。

    这些文件是历次抓取、拼接留下的，一段一行、缩进各不同，整段 dumps 会把一条记录压成一行，
    改两个字变成改整条。做法同 patch_json：只替换值的那一段。同一记录里若段落数也变了
    （史达祖那条要合并两段），就把改动**都从后往前**做 —— 先改靠后的段落，偏移不会串。
    """
    path = os.path.join(ROOT, rel)
    text = open(path, encoding='utf-8').read()
    spans = pj._spans(text)
    head = '"paragraphs": '
    for idx in sorted(edits, reverse=True):
        a, b = spans[idx]
        body_open = a
        j = text.find(head, a, b)
        if j < 0:
            raise SystemExit(f'{rel}#{idx} 没有 paragraphs 字段')
        k = j + len(head)
        end, strs = _array_span(text, k)
        old_val = [json.loads(text[x:y]) for x, y in strs]
        new_val = list(edits[idx])
        if len(old_val) != len(new_val):
            enc = json.dumps(new_val, ensure_ascii=False)
            text = text[:k] + enc + text[end:]
            continue
        for i in range(len(strs) - 1, -1, -1):
            if new_val[i] == old_val[i]:
                continue
            x, y = strs[i]
            text = text[:x] + json.dumps(new_val[i], ensure_ascii=False) + text[y:]
    json.loads(text)
    open(path, 'w', encoding='utf-8').write(text)


def _array_span(text, k):
    """text[k] == '['：返回 (数组结尾的下标+1, 各字符串值的 (起, 止))。"""
    depth, strs, p = 0, [], k
    while True:
        ch = text[p]
        if ch == '[':
            depth += 1
        elif ch == ']':
            depth -= 1
            if depth == 0:
                return p + 1, strs
        elif ch == '"':
            q = p + 1
            while text[q] != '"' or text[q - 1] == '\\':
                q += 1
            strs.append((p, q + 1))
            p = q + 1
            continue
        p += 1


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--apply', action='store_true')
    ap.add_argument('--date')
    ap.add_argument('--reviewer')
    args = ap.parse_args()

    files = {}
    plans = []
    for rel, idx, pno, old, new, why in FIXES:
        if rel not in files:
            files[rel] = json.load(open(os.path.join(ROOT, rel), encoding='utf-8'))
        para = files[rel][idx]['paragraphs'][pno]
        if old not in para:
            print(f'跳过：{rel}#{idx} 段{pno} 找不到「{old}」', file=sys.stderr)
            continue
        plans.append((rel, idx, pno, old, new, why))

    for rel, idx, pno, old, new, why in plans:
        # 每处都在**最初读进来的**正片上改，别在上一步改过的串上再 replace：
        # #1095 两处一前一后，若第一处已换掉，第二处的定位串就不在原串里也可能换错位
        base = json.load(open(os.path.join(ROOT, rel), encoding='utf-8'))[idx]['paragraphs'][pno]
        for r2, i2, p2, o2, n2, _w in plans:
            if (r2, i2, p2) == (rel, idx, pno):
                base = base.replace(o2, n2)
        files[rel][idx]['paragraphs'][pno] = base
        print(f'{rel}#{idx} 段{pno}  「{old}」 → 「{new}」')
        print(f'    {why}\n')

    print(f'合计 {len(plans)} 处，涉及 {len({p[0] for p in plans})} 个文件')
    if not args.apply:
        return
    if not (args.date and args.reviewer):
        sys.exit('--apply 需要 --date 与 --reviewer')
    by_file = {}
    for rel, idx, pno, old, new, why in plans:
        by_file.setdefault(rel, set()).add(idx)
    for rel, idxs in by_file.items():
        # 一个文件一次写完：同一记录的多处改动都在 files[rel] 里，别读回原件再覆盖。
        # patch_json 只认单行字符串值，paragraphs 是数组，值那一段自己算（到 `]` 为止）
        edits = {}
        for idx in idxs:
            enc = json.dumps(files[rel][idx]['paragraphs'], ensure_ascii=False)
            edits[idx] = (enc, pj._value_span(open(os.path.join(ROOT, rel), encoding='utf-8').read(), ''))
        _patch_paragraphs(rel, {idx: files[rel][idx]['paragraphs'] for idx in idxs})
        fixes = [{'original': old, 'corrected': new, 'note': why} for r, i, p, old, new, why in plans if r == rel]
        pg.merge(rel, dict(status='fixed', reviewer=args.reviewer, date=args.date, fixes=fixes,
                           note='《宋词三百首》正文勘误：只改本库读法在古籍中找不到依据的字，'
                                '异文异体不动；逐条依据见 fixes 的 note（识典古籍可复现）。'))
    print(json.dumps(pg.write_index()['stats'], ensure_ascii=False))


if __name__ == '__main__':
    main()
