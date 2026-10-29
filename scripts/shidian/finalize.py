#!/usr/bin/env python3
"""convert_classic.py 的产出 → 落盘 JSON（补 id、按书定题名格式、注册 loader）。"""
import argparse, json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from convert import make_id

BOOK_TITLE = {
    'rulin': ('吴敬梓', lambda r: r['title']),          # 已在 head 里带「第X回」
}


def title_of(book, r):
    num, head = r['num'], (r.get('head') or '').strip()
    if book == 'rulin':
        return f'第{num}回' + (f'　{head}' if head else '')
    if book == 'jinghuayuan':
        return f'镜花缘·第{num}回' + (f'　{head}' if head else '')
    if book == 'fengshen':
        return f'封神演义·第{num}回' + (f'　{head}' if head else '')
    if book == 'soushenji':
        return f'搜神记·卷{num}'
    if book == 'yuewei':
        return f'阅微草堂笔记·{head}' if head else f'阅微草堂笔记·卷{num}'
    if book == 'yanshi':
        return f'喻世明言·第{num}卷' + (f'　{head}' if head else '')
    if book == 'jingshi':
        return f'警世通言·第{num}卷' + (f'　{head}' if head else '')
    if book == 'paiang':
        return f'二刻拍案惊奇·卷{num}' + (f'　{head}' if head else '')
    if book == 'yuchu':
        return f'虞初新志·卷{num}'
    if book == 'dongzhou':
        return f'东周列国志·第{num}回' + (f'　{head}' if head else '')
    if book == 'rongzhai':
        series, juan = divmod(num - 1, 16)
        name = ['随笔', '续笔', '三笔', '四笔', '五笔'][series]
        return f'容斋{name}·卷{juan + 1}'
    if book == 'xiaochuang':
        return f'小窗幽记·卷{num}'
    raise SystemExit('未知书：' + book)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('records')
    ap.add_argument('out')
    ap.add_argument('--book', required=True)
    ap.add_argument('--tags', help='逗号分隔')
    a = ap.parse_args()
    recs = json.load(open(a.records, encoding='utf-8'))
    taken, rows = set(), []
    for r in recs:
        title = title_of(a.book, r)
        body = [p for p in r['paragraphs'] if p.strip()]
        row = {'author': r['author'], 'title': title, 'paragraphs': body}
        if a.tags:
            row['tags'] = a.tags.split(',')
        row['id'] = make_id(r['author'], title, body, taken)
        rows.append(row)
    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    with open(a.out, 'w', encoding='utf-8') as fp:
        json.dump(rows, fp, ensure_ascii=False, indent=2)
        fp.write('\n')
    chars = sum(len(''.join(x['paragraphs'])) for x in rows)
    print(f'{len(rows)} 条，{chars} 字 → {a.out}')


if __name__ == '__main__':
    main()
