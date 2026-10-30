# -*- coding: utf-8 -*-
"""审查人手填替换文本的解析：□ 处该填什么。不联网、不改数据。

  python3 -m pytest scripts/shidian/test_token_from_edit.py -q
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import shidian as sd  # noqa: E402

CASES = [
    # (原句（含 □）, 审查人填的, 期望)
    ('□浪痕痕去。', '碧浪痕痕去。', '碧'),                        # 单字缺，判定直接给整句
    ('□□处。', '花深处。', '花深'),
    ('□□银烛夜厌厌。', '光摇银烛夜厌厌。', '光摇'),
    ('拟倩东□。', '拟倩东君。', '君'),
    ('玉人双鞚华□。', '玉人双鞚华鑣。', '鑣'),
    ('□见。', '乍见。', '乍'),
    ('半酣漏声频□', '半酣漏声频促', '促'),
    ('未散娇云轻□鬓，欲融轻雪乍凝', '未散娇云轻嚲鬓', '嚲'),      # 粘来的句子只到缺字为止
    ('过□添炉鼎，朱颜愈少。', '添', '添'),                        # 只填一个字：接在 □ 前，不是原句里已有的字
    ('过□添炉鼎，朱颜愈少。', '⟦删框⟧', ''),                      # 标了删框记号：□ 整个删掉
]


def test_cases():
    for orig, prop, want in CASES:
        assert sd.token_from_edit(orig, prop) == want, (orig, prop)
