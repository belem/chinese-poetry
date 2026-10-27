#!/usr/bin/env python3
"""把 crawl_book.mjs 缓存的整书正文切成「章节」，供建目录（目次）用。

识典古籍的章节页正文是纯文本，标题 / 作者 / 正文混排，且不同卷的排版不一致
（有的卷「标题」单独一行，有的整卷挤成一段）。这里只做能稳定做到的两件事：

  1. 按段落顺序保留每一段正文（去掉站点 UI 噪声）；
  2. 标出「类目行」——底本编排体类，如 五言古詩 / 七言律詩 / 樂府，是选本最强的指纹。

具体到每部书怎么细分（标题从哪断、作者怎么认），由各自的 build_*.py 处理。
"""
import json
import re

UI_HEAD = '登录'
UI_TAIL = '下一篇'
# 「唐詩三百首注疏卷之一，蘅塘退士手編，…」这类卷首题署
VOLUME_HEAD = re.compile(r'^.*(卷之?[一二三四五六七八九十上中下]+|卷[一二三四五六七八九十]+上|手編)')
PUNCT = re.compile(r'[，。：；？！、]')


def page_body(text):
    """去掉站点 UI，留下正文。"""
    i = text.find(UI_HEAD)
    body = text[i + len(UI_HEAD):] if i >= 0 else text
    j = body.find(UI_TAIL)
    return body[:j] if j >= 0 else body


def paragraphs(text):
    return [p.strip() for p in page_body(text).split('\n') if p.strip()]


def is_short_line(p, max_len=15):
    """标题 / 作者行：短、不带句读、不是卷首题署。"""
    return len(p) <= max_len and not PUNCT.search(p) and not VOLUME_HEAD.match(p) and not p.startswith('卷')


def load(path):
    return json.load(open(path, encoding='utf-8'))


PREAMBLE = re.compile(r'^(元和|開元|天寶|大歷|貞元|至德|乾元|上元)[一二三四五六七八九十〇零\d]*年')
SENT = re.compile(r'[^，。：；？！]+[，。：；？！]?')
CATEGORY = re.compile(r'^(五言古詩|七言古詩|五言樂府|七言樂府|樂府|五言律詩|七言律詩|五言絶句|七言絶句|五言排律|七言排律)$')
SUBHEAD = re.compile(r'^(其一|其二|其三|其四|其五|其六|其七|其八|其九|其十|其二首|二首|三首)$')


def sentences(p):
    return [s for s in SENT.findall(p) if s.strip()]


def is_category(p):
    return bool(CATEGORY.match(p))


def is_subhead(p):
    return bool(SUBHEAD.match(p)) or len(p) <= 3 and p.startswith('其')


def sb_sentences(p):
    return sentences(p)


def first_sentence(p, n=8):
    """段落开头 n 字，作为「首句」锚点（不带标点的连写）。

    底本夹注会整段混进正文（「屬湖廣常德府旁有桃源縣」「漢書曰冰姓李」），
    这类段落不是诗句：没有句读的连续文字超过 15 字，或整段落在一句话里，
    就当注释跳过，往下找第一段像诗的。
    """
    for para in p.split('\n'):
        para = para.strip()
        if not para:
            continue
        if PREAMBLE.search(para):          # 「元和十年，余左遷九江郡司馬。明年秋…」诗序
            continue
        if len(sb_sentences(para)) < 2:     # 只有一句话的段落是标题或夹注，不是诗句
            continue
        return re.sub(r'[，。：；？！、]', '', para)[:n]
    return re.sub(r'[，。：；？！、]', '', p)[:n]
