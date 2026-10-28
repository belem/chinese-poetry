朝代概述
========

18 个朝代（上古至当代）的概述，供跨目录检索与展示使用。

## 数据形式

```json
[
  {
    "name": "宋",
    "start_year": 960,
    "end_year": 1279,
    "intro": "宋朝是中国历史上承五代十国、下启元朝的时代，分为北宋和南宋……"
  }
]
```

| 字段 | 说明 |
| --- | --- |
| `name` | 朝代名，与 `authors/authors.json` 的 `dynasty` 一致 |
| `start_year` / `end_year` | 起止年，整数，公元前为负数 |
| `intro` | 概述 |

按 `start_year` 升序排列。

## 来源

`reference/mit_licence_haitangshishe`（MIT 授权），由 `scripts/haitangshishe/import.py` 生成。
