先秦/文/
========

从「诗」里拆出来的子史佛经医书：一部书一个 JSON。2026-11 起 33 部 ——
《左传》已整份删除，改由 `史书/春秋左氏传/zuozhuan.json` 依底本整本承担（见
[`docs/春秋左氏传重建.md`](../../docs/春秋左氏传重建.md)）。
2026-10 之前它们混在 `先秦/诗/poet.xianqin.json` 里，文体、书名、作者三样全不对，
拆分过程见 [`docs/先秦拆分.md`](../../docs/先秦拆分.md)。

## 文件与书名

| 文件 | 书 |
| --- | --- |
| `guoyu.json` | 国语（《左传》见 `史书/春秋左氏传/`） |
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
| `shangshu.json` | 尚书 |
| `gongyangzhuan.json` `guliangzhuan.json` `chunqiuguliangzhuan.json` | 公羊传、穀梁传 |
| `liji.json` | 礼记 |
| `zhouyi.json` | 周易 |
| `daodejing.json` | 道德经 |
| `huangdineijing.json` | 黄帝内经 |
| `sishierzhangjing.json` `jingangjing.json` `fahuajing.json` `dizangjing.json` `yuanjuejing.json` `weimojiejing.json` | 佛经六种 |
| `songyu.json` `qinwen.json` `gushi.json` `shangtang.json` | 零篇（宋玉、李斯《谏逐客书》、荆轲《易水歌》、商汤《盘铭》） |

## 孙子兵法

`sunzibingfa.json` 13 篇，`title` 作 `孙子兵法·始计篇` 这样带书名的形式（2026-11 由 `始计篇` 补书名前缀）。
这 13 条是从 `poet.xianqin.json` 拆出来的，题名原来只有篇名，脱离了目录就认不出是哪部书；
同目录的《三十六计》（`三十六计·勝戰計·瞞天過海`）、《山海经》（`山经·东山经`）、
《道德经》（`道德經（第一章）`）早已如此。正文一字未动。

## 尚书与周易

`shangshu.json`、`zhouyi.json` 2026-11 依 repo 内 [`reference/尚书.txt`](../../reference/尚书.txt)、
[`reference/周易.txt`](../../reference/周易.txt) 整本重出：

| 文件 | 条数 | 题名 | 备注 |
| --- | --- | --- | --- |
| `shangshu.json` | 79 | `尚書·虞书·尧典`（虞书 6、夏书 6、商书 17、周书 50） | 底本含今古文五十八篇；19 条亡篇只有书序、没有正文，照录书序并注明 |
| `zhouyi.json` | 64 | `周易·乾卦` | 只收经文六十四卦；底本没有十翼，不收《系辞》等 |

原文一字未改：只拼回底本折行的两段，并按 ERRATA 改正 26 处（尚书）与 11 处（周易）定案的
讹字与缺字，逐条依据见 [`docs/尚书周易重建.md`](../../docs/尚书周易重建.md)。

## 道德经

`daodejing.json` 2026-11 依 repo 内 [`reference/道德經.txt`](../../reference/道德經.txt) 整本重出：
81 章一章一条，`title` 作 `道德經（第一章）`，`author` 老子，正文改繁体、按章次排齐。
底本里的夹注（「一作『…』」与第一章的句读说明）不是正文，移到该条 `note` 字段。
过程见 [`docs/四书校对.md`](../../docs/四书校对.md)。
