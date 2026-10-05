# team1 独立代码审查 — 2026-10-06

**结论：APPROVE。未发现阻塞问题。**

审查提交 `443403b9403fd32992888612dcffe272a26bb990`，父提交 `13c288bcfc901f50f6f6e92f12850b7fd25deb31`。范围限于三个改动文件及签署、锁、scope 与 undo 的必要相邻路径；不重审此前已批准的完整 raw-title 功能。

## 已核实的边界

- 例外固定为 raw `团体赛`、现有 owner `73686`。独立读取两库完整捕获，确认生产常量及测试 fixture 的所有 ID 都与实际数据一致：全部 **324**、eligible **294**、排除 **30**，后者均为 `event_id=73`。三组 SHA 分别为 `39fee6c73115534d2c206b0eaa4fc834cb6bc624dafdf147a3955fb09a9ea967`、`8dc603a8278797dd57a271b76f2316cca40c49ed36465001c8d5d9e77f9605bb`、`84e87533c0b750f6bbae1d9dc2df2b738f1075f9e937e65dce7c82cf91ad074b`。
- `_team_raw_scope` 同时要求精确 ID/数量/分区、全部公开非重复、无同 album 或同 raw 的 selected scope、每局恰好一个 source link。其他非空 event ID、增删/交换分区或范围变化均不能满足固定条件。
- `prepare_plan` 比较 manifest 内完整 album/source-link 捕获；signed plan 保留全量镜像及 324 occurrence IDs。`inspect_plan` 在 apply 的既有写锁内重新比较完整镜像、分区、owner 前像及 inventory/catalog pins，并校验与计划一致的独立签署。外部 plan/manifest SHA 门禁保留。
- 名称写入仅对固定 owner/raw 且有批准的 `team_scope` 元数据进入例外；重新生成当前全量 scope，并严格比较 metadata 中所有固定字段与完整镜像 SHA。`73→74` 会被分区拒绝；SGF/source-link/其他捕获表字段变化会使完整 scope SHA 不符。缺少此证据仍进入原纯无关联门禁并拒绝当前 mixed scope。
- owner 写操作仍只更新 review status/metadata；ledger 保存已签计划与 owner 前后像，原条件 undo 路径不变。没有 album/FK/SGF/parser/schema 写入，也没有扩大其他 profiles 的无关联规则。
- `_v2_scope`、成员语义与 readers 未改：owner occurrence 必须为全部 324，五语言 bundle 仍为 5 个名称成员；`_affected_albums=324` 是审计范围。现有 reader 的 NULL-event/public/nonduplicate/no-selection 条件排除原有 30 条赛事关联，新增覆盖为 294。

## 验证与装配提示

独立纯读取 Python probe 对 TEST、PROD 两份捕获分别验证了上述精确集合、分区、哈希、可见性、selection 及一对一 source link；均通过。`git diff --check` 通过，worktree 干净。已读新增测试，覆盖缺少 linked IDs、过期捕获、伪造分区、SGF/source-link/linked-event 改动、名称门禁和 owner undo。实现者报告 45 个聚焦测试通过；未重复运行测试套件或连接数据库。

现有 capture 的 `occurrence_album_ids` 字段仍存 294 eligible IDs；装配正式 manifest/name owner 时必须使用其 `associated_album_ids` 的全 324。`album_scope_preimage` 应取实际表列：去掉捕获派生的 `sgf_sha256`、两个 `is_*` 标记及 source join 附加的 `source_key`/`display_name`，保留所有真实 album/source-link 列。这是捕获格式对接提示，代码会拒绝错误装配。

本结论为代码批准；未进行 SSH、数据库操作、代码修改或部署。本报告是本轮唯一写入的本地文件。
