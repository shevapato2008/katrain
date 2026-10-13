# 2,134 局 raw 赛事显示：最小兼容实现与待审包

## 独立决定

`/root/event10_review_apply`（gpt-6-astra）复核已批准的 classification-v2 与 archive-description-v1 原件后，确认复用原词句。段位赛/个人赛是通用描述；Hoensha 是史料来源说明，不建立赛事身份或别名，不写 album、SGF、event_id、棋手 FK。

| 既有 raw（两库 ID 相同） | 公开 NULL 棋局 | cn / tw / jp / ko / en |
|---|---:|---|
| 段位赛 74834 | 901 | 段位赛 / 段位賽 / 段位戦 / 단위(段位) 관련 대회 / Dan-rank tournament |
| 个人赛 71508 | 638 | 个人赛 / 個人賽 / 個人戦 / 개인전 / Individual tournament |
| Hoensha game 69522 | 595 | 方圆社史料棋局 / 方圓社史料棋局 / 方円社の棋譜（史料） / 호엔샤(方円社) 관련 옛 기보 / Hoensha archive game |

当前 gate 要求每个分类一次批准十一语，故保留 **33 条原有词句**，其中主流五语覆盖 10,670 个棋局语言槽。此数字是待落地范围，**尚未在线新增覆盖**。

只读实抓确认：三 owner 均 pending，名称均 0。既有 importer 的已有 ID 分支不修改类别，archive 校验明确拒绝直接重分类。因此采用一次有限类别 CAS，再用原 importer 写名称；不扩 importer、不增表。类别批准改变 catalog hash，应在主线程排队的棋手名称写入完毕后统一执行。

## 实现范围

隔离工作树 `.worktrees/kifu-raw2134-compat`，分支 `codex/kifu-raw2134-compat`。

- `scripts/kifu_raw2134_categories.py`：只接受三条精确 raw，完整 before/after CAS，仅允许 category/parser_version/review_status/review_metadata 改动。验证当前 901/638/595 公开 NULL 范围；Hoensha 另核对完整 live album/source context 与无 selected event。复用 `name_batch` 锁、`KifuNameBatch/KifuNameChange` 和 `undo_batch`，支持只读 dry-run、精确 hash apply、零改动 replay。独立签名缺失即拒绝。
- `katrain/web/kifu/legacy_raw_events.py`：兼容没有 raw ORM 映射的 PROD，SQL 精确联结 owner/name/evidence 的审核、revision、decision、rule、display 和独立 reviewer；只读这三原文。重用现有签名、精确模板与 Hoensha scope 验证器。显示与搜索均排除已关联赛事、selected event 及 archive 范围外棋局。
- `scripts/build_kifu_raw2134_overlay.py`：从实际 PROD 文件生成补丁；每个替换锚必须恰有一次。把现有 `name_candidates.py` 所需纯规则函数原样提取为 `legacy_raw_event_rules.py`，避免替换旧 ORM 或整套 identity。
- 两份聚焦测试：`tests/web_ui/test_kifu_legacy_raw_events.py`、`tests/web_ui/test_kifu_raw2134_categories.py`。

### 精确线上差异（仅准备，未部署）

实际运行时已只读捕获到 `/tmp/kifu-raw2134-20261005/runtime-prod/`，before hash 在 `hashes.json`。生成输出 `/tmp/kifu-raw2134-20261005/overlay-prod/manifest.json` 固定 before/after：

1. `identity.py` 的 `display_maps` 返回前新增三行：加载 raw helper、将合格多语 raw 名称并入现有逐局 hints。
2. `endpoints/kifu.py` 搜索过滤前新增六行：没有唯一实体命中时，以唯一已审 raw 的精确范围作为搜索条件；未命中 raw 时保持原有模糊搜索。原列表隐藏、分页和其它路径保留。
3. 新增两个小 helper 文件：`legacy_raw_events.py` 与从当前规则打包的 `legacy_raw_event_rules.py`。

TEST 已有 strict/progressive raw 读取路径，无须部署这份 legacy overlay。两库共享名称/CAS 工具仍使用兼容 importer image。

## 待审数据与执行顺序

根目录 `/tmp/kifu-raw2134-20261005/`：

- `PROD|TEST/current.json`：真实三 owner 全字段、名称前像、公开 NULL ID 范围；只读获取。
- `catalog-digests.json.gz`：现有目录每行 hash，用于本地预测只修改三条后的 catalog hash；未重抓 173,025 局。
- `PROD|TEST/categories.pending.json`：独立签署前的有限 CAS 方案。
- `PROD|TEST/bundle.pending.json`、`research.pending.jsonl`、`inventory.json.gz`：33 条待审名称、空独立检索集、post700 format4 基线。
- `sources/`：Hoensha 两份真实保留正文，原字节 hash 不变；`source-provenance.json` 固定两个历史批准包。
- `prepare.py`：仅本地重绑/预测，不连接数据库。默认所有新类别/模板/候选保持 pending。

**pending validator 当前不是 ready**：旧 gate 要求 archive category 先有真实独立签名，并要求分类的十一候选全部批准。报告明确保留这些预期审核缺口，没有移植旧签名或伪造新审批。

主线程执行次序：

1. 完成排队的名字包；若先做其它 catalog/FK 改动，重跑本目录 `capture.py` 只读刷新三 owner 与 catalog digests，`prepare.py --inventory-root <新的format4基线根目录>` 重绑一次。
2. 独立复核三类别、新 Hoensha 595 行绑定与原 33 词句。保存自己的 `review.json`，字段为 `reviewer_id/reviewer_model/reviewed_at/conclusion`（真实独立身份和时间）。
3. `prepare.py --review-json review.json --inventory-root <基线根目录>` 将该真实类别/模板签署绑定到现 owner，输出 `categories.approved.json`，名称候选仍 pending。catalog 后像在此时重算，旧 pending hash 随之作废。
4. 用原名称审核流程签署 33 个最终候选，时间晚于新前像绑定；重新 validate。类别 CAS 先 TEST dry/apply，再 PROD dry/apply，全部带 `--expected-plan-sha256`；名称包绑定预期类别后像，继续原 TEST/PROD dry/apply。主线程也可每环境连续类别→名称，再切换环境。
5. 部署仅 PROD overlay 后，验证代表性五语显示和精确搜索的 901/638/595 ID 范围。撤销按名称 batch → 类别 batch 顺序调用原 `undo_batch`。

CAS 命令只从环境变量读 `KATRAIN_DATABASE_URL`，不输出凭据。容器执行时把整个 packet 只读挂载到原绝对路径 `/tmp/kifu-raw2134-20261005`，这样 retained body 的校验路径不变。这里没有执行上述写入或部署。

## 验证

- 初版新增 6 个聚焦测试及原有 6 个分类/archive 测试通过。独立审核发现精确搜索仍 OR 入模糊条件；修复后新增一个生成 endpoint 查询的代表性测试，两份改动测试文件 **7 passed**。覆盖十一语显示/搜索，证据撤销、revision 错配，Hoensha 未批准新增同名局、已关联、selected event 排除；CAS dry-run 零写、3项 apply、replay 零改动、原 undo 恢复；source context 改动和未签名拒绝。精确「个人赛」排除标题仅包含该词的范围外棋局，其他输入保持模糊搜索。
- 独立 `gpt-6-astra` 审查修复后通过，无未解决 critical/important；另从实际生成的 PROD overlay 提取真实列表函数做 SQLite 隔离复现，精确范围及分页 total 均正确。审查报告见 `kifu-raw2134-independent-code-review-2026-10-05.md`。数据审批和部署仍待主线程执行。
- 实际 PROD 一次性 Python 进程纯内存导入全部 4 个 prospective overlay 模块成功：旧 models 保留，数据库查询 0，文件写入 0。没有替换运行中的应用。
- 未改 importer、主工作区业务代码、任一数据库或任何部署状态。
