# AGENTS.md — chinese-poetry Dataset Maintenance

Instructions for AI agents contributing to this dataset. Currently one active task:

---

## Task: Fix Typos & Garbled Characters (乱码修复)

Community task: systematically review all JSON poetry files and fix typos and garbled characters. Progress is tracked in `fix_progress.json` so contributors (human or AI) can pick up where others left off.

---

### Directory layout

顶层是 **14 个朝代目录**（与 `dynasties/dynasties.json` 的 `name` 一一对应）加一个 `汇编/`：

```
先秦 汉 三国 晋 南北朝 隋 唐 五代十国 宋 元 明 清 近现 当　汇编
```

朝代下面按「一部书一个目录」或「诗 / 词 / 文」体裁目录排，选本不并进总集：

```
先秦/{诗经,楚辞,论语,孟子,大学,中庸,文/（zuozhuan.json 等 34 部子史佛经）}
汉/{曹操诗集,古诗源/汉魏六朝诗.json,诗/poet.han.json,词/ci.han.json}
三国/ 晋/ 南北朝/ 隋/（同上，各 诗/poet.*.json、词/ci.*.json；隋只 18 首，见 docs/隋拆分.md）
唐/{诗/全唐诗/（poet.tang.*，选本并进这里作 tags）,词/ci.tang.json}
五代十国/{词/五代诗词/{huajianji,nantang},诗/poet.wudai.json}
宋/{诗/全宋诗/（poet.song.*）,宋词/（ci.song.*）,诗/poet.song.json,词/ci.song.json,诗/古诗源·宋诗.json,诗/千家诗/}
元/{元曲/yuanqu.json（元人诗词曲的唯一总集）,诗/poet.yuan.json}
明/{诗/{poet.ming.json,古诗源·明诗.json},词/ci.ming.json,幽梦影/}
清/{诗/{poet.qing.json,古诗源·清诗.json,纳兰诗/},词/ci.qing.json（含纳兰词，tags 标记）}
近现/现代诗.json　当/{poet.dang.json,ci.dang.json}
汇编/{古文观止/（古文观止.json、12 卷、古文观止·补.json）,课本选目/（原 先秦/课外经典/）,
      诗文总集/{乐府诗集,昭明文选},蒙学/（三字经…增广贤文 10 种）}
```

`诗/poet.*`、`词/ci.*` 是 `历代/` 拆出来的补录，**`poet.*` 里诗与文混放**（体裁只决定进 `诗/` 还是 `词/` 目录）。
选本不占目录：宋词三百首、唐诗三百首（两份，见 `docs/唐诗三百首并入.tsv`）、水墨唐诗、纳兰词都并进总集作 `tags`，目录已删。
`先秦/文/` 是从 `先秦/诗/poet.xianqin.json` 里拆出来的子史佛经（原文件 1311 条只有个位数是诗），
见 [docs/先秦拆分.md](docs/先秦拆分.md)。

- **哪个朝代归哪个目录**：作者朝代（`authors/authors.json` 的 `dynasty`）说话。春秋战国、秦、商、上古 → `先秦`；
  辽、金 → `宋`；1912—1949 年出生的作者 → `近现`；1949 年以后 → `当`。`晋` 不再细分东西晋，`南北朝` 不分南北。
- 跨代、又没有单一主时段的书放 `汇编/`：《古文观止》（周文至明文）、课本选目（原 `先秦/课外经典/`，
  按主题编的课本选目，不是一个集子名）、《乐府诗集》《昭明文选》（2026-10 由 `先秦/诗文总集/` 移入）、
  蒙学一组书（2026-10 由 `先秦/蒙学/` 移入，成于梁至清，没有一部是先秦的）。
- 跨代但能指出主时段的选本按主时段落位：《千家诗》唐宋各半、编定于南宋 → `宋/诗/千家诗/`；
  《古诗源》先秦部分已并回《诗经》《楚辞》，其余 12 首在 `汉/古诗源/`。
- `先秦/论语`、`先秦/孟子`、`先秦/大学`、`先秦/中庸`、`明/幽梦影`
  是按「作者所处时代占多数」就近收的，本身跨代；它们的归属写在这份文件与 README 里，不靠目录名判断。

一件作品只留一份正文：选本与总集逐字相重的，删选本那一份；《古诗源》摘句的《诗经》《楚辞》篇目已删，
只保留 `诗经/shijing.json`、`楚辞/chuci.json` 的全文版本。

- 路径改了，正文没改：提交 PR 时不要顺手格式化被移动的文件。
- `loader/datas.json` 是数据读取入口，dataset 的 key 不变，只改 `path`；新增目录要在那里注册。
- `scripts/check_structure.py` 判体裁看文件名前缀（`poet.*` 诗、`ci.*` 词），不看顶层目录名；`poet.*` 里混着文，句长类检查会报噪音。

---

### Step 1 — Find the next 5 files to review

Files are processed in **priority order**: known-issue files first, then alphabetically by path.

Run this script to get your next batch:

```python
import os, json, re

ROOT = os.path.dirname(os.path.abspath('fix_progress.json'))
SKIP = {'author', 'rank', 'settings', '表面结构字', 'error', 'fix_progress'}
SKIP_DIRS = {'loader', 'strains', 'images', 'rank', 'error', 'authors', 'dynasties', 'anthologies', 'scripts', 'docs', '.git', '.claude', '.github', '.cnb', 'reference'}  # 宋/诗/全宋诗/error is out of scope
CYRILLIC_GREEK = re.compile(r'[Ѐ-ӿͰ-Ͽ]')

# Build full file list (alphabetical)
all_files = []
for dirpath, dirs, filenames in os.walk(ROOT):
    dirs[:] = sorted([d for d in dirs if d not in SKIP_DIRS])
    for f in sorted(filenames):
        if not f.endswith('.json') or any(s in f for s in SKIP):
            continue
        rel = os.path.relpath(os.path.join(dirpath, f), ROOT)
        all_files.append(rel)

with open(os.path.join(ROOT, 'fix_progress.json'), 'r', encoding='utf-8') as fp:
    progress = json.load(fp)

reviewed = set(progress.get('reviewed', {}).keys())
pending = [f for f in all_files if f not in reviewed]

# Priority 1: files with confirmed Cyrillic/Greek characters
priority = []
normal = []
for rel in pending:
    fpath = os.path.join(ROOT, rel)
    try:
        content = open(fpath, encoding='utf-8').read()
        if CYRILLIC_GREEK.search(content):
            priority.append(rel)
        else:
            normal.append(rel)
    except Exception:
        normal.append(rel)

queue = priority + normal
print(f"Total: {len(all_files)} | Reviewed: {len(reviewed)} | Pending: {len(pending)}")
print(f"Priority (Cyrillic/Greek detected): {len(priority)}")
print("\nNext 5 files:")
for f in queue[:5]:
    tag = " ⚠ Cyrillic/Greek detected" if f in priority else ""
    print(f"  {f}{tag}")
```

Pick the first 5 from the output.

---

### Step 2 — Review each file

For each file, read it fully and check for the following:

#### 2a. Cyrillic / Greek garbled characters (highest priority)

Encoding errors where non-Chinese characters replaced Chinese ones. Always wrong in poetry text.

Known offenders in this dataset:

| Wrong | Unicode | Likely correct | Confirmed example                      |
|-------|---------|----------------|----------------------------------------|
| и     | U+0438  | 婵             | 风月正и娟 → 风月正婵娟                        |
| б     | U+0431  | 婵             | 风月正б娟 → 风月正婵娟                        |
| Н     | U+041D  | 潺             | НН绕城萦市 → 潺潺绕城萦市                      |
| ь     | U+044C  | 枝             | 一ь杨柳作腰肢 → 一枝杨柳作腰肢                    |
| Α     | U+0391  | 秩             | 七Α开颜 → 七秩开颜                          |
| Ι     | U+0399  | 徽             | Ι州 → 徽州                              |
| Θ     | U+0398  | 种             | Θ瓜邵平 → 种瓜邵平                          |
| с     | U+0441  | □ (lacuna)     | 只守伯禽法，с野万云烟 → □野万云烟 (《全宋词》底本缺字) |
| М     | U+041C  | 剉 / 挫          | 斋时М → 斋时剉；眼М了 → 眼挫了               |
| Λ     | U+039B  | ?              | determine from context + sources below |

The same symbol does not always map to the same character (и and б both → 婵; Θ → 种 but Θ迁 → 鉏麑), so verify every occurrence against a source.

Japanese kana and bopomofo (e.g. け然 → 翛然, 荼コ → 荼蘼, ゐ惶 → 恓惶, 不会ㄐ → 不会搊) are the same kind of garble. The title separator `・` (U+30FB) is legitimate.

**Detection**: regex `[Ѐ-ӿͰ-Ͽ]` (Cyrillic/Greek) and `[぀-ヺー-ヿ㄀-ㄯㆠ-ㆿ]` (kana/bopomofo). `python3 scripts/check_structure.py` runs these and other structural checks over the whole dataset, including `title` fields (元曲 titles contain body text).

**Correction approach** (in order of confidence):
1. Obvious from immediate context (single character gap, clear word/phrase)
2. Look up the poem by title/author in authoritative sources (see §Authoritative Sources)
3. Infer from meter (平仄) and rhyme scheme
4. If still uncertain → mark `needs_review`, do not guess

#### 2b. PUA characters (U+E000–U+F8FF)

`{...}` notation like `{疒}`, `{厓厂=}` = **intentional** placeholders for rare unencoded characters. Leave them alone.

Bare PUA chars outside `{}` in sentence body may be genuine errors — check context and sources before changing.

#### 2c. General typos (错别字)

Typo detection requires assessing your own confidence before acting. Apply the following tiers:

**Tier 1 — Fix directly**

You can name the work, author, and the correct line from your training data. Fix the character and cite the source in the `note` field.

Example: a line reads "床前明月关" → you recognize 李白《静夜思》, the line is "床前明月光" in every edition. Fix it.

**Textbook wording ≠ correct wording.** Many lines you "know" come from modern anthologies that changed the old text. 白居易《琵琶引》 reads "枫叶荻花秋**索索**" in 《全唐诗》 and Song-era sources (黄庭坚《山谷外集诗注》, 《舆地纪胜》); the familiar "秋瑟瑟" comes from Ming–Qing anthologies. That is an edition variant (异文), not a typo — do not change it. Fix only when the dataset's reading is attested in **no** edition; when in doubt, check 识典古籍 for older editions and mark `needs_review`.

**Tier 2 — Mark `needs_review`, do not fix**

The line reads strangely or a character seems wrong, but you cannot recall the authoritative text with confidence. Add a `needs_review` entry describing what looks suspicious and why. Do not guess.

**Tier 3 — Skip typo checking entirely**

You do not recognize the poem at all. Only apply the mechanical scans (Cyrillic/Greek, PUA). A missed error is safer than a hallucinated "fix".

The threshold in plain terms: **if you are not willing to stake your confidence on it, do not change it.**

Common typo patterns when Tier 1 applies:
- Look-alike (形近字): 日/曰，己/已/巳，戊/戌/戍，土/士，末/未
- Sound-alike (音近字): 关/光

#### 2d. Do not change

- `·` (U+00B7) in titles like `《宋史·乐志》` — standard Chinese punctuation
- Traditional/simplified variants — intentional
- Archaic character forms

---

### Step 3 — Authoritative sources for verification

When context alone is insufficient, look up the poem in these sources (in order of preference):

| Source | URL | Notes |
|--------|-----|-------|
| 搜韵网 | https://sou-yun.cn | Comprehensive poetry search with rhyme annotation; good for Tang/Song |
| 古文岛 | https://www.guwendao.net | Covers most canonical works; good full-text search |
| 汉典 | https://www.zdic.net | Character-level dictionary; use for verifying individual characters |
| 识典古籍 | https://www.shidianguji.com | Full-text search over scanned editions (OCR + page images), cites book / 卷 / page; independent of web-crawled texts. Best source for 元曲/散曲 (《雍熙乐府》《词林摘艳》《盛世词林》 etc.). Search URL: `https://www.shidianguji.com/search/<query>` (simplified display) or `https://www.shidianguji.com/zh/search/<query>` (traditional display); texts are mostly unpunctuated, so search a 4–6 character run without punctuation. Both displays are automatic conversions, not the original glyphs: simplified display turns rare chars into 类推简化 forms (搊→𫼝, 篘→𫇴, 紞→𬘘), traditional display can over-convert (卜→蔔). Use the traditional display to read a rare character, then write it in the form this dataset already uses (e.g. 䕷 not 𧃲, 裀 not 䄄) |

Search by: poem title (`rhythmic` field) + author (`author` field). Compare the suspect line against the authoritative version character by character.

**Caveat for 元曲**: 古文岛/古诗文网's 元曲 texts largely share this dataset's crawled source and often carry the same garbled characters (e.g. `阁门珠路Λ`). It sometimes lists a second, proofread version of the same piece — use only a version without the garble, and prefer 识典古籍 when the two disagree.

If the authoritative source shows a different character, that is strong evidence for a fix. Record the source URL in the `note` field of your fix entry.

If neither source covers the poem, mark it `needs_review` — do not infer from uncertain sources such as crowdsourced wikis or link-aggregator sites.

---

### Step 3b — Batch tools (dataset-wide, alternative to the per-file loop)

Per-file review cannot scale to rare poems you do not recognize. These tools fix whole categories of defects with 识典古籍 as evidence, and leave every decision reviewable.

| Tool | Purpose |
|------|---------|
| `scripts/check_structure.py` | Scan the whole dataset: garbles (Cyrillic/Greek, kana/bopomofo, box-drawing, U+FFFD, bare PUA, ASCII residue), `□` gaps, line-length and 词牌 anomalies. Report only. |
| `scripts/collate.py` | Whole-corpus, sentence-by-sentence collation against 识典古籍, run in small daily batches by the scheduled workflow `.github/workflows/collate-songci.yml`; humans review its `review.tsv` artifact. 宋词 is in progress — see `docs/宋词对勘.md`. |
| `scripts/twin_collate.py` | Collate anthologies (花间集, 南唐, 唐诗三百首, 千家诗, 水墨唐诗) against the same poems in 全唐诗/宋词; one-char differences judged on 识典古籍, reviewed in `review.tsv`, closed items kept in `docs/小合集互校.applied.json`. Read its docstring for review lessons before deciding. |
| `scripts/merge_anthologies.py` | Merge Tang anthologies into 全唐诗/poet.tang.* (tags + `prologue`) and drop poet.tang copies of 花间集/南唐 词; dry-run by default, `--apply` writes `docs/唐诗去重.tsv`. Already applied — rerun only if those files are re-imported. |
| `scripts/shidian.py` + `scripts/shidian/search.mjs` | Evidence pipeline: `build` → search 识典古籍 → `analyze` → review `review.tsv` → `apply`. |
| `scripts/split_dynasty.py` | Split `历代/` into the per-dynasty directories by author dynasty and genre (dry-run by default; `--apply` writes and emits `docs/历代拆分.tsv`). Already applied — `历代/` no longer exists |
| `scripts/check_anthology.py` | Align 选本 目次 (`anthologies/*.json`) with the records carrying that anthology's tag; reports 混入 / 漏收 / 重覆 into `docs/选本对齐.tsv`. See `docs/选本对齐.md`. |

```bash
pip install opencc-python-reimplemented
(cd scripts/shidian && npm install && npx playwright install chromium)
W=/tmp/sd_kana                                   # work dir — never inside the data directories
python3 scripts/shidian.py build --check kana_bopomofo --work $W
node scripts/shidian/search.mjs $W/queries.json $W/results.jsonl   # add --cdp http://127.0.0.1:9333 to reuse an open browser
python3 scripts/shidian.py analyze --work $W     # writes $W/review.tsv
# review: decision column = accept / reject / verified / or type the correct text yourself
python3 scripts/shidian.py apply --work $W --reviewer <model or handle> --date YYYY-MM-DD [--record-pending]
```

Rules built into `analyze` (learned the hard way — keep them if you change it):
- **Garbles almost always replaced a character outside GB2312.** Use this to rank candidates: non-GB2312 candidates first; a GB2312 candidate (often OCR noise) is accepted only with ≥2 books and ≥6 characters of matching context. Confirmed exceptions: 裔、綸、撲、峰、楹 — and edition variants such as 纤纤 vs 攕攕; flag these in the note.
- **The same garble symbol or PUA code point can stand for different characters** in different files; each occurrence needs its own evidence.
- **`□` gaps** are mostly lacunae in the base text. Filling one from another edition needs ≥2 independent books; if a book shows a box-like OCR char (`口 囗 丶 〇`) at the same spot, the source has the same gap — do not fill.
- **Compare in simplified form** (`t2s` on both sides) so variants like 峯/峰 do not hide matches, but **write back with the dataset's own glyphs**: change only the inserted/deleted character, and use the form the dataset already uses (e.g. 搊 not 𫼝, 䕷 not 𧃲, 殢 not 𣨼).
- **Line edits next to garbage are not line edits**: `noisy` status means the sentence touches a residue/garble — replace that token instead of inserting a character.
- `missing_char` is slow (thousands of queries); expect ~4 s per query, run overnight, and reruns resume where they stopped.

---

### Step 4 — Fix and update progress

1. **Edit the file**: change only the erroneous characters, nothing else.

2. **Update `fix_progress.json`** — add each reviewed file to the `reviewed` object. Keep it to the review record only; the fix log itself is not kept (the git commit is the record, and `scripts/check_structure.py` re-checks the whole dataset any time):

```json
{
  "reviewed": {
    "宋/宋词/ci.song.13000.json": {
      "date": "YYYY-MM-DD",
      "reviewer": "<AI model name or GitHub handle>",
      "status": "clean"
    },
    "元/元曲/yuanqu.json": {
      "date": "YYYY-MM-DD",
      "reviewer": "<AI model name or GitHub handle>",
      "status": "fixed",
      "fixes": [
        { "original": "Θ瓜邵平", "corrected": "种瓜邵平", "note": "Greek Θ → 种; verified on 识典古籍" }
      ]
    }
  }
}
```

Status values:
- `clean` — no issues found, or every issue found was corrected (the `fixes` list may be empty)
- `fixed` — same as `clean` for a file that had corrections; the entries you list are what the commit fixed
- `needs_review` — corrections are still outstanding and worth tracking: either the file has not been collated line by line (batch records like `_新增选本`, `_目录重构：按朝代分层`), or a specific known defect is open. Rare-character lacunae (`□`, bare PUA) that no evidence can settle are **not** tracked here — `scripts/check_structure.py` reports them live
- `out_of_scope` — not part of the published dataset (currently all of `宋/诗/全宋诗/error/`, records the upstream project flagged as defective and `loader/datas.json` excludes); kept for reference, not counted as pending

Do not accumulate per-character repair history in this file: entries for completed fixes are deleted once the character is fixed in the dataset. Keep only what is still actionable.

Also update the top-level `stats` counters (`reviewed`, `clean`, `fixed`, `needs_review`, `out_of_scope`, `in_scope_files`). The batch tools recompute them from file statuses automatically.

**Never record a file as `clean` unless you actually read it.** A file that was only converted / split / deduplicated is *not* reviewed. Bulk imports that have not been collated line by line are registered as a single `reviewed["_<批次名>"]` entry with `status: needs_review` and a note saying what was and was not checked (see `_新增选本`, the 7 anthologies imported from poem-wechat); split it into per-file entries only as the collation completes. That keeps `stats.total_files` equal to the number of JSON files actually in the repo.

---

### Step 5 — Report

After the batch, summarize in the PR / issue comment:
- Files processed and their status
- What was fixed, with the evidence for anything non-obvious
- Any `needs_review` items still open and why
- `python3 scripts/check_structure.py` counts before / after, so regressions stay visible

**Submit a PR.** Commit your changes on a new branch and open a pull request against `develop`; the maintainer reviews and merges it.
