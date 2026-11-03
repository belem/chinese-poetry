# -*- coding: utf-8 -*-
"""卷四十七（頌、贊）七篇：正文取《昭明文選》六臣注本（識典古籍 SBCK300）卷四十七的白文，
段落照底本自然段，字形归一到本库用字。

用法（抓取要点见 docs/昭明文选重建.md）：
  1. 把识典 SSR 缓存放到 $ZHAOMING_SD（默认 /tmp/zhaoming-sd），一节一文件 <章节id>.json
  2. python3 scripts/anthology/zhaoming_gen47.py      # 只打印，不写文件
"""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import zhaoming_sd as _sd
import zhaoming_variant as V

def body_of(v, first, last):
    """取 [first, last] 之间的识典正文页（末页 inclusive）"""
    out, started = [], False
    for pp in _sd.load(v):
        if pp['id'] == first:
            started = True
        if started:
            b = _sd.body(pp).strip()
            if b and not b.endswith('卷第四十七'):
                out.append(V.norm(b))
        if pp['id'] == last:
            break
    return out

SPEC = [
 ('颂', '聖主得賢臣頌', '王子淵', '1j73qwm1jvaxx_578', 'SBCK300_1_3716', 'SBCK300_1_3719'),
 ('颂', '趙充國頌', '揚子雲', '1j73qwm41vv3v_579', 'SBCK300_1_3723', 'SBCK300_1_3723'),
 ('颂', '出師頌', '史孝山', '1j73qwm4qovnh_580', 'SBCK300_1_3727', 'SBCK300_1_3727'),
 ('颂', '酒德頌', '劉伯倫', '1j73qwm5n80mz_581', 'SBCK300_1_3730', 'SBCK300_1_3730'),
 ('颂', '漢高祖功臣頌', '陸士衡', '1j73qwm69or3s_582', 'SBCK300_1_3733', 'SBCK300_1_3761'),
 ('赞', '東方朔畫贊', '夏侯孝若', '1j73qwmgjbu48_583', 'SBCK300_1_3765', 'SBCK300_1_3771'),
 ('赞', '三國名臣序贊', '袁彥伯', '1j73qwmm7znek_584', 'SBCK300_1_3775', 'SBCK300_1_3804'),
]
FILE = {'颂': '颂.json', '赞': '赞.json'}

# 六臣本 SSR 脱字/误断，依 reference/昭明文選4.txt 底本补正（见 docs/昭明文选重建.md）
FIX = {
 '出師頌': [('易。零不顺，夷遘逆', '易。西零不顺，东夷遘逆')],
 '漢高祖功臣頌': [('梁王昌彭越', '梁王昌邑彭越'), ('魏传宽', '魏傅宽'),
                  ('与定天下。安社稷者也', '与定天下安社稷者也')],
}

OUT = '汇编/昭明文选'

def entries():
    data = {}
    for fn, title, author, v, a, b in SPEC:
        ps = body_of(v, a, b)
        for old, new in FIX.get(title, ()):
            ps = [p.replace(old, new) for p in ps]
        data.setdefault(fn, []).append({'title': title, 'author': author, 'paragraphs': ps})
    return data

def write():
    for fn, items in entries().items():
        p = os.path.join(OUT, FILE[fn])
        old = {it['title']: it for it in json.load(open(p, encoding='utf-8'))}
        out = []
        for it in items:
            o = {'author': it['author'], 'paragraphs': it['paragraphs'], 'title': it['title']}
            if old.get(it['title'], {}).get('id'):
                o['id'] = old[it['title']]['id']
            out.append(o)
        json.dump(out, open(p, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
        open(p, 'a', encoding='utf-8').write('\n')
        print('wrote', p, len(out))

if __name__ == '__main__':
    for fn, items in entries().items():
        for it in items:
            print('%-4s %-9s %-5s %2d 段 %5d 字' % (fn, it['title'], it['author'],
                                                len(it['paragraphs']),
                                                sum(len(x) for x in it['paragraphs'])))
