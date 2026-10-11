# 非汉字棋手第 301–320 名身份审查（2026-10-04）

冻结 post7 排名。TEST/PROD 只读事务确认 20 exact raw 各 572 槽，全部 FK 为 NULL；16 个 / 458 槽列精确白名单，4 个 / 114 槽暂缓。

| 排名 | exact raw | 槽位 | 中文规范名 | PROD / TEST 目标 | 决定 |
|---:|---|---:|---|---|---|
| 301 | `OKyu-ch'eol` | 30 | 吴圭喆 | 暂缓 | 暂缓 |
| 302 | `Sekine Naohisa` | 30 | 关根直久 | 3976 / 9773 | 白名单 |
| 303 | `Yasui Senchi Senkaku` | 30 | 安井仙知仙角 | 新建 / 新建 | 白名单 |
| 304 | `Aragaki Takeshi` | 29 | 新垣武 | 4758 / 10548 | 白名单 |
| 305 | `ChoiMyeongHun` | 29 | 崔明勋 | 188 / 189 | 白名单 |
| 306 | `Kojima Shunichi` | 29 | 小岛春一 | 新建 / 新建 | 白名单 |
| 307 | `Kuwahara Shusaku` | 29 | 本因坊秀策 | 4 / 4 | 白名单 |
| 308 | `Sato Machiko` | 29 | 佐藤真知子 | 3901 / 9698 | 白名单 |
| 309 | `SatoSunao` | 29 | 佐藤直男 | 3900 / 9697 | 白名单 |
| 310 | `Shoji Kazuko` | 29 | 尚司和子 | 4444 / 10235 | 白名单 |
| 311 | `Sumino Takeshi` | 29 | 炭野武司 | 暂缓 | 暂缓 |
| 312 | `Yasui Shuntetsu Senkaku` | 29 | 安井春哲仙角 | 新建 / 新建 | 白名单 |
| 313 | `Amano Masafumi` | 28 | 天野雅文 | 4268 / 10063 | 白名单 |
| 314 | `Ishii Shinzo` | 28 | 石井新藏 | 暂缓 | 暂缓 |
| 315 | `Koyama Yasuo` | 28 | 小山靖男 | 4411 / 10202 | 白名单 |
| 316 | `Sakaguchi Sentoku II` | 28 | 坂口仙得（二世） | 新建 / 新建 | 白名单 |
| 317 | `Yamashita Yorimoto` | 28 | 山下顺源 | 4489 / 10280 | 白名单 |
| 318 | `Cho Hunhyun` | 27 | 曹薰铉 | 暂缓 | 暂缓 |
| 319 | `Kadono Matsunosuke` | 27 | 本因坊丈和 | 3 / 3 | 白名单 |
| 320 | `KobayashiKoichi` | 27 | 小林光一 | 82 / 82 | 白名单 |

暂缓项：
- `OKyu-ch'eol`：韩国棋院直接列吳圭喆；目录有吴圭哲与吴圭喆两 ID，先确认合并归属。
- `Sumino Takeshi`：CWI 同行列炭野武司=炭野恒広/Sumino Takeshi；目录有武司5437/11212、恒広5436及恒广5435等多 ID，先去重。
- `Ishii Shinzo`：CWI 同行列石井新蔵/Ishii Shinzo；目录有石井新蔵5635/11408和石井新藏5636/11409两个 ID，先去重。
- `Cho Hunhyun`：目录存在曹薰铉46与曹薰炫4814/10601两个 ID；先合并目录。

逐条来源与注释见[审查 JSON](kifu-player-nonhan-ranks-301-320-review-2026-10-04.json)，可导入项见[精确白名单 JSON](kifu-player-nonhan-ranks-301-320-exact-allowlist-2026-10-04.json)。未写数据库。
