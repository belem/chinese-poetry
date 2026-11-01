#!/usr/bin/env python3
"""在 JSON 语料文件里就地改「某条记录的某个字段」，不动其余字节。

`宋/宋词/ci.song.*` 这些文件是历次抓取、拼接留下的，排版各不一样（行尾空格、`,` 后留不留空格、
`[`/`{` 后留不留空格，一个文件一种习惯，一个文件里还前后不一）。统一格式会让整份文件都进 diff，
改一个字变成改一万行，所以不 dumps 整个文件，只替换「某条记录里某个字段的值」那一段。

  patch(rel, {记录下标: {'title': 新值}})

改完用 json.load 校验，保证仍是合法 JSON。
"""
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _spans(text):
    """顶层数组里每条记录在原文中的 (起, 止) 偏移。"""
    spans, depth, in_str, esc, begin = [], 0, False, False, None
    for i, ch in enumerate(text):
        if in_str:
            if esc:
                esc = False
            elif ch == '\\':
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch in '[{':
            depth += 1
            if ch == '{' and depth == 2:
                begin = i
        elif ch in ']}':
            if ch == '}' and depth == 2:
                spans.append((begin, i + 1))
            depth -= 1
    return spans


def _value_span(body, key):
    """记录正文里 `"key": 值` 的值在正文中的 (起, 止)。"""
    head = json.dumps(key, ensure_ascii=False) + ': '
    j = body.find(head)
    if j < 0:
        return None
    k = j + len(head)
    if body[k] == '"':                       # 字符串：数到配对的引号（转义的引号不算）
        end, esc = k + 1, False
        while end < len(body):
            if esc:
                esc = False
            elif body[end] == '\\':
                esc = True
            elif body[end] == '"':
                return k, end + 1
            end += 1
        raise SystemExit('字符串引号不配对')
    if body[k] == '[':                       # 数组：数括号到配平，字符串里的 [ ] 不算
        depth, end, in_str, esc = 0, k, False, False
        while end < len(body):
            c = body[end]
            if in_str:
                if esc:
                    esc = False
                elif c == '\\':
                    esc = True
                elif c == '"':
                    in_str = False
            elif c == '"':
                in_str = True
            elif c == '[':
                depth += 1
            elif c == ']':
                depth -= 1
                if depth == 0:
                    return k, end + 1
            end += 1
        raise SystemExit('数组括号不配平')
    end = k
    while body[end] not in ',\n}':
        end += 1
    return k, end


def patch(rel, edits):
    """edits: {记录下标: {字段: 新值}}；字段不存在时追加在记录末尾，沿用同行的写法。"""
    path = os.path.join(ROOT, rel)
    text = open(path, encoding='utf-8').read()
    records = json.loads(text)
    spans = _spans(text)
    if len(spans) != len(records):
        raise SystemExit(f'{rel}: 记录边界解析不一致（{len(spans)} vs {len(records)}）')
    for idx in sorted(edits, reverse=True):          # 从后往前改，前面的偏移不受影响
        a, b = spans[idx]
        body = text[a:b]
        for key, val in edits[idx].items():
            enc = json.dumps(val, ensure_ascii=False)
            span = _value_span(body, key)
            if span:
                body = body[:span[0]] + enc + body[span[1]:]
            else:
                # 追加：插到最后一个字段的值后面，缩进 / 尾随空格照抄前一行
                last = body.rstrip('}').rstrip()
                eol = ' ' if body != body.rstrip() else ''
                indent = '\n    '
                body = last + ',' + indent + json.dumps(key, ensure_ascii=False) + ': ' + enc + eol + '\n  }'
        text = text[:a] + body + text[b:]
    json.loads(text)                                     # 校验
    open(path, 'w', encoding='utf-8').write(text)
