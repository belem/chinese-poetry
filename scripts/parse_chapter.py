#!/usr/bin/env python3
"""把 scripts/shidian/chapter.mjs 抓下来的章节页 HTML 解析成正文。

章节页 HTML 里内嵌整章正文：`paragraphList` 的每段是一个 JSON 串，`lines` 里逐行带 `lineType`：
  8 = 作者   9 = 题名   1 = 正文   3 = 空行
一篇会在目录里连排好几章（下一篇的题名、作者也会出现在同一页），所以遇到第二个「作者/题名」就截断。

  python3 scripts/parse_chapter.py <html目录> [--json 输出路径]
"""
import argparse
import json
import os
import re
import sys

LINE = re.compile(r'"content":"((?:[^"\\]|\\.)*)"')


def chapter_lines(path):
    h = open(path, encoding='utf-8').read()
    i = h.find('"paragraphList":')
    if i < 0:
        return None
    out, seen_body = [], False
    for m in LINE.finditer(h[i:i + 300000]):
        raw = m.group(1)
        if 'lines' not in raw[:12]:                    # 只认段落对象，跳过标题、摘要等字符串
            continue
        try:
            d = json.loads(json.loads('"' + raw + '"'))      # 两层转义
        except Exception:
            continue
        for ln in d.get('lines') or []:
            t, c = ln.get('lineType'), ln.get('content') or ''
            if t in (8, 9):
                if seen_body:                               # 已进正文，再遇题名/作者 = 下一篇
                    return out
                out.append([t, c])
            elif t == 1:
                seen_body = True
                out.append([t, c])
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('dir')
    ap.add_argument('--json')
    a = ap.parse_args()
    res = {}
    for fn in sorted(os.listdir(a.dir)):
        if not fn.endswith(('.json', '.html')):
            continue
        lines = chapter_lines(os.path.join(a.dir, fn))
        res[os.path.splitext(fn)[0]] = lines
    if a.json:
        json.dump(res, open(a.json, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(f'{len(res)} 章；空 {sum(1 for v in res.values() if not v)}')
    for k in list(res)[:3]:
        print(k, res[k])


if __name__ == '__main__':
    main()
