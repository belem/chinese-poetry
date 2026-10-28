#!/usr/bin/env python3
"""把 OCR 成 □ 的句读还原成标点（只处理「疑问/语气词 + □ + 汉字」这一类）。

  python3 scripts/fix_punct_box.py            # 预演：只打印将要改的行
  python3 scripts/fix_punct_box.py --apply    # 写回，并登记进度

判据只有一条，够用也够窄：□ 夹在汉字之间，前字是疑问/语气词，后接新句子起首的词，
且后字不是「也」「者」「之」这类只能续句的字。这样能一口气收掉白话小说里
「你怎么瞒得过我□我这左耳往上一扯」这类问号缺失，又不会碰到「掣做个肉□子」这类真缺字
（那得逐句对刻本，不归这一支，见 AGENTS.md 的缺字对勘流程）。

改的是标点，不是字：□ → ？ / ！ / ，。只动这一个字符，正文其余一字不改。
"""
import argparse, json, os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HAN = r'\u4e00-\u9fff'

# 前字：疑问词、语气词。这些字后面直接接下一句，中间那个字只能是句末标点。
Q_BEFORE = '谁何甚怎岂那那吗呢哩么否耶乎哉哉我你他您咱俺哥师父妖猴君卿吾汝尔'
# 后字：典型的新句起首。见了它，前面必然是句末标点。
NEXT_START = '我你他您咱俺这那哥师父妖猴君卿吾汝尔'
# 后字若是这些，就是在词中间，不动
KEEP = set('也者之于的了个们么得地')

CJK_SENT = re.compile(rf'(?<=[{HAN}])□(?=[{HAN}])')


def judge(pre, nxt):
    """返回替换字符；判不了返回 None。"""
    if not pre or not nxt or nxt in KEEP:
        return None
    p, n = pre[-1], nxt
    if p in Q_BEFORE and n in NEXT_START:
        return '？'
    if p in '啊呀呵嗄吓' and n in NEXT_START:
        return '！'
    return None


def scan(path):
    with open(path, encoding='utf-8') as fp:
        return json.load(fp)


def fix_file(rel, apply):
    path = os.path.join(ROOT, rel)
    data = scan(path)
    changes = []
    for rec in data:
        for i, para in enumerate(rec['paragraphs']):
            out, pos = [], 0
            for m in CJK_SENT.finditer(para):
                j = m.start()            # □ 的位置（正则整个匹配就是这一个字）
                rep = judge(para[max(0, j - 1):j], para[j + 1:j + 2])
                if not rep:
                    continue
                out.append(para[pos:j]); out.append(rep)
                pos = j + 1
                changes.append((rec['title'], para[max(0, j - 12):j + 12], rep))
            if out:
                out.append(para[pos:])
                rec['paragraphs'][i] = ''.join(out)
    return data, changes


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('files', nargs='*',
                    default=['明/诗/poet.ming.json', '清/诗/poet.qing.json'])
    ap.add_argument('--apply', action='store_true')
    ap.add_argument('--reviewer', default='codebuddy')
    ap.add_argument('--date', default='')
    a = ap.parse_args()
    total = 0
    for rel in a.files:
        data, changes = fix_file(rel, a.apply)
        total += len(changes)
        print(f'{rel}: {len(changes)} 处')
        for t, ctx, rep in changes[:5]:
            print('   ', t, '|', ctx, '→', rep)
        if a.apply and changes:
            with open(os.path.join(ROOT, rel), 'w', encoding='utf-8') as fp:
                json.dump(data, fp, ensure_ascii=False, indent=2)
                fp.write('\n')
    print('合计', total, '处' + ('' if a.apply else '（预演，未写回）'))


if __name__ == '__main__':
    main()
