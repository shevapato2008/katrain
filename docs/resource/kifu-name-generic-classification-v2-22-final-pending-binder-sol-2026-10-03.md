# classification-v2：22 格最终 PENDING 前像绑定

2026-10-03；绑定者 `/root/generic_v2_22_binder_sol`，运行时标识 GPT-6，任务名 sol 不认证具体子型号。代码固定 `e8110c2471a674b3fabc0450fbc00cf0963ec499`。**22/22 最终候选仍 pending；0 最终签署、0 数据库写入、0 实际显示增益。**

受控目录 `/Users/fan/.local/share/kifu-name-audit/2026-10-03/generic-classification-v2-22-final-pending-binder-sol`。从原 producer 和独立 source/category/template review 开始，复算两份 manifest 下全部 15+9 文件；原文件只读复制并保留作者、模型、生产和历史审核时间。全部 22 条来源候选原文字面值、producer 字段、规则版均保留；每条绑定原候选的规范 SHA-256。原 33 格审核的 30 PASS / 3 HOLD 历史结论未改。

仅启动隔离容器 `kifu-raw31-clone-20261003`，连接 `127.0.0.1:55433/kifu_raw31_clone_20261003`，驱动 `default_transaction_read_only=on`，前像事务 `REPEATABLE READ READ ONLY`。新前像采集 `2026-10-02T23:03:37.459963+00:00`，绑定 `2026-10-02T23:03:37.737594+00:00`。这是旧生产 dump 的克隆当前复查，不是新生产快照；来源及克隆空选择表兼容处理见保留的 raw31 preview。未连接生产或现役测试库，未调用 importer，也未写隔离库。

两个精确 `raw_event` 的 SELECT 均为零行：`段位赛` 和 `个人赛` 明确采用原 symbolic create ref；各十一语名称前像 NULL。前像原始字节 hash `2537a40da6743e6210227ac552c5419ecf1725e770fbd512c1f40d4bc12fc8bd`。catalog `37ab4773652e10e38cdcc49a6fc13e3f72ec734aeb30be548d2597c0660f7f09`；inventory `f4907ffbe70d62b4b77f6d3bf5ba7ed789f2685f46eff7ffdfe080f2abc4bab1`，173,025 盘、event selections 0。克隆保留此前演练的 1 batch / 23 change 审计行，当前 raw_event value/name 与 research 均 0；这些不是本次写入。

当前精确范围 `段位赛` 901、`个人赛` 638，共 1,539 盘；完整逐盘 contexts、occurrence IDs/hash 与旧独立审核完全一致。历史两项 category_review 原样使用，十一语 v2 template_review 原样使用，且新代码逐项模板 hash 一致。范围、owner/member/link 哈希按最终包重算；零 event owner、零 event alias 提案、`album_links=[]`，不写棋谱 `event_id`。

最终 pending bundle 的规范 SHA-256 `b0956e731c441b2d83f5fb95a89a971f00f92ffe3b6228b48a6440153d28e4fa`，字节 SHA-256 `37bc02517ed97bead1fb61650c84aeffa777b2c37d135be55ba17d3755a51b1a`。现有 CLI 校验实际 exit 1：`pending=22, approved=0, missing=0, rejected=0, write_errors=[]; ready=false/write_ready=false`。四项错误仅是两 owner 各自尚无全部十一语批准，以及新 raw category 尚无对应已批准 display。22 单条 pending 精确文本校验全部成功，没有靠伪造候选签署绕过整包闸。

剩余批准为 **22 条最终候选的独立签署**，包含本次 capture、owner 不存在/create、完整当前 scope 和各前像绑定核对。审核者必须不同于来源 producer 与本次 binder。若复用现有模板签署，最终 candidate reviewer 必须为 `/root/generic_v2_22_source_review_sol` 且实际模型字段与该签署一致；另一审核者须另行实际审核并签署十一语精确 v2 模板，不能改写历史 signer。最终 reviewed_at 须晚于绑定。来源/类别/模板历史批准不能充当这些新前像的最终候选批准。

签后还需既有 validator、独立克隆 importer dry-run 与授权的 apply/replay/undo/reapply、十一语显示/搜索/覆盖验收；本次没有执行这些写操作。正式入库前必须核对实际目标 inventory/catalog/name 前像；当前克隆 capture 不能证明未来生产状态。Hoensha 阶段二十一格不在本包范围，三组 33 格目标尚未完成。克隆已停止，停止收据已留存。未改应用代码或提交。
