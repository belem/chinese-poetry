#!/usr/bin/env python3
"""按识典古籍《古文觀止》(SDZJ0641，粗校 + 译文) 重建 汇编/古文观止/ 的 12 个卷文件。

底本：识典古籍《古文觀止》光绪二十八年善成堂刊本（SDZJ0641，粗校，带人工校对过的
机器译文）。正文取 lineType=1 的行（2 是夹注、3 是眉批，都不进库）；译文按
logicSentenceId 在段内定序——底本返回的译句是批内乱序，且该 id 是节级共享的，
只能按「本段正文里出现的句子 id」对齐，不能跨段排。

流程：
  1. 抓章节页（带译文），每章一个文件，存进 --pages 目录
       node scripts/shidian/gwz_fetch.mjs <outdir> <chapterId>...
  2. 核对 222 篇是否都抓齐
       python3 scripts/build_guwen.py --dump
  3. 生成 12 卷
       python3 scripts/build_guwen.py --out 汇编/古文观止

篇目表 scripts/guwen_canon.tsv 是通行本 12 卷 222 篇与底本章节 id 的对照，卷次、
篇题、作者都按通行本写。善成堂本卷末的「國朝文」十篇不是本书篇目，不入。
"""
import argparse
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CANON = os.path.join(ROOT, 'scripts', 'guwen_canon.tsv')
VOL = {'一': '卷一周文', '二': '卷二周文', '三': '卷三周文', '四': '卷四戰國文',
       '五': '卷五漢文', '六': '卷六漢文', '七': '卷七六朝唐文', '八': '卷八唐文',
       '九': '卷九唐宋文', '十': '卷十宋文', '十一': '卷十一宋文', '十二': '卷十二明文'}
OUTLINE = ['卷一周文', '卷二周文', '卷三周文', '卷四戰國文', '卷五漢文', '卷六漢文',
           '卷七六朝唐文', '卷八唐文', '卷九唐宋文', '卷十宋文', '卷十一宋文', '卷十二明文']

PUNCT = '，。、；：？！“”‘’（）「」『』《》…—'


def join_lines(lines):
    """把底本同一段的多行正文拼回去。

    底本把句读单独排成一行：「…三踴，而出」+「。」+「。人謂崔子」应得
    「…三踴，而出。人謂崔子」。纯标点行并进前行（不添字），接上后出现叠标点的
    只留一个。底本自己缺的标点不改：行与行都在汉字处断开的那 20 来处（以及引号
    收尾后直接接正文的那几处），补什么全凭猜，宁缺毋滥 —— 留给逐篇勘误去定。
    """
    out = []
    for t in lines:
        if not out:
            out.append(t)
            continue
        prev, st = out[-1], t.strip()
        if st and all(c in PUNCT for c in st):
            if prev and prev[-1] == st[0]:      # 前行已给出这个标点
                continue
            if prev and prev[-1] in '”’」』' and st in ('，', '、', '；', '：'):
                continue
            out[-1] = prev + st
            continue
        out.append(t)
    text = ''.join(out).replace('\n', '')
    for _ in range(2):
        text = text.replace('。，', '，').replace('，。', '。')
        for p in PUNCT:
            text = text.replace(p * 2, p)
    return text.strip()


def chapter(pages, sid):
    """一章的正文段与段级译文。"""
    d = json.loads(open(os.path.join(pages, sid + '.json'), encoding='utf-8').read())
    ps = [p for p in d['data']['paragraphs'] if p['chapterId'] == sid]
    assert ps, '响应里的段落不属于 %s（底本偶尔把相邻两篇塞进同一响应）' % sid
    body = []
    for p in ps:
        lines = (p.get('content') or {}).get('lines') or []
        main = join_lines([l['content'] for l in lines if l['lineType'] == 1])
        if not main:
            continue
        sents = [s for s in ((p.get('translateContent') or {}).get('sentences') or [])
                 if str(s.get('logicSentenceId')) not in ('None', '0')]
        seen, tr = set(), []
        for s in sorted(sents, key=lambda s: int(s['logicSentenceId'])):
            if s['logicSentenceId'] in seen:
                continue
            seen.add(s['logicSentenceId'])
            tr.append(s['content'])
        body.append({'main': main, 'tr': tr})
    if body and len(body[0]['main']) <= 4:      # 首段是出处行（「左傳」「國語」…）
        body = body[1:]
    # 无译文的是作者署名单段或另一篇的题名段，不进库
    return [p for p in body if p['tr']]


def load_canon():
    rows = []
    for line in open(CANON, encoding='utf-8'):
        if line.startswith('#') or not line.strip():
            continue
        vol, title, author, sid = line.rstrip('\n').split('\t')
        rows.append({'vol': vol, 'title': title, 'author': author, 'id': sid})
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--pages', default='/tmp/gw/pages')
    ap.add_argument('--out', default=os.path.join(ROOT, '汇编/古文观止'))
    ap.add_argument('--dump', action='store_true')
    a = ap.parse_args()
    canon = load_canon()
    if a.dump:
        miss = 0
        for c in canon:
            try:
                body = chapter(a.pages, c['id'])
                ok = 'OK' if body else 'EMPTY'
            except (FileNotFoundError, AssertionError):
                body, ok = [], 'MISSING'
            miss += ok != 'OK'
            print(c['vol'], c['title'], c['author'], c['id'], ok,
                  sum(len(p['tr']) for p in body), sum(len(p['main']) for p in body))
        print('%d 篇，缺 %d' % (len(canon), miss))
        return
    total = 0
    for vol in OUTLINE:
        recs = []
        for c in canon:
            if VOL[c['vol']] != vol:
                continue
            body = chapter(a.pages, c['id'])
            assert body, '缺底本：%s %s' % (vol, c['title'])
            recs.append({
                'author': c['author'],
                'title': c['title'],
                'paragraphs': [p['main'] for p in body],
                'translation': [p['tr'] for p in body],
                'notes': '底本：《古文觀止》識典古籍精校本（SDZJ0641，光緒二十八年善成堂刊本，'
                         '粗校，帶譯文），章節 %s。正文取 lineType=1 的行，夾注、眉批不錄；'
                         '译文按 logicSentenceId 段内定序。' % c['id'],
                'id': '',
            })
        total += len(recs)
        with open(os.path.join(a.out, vol + '.json'), 'w', encoding='utf-8') as fp:
            json.dump(recs, fp, ensure_ascii=False, indent=2)
        print('%s %d 篇 %d 段' % (vol, len(recs), sum(len(r['paragraphs']) for r in recs)))
    print('合计 %d 篇（生成后跑 python3 scripts/backfill_ids.py --apply 补 id）' % total)


if __name__ == '__main__':
    main()
