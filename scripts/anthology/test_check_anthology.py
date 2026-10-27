# -*- coding: utf-8 -*-
"""选本对齐的自检：目录结构 + 匹配器行为。不联网、不改数据。

  python3 -m pytest scripts/anthology/test_check_anthology.py -q
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import check_anthology as ca  # noqa: E402
import shidian as sd  # noqa: E402


def test_anthologies_wellformed():
    anths = ca.load_anthologies()
    assert anths, 'anthologies/ 下没有选本目录'
    for name, a in anths.items():
        assert a['entries'], f'{name} 目次为空'
        nos = [e['no'] for e in a['entries']]
        assert nos == list(range(1, len(nos) + 1)), f'{name} 的 no 不连续'
        for e in a['entries']:
            assert e['first_line'], f'{name} 第 {e["no"]} 条没有 first_line'
            assert len(ca.FLAT.sub('', e['first_line'])) >= 4, f'{name} 第 {e["no"]} 条 first_line 太短'


def variant_map():
    """Unihan 异体表由 collate.norm_factory 下载并缓存；缓存不在时跳过这条检查。"""
    work = os.environ.get('ANTH_WORK', '/tmp/sd_anthology')
    path = os.path.join(work, 'variant_map.json')
    if not os.path.exists(path):
        return None
    ca.load_variants(path)
    return path


def test_variants_converge():
    """简繁、异体两种写法必须落到同一个 key，否则对齐会大面积漏。"""
    if not variant_map():
        import pytest
        pytest.skip('没有 Unihan 异体表缓存，先跑一次 check_anthology.py')
    assert ca.keys_of('憶昔西池池上飮年年')[-1] == ca.keys_of('忆昔西池池上饮年年')[-1]
    assert ca.keys_of('碧雲天黃花地秋色')[-1] == ca.keys_of('碧云天黄花地秋色')[-1]


def test_stray_detected():
    """挂了 tag 但对不上目录的记录，必须报成 stray。"""
    entries = [dict(no=1, first_line='孤鴻海上來池潢不敢顧')]
    records = [
        ('唐代/诗/全唐诗/poet.tang.0.json', 0, dict(author='張九齡', title='感遇', tags=['唐诗三百首'],
                                        paragraphs=['孤鴻海上來，池潢不敢顧。'])),
        ('唐代/诗/全唐诗/poet.tang.0.json', 1, dict(author='李白', title='靜夜思', tags=['唐诗三百首'],
                                        paragraphs=['牀前看月光，疑是地上霜。'])),
    ]
    hits = ca.match(entries, records, 'poet.tang.')
    assert [r[1] for r in hits[1]] == [0]


def test_song_poems_excluded():
    """《全宋诗》里的记录不能被当成唐诗三百首。"""
    entries = [dict(no=1, first_line='孤鴻海上來池潢不敢顧')]
    records = [('唐代/诗/全唐诗/poet.song.0.json', 0,
                dict(author='某人', title='x', tags=[], paragraphs=['孤鴻海上來，池潢不敢顧。']))]
    assert ca.match(entries, records, 'poet.tang.')[1] == []
