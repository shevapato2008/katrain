# Miyasaka Shinji 字形更正（2026-10-04）

`Miyasaka Shinji` 在冻结清单第 171 名，共 72 槽；TEST/PROD 两库只读复核时均未关联。原 161–180 审查与白名单误采用 CWI [升段表](https://homepages.cwi.nl/~aeb/go/misc/progression.html) 的「宮坂莱二」。

日本棋院官方 [创立 90 周年照片说明](https://www.nihonkiin.or.jp/special/90anniversary/message/index.html) 列 1924 年创立时的棋手「宮坂寀二」；日本棋院官方 [《棋道web》历史文章](https://note.com/nihonkiin/n/n679bb4de0ea7) 同样列「宮坂寀二六段」。**正确汉字是「宮坂寀二」**，简体中文默认名可写「宫坂寀二」。CWI 的「莱」是不同字，不能作为正式目录名；「宷」也不同于日本棋院使用的「寀」。

本补注只修正身份研究，未更改旧白名单 JSON，避免下游正在使用时发生竞态。迁移时须排除旧白名单里的该 exact raw，按更正姓名重建并重新双库 dry-run；未写数据库。
