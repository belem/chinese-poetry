#!/usr/bin/env python3
"""把 先秦/诗/poet.xianqin.json 里混进来的「文」拆出去，并消掉与已有专书的重复。

poet.xianqin.json 1311 条里大半不是诗：《论语》《孟子》《左传》诸篇、佛经、医经、
兵书、史书都在里面，与 先秦/论语、先秦/四书五经、先秦/楚辞、先秦/古文观止 等
已有专书大量逐字重复。本脚本按「一件作品只留一份正文」把它们分派出去：

  drop     正文已完整存在于某部专书 —— 删本条（专书正文不动）
  move     正文不在专书里，但属于某部书 —— 移到 先秦/文/<书>.json
  keep     确实是诗/辞 —— 留在 先秦/诗/poet.xianqin.json

判定先按题名前缀（`论语·学而篇·第二章`）认书，题名不含书名的再按别名表
（`鱼我所欲也` → 孟子）认书，认不出书名的按作者认书（左丘明 → 左传）。

重复判定用简繁归一、去标点后的正文做子串匹配，逐条试「全篇 → 前 N 字」。

用法：
  python3 scripts/reorg_xianqin.py            # dry-run，打印分派清单
  python3 scripts/reorg_xianqin.py --apply    # 落盘
  python3 scripts/reorg_xianqin.py --apply --report docs/先秦拆分.tsv
"""
import argparse
import json
import os
import re
import sys

from opencc import OpenCC

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
T2S = OpenCC('t2s')
SOURCE = '先秦/诗/poet.xianqin.json'
WEN_DIR = '先秦/文'

# 已有专书：书 → (文件, 说明)。正文以这些文件为准，poet.xianqin 里的重出一律删。
CANON = {
    # 书 → (正文文件, 正文文件对应的 先秦/文 落位名)
    '论语': ('先秦/论语/lunyu.json', 'lunyu'),
    '孟子': ('先秦/四书五经/mengzi.json', 'mengzi'),
    '中庸': ('先秦/四书五经/zhongyong.json', 'zhongyong'),
    '大学': ('先秦/四书五经/daxue.json', 'daxue'),
    '楚辞': ('先秦/楚辞/chuci.json', 'chuci'),
    '诗经': ('先秦/诗经/shijing.json', 'shijing'),
    '古文观止': ('汇编/古文观止/古文观止.json', 'guwenguanzhi'),
}

# 题名里不带书名、要另认的篇目 → 所属书
TITLE_ALIAS = {
    '鱼我所欲也': '孟子', '得道多助，失道寡助': '孟子', '生于忧患，死于安乐': '孟子',
    '逍遥游': '庄子', '北冥有鱼': '庄子', '庖丁解牛': '庄子', '惠子相梁': '庄子',
    '劝学': '荀子', '大略': '荀子',
    '《论语》十二章': '论语', '论语三则': '论语', '子路、曾晳、冉有、公西华侍坐': '论语',
    '大道之行也': '礼记',
    '郑伯克段于鄢': '左传', '齐桓下拜受胙': '左传', '石碏谏宠州吁': '左传',
    '臧僖伯谏观鱼': '左传', '子鱼论战': '左传', '寺人披见文公': '左传',
    '郑子家告赵宣子': '左传', '王孙满对楚子': '左传', '祁奚请免叔向': '左传',
    '季札观周乐': '左传', '子产却楚逆女以兵': '左传', '子革对灵王': '左传',
    '吴许越成': '左传', '齐国佐不辱命': '左传', '吕相绝秦': '左传',
    '驹支不屈于晋': '左传', '子产坏晋馆垣': '左传', '展喜犒师': '左传',
    '蹇叔哭师': '左传', '介之推不言禄': '左传', '宫之奇谏假道': '左传',
    '臧哀伯谏纳郜鼎': '左传', '郑庄公戒饬守臣': '左传', '齐桓公伐楚盟屈完': '左传',
    '对楚王问': '宋玉',
    '管子形势': '管子',
    '卜居': '楚辞',
    '国风·卫风·竹竿': '诗经', '大雅·烝民': '诗经',
    '离骚': '楚辞', '离骚（节选）': '楚辞',
}

# 认不出书名的，按作者归书
AUTHOR_BOOK = {
    '左丘明': '左传', '老子': '道德经', '庄子': '庄子', '孟子': '孟子', '孔子': '论语',
    '曾子': '大学', '子思': '中庸', '屈原': '楚辞', '荀子': '荀子',
    '墨子': '墨子', '孙武': '孙子兵法', '鬼谷子': '鬼谷子', '韩非': '韩非子',
    '商鞅': '商君书', '管仲': '管子', '吕不韦': '吕氏春秋', '公羊高': '公羊传',
    '穀梁子': '穀梁传', '释迦牟尼': '佛经',
    '宋玉': '宋玉', '荆轲': '荆轲', '李斯': '李斯', '尹文': '尹文',
    '商汤': '商汤', '周公旦': '周礼', '乐正克': '乐正克', '尹吉甫': '诗经',
}

# 题名里的书名 → 落位用的书；'诗经' 类作品留在 poet.xianqin（它们是诗）
BOOK_OF_PREFIX = {
    '楚辞': '楚辞', '国风': '诗经', '大雅': '诗经', '小雅': '诗经', '周颂': '诗经',
    '鲁颂': '诗经', '商颂': '诗经',
}

# 书 → 作者（move 出去时补 author 用）
BOOK_AUTHOR = {
    '论语': '孔子及其弟子', '孟子': '孟子', '大学': '曾子', '中庸': '子思',
    '老子': '老子', '庄子': '庄子', '荀子': '荀子', '墨子': '墨子',
    '孙子兵法': '孙武', '鬼谷子': '鬼谷子', '韩非子': '韩非', '商君书': '商鞅',
    '管子': '管子', '吕氏春秋': '吕不韦', '公羊传': '公羊高', '穀梁传': '穀梁子',
    '左传': '左丘明', '国语': '左丘明', '晏子春秋': '晏婴', '山海经': '无名氏',
    '黄帝内经': '无名氏', '今文尚书': '无名氏', '逸周书': '无名氏', '礼记': '无名氏',
    '周易': '无名氏', '三十六计': '无名氏', '佛经': '释迦牟尼',
    '道德经': '老子', '孝经': '孔子',
}

# 书名 → 落位文件名（先秦/文/<文件名>.json）
WEN_FILE = {
    '佛说四十二章经': 'sishierzhangjing', '圆觉经': 'yuanjuejing', '地藏经': 'dizangjing',
    '妙法莲华经': 'fahuajing', '维摩诘经': 'weimojiejing', '金刚经': 'jingangjing',
    '周礼': 'zhouli', '春秋穀梁传': 'chunqiuguliangzhuan',
    '公羊传': 'gongyangzhuan', '谷梁传': 'guliangzhuan',
    '论语': 'lunyu', '孟子': 'mengzi', '大学': 'daxue', '中庸': 'zhongyong',
    '老子': 'daodejing', '道德经': 'daodejing', '庄子': 'zhuangzi', '荀子': 'xunzi',
    '墨子': 'mozi', '孙子兵法': 'sunzibingfa', '鬼谷子': 'guiguzi',
    '韩非子': 'hanfeizi', '商君书': 'shangjunshu', '管子': 'guanzi',
    '吕氏春秋': 'lushichunqiu', '公羊传': 'gongyangzhuan', '穀梁传': 'guliangzhuan',
    '左传': 'zuozhuan', '国语': 'guoyu', '晏子春秋': 'yanzichunqiu',
    '山海经': 'shanhaijing', '黄帝内经': 'huangdineijing', '今文尚书': 'shangshu',
    '逸周书': 'yizhoushu', '礼记': 'liji', '周易': 'zhouyi', '三十六计': 'sanshiliuji',
    '佛经': 'fojing', '楚辞': 'chuci', '诗经': 'shijing',
    '宋玉': 'songyu', '李斯': 'qinwen', '荆轲': 'gushi', '尹文': 'yinwenzi',
    '商汤': 'shangtang', '周公旦': 'zhouli', '乐正克': 'yuezhengke',
}

PUNCT = re.compile(r'[“”「」『』"\'‘’（）()，。、；：！？,.;:!?□【】\[\]·—…《》〈〉\s]')


def norm(s):
    return PUNCT.sub('', T2S.convert(s or ''))


def body_of(rec):
    return norm(''.join(rec.get('paragraphs') or []))


def canon_texts():
    """书 → 正文（简繁归一、去标点），用于子串判重。"""
    out = {}
    for book, (path, _) in CANON.items():
        full = os.path.join(ROOT, path)
        if not os.path.exists(full):
            continue
        data = json.load(open(full, encoding='utf-8'))
        items = data if isinstance(data, list) else [data]
        chunks = []
        for it in items:
            for key in ('paragraphs', 'content'):
                v = it.get(key)
                if isinstance(v, list):
                    chunks.append(''.join(norm(x) for x in v))
                elif isinstance(v, str):
                    chunks.append(norm(v))
        out[book] = ''.join(chunks)
    return out


def book_of(rec):
    title = rec.get('title') or ''
    if title in TITLE_ALIAS:
        return TITLE_ALIAS[title]
    if '·' in title:
        head = title.split('·')[0]
        if head in BOOK_OF_PREFIX:
            return BOOK_OF_PREFIX[head]
        return head
    author = rec.get('author') or ''
    return AUTHOR_BOOK.get(author)


def covered(body, text):
    """body 是否已完整出现在 text 里；返回 (前多少字对上, 总长)。"""
    if not body or not text:
        return 0, len(body)
    if body in text:
        return len(body), len(body)
    lo, hi = 0, len(body)
    while lo < hi:                      # 二分找最长可对上前缀（子串匹配有单调性）
        mid = (lo + hi + 1) // 2
        if body[:mid] in text:
            lo = mid
        else:
            hi = mid - 1
    return lo, len(body)



POETIC = {'诗经', '楚辞'}          # 这两部留下的理由自己是诗/辞，落位各自专书


def book_of_target(book):
    """书 → 落位名。返回 None 表示留在 poet.xianqin（诗/辞或认不出书）。"""
    if not book:
        return None
    if book in POETIC:
        return None
    if book in CANON:
        return CANON[book][1] if book not in POETIC else None
    if book in BOOK_OF_PREFIX:
        return book_of_target(BOOK_OF_PREFIX[book])
    return book


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--apply', action='store_true')
    ap.add_argument('--report', default=None)
    ap.add_argument('--min-prefix', type=int, default=20,
                    help='前 N 字已在专书里即视为重出（默认 20）')
    args = ap.parse_args()

    src = json.load(open(os.path.join(ROOT, SOURCE), encoding='utf-8'))
    texts = canon_texts()
    kept, dropped, moved = [], [], {}
    rows = []

    for rec in src:
        body = body_of(rec)
        book = book_of(rec)
        hit_book, hit_len = None, 0
        for cb, text in texts.items():
            n, total = covered(body, text)
            if n > hit_len:
                hit_book, hit_len, hit_total = cb, n, total

        if hit_len and hit_len >= min(args.min_prefix, hit_total):
            dropped.append((rec, hit_book, hit_len))
            rows.append(('drop', rec.get('title'), hit_book, f'正文 {hit_len}/{hit_total} 字已在专书内'))
            continue

        key = book_of_target(book)
        if key is None:
            kept.append(rec)
            rows.append(('keep', rec.get('title'), book or '?', '诗/辞，留在 poet.xianqin'))
            continue

        moved.setdefault(key, []).append(rec)
        rows.append(('move', rec.get('title'), key, ''))

    print(f'总计 {len(src)} 条：drop {len(dropped)}，move {sum(len(v) for v in moved.values())}，keep {len(kept)}')
    for book, items in sorted(moved.items(), key=lambda kv: -len(kv[1])):
        print(f'  move {len(items):4d}  {book}')
    if args.report:
        with open(os.path.join(ROOT, args.report), 'w', encoding='utf-8') as fp:
            fp.write('action\ttitle\tbook\tnote\n')
            for r in rows:
                fp.write('\t'.join(str(x) for x in r) + '\n')
        print(f'  明细写入 {args.report}')
    if not args.apply:
        print('（dry-run，未改动任何文件；加 --apply 落盘）')
        return

    # 写 先秦/文/*.json
    os.makedirs(os.path.join(ROOT, WEN_DIR), exist_ok=True)
    for book, items in sorted(moved.items()):
        fname = WEN_FILE.get(book, book)
        author = BOOK_AUTHOR.get(book)
        out = []
        for rec in items:
            rec = dict(rec)
            title = rec.get('title') or ''
            if '·' in title and book not in ('lunyu', 'mengzi', 'zhongyong', 'daxue', 'chuci'):
                rec['title'] = title.split('·', 1)[1]   # `庄子·内篇·逍遥游` → `内篇·逍遥游`
            if author and book in BOOK_AUTHOR:
                rec['author'] = BOOK_AUTHOR[book]
            out.append(rec)
        out.sort(key=lambda r: (r.get('author') or '', r.get('title') or ''))
        path = os.path.join(ROOT, WEN_DIR, f'{fname}.json')
        with open(path, 'w', encoding='utf-8') as fp:
            json.dump(out, fp, ensure_ascii=False, indent=2)
            fp.write('\n')
        print(f'  写 {WEN_DIR}/{fname}.json  {len(out)} 条')

    kept.sort(key=lambda r: (r.get('author') or '', r.get('title') or ''))
    with open(os.path.join(ROOT, SOURCE), 'w', encoding='utf-8') as fp:
        json.dump(kept, fp, ensure_ascii=False, indent=2)
        fp.write('\n')
    print(f'  {SOURCE} 剩 {len(kept)} 条')


if __name__ == '__main__':
    main()
