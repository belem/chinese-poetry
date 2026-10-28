#!/usr/bin/env python3
"""审查进度记录：一个文件一条记录，一条记录一个文件。

替代原来单文件、整表重写的 fix_progress.json —— 两个人并行审查不同文件时
改的是不同文件，git 不会撞在一起。

  索引     fix_progress.json                   只留 stats 与逐文件的 date/reviewer/status
  正文     docs/progress/<路径>.json            fixes / batch_files / note / scope_note

记录正文只在 docs/progress/ 里存在一份，索引不重复它；读记录走 load(rel)，
两边不一致时以 docs/progress/ 为准（索引是派生物，随时可以重算）。

文件名：路径里的 / → @，不在路径里出现的字符，不需要转义表。
超过 NAME_MAX 的长路径改写成 <父目录>@<正文哈希>-<原文件名>。

  python3 scripts/progress.py migrate   # fix_progress.json → docs/progress/（一次性）
  python3 scripts/progress.py index     # 重算索引与 stats
  python3 scripts/progress.py check     # 索引与记录是否一致、有无死链
"""
import argparse
import hashlib
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INDEX = os.path.join(ROOT, 'fix_progress.json')
BODY_DIR = os.path.join(ROOT, 'docs/progress')

DESCRIPTION = (
    '审查进度索引。每个文件的记录正文在 docs/progress/<路径>.json（路径里的 / 写作 @），'
    '两边的 date / reviewer / status 必须一致，由 scripts/progress.py index 重算。'
    '审查流程见 AGENTS.md「Step 1」。'
)
FIELDS = ('date', 'reviewer', 'status')
BODY_KEYS = ('fixes', 'batch_files', 'note', 'scope_note')
NAME_MAX = 200


def esc(rel):
    """路径 → 记录文件名（相对 docs/progress/）。"""
    rel = rel.replace(os.sep, '/').strip('/')
    name = rel.replace('/', '@')
    if not name.endswith('.json'):
        name += '.json'                      # 批次记录（_新增选本 之类）不是文件路径
    if len(name) <= NAME_MAX:
        return name
    parent, base = os.path.dirname(rel), os.path.basename(rel)
    digest = hashlib.sha1(rel.encode('utf-8')).hexdigest()[:8]
    return f'{parent.replace("/", "@")}@{digest}-{base}.json'


def _walk(dirpath):
    for dirpath, dirs, files in os.walk(dirpath):
        dirs.sort()
        for f in sorted(files):
            if f.endswith('.json'):
                yield os.path.join(dirpath, f)


def read_path(path):
    with open(path, encoding='utf-8') as fp:
        return json.load(fp)


def load_records():
    """docs/progress/ → {键: 记录}。"""
    out = {}
    if not os.path.isdir(BODY_DIR):
        return out
    for path in _walk(BODY_DIR):
        rec = read_path(path)
        rel = rec.get('path')
        if not rel:
            print(f'warning: {os.path.relpath(path, ROOT)} 缺 path 字段，跳过', file=sys.stderr)
            continue
        out[rel] = {k: v for k, v in rec.items() if k != 'path'}
    return out


def write_record(rel, rec):
    path = os.path.join(BODY_DIR, esc(rel))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as fp:
        json.dump(dict(path=rel, **rec), fp, ensure_ascii=False, indent=2)
        fp.write('\n')
    invalidate()
    return path


def ordered(rec):
    """正文键固定顺序，其余键（含来源加的字段）按原名排在后面。"""
    out = {}
    for k in BODY_KEYS:
        if k in rec:
            out[k] = rec[k]
    for k in FIELDS:
        if k in rec and rec[k] is not None:
            out[k] = rec[k]
    for k, v in rec.items():
        if k not in out and k != 'path' and k not in BODY_KEYS and k not in FIELDS:
            out[k] = v
    return out


def merge(rel, entry):
    """把一条 {date, reviewer, status, ...} 并进该文件的记录，语义同原来 setdefault + 逐条追加。

    fixes 按 (original, corrected) 去重；同一条已存在的 needs_review（corrected
    为 None）就地补上 corrected，而不是另起一条 —— 这是 shidian.py apply 的老规矩。
    """
    rec = load().get(rel) or {'status': 'clean'}
    rec = json.loads(json.dumps(rec))            # 缓存里的对象不就地改
    new_fixes = entry.get('fixes') or []
    if new_fixes or rec.get('fixes'):
        fixes = rec.setdefault('fixes', [])
        known = {(x.get('original'), x.get('corrected')) for x in fixes}
        for x in new_fixes:
            key = (x.get('original'), x.get('corrected'))
            if key in known:
                continue
            old = next((y for y in fixes if y.get('corrected') is None and y.get('original') == x.get('original')), None)
            if old is not None and x.get('corrected') is not None:
                old['corrected'] = x['corrected']
                old['note'] = (old.get('note', '') + f' | resolved: ' + x.get('note', '')).strip(' |')
            elif old is None:
                fixes.append(x)
                known.add(key)
    for k, v in entry.items():
        if k == 'fixes' or k not in rec:
            if k != 'fixes' and v is not None:
                rec[k] = v
        elif k in FIELDS and v is not None:
            rec[k] = v
    rec.setdefault('status', 'clean')
    if 'fixes' in rec and not rec['fixes']:
        del rec['fixes']
    write_record(rel, ordered(rec))
    return rec


def load_one(rel):
    rec = load().get(rel, {})
    return dict(rec)


_CACHE = {}


def load():
    """{键: 记录}，进程内缓存；merge / write_record 后自动失效。"""
    if 'all' not in _CACHE:
        _CACHE['all'] = load_records()
    return _CACHE['all']


def invalidate():
    _CACHE.pop('all', None)


def recompute_stats():
    """从各记录的状态重算 stats；stats 只是索引里的汇总，不参与判重。"""
    recs = load()
    return {
        'total_files': count_data_files(),
        'reviewed': len(recs),
        'clean': sum(1 for r in recs.values() if r.get('status') == 'clean'),
        'fixed': sum(1 for r in recs.values() if r.get('status') == 'fixed'),
        'needs_review': sum(1 for r in recs.values() if r.get('status') == 'needs_review'),
        'out_of_scope': sum(1 for r in recs.values() if r.get('status') == 'out_of_scope'),
        'in_scope_files': sum(1 for r in recs.values() if r.get('status') != 'out_of_scope'),
    }


def count_data_files():
    """仓库里的语料 JSON 个数（口径同 stats.total_files：含 error/，不含 docs/ 等）。"""
    # 口径同 AGENTS.md Step 1 的脚本：只跳过这几个工具目录，含 宋/诗/全宋诗/error/
    skip = {'loader', 'strains', 'images', 'scripts', 'docs', '.git', '.claude', '.github', '.cnb', 'reference'}
    skip_files = {'author', 'rank', 'settings', '表面结构字', 'error', 'fix_progress'}
    n = 0
    for dirpath, dirs, files in os.walk(ROOT):
        dirs[:] = [d for d in dirs if d not in skip and not d.startswith('.')]
        for f in files:
            if f.endswith('.json') and not any(s in os.path.splitext(f)[0] for s in skip_files):
                n += 1
    return n


def write_index():
    """重算 fix_progress.json：stats + 逐文件的 date/reviewer/status。"""
    recs = load()
    reviewed = {}
    for rel in sorted(recs):
        rec = recs[rel]
        entry = {k: rec[k] for k in FIELDS if rec.get(k) is not None}
        entry.setdefault('status', 'clean')
        reviewed[rel] = entry
    index = {
        'version': '2.0',
        'description': DESCRIPTION,
        'stats': recompute_stats(),
        'reviewed': reviewed,
    }
    with open(INDEX, 'w', encoding='utf-8') as fp:
        json.dump(index, fp, ensure_ascii=False, indent=2)
        fp.write('\n')
    return index


# ---------------------------------------------------------------- CLI

def cmd_migrate(args):
    if os.path.isdir(BODY_DIR) and os.listdir(BODY_DIR) and not args.force:
        sys.exit(f'{os.path.relpath(BODY_DIR, ROOT)} 已有内容，迁移不覆盖；确需重做加 --force')
    old = read_path(INDEX)
    os.makedirs(BODY_DIR, exist_ok=True)
    n = 0
    for rel, entry in sorted(old.get('reviewed', {}).items()):
        write_record(rel, ordered(entry))
        n += 1
    invalidate()
    index = write_index()
    print(f'迁移 {n} 条记录 → docs/progress/；索引 stats: {json.dumps(index["stats"], ensure_ascii=False)}')


def cmd_record(args):
    """登记一条审查结论：python3 scripts/progress.py record <路径> --status clean --reviewer 名字 --date 日期。"""
    entry = {'status': args.status, 'reviewer': args.reviewer, 'date': args.date}
    if args.note:
        entry['note'] = args.note
    if args.fix:
        entry['fixes'] = [dict(original=a, corrected=b, note=args.note or '')
                          for a, b in (x.split('=>', 1) for x in args.fix)]
    rec = merge(args.path, entry)
    index = write_index()
    print(f'{args.path}: {rec["status"]} → docs/progress/{esc(args.path)}；'
          f'stats: {json.dumps(index["stats"], ensure_ascii=False)}')


def cmd_index(args):
    invalidate()
    index = write_index()
    print(json.dumps(index['stats'], ensure_ascii=False))


def cmd_check(args):
    """索引与记录是否一致；记录指向的文件/路径是否还合理。"""
    bad = 0
    index = read_path(INDEX)
    recs = load_records()
    for rel, entry in index.get('reviewed', {}).items():
        rec = recs.get(rel)
        if rec is None:
            print(f'索引里有、docs/progress 里没有：{rel}')
            bad += 1
            continue
        for k in FIELDS:
            if entry.get(k) != rec.get(k, 'clean' if k == 'status' else None):
                print(f'{rel}: {k} 不一致 索引={entry.get(k)!r} 记录={rec.get(k)!r}')
                bad += 1
    for rel in recs:
        if rel not in index.get('reviewed', {}):
            print(f'docs/progress 里有、索引里没有：{rel}')
            bad += 1
        if not rel.startswith('_') and not os.path.exists(os.path.join(ROOT, rel)):
            print(f'记录指向的文件不存在（死键？）：{rel}')
            bad += 1
    st, cur = index.get('stats', {}), recompute_stats()
    for k, v in cur.items():
        if st.get(k) != v:
            print(f'stats.{k} 过期：索引={st.get(k)!r} 实际={v!r}')
            bad += 1
    print(f'{"通过" if not bad else f"{bad} 处问题"}')
    return 1 if bad else 0


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest='cmd', required=True)
    m = sub.add_parser('migrate', help='fix_progress.json → docs/progress/（一次性）')
    m.add_argument('--force', action='store_true')
    r = sub.add_parser('record', help='登记一条审查结论')
    r.add_argument('path', help='语料文件相对路径，或 _批次名')
    r.add_argument('--status', required=True, choices=('clean', 'fixed', 'needs_review', 'out_of_scope'))
    r.add_argument('--reviewer', required=True, help='AI model name or GitHub handle')
    r.add_argument('--date', required=True, help='YYYY-MM-DD')
    r.add_argument('--note', help='说明；needs_review 必须写清存疑点')
    r.add_argument('--fix', action='append', metavar='原文=>改后',
                   help='逐条修正记录，可重复；配合 --status fixed')
    sub.add_parser('index', help='重算索引与 stats')
    sub.add_parser('check', help='索引与记录一致性检查')
    args = ap.parse_args()
    return {'migrate': cmd_migrate, 'record': cmd_record, 'index': cmd_index,
            'check': cmd_check}[args.cmd](args)


if __name__ == '__main__':
    sys.exit(main())
