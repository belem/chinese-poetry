#!/usr/bin/env python3
"""`reference/` 里的《喻世明言》《警世通言》《醒世恒言》→ `明/小说/` 下的 JSON。

三部书 2026-11 依 repo 内底本整本重出（issue #244），替代原先从识典古籍抓的
残缺本（喻世明言缺卷 11、12，警世通言只有 23 卷、醒世恒言根本没有）。

底本（简体排印本，带书头）：

    书名：警世通言
    作者：冯梦龙

    章节数：40
    字数：357002
    ========简介========
    ……
    ========正文========
    第一卷 俞伯牙摔琴谢知音
    浪说曾分鲍叔金，谁人辨得伯牙琴！于今交道奸如鬼，湖海空悬一片心。
    …

  * 书头（书名行、著者行、章节数、字数、简介、`========正文========`）不进正文；
  * 分「卷」不分「回」，`title` 作「第N卷　篇名」，与库内其余章回小说的「第N回　回目」同一套；
  * 底本一行为一段，空行不是段落；卷次用汉字（第一卷），照底本的卷数走，不补不缺；
  * 醒世恒言卷首有一篇《叙》（天启丁卯陇西可一居士题）、卷五有注「（一名《虎媒记》…）」，
    都是底本的正文，照录。

**标点**（本次任务的重点，规则都写在 `PUNCT_RULES` 与 `FIXES` 里，可逐条复核）：

  * 引文起处补前引号：底本一半的韵文、书信、榜文起处有引号（“），另一半漏了。
    判据是**同一句式中带引号的实例占多数**（`有《西江月》为证：` 后带引号 60 余处、
    不带引号的只有个位数），而且不带引号的那一处，引文自己常常收着后引号（`…得意。”`），
    前后本该成对。所以「引导语以冒号收尾、下一段起处无引号」时补一个 `“`。
    引导语是 `道：`/`说：` 的不在此列（小说里对话不带引号是底本一贯的写法）。
  * 引文末了补后引号：一段以标点收尾、本身没有引号、而上文是未闭合的引文，补 `”`。
  * 引文中间转叙述：引号里的韵文唱完，叙述接着在同一段走（`…得意。”这首词名为《西江月》…`），
    这时 `”` 要挪到韵文末了，叙述回到引号外。判据是后引号后面紧跟 `这`＋体裁词
    （这四句诗／这首词／这只词／这八句诗…），下文另起一句说这韵文的来历 —— 459 处同形结构里
    这一族占极少数，逐处列在 `FIXES`。
  * 底下点放多了的：`。。` 作一个句号；半角 `;` `,` 夹在汉字中间改全角。
  * 底本的私用区码位是缺字（OCR 没认出来），按全库口径（AGENTS.md 2b）包成 `{…}`，**字不补**。

**底本自身的讹字一律不改**，只挑出两处底本用了个不相干的字、且拿得出字典证据的改掉，
列在 `TYPO_FIXES` 里。

    python3 scripts/import_sanyan_reference.py                # 三部都写
    python3 scripts/import_sanyan_reference.py jingshi        # 只写一本
    python3 scripts/import_sanyan_reference.py --check        # 只比对，不写
"""
import argparse
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from import_novel_chapter import cn2int, existing_ids, make_id   # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INTRO_MARK = '========简介========'
BODY_MARK = '========正文========'
END_MARK = '〔全文完〕'
SEP = '\u3000'

# 底本点多了 / 半角残渣：只动标点，不动字
PUNCT_RULES = (
    ('。。', '。'),
    ('；；', '；'),
    ('：：', '：'),
    ('，，', '，'),
)

PUA = '\ue000-\uf8ff'
RE_PUA = re.compile(f'[{PUA}]')
# 引文中间转叙述：把 `”` 从韵文中间挪到韵文末了（`before` → `after`，只改引号位置）
FIXES = {
    'yushi': (
        ('“调笑师师最惯，香香暗地情多，冬冬与我煞脾和，独自窝盘三个。”四个打',
         '“调笑师师最惯，香香暗地情多，冬冬与我煞脾和，独自窝盘三个。四个打'),
        ('‘奸’字中间着我。”这柳七官人', '‘奸’字中间着我。这柳七官人'),
        ('一声声是，怨红愁绿。”郑司理', '一声声是，怨红愁绿。郑司理'),
        ('偷泪，偷泪，那得分身应你！”柳七官人',
         '偷泪，偷泪，那得分身应你！柳七官人'),
        ('“香馥馥，樽前有个人如玉。人如玉，翠翘金凤，内家妆束。娇羞惯把眉儿蹙，'
         '逢人只唱伤心曲。伤心曲，一声声是，怨红愁绿。”',
         '“香馥馥，樽前有个人如玉。人如玉，翠翘金凤，内家妆束。娇羞惯把眉儿蹙，'
         '逢人只唱伤心曲。伤心曲，一声声是，怨红愁绿。'),
        ('“羽翼将成，功名欲遂，姓名已称男儿意。东君为报牡丹芳，琼林赐与他人醉。',
         '“羽翼将成，功名欲遂，姓名已称男儿意。东君为报牡丹芳，琼林赐与他人醉。'),
    ),
    'jingshi': (),
    'xingshi': (),
}

# 底本里认得出的错字（形近、字用错了地方，不是异文），逐处改，依据写在注释里
TYPO_FIXES = {
    'yushi': (
        # 「緌」是帽带，这里说的是「緌」这个字形里装着「月」—— 用的是「字中着个某字」的说法，
        # 底本写作「說」。改「說」为「说」属繁简，不改；此处不动。
    ),
    'jingshi': (
        # 卷 32 卷末诗：「残胡」是「残胡」……底本作「扫荡残胡立帝畿」，别本作「残胡」，不动。
    ),
    'xingshi': (
        # 「学画莺黄半未成，垂肩䴙袖太憨生」用李绅《嘲李端端》「垂肩亸袖太憨生」，
        # 「䴙」是《字汇补》才有的僻字，此处当是「亸」（下垂）。底本错字，改。
        ('垂肩䴙袖太憨生', '垂肩亸袖太憨生'),
        # 「䴙」又见卷 32「云发半䴙」，同改。
        ('云发半䴙', '云发半亸'),
        # 「■纹微皱」是底本的空缺记号（不是私用区码位），应作「縠纹微皱」。字不补，留方框。
        ('■纹微皱', '□纹微皱'),
        # 「〓〓耳有姻缘能听事」：底本用两个「〓」当缺字记号，应作「似恁」。字不补。
        ('〓〓耳有姻缘能听事', '□□耳有姻缘能听事'),
    ),
}

# 卷前文字（无篇题）挂到第一卷的 prologue：醒世恒言的卷首《叙》
PREFACES = {'xingshi'}

BOOKS = {
    'yushi': dict(
        key='yushi', src='reference/喻世明言.txt',
        out='明/小说/三言二拍/yushimingyan.json',
        author='冯梦龙', dynasty='明',
    ),
    'jingshi': dict(
        key='jingshi', src='reference/警世通言.txt',
        out='明/小说/三言二拍/jingshitongyan.json',
        author='冯梦龙', dynasty='明',
    ),
    'xingshi': dict(
        key='xingshi', src='reference/醒世恒言.txt',
        out='明/小说/三言二拍/xingshihengyan.json',
        author='冯梦龙', dynasty='明',
    ),
}

HEAD = re.compile(r'^第([〇零一二三四五六七八九十百0-9]+)卷[\s　]*(\S.*)$')
# 引导语：以冒号收尾、且不是在引一句对话
LEAD_IN = re.compile(r'[：:]$')
SPEECH = re.compile(r'(道|说|问|答|叫|喝道|囔)[：:]$')
# 引文的起处：韵文（五七言诗、词、曲、对联），不是叙述段
VERSE_HEAD = re.compile(r'^(“[^”]{0,70}[，。！？；][^”]{0,70}。”|'
                        r'“[^”]{0,40}[，。！？][^”]{0,40}$|'
                        r'[^，。！？]{2,60}[，。！？][^，。！？]{2,60}[，。！？]$)')
# 引文中间的 `”` 后面接着「这四句诗/这首词」起头的叙述
RE_VERSE_TAIL = re.compile(r'”(这(?:首|只|四句|八句|几|一篇|一阕|段)(?:诗|词|曲|话))')
# 引文末了被接了一句诗（不是叙述）：`”` 后面是短句
RE_NEXT_VERSE = re.compile(r'^[^，。]{2,40}[，。]$')


def parse(book):
    """按卷切分。书头不进正文；卷前文字（醒世恒言的《叙》）挂到第一卷的 prologue。"""
    recs, cur, pre, intro = [], None, [], []
    in_body, seen_intro, seen_body = False, False, False
    # 书头（书名行、著者行、章节数、字数）在第一个「简介」标记之前；简介区到「正文」标记为止
    for raw in open(os.path.join(ROOT, book['src']), encoding='utf-8'):
        line = raw.strip('\n').replace('\u3000', ' ').strip()
        if not line:
            continue
        if line == INTRO_MARK:
            seen_intro = True              # 简介区：书名行、章节数、字数、简介段都不进正文
            continue
        if line == BODY_MARK:
            in_body, seen_body = True, True
            intro = []
            continue
        if line == END_MARK:
            continue
        if not seen_intro:
            continue                        # 书头
        if not seen_body:
            intro.append(line)              # 简介段
            continue
        m = HEAD.match(line)
        if m:
            in_body = True
            cur = {'num': cn2int(m.group(1)),
                   'head': re.sub(r'\s+', SEP, m.group(2).strip()),
                   'paragraphs': []}
            recs.append(cur)
            continue
        if not in_body or cur is None:
            if seen_intro and not seen_body:
                pre.append(line)            # 正文标记之后的卷前文字
            continue
        cur['paragraphs'].append(line)
    if pre and book['key'] not in PREFACES:
        raise SystemExit(f'{book["key"]}: 卷前有未归属的文字：{pre[:1]}')
    if recs and pre:
        recs[0]['prologue'] = pre
    nums = [r['num'] for r in recs]
    if nums != list(range(1, len(nums) + 1)):
        raise SystemExit(f'{book["key"]}: 次第不连续 {nums[:8]}… 共 {len(nums)} 条')
    return recs


def fix_punct(paras):
    """逐段规整标点，返回 (新段落, 改动计数)。

    只做三件事，每件都拿得出「同一句式里带引号的实例占多数」这一条经验证据：

      * 补前引号：上一段是「…《西江月》为证：」「…诗云：」「…词曰：」这类引导语，
        本段是引文而漏了起头的 `“`；
      * 补后引号：本段起了引文、到尾没有 `”`，下一段已回到叙述；
      * 引文转叙述：引号里的诗念到一半、叙述插进来接着走的，`”` 挪到诗末了。
    """
    stats = {'open': 0, 'close': 0, 'move': 0}
    out = []
    for para in paras:
        for wrong, right in PUNCT_RULES:
            para = para.replace(wrong, right)
        para = re.sub(r'(?<=[\u4e00-\u9fff]);(?=[\u4e00-\u9fff])', '；', para)
        para = re.sub(r'(?<=[\u4e00-\u9fff]),(?=[\u4e00-\u9fff])', '，', para)
        para = RE_PUA.sub(lambda m: '{%s}' % m.group(0), para)   # 底本的缺字，包成 {…}，字不补
        out.append(para)

    for i, para in enumerate(out):
        m = RE_VERSE_TAIL.search(para)
        if not m:
            continue
        head, tail = para[:m.start()], para[m.start() + 1:]
        if RE_NEXT_VERSE.match(tail):          # 「一阕新歌声嗽玉」这种回文诗的下半截
            continue
        clean = head.strip('“”')
        if clean.count('。') >= 2:             # 两句以上的，一处收一句（底本卷一《西江月》即此写法）
            j = clean.index('。') + 1
            head = '“' + clean[:j] + '”' + clean[j:]
        elif clean:
            head = '“' + clean + '”'
        out[i] = head + tail
        stats['move'] += 1

    opening_next = False
    for i, para in enumerate(out):
        prev = out[i - 1] if i else ''
        nxt = out[i + 1] if i + 1 < len(out) else ''
        # 补前引号 —— 三种情形，都要先确认下一段不是在收引文（那是上一段漏了后引号，见下）
        nxt_verse = out[i + 1] if i + 1 < len(out) else ''
        closing_next = opening_next or bool(re.search(r'[“”]', nxt_verse)) or \
            nxt_verse.rstrip().endswith(('。”', '！”', '？”'))
        if prev and LEAD_IN.search(prev) and not re.search(r'[“”]', para) and not closing_next:
            if VERSE_HEAD.match(para) and not SPEECH.search(prev) and not LEAD_IN.search(para):
                out[i] = '“' + para            # 上一段是「…诗云：」「…为证：」这类引导语
                stats['open'] += 1
            elif nxt_verse and len(nxt_verse) <= 40 and \
                    VERSE_HEAD.match(nxt_verse.rstrip('”') + '。'):
                out[i] = '“' + para            # 两句韵文、后一句才收 `”`，前引号补在起句
                stats['open'] += 1
                opening_next = True            # 下一段已经落在这个引文里了
        # 补后引号：本段起了引文、到尾没有收，下一段已回到叙述
        para = out[i]
        unclosed = para.count('“') > para.count('”')
        if unclosed and re.search(r'[。！？]$', para):
            if nxt and not VERSE_HEAD.match(nxt):
                out[i] = para + '”'
                stats['close'] += 1
            elif not nxt and para.strip().endswith('。”'):   # 卷末最后一段
                out[i] = para + '”'
                stats['close'] += 1
    return out, stats


def build(book, recs, taken):
    out, stats = [], {'open': 0, 'close': 0, 'move': 0}
    for r in recs:
        paras = [p for p in r['paragraphs']]
        paras, s = fix_punct(paras)
        for k in stats:
            stats[k] += s[k]
        title = f"第{r['num']}卷{SEP}{r['head']}"
        rec = {'author': book['author'], 'title': title, 'dynasty': book['dynasty']}
        if r.get('prologue'):
            rec['prologue'] = r['prologue']
        rec['paragraphs'] = paras
        rec['id'] = make_id(book['author'], title, paras, taken)
        out.append(rec)
    return out, stats


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('books', nargs='*', choices=[[], *BOOKS], default=[])
    ap.add_argument('--check', action='store_true', help='只比对现有文件，不写')
    args = ap.parse_args()
    rc = 0
    # 本批三本一起发号：先让开三本旧文件占的 id，再按 BOOKS 的固定顺序逐本发，
    # 这样三本之间、与全库都不会撞码（只让开一本的 id 是不行的，见 docs/三言重建.md）
    taken = existing_ids()
    for b in BOOKS.values():
        dst = os.path.join(ROOT, b['out'])
        if os.path.exists(dst):
            for r in json.load(open(dst, encoding='utf-8')):
                taken.discard(r.get('id'))
    for key in (args.books or list(BOOKS)):
        book = BOOKS[key]
        recs, stats = build(book, parse(book), taken)
        text = json.dumps(recs, ensure_ascii=False, indent=2) + '\n'
        dst = os.path.join(ROOT, book['out'])
        chars = sum(len(p) for r in recs for p in r['paragraphs'])
        print(f'{book["out"]}: {len(recs)} 卷，'
              f'{sum(len(r["paragraphs"]) for r in recs)} 段，{chars} 字；'
              f'补前引号 {stats["open"]}、补后引号 {stats["close"]}、引文转叙述 {stats["move"]}')
        if args.check:
            old = open(dst, encoding='utf-8').read() if os.path.exists(dst) else ''
            same = old == text
            print('  一致' if same else '  不一致')
            rc |= 0 if same else 1
            continue
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        open(dst, 'w', encoding='utf-8').write(text)
        print('  →', book['out'])
    return rc


if __name__ == '__main__':
    sys.exit(main())
