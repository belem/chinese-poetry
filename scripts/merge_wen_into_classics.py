#!/usr/bin/env python3
"""把 先秦/文 里与 先秦/论语、先秦/四书五经 同一部书的条目并回去，再删掉这两个专书目录。

reorg_xianqin.py 把 poet.xianqin 里的「文」分派到 先秦/文/<书>.json，但《论语》《孟子》
《大学》《中庸》本来就是仓库已有的专书（先秦/论语/lunyu.json、先秦/四书五经/*.json），
分派时按「正文逐字已在专书里就删」处理，剩下的异文/节选又写了一份到 先秦/文/。

专书目录自己也有问题：四书五经/ 只收了 孟子、大学、中庸 三本，名不符实；
daxue.json、zhongyong.json 是单章 dict，不是列表，loader 读不了。

本脚本一次收干净：

  - 补齐 论语.json：poet.xianqin 里有、lunyu.json 缺的章节（颜渊、子路、宪问、
    卫灵公、微子、子张、尧曰 七篇整缺；季氏、阳货 两篇只有一段）
  - 补齐 mengzi.json：缺的章句按「书·卷·篇·节」题名逐条补进去
  - 大学、中庸 的正文与 先秦/文 的异文合并
  - 四本书都搬到 先秦/<书>/ 下，目录名与书名一致
  - 删除 先秦/文/ 里已并入的 lunyu/mengzi/daxue/zhongyong

用法：
  python3 scripts/merge_wen_into_classics.py            # dry-run
  python3 scripts/merge_wen_into_classics.py --apply
"""
import argparse
import json
import os
import re
import shutil
import sys

from opencc import OpenCC

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
T2S = OpenCC('t2s')
PUNCT = re.compile(r'[“”「」『』"\'‘’（）()，。、；：！？,.;:!?□【】\[\]·—…《》〈〉\s]')

WEN = '先秦/文'
SI_SHU = '先秦/四书五经'
LUNYU = '先秦/论语/lunyu.json'
MENGSI = f'{SI_SHU}/mengzi.json'
DAXUE = f'{SI_SHU}/daxue.json'
ZHONGYONG = f'{SI_SHU}/zhongyong.json'

NEW = {
    'lunyu': '先秦/论语/lunyu.json',
    'mengzi': '先秦/孟子/mengzi.json',
    'daxue': '先秦/大学/daxue.json',
    'zhongyong': '先秦/中庸/zhongyong.json',
}

CN_NUM = '一二三四五六七八九十'


def norm(s):
    return PUNCT.sub('', T2S.convert(s or ''))


def load(path):
    return json.load(open(os.path.join(ROOT, path), encoding='utf-8'))


def dump(path, data):
    full = os.path.join(ROOT, path)
    os.makedirs(os.path.dirname(full), exist_ok=True)
    with open(full, 'w', encoding='utf-8') as fp:
        json.dump(data, fp, ensure_ascii=False, indent=2)
        fp.write('\n')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--apply', action='store_true')
    args = ap.parse_args()

    lunyu = load(LUNYU)
    mengzi = load(MENGSI)

    # 先秦/文 里属于四书的条目
    leftover = {}
    for name in ('lunyu', 'mengzi'):
        path = os.path.join(ROOT, WEN, f'{name}.json')
        leftover[name] = load(os.path.join(WEN, f'{name}.json')) if os.path.exists(path) else []

    # 论语：按章名把 leftover 的段落塞进对应章，缺的章整章补
    chapters = {c['chapter']: c for c in lunyu}
    added_paras = 0
    new_chapters = []
    # 教材选目（《论语》十二章、论语三则、子路曾晳冉有公西华侍坐）是散取各篇拼成的一课，
    # 不是古书单元，也不并进 lunyu.json
    for rec in leftover['lunyu']:
        title = rec['title']
        m = re.match(r'论语·(.+?篇)(?:·第.+章)?$', title)
        if not m:
            continue
        ch = m.group(1)
        if ch not in chapters:
            chapters[ch] = {'chapter': ch, 'paragraphs': []}
            new_chapters.append(ch)
        for p in rec['paragraphs']:
            if norm(p) not in {norm(x) for x in chapters[ch]['paragraphs']}:
                chapters[ch]['paragraphs'].append(p)
                added_paras += 1

    # 章序按 lunyu 原有顺序，新章附在后面
    order = [c['chapter'] for c in lunyu]
    lunyu = [chapters[c] for c in order] + [chapters[c] for c in new_chapters]
    print(f'论语：新增章 {new_chapters}，补段 {added_paras}')

    # 孟子：缺的章句整段补进对应章
    mz_ch = {T2S.convert(c['chapter']): c for c in mengzi}   # 章名是繁体，比对照简化
    added_mz = 0
    for rec in leftover['mengzi']:
        title = rec['title']
        m = re.match(r'孟子·第.+卷·(.+?)·第.+节', title)
        if not m:
            continue
        ch = T2S.convert(m.group(1))
        if ch not in mz_ch:
            print(f'  跳过（章名对不上）：{title}')
            continue
        existing = ''.join(norm(p) for p in mz_ch[ch]['paragraphs'])
        new = [p for p in rec['paragraphs'] if norm(p) and norm(p) not in existing]
        if not new:
            continue                     # 该节正文已全在章里，只是标点/异体字不同
        mz_ch[ch]['paragraphs'].extend(new)
        mz_ch[ch].setdefault('extra', []).append(title)
        added_mz += 1
    print(f'孟子：补章句 {added_mz}')
    mengzi = list(mz_ch.values())

    if not args.apply:
        print('（dry-run，未改动任何文件；加 --apply 落盘）')
        return

    dump(NEW['lunyu'], lunyu)
    dump(NEW['mengzi'], mengzi)
    # 大学、中庸：dict → 列表，正文原样
    dump(NEW['daxue'], [load(DAXUE)])
    dump(NEW['zhongyong'], [load(ZHONGYONG)])
    for p in (LUNYU, MENGSI, DAXUE, ZHONGYONG):
        os.remove(os.path.join(ROOT, p))
    for d in (SI_SHU, '先秦/论语'):
        full = os.path.join(ROOT, d)
        if os.path.isdir(full) and not os.listdir(full):
            os.rmdir(full)
    for name in ('lunyu', 'mengzi', 'daxue', 'zhongyong'):
        p = os.path.join(ROOT, WEN, f'{name}.json')
        if os.path.exists(p):
            os.remove(p)
    print('  落盘完成')


if __name__ == '__main__':
    main()
