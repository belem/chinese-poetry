#!/usr/bin/env python3
"""把 `历代/` 里明清作者的作品按朝代、体裁拆成独立总集，并把课本选目归位。

  python3 scripts/split_dynasty.py            # 预演：打印分类统计与归位报告
  python3 scripts/split_dynasty.py --apply    # 写回数据，生成 docs/历代拆分.tsv

为什么拆：目录按「一部书」切，`历代/` 是 haitang 补录的一锅烩（5607 条，朝代散在作者
索引里，每条只有 `sources: ["haitang"]`）。明清诗人有 2436 条挤在这里，一首诗想按朝代
取就得先 join 作者表。拆出三组书，与「一部书一个目录」的约定一致：

  明代/诗/poet.ming.json       明人诗
  明代/词/ci.ming.json         明人词、散曲小令
  清代/诗/poet.qing.json       清人诗
  清代/词/ci.qing.json         清人词（与 清代/词/古诗源·清词.json 同目录并列）

元人作品已经有一份更大、更完整的《元曲》总集（11415 条），历代里的 324 条元人作品
留在原处，不复制——避免同一批作品被拆成两部书。「宋」同样留在原处：宋诗宋词已各有
总集，历代里那 121 条是对勘用的补录。

归属按作者朝代（`authors/authors.json`）定，体裁按「记录体裁 → 句长」判：
`rhythmic` 字段、题名首段是词牌/曲牌 → 词曲；句长 3~7 字交错 → 词；句式整齐 → 诗；
著名子书的篇目（史记、论语、红楼梦回目……）归文。这四条只看形式，不看内容。

另外把 `近现代诗/` 里课本选录的明清作品并回上面几部书（`tags: ["课本"]`），
余下的近现代作品拆进 `近现代诗/现代诗.json` 与 `近现代诗/当代诗词.json`。
"""
import argparse
import collections
import copy
import difflib
import glob
import json
import os
import re

from opencc import OpenCC

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
T2S = OpenCC('t2s')

LIDAI = '历代'
YUANQU = '元代/元曲/yuanqu.json'
TARGET_DYNASTIES = ('明', '清')
TARGETS = {
    ('明', '诗'): '明代/诗/poet.ming.json',
    ('明', '词'): '明代/词/ci.ming.json',
    ('清', '诗'): '清代/诗/poet.qing.json',
    ('清', '词'): '清代/词/ci.qing.json',
}
NEAR_MODERN = '近现代诗'
RECENT = '近现代诗/现代诗.json'      # 1919 以后、无平仄格律约束的作品
CONTEMPORARY = '近现代诗/当代诗词.json'  # 1919 年以后仍用诗、词、曲体的作品

HAN = re.compile(r'[\u3400-\u9fff\U00020000-\U0003ffff]')
SENT = re.compile(r'[，。！？；、：,.!?;:]')

# 词牌、曲牌：题名「<词牌>・<题目>」时首段是牌名
CIPAI = set('''
浣溪沙 如梦令 满江红 念奴娇 水调歌头 临江仙 蝶恋花 沁园春 卜算子 菩萨蛮 清平乐 西江月 鹧鸪天 虞美人 采桑子
忆秦娥 浪淘沙 渔家傲 苏幕遮 定风波 青玉案 江城子 相见欢 长相思 忆江南 梦江南 望江南 生查子 点绛唇 踏莎行 千秋岁
一剪梅 醉花阴 声声慢 扬州慢 桂枝香 六丑 兰陵王 瑞鹤仙 风入松 洞仙歌 天仙子 木兰花 减字木兰花 昭君怨 阮郎归 画堂春
眼儿媚 南乡子 南歌子 好事近 鹊桥仙 夜游宫 祝英台近 摸鱼儿 贺新郎 八声甘州 满庭芳 醉蓬莱 喜迁莺 高阳台 解语花 水龙吟
石州慢 绮罗香 齐天乐 瑞龙吟 宴山亭 曲玉管 木兰花令 甘草子 少年游 秋蕊香 诉衷情 诉衷情令 添字浣溪沙 更漏子 调笑令 河传
甘州令 婆罗门令 凤栖梧 凤箫吟 千秋岁引 迷神引 竹马子 采莲令 夜半乐 玉蝴蝶 八六子 望海潮 绿头鸭 尉迟杯 应天长 三姝媚
过秦楼 花犯 拜星月慢 关河令 西河 夜飞鹊 感皇恩 天门谣 石州引 望湘人 薄幸 国香 惜分飞 惜黄花慢 花心动 南浦 解蹀躞 夜合花
青门引 天香 金明池 剑器近 安公子 卜算子慢 忆旧游 琐窗寒 解连环 大有 宴清都 烛影摇红 法曲献仙音 六州歌头 汉宫春 丑奴儿
玉楼春 醉落魄 一斛珠 忆王孙 霜天晓角 谒金门 乌夜啼 谢池春 醉垂鞭 离亭燕 一丛花令 破阵子 雨霖铃 戚氏 浪淘沙慢 秋夜月
巫山一段云 抛球乐 醉花间 三字令 醉公子 河渎神 女冠子 思帝乡 归国遥 荷叶杯 定西番 上行杯 甘州遍 杨柳枝 渔歌子 忆仙姿
醉妆词 花非花 黄莺儿 蟾宫曲 庆东原 天净沙 折桂令 水仙子 山坡羊 寄生草 清江引 醉太平 朝天子 红绣鞋 端正好 新水令 步步娇
雁儿落 得胜令 沽美酒 快活年 拔不断 落梅风 迎仙客 塞鸿秋 天香引 谒金门 落梅风 竹枝词 江南春 渔父词 潇湘神 章台柳
采莲子 八拍蛮 何满子 醉扶归 醉高歌 四块玉 阅金经 干荷叶 一半儿 青哥儿 小梁州 阳春曲 喜春来 上小楼 满庭芳 石榴花
斗鹌鹑 粉蝶儿 醉春风 迎仙客 红芍药 十二月 尧民歌 耍孩儿 煞尾 尾 幺篇 赚煞 混江龙 油葫芦 天下乐 鹊踏枝 寄生草
'''.split())
CIPAI_SUFFIX = ('令', '慢', '近', '歌', '行', '谣', '吟', '曲', '乐', '序', '子', '儿', '调', '引', '弄', '操', '叹', '欢', '怨')
# 「其一」「二首」这类题名分段不是词牌
TITLE_NOISE = re.compile(r'^(?:其[一二三四五六七八九十]+|[一二三四五六七八九十百]+(?:首|章|阕|闋|绝句|絕句))$')
# 成书的子书、小说、总集：篇目归文，不归诗
BOOKS = set('''
论语 孟子 左传 幽梦影 国风 小雅 大雅 周颂 商颂 史记 红楼梦 三国演义 水浒传 西游记 周易 人间词话
佛说四十二章经 六祖坛经 楚辞 三十六计 世说新语 中庸 金刚经 声律启蒙 妙法莲华经 笠翁对韵 月令七十二候集解
西厢记 庄子 唐才子传 资治通鉴 山海经 古诗十九首 随园食单 战国策 孙子兵法 圆觉经 地藏经 鬼谷子 国语
菜根谭 传习录 二程遗书 近思录 颜氏家训 文心雕龙 诗品 沧浪诗话 随园诗话 徐霞客游记 陶庵梦忆 西湖梦寻
浮生六记 镜花缘 聊斋志异 儒林外史 长生殿 桃花扇 牡丹亭 乐府诗集 昭明文选 古文观止 诗经 尚书 礼记 大学
中庸 荀子 韩非子 墨子 淮南子 列子 孝经 尔雅 说文解字 齐民要术 梦溪笔谈 容斋随笔 困学纪闻 日知录
明夷待访录 文史通义 老子 庄子 列仙传 搜神记 世说新语 洛阳伽蓝记 水经注 颜氏家训 中说 意林 群书治要
'''.split())


# ---------------------------------------------------------------- 读写

def load(rel):
    with open(os.path.join(ROOT, rel), encoding='utf-8') as fp:
        return json.load(fp)


def _array_spans(raw):
    """顶层数组每条记录的 (起, 止)，用来只替换动过的记录。"""
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
    """照原文这条记录的缩进宽度与行尾空格重新序列化（与 merge_selections.py 同一套办法）。"""
    lines = text.split('\n')
    if len(lines) <= 2:                      # 单行紧凑格式
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
    """整份重写，保持与现有文件同样的两层缩进与 ensure_ascii=False。"""
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
    """题名首段是词牌 / 曲牌。"""
    parts = (rec.get('title') or '').split('·')
    if len(parts) < 2:
        return False
    head = parts[0].strip()
    if TITLE_NOISE.match(head):
        return False
    if head in CIPAI:
        return True
    return 2 <= len(head) <= 6 and head.endswith(CIPAI_SUFFIX)


def genre(rec):
    """'文' / '词' / '诗'。只看形式：题名、字段、句长。"""
    if (rec.get('title') or '').split('·')[0].strip() in BOOKS:
        return '文'
    if rec.get('rhythmic') or is_pai(rec):
        return '词'
    ss = sentences(rec)
    if not ss:
        return '诗'
    counts = collections.Counter(len(s) for s in ss).most_common(2)
    if counts[0][0] >= 8:                       # 长句为主：赋、骈文
        return '文'
    if len(counts) >= 2 and counts[0][0] <= 7 and counts[0][1] < len(ss) * 0.8:
        return '词'                              # 三言到七言交错，是词的长短句
    return '诗'


# ---------------------------------------------------------------- 朝代归属

def dynasty_index():
    with open(os.path.join(ROOT, 'authors/authors.json'), encoding='utf-8') as fp:
        return {T2S.convert(a['name']): T2S.convert(a['dynasty']) for a in json.load(fp)}


def lidai_records():
    out = []
    for rel in sorted(glob.glob(os.path.join(ROOT, LIDAI, '*.json'))):
        rel = os.path.relpath(rel, ROOT)
        for i, rec in enumerate(load(rel)):
            out.append([rel, i, rec])
    return out


def dedupe(rec, corpus, index, used):
    """正文前 10 字相同且相似度 ≥ 0.8 视为同一首，返回已收记录的下标。"""
    body = hz(''.join(rec.get('paragraphs') or []))
    if not body:
        return None
    for j in index.get(body[:10], ()):
        if j in used:
            continue
        other = hz(''.join(corpus[j].get('paragraphs') or []))
        if abs(len(other) - len(body)) <= max(4, 0.3 * len(body)) and \
                difflib.SequenceMatcher(None, body, other, autojunk=False).ratio() >= 0.8:
            return j
    return None


def body_index(corpus):
    index = collections.defaultdict(list)
    for j, rec in enumerate(corpus):
        index[hz(''.join(rec.get('paragraphs') or []))[:10]].append(j)
    return index


def split(dyn, existing=None):
    """历代/ 拆成四组：明、清（明细分诗/词）、元人并入《元曲》，其余不动。"""
    kept = collections.defaultdict(list)         # rel -> [rec]
    moved = collections.defaultdict(list)        # target -> [rec]
    existing = existing or {}
    indexes = {t: body_index(v) for t, v in existing.items()}
    used = collections.defaultdict(set)
    log = []
    for rel, i, rec in lidai_records():
        d = dyn.get(T2S.convert(rec.get('author')), '')
        g = genre(rec)
        target = None
        if d in TARGET_DYNASTIES and g in ('诗', '词'):
            target = TARGETS[(d, g)]
        elif d == '元' and g in ('诗', '词'):          # 《元曲》是元人作品的唯一总集
            target = YUANQU
        if target:
            dup = dedupe(rec, existing[target], indexes[target], used[target]) if target in existing else None
            if dup is not None:
                used[target].add(dup)
                log.append([rel, str(i), rec.get('author'), rec.get('title') or rec.get('rhythmic') or '',
                            d, g, f'{target}#{dup}', '总集已收，不重复搬'])
                continue
            rec.pop('dynasty', None)                 # 朝代由所在的书决定，字段不重复存
            moved[target].append(rec)
            log.append([rel, str(i), rec.get('author'), rec.get('title') or rec.get('rhythmic') or '',
                        d, g, target, ''])
        else:
            kept[rel].append(rec)
    return kept, moved, log


# ---------------------------------------------------------------- 选本归位

def near_modern(corpora):
    """近现代诗/ 的两份文件：明清作品并回总集，其余按体裁拆成现代 / 当代。"""
    recs = []
    for name in ('元明清詩.json', '近现代诗.json'):
        rel = f'{NEAR_MODERN}/{name}'
        for i, rec in enumerate(load(rel)):
            recs.append([rel, i, rec])
    seen, uniq = set(), []
    for rel, i, rec in recs:                       # 三首在两份文件里各有一份
        key = (hz(rec.get('author')), hz(rec.get('title')), hz(''.join(rec.get('paragraphs'))))
        if key in seen:
            continue
        seen.add(key)
        uniq.append([rel, i, rec])

    index = collections.defaultdict(list)
    for target, data in corpora.items():
        for j, rec in enumerate(data):
            body = hz(''.join(rec.get('paragraphs')))
            index[body[:8]].append((target, j, body))

    log, rest = [], []
    for rel, i, rec in uniq:
        body = hz(''.join(rec.get('paragraphs')))
        author = hz(rec.get('author'))
        hits = [c for c in index.get(body[:8], []) if abs(len(c[2]) - len(body)) <= max(4, 0.3 * len(body))]
        best = None
        for target, j, cand in hits:
            other = corpora[target][j]
            if hz(other.get('author')) != author:   # 作者不同一律两存
                continue
            r = difflib.SequenceMatcher(None, body, cand, autojunk=False).ratio()
            if r >= 0.6 and (best is None or r > best[0]):
                best = (r, target, j)
        if best:
            r, target, j = best
            other = corpora[target][j]
            other['tags'] = list(dict.fromkeys((other.get('tags') or []) + ['课本']))
            log.append([rel, f'{author}《{rec.get("title")}》', f'{target}#{j}',
                        f'{other.get("author")}《{other.get("title") or other.get("rhythmic")}》',
                        '', '诗', '并入 tags 课本', '正文一致' if r > 0.95 else '正文有异文'])
        else:
            log.append([rel, f'{author}《{rec.get("title")}》', '', '', '', ''
                        , RECENT if not is_classical(rec) else CONTEMPORARY, '从选本目录拆出'])
            rest.append(rec)
    return log, rest


def is_classical(rec):
    """课本选目之外的近现代作品：诗、词、曲体 → 当代诗词；自由体 → 现代诗。"""
    return bool(rec.get('rhythmic') or is_pai(rec)) or genre(rec) in ('诗', '词')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--apply', action='store_true')
    args = ap.parse_args()

    outputs = list(TARGETS.values()) + [YUANQU, RECENT, CONTEMPORARY]
    if all(os.path.exists(os.path.join(ROOT, t)) for t in outputs) \
            and not os.path.exists(os.path.join(ROOT, NEAR_MODERN, '近现代诗.json')):
        raise SystemExit('已经拆过了。要重跑：git checkout -- 历代 近现代诗 元代 && '
                         'rm -rf 明代 清代/诗 清代/词/ci.qing.json 近现代诗/现代诗.json 近现代诗/当代诗词.json')

    dyn = dynasty_index()
    kept, moved, log = split(dyn, {YUANQU: load(YUANQU)})

    corpora = {t: moved[t] for t in moved}
    near_log, rest = near_modern(corpora)
    log += near_log

    c = collections.Counter((r[4], r[5]) for r in log if len(r) > 7 and not r[7])
    print('拆出：')
    for k, n in sorted(c.items()):
        print(f'  {k[0]}{k[1]}: {n}')
    print('留在历代/：')
    for rel in sorted(kept):
        print(f'  {rel}: {len(load(rel))} → {len(kept[rel])}')
    print('近现代诗/ 归位：')
    for r in near_log:
        print('  ' + ' | '.join(x for x in r if x))

    recent = [r for r in rest if not is_classical(r)]
    contemp = [r for r in rest if is_classical(r)]
    print(f'近现代诗/ 余 {len(rest)} 首 → {RECENT} {len(recent)}，{CONTEMPORARY} {len(contemp)}')
    if not args.apply:
        return

    for rel, recs in kept.items():
        dump(rel, recs)
    for target, recs in corpora.items():
        if not recs:
            continue
        if os.path.exists(os.path.join(ROOT, target)):
            append(target, recs)                 # 已有总集：追加，原记录字节不动
        else:
            dump(target, recs)
    dump(RECENT, recent)
    dump(CONTEMPORARY, contemp)
    os.remove(os.path.join(ROOT, NEAR_MODERN, '元明清詩.json'))
    os.remove(os.path.join(ROOT, NEAR_MODERN, '近现代诗.json'))

    with open(os.path.join(ROOT, 'docs/历代拆分.tsv'), 'w', encoding='utf-8', newline='') as fp:
        fp.write('原文件\t记录\t作者\t题名\t朝代\t体裁\t去向\t说明\n')
        fp.writelines('\t'.join(r) + '\n' for r in log)


if __name__ == '__main__':
    main()
