# -*- coding: utf-8 -*-
"""識典六臣注本一章的「自然段」列表（去注，保留六臣本的句读）。

缓存目录 `$ZHAOMING_SD` 一章一文件，内容是章节页 DOM 里的块（`article.chapter-reader`
的 h2/h3/h4/p），形如 `{"tag": "p", "t": "..."}`。抓取要点见 docs/昭明文选重建.md：

- 卷五十一至六十在站上按「章」排，长卷（论一、论三、诔上、碑文上、碑文下、行状）被切成
  一篇一章，后续章节没有卷头。章节页要把 `.chapter-reader-container` 滚到文末，再顺着
  `article footer a`（下一篇）继续抓，一章一文件存下来。
- 一行 DOM 就是一个自然段，注文在页面上是折叠的，`innerText` 只有白文——比 SSR 的
  `paragraphList` 干净（SSR 长卷只给前十几页，且正文注文交错）。
"""
import json, os, re

SD = os.environ.get('ZHAOMING_SD', '/tmp/zhaoming-sd')

NUM = {'一': 1, '二': 2, '三': 3, '四': 4, '五': 5, '六': 6, '七': 7, '八': 8, '九': 9}
VOL_RE = re.compile(r'六臣(?:註|注)文[選选][卷巻]第([一二三四五六七八九十]+)')
# 无卷头章节里，页面把后续篇的题头渲染成 p：短、不带句读、以体类字收尾
TITLE_RE = re.compile(r'(論|誄|文|銘|箴|狀|誌|贊|頌|賦|書|啟|序|記|表)$')
SKIP = ('卷終',)


def _cn2int(s):
    """卷号：五十一 → 51，五十五 → 55，六十 → 60"""
    if '十' in s:
        i = s.index('十')
        left = [NUM[c] for c in s[:i] if c in NUM]
        right = [NUM[c] for c in s[i + 1:] if c in NUM]
        return (left[0] if left else 1) * 10 + (right[0] if right else 0)
    return NUM[s]


def blocks(v):
    return json.load(open(os.path.join(SD, v + '.json'), encoding='utf-8'))


def chapter_volume(v):
    """这一章属于第几卷：章内有「六臣注文選卷第五十三」就用它，没有返回 None
    （长卷被切开的后续章节没有卷头，靠抓取顺序推断，见 zhaoming_build2）。"""
    for b in blocks(v):
        m = VOL_RE.search(b['t'])
        if m:
            return _cn2int(m.group(1))
    return None


def paragraphs(v, vol):
    """一章的块：[(kind, text)]，kind = genre/title/author/para。

    有卷头的章，卷头之后才算本卷；没有卷头的章整章算一卷（它是本卷的后续篇）。
    """
    has_header = any(VOL_RE.search(b['t']) for b in blocks(v))
    # 章末只剩一行「六臣注文選卷第五十七」这样的页脚时，前头的正文仍是本卷的
    only_footer = has_header and all(
        VOL_RE.fullmatch(b['t'].strip()) or not VOL_RE.search(b['t']) for b in blocks(v))
    out, cur = [], (not has_header or only_footer)
    for b in blocks(v):
        t = b['t'].strip()
        if not t or t in SKIP:
            continue
        if not has_header and t in ('梁昭明太子撰', '唐李善并五臣注'):
            continue
        m = VOL_RE.search(t)
        if m:
            n = _cn2int(m.group(1))
            if only_footer:
                # 章末页脚，后面没有正文了
                continue
            if n == vol:
                cur = True
            elif n > vol:
                break
            else:
                cur = False
            continue
        if not cur:
            continue
        if b['tag'] in ('h3', 'h4'):
            out.append(('genre' if b['tag'] == 'h3' else 'title', t))
        elif b['tag'] == 'p':
            if len(t) <= 12 and not re.search(r'[，。；：？！]', t) and TITLE_RE.search(t):
                if out and out[-1][0] == 'title' and len(t) <= 5:
                    out.append(('author', t))
                else:
                    out.append(('title', t))
            else:
                out.append(('para', t))
    # 篇题行之后、正文之前的那一段短行是作者；长卷「一段 = 一篇」的章没有单独的上一篇
    # 题行，作者名留在段首（`潘安仁，`），也剥出来。
    res = []
    for k, t in out:
        if k == 'para' and res and res[-1][0] == 'title' and len(t) <= 8 and '。' not in t:
            res.append(('author', t.strip('，,')))
            continue
        if k == 'para' and len(t) <= 8 and '。' not in t and '，' not in t:
            res.append(('author', t.strip('，,')))
            continue
        res.append((k, t))
    return res


def sentences(ps):
    """一段 → 句：按句末标点切，引号内的不切。"""
    out = []
    for t in ps:
        buf, depth = '', 0
        for ch in t:
            buf += ch
            if ch in '“「':
                depth += 1
            elif ch in '”」':
                depth = max(0, depth - 1)
            elif ch in '。！？' and depth == 0:
                out.append(buf)
                buf = ''
        if buf.strip():
            out.append(buf)
    return out
