# 41档AI标定基础 Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 建立与生产运行时一致的五种选点语义、可表达固定/未定配置的41档目录，以及可冻结、恢复和审计的候选筛选与相邻20盘实验协议。

**Architecture:** `katrain/core/ladder.py`继续作为强度配方和共享选点的唯一真源；产品目录使用显式状态表达未拟合档，禁止占位值运行。新的纯协议模块只负责候选、目标槽、摘要、判定和失效传播；命令行runner复用现有`run_selfplay.py`的引擎、裁判和账本能力，不复制走子实现。

**Tech Stack:** Python 3.11、pytest、dataclass、SHA-256、现有KataGo HTTP分析适配器与JSONL账本。

**Design:** `superpowers/tracks/golaxy-ai-ladder-parity/2026-08-03-41-tier-ai-ladder-finalization-design.md`

---

## Chunk 1: 共享选点与41档目录

### Task 1: 把选点语义变成强度配方的一部分

**Files:**
- Modify: `katrain/core/ladder.py`
- Modify: `tests/core/test_ladder.py`
- Modify: `tests/core/test_ladder_strategy.py`
- Modify: `superpowers/tracks/golaxy-ai-ladder-parity/calibration/probe_humansl_search.py`
- Modify: `superpowers/tracks/golaxy-ai-ladder-parity/calibration/run_golaxy_alignment_campaign.py`
- Modify: `superpowers/tracks/golaxy-ai-ladder-parity/calibration/run_golaxy_b18_20game_extension.py`
- Modify: `superpowers/tracks/golaxy-ai-ladder-parity/calibration/run_selfplay.py`
- Modify: `tests/platforms/test_golaxy_calibration_opponent.py`
- Modify: `tests/platforms/test_humansl_probe.py`

- [ ] **Step 1: 写失败测试**

在`tests/core/test_ladder.py`增加五类选择的响应契约测试：

```python
@pytest.mark.parametrize("selection", [
    "human_weighted", "human_temperature", "human_argmax",
    "search", "native_policy_argmax",
])
def test_supported_ladder_selections(selection):
    assert selection in LADDER_SELECTIONS

def test_human_argmax_uses_human_policy_not_move_infos(): ...
def test_native_policy_argmax_requires_one_visit_and_empty_move_infos(): ...
def test_search_requires_nonempty_valid_move_infos(): ...
def test_stochastic_selection_requires_plain_u64_draw(): ...
def test_selection_response_fields_are_not_interchangeable(): ...
```

为PIKL和纯b18配置增加强度摘要测试，断言`rank_9d@2`包含`b18 + humanv0 + rank_9d + HUMANSL_PIKL_BASELINE_V1`，`b18@2`不包含任何HumanSL字段。

- [ ] **Step 2: 运行并确认失败**

Run: `CI=true uv run pytest tests/core/test_ladder.py -q`  
Expected: FAIL，缺少`LADDER_SELECTIONS`和共享rung选点器。

- [ ] **Step 3: 最小实现**

在`katrain/core/ladder.py`：

- 定义五个字符串常量及`LADDER_SELECTIONS`；
- 为`LadderRung`增加`selection: Optional[str]=None`以保持旧账本/未跟踪实验脚本可读取，但所有可执行路径都拒绝`None`；逐一更新上列所有**已跟踪**构造点为显式selection。当前未跟踪的`run_golaxy_rank1_6_sampling_campaign.py`不在本任务隐式修改或暂存，若后续要纳入版本控制则单独迁移并审查；
- 增加`pick_ladder_rung_move(analysis, rung, board_size, *, draw_u64=None)`；
- `human_weighted`复用`pick_temperature_policy(..., T=1, draw_u64)`，`human_temperature`使用rung温度，两个随机选择都要求plain u64；
- 把现有实验argmax和`b18@1 policy_argmax`逻辑移到core共享函数，固定同值时的canonical遍历顺序；
- `search`继续严格验证全部`moveInfos`后选最小`order`；
- 将PIKL常量版本名固定为`HUMANSL_PIKL_BASELINE_V1`，保留旧名兼容别名；
- 新增`rung_endpoint_digest(rung, model_identity)`，canonical JSON绑定模型身份、selection、visits、profile、温度和全部override设置。

旧`pick_ladder_move`保留给非阶梯兼容调用，但新的运行时和实验不得再使用它选择阶梯着法。

- [ ] **Step 4: 运行并确认通过**

Run: `CI=true uv run pytest tests/core/test_ladder.py tests/core/test_ladder_strategy.py tests/platforms/test_humansl_probe.py tests/platforms/test_golaxy_calibration_opponent.py tests/platforms/test_humansl_selfplay.py tests/platforms/test_golaxy_alignment_campaign.py -q`  
Expected: PASS。

- [ ] **Step 5: 格式化并提交**

```bash
uv run black -l 120 katrain/core/ladder.py tests/core/test_ladder.py tests/core/test_ladder_strategy.py \
  superpowers/tracks/golaxy-ai-ladder-parity/calibration/probe_humansl_search.py \
  superpowers/tracks/golaxy-ai-ladder-parity/calibration/run_golaxy_alignment_campaign.py \
  superpowers/tracks/golaxy-ai-ladder-parity/calibration/run_golaxy_b18_20game_extension.py \
  superpowers/tracks/golaxy-ai-ladder-parity/calibration/run_selfplay.py \
  tests/platforms/test_golaxy_calibration_opponent.py tests/platforms/test_humansl_probe.py
git add -- katrain/core/ladder.py tests/core/test_ladder.py tests/core/test_ladder_strategy.py \
  superpowers/tracks/golaxy-ai-ladder-parity/calibration/probe_humansl_search.py \
  superpowers/tracks/golaxy-ai-ladder-parity/calibration/run_golaxy_alignment_campaign.py \
  superpowers/tracks/golaxy-ai-ladder-parity/calibration/run_golaxy_b18_20game_extension.py \
  superpowers/tracks/golaxy-ai-ladder-parity/calibration/run_selfplay.py \
  tests/platforms/test_golaxy_calibration_opponent.py tests/platforms/test_humansl_probe.py
git commit -m "share certified ladder move selection"
```

### Task 2: 让生产LadderStrategy使用完整配方

**Files:**
- Modify: `katrain/core/ai.py`
- Modify: `tests/core/test_ladder_strategy.py`

- [ ] **Step 1: 写失败测试**

- `LadderStrategy`在温度/原生加权档生成一次u64并传入共享选点器；
- `@1s`走`human_argmax`；
- `b18@1`走`native_policy_argmax`；
- malformed response抛`LadderMoveError`，无跨机制fallback；
- 所有随机selection缺少plain-u64 draw时拒绝执行，不允许共享picker自行生成随机数。

- [ ] **Step 2: 运行并确认失败**

Run: `CI=true uv run pytest tests/core/test_ladder_strategy.py -q`  
Expected: FAIL，运行时仍只把`mechanism`传给旧选点器。

- [ ] **Step 3: 最小实现**

- `LadderStrategy`将完整rung传给`pick_ladder_rung_move`；生产随机档使用`secrets.randbits(64)`。
- 本任务不迁移`run_selfplay`：它要等Task 5的通用manifest draw provider就绪后一次迁移，避免中间态为普通weighted实验偷偷生成不可复现随机数。

- [ ] **Step 4: 运行并确认通过**

Run: `CI=true uv run pytest tests/core/test_ladder_strategy.py tests/platforms/test_ladder_query_contract.py -q`  
Expected: PASS。

- [ ] **Step 5: 提交**

```bash
git add -- katrain/core/ai.py tests/core/test_ladder_strategy.py
git commit -m "align ladder runtime and experiment selection"
```

### Task 3: 用显式状态替换旧37档占位表

**Files:**
- Modify: `katrain/core/ladder.py`
- Modify: `tests/core/test_ladder.py`
- Modify: `katrain/web/server.py`
- Modify: `katrain/web/interface.py`
- Modify: `tests/web_ui/test_ladder_injection.py`
- Modify: `tests/platforms/test_golaxy_ladder_consistency.py`
- Modify: `katrain/core/ai.py`
- Modify: `tests/core/test_ladder_strategy.py`
- Modify: `tests/test_ai.py`
- Modify: `tests/core/test_bake_results.py`
- Modify: `tests/platforms/test_golaxy_9d_alignment_runner.py`
- Modify: `tests/platforms/test_golaxy_b18_20game_extension.py`
- Modify: `tests/platforms/test_golaxy_calibration_opponent.py`
- Modify: `tests/platforms/test_ladder_query_contract.py`
- Modify: `tests/platforms/test_golaxy_alignment_campaign.py`
- Modify: `tests/platforms/test_golaxy_fixed_screen.py`
- Modify: `tests/platforms/test_golaxy_humansl_rank_alignment.py`
- Modify: `superpowers/tracks/golaxy-ai-ladder-parity/calibration/bake_results.py`
- Modify: `superpowers/tracks/golaxy-ai-ladder-parity/calibration/run_calibration.py`
- Modify: `superpowers/tracks/golaxy-ai-ladder-parity/calibration/run_golaxy_9d_alignment.py`
- Modify: `superpowers/tracks/golaxy-ai-ladder-parity/calibration/run_golaxy_alignment_campaign.py`
- Modify: `superpowers/tracks/golaxy-ai-ladder-parity/calibration/run_golaxy_b18_20game_extension.py`
- Modify: `superpowers/tracks/golaxy-ai-ladder-parity/calibration/run_golaxy_fixed_screen.py`
- Modify: `superpowers/tracks/golaxy-ai-ladder-parity/calibration/run_golaxy_humansl_rank_alignment.py`
- Modify: `superpowers/tracks/golaxy-ai-ladder-parity/calibration/run_smoke.py`

- [ ] **Step 1: 写失败测试**

断言：

- 41个中文名称严格按设计顺序，顶端只出现`职业水平/职业顶尖/超越人类`；
- 固定配方标签准确；准1–8、准9、职业顶尖没有猜测配方；
- 全表内部认证状态初始为`provisional`，产品availability为`unavailable`；
- `/api/ladder-rungs`返回`rung/rank_name/certification_status/availability/route`；
- 对未认证档发起生产建局返回422，而校准代码仍可构造独立实验rung；
- `get_level(42)`失败；`get_recipe_for_calibration`对准1段等未解析目录项明确失败关闭。

- [ ] **Step 2: 运行并确认失败**

Run: `CI=true uv run pytest tests/core/test_ladder.py tests/web_ui/test_ladder_injection.py tests/platforms/test_golaxy_ladder_consistency.py -q`  
Expected: FAIL，当前仍是37档英文/旧顶档/b28占位配置。

- [ ] **Step 3: 最小实现**

- 保持`LadderRung`为**纯可执行配方**且其模型/机制字段非空；新增`LadderLevel(rung, rank_name, recipe: Optional[LadderRung], candidate_labels, certification_status, availability, route, external_status)`。`LADDER_LEVELS`是41档产品目录，未拟合档`recipe=None`。
- 明确删除模糊的`LADDER_RUNGS/get_rung`产品接口，不保留37档可被误调用的快照。`get_level(n)`只解析目录元数据；`get_recipe_for_calibration(n)`返回已解析配方但忽略产品availability，未拟合档失败；`resolve_available_rung(n)`同时检查配方、认证和availability，且是生产唯一入口。
- 将上列全部已跟踪旧调用点按用途迁移：生产`LadderStrategy/server/interface`只用`resolve_available_rung`；新目录驱动代码可用`get_recipe_for_calibration`；目录/报告测试只遍历`LADDER_LEVELS`。不得留下`get_rung/LADDER_RUNGS`引用。
- **历史实验脚本不得把旧数字rung传给新目录。** 把每个旧数字引用改成脚本内显式冻结的`LadderRung`/endpoint label（或版本化legacy endpoint descriptor）；例如旧rung 33的9D不得被重解释为新rung 33准7段。相应直接测试逐脚本断言精确profile、main/human模型、visits、selection和Golaxy API level，保证迁移不改变历史实验含义。
- `rung_strength_spec`、query builder、picker和strategy只接受`LadderRung`，从类型边界避免读未解析字段。
- 增加`dataclasses.replace/asdict`、旧checkpoint缺selection仍能解析但执行失败关闭的回归测试。
- 构建41档目录；所有档先保持`provisional + unavailable`，不把占位温度暴露给API。
- `LadderStrategy`也改用`resolve_available_rung`，不能绕过availability。`server.py`的HTTP预校验和`interface.resolve_ladder_rung`同样调用它；断言422发生在session/game状态变更之前。`/api/ladder-rungs`从`LADDER_LEVELS`返回新状态契约。
- 删除旧`KataGo中等/超职业`命名和旧Band B b28临时配置。

- [ ] **Step 4: 运行并确认通过**

Run: `CI=true uv run pytest tests/core/test_ladder.py tests/core/test_ladder_strategy.py tests/core/test_bake_results.py tests/test_ai.py tests/web_ui/test_ladder_injection.py tests/platforms/test_golaxy_ladder_consistency.py tests/platforms/test_ladder_query_contract.py tests/platforms/test_golaxy_9d_alignment_runner.py tests/platforms/test_golaxy_b18_20game_extension.py tests/platforms/test_golaxy_calibration_opponent.py tests/platforms/test_golaxy_alignment_campaign.py tests/platforms/test_golaxy_fixed_screen.py tests/platforms/test_golaxy_humansl_rank_alignment.py -q`  
Expected: PASS。

- [ ] **Step 5: 提交**

```bash
git add -- katrain/core/ladder.py katrain/core/ai.py katrain/web/server.py katrain/web/interface.py \
  tests/core/test_ladder.py tests/core/test_ladder_strategy.py tests/core/test_bake_results.py tests/test_ai.py \
  tests/web_ui/test_ladder_injection.py tests/platforms/test_golaxy_ladder_consistency.py \
  tests/platforms/test_ladder_query_contract.py tests/platforms/test_golaxy_9d_alignment_runner.py \
  tests/platforms/test_golaxy_b18_20game_extension.py tests/platforms/test_golaxy_calibration_opponent.py \
  tests/platforms/test_golaxy_alignment_campaign.py tests/platforms/test_golaxy_fixed_screen.py \
  tests/platforms/test_golaxy_humansl_rank_alignment.py \
  superpowers/tracks/golaxy-ai-ladder-parity/calibration/bake_results.py \
  superpowers/tracks/golaxy-ai-ladder-parity/calibration/run_calibration.py \
  superpowers/tracks/golaxy-ai-ladder-parity/calibration/run_golaxy_9d_alignment.py \
  superpowers/tracks/golaxy-ai-ladder-parity/calibration/run_golaxy_alignment_campaign.py \
  superpowers/tracks/golaxy-ai-ladder-parity/calibration/run_golaxy_b18_20game_extension.py \
  superpowers/tracks/golaxy-ai-ladder-parity/calibration/run_golaxy_fixed_screen.py \
  superpowers/tracks/golaxy-ai-ladder-parity/calibration/run_golaxy_humansl_rank_alignment.py \
  superpowers/tracks/golaxy-ai-ladder-parity/calibration/run_smoke.py
git commit -m "replace provisional ladder with 41-level catalog"
```

## Chunk 2: 冻结候选协议与可恢复runner

### Task 4: 实现纯候选选择和相邻边失效规则

**Files:**
- Create: `superpowers/tracks/golaxy-ai-ladder-parity/calibration/ladder_campaign.py`
- Create: `tests/platforms/test_ladder_campaign.py`

- [ ] **Step 1: 写失败测试**

覆盖：固定温度网格、准9候选顺序、职业顶尖候选顺序；2个screen槽/10个formal槽；每槽最多5次；整对剔除；screen合格线与完整tie-break；唯一候选confirmation失败；职业顶尖内部通过者的星阵2星阶段（按固定顺序首个2–2，否则距50%最近，再按内部距离/visits/固定顺序）；40条相邻边；端点摘要变化只使两侧边失效；固定端点失败返回`product_decision_required`。

- [ ] **Step 2: 运行并确认失败**

Run: `CI=true uv run pytest tests/platforms/test_ladder_campaign.py -q`  
Expected: FAIL，模块不存在。

- [ ] **Step 3: 最小实现**

实现纯dataclass和函数：

```python
TEMPERATURE_GRID = ("1.15", "1.3", "1.6", "2", "2.5", "3")
QUASI_9_CANDIDATES = ("rank_9d@1", "rank_9d@1s", "rank_9d@2", "rank_9d@3")
PRO_TOP_CANDIDATES = ("b18@12", "b18@10", "b18@14", "b18@8", "b18@16")

def next_slot_attempt(records, manifest): ...
def classify_screen(candidate_edges): ...
def classify_pro_top_external_screen(records): ...
def select_unique_candidate(results, protocol): ...
def classify_formal_edge(high_wins, eligible): ...
def invalidated_edges(old_table, new_table, previous_edges): ...
```

所有函数只接受已验证记录，不访问网络或全局随机数。

- [ ] **Step 4: 运行并确认通过**

Run: `CI=true uv run pytest tests/platforms/test_ladder_campaign.py -q`  
Expected: PASS。

- [ ] **Step 5: 提交**

```bash
git add superpowers/tracks/golaxy-ai-ladder-parity/calibration/ladder_campaign.py \
  tests/platforms/test_ladder_campaign.py
git commit -m "freeze 41-level calibration campaign rules"
```

### Task 5: 实现manifest、全随机选点追踪和runner

**Files:**
- Create: `superpowers/tracks/golaxy-ai-ladder-parity/calibration/run_ladder_campaign.py`
- Create: `superpowers/tracks/golaxy-ai-ladder-parity/calibration/generate_ladder_campaign_manifest.py`
- Modify: `superpowers/tracks/golaxy-ai-ladder-parity/calibration/temperature_pilot.py`
- Modify: `superpowers/tracks/golaxy-ai-ladder-parity/calibration/run_selfplay.py`
- Modify: `tests/platforms/test_ladder_campaign.py`

- [ ] **Step 1: 写失败测试**

- manifest绑定**已经提交的实现父revision**、显式相关源码路径/哈希（排除manifest与results）、模型、端点摘要、opening slots和reserves；manifest后续提交使HEAD前进仍可预检，相关源码漂移才拒绝；重复创建拒绝覆盖；
- `ladder-draw-sha256-u64-v1`冻结UTF-8 canonical JSON数组`[protocol,manifest_sha256,edge_or_candidate_id,target_slot,attempt,color,ply,player_label]`，取SHA-256前8字节big-endian；对普通`rank_*@1`和温度档均给出known-answer draw；
- screen和formal都必须记录draw、policy digest、selected index；
- 每个颜色开局前先append+fsync reservation，结束后append+fsync result；resume验证header、端点、slot/attempt、trace和账本尾。内部自对弈的尾部reservation无result时可恢复同一颜色/attempt并复用同一draw域；Golaxy外部尾部reservation因是否已执行/计费未知，必须返回`external_reconciliation_required`并停止，禁止自动重放或分配新attempt。两条恢复路径都要有测试；未知行/相关源漂移失败关闭；
- 达到每槽5次仍无完整pair返回`incomplete`；废弃attempt留在审计记录但不进分母。

- [ ] **Step 2: 运行并确认失败**

Run: `CI=true uv run pytest tests/platforms/test_ladder_campaign.py -q`  
Expected: FAIL，缺少manifest和runner入口。

- [ ] **Step 3: 最小实现**

- 从`temperature_pilot.py`抽取通用draw/policy摘要/trace helper，所有screen/formal中的`human_weighted`与`human_temperature`都记录同一trace，保留旧协议兼容验证；
- 从`run_selfplay.py`抽出明确的`play_manifest_pair(client, endpoints, referee, opening, slot, attempt, draw_provider, ledger)`原语：接收完整`LadderRung`端点、manifest裁判/模型身份、精确slot+reserve开局和attempt，不解析CLI matchup、不选择自己的开局、不硬编码b28@200；runner只编排此原语。
- 增加集成测试覆盖`b18@1`对`b18@12/b18@64`以及`rank_9d@2/@3`，证明原语可执行五类selection和显式裁判。
- 每完成一盘fsync追加JSONL；重启只从严格验证后的下一slot/attempt继续；
- `--dry-run`只输出下一动作和身份预检，不写对局；`--phase screen|formal`使用manifest冻结的目标数。

- [ ] **Step 4: 运行并确认通过**

Run: `CI=true uv run pytest tests/platforms/test_ladder_campaign.py tests/platforms/test_temperature_pilot.py tests/platforms/test_humansl_selfplay.py -q`  
Expected: PASS。

- [ ] **Step 5: 提交**

```bash
git add superpowers/tracks/golaxy-ai-ladder-parity/calibration/run_ladder_campaign.py \
  superpowers/tracks/golaxy-ai-ladder-parity/calibration/generate_ladder_campaign_manifest.py \
  superpowers/tracks/golaxy-ai-ladder-parity/calibration/temperature_pilot.py \
  superpowers/tracks/golaxy-ai-ladder-parity/calibration/run_selfplay.py \
  tests/platforms/test_ladder_campaign.py
git commit -m "add resumable 41-level calibration runner"
```

### Task 6: 冻结第一批候选manifest并启动实验

**Files:**
- Create: `superpowers/tracks/golaxy-ai-ladder-parity/calibration/manifests/41-tier-screen-v1.json`
- Modify: `superpowers/tracks/golaxy-ai-ladder-parity/EXPERIMENTS.md`

- [ ] **Step 1: 运行回归测试**

Run: `CI=true uv run pytest tests/core/test_ladder.py tests/core/test_ladder_strategy.py tests/platforms/test_ladder_campaign.py tests/platforms/test_humansl_selfplay.py tests/web_ui/test_ladder_injection.py -q`  
Expected: PASS。

- [ ] **Step 2: 生成不可变manifest**

Run: `KIVY_NO_ARGS=1 uv run python superpowers/tracks/golaxy-ai-ladder-parity/calibration/generate_ladder_campaign_manifest.py --phase screen --source-revision HEAD --out superpowers/tracks/golaxy-ai-ladder-parity/calibration/manifests/41-tier-screen-v1.json`  
Expected: 绑定当前已提交实现revision及显式源码哈希，写入所有温度、准9、职业顶尖内部screen、星阵2星外部screen与10盘续样协议及canonical digest；manifest/results自身不在绑定集合中。

- [ ] **Step 3: 提交manifest后做只读预检**

```bash
git add superpowers/tracks/golaxy-ai-ladder-parity/calibration/manifests/41-tier-screen-v1.json
git commit -m "freeze 41-level candidate screen"
KIVY_NO_ARGS=1 uv run python superpowers/tracks/golaxy-ai-ladder-parity/calibration/run_ladder_campaign.py \
  --manifest superpowers/tracks/golaxy-ai-ladder-parity/calibration/manifests/41-tier-screen-v1.json \
  --base-url http://127.0.0.1:8000 --golaxy --dry-run
```

Expected: `/health`、模型身份、源码摘要与下一动作全部通过。

- [ ] **Step 4: 启动并可恢复地运行screen**

Run: `KIVY_NO_ARGS=1 uv run python superpowers/tracks/golaxy-ai-ladder-parity/calibration/run_ladder_campaign.py --manifest superpowers/tracks/golaxy-ai-ladder-parity/calibration/manifests/41-tier-screen-v1.json --base-url http://127.0.0.1:8000 --golaxy`  
Expected: 持续运行直至全部候选选出、出现明确`no_candidate/incomplete`，或用户停止；不得把未完成状态报告为通过。

- [ ] **Step 5: 记录证据**

`--golaxy`复用现有Golaxy adapter/token/reservation API；无有效授权时在任何外部计费请求前失败关闭，内部screen结果仍可独立保留但职业顶尖不得标记selected。更新`EXPERIMENTS.md`，列出每个候选两侧比分、星阵2星screen/续样、被选项、不可判定attempt和精确ledger路径；提交时使用`git add -- <EXPERIMENTS.md> <manifest> <明确ledger文件>`，绝不暂存整个results目录或现有无关脏文件。

---

## 后续切片（本计划不提前实现）

1. 候选全部选出后，单独冻结40条边、至少800盘有效棋的formal计划和manifest。
2. 内部单调认证完成后，实施`ai_ladder_rung`数据库/幂等结果账本/五盘定级/累计净胜±3后端切片。
3. 后端真实契约可用后，按Galaxy再kiosk的用户旅程完成前端视觉确认、集成、RK3562 P95路由和fan账户验收。
