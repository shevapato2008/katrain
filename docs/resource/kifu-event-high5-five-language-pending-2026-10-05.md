# 高频赛事五语名称：待独立审核（2026-10-05）

状态：producer pending。25 个名称格已通过现有结构校验；未签名、未写数据库。

Producer: `/root/event10_review_apply`，配置模型 `gpt-6-astra`，推理 `max`。

## 名称与直接来源

| ID | 赛事 | 可见非重复棋局/环境 | cn | tw | jp | ko | en |
|---|---|---:|---|---|---|---|---|
| 41 | 中国围棋甲级联赛 | 12828 | [中国围棋甲级联赛](https://www.sport.gov.cn/n322/n3407/n3413/c564649/content.html) | [中國圍棋甲級聯賽](https://www.haifong.org/news/content/44A50C946C4E448FD6315C86C49D835A) | [中国囲碁甲級リーグ戦](https://www.pandanet.co.jp/event/chinaevent/backnumber2020.htm) | [중국갑조리그](https://m.baduk.or.kr/news/B02_view.asp?news_sum_no=1692) | [Chinese A League](https://gotoeveryone.k2ss.info/news/cn/al/28/) |
| 50 | 韩国围棋联赛 | 6180 | [韩国围棋联赛](https://www.sport.gov.cn/n14471/n14481/n14518/c893134/content.html) | [韓國圍棋聯賽](https://haifong.org/game/classes/F073F992B64DE103212A93B6E0C3AB1C) | [韓国囲碁リーグ](https://kb-league.syuusaigo.com/) | [한국바둑리그](https://www.baduk.or.kr/record/player_view.asp?pkey=10000545) | [Korean Baduk League](https://gotoeveryone.k2ss.info/news/kr/kl/10/) |
| 42 | 中国女子围棋甲级联赛 | 2680 | [中国女子围棋甲级联赛](https://www.sport.gov.cn/n20001280/n20067662/n20067613/c27635988/content.html) | [中國女子圍棋甲級聯賽](https://zh.wikipedia.org/w/index.php?title=%E4%B8%AD%E5%9B%BD%E5%A5%B3%E5%AD%90%E5%9B%B4%E6%A3%8B%E7%94%B2%E7%BA%A7%E8%81%94%E8%B5%9B&oldid=92668094&variant=zh-tw) | [中国女子囲碁甲級リーグ](https://www.nihonkiin.or.jp/match_news/match_info/2025_5.html) | [중국여자갑조리그](https://m.baduk.or.kr/news/B01_view.asp?news_no=4038) | [Chinese Women’s A League](https://www.usgo.org/content.aspx?club_id=454497&item_id=92428&page_id=5) |
| 40 | 日本龙星战 | 2678 | [日本龙星战](https://www.foxwq.com/news/8091.html) | [日本龍星戰](https://zh.wikipedia.org/w/index.php?title=%E9%BE%8D%E6%98%9F%E6%88%B0&oldid=52849061&variant=zh-tw) | [竜星戦](https://www.nihonkiin.or.jp/match/ryusei/022.html) | [일본 용성전](https://www.cyberoro.com/news/N_news_view.oro?cmt_n=&div_no=A1&num=525830&pageNo=) | [Ryusei Tournament](https://www.nihonkiin.or.jp/english/topics/11/topics2011_10.htm) |
| 43 | 三星杯世界围棋大师赛 | 2285 | [三星杯世界围棋大师赛](https://www.sport.gov.cn/n20001280/n20067662/n20067613/c27069198/content.html) | [三星盃世界圍棋大師賽](https://www.haifong.org/game/classes/B0A85C728A240460DBA68725773324CF) | [三星火災杯世界囲碁マスターズ](https://www.nihonkiin.or.jp/match/sansei/archive.html) | [삼성화재배 월드바둑마스터스](https://baduk.or.kr/game/game_view.asp?cmpt_code=2104&etcKey=2) | [Samsung Cup](https://homepages.cwi.nl/~aeb/go/games/games/Samsung/) |

TEST、PROD 一致：26,651 盘非重复且未隐藏棋局。三星杯 2,287 条关联行，其中 2 条为重复棋局。五项当前均没有名称行。

## 审核要点

- 当前频次优先五项为中国围甲、韩国联赛、中国女甲、日本龙星战、三星杯；按要求排除了已完成赛事及另批处理的日本大赛。
- 23 格取自官方或专业围棋页面；繁体女甲及日本龙星战采用固定版本维基正文，加官方原文赛事身份佐证。日本龙星战维基来源是正文消歧义列表，记录为百科用例，未包装成台湾机构定名。
- 韩国联赛 en 选正文中的 `Korean Baduk League`；和另建实体的韩国围乙/未来联赛区分。
- 三星杯 jp 采用第14届起的现用系列名；原历史届次标题保持在 raw EV。来源明确列出名称沿革。
- 25 格均有原样公开用例，本批没有生成直译、读音推导或无惯用名断言。

## 范围与校验

- 只提议已有 5 个 event 的 `cn/tw/jp/ko/en` 名称及研究证据；没有 owner、album、alias 或关联修改。
- TEST/PROD `validation.pending.json`：`errors=[]`、`write_errors=[]`、25 格 pending；`ready=false` 是尚未独立签名的预期状态。
- 已保留 HTTP 200 原始响应、SHA-256、精确获取时间和目标语正文片段。
- 包目录：`/tmp/kifu-event-next-high5-20261005`；每环境 `bundle.pending.json`、`inventory.json.gz`、`current.json`、`validation.pending.json`；共享 `registry.json`、`research.pending.jsonl`、`sources/manifest.json`。

## raw EV 展示边界

`identity.strict_display_maps` 读取已批准赛事类型名和另行批准的 raw-event 组合名。`display_event_name` 当前只为 Oteai 自动装饰 CWI 年份/春秋，尚无适用于这五项赛事的通用年、届、轮装饰。此包仅完成赛事类型名；不把原始年份轮次另作未经审核翻译。
