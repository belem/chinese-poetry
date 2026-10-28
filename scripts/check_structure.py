#!/usr/bin/env python3
"""结构 / 字符层面的自动质检，只报告可疑位置，不修改任何数据。

检查项：
  shi_line_length  诗：整首以五言或七言为主，个别句子字数多/少 1~2 字（疑漏字、衍字）
  ci_pattern       词：与同词牌主流体式相比总字数差 1~2 字，且该字数极少见（疑漏字、衍字）
  ascii_residue    正文中混入的 ASCII 字母/数字（爬取残渣，如 z5、zB）
  cyrillic_greek   西里尔 / 希腊字母乱码
  kana_bopomofo    日文假名 / 注音符号 / 竖排标点（U+FE3D–U+FE44，如 ﹀︽）乱码
  box_drawing      制表符号乱码（┾ ╆ 等）与 U+FFFD 替换符
  dup_punct        重复标点（？。 ！。 。。 ，， 、、）
  half_width_punct 紧邻汉字的半角 , ; : !
  bare_pua         {...} 之外的私用区字符
  zero_width       零宽空格等不可见字符（抓取残留，正文与标题都查）
  missing_char     □ 缺字

用法：
  python3 scripts/check_structure.py --baseline scripts/check_baseline.json   # 与基线逐项比对
  python3 scripts/check_structure.py --write-baseline scripts/check_baseline.json   # 把当前数量写为基线
  python3 scripts/check_structure.py --baseline-from HEAD     # 基线取自已提交的版本：只判本次改动
  python3 scripts/check_structure.py --files-from-diff <ref>  # 只查相对 <ref> 有改动的数据文件
  python3 scripts/check_structure.py --files-from-diff <ref> --emit-baseline out.json
                                                      # 只写改动文件涉及检查项的基线（CI 自动维护基线与汇总用）
  python3 scripts/check_structure.py --allow-fewer     # 允许检查项数量低于基线（旧口径，CI 已不再使用）
  python3 scripts/check_structure.py                 # 打印汇总
  python3 scripts/check_structure.py --out r.jsonl   # 同时输出逐条明细（JSON Lines）
  python3 scripts/check_structure.py --only ci_pattern --show 20
"""
import argparse
import collections
import json
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKIP = {'author', 'rank', 'settings', '表面结构字', 'error', 'fix_progress'}
SKIP_DIRS = {'loader', 'strains', 'images', 'rank', 'error', 'scripts', 'docs', '.git', '.claude', '.github',
             '.cnb', 'reference'}  # reference/ 是导入源，不是发布语料

SENT_SPLIT = re.compile(r'[，。！？；、,!?;：:]')
NOTE = re.compile(r'（[^）]*）|\([^)]*\)')           # 夹注，如（一作……）
PLACEHOLDER = re.compile(r'\{[^}]*\}')               # {疒} 等生僻字占位，计 1 字
FOOTNOTE = re.compile(r'\[\d+\]|〖\d+〗')          # 脚注 / 校注标号 [1] 〖1〗
ZAYAN_TITLE = re.compile(r'[歌行吟引曲謠谣辭辞詞词句]')  # 歌行杂言、摘句，句长本就不齐
ASCII_RES = re.compile(r'[A-Za-z0-9]+')
HANZI = re.compile(r'[\u3400-\u9fff\U00020000-\U0003ffff\ue000-\uf8ff□〇]')
CYRILLIC_GREEK = re.compile(r'[Ѐ-ӿͰ-Ͽ]')
BOX_DRAWING = re.compile(r'[\u2500-\u257f\ufffd]')   # 制表符号乱码与 U+FFFD 替换符（GBK 字节错位）
DUP_PUNCT = re.compile(r'？。|！。|。。|，，|、、')                 # 已规整过的重复标点
HALF_PUNCT = re.compile(r'(?<=[\u4e00-\u9fff])[,;:!]|[,;:!](?=[\u4e00-\u9fff])')   # 紧邻汉字的半角标点
KANA_BOPOMOFO = re.compile(r'[\u3040-\u30fa\u30fc-\u30ff\u3100-\u312f\u31a0-\u31bf\ufe3d-\ufe44]')  # 假名、注音、竖排标点乱码（不含标题分隔符・）
# 竖排/兼容形式的标点（U+FE3D ︽、U+FE40 ﹀ 等）出现在正文，是「僝僽」这类横向排版日文字形的乱码，
# 与 kana_bopomofo 同类：见 宋/宋词/ci.song.*「风﹀雨︽」。
ZERO_WIDTH = re.compile('[\u200b-\u200f\u2060\ufeff]')  # 零宽空格等不可见字符：多为抓取残留
PUA = re.compile(r'[-]')
# 目录已按朝代分层（先秦/ 唐代/ 五代十国/ 宋/ ...），按顶层目录判断体裁不再可行，
# 改用文件名前缀定体裁：诗 poet.*、词 ci.*。只对这两类做句长/词牌检查。
SHI_PREFIX, CI_PREFIX = 'poet.', ('ci.',)   # 体裁看文件名前缀：poet.* 是诗，ci.* 是词；目录已按朝代分层，看不了目录名


# 历史口径：这八类是「一增加即退化」。2026-10 起 --baseline 对全部检查项做双向比对
# （少报与多报都要管），这份名单只留作文档
STRICT = ('bad_json', 'cyrillic_greek', 'kana_bopomofo', 'box_drawing', 'bare_pua', 'ascii_residue',
          'dup_punct', 'half_width_punct', 'zero_width')


def iter_files():
    for dirpath, dirs, filenames in os.walk(ROOT):
        dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS)
        for f in sorted(filenames):
            if f.endswith('.json') and not any(s in f for s in SKIP):
                yield os.path.relpath(os.path.join(dirpath, f), ROOT)


def is_data_file(rel):
    """iter_files() 会遍历的那些文件：判定口径只有这一处，别处都调它。"""
    if not rel.endswith('.json') or any(s in os.path.basename(rel) for s in SKIP):
        return False
    return not any(part in SKIP_DIRS for part in rel.split(os.sep)[:-1])


def changed_data_files(ref):
    """相对 git ref 有增删改的数据文件（不含本次新加的、从未提交过的）。"""
    def git(*args):
        return subprocess.run(['git', '-C', ROOT, '-c', 'core.quotepath=false', *args], check=True,
                              stdout=subprocess.PIPE, text=True).stdout.splitlines()
    out = git('diff', '--name-only', '--diff-filter=d', ref, '--')   # d：删掉的文件不查
    present = {os.path.normpath(x) for x in git('ls-files')}
    files = []
    for rel in out:
        rel = os.path.normpath(rel)
        if rel in present and is_data_file(rel):
            files.append(rel)
    return sorted(files)


def count_all():
    """全库各类问题的数量（不保留明细，省内存）。"""
    counts = collections.Counter()
    files = changed_data_files(args.files_from_diff) if args.files_from_diff else None
    if files is not None and not files:
        print('本次改动不涉及数据文件，无需比较')
        return 0
    ci_poems = []
    for rel in files if files is not None else iter_files():
        try:
            poems = list(iter_poems(rel))
        except (json.JSONDecodeError, UnicodeDecodeError):
            counts['bad_json'] += 1
            continue
        name = os.path.basename(rel)
        for idx, it, lines in poems:
            check_chars(rel, idx, it, lines, lambda kind, *a, **k: counts.update([kind]))
            if name.startswith(CI_PREFIX) and it.get('rhythmic'):
                ci_poems.append((rel, idx, it, lines))
            elif name.startswith(SHI_PREFIX):
                check_shi(rel, idx, it, lines, lambda kind, *a, **k: counts.update([kind]))
    for _ in ci_anomalies(ci_poems):
        counts['ci_pattern'] += 1
    return dict(sorted(counts.items()))


def iter_poems(rel):
    with open(os.path.join(ROOT, rel), encoding='utf-8') as fp:
        data = json.load(fp)
    items = data if isinstance(data, list) else [data]
    for idx, it in enumerate(items):
        if not isinstance(it, dict):
            continue
        lines = it.get('paragraphs')
        if isinstance(lines, str):
            lines = [lines]
        if not isinstance(lines, list) or not all(isinstance(s, str) for s in lines):
            continue
        yield idx, it, lines


def clean(s):
    """去夹注与校勘方括号，生僻字占位折算为 1 个字符，叠字符号「々」展开为前一字。"""
    s = NOTE.sub('', s)
    s = PLACEHOLDER.sub('〇', s)
    s = s.replace('[', '').replace(']', '')
    return re.sub(r'(.)々', r'\1\1', s)


def sentences(lines):
    """按标点切句，每句只保留汉字（书名号、引号等不计字数）。"""
    out = []
    for line in lines:
        for x in SENT_SPLIT.split(clean(line)):
            x = ''.join(HANZI.findall(x))
            if x:
                out.append(x)
    return out


def label(it):
    return f"{it.get('author', '')}《{it.get('title') or it.get('rhythmic') or ''}》"


def check_chars(rel, idx, it, lines, report):
    for line in lines:
        body = FOOTNOTE.sub('', PLACEHOLDER.sub('', line))
        for kind, rx in (('cyrillic_greek', CYRILLIC_GREEK), ('kana_bopomofo', KANA_BOPOMOFO),
                         ('box_drawing', BOX_DRAWING), ('bare_pua', PUA), ('ascii_residue', ASCII_RES),
                         ('dup_punct', DUP_PUNCT), ('half_width_punct', HALF_PUNCT), ('zero_width', ZERO_WIDTH)):
            for m in rx.finditer(body):
                report(kind, rel, idx, it, line, token=m.group())
        if '□' in line:
            report('missing_char', rel, idx, it, line, token='□')
    # 元曲等的标题里混有正文片段，乱码同样会出现在标题中
    for field in ('title', 'rhythmic'):
        text = it.get(field)
        if isinstance(text, str):
            body = PLACEHOLDER.sub('', text)
            for kind, rx in (('cyrillic_greek', CYRILLIC_GREEK), ('kana_bopomofo', KANA_BOPOMOFO),
                             ('bare_pua', PUA), ('zero_width', ZERO_WIDTH)):
                for m in rx.finditer(body):
                    report(kind, rel, idx, it, f'[{field}] {text}', token=m.group())


LEGIT_ODD = re.compile(r'^君不[見见]|^嗚呼|^呜呼|兮')    # 歌行常见的合法加字
# 鼎、铭、颂、赋、表、序、传等本是散文，收在 poet.* 里但不能按齐言诗判句长
PROSE_TITLE = re.compile(r'銘|铭|頌|颂|贊|赞|賦|赋|表|啟|启|狀|状|書|书|序|記|记|傳|传|說|说|'
                         r'論|论|議|议|疏|策|碑|偈|誄|诔|祭|禱|祷|告|牒|帖|引|自述|行狀|行状|'
                         r'墓誌|墓志|神道碑|塔銘|塔铭')


def check_shi(rel, idx, it, lines, report):
    sents = sentences(lines)
    if len(sents) < 4:
        return
    lens = collections.Counter(len(s) for s in sents)
    main, n = lens.most_common(1)[0]
    title = it.get('title') or ''
    if main not in (5, 7) or n / len(sents) < 0.9 or ZAYAN_TITLE.search(title) or PROSE_TITLE.search(title):
        return
    for i, s in enumerate(sents):
        if abs(len(s) - main) == 1 and not LEGIT_ODD.search(s):
            report('shi_line_length', rel, idx, it, s,
                   detail=f'{main}言诗中出现 {len(s)} 字句')


def ci_tune(it):
    name = (it.get('rhythmic') or '').strip()
    return re.split(r'[・·]', name)[-1] if name else ''


def ci_anomalies(ci_poems):
    """与同词牌主流体式相比总字数差 1~2 字、且该字数极少见的词。

    逐首产出 dict：rel/idx/it/sents/tune/total/main_total/main_n/n_poems/count，
    以及 bad = [(句序, 常体句长), ...]（句数与常体一致且只有 1~2 句不同时），否则为 None。
    """
    groups = collections.defaultdict(list)
    for rel, idx, it, lines in ci_poems:
        sents = sentences(lines)
        if sents and '□' not in ''.join(lines):     # 缺字的另由 missing_char 处理
            groups[ci_tune(it)].append((rel, idx, it, sents))
    for tune, poems in groups.items():
        if len(poems) < 10:
            continue
        totals = collections.Counter(sum(map(len, p[3])) for p in poems)
        main_total, main_n = totals.most_common(1)[0]
        if main_n / len(poems) < 0.4:
            continue
        # 主流体式的句式（句长序列）
        main_sig = collections.Counter(
            tuple(map(len, p[3])) for p in poems if sum(map(len, p[3])) == main_total
        ).most_common(1)[0][0]
        for rel, idx, it, sents in poems:
            total = sum(map(len, sents))
            diff = total - main_total
            if not diff or abs(diff) > 2 or totals[total] / len(poems) > 0.03:
                continue
            sig = tuple(map(len, sents))
            bad = None
            if len(sig) == len(main_sig):
                bad = [(i, main_sig[i]) for i, (a, b) in enumerate(zip(sig, main_sig)) if a != b]
                if len(bad) > 2:
                    bad = None
            yield dict(rel=rel, idx=idx, it=it, sents=sents, tune=tune, total=total,
                       main_total=main_total, main_n=main_n, n_poems=len(poems),
                       count=totals[total], bad=bad)


def check_ci(ci_poems, report):
    for a in ci_anomalies(ci_poems):
        sents = a['sents']
        where = '；'.join(f'「{sents[i]}」{len(sents[i])}字(常体{n})' for i, n in a['bad'] or [])
        report('ci_pattern', a['rel'], a['idx'], a['it'], where,
               detail=f"{a['tune']} 共{a['total']}字，常体{a['main_total']}字"
                      f"（{a['main_n']}/{a['n_poems']}首），本字数仅{a['count']}首")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', help='逐条明细输出路径（.jsonl）')
    ap.add_argument('--only', help='只显示某类检查')
    ap.add_argument('--show', type=int, default=5, help='每类展示的样例数')
    ap.add_argument('--baseline', help='与基线比较：各类数量比基线多即非零退出；数量变少的只提示')
    ap.add_argument('--baseline-from', metavar='REF',
                    help='基线取自已提交的版本（如 HEAD、origin/develop），与 --baseline 同样比较。'
                         '用来只判本次改动：别人删掉的问题不会算到你头上，你修好的也不必写回基线')
    ap.add_argument('--files-from-diff', metavar='REF',
                    help='只查相对 REF 有改动的数据文件（配合 --baseline-from 用，可把 CI 从数分钟压到几十秒）')
    ap.add_argument('--emit-baseline', metavar='PATH',
                    help='配合 --files-from-diff：只把改动文件涉及检查项的当前数量写成 JSON，'
                         '给 CI 与 REF 上的基线合并用；写完后正常退出')
    ap.add_argument('--allow-fewer', action='store_true',
                    help='保留参数，已无作用：数量低于基线不再报错（旧口径见 docs/质检基线.md）')
    ap.add_argument('--write-baseline', help='把当前各类数量写为基线')
    args = ap.parse_args()

    findings = []

    def report(kind, rel, idx, it, text, token=None, detail=None):
        findings.append({'check': kind, 'file': rel, 'index': idx, 'poem': label(it),
                         'text': text, 'token': token, 'detail': detail})

    files = changed_data_files(args.files_from_diff) if args.files_from_diff else None
    if files is not None and not files:
        print('本次改动不涉及数据文件，无需比较')
        return 0
    ci_poems = []
    for rel in files if files is not None else iter_files():
        try:
            poems = list(iter_poems(rel))
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            report('bad_json', rel, -1, {}, str(e))
            continue
        name = os.path.basename(rel)
        for idx, it, lines in poems:
            check_chars(rel, idx, it, lines, report)
            if name.startswith(CI_PREFIX) and it.get('rhythmic'):
                ci_poems.append((rel, idx, it, lines))
            elif name.startswith(SHI_PREFIX):
                check_shi(rel, idx, it, lines, report)
    check_ci(ci_poems, report)

    if args.out:
        with open(args.out, 'w', encoding='utf-8') as fp:
            for f in findings:
                fp.write(json.dumps(f, ensure_ascii=False) + '\n')

    by_kind = collections.defaultdict(list)
    for f in findings:
        by_kind[f['check']].append(f)
    for kind, items in sorted(by_kind.items(), key=lambda kv: -len(kv[1])):
        if args.only and kind != args.only:
            continue
        nfiles = len({f['file'] for f in items})
        print(f'\n== {kind}: {len(items)} 处，涉及 {nfiles} 个文件')
        if kind == 'ascii_residue':
            top = collections.Counter(f['token'] for f in items).most_common(15)
            print('   高频残渣:', '  '.join(f'{t}×{n}' for t, n in top))
        for f in items[:args.show]:
            extra = f" | {f['detail']}" if f['detail'] else ''
            print(f"   {f['file']}#{f['index']} {f['poem']} {f['text']}{extra}")

    counts = {k: len(v) for k, v in sorted(by_kind.items())}
    if args.write_baseline:
        with open(args.write_baseline, 'w', encoding='utf-8') as fp:
            json.dump(counts, fp, ensure_ascii=False, indent=2)
            fp.write('\n')
        print(f'\nbaseline written: {args.write_baseline}')
    if args.emit_baseline:
        # 只写「本次改动的文件里，有哪些检查项」的当前数量，与基线取同口径：
        # 键缺失即该检查项在改动范围内本来就没有问题，全库的其它同类问题不背锅
        with open(args.emit_baseline, 'w', encoding='utf-8') as fp:
            json.dump(counts, fp, ensure_ascii=False, indent=2)
            fp.write('\n')
        print(f'\nbaseline emitted: {args.emit_baseline}')
        return 0
    base = None
    if args.baseline_from:
        base = baseline_at(args.baseline_from)
        print(f'\n基线取自 {args.baseline_from}（只比较改动文件涉及的检查项）')
    elif args.baseline:
        with open(args.baseline, encoding='utf-8') as fp:
            base = json.load(fp)
    if base is not None:
        if files is None:
            worse = {k: (base.get(k, 0), counts.get(k, 0))
                     for k in set(base) | set(counts) if counts.get(k, 0) > base.get(k, 0)}
        else:
            # 只判改动文件：基线里没有的检查项说明改动范围内本无此类问题
            worse = {k: (base.get(k, 0), n) for k, n in counts.items() if n > base.get(k, 0)}
        better = {k: (base.get(k, 0), counts.get(k, 0)) for k in base if counts.get(k, 0) < base[k]}
        if better:
            print('\n本次改动使这些检查项数量下降（不必改基线，' +
                  'scripts/check_structure.py --write-baseline 重算即可）：'
                  + '，'.join(f'{k} {a}→{b}' for k, (a, b) in better.items()))
        if worse:
            print('\n::error::以下检查项比基线增加，请修正后再提交：'
                  + '，'.join(f'{k} {a}→{b}' for k, (a, b) in worse.items()))
            return 1
        print('\n与基线比较：没有新增问题')
    return 0


def baseline_at(ref):
    """取 git ref 上的 check_baseline.json。基线不再要求手写回、也就不再是合并热点：

    只在「没改动任何数据文件」的提交（专职重算基线）里放进去，其余情况一律从 ref 现取。
    """
    for path in ('scripts/check_baseline.json', 'check_baseline.json'):
        r = subprocess.run(['git', '-C', ROOT, 'show', f'{ref}:{path}'],
                           stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
        if r.returncode == 0:
            return json.loads(r.stdout)
    print(f'::warning::{ref} 上没有 check_baseline.json，基线记为全 0（改动范围内出现任何问题都会失败）')
    return {}


if __name__ == '__main__':
    sys.exit(main())
