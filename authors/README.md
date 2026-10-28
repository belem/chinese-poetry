作者索引
========

全库通用的作者小传索引，覆盖 2402 位作者。与各总集自带的作者表并存：

- `authors/authors.json` — 本目录，按（朝代, 姓名）排序的通用索引
- `全唐诗/authors.tang.json`、`全唐诗/authors.song.json` — 《全唐诗》《全宋诗》原有作者表
- `宋词/author.song.json` — 《全宋词》原有作者表

原有三份各管一个总集、字段还互不相同，跨目录查不着人；这份索引补上这一层，
语料与介绍分开，不混放在诗集里。

## 数据形式

```json
[
  {
    "name": "苏轼",
    "dynasty": "宋",
    "birth_year": "1037年",
    "death_year": "1101年",
    "intro": "北宋文学家、书画家，唐宋八大家之一，眉州眉山（今属四川）人……"
  }
]
```

| 字段 | 说明 |
| --- | --- |
| `name` | 姓名 |
| `dynasty` | 朝代，与本目录 `dynasties/dynasties.json` 的 `name` 对应 |
| `birth_year` / `death_year` | 生卒年，原样保留源数据的「1037年」这种写法；不详为空串 |
| `intro` | 小传 |

## 来源

`reference/mit_licence_haitangshishe`（MIT 授权），由 `scripts/haitangshishe/import.py` 生成。
