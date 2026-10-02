# 李昌镐 ID 143：2010–2011 韩国联赛 15 槽位独立身份复核

审核者 `/root/lee_league_2010_11_identity_sol`；实际配置模型 **`gpt-6-sol`**。本次只审核[来源研究](kifu-name-lee-143-korean-league-2010-2011-source-research-2026-10-02.md)标为“进入下一轮审核”的 **15 个精确 `album_id/side`**；此前 9 个 HOLD 未纳入。结论：**15 个身份事实批准，0 个暂缓**。这是有限对局身份决定，不是已冻结导入包的签名，也不批准任何语言名称或数据库写入。

| 赛季 | 批准的精确槽位 |
| --- | --- |
| 2010 | `74958/black`、`84074/black`、`83412/black`、`50340/black`、`98013/black`、`98023/black` |
| 2011 | `98039/black`、`28261/white`、`89846/white`、`98043/black`、`98050/black`、`27182/white`、`98054/white`、`87568/black`、`44125/black` |

逐条重新阅读 [2010 联赛成绩表](https://gotoeveryone.k2ss.info/news/kr/kl/8/)与 [2011 联赛成绩表](https://gotoeveryone.k2ss.info/news/kr/kl/9/)中的日期、双方、执色、结果和赛段；表格未给这些对局明确轮次。从 `home-ubuntu` 只读获取 15 份源 SGF，检查根属性中的双方、日期、结果、赛事和段位；全部 15 份经现有 `SGF.parse_sgf(...).sgf()` 规范化后的 SHA-256 均与预备清单一致，且根属性与固定生产 inventory 对应行一致。拟关联槽位旧 FK 均为空，均非重复盘。韩国棋院的[棋手档案](https://m.baduk.or.kr/record/gisa_info.asp?PRPL_CODE=10000001)标识 `10000001` 为九段 `이창호 (李昌鎬)`；先前有限身份审核已对照其中文写法与 `player:143`。所读目录快照中 `143=李昌镐` 精确唯一且无该 ID 或同名别名；这只是排除已知目录冲突的辅助条件，逐盘赛绩与 SGF 对照才是本轮的正面依据。

有两处必须保留的来源差异：

- **`98043/black`：2011 成绩表写反执色及胜者。** 表中写李世石黑、李昌镐白、白胜；源 SGF 写李昌镐黑、李世石白、白胜。另从 [CyberOro 原始对局文件](https://open.cyberoro.com/gibo/201107/110721-bl-lee.sd.sgf)取得 `PB[이창호]`、`PW[이세돌]`、192 手白中盘胜，192 个执色／落点对与源 SGF 完全相同；[当时赛事报道](https://www.cyberoro.com/news/N_news_view.oro?cmt_n=&div_no=A1&num=515477&pageNo=)明确记载李世石在 2011-07-21 韩国联赛第 6 轮第 1 场第 2 局击败李昌镐。故原始对局文件和当时报道支持 `98043/black → player:143`，成绩表此行的反向信息不得沿用。原始对局文件字节 SHA-256 `6de744604394c38bf5dc893e170e29b3c11b3edad36a10aa4576c906d373ada7`；报道响应体 SHA-256 `81c119f3d4252f09afb58ad5fa44d0011edee3342bf6e4f2d1515ddd5163eb59`。
- **`89846/white`：对手段位有差异。** 源 SGF 写金起用五段，联赛表写六段，[Hangame 棋谱清单](https://baduk.hangame.com/gibo.nhn?kind=0&leagueseq=0&m=list&page=10449&searchtext=%3F%3F%EB%90%A4%3F%3F%3F)也写六段。双方身份、李昌镐九段、日期、执色和白胜 1.5 目一致；只批准李昌镐身份关联，不推断或修正对手段位。

受控逐槽裁决与根属性、原始及规范化 SGF 哈希、成绩表短摘录及哈希、固定 inventory 行保存在 `/Users/fan/.local/share/kifu-name-audit/2026-10-02/lee-143-link-prep/lee-143-korean-league-2010-2011-identity-review-sol.json`（`0600`），文件 SHA-256 为 `86d653ea00ed5e22db9997b7e8760051747895bf69995aca29b4a5ba9217030c`。韩国棋院页面响应体 SHA-256 `ad0fb2eedf8fbcebca17581ba3752a3ee40726a819e102217dbc9950367ce3c6`。联赛页面可通过网页读取逐行核对，但直接 HTTP 获取返回 403，故没有完整页面响应体哈希；逐行短摘录哈希在受控工件中。

本轮没有查询数据库：使用的是已固定的 inventory 和先前只读捕获的棋手目录，不声称它们仍是现时生产快照。未来若制作关联载荷，仍须重新绑定当时 inventory／catalog、每盘生产 SGF 哈希及前像，并对最终冻结范围独立签署。本轮没有生产或测试库写入、导入包、部署、应用代码修改、暂存或提交。
