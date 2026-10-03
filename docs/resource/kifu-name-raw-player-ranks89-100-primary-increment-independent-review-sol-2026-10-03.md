# Ranks 89–100：五格来源增量独立审核

2026-10-03，审核员 `/root/freq41_60_95_review_sol`。审核 [Luna 增量提案](kifu-name-raw-player-ranks89-100-primary-increment-luna-2026-10-03.md)，输入 manifest SHA-256 `841278eaa781a94f5a9ffb7bff610041aea1cd5a73b569a5f645840e8bbe4553`。

**本轮 5 PASS、0 HOLD；原 21 PASS 保留，合计 26/60 PASS、34 HOLD。** 合并各语言 PASS/HOLD：cn 7/5、tw 4/8、jp 2/10、ko 11/1、en 2/10。

| 原名 | 语言 | 精确来源姓名 | 结论 | 实际正文与来源人物对应 |
| --- | --- | --- | --- | --- |
| 李钦诚 | en | LI Qincheng | PASS | OCA/Hangzhou 英语 Go 运动员页，DOB `20 Oct 1998`，匹配已审 profile 1282 / `1998-10-20`；正文明确中国围甲 MVP、职业俱乐部语境 |
| 吴侑珍 | en | OH Yujin | PASS | 同一赛事英语 Go 女队运动员页，DOB `11 Jun 1998`，匹配已审 KBA/GoRatings 1315 / `1998-06-11` |
| 吴侑珍 | tw | 吳侑珍 | PASS | 海峰 2017 IMSA 台繁正文列韩国女团及个人金牌；KBA 10000736 正文也列同届团体、个人夺冠 |
| 睦镇硕 | tw | 睦鎮碩 | PASS | 海峰 2018 正文明确韩国国家队总教练九段；KBA 10000093 履历列国家队主教练 2017–2023，对应 profile 121 / `1980-01-20`；2026 海峰正文另印同名及前教练身份 |
| 彭立尧 | tw | 彭立堯 | PASS | 海峰 2024 应氏杯正文明确对手、职业八段；已审 profile 993 / `1992-01-14` 的留存棋局表也列 2024-07-03 负许皓鋐 |

8 份正文的原字节 hash/长度全部匹配 manifest。两份 athlete 页实际为 `en-us`；三份台湾报道及辅助台湾报道为 `zh-tw`，姓名在真实正文而非网址/导航中。英文大小写 `LI`、`OH` 原样保留；职衔/段位没有并入显示姓名。来源为亚运会正式参赛档案与海峰职业围棋报道；[OCA 官方杭州赛事记录](https://oca.asia/games/2-hangzhou-2023.html)亦列第19届及 Weiqi 项目。候选依据仍为本包已经冻结的 athlete 正文。

**三个 tw 报道没有打印 DOB。** 表中的 DOB 来自此前已签来源人物 crosswalk；新增身份对应以具体成绩、教练任期和对手记录补强，不声称报道本身提供出生日期，更不把某个人物的译名批准外推到同名 raw 棋谱。

## 辅助 metadata 修正：保留 HOLD

两个来源姓名格 PASS，但不批准提案 memo 的错误辅助字段，亦不改生产者文件：

- 吴侑珍第二金牌引句实际为 **`金牌 【韓國】吳侑珍`**；memo 写成 `金牌 〖韓國〗吳侑珍`。第一处 `金牌 韓國隊(崔精/吳侑珍)` 正确，姓名本体也正确。
- 睦镇硕 2018 捕获时间以 manifest 为 **`2026-10-03T01:45:18.256045+00:00`**；memo 表格的 `.256075` 应修正。正文 SHA-256 `b964cef07106b9c0db4d25fb9141d9d1edab1d542f1fc47087829a720cde1395` 正确。

另两条英文线索仍 HOLD，不增第六/第七格。日本棋院 `Li He` 报道有真实英语职业赛事语境，但本轮未补直接 DOB/profile 对应。BGA PDF 实际提到 young Chinese with professional grades 与 `China’s Lingyi Gu`；HOLD 的限制是该名字的直接人物对应，而非“没有职业语境”。这不构成英文姓名不存在的结论。

## 受控记录

`~/.local/share/kifu-name-audit/2026-10-03/raw-player-ranks89-100-primary-increment-independent-review-sol/`（0700，文件 0400）包含 5 条独立来源签署、合并 60 格矩阵、8 份正文、原 manifest、此前签署依赖、实际正文提取、metadata 修正/held lead 限制、review record 与 manifest。

- 新增格 canonical SHA-256：`227043f2ffdff35ee259862ae2520a890b10fe7ecc6149c5997dd415264f89b1`。
- review-record SHA-256：`8cd6711b9529be5594cdba6ff5823fc34b7483e45e3ff34e332affc4cafa506a`。
- manifest SHA-256：`b613a7b5d11a9df414089847fb9c28ca7a99a5a00ff9e5df3c6095eb8280bcab`。

只签来源姓名事实；raw 适用性、人物 FK、alias、数据库应用批准均为零。未改生产者材料、代码或数据库，未提交；独立署名与内容 hash 不是密码学签名。
