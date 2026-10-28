#!/usr/bin/env python3
"""把 `历代/` 按朝代拆进顶层朝代目录，`历代/` 随之消失。

  python3 scripts/split_dynasty.py            # 预演：打印分类统计
  python3 scripts/split_dynasty.py --apply    # 写回数据，生成 docs/历代拆分.tsv

为什么拆：目录按「朝代 → 一部书」切，`历代/` 是 haitang 补录的一锅烩，周秦汉晋南北朝隋
唐宋元明清当代全混在 9 个文件里，朝代只记在 `authors/authors.json`。想「取唐诗」得先 join
作者表，这与「一个朝代一个目录」的结构冲突。

规则：
  * 作者朝代（`authors/authors.json`）定归属，与 `dynasties/dynasties.json` 的 name 对齐，
    落成 `唐/诗/poet.tang.json` 这样的文件名前缀，前缀表来自 loader/datas.json 已有的 key。
  * 金、辽、商、上古没有自己的目录，并入它接续的那个朝代目录（辽、金 → 宋，商、上古 → 先秦）。
  * 体裁按形式判：有 rhythmic 或题名首段是词牌 → 词；句长 3~7 字交错 → 词；句子普遍 ≥ 8 字 → 文；
    其余为赋。散文、赋、经史子集篇目一律记 文。
  * 目标书已有同一首正文（同作者、正文相似度 ≥ 0.8）就不搬，避免同一首存两份正文。
"""
import argparse
import collections
import difflib
import glob
import json
import os
import re

from opencc import OpenCC

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
T2S = OpenCC('t2s')
LIDAI = '历代'

# 朝代 → (诗, 词) 的文件前缀；没有前缀的组合不落这一类
PREFIX = {
    '先秦': ('先秦/诗/poet.xianqin', '先秦/词/ci.xianqin'),
    '汉': ('汉/诗/poet.han', '汉/词/ci.han'),
    '三国': ('三国/诗/poet.sanguo', '三国/词/ci.sanguo'),
    '晋': ('晋/诗/poet.jin', '晋/词/ci.jin'),
    '南北朝': ('南北朝/诗/poet.nanbeichao', '南北朝/词/ci.nanbeichao'),
    '隋': ('隋/诗/poet.sui', '隋/词/ci.sui'),
    '唐': ('唐/诗/poet.tang', '唐/词/ci.tang'),
    '五代十国': ('五代十国/诗/poet.wudai', '五代十国/词/ci.wudai'),
    '宋': ('宋/诗/poet.song', '宋/词/ci.song'),
    '元': ('元/诗/poet.yuan', '元/词/ci.yuan'),
    '明': ('明/诗/poet.ming', '明/词/ci.ming'),
    '清': ('清/诗/poet.qing', '清/词/ci.qing'),
    '近现': ('近现/诗/poet.jinxiandai', None),
    '当': ('当/poet.dang.json', '当/ci.dang.json'),
}
# 没有独立目录的朝代，并入它接续的朝代
ALIAS = {'辽': '宋', '金': '宋', '商': '先秦', '上古': '先秦'}

HAN = re.compile(r'[\u3400-\u9fff\U00020000-\U0003ffff]')
SENT = re.compile(r'[，。！？；、：,.!?;:]')

CIPAI = set('''
浣溪沙 如梦令 满江红 念奴娇 水调歌头 临江仙 蝶恋花 沁园春 卜算子 菩萨蛮 清平乐 西江月 鹧鸪天 虞美人 采桑子
忆秦娥 浪淘沙 渔家傲 苏幕遮 定风波 青玉案 江城子 相见欢 长相思 忆江南 梦江南 望江南 生查子 点绛唇 踏莎行 千秋岁
一剪梅 醉花阴 声声慢 扬州慢 桂枝香 六丑 兰陵王 瑞鹤仙 风入松 洞仙歌 天仙子 木兰花 减字木兰花 昭君怨 阮郎归 画堂春
眼儿媚 南乡子 南歌子 好事近 鹊桥仙 夜游宫 祝英台近 摸鱼儿 贺新郎 八声甘州 满庭芳 醉蓬莱 喜迁莺 高阳台 解语花 水龙吟
石州慢 绮罗香 齐天乐 瑞龙吟 宴山亭 曲玉管 木兰花令 甘草子 少年游 秋蕊香 诉衷情 更漏子 调笑令 河传 甘州令 凤栖梧
凤箫吟 千秋岁引 迷神引 竹马子 采莲令 夜半乐 玉蝴蝶 八六子 望海潮 绿头鸭 尉迟杯 应天长 三姝媚 过秦楼 花犯
拜星月慢 关河令 西河 夜飞鹊 感皇恩 天门谣 石州引 望湘人 薄幸 国香 惜分飞 花心动 南浦 夜合花 青门引 天香
金明池 剑器近 安公子 忆旧游 琐窗寒 解连环 宴清都 烛影摇红 六州歌头 汉宫春 丑奴儿 玉楼春 醉落魄 一斛珠 忆王孙
霜天晓角 谒金门 乌夜啼 谢池春 醉垂鞭 离亭燕 一丛花令 破阵子 雨霖铃 秋夜月 巫山一段云 抛球乐 醉花间 三字令
醉公子 河渎神 女冠子 思帝乡 归国遥 荷叶杯 定西番 上行杯 甘州遍 杨柳枝 渔歌子 忆仙姿 醉妆词 花非花 黄莺儿
蟾宫曲 庆东原 天净沙 折桂令 水仙子 山坡羊 寄生草 清江引 醉太平 朝天子 红绣鞋 端正好 新水令 步步娇 雁儿落
得胜令 沽美酒 拔不断 落梅风 迎仙客 塞鸿秋 天香引 竹枝词 江南春 渔父词 潇湘神 章台柳 采莲子 八拍蛮 何满子
醉扶归 醉高歌 四块玉 阅金经 干荷叶 一半儿 青哥儿 小梁州 阳春曲 喜春来 上小楼 石榴花 斗鹌鹑 粉蝶儿 醉春风
红芍药 十二月 尧民歌 耍孩儿 混江龙 油葫芦 天下乐 鹊踏枝
'''.split())
CIPAI_SUFFIX = ('令', '慢', '近', '歌', '行', '谣', '吟', '曲', '乐', '序', '子', '儿', '调', '引', '弄', '操', '叹', '欢', '怨')
TITLE_NOISE = re.compile(r'^(?:其[一二三四五六七八九十]+|[一二三四五六七八九十百]+(?:首|章|阕|闋|绝句|絕句))$')
# 书名以这些字开头时归文（《楚辞·九歌》是骚体，《诗经》的分卷名是标签）
BOOK_STARTS = ('楚辞', '庄子', '老子', '孟子', '论语', '荀子', '韩非子', '墨子', '左传', '国语', '礼记', '周易',
               '尚书', '诗经', '山海经', '淮南子', '列子', '史记', '汉书', '三十六计', '古文观止', '昭明文选',
               '说苑', '新序', '管子', '吕氏春秋', '战国策', '世说新语', '水经注', '文心雕龙', '诗品')
# 贴错作者的经史子集篇目：老子、释迦牟尼、姬昌、子思等人在作者表里没有行，被记到了别人名下
NOT_SHI = re.compile(r'^(?:楚辞|庄子|老子|道德经|论语|孟子|荀子|韩非子|墨子|左传|国语|礼记|周易|尚书|诗经|山海经|'
                     r'淮南子|列子|史记|汉书|三十六计|古文观止|昭明文选|说苑|新序|管子|吕氏春秋|战国策|世说新语|'
                     r'水经注|文心雕龙|诗品|金刚经|坛经|四十二章经)+[·・]')
NOT_SHI_AUTHORS = {'老子', '释迦牟尼', '姬昌', '子思', '曾子', '周公旦', '乐正克', '管仲', '尹文', '公羊高', '穀梁子',
                   '韩非', '商鞅', '吕不韦', '孙武', '鬼谷子', '左丘明', '孟子', '庄子', '荀子', '孔子', '屈原'}
BOOKS = set('''
论语 孟子 左传 幽梦影 国风 小雅 大雅 周颂 商颂 史记 红楼梦 三国演义 水浒传 西游记 周易 人间词话
佛说四十二章经 六祖坛经 楚辞 三十六计 世说新语 中庸 金刚经 声律启蒙 妙法莲华经 笠翁对韵 月令七十二候集解
西厢记 庄子 唐才子传 资治通鉴 山海经 古诗十九首 随园食单 战国策 孙子兵法 圆觉经 地藏经 鬼谷子 国语
菜根谭 传习录 二程遗书 近思录 颜氏家训 文心雕龙 诗品 沧浪诗话 随园诗话 徐霞客游记 陶庵梦忆 西湖梦寻
浮生六记 镜花缘 聊斋志异 儒林外史 长生殿 桃花扇 牡丹亭 乐府诗集 昭明文选 古文观止 诗经 尚书 礼记 大学
荀子 韩非子 墨子 淮南子 列子 孝经 尔雅 说文解字 齐民要术 梦溪笔谈 容斋随笔 困学纪闻 日知录 老子
明夷待访录 文史通义 列仙传 搜神记 洛阳伽蓝记 水经注 中说 意林 群书治要
'''.split())


# ---------------------------------------------------------------- 读写

def load(rel):
    with open(os.path.join(ROOT, rel), encoding='utf-8') as fp:
        return json.load(fp)


def _array_spans(raw):
    open_at = raw.index('[') + 1
    close_at = raw.rindex(']')
    spans, depth, in_str, esc, start, i = [], 0, False, False, None, open_at
    while i < close_at:
        ch = raw[i]
        if in_str:
            if esc:
                esc = False
            elif ch == '\\':
                esc = True
            elif ch == '"':
                in_str = False
        elif ch == '"':
            in_str = True
        elif ch in '{[':
            if depth == 0:
                start = i
            depth += 1
        elif ch in '}]':
            depth -= 1
            if depth == 0:
                spans.append((start, i + 1))
        i += 1
    return open_at, close_at, spans


def _reserialize(rec, text):
    lines = text.split('\n')
    if len(lines) <= 2:
        return json.dumps(rec, ensure_ascii=False, separators=(',', ':'))
    widths, closing, trail = [], None, set()
    for line in lines:
        st = line.strip()
        if not st:
            continue
        pad = len(line) - len(line.lstrip(' '))
        if st == '}':
            closing = pad
        elif pad not in widths:
            widths.append(pad)
        if line != line.rstrip(' '):
            trail.add(st)
    out = ['{']
    for line in json.dumps(rec, ensure_ascii=False, indent=2).split('\n')[1:]:
        st = line.strip()
        if st == '}':
            out.append(' ' * (closing or 0) + st)
            continue
        depth = (len(line) - len(line.lstrip(' '))) // 2
        out.append(' ' * widths[min(depth, len(widths) - 1)] + st + (' ' if st in trail else ''))
    return '\n'.join(out)


def append(rel, recs):
    """把记录追加到已有总集末尾，原有记录的字节不动。"""
    path = os.path.join(ROOT, rel)
    with open(path, encoding='utf-8') as fp:
        raw = fp.read()
    open_at, close_at, spans = _array_spans(raw)
    if not spans:
        raise ValueError(f'{rel} 不是非空顶层数组')
    template = raw[spans[-1][0]:spans[-1][1]]
    tail = raw[spans[-1][1]:close_at].rstrip()
    sep = tail.strip() if tail.strip() else ','
    body = sep.join(['', *(_reserialize(r, template) for r in recs)])
    text = raw[:spans[-1][1]] + body + raw[spans[-1][1]:]
    json.loads(text)
    with open(path, 'w', encoding='utf-8') as fp:
        fp.write(text)


def dump(rel, data):
    path = os.path.join(ROOT, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as fp:
        json.dump(data, fp, ensure_ascii=False, indent=2)
        fp.write('\n')


def hz(s):
    return ''.join(HAN.findall(T2S.convert(s or ''))).strip()


def sentences(rec):
    return [hz(s) for s in SENT.split(''.join(rec.get('paragraphs') or [])) if len(hz(s)) >= 2]


# ---------------------------------------------------------------- 体裁判定

def is_pai(rec):
    parts = (rec.get('title') or rec.get('rhythmic') or '').split('·')
    if len(parts) < 2:
        return False
    head = parts[0].strip()
    if TITLE_NOISE.match(head):
        return False
    if head in CIPAI:
        return True
    return 2 <= len(head) <= 6 and head.endswith(CIPAI_SUFFIX)


def genre(rec):
    """'诗' / '词' / '文'。只看形式：赋、文用什么形式都判得出，诗与词只在词牌字段/题名下分。"""
    title = rec.get('title') or rec.get('rhythmic') or ''
    if title.split('·')[0].strip() in BOOKS or NOT_SHI.match(title) or hz(rec.get('author')) in NOT_SHI_AUTHORS:
        return '文'
    ss = sentences(rec)
    if ss:
        counts = collections.Counter(len(s) for s in ss).most_common(2)
        if counts[0][0] >= 8:                   # 长句为主：赋、骈文、散文
            return '文'
    if rec.get('rhythmic') or is_pai(rec):
        return '词'
    return '诗'


# ---------------------------------------------------------------- 朝代归属

def dynasty_index():
    """作者 → 朝代。同名多行（作者表里「无名氏」有 9 行，`？年` 出生）按「有确切朝代的优先」收敛，
    绝不能取最后一行——`dict` 推导式的后写覆盖前写，会让「无名氏」落到任意一个朝代上去，
    2026-10 就是这样把 457 条先秦两汉的无名氏作品全判给了隋。"""
    with open(os.path.join(ROOT, 'authors/authors.json'), encoding='utf-8') as fp:
        rows = json.load(fp)
    seen = collections.defaultdict(list)
    for a in rows:
        seen[T2S.convert(a['name'])].append(T2S.convert(a['dynasty']))
    return {name: pick_dynasty(ds) for name, ds in seen.items()}


def pick_dynasty(ds):
    """一个作者记了几个朝代时取哪个：不同朝代各自成立（作者归属异说），取最早的；
    同一作者表里 9 行「无名氏」这种情况是缺数据，不是异说，一律判为「朝代不明」。"""
    uniq = list(dict.fromkeys(ds))
    if len(uniq) == 1:
        return uniq[0]
    return None


def year_of(rec):
    """从 birth_year / death_year 这类字符串里取年份，取不到就是 None。
    原先的写法把 `？年`、`?`、`未知年` 都当成数字参与比较，`？？` 落到任何一个区间里都成立。"""
    for key in ('birth_year', 'death_year'):
        m = re.search(r'-?\d{1,4}', str(rec.get(key) or ''))
        if m:
            return int(m.group())
    return None


def lidai_records():
    out = []
    for rel in sorted(glob.glob(os.path.join(ROOT, LIDAI, '*.json'))):
        rel = os.path.relpath(rel, ROOT)
        for i, rec in enumerate(load(rel)):
            out.append([rel, i, rec])
    return out


def body_index(corpus):
    index = collections.defaultdict(list)
    for j, rec in enumerate(corpus):
        index[hz(''.join(rec.get('paragraphs') or ''))[:10]].append(j)
    return index


def dedupe(rec, corpus, index, used):
    body = hz(''.join(rec.get('paragraphs') or []))
    if not body:
        return None
    author = hz(rec.get('author'))
    for j in index.get(body[:10], ()):
        if j in used:
            continue
        other = corpus[j]
        if hz(other.get('author')) != author:      # 作者不同一律两存
            continue
        text = hz(''.join(other.get('paragraphs') or []))
        if abs(len(text) - len(body)) <= max(4, 0.3 * len(body)) and \
                difflib.SequenceMatcher(None, body, text, autojunk=False).ratio() >= 0.8:
            return j
    return None


def plan():
    dyn = dynasty_index()
    existing = {}
    for rec_path in {p for pair in PREFIX.values() for p in pair if p}:
        rel = f'{rec_path}.json'
        if os.path.exists(os.path.join(ROOT, rel)):
            existing[rel] = load(rel)
    indexes = {rel: body_index(v) for rel, v in existing.items()}
    used = collections.defaultdict(set)

    moved = collections.defaultdict(list)      # rel -> [rec]
    log = []
    for rel, i, rec in lidai_records():
        d = dyn.get(T2S.convert(rec.get('author')))
        if not d:
            # 作者表里查不到，或同名的几行写着互相矛盾的朝代（「无名氏」有 13 行）：
            # 退回记录自带的 dynasty 字段，没有就留在原处
            d = T2S.convert(str(rec.get('dynasty') or ''))
            if d and d not in PREFIX:
                d = ALIAS.get(d, d)
        g = genre(rec)
        if d not in PREFIX:
            log.append([rel, str(i), rec.get('author', ''), rec.get('title') or rec.get('rhythmic') or '',
                        d or '(无)', g, '', '朝代不明，留在原处'])
            continue
        prefix = PREFIX[d][0 if g != '词' else 1]
        assert prefix, (d, g)
        if g == '文':                          # 文只有一部：poet.* 是「诗列」，文的正文也放这里
            prefix = PREFIX[d][0]
        target = prefix if prefix.endswith('.json') else f'{prefix}.json'
        rec.pop('dynasty', None)               # 朝代由所在目录决定，字段不重复存
        dup = dedupe(rec, existing[target], indexes[target], used[target]) if target in existing else None
        if dup is not None:
            used[target].add(dup)
            log.append([rel, str(i), rec.get('author', ''), rec.get('title') or rec.get('rhythmic') or '',
                        d, g, f'{target}#{dup}', '该书已收同一首，不重复搬'])
            continue
        moved[target].append(rec)
        log.append([rel, str(i), rec.get('author', ''), rec.get('title') or rec.get('rhythmic') or '',
                    d, g, target, ''])
    return moved, log


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--apply', action='store_true')
    args = ap.parse_args()

    if not os.path.isdir(os.path.join(ROOT, LIDAI)):
        raise SystemExit('历代/ 已经不在了：已经拆过')

    moved, log = plan()
    c = collections.Counter((r[4], r[5]) for r in log if r[6] and not r[7])
    print('拆出：')
    for k, n in sorted(c.items()):
        print(f'  {k[0] or "(无)"}{k[1]}: {n}')
    d = collections.Counter(r[6] for r in log if r[7] == '该书已收同一首，不重复搬')
    if d:
        print('已收未搬：', dict(d))
    odd = [r for r in log if r[7].startswith('朝代不明')]
    if odd:
        print('留在原处（需人工判）：')
        for r in odd:
            print('  ' + ' | '.join(r))
    tot = sum(len(v) for v in moved.values())
    print(f'合计搬 {tot} 条 → {len(moved)} 个文件')
    if not args.apply:
        return

    for rel, recs in sorted(moved.items()):
        if os.path.exists(os.path.join(ROOT, rel)):
            append(rel, recs)
        else:
            dump(rel, recs)
    for rel in sorted(glob.glob(os.path.join(ROOT, LIDAI, '*.json'))):
        os.remove(rel)
    os.rmdir(os.path.join(ROOT, LIDAI))

    with open(os.path.join(ROOT, 'docs/历代拆分.tsv'), 'w', encoding='utf-8', newline='') as fp:
        fp.write('原文件\t记录\t作者\t题名\t朝代\t体裁\t去向\t说明\n')
        fp.writelines('\t'.join(r) + '\n' for r in log)


if __name__ == '__main__':
    main()
