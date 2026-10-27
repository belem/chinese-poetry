#!/usr/bin/env python3
"""从识典古籍《宋詞三百首》（朱祖謀編，民國十三年朱祖母集解本，bookId 7374122395470135333）
的抓取结果里抽目次：作者 / 词牌 / 首句。

这本的章节页排版很规整：作者行 → 词牌行 → 正文段落。作者只在每组的第一首出现，
后面同作者的词不再重复署名，所以要顺延。

  python3 scripts/anthology/build_songci300.py --work /tmp/sd_songci --out anthologies/songci300.json
"""
import argparse
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import split_book as sb  # noqa: E402

BOOK = '7374122395470135333'
PERSON = re.compile(r'^[\u4e00-\u9fff]{2,4}$')
SKIP = re.compile(r'^(序|宋詞三百首|宋詞三百首目錄|目錄)$')


def split_page(paras, author):
    """一页一首词：短行里第一个是作者（可能缺），第二个是词牌，其余是正文。"""
    out, shorts, body = [], [], []
    for p in paras:
        if SKIP.match(p):
            continue
        if sb.is_short_line(p, max_len=12) and not body:
            shorts.append(p)
        else:
            body.append(p)
    if not body:
        return None, author
    if len(shorts) >= 2 and PERSON.match(shorts[0]):
        author, title = shorts[0], shorts[1]
    elif shorts:
        title = shorts[-1]
    else:
        title = None
    return dict(author=author, title=title, first_line=sb.first_sentence('\n'.join(body), 12)), author


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--work', required=True)
    ap.add_argument('--out', required=True)
    args = ap.parse_args()

    pages = sb.load(os.path.join(args.work, f'songci300_{BOOK}.json'))
    entries, author = [], None
    for pg in pages:
        e, author = split_page(sb.paragraphs(pg['text']), author)
        if e:
            e['source'] = 'zzm/' + pg['url'].split('/chapter/')[-1]
            entries.append(e)

    data = dict(
        name='宋词三百首',
        book=dict(title='宋詞三百首', editor='朱祖謀（彊村）編', edition='民國十三年朱祖母集解本',
                  source=f'https://www.shidianguji.com/zh/book/{BOOK}'),
        note='目次按识典古籍本正文顺序抽取；作者只在每组第一首署名，其余顺延。first_line 为首句前 12 字。',
        entries=[dict(no=i + 1, **e) for i, e in enumerate(entries)],
    )
    os.makedirs(os.path.dirname(args.out) or '.', exist_ok=True)
    json.dump(data, open(args.out, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(f'{len(entries)} entries → {args.out}')


if __name__ == '__main__':
    main()
