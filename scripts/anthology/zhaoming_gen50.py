# -*- coding: utf-8 -*-
"""卷五十至六十：按「底本定段、六臣本定字句」重出《文選》各篇，写入 汇编/昭明文选/。

用法（抓取要点见 docs/昭明文选重建.md）：
  1. 把識典 SBCK300 卷五一至六十的章节页 DOM 块存到 $ZHAOMING_SD（一章一文件，
     `{"tag": "p", "t": "..."}`），并把抓取顺序存成 `$ZHAOMING_SD/order.json`；
  2. python3 scripts/anthology/zhaoming_gen50.py           # 只打印对勘报告
     python3 scripts/anthology/zhaoming_gen50.py --apply   # 写回 JSON
"""
import json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import zhaoming_align as AL
import zhaoming_build2 as B2
import zhaoming_variant as V

OUT = os.path.join(HERE, '..', '..', '汇编', '昭明文选')

# 底本篇题 → (库内文件, 库内篇题, 作者)。篇题与作者照《文選》目录（庫内旧有心裁）。
SPEC = {
    51: [('过秦论', '论·论一.json', '過秦論', '賈長沙'),
         ('非有先生论', '论·论一.json', '非有先生論', '東方曼倩'),
         ('四子讲德论（并序）', '论·论一.json', '四子講德論', '王子淵')],
    52: [('王命论', '论·论二.json', '王命論', '班叔皮'),
         ('典论论文', '论·论二.json', '典論論文', '魏文帝'),
         ('六代论', '论·论二.json', '六代論', '曹元首'),
         ('博弈论', '论·论二.json', '博弈論', '韋弘嗣')],
    53: [('养生论', '论·论三.json', '養生論', '嵇叔夜'),
         ('运命论', '论·论三.json', '運命論', '李蕭遠'),
         ('辩亡论上下二首', '论·论三.json', '辯亡論上', '陸士衡'),
         ('辩亡论下', '论·论三.json', '辯亡論下', '陸士衡')],
    54: [('五等论', '论·论四.json', '五等諸侯論', '陸士衡'),
         ('辩命论', '论·论四.json', '辯命論', '劉孝標')],
    55: [('广绝交论', '论·论五.json', '廣絕交論', '劉孝標'),
         ('演连珠五十首', '连珠.json', '演連珠五十首', '陸士衡')],
    56: [('女史箴', '箴.json', '女史箴', '張茂先'),
         ('封燕然山铭', '铭.json', '封燕然山銘', '班孟堅'),
         ('座右铭', '铭.json', '座右銘', '崔子玉'),
         ('剑阁铭', '铭.json', '劍閣銘', '張孟陽'),
         ('石阙铭一首', '铭.json', '石闕銘', '陸佐公'),
         ('新刻漏铭（并序）', '铭.json', '新刻漏銘', '陸佐公'),
         ('王仲宣诔（并序）', '诔.json', '王仲宣誄', '曹子建'),
         ('杨荆州诔（并序）', '诔.json', '楊荊州誄', '潘安仁'),
         ('杨仲武诔（并序）', '诔.json', '楊仲武誄', '潘安仁')],
    57: [('夏侯常侍诔（并序）', '诔.json', '夏侯常侍誄', '潘安仁'),
         ('马汧督诔', '诔.json', '馬汧督誄', '潘安仁'),
         ('阳给事诔（并序）', '诔.json', '陽給事誄', '顏延年'),
         ('陶徵士诔（并序）', '诔.json', '陶徵士誄', '顏延年'),
         ('宋孝武宣贵妃诔一首', '诔.json', '宋孝武宣貴妃誄', '謝希逸'),
         ('哀永逝文一首', '哀.json', '哀永逝文', '潘安仁')],
    58: [('宋文皇帝元皇后哀策文', '哀.json', '宋文元皇后哀策文', '顏延年'),
         ('齐敬皇后哀策文', '哀.json', '齊敬皇后哀策文', '謝玄暉'),
         ('郭有道碑文（并序）', '碑文.json', '郭有道碑文', '蔡伯喈'),
         ('陈太丘碑文（并序）', '碑文.json', '陳太丘碑文', '蔡伯喈'),
         ('褚渊碑文（并序）', '碑文.json', '褚淵碑文', '王仲寶')],
    59: [('头纮寺碑文', '碑文.json', '頭陀寺碑文', '王簡栖'),
         ('齐故安陆昭王碑文一首', '碑文.json', '齊故安陸昭王碑文', '沈休文')],
    60: [('齐竟陵文宣王行状', '行状.json', '齊竟陵文宣王行狀', '任彥昇'),
         ('吊屈原文（并序）', '吊文.json', '弔屈原文', '賈長沙'),
         ('吊魏武帝文（并序）', '吊文.json', '弔魏武帝文', '陸士衡'),
         ('祭古冢文（并序）', '祭文.json', '祭古冢文', '謝惠連'),
         ('祭屈原文', '祭文.json', '祭屈原文', '顏延年'),
         ('祭颜光禄文一首', '祭文.json', '祭顏光祿文', '王僧達')],
}





def keep_form(s):
    """只把旧刻异体写成标准繁体（丗→世、髙→高），繁简不动。"""
    return ''.join(V.VAR.get(ch, ch) for ch in s)


def normalize(paras):
    """落库前的最后一道：统一的句读与全角引号。

    - 六臣本（DOM）的引号是 `“…”` 但常常不成对，成对补齐；`「」` 不改；
    - `：` 后面跟引语时不加引号（本库其余篇目照原书只留冒号）。
    """
    out = []
    for p in paras:
        t = p.strip()
        q = t.count('“') - t.count('”')
        if q > 0:
            t += '”' * q
        elif q < 0:
            t = '“' * (-q) + t
        out.append(t)
    return out


def entries():
    """{文件名: [条目...]}，条目按 SPEC 的顺序排。"""
    files = {}
    for vol, specs in SPEC.items():
        built = {it['ref_title']: it for it in B2.build_volume(vol)}
        for ref_title, fn, ktitle, author in specs:
            it = built.get(ref_title)
            if it is None:
                raise KeyError('卷%d 缺篇：%s' % (vol, ref_title))
            # 本库《昭明文选》其余 89 个文件都用繁体（`賦者古詩之流也`、`與君生別離`），
            # 这批也照旧用繁体：只归一异体字形（髙/曺/𤣥…），不做繁简转换。
            paras = normalize([keep_form(x) for x in B2.final_text(it['rows'])])
            paras = [p for p in paras if p]
            files.setdefault(fn, []).append({'title': ktitle, 'author': author, 'paras': paras})
    return files


def report():
    for vol, specs in SPEC.items():
        for it in B2.build_volume(vol):
            n = sum(len(AL.flat(r[0])) for r in it['rows'])
            use = sum(1 for r in it['rows'] if r[2])
            print('%d %-22s <- %-20s %2d段 %5d字  改用底本 %d 段'
                  % (vol, it['ref_title'], it['sd_title'] or '（无）', len(it['rows']), n, use))


def write():
    for fn, items in entries().items():
        p = os.path.join(OUT, fn)
        old = {}
        if os.path.exists(p):
            old = {x['title']: x for x in json.load(open(p, encoding='utf-8'))}
        out = []
        for it in items:
            o = {'author': it['author'], 'paragraphs': it['paras'], 'title': it['title']}
            if old.get(it['title'], {}).get('id'):
                o['id'] = old[it['title']]['id']
            out.append(o)
        json.dump(out, open(p, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
        open(p, 'a', encoding='utf-8').write('\n')
        print('wrote', p, len(out))


if __name__ == '__main__':
    if '--apply' in sys.argv:
        write()
    else:
        report()


