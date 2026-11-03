# -*- coding: utf-8 -*-
"""对勘用的文字工具：去标点、归一异体、按句界切分。

底本（简体排印李善注本）与六臣本（宋刊本，字形古）比字之前，两边都要
1) 去掉标点空白、2) 用 `zhaoming_variant.norm` 归一异体与繁简，然后才逐字对齐。
"""
import re, sys, os

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import zhaoming_variant as V

NOISE = re.compile('[\\s\\u3000，。、；：？！“”‘’（）()【】《》·〈〉—…,.\\-—「」『』□■]')


def flat(s):
    """去标点 → 归一异体/繁简。"""
    return NOISE.sub('', V.norm(s))


def split_sentences(t):
    """一段 → 句：按句末标点切，引号内的不切。"""
    out, buf, depth = [], '', 0
    for ch in t:
        buf += ch
        if ch in '“「':
            depth += 1
        elif ch in '”」':
            depth = max(0, depth - 1)
        elif ch in '。！？' and depth == 0:
            out.append(buf)
            buf = ''
    if buf.strip():
        out.append(buf)
    return out
