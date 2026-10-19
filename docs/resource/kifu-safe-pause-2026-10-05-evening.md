# 棋谱名称工作安全暂停记录

暂停时间：2026-10-05 21:00 左右（Asia/Shanghai）。用户明确要求安全暂停，等待用户通知继续。

## 已停止

- 并行资料任务 `event10_review_apply`、`link407_review_astra` 已中断。
- `hide250_review_astra` 已完成只读交付，未进行待执行的 700 槽写库。
- 本地 8775 报告预览服务已停止；报告 HTML 文件保留。
- 主线程当前没有数据库写入或部署在执行。

## 已保存的实际成果

- 正式库五语言完整棋手：182 / 3,700（4.92%）；测试库为 181，保留原有无棋局关联的数据闸门。
- 五语言完整赛事：64 / 85（75.29%）。
- 两位棋手及赛事五语言全部完整的棋局：27,499 / 173,025（15.89%）。
- 正式库 182 位棋手保存了 1,102 个资料链接。
- `kifu_players.authoritative_pages` 字段及同步工具已在两库落地，保存 URL、来源、语言、资料角色和证据 ID。未来棋手主页尚未开发。
- 隐藏的 250 盘边缘赛事保留隐藏状态；已完成的 1,117 个赛事关联更新保留。
- 已推送提交截至 `02b551f6`。随后 AC、AD、AE、AF 四批实际入库收据及最新 HTML 已保存在工作区，尚未提交；不要丢弃。
- 报告：`docs/resource/kifu-five-language-progress-2026-10-05.html`。
- 进度快照：`/tmp/kifu-five-language-progress-prod-20261005.json`。

## 待审核、未入库

1. AG：`/tmp/kifu-player-next5ag-20261005`。唐奕、上野爱咲美、崔明勋、陆敏全、王昊洋，25 个五语言单元。两库只读校验通过；未审签、未写库。
2. AH：`/tmp/kifu-player-next5ah-20261005`。蔡丞韦（旧 canonical 为蔡丞伟）、志田达哉、本木克弥、林至涵、范胤，25 个五语言单元。两库只读校验通过；未审签、未写库。
3. AI / AJ：`/tmp/kifu-player-next10aij-20261005`，资料生产中。久井敬史韩文资料实际仍为 Latin，留到第二轮；由李昌锡 PROD 193 补位。王雷与已完成的王磊是不同棋手，不可因英文同为 Wang Lei 合并。
4. Latin700：`/tmp/kifu-player-latin700-review-20261005`，690 行、700 个空棋手 FK 槽，仅 Rin Kaiho / Takemiya Masaki / Cho Chikun 三种原文。两库只读 check 通过，0 更新。`execute.py` SHA256 为 `14337920c112c329b19428f0ebbee322a180d0555a901453b1dc04d823637f47`；`transport.py` 为 `b54aeb3e22455b6142491a4c150e22f938e189c8c6b71d053d076629989ff782`。主线程尚未独立审签、dry-run 或 apply。

## 未满五语棋手的资料链接

- `/tmp/kifu-held-player-pages-pending-20261005.json`：篠原正美、林有太郎尚无已保存本人正文；曲励起目前仅 GoRatings 正文，不把尚未抓取的官方/Wiki 目的 URL 冒充已核资料。久井敬史已有棋院本人页及日文 Wiki 正文，可独立核身份后保存链接。
- `/tmp/kifu-player-next5ae-20261005/nakamura-retained-authority-pages.json`：中村勇太郎日文 Wiki 是本人传记；棋院 ki000030 是弟子黒沢忠尚页面，只可作为上下文佐证。以上尚未追加数据库；不计作五语完成。

## 恢复顺序

1. 等待用户明确继续；本次暂停期间不要启动生产、写库或部署。
2. 审阅 Latin700 固定执行器及完整前后像；若批准，再依次 TEST / PROD dry-run、apply、verify。
3. 若更新了棋手 FK，只捕获一次 post700 快照，替换 `/tmp/kifu-run-reviewed-batches.py` 的 post1117 基线并重新绑定尚未写入批次的快照摘要；重新审签，不放松原有前像校验。
4. 独立审 AG / AH 的实际来源后，每五位同步两库、资料链接、实际统计和 HTML。资料生产继续按已分配队列推进。
5. 对未满五语的已核本人资料做小范围字段追加；无正证的不追加、不伪造核实名称。
6. 提交只包含已完成的准确文件列表；本工作区还有大量历史未跟踪资料，禁止 `git add -A`。

目前任务未完成。本文件仅记录安全暂停位置。
