#!/usr/bin/env python3
"""`reference/` 里的四部章回小说 → `明/小说/`、`清/小说/` 下的 JSON。

按 `reference/东周列国志.txt`、`封神演义.txt`、`水浒传.txt`、`红楼梦.txt`
把四部书整本重出（issue #200）。底本都是简体、逐段带句读的排印本，版式如下。

东周列国志、封神演义（带书头，回目行前后各有一个空行）：

    《东周列国志》 明 冯梦龙

    章节数：108
    字数：681497
    ========简介========
    ……
    ========正文========
    第一回 周宣王闻谣轻杀 杜大夫化厉鸣冤
    词曰：
    ……

  * 书头（著者行、章节数、字数、简介、`========正文========`）不入正文；
  * 封神演义每回起处有「封神演义 / 明·许仲琳 / 第N回XXX」三行版头，是版面残留，不进正文；
    回目行在同回出现两次（「第二回 冀州侯苏护反商」「第二回冀州侯苏护反商」），取第一次，第二次起属正文版头。

水浒传（无书头，回目行前后各一个空行）：

    《水浒传》明  施耐庵

    第一回 张天师祈禳瘟疫 洪太尉误走妖魔
    …
  * 第 100–120 回的回目与正文起句「话说…」黏在同一行，按「话说」切开；
  * 繁体底本，一字不改。

红楼梦（回目作「第N章」，正文段首两个全角空格）：

    《红楼梦》清  曹雪芹

    第1章 甄士隐梦幻识通灵 贾雨村风尘怀闺秀
    　　此开卷第一回也。
    …
  * 底本 120 章（章号＝回次），段首缩进去掉，段内一字不动；
  * 每回末的 `(本章完)` 是电子本的标记，不是正文，去掉。

四本的底本里另有一类抓取残留，处理时**只动排版与标记、不动字**，逐项记在这里：

  * 东周列国志：网站水印行「奇Qīsuū.сom书」「|Qī-shu-ωang|」共 6 行，整行去掉（是水印，
    不是底本正文，与「西里尔/希腊乱码」不同）；底本点放多了一下的地方（「充鹤粮；，民有饥冻」
    「必不能返！”，捶胸」「此乃，干将，、，莫邪，之结末也」）删掉多出来的那一下。
  * 封神演义：第 48 回「红水阵」一段后半是抓取时带进来的坏 HTML（从「弟子分开左摇」起
    一长串乱码夹着 `</font>`），这一截整段不取（底本对应处要另找本子补，记在 docs 里）；
    每回起处的「封神演义 / 明·许仲琳」版头与重复的那遍回目行不进正文；
    第 44 回诗末「更难禁。。」按一个句号。
  * 封神演义、红楼梦底本里的私有区码位是底本的缺字（封神 e4cc→堂、红楼 e24b→階 ……），
    底本没有用 `{}` 标出，按全库口径（AGENTS.md 2b）加 `{}`，**字不补**；它们算底本的缺字，
    不算错讹，等另找底本对勘。

四本书共用的规则：

  * 一段一行，空行不是段落；
  * `author` 取书头著者，`dynasty` 按作者朝代；
  * `title` 统一作「第N回　回目」（全角空格分隔，红楼梦底本的「第N章」也写作「第N回」）；
  * `id` 规则同 `scripts/shidian/convert.py`（author|title|正文 blake2b），改正文才变。

    python3 scripts/import_novel_reference.py                # 四本都写
    python3 scripts/import_novel_reference.py dongzhou      # 只写一本
    python3 scripts/import_novel_reference.py --check        # 只比对，不写
"""
import argparse
import hashlib
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

CN = {c: i for i, c in enumerate('零一二三四五六七八九')}
CN['〇'] = 0


def cn2int(s):
    if s.isdigit():
        return int(s)
    s = s.replace('〇', '零')
    if '百' not in s and '十' not in s and len(s) > 1:
        return int(''.join(str(CN[c]) for c in s if c in CN))
    if '百' in s:
        hi, lo = s.split('百')
        lo = lo.lstrip('零')
        return (CN[hi] if hi else 1) * 100 + (cn2int(lo) if lo else 0)
    if '十' not in s:
        return CN[s]
    hi, lo = s.split('十')
    return (CN[hi] if hi else 1) * 10 + (CN[lo] if lo else 0)


def make_id(author, title, body, taken):
    key = f'{author}|{title}|{"".join(body)}'
    size = 6
    while True:
        digest = hashlib.blake2b(key.encode(), digest_size=16).digest()
        v = int.from_bytes(digest, 'big')
        out = ''
        for _ in range(size):
            v, r = divmod(v, 22)
            out = '0123456789abcdefghijklmnopqrstuv'[r] + out
        if out not in taken:
            taken.add(out)
            return out
        size += 1


# 底本残留的网站水印行：「奇Qīsuū.сom书」「|Qī-shu-ωang|」，行首行尾都可能带竖线
WATERMARK = re.compile(r'^\|?(奇Q|Q)[īi]?[-\w.\u03c9\u0430-\u044f\s]*\|?$')

# ── 四本的版式差异都在这里 ────────────────────────────────────────────────

BOOKS = {
    'dongzhou': dict(
        key='dongzhou',
        src='reference/东周列国志.txt',
        out='明/小说/东周列国志/dongzhoulieguozhi.json',
        author='冯梦龙', dynasty='明',
        head=re.compile(r'^第([〇零一二三四五六七八九十百]+)回[\s　]*(\S.*)$'),
        skip_head=True,
        # 底本残留的网站水印行（与错讹、缺文无关，不是正文）
        drop=WATERMARK,
        # 底本点放多了一下的地方，删掉那一下，字不动：
        # 换行处「。」「，」叠用（「充鹤粮；，民有饥冻」「由，，皆因」「左右，，缚」），
        # 引号外多一个逗号（「必不能返！”，捶胸」「天下才也。，”孝公曰」），
        # 书名号外的逗号（「此乃，干将，、，莫邪，之结末也」→「此乃‘干将’、‘莫邪’之结末也」）
        fix=(('”，。', '”。'), ('；，', '；'), ('，，', '，'), ('？。', '？'), ('！。', '！'),
             ('。，', '。'), ('，。', '，'), ('此乃，', '此乃‘'), ('，、，', '‘、‘'),
             ('‘莫邪，之', '‘莫邪’之'), ('‘干将‘', '‘干将’')),
    ),
    'fengshen': dict(
        key='fengshen',
        src='reference/封神演义.txt',
        out='明/小说/封神演义/fengshenyanqi.json',
        author='许仲琳', dynasty='明',
        head=re.compile(r'^第([〇零一二三四五六七八九十百]+)回[\s　]*(\S.*)$'),
        skip_head=True,
        # 每回起处的版面残留：书名、著者（第100回起还夹着「地藏王」一行）
        plate=re.compile(r'^(封神演义|明·许仲琳|地藏王)$'),
        # 第48回「红水阵」一处，正文后半是抓取时带进来的坏 HTML，从「左摇」下的乱码一直错到行尾
        drop=re.compile(r'<\s*/?\s*font[^>]*>?.*$'),
        trunc=re.compile(r'左摇.*$'),
        # 第44回诗末「更难禁。。」，底本点了两个句号
        # 私有区码位是底本的缺字：e4cc→堂、e4b8→袅、e406→喤、e56d→纵、e3fe→𤜯。
        # 底本没有用 {} 标出，加 {} 与全库口径一致（AGENTS.md 2b），字不补
        fix=(('。。', '。'), ('！。', '！'), ('？。', '？'), ('\ue4cc', '{堂}'), ('\ue4b8', '{袅}'),
             ('\ue406', '{喤}'), ('\ue56d', '{纵}'), ('\ue3fe', '{𤜯}'),
             ('\ue404', '{咼}'), ('\ue349', '{㺄}'), ('\ue3ab', '{𣏌}'),
             ('\ue1e2', '{犴}'), ('\ue4b4', '{邘}'), ('\ue407', '{凫}'),
             ('\ue807', '{睞}'), ('\ue008', '{飡}')),
    ),
    'shuihu': dict(
        key='shuihu',
        src='reference/水浒传.txt',
        out='明/小说/水浒传/shuihuzhuan.json',
        author='施耐庵', dynasty='明',
        head=re.compile(r'^第([〇零一二三四五六七八九十百]+)回[\s　]*(\S.*)$'),
        skip_head=False,
    ),
    'honglou': dict(
        key='honglou',
        src='reference/红楼梦.txt',
        out='清/小说/红楼梦/hongloumeng.json',
        author='曹雪芹', dynasty='清',
        # 回目行顶格起；正文段前有两个全角缩进，故以「第N章」起首为判据
        head=re.compile(r'^第([0-9〇零一二三四五六七八九十百]+)章[\s　]*(\S.*)$'),
        skip_head=False,
        # 底本每回末的「(本章完)」是电子本的标记，不是正文
        drop=re.compile(r'^[(（]本章完[)）]$'),
        # 私有区码位是底本的缺字：e24b→階、e24c→放、e24d→槅、e02d→卍、e266→啑、
        # e247→靸、e272→縐、e23f→鬧、e265→嗤、e3ab→攏、e2b9→籙。加 {}，字不补
        fix=(('\ue24b', '{階}'), ('\ue24c', '{放}'), ('\ue24d', '{槅}'),
             ('\ue02d', '{卍}'), ('\ue266', '{啑}'), ('\ue247', '{靸}'),
             ('\ue272', '{縐}'), ('\ue23f', '{鬧}'), ('\ue265', '{嗤}'),
             ('\ue3ab', '{攏}'), ('\ue2b9', '{籙}')),
    ),
}

# 水浒传第 100 回起，回目与正文起句黏在一行
NARR_START = '话说'
# 书头结束标记
BODY_MARK = '========正文========'


def parse(book):
    # 东周列国志、封神演义带书头（著者行、章节数、简介），正文从标记行之后起
    recs, cur, in_body = [], None, not book['skip_head']
    plate_head = None
    for raw in open(os.path.join(ROOT, book['src']), encoding='utf-8'):
        raw = raw.rstrip('\n')
        if book.get('plate') and book['plate'].match(raw.replace('\u3000', ' ').strip()):
            continue                                   # 回目行之前的「封神演义 / 明·许仲琳」版头
        # 红楼梦的回目行顶格、正文段前两个全角缩进，判断在去缩进之前
        m = book['head'].match(raw) if raw[:2] != '第' else \
            book['head'].match(raw.replace('\u3000', ' ').strip())
        line = raw.replace('\u3000', ' ').strip()
        if not line:
            continue
        if not in_body:
            if line == BODY_MARK:
                in_body = True
            continue
        if m:
            head = re.sub(r'\s+', '\u3000', m.group(2).strip())
            if head == plate_head:
                continue                               # 回目之后重复的那遍版头行
            # 水浒传：回目与正文起句黏在一行
            k = head.find(NARR_START)
            if k > 0:
                cur = {'num': cn2int(m.group(1)), 'head': head[:k].strip(),
                       'paragraphs': [head[k:]]}
            else:
                cur = {'num': cn2int(m.group(1)), 'head': head, 'paragraphs': []}
            plate_head = head
            recs.append(cur)
            continue
        if cur is None:
            continue
        if book.get('drop') and book['drop'].match(line):
            continue
        if book.get('trunc'):
            line = book['trunc'].sub('', line) or line   # 坏 HTML 起的那一截整段不取
        for old, new in book.get('fix', ()):
            line = line.replace(old, new)
        if line:
            cur['paragraphs'].append(line)
    return recs


def build(book, recs):
    taken, out = set(), []
    nums = [r['num'] for r in recs]
    if nums != list(range(1, len(nums) + 1)):
        raise SystemExit(f'{book["key"]}: 回次不连续 {nums[:8]}… 共 {len(nums)} 条')
    for r in recs:
        assert r['paragraphs'], f'{book["key"]}: 第{r["num"]}回 无正文'
        title = f"第{r['num']}回\u3000{r['head']}"
        rec = {'author': book['author'], 'title': title, 'dynasty': book['dynasty'],
               'paragraphs': r['paragraphs']}
        rec['id'] = make_id(book['author'], title, rec['paragraphs'], taken)
        out.append(rec)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('books', nargs='*', choices=[[], *BOOKS], default=[])
    ap.add_argument('--check', action='store_true', help='只比对现有文件，不写')
    args = ap.parse_args()
    keys = args.books or list(BOOKS)
    rc = 0
    for key in keys:
        book = BOOKS[key]
        recs = build(book, parse(book))
        text = json.dumps(recs, ensure_ascii=False, indent=2) + '\n'
        dst = os.path.join(ROOT, book['out'])
        chars = sum(len(p) for r in recs for p in r['paragraphs'])
        print(f'{book["out"]}: {len(recs)} 回，'
              f'{sum(len(r["paragraphs"]) for r in recs)} 段，{chars} 字')
        if args.check:
            old = open(dst, encoding='utf-8').read() if os.path.exists(dst) else ''
            same = old == text
            print('  一致' if same else '  不一致')
            rc |= 0 if same else 1
            continue
        open(dst, 'w', encoding='utf-8').write(text)
        print('  →', book['out'])
    return rc


if __name__ == '__main__':
    sys.exit(main())
