"""读取 reference/mit_licence_haitang 的源数据。

works_3.json 缺外层方括号（裸对象流），不是合法 JSON，需按流解析；
其余 works_*.json 是正常数组。
"""
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SRC = os.path.join(ROOT, 'reference', 'mit_licence_haitang')


def _load(name):
    path = os.path.join(SRC, name + '.json')
    with open(path, encoding='utf-8') as fp:
        text = fp.read().strip()
    if text.startswith('['):
        return json.loads(text)
    return json.loads('[' + text + ']')


def works():
    """11407 条正文。"""
    out = []
    for i in range(1, 9):
        out.extend(_load('works_%d' % i))
    return out


def authors():
    return _load('authors')


def dynasties():
    return _load('dynasties')


def collections():
    return _load('collections')
