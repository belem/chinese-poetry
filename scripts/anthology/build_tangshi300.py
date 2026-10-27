#!/usr/bin/env python3
"""从识典古籍《唐詩三百首注疏》（上海掃葉山房石印本，bookId XYXTSSBSZS）的抓取结果里抽目次。

底本排版两套：
  卷三以后「标题」单独成行、作者单独成行，正文另起段落 —— 最好切；
  卷一、卷二整卷挤成段落，标题只能靠排除法猜，不可靠，所以这里只收能稳妥切出的部分
  （卷三以后的七言古诗、五言律诗等），并把条目对应的扫描页记在 source 里，
  没切出来的部分留白，不假装它是干净目次。

  python3 scripts/anthology/crawl_book.mjs XYXTSSBSZS 1l1rcvgxdybl0 <work>/tsss_XYXTSSBSZS.json
  python3 scripts/anthology/build_tangshi300.py --work <work> --out anthologies/tangshi300.json
"""
import argparse
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import split_book as sb  # noqa: E402

BOOK = 'XYXTSSBSZS'
VOLUME_NOISE = re.compile(r'(卷|校正|手編|注疏|先生)')


def first_poetic(paras, n=10):
    """跳过夹注 / 诗序，取第一段像诗的正文的首句。"""
    for p in paras:
        if len(sb.sentences(p)) >= 2 and not sb.PREAMBLE.search(p):
            return sb.first_sentence(p, n)
    return ''


def split_page(paras, cat, page):
    """一页里可能有多首：标题短行开头就是新的一首，正文段落归给当前这首。"""
    out, i = [], 0
    while i < len(paras):
        p = paras[i]
        if sb.is_category(p):
            cat, i = p, i + 1
            continue
        if not sb.is_short_line(p) or VOLUME_NOISE.search(p):
            i += 1
            continue
        title, author, j = p, None, i + 1
        if j < len(paras) and sb.is_short_line(paras[j]) and not sb.is_subhead(paras[j]) \
                and len(paras[j]) <= 4 and not VOLUME_NOISE.search(paras[j]):
            author, j = paras[j], j + 1
        while j < len(paras) and (sb.is_short_line(paras[j]) or sb.PREAMBLE.search(paras[j])) \
                and not VOLUME_NOISE.search(paras[j]):
            j += 1
        body = paras[j] if j < len(paras) else ''
        first = first_poetic([body]) if body else ''
        if first:
            out.append(dict(category=cat, author=author, title=title, first_line=first, source=page))
        i = j + 1
    return out, cat


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--work', required=True)
    ap.add_argument('--out', required=True)
    args = ap.parse_args()

    pages = sb.load(os.path.join(args.work, f'tsss_{BOOK}.json'))
    entries, cat, seen = [], None, set()
    for pg in pages:
        page = 'XYXTSSBSZS/' + pg['url'].split('/chapter/')[-1]
        items, cat = split_page(sb.paragraphs(pg['text']), cat, page)
        for e in items:
            if e['title'] in seen:      # 目录页与正文页会重复出现同名条目
                continue
            seen.add(e['title'])
            entries.append(e)
    for bad in ('附韓愈平淮西奉敕撰', '漢江臨眺', '桃源行'):   # 夹注 / 卷首题署 / 诗序，不是目次
        entries = [e for e in entries if e['title'] != bad]

    data = dict(
        name='唐诗三百首',
        book=dict(title='唐詩三百首注疏', editor='蘅塘退士 編、章燮 注', edition='上海掃葉山房石印本',
                  source=f'https://www.shidianguji.com/zh/book/{BOOK}'),
        note='据识典古籍扫描本正文顺序抽取，只收能稳妥切出标题的条目（卷三及其后）；category 照底本编排；'
             'first_line 为首句前 10 字，只作匹配锚点，不是正文。',
        entries=[dict(no=i + 1, **e) for i, e in enumerate(entries)],
    )
    os.makedirs(os.path.dirname(args.out) or '.', exist_ok=True)
    json.dump(data, open(args.out, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(f'{len(entries)} entries → {args.out}')


if __name__ == '__main__':
    main()
