#!/usr/bin/env python3
"""识典古籍整本抓下的章节（book_text.mjs 产出）→ chinese-poetry 记录。

  python3 convert_classic.py <raw.json> <out.json> --book rulin|jinghuayuan|...

每部书三件事：去页眉页脚与评语、定题名（回/卷次 + 篇名）、落 {author,title,paragraphs,id}。
id 规则同 scripts/backfill_ids.py。

卷首页（序、目録、凡例）默认不入库：它们是这部书的附件，不是正文，逐部书在 NOTES 里有一句话说明。
"""
import argparse, json, re
from convert import make_id, norm, cn2int

CN = '〇零一二三四五六七八九十百'
NUM_CHARS = set(CN)


def int2cn(n):
    """1..999 转汉数字，与底本的「卷二十第一百回」同形。"""
    d = '〇一二三四五六七八九'
    if n < 10:
        return d[n]
    if n < 20:
        return '十' + (d[n % 10] if n % 10 else '')
    if n < 100:
        return d[n // 10] + '十' + (d[n % 10] if n % 10 else '')
    return d[n // 100] + '百' + (int2cn(n % 100) if n % 100 else '')
UNIT_RX = re.compile(r'第([%s]+)(回|卷|則|章)' % CN)
LOCATOR_RX = re.compile(r'^[^\s]{0,8}第[%s]+[回卷]$' % CN)
HEAD_RX = re.compile(r'^[^\s]{0,10}第[%s]+[回卷]' % CN)


NUM_MAP = {'”': '二', '“': '二', '〃': '二', '，': '一', '．': '一', '＝': '二', '一': '一'}


def cn_unit_num(name):
    """从章节名里取回/卷次：「第一卷」「卷三」「第二卷莊子休鼓盆成大道」都认。"""
    name = repair_num(name)
    for rx, kw in ((r'第([%s]+)回' % CN, '回'), (r'第([%s]+)卷' % CN, '卷'),
                   (r'卷之([%s]+)' % CN, '卷'), (r'^[^\s]{0,8}卷([%s]+)' % CN, '卷')):
        m = re.search(rx, name)
        if m:
            n = cn2int(m.group(1))
            if n:
                return n, kw
    return None, ''


def repair_num(name):
    """底本 OCR 把汉数字认成标点（「搜神記卷”六」）：只修紧跟着「卷/第」的那一个字。"""
    return re.sub(r'(卷[之第]?|第)([%s])' % ''.join(NUM_MAP), lambda m: m.group(1) + NUM_MAP[m.group(2)], name)


def strip_locator(text):
    """「鏡花緣卷一第二回」「儒林外史第二回」这类版心/回次行：摘掉前面那截书名与卷次。"""
    m = re.match(r'^(.{0,10})?(第[%s]+(?:回|卷)[，。、：:．]?\s*)(.*)$' % CN, text.strip())
    if not m:
        return None
    return m.group(2).strip('，。、：:． '), m.group(3).strip()


class Book:
    author = ''
    # 卷首页的题名特征；匹配到的页整页丢弃
    skip_rx = re.compile(r'(序|敘|叙|引|目[録錄]|凡例|總跋|跋|題詞|例言|緣起)[，。：:]?$')
    round_rx = re.compile(r'第([%s]+)回' % CN)
    # 有些书章节名只写「搜神記卷一」，回次用卷次
    vol_as_unit = False
    vol_rx = re.compile(r'卷[之第]?([%s]+)' % CN)
    # 折行页（底本按定长折断、回次错乱）的字数上限；正常整页远远超过它
    fold_limit = 1200

    def head_of(self, chapter, cleaned, num):
        """回目：先看章节名里的后半截，再看首段。"""
        name = norm(chapter['name'])
        m = self.round_rx.search(name)
        if m:
            tail = name[m.end():].strip('，。、：:．・ ')
            if 4 <= len(tail) <= 40:
                return tail
        if cleaned:
            first = norm(cleaned[0])
            if 4 <= len(first) <= 40 and not re.search(r'[。；：？！]$', first):
                return cleaned[0].strip(' ，。、：:')
        return ''

    def is_title_line(self, text, head):
        t0 = norm(text)
        # 版心行「容齋五筆卷第九」这类只有书卷次、没有篇名的，不算篇名
        if re.fullmatch(r'[^\s]{0,8}卷[之第]?[%s]+' % CN, t0):
            return False
        if not head:
            return False
        t = norm(text).strip('，。、：: ')
        h = norm(head).strip('，。、：: ')
        return t == h or (t.endswith(h) and len(t) - len(h) <= 12) or HEAD_RX.match(t) is not None

    def clean(self, chapter, num):
        paras = chapter['paragraphs']
        # 折行页：底本 OCR 把整页按定长折断，只能标出来、不硬劈
        folded = sum(len(p) for p in paras) > self.fold_limit and (
            sum(1 for p in paras if len(norm(p)) <= 30) / max(len(paras), 1) > 0.8)
        if folded:
            return [], True
        return [p.strip() for p in paras if p.strip()], False


class Rulin(Book):
    """《儒林外史》卧閑草堂刻本（精校）：一卷一回。

    正文首段之前没有回目行——回目只在章节名「儒林外史第X回」和卷首目録里，
    所以回目一律从目録补（读不到目録时退回章节名的后半截）。
    """
    author = '吴敬梓'

    def head_of(self, chapter, cleaned, num):
        return ''

    def clean(self, chapter, num):
        if self.skip_rx.search(norm(chapter['name'])):
            return [], False
        return [p.strip() for p in chapter['paragraphs'] if p.strip()], False


class Jinghuayuan(Book):
    """《鏡花緣》道光十二年刻本：回次在「卷一第X回」这类版心行里，回目紧随其后。"""
    author = '李汝珍'

    def head_of(self, chapter, cleaned, num):
        """回目紧跟在版心行「鏡花緣卷第X回」之后，中间常还压着一段夹批。

        版心行本身会被 OCR 折成「鏡花緣卷」「一第四回吟雪詩，暖閣賭酒」「；揮醉筆上苑催花」，
        也会被夹批顶成「菊如鏡花緣卷一第三回徐英公傳檄起義兵」。所以锚点只有一处：正文起句之前那句。
        """
        # 版心行摘出来的回目优先：就在本页报的「第X回」旁边，比猜更可靠
        for p in cleaned[:6]:
            if p.startswith('\x00'):
                cand = p[1:].strip('。 ')
                if not re.search(r'菊如$|蔬菴$|蔬庵$', cand):
                    return cand
        want = f'第{int2cn(num)}回'
        texts = [norm(p) for p in cleaned[:6] if not p.startswith('\x00')]
        for k, t in enumerate(texts):
            if want not in t:
                continue
            # 版心行之后的残句；若版心行本身被折断，接上下两段
            chunk = ' '.join(texts[k:k + 3])
            tail = chunk.split(want)[-1]
            # 回目到句号为止：版心行之后的残句或下一段的首句
            tail = tail.split('。')[0]
            tail = re.split(r'^(?:[^，。；]{0,10}(?:[蔬菴]{2}|菊如))', tail)[-1]
            tail = re.sub(r'^[，。、：:； ]+', '', tail)
            tail = tail.strip('，。、：:； ')
            if 6 <= len(tail) <= 42:
                return tail
        return ''

    def clean(self, chapter, num):
        if self.skip_rx.search(norm(chapter['name'])):
            return [], False
        want = f'第{int2cn(num)}回'
        want_cn = int2cn(num)
        # 页首就带着别回版心行的（「卷二第七回」页首压着「鏡花緣卷二第六回」）：那是上一页的版心行
        paras = []
        for p in chapter['paragraphs']:
            p = (p or '').strip()
            if not p:
                continue
            t = norm(p)
            # 这一页里冒出别的回次（「鏡花緣卷三第十一回」出现在第八回页首）：那是上一页的版心行，
            # 只有行首就是版心才算，正文里提到「第三回」的评语不能误删。
            m = re.match(r'^[^\s，。]{0,8}卷[%s]*第([%s]+)回' % (CN, CN), t)
            if m and m.group(1) != want_cn and any(want in norm(x) for x in chapter['paragraphs']):
                p = t[m.end():].strip('，。、：:； ')
            if p:
                paras.append(p)
        # 页首没有版心行时（「鏡花緣卷二」那页），首段可能只是正文的首句：
        # 认作回目的条件是首段本身就没有叙事起句，且下一段才是「話説…」
        if paras and not any(re.search(r'第[%s]+回' % CN, norm(x)) for x in paras[:1]):
            first = norm(paras[0]).rstrip('。')
            nxt = norm(paras[1])[:24] if len(paras) > 1 else ''
            # 回目后面紧跟的就是正文；紧跟另一句夹批（「…菊如」）时不能算
            if (6 <= len(first) <= 30 and not re.match(r'^(話説|話說|却説|且説|原來|原來如此)', first)
                    and not re.search(r'菊如|蔬菴|蔬庵|此批|評曰', first + nxt[:8])):
                paras[0] = '\x00' + first
        # 版心行被 OCR 折成「鏡花緣卷」「一第四回吟雪詩，暖閣賭酒」「；揮醉筆上苑催花」：
        # 不拼回去，回目就落在夹批后面，判不出来。只拼紧挨着的下两段，且下一段以数字或标点起首。
        merged = []
        for p in paras:
            if merged and len(norm(merged[-1])) <= 10 and re.match(r'^[%s、；]' % CN, norm(p)):
                merged[-1] += p
                continue
            merged.append(p)
        out = []
        for p in merged:
            if not p:
                continue
            got = strip_locator(p)
            if got and re.match(r'第[%s]+回' % CN, got[0]):
                head = got[1].strip('。 ')
                if head:
                    out.append('\x00' + head)   # 版心行摘出的回目另存标记行，避免与正文混淆
                continue
            out.append(p)
        return out, False


class Soushenji(Book):
    """《搜神記》汲古閣本：一卷一条，卷内逐条志怪。"""
    vol_as_unit = True
    author = '干宝'
    round_rx = None

    def clean(self, chapter, num):
        if self.skip_rx.search(norm(chapter['name'])):
            return [], False
        out = [p.strip() for p in chapter['paragraphs'] if p.strip()]
        if out and re.fullmatch(r'晉[干于]寶撰(\s*明胡震亨毛晉同訂)?', norm(out[0])):
            out = out[1:]
        return out, False

    def head_of(self, chapter, cleaned, num):
        return ''


class Yuewei(Book):
    """《閲微草堂筆記》盛氏望益書屋刻本：五书二十四卷，卷内逐条志怪。"""
    vol_as_unit = True
    author = '纪昀'
    round_rx = None
    SERIES = {
        1: '灤陽消夏錄一', 2: '灤陽消夏錄二', 3: '灤陽消夏錄三', 4: '灤陽消夏錄四',
        5: '灤陽消夏錄五', 6: '灤陽消夏錄六', 7: '如是我聞一', 8: '如是我聞二',
        9: '如是我聞三', 10: '如是我聞四', 11: '槐西雜志一', 12: '槐西雜志二',
        13: '槐西雜志三', 14: '槐西雜志四', 15: '姑妄聽之一', 16: '姑妄聽之二',
        17: '姑妄聽之三', 18: '姑妄聽之四', 19: '灤陽續錄一', 20: '灤陽續錄二',
        21: '灤陽續錄三', 22: '灤陽續錄四', 23: '灤陽續錄五', 24: '灤陽續錄六',
    }

    def clean(self, chapter, num):
        if self.skip_rx.search(norm(chapter['name'])):
            return [], False
        out = [p.strip() for p in chapter['paragraphs'] if p.strip()]
        out = [p for p in out if not re.fullmatch(r'觀弈道人撰', norm(p))]
        series = self.SERIES.get(num, '')
        while out and series and norm(out[0])[:len(series)] == norm(series) and len(norm(out[0])) <= len(series) + 3:
            out = out[1:]
        return out, False

    def head_of(self, chapter, cleaned, num):
        return ''


class Yanshi(Book):
    """《喻世明言》明刊本：一卷一篇（有些卷含两篇），篇名在卷次行之后、正文之前。"""
    vol_as_unit = True
    author = '冯梦龙'

    def clean(self, chapter, num):
        name = norm(chapter['name'])
        if self.skip_rx.search(name) or name.endswith('序'):
            return [], False
        out = []
        for p in (p.strip() for p in chapter['paragraphs']):
            if not p:
                continue
            t = norm(p)
            m = re.match(r'^第[%s]+[卷回](.*)$' % CN, t)
            if m:
                rest = m.group(1).strip('．.、：: ，')
                if rest:
                    out.append('\x00' + rest)    # 版心行带着篇名
                continue
            out.append(p)
        return out, False

    def head_of(self, chapter, cleaned, num):
        for p in cleaned[:4]:
            if p.startswith('\x00'):
                return p[1:]
            t = norm(p).strip('．.、：: ，')
            if 3 <= len(t) <= 24 and not re.search(r'[。；，？]$', t):
                return t
        return ''


class Huaben(Book):
    """三言二拍：一卷（回）一篇话本。

    底本有两个麻烦：一是按定长折行（一行一段），二是卷末重复卷次、有时还重复篇名。
    所以正文=卷次行之后到卷末题名行之前，篇名=卷次行之后那一小截。
    """
    vol_as_unit = True
    author = ''

    def clean(self, chapter, num):
        if self.skip_rx.search(norm(chapter['name'])):
            return [], False
        return [p.strip() for p in chapter['paragraphs'] if p.strip()], False

    def _locator_rx(self, num):
        return re.compile(r'^[^\s]{0,6}第?[%s]*[%s][卷回]' % (CN, CN))

    def head_of(self, chapter, cleaned, num):
        want = re.compile(r'^第?[%s]*[%s][卷回](.*)$' % (CN, CN))
        for k, p in enumerate(cleaned[:4]):
            t = norm(p)
            m = want.match(t)
            if not m:
                continue
            rest = m.group(1).strip('．.、：:，。 ')
            if rest:
                # 篇名与首句并在一段：到冒号／句号为止；都判不出来就整截留给 FALLBACK
                cut = re.split(r'[：:。]', rest)[0]
                return cut.strip('，。、：:； ')[:40]
            for nxt in cleaned[k + 1:k + 2]:
                cand = norm(nxt).strip('．.、：:，。 ')
                if 4 <= len(cand) <= 40 and not re.search(r'[。；]$', cand):
                    return cand
            break
        return ''

    def body_start(self, cleaned, head):
        """正文起点。

        底本按定长折行，篇名与首句常在同一段，而目录给的篇名可能只有上半句，
        所以切法只有一条：本段里「卷次 + 篇名」之后那截留着，其余整段照录。
        """
        out = []
        for p in cleaned:
            t = norm(p)
            if not out:
                m = re.search(r'[卷][之第]?[%s]+' % CN, t)
                cut = m.end() if m else 0
                if head and head in t[cut:]:
                    cut = t.index(head, cut) + len(head)
                    # 双句篇名目录只给了上半句：把紧跟的下半句也切掉（到第一个冒号/句号为止）
                    m2 = re.match(r'[^：:。，；]{0,20}[：:。]', t[cut:])
                    if m2 and not re.match(r'^[。，；]', t[cut:]):
                        cut += m2.end()
                rest = t[cut:].lstrip('：:，。、 ') if cut else t
                if rest and rest != t:
                    out.append(rest)
                    continue
                if cut and not rest:
                    continue
                if not cut:
                    out.append(p)
                    continue
            out.append(p)
        while out and (re.fullmatch(r'[^\s]{0,10}第?[%s]*[%s][卷回]' % (CN, CN), norm(out[-1]))
                       or norm(out[-1]) == head):
            out.pop()
        return out


class Fengshen(Book):
    """《封神演義》康熙四雪草堂刻後印本：回目在章节名里（「第X回 紂王女媧宫進香」）。"""
    author = '许仲琳'

    def clean(self, chapter, num):
        if self.skip_rx.search(norm(chapter['name'])) or re.search(r'序|目[録錄]', norm(chapter['name'])):
            return [], False
        out = []
        for p in (p.strip() for p in chapter['paragraphs']):
            if not p:
                continue
            t = norm(p)
            if re.fullmatch(r'新刻[鐘锺][伯]敬先生批評封神演義[卷第]?[%s]*' % CN, t):
                continue
            out.append(p)
        return out, False


class Dongzhou(Book):
    """《東周列國全志》蔡元放評本：一卷两回，底本按定长折行，「第X回」与回目散在行内，回末附评语。

    回目常被折成两三行（「第一回」「周宣王聞謡輕殺」「杜大夫化厲鳴冤」），
    正文是长折行，所以判据是行短、且下一行也是短行。
    """
    vol_as_unit = True
    author = '蔡元放'
    round_rx = None
    SCAN = 1200

    def clean(self, chapter, num):
        name = norm(chapter['name'])
        if re.search(r'卷首|目[録錄]', name):
            return [], False
        return [p.strip() for p in chapter['paragraphs'] if p.strip()], False

    def rounds(self, chapter, num):
        """一卷不止一回：按「第X回」切段。"""
        cleaned, _ = self.clean(chapter, num)
        out, cur = [], None
        for p in cleaned:
            t = norm(p)
            m = re.match(r'^第([%s]+)回(?![%s])' % (CN, CN), t)
            if m:
                if cur:
                    out.append(cur)
                cur = [cn2int(m.group(1)), [], []]
                rest = t[m.end():].strip('，。、：:； ')
                if rest:
                    cur[1].append(rest)
                continue
            if cur is not None:
                cur[2].append(p)
        if cur:
            out.append(cur)
        # 回目被折成两三行短句（「周宣王聞謡輕殺」「杜大夫化厲鳴冤」）：取正文前的短行。
        # 正文折行也常在 12 字以内，所以加一条：拼起来要像回目（7~32 字、不含句读），否则不拼。
        for r in out:
            head_parts, body = r[1], r[2]
            while body and len(norm(body[0])) <= 12 and len(head_parts) < 3:
                cand = norm(body[0]).strip('，。、：:； ')
                if not re.fullmatch(r'[^，。；：？！]{2,12}', cand):
                    break
                trial = ''.join(head_parts + [cand])
                if len(trial) > 32:
                    break
                head_parts.append(cand)
                body.pop(0)
            r[1] = ''.join(head_parts)
        return out


class Yuchu(Book):
    """《虞初新志》康熙刻本：一卷数篇，卷内是篇名 + 正文 + 「張山來曰」评语。

    底本把作者小传、篇名、评语都压在段落里，没有可靠的版面标记；这一轮只按卷收录，
    逐篇切分留给对勘（见 docs/名著增补.md）。
    """
    vol_as_unit = True
    author = '张潮'
    round_rx = None
    # 卷次行被 OCR 认丢时（「會仙記」页其实属卷之十四），卷序只能按目录序推
    ORDER_ONLY = {'會仙記': 14}

    def clean(self, chapter, num):
        if self.skip_rx.search(norm(chapter['name'])):
            return [], False
        out = []
        for p in (p.strip() for p in chapter['paragraphs']):
            if not p or re.fullmatch(r'新安張潮山來氏輯', norm(p)):
                continue
            out.append(p)
        return out, False

    def head_of(self, chapter, cleaned, num):
        return ''


class Rongzhai(Book):
    """《容齋隨筆》明抄本：五集七十四卷，卷内逐条札记，条目名落在段首。"""
    vol_as_unit = True
    author = '洪迈'
    round_rx = None
    # 明抄本的章节名只写「一」「二」…，同一集内卷次重起；集名（容齋隨筆／續筆…）
    # 要么在章节名里（「容齋五筆卷三」），要么只出现在正文首行。按集分段、段内计卷。
    ORDER_ONLY = 'seq'
    SERIES_RX = re.compile(r'容齋([隨随續续三四五])[筆笔]')
    ORDER = {'隨': 1, '续': 2, '三': 3, '四': 4, '五': 5}

    def seq_num(self, v, seen):
        name = norm(v['name'])
        first = norm((v.get('paragraphs') or [''])[0])[:20]
        head = name + first
        m = self.SERIES_RX.search(head)
        series = self.ORDER.get(m.group(1), 1) if m else 1
        if not re.fullmatch(r'[%s]+' % CN, name):
            return None               # 卷首、目録、五筆的集首页都不是正文
        seen[series] = seen.get(series, 0) + 1
        return (series - 1) * 16 + seen[series]

    def clean(self, chapter, num):
        if self.skip_rx.search(norm(chapter['name'])):
            return [], False
        out = []
        for p in (p.strip() for p in chapter['paragraphs']):
            if not p:
                continue
            if re.fullmatch(r'容齋[隨随續续三四五][筆笔]?卷?[%s]*' % CN, norm(p)):
                continue          # 版心行「容齋隨筆卷第一」
            out.append(p)
        return out, False

    def head_of(self, chapter, cleaned, num):
        return ''


class Xiaochuang(Book):
    """《小窗幽記》（醉古堂劍掃）日本江户写本：原作十二卷，底本目录残缺，只能整书成条。"""
    vol_as_unit = True
    author = '陆绍珩'
    round_rx = None
    ORDER_ONLY = {1: 1, 2: 1, 3: 1, 4: 2, 5: 3, 6: 4, 7: 5, 8: 6, 9: 7, 10: 8, 11: 9}

    def clean(self, chapter, num):
        name = norm(chapter['name'])
        if re.search(r'自叙|序|採用書目|采用书目', name):
            return [], False
        out = []
        for p in (p.strip() for p in chapter['paragraphs']):
            if not p:
                continue
            t = norm(p)
            if re.fullmatch(r'醉[古台]?堂劍掃', t) or re.match(r'^松陵[陸陆障]紹珩', t):
                continue
            out.append(p)
        return out, False

    def head_of(self, chapter, cleaned, num):
        return ''


BOOKS = {'rulin': Rulin, 'jinghuayuan': Jinghuayuan, 'soushenji': Soushenji,
         'yuewei': Yuewei, 'yanshi': Yanshi, 'fengshen': Fengshen, 'rongzhai': Rongzhai,
         'jingshi': Huaben, 'paiang': Huaben, 'yuchu': Yuchu, 'dongzhou': Dongzhou,
         'xiaochuang': Xiaochuang}


def read_catalog(raw):
    """卷首「目錄」页 → {卷/回次: 篇名}。目录页多是「第X卷，篇名；卷十一、篇名」连排。"""
    cat = {}
    for v in raw.values():
        paras = v.get('paragraphs') or []
        name = norm(v.get('name') or '')
        head = name + (norm(paras[0])[:24] if paras else '')
        if not re.search(r'目[録錄]|目次', head) or head.count('目') > 2:
            continue
        for p in paras:
            t = norm(p)
            # 「卷之一，篇名」「卷十一、篇名」「卷三十七叠居奇…」三种写法都见
            for m in re.finditer(r'卷[之第]?([%s]+)[，、。：:．；;]?\s*([^卷]{2,40})' % CN, t):
                n = cn2int(m.group(1))
                if not n:
                    continue
                name = re.split(r'[；;。，、]', m.group(2))[0].strip('，、。：:；; ')
                if 2 <= len(name) <= 30:
                    cat.setdefault(n, name)
            for m in re.finditer(r'第([%s]+)卷[，、。：:．；;]?\s*([^卷第]{2,40})' % CN, t):
                n = cn2int(m.group(1))
                if not n:
                    continue
                name = re.split(r'[；;。，、]', m.group(2))[0].strip('，、。：:；; ')
                if 2 <= len(name) <= 30:
                    cat.setdefault(n, name)
            # 「第一回篇名。第二回篇名。」连排、回次之间不用标点的排法（鏡花緣卷首目録）
            for m in re.finditer(r'第([%s]+)回。?([^第]{4,80})' % CN, t):
                n = cn2int(m.group(1))
                if not n:
                    continue
                name = re.split(r'[；;。]', m.group(2))[0].strip('，、。：:；; ')
                if 4 <= len(name) <= 40:
                    cat.setdefault(n, name)
        # 一回一行、回次与回目分两段的排法（儒林外史卷首目録：「第一回」「説楔子敷陳大義，借名流隱括全文。」）
        for i, p in enumerate(paras[:-1]):
            m = re.fullmatch(r'第([%s]+)回' % CN, norm(p))
            if not m:
                continue
            nxt = norm(paras[i + 1]).strip('。； ')
            if 4 <= len(nxt) <= 30 and not re.match(r'^第[%s]+回' % CN, nxt):
                cat.setdefault(cn2int(m.group(1)), nxt)
    return cat


def convert(raw, book, cat=None):
    cat = cat or {}
    taken, records, folded = set(), [], []
    seen = {}
    auto = 0
    for v in sorted(raw.values(), key=lambda x: x['index']):
        num, unit_used = cn_unit_num(norm(v['name']))
        oo = getattr(book, 'ORDER_ONLY', None)
        if num is None and isinstance(oo, dict):
            num = oo.get(v['index'])
        if num is None and getattr(book, 'SCAN', None):
            for p in (v.get('paragraphs') or [])[:book.SCAN]:
                m = re.match(r'^第([%s]+)回(?![%s])' % (CN, CN), norm(p))
                if m:
                    num, unit_used = cn2int(m.group(1)), '回'
                    break
        if (unit_used == '卷' and getattr(book, 'round_rx', None)
                and not getattr(book, 'vol_as_unit', False)):
            # 章节名只报卷次（「鏡花緣卷二」），这一页里另有版心行报着回次，用它
            for p in (v.get('paragraphs') or [])[:3]:
                m = re.search(r'第([%s]+)回' % CN, norm(p))
                if m and cn2int(m.group(1)):
                    num, unit_used = cn2int(m.group(1)), '回'
                    break
            else:
                # 本页没有版心行，是上一回的下半页：接在上一页后面，回目也不再另起
                num = auto
                book.cont_page = True
        if getattr(book, 'ORDER_ONLY', None) == 'seq':
            num = book.seq_num(v, seen)
        if num is None:
            folded.append({'name': v['name'], 'reason': '章节名取不到回/卷次'})
            continue
        if hasattr(book, 'rounds'):
            chunks = book.rounds(v, num) or []
        else:
            cleaned, is_folded = book.clean(v, num)
            if is_folded:
                folded.append({'name': v['name'], 'reason': '折行页：底本按定长折断，回次错乱'})
                continue
            if not cleaned:
                continue
            # 章节名只报卷次时（「鏡花緣卷二」），回次与回目都在正文里，head_of 得按页码判
            head = book.head_of(v, cleaned, num) or ''
            # 章节名只有卷次、回目从目录来（「鏡花緣卷二」那页的回次是第二回）：
            # 页内报出的回目比目录可靠，先认页内的
            if not head or len(norm(head)) > 24:
                head = cat.get(num, '')
            if isinstance(book, Huaben) and head:
                body = book.body_start(cleaned, head)
            else:
                body = [p for p in cleaned
                        if not p.startswith('\x00')
                        and not book.is_title_line(p, head) and not LOCATOR_RX.match(norm(p))]
            chunks = [[num, head, body]]
        for n, head, body in chunks:
            if n is None:
                auto += 1
                n = auto
            else:
                auto = n
            head = head or ''
            if not head or len(norm(head)) > 24:
                head = cat.get(n, '')
            # 版心行「容齋五筆卷第十」这类只标书卷、没有篇名的行，不留在正文里
            body = [p for p in body
                    if norm(p) and len(norm(p)) >= 2
                    and not re.fullmatch(r'[^\s]{0,8}卷[之第]?[%s]+' % CN, norm(p))]
            if not body:
                continue
            if records and records[-1]['num'] == n:
                records[-1]['paragraphs'].extend(body)   # 同一回的续页：接着上一页写
                if not records[-1]['head']:
                    records[-1]['head'] = head
                continue
            records.append({'num': n, 'author': book.author, 'head': head, 'paragraphs': body})
    return records, folded


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('raw')
    ap.add_argument('out')
    ap.add_argument('--book', required=True, choices=sorted(BOOKS))
    ap.add_argument('--catalog', help='另抓的目录页 raw.json（book_text.mjs 产出）')
    a = ap.parse_args()
    raw = json.load(open(a.raw, encoding='utf-8'))
    book = BOOKS[a.book]()
    cat = read_catalog(json.load(open(a.catalog, encoding='utf-8'))) if a.catalog else read_catalog(raw)
    if cat:
        print(f'目錄补到 {len(cat)} 条')
    recs, folded = convert(raw, book, cat)
    print(f'{len(recs)} 条；跳过 {len(folded)} 页')
    for f in folded:
        print('  跳过', f['name'], '—', f['reason'])
    print(f'{sum(len("".join(r["paragraphs"])) for r in recs)} 字')
    for r in recs[:3] + recs[-2:]:
        print('  ', r['num'], r['head'][:34], len(r['paragraphs']), '段')
    if a.out:
        json.dump(recs, open(a.out, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)


if __name__ == '__main__':
    main()
