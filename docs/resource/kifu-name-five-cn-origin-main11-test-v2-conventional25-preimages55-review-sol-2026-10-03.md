# TEST v2 conventional25 / preimage55 独立审核

2026-10-03，reviewer `/root/five_test_conventional25_review_sol`；模型 GPT-6（runtime identity，未独立验证 subtype）。签审时间 `2026-10-03T09:10:12.468046+00:00`，晚于 fresh binding `09:03:25.858394 UTC`。

**PASS：25 conventional候选、55 clone前像bindings。HOLD：30 secondary候选、active TEST/PROD写入。**

受控包：`~/.local/share/kifu-name-audit/2026-10-03/china-professional-roster/five-cn-origin-main11-test-v2-conventional25-preimages55-independent-review-sol/`（0700目录、6文件0400）。manifest SHA-256 `3eb7b3e5c4842e1212a3bd21b6f82348bc5b5f72484cd767184fd1783b393d25`。输入manifest `adf3dc68e2beeaad1abe35de64cb02f7ff9834ad7f4cfed244caf8da58dca03e`。

审核150个依赖文件的实际字节hash、25 exact source-name字符串/目标语言/职业棋手同人上下文、candidate→research→detached review精确hash、signed scope与anchor依赖。所有25 source span使用原始UTF-8字节解码文本核对，保留CRLF；未归一化姓名或源文本。唐韋星日文采用已签Wikipedia article H1及独立CWA出生日期同人证据；楊鼎新日文保留三星杯2019-09-04对局上下文对应证据。其余沿原签审职业资料与比赛上下文，不扩大为游戏人物身份或FK批准。

55 binding逐项核对未绑定candidate canonical SHA、capture字节hash `c55c7355e30bd4d7d060ca52494f41e40b1f7ad1dc84f665425e80a500bb5478`、bound_at及NULL前像。Capture中五raw owner不存在，55 name rows为空，4358槽位context一致，4238 albums范围未变。原container `facc819d4d75635debced92f024ec3ff9591c2ab280f2a4aaaa4b9cad8e916f5`、同名volume `kifu-five-test-rebind-sol-v2-20261003`、127.0.0.1:55445、停止回执一致。批准只涵盖该历史隔离clone capture；未重新启动或连接数据库。

`conventional25.approved.json`为25签名候选；`preimage55.reviews.approved.json`只批准前像binding，**不批准30 secondary显示决策**。后者仍需新bound_at之后六个完整batch复审及精确SHA重绑，再最终validate/dry-run。此包未宣称全55 ready、未修改source包、未apply/undo、未改代码、未commit/push，reviewer数据库连接与写入均0。
