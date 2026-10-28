#!/usr/bin/env python3
"""识典古籍抓下的章节 → chinese-poetry 记录。

  python3 convert.py <raw.json> <out.json> --book hongloumeng|xiyou|shuihu|sanguo

每本书三件事：
  1. 去页眉页脚：卷题行、评阅者行、卷末重复的卷题、评语段。
  2. 定题名：回次 + 回目；回目缺的从卷首目録补。
  3. 落 {author,title,paragraphs,id}，id 规则同 scripts/backfill_ids.py。
"""
import argparse, hashlib, json, re

ALPHABET = '0123456789abcdefghijklmnopqrstuvwxyz'
CN_NUM = {'〇': 0, '零': 0, '一': 1, '二': 2, '三': 3, '四': 4, '五': 5,
          '六': 6, '七': 7, '八': 8, '九': 9}


def base22(digest, n):
    v = int.from_bytes(digest, 'big')
    out = []
    for _ in range(n):
        v, r = divmod(v, 22)
        out.append(ALPHABET[r])
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


def cn2int(s):
    s = (s or '').strip()
    if not s:
        return None
    if s.isdigit():
        return int(s)
    total, cur = 0, 0
    for ch in s:
        if ch in CN_NUM:
            cur = CN_NUM[ch]
        elif ch == '十':
            total += (cur or 1) * 10
            cur = 0
        elif ch == '百':
            total += (cur or 1) * 100
            cur = 0
        else:
            return None
    return total + cur


def norm(s):
    return re.sub(r'\s+', '', s or '')


def looks_like_heading(line):
    """回目行：6~40 字、只有句末一个句号，开头不是「却説」「原来」这类叙事起句。"""
    t = norm(line).rstrip('。')
    if not (6 <= len(t) <= 40):
        return False
    if '。' in t:
        return False
    if re.match(r'^(却説|却说|原来|只見|只见|話説|话说|且説|且说|如今|那|這|这|原|當下|当下)', t):
        return False
    return True


# ---------------------------------------------------------------- 各书口径

class Book:
    author = ''
    round_rx = re.compile(r'^第([〇零一二三四五六七八九十百]+)回[，。、：:．]?\s*(.*)$')
    vol_rx = None

    def clean(self, paragraphs):
        out = []
        for p in paragraphs:
            t = (p or '').strip()
            n = norm(t)
            if self.round_rx and self.round_rx.match(n):
                out.append(t)
                continue
            if len(n) < 4:
                continue
            if self.vol_rx and self.vol_rx.match(n):
                continue
            out.append(t)
        return out

    def rounds(self, chapter, cleaned):
        """默认：正文里以回次行分回（《水滸傳》一卷一回，《三國》一卷两回）。"""
        out, cur = [], None
        for p in cleaned:
            m = self.round_rx.match(norm(p))
            if m:
                if cur:
                    out.append(cur)
                cur = [cn2int(m.group(1)), m.group(2).strip(), []]
                continue
            if cur is not None:
                cur[2].append(p)
        if cur:
            out.append(cur)
        return out


# 識典程甲本有 12 回没有小标题（底本缺），回目按通行本补
HLM_TOC_FALLBACK = {
    1: '甄士隱夢幻識通靈，賈雨村風塵懷閨秀', 5: '遊幻境指迷十二釵，飲仙醪曲演紅樓夢',
    27: '滴翠亭楊妃戲彩蜨，埋香塚飛燕泣殘紅', 30: '寳釵借扇機帶雙敲，椿齡畫薔癡及局外',
    32: '訴肺腑心迷活寳玉，含耻辱情烈死金釧', 33: '手足眈眈小動唇舌，不肖種種大承笞撻',
    69: '弄小巧用借劍殺人，覺大限吞生金自逝', 72: '王熙鳳恃强羞説病，來旺婦倚勢霸成親',
    74: '惑姦讒抄揀大觀園，矢孤介杜絶寧國府', 81: '占旺相四美釣游魚，奉嚴詞兩番入家塾',
    95: '因訛成實元妃薨逝，以假混真寳玉瘋癲', 115: '惑偏私惜春矢素志，證同類寳玉失相知',
}


class Hongloumeng(Book):
    """庚辰本／程甲本：回次在页面标题里，回目是正文首行，正文中没有回次行。"""
    author = '曹雪芹'
    round_rx = None
    name_rx = re.compile(r'第([〇零一二三四五六七八九十百]+)回')
    vol_rx = re.compile(r'^紅樓夢[第一]?[〇零一二三四五六七八九十百]*回?$')

    def clean(self, paragraphs):
        return [t for t in (p.strip() for p in paragraphs) if norm(t) and norm(t) != '紅樓夢']

    def rounds(self, chapter, cleaned):
        m = self.name_rx.search(norm(chapter['name']))
        if not m:
            return []
        num = cn2int(m.group(1))
        body = list(cleaned)
        head = (chapter.get('subtitle') or '').strip(' 。')
        if not head and body and looks_like_heading(body[0]):
            head, body = body[0].strip(' 。'), body[1:]
        elif head and body and norm(body[0])[:12] == norm(head)[:12]:
            body = body[1:]                  # 回目同时出现在正文首段
        if not head:
            head = HLM_TOC_FALLBACK.get(num, '')
        return [[num, head, body]]



class Xiyou(Book):
    author = '吴承恩'
    name_rx = re.compile(r'第([〇零一二三四五六七八九十百]+)回')
    note_flag = re.compile(r'^總批')

    def clean(self, paragraphs):
        out = []
        for p in paragraphs:
            t = (p or '').strip()
            n = norm(t)
            if self.note_flag.match(n):
                break                      # 總批及其后全是评语
            k = t.find('總批：')             # 有時評語並進了末段
            if k > 0:
                t = t[:k].rstrip()
                out.append(t)
                break
            if len(n) < 4 or n == '西遊記':
                continue
            out.append(t)
        return out

    def rounds(self, chapter, cleaned):
        m = self.name_rx.search(norm(chapter['name']))
        if not m:
            return []
        body = list(cleaned)
        head = (chapter.get('subtitle') or '').strip(' ，。')
        if not head and body and looks_like_heading(body[0]):
            head, body = body[0].strip(' ，。'), body[1:]
        elif head and body and norm(body[0])[:12] == norm(head)[:12]:
            body = body[1:]
        return [[cn2int(m.group(1)), head, body]]


class Shuihu(Book):
    """容與堂本（識典 NGJ...1879587548）：一卷一回，卷首页是「第X回」「回目」。

    底本 OCR 有回次认错（第二十三回标成「第十三回」）与漏行的页，所以回次以卷序为准：
    卷 N 就是第 N 回，页内回次行只在没有卷号时兜底。
    """
    author = '施耐庵'
    vol_rx = re.compile(r'^[忠義水滸傳]*卷第?[〇零一二三四五六七八九十百]+[，。]?$')
    vol_num_rx = re.compile(r'卷[之第]?([〇零一二三四五六七八九十百]+)')

    def rounds(self, chapter, cleaned):
        name = norm(chapter['name'])
        # 卷首三页（李卓吾评、目録、引首）不是正文回次
        if re.search(r'(評$|目[録錄]|引首)', name[:12]):
            return []
        # 卷题 OCR 不可靠（「卷之四卜四」「卷之六十十」），页内回次行也常错位；
        # 但全书是「一卷一回、卷序即回次」，所以回次一律留空，由 convert() 按顺序编号。
        out = super().rounds(chapter, cleaned)
        if not out:
            # 回次行被 OCR 弄糊了（「弟三十七回」「第四十才回」）：整页作一回，回次留空按序编号，
            # 回目取正文里第一个像回目的短行
            body = list(cleaned)
            while body and (self.vol_rx.match(norm(body[0]))
                            or re.fullmatch(r'[李林施]?[耐一]?菴?集?撰?[，。]?', norm(body[0]))
                            or re.fullmatch(r'貫中[綦纂]修?[。，]?', norm(body[0]))):
                body = body[1:]
            head = ''
            if body and looks_like_heading(body[0]):
                head, body = body[0].strip(' ，。'), body[1:]
            out = [[None, head, body]]
        for r in out:
            r[0] = None
            if not r[1] and r[2] and looks_like_heading(r[2][0]):
                r[1] = r[2][0].strip(' ，。')
                r[2] = r[2][1:]
        return out

    # 回目被底本 OCR 弄糊、正文首行也取不到的两回，按容與堂本回目补
    HEAD_FALLBACK = {
        4: '趙員外重修文殊院，魯智深大鬧五臺山',
        59: '吳用賺金鈴吊挂，宋江鬧西嶽華山',
        95: '張順魂捉方天定，宋江智取寧海軍',
        100: '宋公明神聚蓼兒洼，徽宗帝夢游梁山',
    }

    def clean(self, paragraphs):
        out = []
        for p in paragraphs:
            t = (p or '').strip()
            n = norm(t)
            if self.round_rx and self.round_rx.match(n):
                out.append(t)                                        # 回次行必须留
                continue
            if len(n) < 4 or self.vol_rx.match(n):
                continue
            if re.fullmatch(r'[李林]卓吾[評评][閲阅][纂修]*[：:，。]?', n):
                continue
            if re.fullmatch(r'[菴庵]集撰[，。]?', n) or re.fullmatch(r'羅貫中纂[脩修][。，]?', n):
                continue
            out.append(t)
        return out



class Sanguo(Book):
    """《三國志通俗演義》嘉靖本：一页一回，回目在页面小标题（H3）里，正文不带回次。"""
    author = '罗贯中'
    round_rx = None
    vol_rx = re.compile(r'^三國志通俗演義卷第?[〇零一二三四五六七八九十百]+[，。]?$')
    section_rx = re.compile(r'^三國志通俗演義卷之?[〇零一二三四五六七八九十百]+[，。]?$')

    def rounds(self, chapter, cleaned):
        name = norm(chapter['name'])
        sub = (chapter.get('subtitle') or '').strip()
        # 卷题页只列本卷目次；序、宗僚页没有回目 —— 都不收
        if self.section_rx.match(name) or not sub or re.search(r'目[録錄]', sub):
            return []
        return [[None, sub, list(cleaned)]]


BOOKS = {'hongloumeng': Hongloumeng, 'xiyou': Xiyou, 'shuihu': Shuihu, 'sanguo': Sanguo}


# ---------------------------------------------------------------- 目录

def read_catalog(raw):
    """卷首「目録」页 → {回次: 回目}。模式是「第N回」「回目」两段一行一组。"""
    cat = {}
    for v in raw.values():
        ps = v['paragraphs']
        head = norm(v.get('name') or '') + norm((v.get('paragraphs') or [''])[0])[:20]
        if not re.search(r'目[録錄]', head):
            continue
        i = 0
        while i < len(ps) - 1:
            m = re.match(r'^第([〇零一二三四五六七八九十百]+)回[，。]?$', norm(ps[i]))
            if m:
                nxt = norm(ps[i + 1])
                if not re.match(r'^第[〇零一二三四五六七八九十百]+回', nxt):
                    cat.setdefault(cn2int(m.group(1)), ps[i + 1].strip(' ，。'))
                    i += 2
                    continue
            i += 1
    return cat


# ---------------------------------------------------------------- 主流程

def convert(raw, book, catalog):
    taken, records = set(), []
    auto = 0
    for v in sorted(raw.values(), key=lambda x: x['index']):
        cleaned = book.clean(v['paragraphs'])
        if not cleaned:
            continue
        for num, head, body in book.rounds(v, cleaned):
            if num is None:            # 正文不带回次的版本（《三國》嘉靖本）：按出现次序编号
                auto += 1
                num = auto
            else:
                auto = num
            head = (head or '').strip(' ，。、：:')
            if len(norm(head)) < 6:
                head = catalog.get(num, head)
            if not head:
                head = (getattr(book, 'HEAD_FALLBACK', None) or {}).get(num, '')
            title = f'第{num}回' + (f'　{head}' if head else '')
            body = [b for b in body if len(norm(b)) >= 4]
            if not body:
                continue
            records.append({'author': book.author, 'title': title, 'paragraphs': body})
    for r in records:
        r['id'] = make_id(r['author'], r['title'], r['paragraphs'], taken)
    return records


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('raw')
    ap.add_argument('out')
    ap.add_argument('--book', required=True, choices=sorted(BOOKS))
    a = ap.parse_args()

    raw = json.load(open(a.raw, encoding='utf-8'))
    book = BOOKS[a.book]()
    catalog = read_catalog(raw)
    print(f'目録补到 {len(catalog)} 条回目；抓到 {len(raw)} 章')
    records = convert(raw, book, catalog)
    with open(a.out, 'w', encoding='utf-8') as fp:
        json.dump(records, fp, ensure_ascii=False, indent=2)
        fp.write('\n')
    chars = sum(len(''.join(r['paragraphs'])) for r in records)
    print(f'{len(records)} 回，{chars} 字 → {a.out}')
    for r in records[:3] + records[-2:]:
        print('  ', r['title'][:34], len(r['paragraphs']), '段')


if __name__ == '__main__':
    main()
