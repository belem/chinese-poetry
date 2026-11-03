#!/usr/bin/env python3
"""《词综》卷首记数与实收逐卷对账。

  python3 scripts/cizong_volcount.py            # 打印逐卷对账表
  python3 scripts/cizong_volcount.py > docs/词综卷首记数.tsv    # 写明细

底本每卷卷首有一行自记首数，写法前后三种，还有几卷根本没写数目：

  卷一～三十   `唐词六十八首`、`宋词七十首`、`元词五十三首`（句末带「首」）
  卷三十一～三十五  `（六十九首）宋词`、`（词五十七）宋词`（记数在前、类别在后，卷三十四掉了「首」）
  卷三十二、三十三  只写 `宋词`、`金元词`，不记数

对的是同一卷的「底本自记」与「实收」（`汇编/词综/卷N.json` 的条数）。差额逐类看：

  * **卷二十八：底本把元人一段接在宋人之后**。卷首只写「元词二首」（李琳两首），紧接着没有另起
    「《词综》（卷二十九）」，赵文以下 52 首元人一路排下来，到 `苏武慢和冯尊师虞集` 才又出现卷首行。
    所以底本的四栏里，卷二十八实收 54 首（2 + 52），卷二十九自记的 52 首正好是这后一半。
    按底本分卷，不改（底本就这么排）；账上记 +52；
  * **卷七 +3、卷十四 +1、卷十六 +1、卷二十五 +1**：底本在记数之后又多排了「又」条，
    编者记数时没算进去；
  * **卷十七 −1、卷十八 −1、卷二十 −2、卷二十四 −1、卷三十 −1、卷三十五 −1**：底本漏抄或是并了「又」条。
    卷三十五是卷末《玉漏迟》与卷三十四重出，底本抄了两遍；
  * **卷三十二、卷三十三**：卷首只写「宋词」「金元词」，底本自己没记数。

记数本身不改：底本是清刻本，卷首记数是编者自己写的，与实收的差额属于底本原貌，
写进 docs/词综重建.md，不在数据里补。
"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import import_cizong as ic  # noqa: E402

ROOT = ic.ROOT

DECL = re.compile(r'(?:[（(]\s*(?:词)?([〇一二三四五六七八九十百\d]+)\s*首?\s*[）)])?'
                  r'(?:([〇一二三四五六七八九十百\d]+)首)?')


def declared(line):
    """卷首那一行里记的首数：`宋词六十八首`、`（六十九首）宋词`、`（词五十七）宋词`；没有数目返回 None。"""
    s = line.replace('（', '(').replace('）', ')')
    m = re.search(r'[(（]?\s*(?:词)?([〇一二三四五六七八九十百]+)\s*首?\s*[)）]', s)
    if m:
        return ic.cn2int(m.group(1))
    m = re.search(r'词([〇一二三四五六七八九十百]+)首', s)
    if m:
        return ic.cn2int(m.group(1))
    return None


def main():
    lines = open(os.path.join(ROOT, ic.SRC), encoding='utf-8').read().split('\n')
    heads = [i for i, l in enumerate(lines) if l.startswith('《词综》（卷')]
    actual = {}
    for f in os.listdir(os.path.join(ROOT, ic.OUT)):
        m = re.fullmatch(r'卷(.+)\.json', f)
        if not m:
            continue
        arr = json.load(open(os.path.join(ROOT, ic.OUT, f), encoding='utf-8'))
        actual[m.group(1)] = len(arr)

    print('volume\tlabel\tgenre\tdeclared\treceived\tdelta\tsource_line')
    tot_d = tot_r = tot_miss = 0
    for k, v in enumerate(heads):
        end = heads[k + 1] if k + 1 < len(heads) else len(lines)
        name = re.search(r'卷([〇一二三四五六七八九十百]+)', lines[v]).group(1)
        vol = ic.cn2int(name)
        label, dl = '', None
        for j in range(v + 1, min(end, v + 8)):
            s = lines[j].strip()
            if not s:
                continue
            label, dl = s, declared(s)
            break
        got = actual.get(ic.int2cn(vol), 0)
        # 类别：去掉括号、记数与「词」字，剩下的「唐」「五代十国」「宋金元」等
        # （`（词五十七）宋词` 里的「词」在记数前头，一并去掉）
        genre = re.sub(r'[〇一二三四五六七八九十百\d]+首?', '', label)
        genre = re.sub(r'[（()）]', '', genre)
        genre = '五代十国' if label.startswith('五代') else genre.replace('词', '')
        genre = genre or '—'
        if dl is None:
            tot_miss += 1
            print(f'{ic.int2cn(vol)}\t{label}\t{genre}\t—\t{got}\t—\t{j + 1}')
            continue
        tot_d += dl
        tot_r += got
        print(f'{ic.int2cn(vol)}\t{label}\t{genre}\t{dl}\t{got}\t{got - dl:+d}\t{j + 1}')
    print(f'# 合计：自记 {tot_d} 首（另有 {tot_miss} 卷不记数）、实收 {tot_r} 首、差 {tot_r - tot_d:+d}',
          file=sys.stderr)


if __name__ == '__main__':
    main()
