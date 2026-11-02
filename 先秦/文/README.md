先秦/文/
========

从「诗」里拆出来的子史佛经医书：一部书一个 JSON，共 34 部。
2026-10 之前它们混在 `先秦/诗/poet.xianqin.json` 里，文体、书名、作者三样全不对，
拆分过程见 [`docs/先秦拆分.md`](../../docs/先秦拆分.md)。

## 文件与书名

| 文件 | 书 |
| --- | --- |
| `zuozhuan.json` | 左传 |
| `guoyu.json` | 国语 |
| `zhuangzi.json` | 庄子 |
| `xunzi.json` | 荀子 |
| `mozi.json` | 墨子 |
| `hanfeizi.json` | 韩非子 |
| `guanzi.json` | 管子 |
| `shangjunshu.json` | 商君书 |
| `lushichunqiu.json` | 吕氏春秋 |
| `yinwenzi.json` | 尹文子 |
| `guiguzi.json` | 鬼谷子 |
| `sunzibingfa.json` | 孙子兵法 |
| `sanshiliuji.json` | 三十六计 |
| `shanhaijing.json` | 山海经 |
| `yanzichunqiu.json` | 晏子春秋 |
| `zhouli.json` | 周礼 |
| `yizhoushu.json` | 逸周书 |
| `shangshu.json` | 今文尚书 |
| `gongyangzhuan.json` `guliangzhuan.json` `chunqiuguliangzhuan.json` | 公羊传、穀梁传 |
| `liji.json` | 礼记 |
| `zhouyi.json` | 周易 |
| `daodejing.json` | 道德经 |
| `huangdineijing.json` | 黄帝内经 |
| `sishierzhangjing.json` `jingangjing.json` `fahuajing.json` `dizangjing.json` `yuanjuejing.json` `weimojiejing.json` | 佛经六种 |
| `songyu.json` `qinwen.json` `gushi.json` `shangtang.json` | 零篇（宋玉、李斯《谏逐客书》、荆轲《易水歌》、商汤《盘铭》） |

## 道德经

`daodejing.json` 2026-11 依 repo 内 [`reference/道德經.txt`](../../reference/道德經.txt) 整本重出：
81 章一章一条，`title` 作 `道德經（第一章）`，`author` 老子，正文改繁体、按章次排齐。
底本里的夹注（「一作『…』」与第一章的句读说明）不是正文，移到该条 `note` 字段。
过程见 [`docs/四书重出.md`](../../docs/四书重出.md)。
