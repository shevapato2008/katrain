# 围棋 kiosk · 视觉 / 标定 / 实体盘(kiosk-go-vision)Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 给「盘被碰动了」和「误触取消了」这两件事补上回得来的路:① 取消之后还能沿用上次标定;② 漂移后先自动用**外框**(不亮灯)找回几何,不行再给用户一颗「对齐外框」——**盘上有子也能按**;③ ~~没有 LED 的盒子也能完成第一次标定~~(**Fan 2026-09-23 裁定本轮不做**);④ 把「LED 就绪」这句话改准(标定屏、左栏、设计稿源头),并产出一份可执行的上板清单。

**Architecture:**
- V2:服务端 `confirm_existing` 白名单加 `cancelled`(**不加 `degraded`**);前端 `canReuse` 与「为什么按不了」同步。
- V1:新建纯函数 `katrain/vision/relock.py`(按新单应重建 lock,**四角按旧锁朝向重排**,保留 `baseline`);标定服务接进 `CalibrationSelector`,漂移分支先试 `RUNTIME_RECALIBRATION`(策略表只有 `outer_corner`,**结构上不可能亮灯**),失败才降级;新增 `relocate()` + `POST /geometry/relocate` + 标定屏一颗键。自动那条**默认关**,等上板精度闸。
- V3(**⛔ 本轮不做,Fan 2026-09-23 裁定**,PRD §4;原设计留作以后):`start()` 在没有可用 LED 时走 `INITIAL_SETUP` 选择器(落到 `empty_board_autocal`),空盘要求不放开;前端 `canStart` 去掉 `ledReady`。
- V4 / Z3:标定屏那一格改「串口已连接」(复用设置屏的 key)、左栏改「已连接」、smartbox 设计稿源头同一个词(设置屏已由设置赛道改完;参考图不重拍);删零消费者的 `PoseLostBanner`。
- **与 09-21 至 09-23 识别优化的边界(PRD §2.1)**:新锁只经 `on_success` → `promote_geometry` → `vision.set_geometry()` 交付(视差重推、参照帧作废都由 worker 自己做);重定位期间**不挂起识别**;识别优化的文件一行不改。
- **重定位不写盘**:磁盘上那份是 LED 13 点的 golden reference,外框法是**本次会话的运行时修正**(重启后回到 `required`,可「沿用上次标定」)。这样也避开了发布/回滚与曝光校验那一整套。

**Tech Stack:** Python 3.12 + OpenCV + FastAPI(pytest);React 18 + TypeScript(vitest);Playwright(四图 / 承重)。

**Spec:** `superpowers/tracks/kiosk-go-vision/prd.md`

## Global Constraints

> **开工前先读 `prd.md` §6.0**:四条新赛道的共享文件归属与合并顺序。本赛道排在合并顺序第一位(设置赛道要引用它的状态词)。

- worktree `/Users/fan/Repositories/katrain-kiosk-go-vision`(分支 `feature/kiosk-go-vision`,基线 **`a512aa6a`** = 2026-09-24 合入 origin/develop(此前 `a586026b` / 原基线 `7a152df1`);**「识别优化零改动」一律对 `git merge-base HEAD origin/develop` 比,不写死提交号**;**不 push、不合并 develop**。
- Python 环境 `uv sync --extra web --extra vision`(光 `uv sync` 缺 fastapi ⇒ 基线会静默变空;光 `--extra web` 缺 OpenCV ⇒ 视觉测试在收集阶段全部报错,2026-09-23 实测);前端 `cd katrain/web/ui && npm ci`。
- **识别优化零改动(PRD §2.1 R4)**:`katrain/vision/{worker_inprocess,board_state,parallax,parallax_store,reference_frame,camera,service}.py`、`katrain/web/core/led_service.py` 一行不改;`katrain/web/server.py` **不改**(含 `drift_needed=` 那一行与 `_vision_needs_frames` / `_adjust_led_brightness`);`GeometryCalibrationScreen.tsx` 里的 `RAW_STREAM_SCALE` / `WARPED_STREAM_SCALE` 与 `onImageLoad` 乘回照原样保留。收尾由 Task 10 Step 2b 对 `git merge-base HEAD origin/develop` 核。
- **新锁的唯一交付口是 `on_success`**(PRD §2.1 R1):不许直接调 worker / extractor,不许原地改旧锁对象。**重定位期间不调 `on_suspend`**(R3:挂起会让 `recognition_ready` 掉下来,守卫把对局屏换成标定台)。
- **朝向**(R2):任何从外框法得到的锁,四角顺序都必须对齐到旧锁;对不齐就当失败处理。
- **硬规矩:LED 绝不为几何自动点亮。** 本轮新增的两条重定位路径都走 `Scenario`(`RUNTIME_RECALIBRATION` / `MANUAL_FALLBACK` 里 `outer_corner` 排第一),**不许**把 `led` 传进 `CalibrationContext`,也不许新增任何「自动闪灯」分支。这条有一条结构闸测试守着(Task 4)。
- **自动重定位默认关**:`AUTO_RELOCATE_ON_DRIFT = False` 写成源码里的字面量常量(不是 env —— 闸只看得见源码),注释里点名它等的是哪条上板闸。翻成 `True` 要和上板结果同一次提交。
- **不写盘**:重定位只更新内存 lock 并推给识别 worker(`on_success`),不碰 `persist_state` / `_persist_legacy`。
- `black -l 120`;`npx tsc -b`;两套构建都要绿(本轮碰了 `src/api/geometryApi.ts`,它在共享领地)。
- 新文案 `t('ns:key','中文默认')`,**并用 `katrain-i18n-expert` 补齐 11 语种 `.po`**(2026-09-23 更正:develop 已有 `tests/web_ui/test_kiosk_i18n.py`,`src/kiosk` 下每个 `t()` key 都要有 11 语种真译文,原来的「不改 `.po`」会让它变红;PRD §6.0 第 5 条)。能复用的现成 key 就复用。
- 屏 26 有参考图 ⇒ 四图关卡触发,跑两次排抖动,**交 Fan 确认**;承重按「最满」「最空」两态各量一次(真浏览器,jsdom 不作数)。
- 提交信息用中文,结尾用**执行时**系统提示给的 `Co-Authored-By` 行(下面各 Task 里的示例写的是 `Claude Opus 5.5 (1M context)`)。

---

## File Structure

| 文件 | 动作 | 职责 |
|---|---|---|
| `katrain/vision/relock.py` | **新建** | 按新单应重建 `GeometryLock`(四角对齐旧锁朝向、重算 corners/points,保留 baseline) |
| `tests/test_relock.py` | **新建** | 纯函数单测(含朝向闸:四种旋转 + 镜像、视差 nadir 同边、45° 拒绝) |
| `katrain/web/core/geometry_calibration_service.py` | 改 `:70-127`(构造,**保留 `drift_needed`**)、`:193-213`(白名单)、`:635-653`(漂移分支);新增 `relocate()` / `_try_relocate()`(行号在 `a586026b` 上核过,`a512aa6a` 上这些文件一字未变;V3 的 `:129` / `:479-533` / `_calibrate_no_led()` 本轮不动) | V1 V2 |
| `tests/test_geometry_calibration_service.py` | 追加 | V1 V2 的七条(含两条反向闸与一条结构闸) |
| `katrain/web/api/v1/endpoints/geometry.py` | 新增 `POST /relocate` | V1-b |
| `tests/test_geometry_api.py` | 追加 | 端点两条 |
| ~~`katrain/web/server.py`~~ | **不改**(服务默认参数就是开关常量;显式导入会让 lifespan 测试的假模块 ImportError) | — |
| `katrain/web/ui/src/api/geometryApi.ts`(共享) | 新增 `relocate()` | V1-b |
| `katrain/web/ui/src/kiosk/context/GeometryContext.tsx` | 新增 `relocate` 动作 | V1-b |
| `katrain/web/ui/src/kiosk/components/vision/GeometryCalibrationScreen.tsx` | V1-b 按钮、V2 判别位与原因、V4 措辞、V6 注释;`canStart` 不动(V3 不做);推流缩放那段不动 | 前端主体 |
| `katrain/web/ui/src/kiosk/__tests__/GeometryCalibrationScreen.test.tsx` | 追加 | 四态 × 有无 LED |
| `katrain/web/ui/src/kiosk/components/physical/PoseLostBanner.tsx` + `__tests__/PoseLostBanner.test.tsx` | **删** | Z3 |
| `katrain/web/ui/tests/kiosk-shell-geometry.spec.ts` | 在 `§11 标定屏` 那组加一态(cn + de) | 承重(最满),真浏览器;最空由既有那条守 |
| `katrain/web/ui/tests/kiosk-screen-26-calib.fourup.spec.ts` | 改实现侧图注一处 | V2 后「沿用要 phase∈{required,failed}」过期;V4 后 LED 那格是「串口已连接」 |
| `katrain/vision/tools/outer_corner_accuracy.py` | 追加 `grab_mjpeg_frames` / `measure_real` / `--live` | 上板闸的量具(Task 8b) |
| `tests/test_vision/test_outer_corner_accuracy.py` | 追加三条 | 真帧模式 |
| `superpowers/tracks/kiosk-go-vision/board-checklist.md` | **新建** | V5 上板清单 |
| `katrain/i18n/locales/*/LC_MESSAGES/katrain.po` | 追加本赛道全部新 `vision:*` key × 11 语种(约 7 个;`.mo` 被 `.gitignore:43` 忽略,本地生成、不提交) | Task 7b 收口,用 `katrain-i18n-expert` |
| ~~`katrain/web/ui/src/kiosk/pages/SettingsPage.tsx`~~ | **不改**(V4 那一格设置赛道已改,`3b8af0a2`) | — |
| `katrain/web/ui/src/kiosk/components/layout/GoConsoleRail.tsx` + `GoConsoleRail.test.tsx` | 「就绪」→「已连接」 | V4(Task 7) |
| smartbox `superpowers/shared/kiosk-shell/sample-go/go-kiosk{.tmpl,,-proto}.html` | `STATUS` 里 LED 那格同一个词;smartbox main 本地提交,不重拍参考图、不 push | V4 设计稿源头(Task 7 Step 4) |
| 识别优化文件(见 Global Constraints) | **一行不改** | — |

任务顺序:Task 1 基线 → Task 2 V2 → Task 3 relock 纯函数 → Task 4 服务端 V1 → Task 5 端点与前端 V1-b → ~~Task 6 V3~~(**⛔ 本轮不做,跳过**) → Task 7 V4 + Z3 → Task 8 四图与承重 → Task 8b 精度工具真帧模式 → Task 9 上板清单 → Task 10 收尾。
Task 2 与 Task 3 互相独立;Task 4 依赖 3;Task 5 依赖 4;Task 6 独立于 4/5(但都动同一个文件,按序做)。

### 执行编排(2026-09-24,Codex 第 1 轮后定)

执行者是**并行的子 agent**。并行写代码的 agent **绝不共用一棵工作树**(会互相冲掉未提交的改动)——
能并行的任务各开一个**隔离 worktree**,做完提交,由编排者按顺序合回本分支;其余一律串行。

| 批次 | 任务 | 为什么能 / 不能并行 |
|---|---|---|
| 0 | Task 1(基线) | 其余一切的起点;编排者自己做 |
| 1(并行,各自隔离 worktree) | Task 2(V2)· Task 3(relock 纯函数)· Task 8b(精度工具)· Task 9(上板清单)· Task 7 Step 4(smartbox 设计稿,另一个仓) | 文件互不相交。Task 2 碰 `geometry_calibration_service.py` 与标定屏,但本批没有别人碰这两个文件 |
| 2(串行) | Task 4 → Task 5 → Task 7(Step 1–3) → Task 7b → Task 8 | 4 依赖 3;4/5/7 都改 `geometry_calibration_service.py` 或标定屏及其测试;7b 要等 2/5/7 的 key 都落地;8 要量 5/7 的结果 |
| 3 | Task 10(收尾) | 编排者自己做 |

每个任务的提交**只 `git add` 本任务列出的文件**(已把各处 `git add -A` 换成精确列表)。
合回时若有冲突,冲突只可能来自批次 1 里 Task 2 与之后批次 2 的同文件改动 —— 批次 2 在批次 1 全部合回之后才开始,所以按上表执行不会冲突。


---

### Task 1: 核对 worktree、装依赖、记录双基线

**Files:** 不改仓内文件;基线写到 `$(git rev-parse --absolute-git-dir)/vision-baseline/`。

- [ ] **Step 1: worktree 与依赖**

```bash
cd /Users/fan/Repositories/katrain
# worktree 已于 2026-09-21 建好,本步只核对,不要再 add
git -C /Users/fan/Repositories/katrain-kiosk-go-vision rev-parse --abbrev-ref HEAD            # 预期 feature/kiosk-go-vision
git -C /Users/fan/Repositories/katrain-kiosk-go-vision merge-base --is-ancestor a512aa6a HEAD && echo base-ok
cd /Users/fan/Repositories/katrain-kiosk-go-vision
uv sync --extra web --extra vision
uv run python -c "import cv2, fastapi; print('env-ok')"   # 两个都要在,缺一个基线就会混进收集错误
cd katrain/web/ui && npm ci
```

- [ ] **Step 2: Python 基线**

```bash
cd /Users/fan/Repositories/katrain-kiosk-go-vision
BASE="$(git rev-parse --absolute-git-dir)/vision-baseline"; mkdir -p "$BASE"
CI=true uv run pytest tests --continue-on-collection-errors -q > "$BASE/before-py.log" 2>&1; echo "exit=$?"
grep '^FAILED\|^ERROR' "$BASE/before-py.log" | sort -u > "$BASE/before-py.txt"
wc -l < "$BASE/before-py.txt"
```

- [ ] **Step 2b: 识别优化的回归集与 i18n 闸的起点**(PRD §2.1 R5、§7「i18n 闸」)

```bash
cd /Users/fan/Repositories/katrain-kiosk-go-vision
BASE="$(git rev-parse --absolute-git-dir)/vision-baseline"
cat > "$BASE/recog-tests.txt" <<'EOF2'
tests/test_vision/test_parallax_apply.py tests/test_vision/test_parallax_fit.py tests/test_vision/test_parallax_store.py
tests/test_vision/test_parallax_wiring.py tests/test_vision/test_board_state_parallax.py tests/test_vision/test_board_state_golden.py
tests/test_vision/test_reference_frame.py tests/test_vision/test_sustain_threshold.py tests/test_vision/test_vision_idle.py
tests/test_vision/test_led_glow.py tests/test_vision/test_worker_commands.py tests/test_vision/test_calibrate_parallax.py
tests/test_vision/test_board_state_shadow.py tests/test_vision/test_shadow_phantom.py
tests/web_ui/test_led_brightness_loop.py tests/test_led_service.py tests/test_geometry_calibration_service.py
EOF2
xargs env CI=true uv run pytest -q < "$BASE/recog-tests.txt" 2>&1 | tail -1   # 2026-09-24 在 a512aa6a 上实测:362 passed
CI=true uv run pytest -q tests/web_ui/test_kiosk_i18n.py 2>&1 | tail -1               # 2026-09-24 实测:12 passed
CI=true uv run pytest -q tests/web_ui/test_kiosk_i18n.py 2>&1 | grep -c "'vision:"   # 预期 0
```

⚠️ `test_kiosk_i18n.py` 在 `a512aa6a` 上是绿的(09-23 时曾因别的赛道漏译 16 个 key 红过,develop `7cc6c5d4` 已补)。仍然保留按本赛道范围切的那行 `grep -c "'vision:"`:万一别的赛道再让它变红,失败的用例名早就在基线里,`comm` 比对会看不见本赛道新增的缺译。
(用 `xargs` 而不是 `$(cat …)`:zsh 不做词分割,后者会把整串当成一个参数。)

- [ ] **Step 3: 前端基线**(脚本同其它赛道:`failed-names.cjs` + `before-failed.txt`)

```bash
cd katrain/web/ui
BASE="$(git -C /Users/fan/Repositories/katrain-kiosk-go-vision rev-parse --absolute-git-dir)/vision-baseline"
cat > "$BASE/failed-names.cjs" <<'EOF'
const report = require(process.argv[2]);
const out = [];
for (const file of report.testResults) {
  const rel = file.name.replace(/^.*\/katrain\/web\/ui\//, '');
  if (file.status === 'failed' && file.assertionResults.length === 0) out.push(`${rel} :: <文件级失败>`);
  for (const a of file.assertionResults) if (a.status === 'failed') out.push(`${rel} :: ${a.fullName}`);
}
console.log(out.sort().join('\n'));
EOF
npx vitest run --reporter=json --outputFile="$BASE/before.json" > "$BASE/before.log" 2>&1
node "$BASE/failed-names.cjs" "$BASE/before.json" > "$BASE/before-failed.txt"
npx tsc -b; echo "tsc=$?"
```

---

### Task 2: V2 · 取消之后还能「沿用上次标定」

**Files:**
- Modify: `katrain/web/core/geometry_calibration_service.py`(`confirm_existing`,`:193-199`)
- Modify: `katrain/web/ui/src/kiosk/components/vision/GeometryCalibrationScreen.tsx`(`:342-345`、`:486-504` 的注释)
- Test: `tests/test_geometry_calibration_service.py`、`src/kiosk/__tests__/GeometryCalibrationScreen.test.tsx`

**Interfaces:**
- Produces:`confirm_existing()` 在 `{required, failed, cancelled}` 三态可用;前端 `canReuse` 同表。

- [ ] **Step 1: 写失败的测试**

```python
# tests/test_geometry_calibration_service.py:在**既有的**
# test_cancel_before_store_pointer_swap_keeps_old_generation_and_restores_exposure(:841)末尾、
# `service.stop()` 之前追加 —— 那条是真的 start → 卡在发布边界 → cancel → wait,取消之后 current_lock 仍是 old_lock。
# 在它上面接着验 V2,而不是另造一个 `_status["phase"] = "cancelled"` 的假状态:假状态验不了「沿用的是哪把锁」。
    # V2:取消之后「沿用上次标定」能用,而且沿用的是旧锁(不是被取消那次的新锁)
    status = service.confirm_existing()
    assert status["phase"] == "ready"
    assert status["session_calibrated"] is True
    assert service.current_lock is old_lock
    assert promoted == [old_lock]
```

回滚失败那条路(`test_...rollback...`,`current_lock` 被清成 None)不用新加:`confirm_existing` 对 `current_lock is None` 早就拒绝
(`no existing geometry to confirm`),Codex 第 1 轮核过发布边界之后取消不会落成 `cancelled`。

**反向闸已经在了**:`test_confirm_existing_cannot_override_degraded_state`(同文件,`match="only be confirmed after restart"`)。
**不要再加一条重复的**;下面 Step 3 改了报错文案,新文案仍以 `existing geometry can only be confirmed after restart` 开头,那条照旧匹配 —— 跑一下确认它还绿。

```tsx
// 追加到 src/kiosk/__tests__/GeometryCalibrationScreen.test.tsx 的 describe 里
// (照该文件既有写法:改模块级的 `status` 再调无参数的 `renderScreen()`;`acts()` 取动作区)
  it('取消之后「沿用上次标定」可以按', () => {
    status = { ...status, phase: 'cancelled', last_valid: true };
    renderScreen();
    expect(within(acts()).getByRole('button', { name: '沿用上次标定' })).toBeEnabled();
  });

  it('漂移失效时按不了,而且屏上说得出为什么', () => {
    status = { ...status, phase: 'degraded', last_valid: true };
    renderScreen();
    expect(within(acts()).getByRole('button', { name: '沿用上次标定' })).toBeDisabled();
    expect(screen.getByText(/棋盘挪动过/)).toBeInTheDocument();
  });
```

- [ ] **Step 2: 跑,确认失败**

```bash
cd /Users/fan/Repositories/katrain-kiosk-go-vision
CI=true uv run pytest tests/test_geometry_calibration_service.py -q -k "cancel or degraded"   # 预期:那条真取消测试在 confirm_existing 处红
cd katrain/web/ui && npx vitest run src/kiosk/__tests__/GeometryCalibrationScreen.test.tsx
```

- [ ] **Step 3: 服务端白名单**

```python
    # 取消过的运行也能沿用:取消时服务端什么都没丢(current_lock 还在,on_resume 已把识别
    # 恢复到旧几何),缺的只是把 phase 拉回 ready 的入口。**degraded 不在表里** ——
    # 那一态是「这份几何已知是错的」,它的出路是重定位(relocate),不是确认沿用。
    _REUSABLE_PHASES = frozenset({"required", "failed", "cancelled"})
    ...
            if self._status["phase"] not in self._REUSABLE_PHASES:
                raise ValueError(
                    "existing geometry can only be confirmed after restart, a failed run, or a cancelled run"
                )
```

- [ ] **Step 4: 前端判别位与原因**

```tsx
  const canReuse = (phase === 'required' || phase === 'failed' || phase === 'cancelled')
    && status.last_valid && cameraReady && !starting && !active;
  const reuseBlockedWhy = active ? '标定进行中'
    : !cameraReady ? '摄像头未连接，无法核对网格'
      : phase === 'ready' ? '这一局已经在用这次标定'
        // 「按不了」永远要有话说:degraded 是唯一剩下的按不了的情形。新文案走 t(),译文在 Task 7b 收口。
        : phase === 'degraded' ? t('vision:reuse_blocked_moved', '棋盘挪动过，上次的标定对不上了 —— 用「对齐外框」（不亮灯，盘上有子也能对）或重新标定')
          : null;
```

并把 `:486-504`(运行中那颗「取消标定」)那段注释末尾的「不配确认弹层 —— 取消是廉价且可逆的」改写为:

```
 * 不配确认弹层 —— 取消是廉价且可逆的:取消之后「沿用上次标定」仍然可以按
 * (2026-09-20 起,`_REUSABLE_PHASES` 含 cancelled)。**这句话在那之前是不成立的**,
 * 当时取消会让本次开机的标定一起作废;登记不做确认层的那条裁定,依据的正是这个前提。
```

- [ ] **Step 5: 跑,确认通过 + 提交**

```bash
CI=true uv run pytest tests/test_geometry_calibration_service.py -q
cd katrain/web/ui && npx vitest run src/kiosk/__tests__/GeometryCalibrationScreen.test.tsx && npx tsc -b
cd /Users/fan/Repositories/katrain-kiosk-go-vision && uv run black -l 120 katrain/web/core/geometry_calibration_service.py
git add katrain/web/core/geometry_calibration_service.py tests/test_geometry_calibration_service.py \
  katrain/web/ui/src/kiosk/components/vision/GeometryCalibrationScreen.tsx katrain/web/ui/src/kiosk/__tests__/GeometryCalibrationScreen.test.tsx
git commit -m "$(cat <<'EOF'
fix(vision): 取消标定之后仍可沿用上次标定

取消时服务端什么都没丢,缺的只是把 phase 拉回 ready 的入口。
degraded 不放开(那是「已知是错的」),并补一条反向闸钉住。
顺带把「取消廉价可逆」那条裁定的前提写清楚——在这次改动之前它并不成立。

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 3: V1-a · 按新单应重建 lock 的纯函数

**Files:**
- Create: `katrain/vision/relock.py`
- Test: `tests/test_relock.py`

**Interfaces:**
- Produces:`relock_with_homography(lock, M, Minv=None, *, frame_size=None, confidence=None) -> GeometryLock`。四角对齐到 `lock.corners`(先按旧锁的源分辨率换算到本次帧坐标)的朝向;新锁记本次帧的 `source_width/height`、外框法的 `confidence`,`diag` 加 `relocated_by="outer_corner"`。朝向分不清抛 `ValueError("orientation_ambiguous")`,四角平均位移超过 `MAX_SHIFT_CELLS = 3` 格抛 `ValueError("moved_too_far")`。

> **2026-09-23 改写**:原稿直接用外框法的 `M` 建锁,没管四角顺序。合并 develop 后核到:外框法按画面位置排四角,LED 锁按棋盘行列排,而新上线的视差校正靠四角顺序认「哪条边朝镜头」(盒上是 col 18 那条)。下面的测试与实现已在 `a586026b` 上用真模块跑过(15 passed、black 干净);**09-24 按 Codex 第 1 轮补了分辨率、位移上限、置信度与 diag,在 `a512aa6a` 上重跑 22 passed、black 干净**;`test_without_alignment_the_nadir_would_move` 是对照组,证明朝向那两条测得到东西。

- [ ] **Step 1: 写失败的测试**

```python
# tests/test_relock.py
"""按新单应重建 GeometryLock。

外框法(`OuterCornerStrategy`)只给得出 `M` / `Minv` —— 它是**帧单应**,
不产出整张网格。而识别用的是 `points`(19×19 的交叉点像素坐标),
所以要用新的 M 把四角映回原图,再走和首次标定同一个 `grid_points_from_corners`。

**朝向**(PRD §2.1 R2):外框法按**画面位置**排四角(`sort_corners`),LED 锁按**棋盘行列**排。
两者不一定一致 ⇒ 重建时把四角重排成离旧锁最近的那一种,否则整张网格转 90°/180°,
识别坐标、维持档、视差(`mount_parallax_for_lock` 按四角顺序认哪条边朝镜头)一起转。

`baseline`(空盘 HSV 基线)**原样保留**:它采在 warp 空间的 xs/ys 上,
几何对齐回同一块实体盘之后仍然成立;重采要空盘,而这条路存在的理由正是盘上有子。
"""
from dataclasses import replace

import cv2
import numpy as np
import pytest

from katrain.vision import geometry_calibrate
from katrain.vision.geometry_detect import sort_corners
from katrain.vision.geometry_lock import GeometryLock
from katrain.vision.parallax import mount_parallax_for_lock
from katrain.vision.relock import relock_with_homography

SIZE = 950
DST = np.array([[0, 0], [SIZE - 1, 0], [SIZE - 1, SIZE - 1], [0, SIZE - 1]], np.float32)
# 画面里的外框:下边成像最长 ⇒ 下边离镜头最近(视差认边靠的就是这个)。
IMG_QUAD = np.array([[200, 100], [800, 100], [900, 700], [100, 700]], np.float32)
BUMP = np.array([6.0, -4.0], np.float32)  # 盘被推了一点


def _lock(corners):
    corners = np.asarray(corners, np.float32)
    M = cv2.getPerspectiveTransform(corners, DST).astype(np.float64)
    xs = np.linspace(0, SIZE - 1, 19).astype(np.float32)
    return GeometryLock(
        corners=corners,
        points=geometry_calibrate.grid_points_from_corners(corners, size=SIZE).astype(np.float32),
        xs=xs, ys=xs.copy(), M=M, Minv=np.linalg.inv(M), out_size=SIZE,
        baseline=np.full((19, 19, 3), 7.0, np.float32), confidence=0.9,
    )


def _outer_M(quad):
    """外框法的输出形状:四角按**画面**左上/右上/右下/左下排,与锁的朝向无关。"""
    return cv2.getPerspectiveTransform(sort_corners(quad), DST).astype(np.float64)


def test_points_match_the_shared_grid_helper():
    lock = _lock(IMG_QUAD)
    out = relock_with_homography(lock, _outer_M(IMG_QUAD + BUMP))
    expected = geometry_calibrate.grid_points_from_corners(IMG_QUAD + BUMP, size=SIZE)
    assert np.allclose(out.points, expected, atol=0.5)
    assert np.allclose(out.corners, IMG_QUAD + BUMP, atol=0.5)


@pytest.mark.parametrize("roll", [0, 1, 2, 3])
def test_relock_keeps_the_lock_orientation(roll):
    """旧锁的四角是画面顺序转过 roll 格;外框法给的永远是画面顺序。重建后必须仍是旧锁的顺序。"""
    lock = _lock(np.roll(IMG_QUAD, roll, axis=0))
    out = relock_with_homography(lock, _outer_M(IMG_QUAD + BUMP))
    assert np.allclose(out.corners, np.roll(IMG_QUAD + BUMP, roll, axis=0), atol=0.5)
    assert np.allclose(out.points[0, 0], lock.points[0, 0] + BUMP, atol=0.5)  # 只随平移动,不换点


@pytest.mark.parametrize("roll", [0, 1, 2, 3])
def test_parallax_nadir_stays_on_the_same_edge(roll):
    """**守住 develop 的视差校正**(`f522fe53`):worker 在 set_geometry 里按新锁重推 nadir,
    朝镜头的是哪条边由四角顺序决定。朝向没对齐,nadir 就换到另一条边。"""
    lock = _lock(np.roll(IMG_QUAD, roll, axis=0))
    out = relock_with_homography(lock, _outer_M(IMG_QUAD + BUMP))
    assert mount_parallax_for_lock(out).nadir == mount_parallax_for_lock(lock).nadir


def test_mirrored_lock_order_is_kept_too():
    mirrored = IMG_QUAD[[0, 3, 2, 1]]
    out = relock_with_homography(_lock(mirrored), _outer_M(IMG_QUAD + BUMP))
    assert np.allclose(out.corners, mirrored + BUMP, atol=0.5)


def test_without_alignment_the_nadir_would_move():
    """对照:直接用画面顺序建锁(不对齐)时 nadir 会换边 —— 证明上面那条测得到东西。"""
    lock = _lock(np.roll(IMG_QUAD, 1, axis=0))
    M = _outer_M(IMG_QUAD)
    naive = replace(lock, corners=IMG_QUAD, M=M, Minv=np.linalg.inv(M))
    assert mount_parallax_for_lock(naive).nadir != mount_parallax_for_lock(lock).nadir


def test_a_board_turned_half_way_is_refused():
    """盘转了约 45°:最近与次近两种排法一样近,分不出朝向 ⇒ 拒绝,不猜。"""
    square = np.array([[100, 100], [900, 100], [900, 900], [100, 900]], np.float32)
    c, th = np.array([500.0, 500.0]), np.deg2rad(45)
    R = np.array([[np.cos(th), -np.sin(th)], [np.sin(th), np.cos(th)]])
    turned = ((square - c) @ R.T + c).astype(np.float32)
    with pytest.raises(ValueError, match="orientation_ambiguous"):
        relock_with_homography(_lock(square), cv2.getPerspectiveTransform(turned, DST))


def test_baseline_is_carried_over_untouched():
    lock = _lock(IMG_QUAD)
    out = relock_with_homography(lock, lock.M)
    assert out.baseline is lock.baseline or np.array_equal(out.baseline, lock.baseline)


def test_original_lock_is_not_mutated():
    lock = _lock(IMG_QUAD)
    before = lock.points.copy()
    relock_with_homography(lock, _outer_M(IMG_QUAD + BUMP))
    assert np.array_equal(lock.points, before)


def test_singular_homography_raises():
    with pytest.raises(ValueError):
        relock_with_homography(_lock(IMG_QUAD), np.zeros((3, 3), np.float64))


@pytest.mark.parametrize("roll", [0, 1, 2, 3])
def test_a_real_bump_is_accepted(roll):
    """真碰盘:平移 + 小角度旋转 + 一点透视。朝向保持,nadir 同边。"""
    c, th = IMG_QUAD.mean(axis=0), np.deg2rad(8)
    R = np.array([[np.cos(th), -np.sin(th)], [np.sin(th), np.cos(th)]])
    bumped = ((IMG_QUAD - c) @ R.T + c + np.array([25.0, -15.0])).astype(np.float32)
    bumped[2] += np.array([6.0, 4.0], np.float32)  # 透视:一个角多挪一点
    lock = _lock(np.roll(IMG_QUAD, roll, axis=0))
    out = relock_with_homography(lock, _outer_M(bumped))
    assert np.allclose(out.corners, np.roll(bumped, roll, axis=0), atol=0.5)
    assert mount_parallax_for_lock(out).nadir == mount_parallax_for_lock(lock).nadir


def test_a_board_moved_far_is_refused():
    """挪了 4 格:不是碰动,是换了位置 —— 拒绝,交给用户重新标定。"""
    cell = (IMG_QUAD[1, 0] - IMG_QUAD[0, 0]) / 18.0
    with pytest.raises(ValueError, match="moved_too_far"):
        relock_with_homography(_lock(IMG_QUAD), _outer_M(IMG_QUAD + np.array([4 * cell * 1.2, 0], np.float32)))


def test_new_lock_records_the_frame_resolution_it_was_computed_on():
    """旧锁在 1920x1080 上标定,这次帧是 1280x720:四角先换算再对齐,新锁记本次尺寸。"""
    lock = _lock(IMG_QUAD * 1.5)
    lock.source_width, lock.source_height = 1920, 1080
    out = relock_with_homography(lock, _outer_M(IMG_QUAD + BUMP), frame_size=(1280, 720))
    assert (out.source_width, out.source_height) == (1280, 720)
    assert np.allclose(out.corners, IMG_QUAD + BUMP, atol=0.5)


def test_confidence_and_diag_say_this_lock_came_from_relocation():
    lock = _lock(IMG_QUAD)
    lock.diag = {"source": "led_anchor_ransac", "orientation": "seated_human"}
    out = relock_with_homography(lock, _outer_M(IMG_QUAD + BUMP), confidence=0.73)
    assert out.confidence == pytest.approx(0.73)
    assert out.diag["relocated_by"] == "outer_corner"
    assert out.diag["orientation"] == "seated_human"
    assert lock.diag == {"source": "led_anchor_ransac", "orientation": "seated_human"}  # 旧锁没被改
```

- [ ] **Step 2: 跑,确认失败**

```bash
CI=true uv run pytest tests/test_relock.py -q
```

- [ ] **Step 3: 写实现**

```python
# katrain/vision/relock.py
"""把一个已有的 GeometryLock 搬到新的单应上(外框重定位用)。

`OuterCornerStrategy` 给的是**帧单应**(M / Minv),不产出网格与基线。识别要的是
`points`(19×19 交叉点像素坐标),所以这里用 M 把 warp 空间的四角映回原图,
再走与首次标定**同一个** `grid_points_from_corners` —— 两条路算网格的方式必须同源,
否则重定位之后的坐标会和标定时差一点点,而那一点点正好是「识别串位」。

**朝向**:外框法按画面位置排四角,LED 锁按棋盘行列排(`diag.orientation = "seated_human"`)。
这里把四角重排成离旧锁四角最近的那一种(4 个起点 × 2 个绕向),M 按重排后的四角重算。
盘只是被碰动时,最近的那一种比次近的近得多;两者分不开(盘转了约 45°)就拒绝,不猜。
外框是对称的,**盘被整个转了 90° 是认不出来的** —— 这里的前提是「碰动」,即小位移;
挪得超过 MAX_SHIFT_CELLS 就拒绝,交给用户重新标定。

**分辨率**:M 是在本次帧上算的。旧锁的四角先按它记录的源分辨率换算到本次帧坐标再比,
新锁记录本次帧的 `source_width/height` —— 否则 worker 的 `adjust_M_for_resolution`
会按旧尺寸把新 M 再缩放一次。

`baseline` 原样带过去:它采在 warp 空间的 xs/ys 上,几何对齐回同一块盘之后仍然成立;
重采需要空盘,而这条路存在的理由正是**盘上有子**。
"""

from dataclasses import replace

import cv2
import numpy as np

from katrain.vision import geometry_calibrate

# 同一块盘的四角在画面里的八种排法:四个起点 × 两个绕向。
_ORDERS = [tuple((start + step * i) % 4 for i in range(4)) for start in range(4) for step in (1, -1)]
# 「碰动」的上限:四角平均位移超过这么多格就不是碰动了(盘被挪走 / 换了位置),拒绝。
MAX_SHIFT_CELLS = 3.0


def _lock_corners_in_frame(lock, frame_size):
    corners = np.asarray(lock.corners, np.float64)
    src_w, src_h = getattr(lock, "source_width", None), getattr(lock, "source_height", None)
    if frame_size is None or not src_w or not src_h:
        return corners
    w, h = frame_size
    return corners * np.array([w / float(src_w), h / float(src_h)])


def _align_to_lock(quad, lock_corners):
    costs = sorted((float(np.linalg.norm(quad[list(order)] - lock_corners, axis=1).sum()), order) for order in _ORDERS)
    (best, order), (second, _) = costs[0], costs[1]
    if not best < 0.5 * second:
        raise ValueError("orientation_ambiguous")
    aligned = quad[list(order)]
    sides = np.linalg.norm(lock_corners - np.roll(lock_corners, -1, axis=0), axis=1)
    cell_px = float(sides.mean()) / 18.0
    if best / 4.0 > MAX_SHIFT_CELLS * cell_px:
        raise ValueError("moved_too_far")
    return aligned


def relock_with_homography(lock, M, Minv=None, *, frame_size=None, confidence=None):
    """``frame_size`` = (width, height) of the frames M was computed on."""
    M = np.asarray(M, np.float64)
    if M.shape != (3, 3):
        raise ValueError(f"M must be 3x3, got {M.shape}")
    if Minv is None:
        try:
            Minv = np.linalg.inv(M)
        except np.linalg.LinAlgError as exc:
            raise ValueError("singular homography") from exc
    Minv = np.asarray(Minv, np.float64)
    if not np.all(np.isfinite(Minv)):
        raise ValueError("singular homography")

    size = int(lock.out_size)
    dst = np.array([[0, 0], [size - 1, 0], [size - 1, size - 1], [0, size - 1]], np.float32)
    quad = cv2.perspectiveTransform(dst.reshape(-1, 1, 2), Minv).reshape(4, 2)
    corners = _align_to_lock(quad, _lock_corners_in_frame(lock, frame_size)).astype(np.float32)
    M = cv2.getPerspectiveTransform(corners, dst).astype(np.float64)
    points = geometry_calibrate.grid_points_from_corners(corners, size=size).astype(np.float32)
    changes = dict(corners=corners, points=points, M=M, Minv=np.linalg.inv(M))
    if frame_size is not None:
        changes.update(source_width=int(frame_size[0]), source_height=int(frame_size[1]))
    if confidence is not None:
        changes["confidence"] = float(confidence)
    # 这把锁不是 LED 13 点出来的:diag 里点名,排查识别问题时有个起点。旧的 anchors 等键留着(那是 golden 的来历)。
    changes["diag"] = {**(lock.diag or {}), "relocated_by": "outer_corner"}
    # `replace` 返回新对象 —— 调用方可能还拿着旧 lock(失败时要回退到它);也不许原地改(PRD §2.1 R1)。
    return replace(lock, **changes)
```

- [ ] **Step 4: 跑,确认通过 + 提交**

```bash
CI=true uv run pytest tests/test_relock.py -q
uv run black -l 120 katrain/vision/relock.py
git add katrain/vision/relock.py tests/test_relock.py
git commit -m "$(cat <<'EOF'
feat(vision): 按新单应重建 GeometryLock

外框法只给帧单应,识别要的是 19x19 网格 ⇒ 用同一个 grid_points_from_corners 重算,
两条路算网格的方式必须同源,否则重定位后会差一点点——那一点点就是识别串位。
四角按旧锁朝向重排:外框法按画面排、LED 锁按棋盘行列排,不对齐整盘会转,
视差 nadir 也会换边(有一条对照用例证明)。盘转约 45° 分不清朝向时拒绝。
baseline 原样保留:重采要空盘,而这条路存在的理由正是盘上有子。

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 4: V1-b · 标定服务接进选择器:漂移先自动重定位,并给出 `relocate()`

**Files:**
- Modify: `katrain/web/core/geometry_calibration_service.py`
- **不改** `katrain/web/server.py`(见 Step 3 末尾)
- Test: `tests/test_geometry_calibration_service.py`(追加 15 条,含两条反向闸、一条结构闸、四条并发/交付闸、一条相机掉线);`tests/web_ui/test_board_lifespan_camera_degraded.py`(不改,跑它兜 `server.py` 那段构造)

**Interfaces:**
- Consumes:Task 3 的 `relock_with_homography(lock, M, Minv, *, frame_size, confidence)`;Task 2 的 `_REUSABLE_PHASES`。
- Produces:
  - 模块常量 `AUTO_RELOCATE_ON_DRIFT: bool = False`、`_RELOCATABLE_PHASES = {degraded, cancelled, failed}`;
  - `GeometryCalibrationService(..., drift_needed=None, selector=None, auto_relocate=AUTO_RELOCATE_ON_DRIFT)` —— **`drift_needed` 是 develop `275625ec` 加的,原样保留**(漂移检测只在有人用摄像头时跑;自动重定位长在漂移分支里,所以也只在那时跑);
  - `service.relocate(trigger="manual") -> dict`:只在 `_RELOCATABLE_PHASES` 可用(否则 `ValueError`);标定或重定位进行中抛 `CalibrationBusy`;失败抛 `ValueError(<原因>)`,原因同时写进 `status()["relocate_error"]`;
  - `status()` 多一个键 `relocate_error: str | None`;`metrics["relocated"] = 1.0`(数值,前端类型是 `Record<string, number | null>`);
  - 重定位进行中:`start()` 抛 `CalibrationBusy`,`confirm_existing()` 抛 `ValueError("relocation in progress")`(那个端点只把 ValueError 映射成 409);
  - `_apply_drift(drift, monitor=None)`:传入的 monitor 不是当前那个就忽略(过期结论);
  - 内部 `_relocate(scenario, *, trigger, allowed_phases) -> str | None`、`_compute_relocation(lock, scenario)`、`_adopt_relocated_lock(lock, *, trigger) -> str | None`。

- [ ] **Step 1: 写失败的测试**

```python
# 追加到 tests/test_geometry_calibration_service.py
# 照该文件既有写法:每条就地构造服务,用文件顶部的 FakeLed / FreshFakeCapture / FakeDrift ——
# 这个文件没有共享夹具,别自创 conftest。锁与「推了一点」的单应从 tests/test_relock.py 拿(`tests/` 是包)。
from katrain.web.core import geometry_calibration_service as calibration_module
from tests.test_relock import BUMP, DST, IMG_QUAD, _lock, _outer_M


class _FakeSelector:
    """只回一个给定的单应,或者失败。**不接受 led** —— 传进来就炸,这是结构闸的一半。"""

    def __init__(self, M=None, reason="no_board_detected", confidence=0.8):
        self.M, self.reason, self.confidence, self.calls = M, reason, confidence, []

    def calibrate(self, scenario, ctx):
        from katrain.vision.calibration_strategy import CalibrationOutcome

        assert ctx.led is None, "重定位路径绝不允许把 led 交给策略(硬规矩:LED 不为几何自动点亮)"
        self.calls.append(scenario)
        if self.M is None:
            return CalibrationOutcome(ok=False, strategy="outer_corner", reason=self.reason)
        return CalibrationOutcome(
            ok=True, M=self.M, Minv=np.linalg.inv(self.M), confidence=self.confidence, strategy="outer_corner"
        )


class _Calls:
    def __init__(self):
        self.success, self.degraded, self.suspend, self.persist = [], [], [], []


def _relocating_service(*, selector, auto_relocate=True, phase="ready", capture=None):
    calls = _Calls()
    service = GeometryCalibrationService(
        led=FakeLed(),
        capture=capture or FreshFakeCapture(),
        # 用 persist_state 而不是 save_path:这样「写没写盘」能直接数(不写盘是本条路的约束)
        persist_state=lambda lock, strategy, before_publish: calls.persist.append(lock),
        initial_lock=_lock(IMG_QUAD),
        on_success=calls.success.append,
        on_degraded=lambda: calls.degraded.append(True),
        on_suspend=lambda: calls.suspend.append(True),
        selector=selector,
        auto_relocate=auto_relocate,
    )
    service._status["phase"] = phase
    return service, calls


def test_drift_auto_relocates_instead_of_degrading():
    service, calls = _relocating_service(selector=_FakeSelector(M=_outer_M(IMG_QUAD + BUMP), confidence=0.77))

    service._apply_drift(FakeDrift(degraded=True))

    status = service.status()
    assert status["phase"] == "ready"                              # 不进标定台
    assert len(calls.success) == 1                                 # 新几何经 on_success 推给识别 worker(R1)
    assert np.allclose(calls.success[0].corners, IMG_QUAD + BUMP, atol=0.5)
    assert calls.degraded == []
    assert calls.suspend == []      # PRD §2.1 R3:挂起会让守卫把对局屏换成标定台
    assert calls.persist == []      # 不写盘:磁盘上那份是 LED golden reference
    assert status["metrics"].get("relocated") == 1.0               # metrics 是 Record<string, number|null>,不放布尔
    assert status["relocate_error"] is None
    assert status["confidence"] == pytest.approx(0.77)             # 报的是这次外框法的置信度,不是旧锁的
    service.stop()


def test_drift_degrades_when_relocation_fails():
    service, calls = _relocating_service(selector=_FakeSelector(M=None, reason="no_board_detected"))

    service._apply_drift(FakeDrift(degraded=True))

    status = service.status()
    assert status["phase"] == "degraded"                           # 终态与今天相同
    assert status["error"] == "board_moved"
    assert status["relocate_error"] == "no_board_detected"         # 原因放独立字段,不塞进数值型 metrics
    assert calls.degraded == [True]
    service.stop()


def test_auto_relocate_is_off_by_default(tmp_path):
    """**反向闸。** 默认关,等上板精度闸(< 0.12 格)。这条一旦变绿说明有人把默认打开了。"""
    assert calibration_module.AUTO_RELOCATE_ON_DRIFT is False
    selector = _FakeSelector(M=_outer_M(IMG_QUAD + BUMP))
    service = GeometryCalibrationService(          # 不传 auto_relocate:用默认
        led=FakeLed(), capture=FreshFakeCapture(), save_path=tmp_path / "geometry.npz",
        initial_lock=_lock(IMG_QUAD), selector=selector,
    )
    service._status["phase"] = "ready"

    service._apply_drift(FakeDrift(degraded=True))

    assert service.status()["phase"] == "degraded"
    assert selector.calls == []                                    # 根本没去试
    service.stop()


@pytest.mark.parametrize("phase", ["degraded", "cancelled", "failed"])
def test_manual_relocate_works_on_a_crowded_board(phase):
    selector = _FakeSelector(M=_outer_M(IMG_QUAD + BUMP))
    service, calls = _relocating_service(selector=selector, auto_relocate=False, phase=phase)

    out = service.relocate(trigger="manual")                       # **不要求空盘**

    assert out["phase"] == "ready"
    assert selector.calls[-1].name == "MANUAL_FALLBACK"
    assert len(calls.success) == 1 and calls.suspend == [] and calls.persist == []
    service.stop()


@pytest.mark.parametrize("phase", ["ready", "required"])
def test_manual_relocate_refuses_outside_its_three_phases(phase):
    """ready 下会拿低精度外框锁换掉好锁;required 下会绕过「沿用上次标定」。都不许。"""
    selector = _FakeSelector(M=_outer_M(IMG_QUAD + BUMP))
    service, calls = _relocating_service(selector=selector, phase=phase)

    with pytest.raises(ValueError, match="only available after drift, cancel or failure"):
        service.relocate(trigger="manual")
    assert selector.calls == [] and calls.success == []
    service.stop()


def test_manual_relocate_reports_why_it_failed():
    service, _calls = _relocating_service(selector=_FakeSelector(M=None, reason="no_board_detected"), phase="degraded")

    with pytest.raises(ValueError, match="no_board_detected"):
        service.relocate(trigger="manual")
    assert service.status()["phase"] == "degraded"
    assert service.status()["relocate_error"] == "no_board_detected"
    service.stop()


def test_manual_relocate_refuses_an_ambiguous_orientation():
    """盘转了约 45°:relock 分不清朝向 ⇒ 当失败,不猜(PRD §2.1 R2)。"""
    import cv2

    square = np.array([[100, 100], [900, 100], [900, 900], [100, 900]], np.float32)
    c, th = np.array([500.0, 500.0]), np.deg2rad(45)
    R = np.array([[np.cos(th), -np.sin(th)], [np.sin(th), np.cos(th)]])
    turned = ((square - c) @ R.T + c).astype(np.float32)
    service, calls = _relocating_service(
        selector=_FakeSelector(M=cv2.getPerspectiveTransform(turned, DST)), phase="degraded"
    )
    service.current_lock = _lock(square)

    with pytest.raises(ValueError, match="orientation_ambiguous"):
        service.relocate(trigger="manual")
    assert calls.success == []
    service.stop()


def test_manual_relocate_refuses_while_a_calibration_runs():
    service, _calls = _relocating_service(selector=_FakeSelector(M=_outer_M(IMG_QUAD + BUMP)), phase="degraded")
    release = threading.Event()
    service._thread = threading.Thread(target=release.wait, daemon=True)   # 造「正在标定」:只看线程活没活
    service._thread.start()
    try:
        with pytest.raises(CalibrationBusy):
            service.relocate(trigger="manual")
    finally:
        release.set()
        service._thread.join(timeout=2)
    service.stop()


class _BlockingSelector(_FakeSelector):
    """外框检测「正在跑」:进来就停住,等测试放行。用来在**真的** relocate 窗口里戳别的入口。"""

    def __init__(self, M):
        super().__init__(M=M)
        self.entered, self.release = threading.Event(), threading.Event()

    def calibrate(self, scenario, ctx):
        self.entered.set()
        self.release.wait(timeout=5)
        return super().calibrate(scenario, ctx)


def test_start_reuse_and_a_second_relocate_are_refused_while_a_real_relocation_runs():
    """互斥要覆盖**整个**窗口 —— 在线程里真跑一次 relocate,卡在外框检测里,再去按别的键。
    (只把 `_relocating` 手动设成 True 的测试证明不了「从占住到结果落定」。)"""
    selector = _BlockingSelector(M=_outer_M(IMG_QUAD + BUMP))
    service, _calls = _relocating_service(selector=selector, phase="failed")
    worker = threading.Thread(target=service.relocate, kwargs={"trigger": "manual"}, daemon=True)
    worker.start()
    assert selector.entered.wait(timeout=2)
    try:
        with pytest.raises(CalibrationBusy):
            service.start(trigger="manual", empty_confirmed=True)
        # confirm_existing 走 ValueError:/confirm-existing 只把 ValueError 映射成 409(geometry.py:146)
        with pytest.raises(ValueError, match="relocation in progress"):
            service.confirm_existing()
        with pytest.raises(CalibrationBusy):
            service.relocate(trigger="manual")
    finally:
        selector.release.set()
        worker.join(timeout=5)
    assert service.status()["phase"] == "ready"
    service.stop()


def test_ready_is_not_published_before_the_new_lock_is_delivered():
    """先交付、后发布:on_success 还没回来时,status() 不许说 ready,current_lock / revision 不许换。"""
    service, _calls = _relocating_service(selector=_FakeSelector(M=_outer_M(IMG_QUAD + BUMP)), phase="degraded")
    old_lock, old_revision = service.current_lock, service.status()["geometry_revision"]
    entered, release = threading.Event(), threading.Event()

    def slow_delivery(_lock):
        entered.set()
        release.wait(timeout=5)

    service.on_success = slow_delivery
    worker = threading.Thread(target=service.relocate, kwargs={"trigger": "manual"}, daemon=True)
    worker.start()
    assert entered.wait(timeout=2)
    try:
        status = service.status()
        assert status["phase"] == "degraded"
        assert status["geometry_revision"] == old_revision
        assert service.current_lock is old_lock
    finally:
        release.set()
        worker.join(timeout=5)
    assert service.status()["phase"] == "ready"
    assert service.current_lock is not old_lock
    service.stop()


class _CameraDropsOnFourthGrab(FreshFakeCapture):
    """前三次取帧正常(给外框检测),第四次(重建漂移基准)掉线。"""

    def grab_fresh(self, settle_ms=0.0):
        if self.grab_calls >= 3:
            self.grab_calls += 1
            raise RuntimeError("camera dropped")
        return super().grab_fresh(settle_ms=settle_ms)


def test_a_camera_that_drops_while_rearming_drift_is_a_clean_failure():
    """重建漂移基准时相机掉线:干净的失败(400 + 原因),不是 500,也不发布新锁。"""
    service, calls = _relocating_service(
        selector=_FakeSelector(M=_outer_M(IMG_QUAD + BUMP)), phase="degraded", capture=_CameraDropsOnFourthGrab()
    )
    with pytest.raises(ValueError, match="drift_setup_failed"):
        service.relocate(trigger="manual")
    assert service.status()["phase"] == "degraded"
    assert service.status()["relocate_error"] == "drift_setup_failed"
    assert calls.success == []
    service.stop()


def test_a_stale_drift_result_does_not_undo_a_fresh_relocation():
    """漂移线程拿着它那一轮开头缓存的旧 monitor;这期间手动对齐已换了新锁 ⇒ 旧结论作废,不许把新锁降级。"""
    service, calls = _relocating_service(
        selector=_FakeSelector(M=_outer_M(IMG_QUAD + BUMP)), auto_relocate=False, phase="degraded"
    )
    stale_monitor = object()
    service.relocate(trigger="manual")

    service._apply_drift(FakeDrift(degraded=True), monitor=stale_monitor)

    assert service.status()["phase"] == "ready"
    assert calls.degraded == []
    service.stop()


def test_a_relocation_that_cannot_be_delivered_does_not_claim_ready():
    """新锁交不到识别 worker(on_success 抛错):不许停在 ready —— 降级,并说清原因。"""
    service, calls = _relocating_service(selector=_FakeSelector(M=_outer_M(IMG_QUAD + BUMP)), phase="degraded")

    def boom(_lock):
        raise RuntimeError("worker gone")

    old_lock, old_revision = service.current_lock, service.status()["geometry_revision"]
    service.on_success = boom
    with pytest.raises(ValueError, match="delivery_failed"):
        service.relocate(trigger="manual")
    assert service.status()["phase"] == "degraded"
    assert service.status()["relocate_error"] == "delivery_failed"
    assert service.current_lock is old_lock                    # 没交付的锁不许留在服务里
    assert service.status()["geometry_revision"] == old_revision
    assert calls.degraded == [True]
    service.stop()
```

- [ ] **Step 2: 跑,确认失败**

```bash
CI=true uv run pytest tests/test_geometry_calibration_service.py -q -k "relocat or drift or off_by_default"
```

- [ ] **Step 3: 实现**

模块顶部(`CalibrationBusy` 定义附近):

```python
# 漂移之后要不要**自动**用外框找回几何(不亮灯)。
#
# **默认关,等一条上板闸**:满盘下外框法的几何误差要 < 0.12 格(按 19×19 网格最大误差量,
# 见 Task 8b)。在没量之前打开它,等于让一个没验过精度的矩阵去指挥识别 —— 症状会是
# 「偶尔串位」,比直接降级更难查。翻成 True 要和上板结果写在同一次提交里
# (见 track 的 board-checklist.md 第 1–2 项);翻之前还要先有「识别栅栏」(PRD §4 V1-c)。
# 写成源码里的字面量而不是 env:闸只看得见源码。
AUTO_RELOCATE_ON_DRIFT = False

# 用户按的「对齐外框」只在这三态可用:ready 下会拿低精度外框锁换掉好锁,
# required 下会绕过「沿用上次标定」。
_RELOCATABLE_PHASES = frozenset({"degraded", "cancelled", "failed"})
```

构造函数:签名末尾加两个参数,**在 `self._drift_thread.start()` 之前**赋值(漂移线程一起来就可能用到它们),
`_status` 初值加一个键:

```python
    def __init__(
        self,
        *,
        led,
        capture,
        save_path=None,
        persist_state=None,
        initial_lock=None,
        on_success=None,
        on_degraded=None,
        on_suspend=None,
        on_resume=None,
        calibrator_factory=LedGeometryCalibrator,
        drift_needed=None,                        # develop 275625ec 加的,原样保留
        selector=None,
        auto_relocate=AUTO_RELOCATE_ON_DRIFT,
    ):
        ...                                       # 原有赋值一行不动
        # 外框重定位(V1)。selector 懒建(_get_selector);_relocating 是「正在重定位」的互斥标志,
        # 读写都在 self._lock 里,从占住到交付完成一直持有 —— start / confirm_existing / relocate 见到它一律拒绝。
        self.selector = selector
        self.auto_relocate = auto_relocate
        self._relocating = False
        ...                                       # self._drift_thread = ...; .start() 在这之后
        self._status = {
            ...,                                  # 原有键
            "relocate_error": None,               # 最近一次重定位为什么没成(字符串);metrics 是数值型,不放这里
        }

    def _get_selector(self):
        if self.selector is None:
            from katrain.vision.calibration_registry import build_default_selector

            self.selector = build_default_selector()
        return self.selector
```

`start()`:在 `with self._lock:` 里、现有「线程还活着」那条判断旁边加

```python
            if self._relocating:
                raise CalibrationBusy("geometry relocation in progress")
```

`confirm_existing()`:在 `with self._lock:` 里**第一条**加(用 ValueError:`/confirm-existing` 只把 ValueError 映射成 409),
并把白名单换成 Task 2 的 `_REUSABLE_PHASES`(Task 2 已做);成功那次 `self._status.update(...)` 里加 `relocate_error=None`:

```python
            if self._relocating:
                raise ValueError("relocation in progress")
```

`_run` 成功那次 `self._status.update(phase="ready", ...)` 里也加 `relocate_error=None`。

重定位主体(三个方法):

```python
    def _relocate(self, scenario, *, trigger: str, allowed_phases) -> str | None:
        """外框重定位一次:占住互斥 → 取帧 → 选择器 → relock → 交付 → 发布。成功回 None,失败回原因串。

        **绝不亮灯**:`Scenario` 决定 allow_led,而且这里根本不把 `led` 交给 `CalibrationContext`(防御在两层)。
        **不写盘**:磁盘上那份是 LED 13 点的 golden reference,外框法是本次开机的运行时修正。
        **不挂起识别**(PRD §2.1 R3)。互斥从占住一直持有到**结果落定**(成功发布,或失败原因写进 status),
        期间 start / confirm_existing / 另一次 relocate 都进不来 —— 否则两边会互相覆盖 current_lock、phase 与错误。
        """
        with self._lock:
            if self._relocating or (self._thread is not None and self._thread.is_alive()):
                raise CalibrationBusy("geometry calibration or relocation already running")
            if self._status["phase"] not in allowed_phases:
                raise ValueError("relocate is only available after drift, cancel or failure")
            if self.current_lock is None:
                raise ValueError("no existing geometry to relocate")
            self._relocating = True
            lock = self.current_lock
        reason = None
        try:
            new_lock, reason = self._compute_relocation(lock, scenario)
            if new_lock is not None:
                reason = self._adopt_relocated_lock(new_lock, trigger=trigger)
            return reason
        finally:
            with self._lock:
                # 失败原因在**放开互斥之前**落定:放开之后别的请求可能已经开始下一轮,再写就盖到下一轮身上。
                if reason is not None:
                    self._status["relocate_error"] = reason
                self._relocating = False

    def _compute_relocation(self, lock, scenario):
        from katrain.vision.calibration_strategy import CalibrationContext
        from katrain.vision.relock import relock_with_homography

        grab = getattr(self.capture, "grab_fresh", None)
        if grab is None:
            return None, "no_capture"
        frames = []
        try:
            for _ in range(3):
                frame, _seq, _ts = grab(settle_ms=0.0)   # grab_fresh 自己会把空闲的相机叫醒(develop 275625ec)
                if frame is not None:
                    frames.append(frame)
        except Exception as exc:                      # 相机掉线:干净的失败,不是 500
            logger.warning("relocation could not read frames: %s", exc)
            return None, "no_frame"
        if not frames:
            return None, "no_frame"
        height, width = frames[0].shape[:2]
        ctx = CalibrationContext(
            frames=frames, board=None, geometry=lock, led=None, capture=self.capture, out_size=int(lock.out_size)
        )
        # 选择器**不包 try**:OuterCornerStrategy 找不到盘回的是 ok=False,抛异常只可能是 bug ——
        # 也包括测试里那条「led 不许交给策略」的断言,包住就把结构闸吞了。
        out = self._get_selector().calibrate(scenario, ctx)
        if not out.ok or out.M is None:
            return None, out.reason or "relocate_failed"
        try:
            return (
                relock_with_homography(lock, out.M, out.Minv, frame_size=(width, height), confidence=out.confidence),
                None,
            )
        except ValueError as exc:                     # orientation_ambiguous / moved_too_far / singular homography
            return None, str(exc)

    def _adopt_relocated_lock(self, lock, *, trigger: str) -> str | None:
        """**先交付、后发布**:on_success 成功之前,status() 不许说 ready,current_lock / revision 不许换
        (否则慢回调期间前端看到假 ready,回调失败后服务里还留着一把没交付的锁)。
        交付失败 ⇒ 旧锁与 revision 原样留着,降级、让下游清掉几何 —— 与漂移降级同一条出路。"""
        try:
            monitor = self._prepare_drift_monitor(lock)   # 要取一帧:相机可能正好掉线(同文件已有这种用例)
        except Exception as exc:
            logger.warning("relocation could not re-arm drift monitoring: %s", exc)
            return "drift_setup_failed"
        try:
            self.on_success(lock)
        except Exception as exc:
            logger.warning("relocated geometry could not be delivered: %s", exc)
            with self._lock:
                self._status.update(phase="degraded", error="board_moved")
            self.on_degraded()
            return "delivery_failed"
        with self._lock:
            self.current_lock = lock
            self._drift_monitor = monitor
            self._geometry_revision += 1
            self._status.update(
                phase="ready", session_calibrated=True, last_valid=True, trigger=trigger, error=None, relocate_error=None
            )
            self._status["metrics"] = {**self._status["metrics"], "relocated": 1.0}
        return None
```

漂移分支(`_apply_drift`)与漂移循环:

```python
    def _apply_drift(self, drift, monitor=None) -> None:
        if not drift.degraded:
            return
        with self._lock:
            if self._status["phase"] != "ready":
                return
            # 漂移线程用的是它那一轮开头缓存的 monitor;这期间若已换了新锁(手动对齐外框),
            # 旧 monitor 的结论作废。monitor=None(直接调用,如既有测试)时照旧处理。
            if monitor is not None and monitor is not self._drift_monitor:
                return
        reason = None
        # 先试着**自己找回来**(外框,不亮灯)。今天这里直接降级,而降级的出路是
        # 13 点 LED 流程 —— 那要求空盘,也就是「这局别下了」。
        # **这里不调 on_suspend**:挂起会让 recognition_ready 掉下来,PhysicalBoardGuard 就把对局屏
        # 卸载换成标定台 —— 正是这条路要避免的。代价是找回来之前 worker 还按旧几何识别几秒;
        # 翻开 AUTO_RELOCATE_ON_DRIFT 之前要先补「识别栅栏」(PRD §4 V1-c)。
        if self.auto_relocate:
            from katrain.vision.calibration_strategy import Scenario

            try:
                reason = self._relocate(
                    Scenario.RUNTIME_RECALIBRATION, trigger="auto_relocate", allowed_phases=frozenset({"ready"})
                )
            except (CalibrationBusy, ValueError) as exc:
                reason = str(exc)
            if reason is None or reason == "delivery_failed":   # 成功;或 _adopt 已经降级过了
                return
        with self._lock:
            if self._status["phase"] != "ready":
                return
            self._status["phase"] = "degraded"
            self._status["error"] = "board_moved"
            self._status["relocate_error"] = reason
            self._status["metrics"].update(shift_cells=drift.shift_cells, drift_response=drift.response)
        self.on_degraded()
```

`_drift_loop` 里那一行改成把这一轮的 monitor 一起交进去:

```python
                self._apply_drift(monitor.update(frame), monitor=monitor)
```

用户按的那条:

```python
    def relocate(self, trigger: str = "manual") -> dict:
        """用户按的「对齐外框」。**不要求空盘** —— 这颗键存在的理由正是盘上有子。

        走 `MANUAL_FALLBACK`:策略表里 `outer_corner` 排第一,`led_fiducial` 排第二但本轮**不接**
        (它要求空盘,而且 `_compute_relocation` 根本不把 `led` 交出去 ⇒ 它自己 is_applicable 为假)。
        """
        from katrain.vision.calibration_strategy import Scenario

        reason = self._relocate(Scenario.MANUAL_FALLBACK, trigger=trigger, allowed_phases=_RELOCATABLE_PHASES)
        if reason is not None:
            raise ValueError(reason)          # relocate_error 已在 _relocate 放开互斥之前写好
        return self.status()
```

`server.py`:**不改**(2026-09-24 Codex 第 2 轮后定)。服务构造参数 `auto_relocate` 的默认值就是 `AUTO_RELOCATE_ON_DRIFT`,不显式传也是它;而显式导入这个常量会让 `tests/web_ui/test_board_lifespan_camera_degraded.py:357-361`、`:706-710` 注入的假模块(只给了 `GeometryCalibrationService`)在 lifespan 里 `ImportError`。开关的说明写在服务模块顶部那段注释里。

- [ ] **Step 4: 跑,确认通过**

```bash
CI=true uv run pytest tests/test_geometry_calibration_service.py tests/test_relock.py -q
# server.py 不改;跑 lifespan 测试确认服务构造签名的变化没把 board 模式的启动打坏
CI=true uv run pytest tests/web_ui/test_board_lifespan_camera_degraded.py -q
uv run black -l 120 katrain/web/core/geometry_calibration_service.py
```

- [ ] **Step 5: 结构闸单独跑一遍(它守的是硬规矩)**

```bash
CI=true uv run pytest tests/test_geometry_calibration_service.py -q -k "led" -rA | tail -20
uv run python -c "from katrain.vision.calibration_strategy import Scenario; assert not Scenario.RUNTIME_RECALIBRATION.allows_led(); print('ok')"
```

- [ ] **Step 6: 提交**

```bash
git add katrain/web/core/geometry_calibration_service.py tests/test_geometry_calibration_service.py
git commit -m "$(cat <<'EOF'
feat(vision): 漂移后先用外框自动重定位,并给出用户按的 relocate()

库里 P12 那套选择器一直没接进主链(唯一调用方是摆谱采集)。现在接上:
漂移先试 RUNTIME_RECALIBRATION(只有 outer_corner,结构上不可能亮灯),
失败才降级;degraded/cancelled/failed 三态给一条不要求空盘的人工出口。
自动那条默认关,等满盘精度上板闸,并有一条反向闸钉住「默认关」。

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 5: V1-c · `POST /geometry/relocate` 与标定屏那颗「对齐外框」

**Files:**
- Modify: `katrain/web/api/v1/endpoints/geometry.py`
- Modify: `katrain/web/ui/src/api/geometryApi.ts`(共享)、`src/kiosk/context/GeometryContext.tsx`、`GeometryCalibrationScreen.tsx`
- Test: `tests/test_geometry_api.py`、`GeometryCalibrationScreen.test.tsx`、`src/api/geometryApi.test.ts`

**Interfaces:**
- Produces:`POST /api/v1/geometry/relocate` → `GeometryStatus`;409 = 正在标定;400 = 找不到外框;404 = 这台机器没有标定服务。
  前端 `GeometryAPI.relocate()` 与 `useGeometry().relocate()`。

- [ ] **Step 1: 写失败的测试**

```python
# 追加到 tests/test_geometry_api.py 的 class TestGeometryEndpoint 里
# (照 confirm-existing 那三条的写法:`_client()` + 挂一个假的 geometry_calibration)
    def test_relocate_returns_status(self):
        class FakeCalibration:
            def relocate(self, *, trigger):
                assert trigger == "manual"
                return {"phase": "ready", "session_calibrated": True}

        app, c = _client()
        app.state.geometry_calibration = FakeCalibration()

        response = c.post("/geometry/relocate")

        assert response.status_code == 200
        assert response.json()["phase"] == "ready"

    def test_relocate_conflicts_while_calibrating(self):
        from katrain.web.core.geometry_calibration_service import CalibrationBusy

        class BusyCalibration:
            def relocate(self, *, trigger):
                raise CalibrationBusy("geometry calibration already running")

        app, c = _client()
        app.state.geometry_calibration = BusyCalibration()

        assert c.post("/geometry/relocate").status_code == 409

    def test_relocate_reports_a_reason_when_the_frame_has_no_board(self):
        class NoBoardCalibration:
            def relocate(self, *, trigger):
                raise ValueError("no_board_detected")

        app, c = _client()
        app.state.geometry_calibration = NoBoardCalibration()

        response = c.post("/geometry/relocate")

        assert response.status_code == 400
        assert response.json()["detail"] == "no_board_detected"

    def test_relocate_returns_404_without_calibration_service(self):
        _, c = _client()
        assert c.post("/geometry/relocate").status_code == 404
```

```tsx
// src/kiosk/__tests__/GeometryCalibrationScreen.test.tsx
// ① 顶部与 startCalibration / cancelCalibration / confirmExisting 同列加一个:
const relocate = vi.fn();
// ② vi.mock('../context/GeometryContext', …) 返回的对象里加上 relocate:
//    useGeometry: () => ({ status, loaded, startCalibration, cancelCalibration, confirmExisting, relocate, refresh: vi.fn() }),
// ③ describe 里追加:
  it('degraded 时出现「对齐外框」,点它调 relocate', async () => {
    relocate.mockResolvedValue(undefined);
    status = { ...status, phase: 'degraded', last_valid: true };
    renderScreen();
    fireEvent.click(within(acts()).getByRole('button', { name: /对齐外框/ }));
    await waitFor(() => expect(relocate).toHaveBeenCalledTimes(1));
  });

  it('ready 时不出现「对齐外框」—— 没坏就不给修的键', () => {
    status = { ...status, phase: 'ready', session_calibrated: true, last_valid: true,
      capabilities: { ...status.capabilities, geometry_ready: true } };
    renderScreen();
    expect(screen.queryByRole('button', { name: /对齐外框/ })).toBeNull();
  });

  // degraded 与 failed 各一条:这两态的诊断卡原本就被占着,失败原因最容易被它盖掉
  it.each(['degraded', 'failed'] as const)('%s 下对齐外框失败,屏上给原因,不被原来那张诊断卡盖掉', async (phase) => {
    relocate.mockRejectedValue(new Error('geometry relocate failed 400: no_board_detected'));
    status = { ...status, phase, last_valid: true, error: phase === 'failed' ? 'anchor_not_found:3,15' : 'board_moved' };
    renderScreen();
    fireEvent.click(within(acts()).getByRole('button', { name: /对齐外框/ }));
    expect(await screen.findByText(/找不到棋盘外框/)).toBeInTheDocument();
  });
```

⚠️ 前端失败分支靠 `err.message` 里有没有 `no_board_detected` 来选文案,而 `geometryApi.ts:67` 的共享 `json()` 失败时只抛 `geometry request failed <status>`,**不带后端 `detail`**(2026-09-23 核过)。所以 `relocate` 自己读 `detail`(见 Step 4),**不改共享的 `json()`** —— 标定屏「沿用上次标定」失败时显示的就是它的 message,改了会连带改别处的报错文案。

- [ ] **Step 2: 跑,确认失败**

- [ ] **Step 3: 端点**

```python
@router.post("/relocate")
async def geometry_relocate(request: Request):
    """外框重定位(不亮灯,盘上有子也能跑)。漂移或取消之后的人工出口。"""
    calibration = getattr(request.app.state, "geometry_calibration", None)
    if calibration is None:
        raise HTTPException(status_code=404, detail="geometry calibration not enabled")
    from katrain.web.core.geometry_calibration_service import CalibrationBusy   # 与 /calibrate 同一种写法

    try:
        # 三帧取图 + 三次外框检测是 OpenCV 重活:放进线程,别卡住事件循环(同文件 /lock 也这么做,:276)。
        # RK3562 上同步跑会把状态轮询和别的 API 一起冻住。
        return await asyncio.to_thread(calibration.relocate, trigger="manual")
    except CalibrationBusy as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        # 找不到外框 / 朝向分不清 / 挪得太远 / 此刻不在可用的三态 —— 是这次请求做不到,不是服务坏了。
        raise HTTPException(status_code=400, detail=str(exc)) from exc
```

(`CalibrationBusy` 是 `RuntimeError` 子类,不会被 `except ValueError` 截走;两条的顺序无所谓,这里先写它只是为了读起来清楚。)

- [ ] **Step 4: 前端接线**

`src/api/geometryApi.ts`(共享领地,两套构建都要绿)。`GeometryStatus`(`:49`)加一个可选字段,与服务端 `status()` 新键同名:

```ts
  /** 最近一次外框重定位为什么没成(`no_board_detected` / `orientation_ambiguous` / `moved_too_far` / `delivery_failed` …);成了或没试过为 null。 */
  relocate_error?: string | null;
```

`GeometryAPI` 里加:

```ts
  // 自己读 detail:共享的 json() 失败时只给状态码,而屏上要靠 detail 分辨「找不到外框」与其它失败。
  relocate: async (): Promise<GeometryStatus> => {
    const res = await fetch(`${API_BASE}/relocate`, { method: 'POST' });
    if (!res.ok) {
      const detail = await res.json().then((b) => (typeof b?.detail === 'string' ? b.detail : null)).catch(() => null);
      throw new Error(`geometry relocate failed ${res.status}${detail ? `: ${detail}` : ''}`);
    }
    return res.json();
  },
```

对应 vitest(追加到 `src/api/geometryApi.test.ts`,照该文件 `vi.spyOn(globalThis, 'fetch')` 的写法):

```ts
  it('relocate 失败时把后端的 detail 带进错误信息(屏上靠它分辨「找不到外框」)', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify({ detail: 'no_board_detected' }), { status: 400 }),
    );
    await expect(GeometryAPI.relocate()).rejects.toThrow(/400: no_board_detected/);
  });

  it('relocate 成功时回状态', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify({ phase: 'ready' }), { status: 200 }),
    );
    await expect(GeometryAPI.relocate()).resolves.toMatchObject({ phase: 'ready' });
    expect(fetchMock).toHaveBeenCalledWith('/api/v1/geometry/relocate', { method: 'POST' });
  });
```

`GeometryContext.tsx` 加一个动作(与 `cancelCalibration` 同形;接口 `:25` 附近加 `relocate: () => Promise<void>;`,`:77` 的 Provider value 里加 `relocate`。**注意** `useOptionalGeometry` 等别处的消费者与各测试里的 mock 若按字段列举了 value,也要补上):

```tsx
  const relocate = useCallback(async () => {
    setStatus(await GeometryAPI.relocate());
  }, []);
```

`GeometryCalibrationScreen.tsx` 动作区(`:505-527` 那个 `else` 分支)在「沿用上次标定」之前加(同一个文件顶部的 `RAW_STREAM_SCALE` / `WARPED_STREAM_SCALE` 与 `onImageLoad` 乘回是 develop `de40f28c` 的,**别动**):

```tsx
                {/* 盘被碰动之后的出口。**不亮灯、不要求空盘** —— 13 点流程要清盘,
                    而这颗键存在的理由正是盘上有子(对局进行到一半)。
                    只在真的需要时出现:ready 态不给「修」的键。 */}
                {(phase === 'degraded' || phase === 'cancelled' || failed) && status.last_valid && (
                  <button
                    type="button"
                    className="kiosk-btn kiosk-btn--secondary"
                    data-testid="calib-relocate"
                    disabled={!cameraReady || relocating}
                    onClick={() => void handleRelocate()}
                  >
                    {relocating
                      ? t('vision:relocating', '正在对齐…')
                      : t('vision:relocate', '对齐外框')}
                  </button>
                )}
```

以及(`:133` 的解构加上 `relocate`;`:138-140` 旁边加 `const [relocating, setRelocating] = useState(false);` 和 `const [relocateError, setRelocateError] = useState<string | null>(null);`;`failed` 就是 `:240` 那个 `phase === 'failed'`)。
**对齐失败的原因不能放进 `actionError`**:`:352` 的诊断卡按 `failed` → `degraded` → `actionError` 的顺序取,而这颗键恰恰只在 `failed` / `degraded` / `cancelled` 下出现 ⇒ 放进 `actionError` 就永远上不了屏(Codex 第 1 轮核出)。所以单独一个 `relocateError`,并在诊断卡里**排第一**(它是用户刚按下去那一下的结果,比漂移那张卡新):

```tsx
  const handleRelocate = async () => {
    setRelocating(true);
    setRelocateError(null);
    try {
      await relocate();
    } catch (err) {
      // 失败要说话。最常见的一种是外框被人挡住 / 画面太暗,说得出来用户才知道怎么办。
      setRelocateError(
        err instanceof Error && /no_board_detected/.test(err.message)
          ? t('vision:relocate_no_board', '画面里找不到棋盘外框，挪开挡住边框的东西再试一次。')
          : t('vision:relocate_failed', '再试一次；一直不行就清空棋盘重新标定。'),
      );
    } finally {
      setRelocating(false);
    }
  };

  // 诊断卡:**把 `:352-355` 那个 `const diagnostic` 整个换成这一段** —— 刚按的「对齐外框」没成,排在最前;
  // 原来那条链接在它后面,一字不改。
  const diagnostic: Diagnostic | null = relocateError
    ? { kind: 'relocate', title: t('vision:relocate_failed_title', '没对上'), body: relocateError, action: '' }
    : failed ? buildDiagnostic(status.error)
      : phase === 'degraded' ? buildDiagnostic('board_moved')
        : actionError ? { title: '操作没有生效', body: actionError, action: '再试一次；一直不行就检查摄像头和灯带的接线。' }
          : null;
```

同时改 `Diagnostic`(`:70`)与诊断卡渲染(`:434-437`):类型加 `kind?: 'relocate'`;卡片 div 加 `data-kind={diagnostic.kind ?? 'status'}`(承重测试靠它分辨「这张卡是对齐失败那张」—— `degraded` 态本来就有一张诊断卡,只等 testid 什么也证明不了);`<p><b>{diagnostic.action}</b></p>` 改成 `{diagnostic.action && <p><b>{diagnostic.action}</b></p>}`(对齐失败那张没有 action)。
phase 一变(比如对齐成功回到 ready、或用户转去重新标定),`relocateError` 要清掉 —— 加一个 `useEffect(() => { setRelocateError(null); }, [phase]);`。

(新文案的 11 语种译文**不在这里做**,统一在 Task 7b 收口 —— Task 2 / 5 / 7 都会加 key,分三次补会三次冲 `.po`。)

- [ ] **Step 5: 跑、类型、两套构建**(i18n 闸此时会红 —— 新 key 还没译,Task 7b 收口)

```bash
CI=true uv run pytest tests/test_geometry_api.py -q
cd katrain/web/ui && npx vitest run src/kiosk/__tests__/GeometryCalibrationScreen.test.tsx src/api/geometryApi.test.ts && npx tsc -b
npm run build && npm run build:kiosk-2d
```

- [ ] **Step 6: 提交**

```bash
git add katrain/web/api/v1/endpoints/geometry.py tests/test_geometry_api.py \
  katrain/web/ui/src/api/geometryApi.ts katrain/web/ui/src/api/geometryApi.test.ts katrain/web/ui/src/kiosk/context/GeometryContext.tsx \
  katrain/web/ui/src/kiosk/components/vision/GeometryCalibrationScreen.tsx \
  katrain/web/ui/src/kiosk/__tests__/GeometryCalibrationScreen.test.tsx
git commit -m "$(cat <<'EOF'
feat(vision): 标定屏给一颗「对齐外框」,POST /geometry/relocate

盘被碰动之后终于有一条不用清盘的出口。失败给原因,不静默。

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 6: V3 · 没有 LED 的盒子也能完成第一次标定 —— ⛔ **本轮不做(Fan 2026-09-23 裁定),整节跳过**

> **执行者注意:本节不执行。** 原文保留给以后立项用。以后要做时,**先加 Step 0**,再照下面各步做:
>
> **Step 0 · 朝向**(PRD §3 V3「朝向前置」)。`empty_board_autocal` 出的是画面顺序的**整把锁**。磁盘上有旧锁时,把 `corners` 按 Task 3 的 `_align_to_lock` 重排,`points` / `baseline` 用同一个排列做 `np.rot90` / 转置;没有旧锁时用哪条装机约定,**先由 Fan 定**。验收加一条 pytest:有旧锁时新锁的 `mount_parallax_for_lock(...).nadir` 与旧锁同一条边。
>
> 另:下面 Step 3 里 `_calibrate_no_led` 取帧的 `grab(settle_ms=0.0)` 在 develop `275625ec` 之后仍然成立 —— `grab_fresh` 本身会把空闲的相机叫醒。

**Files:**
- Modify: `katrain/web/core/geometry_calibration_service.py`(`start` 的 LED 检查、`_run` 的分支、新增 `_calibrate_no_led`)
- Modify: `GeometryCalibrationScreen.tsx`(`canStart` 与说明)
- Test: `tests/test_geometry_calibration_service.py`、`GeometryCalibrationScreen.test.tsx`

**Interfaces:**
- Produces:`_calibrate_no_led() -> _NoLedResult`(字段与 `LedGeometryCalibrator.calibrate()` 的结果同形:`ok` / `lock` / `reason` / `attempts` / `fit` / `exposure_stats`),使 `_run` 后半段一行不改。

- [ ] **Step 1: 写失败的测试**

```python
def test_first_calibration_without_led_uses_the_no_led_path(service_without_led):
    svc = service_without_led                      # led=None
    svc.start(trigger="manual", empty_confirmed=True)
    assert svc.wait(timeout=30)
    assert svc.status()["phase"] == "ready"
    assert svc.status()["trigger"] == "manual"
    assert svc.used_strategy == "empty_board_autocal"


def test_no_led_path_still_requires_an_empty_board(service_without_led):
    """空盘要求**不放开**:无灯自动标定要认整张网格,盘上有子它认不出来。"""
    with pytest.raises(ValueError):
        service_without_led.start(trigger="manual", empty_confirmed=False)


def test_led_path_is_unchanged_when_led_is_available(service_with_led):
    """**回归闸**:13 点流程仍是首选,没有被顺手换掉。"""
    svc = service_with_led
    svc.start(trigger="manual", empty_confirmed=True)
    assert svc.wait(timeout=30)
    assert svc.calibrator_factory_calls == 1        # LedGeometryCalibrator 被用了
```

```tsx
  it('没有 LED 时「重新开始标定」仍然可以按,并说明是无灯方式', () => {
    renderScreen({ phase: 'required', capabilities: { camera_ready: true, led_ready: false } });
    expect(screen.getByRole('button', { name: /开始标定|重新开始标定/ })).toBeEnabled();
    expect(screen.getByText(/没有灯带/)).toBeInTheDocument();
  });

  it('有 LED 时不出现无灯说明', () => {
    renderScreen({ phase: 'required', capabilities: { camera_ready: true, led_ready: true } });
    expect(screen.queryByText(/没有灯带/)).toBeNull();
  });
```

- [ ] **Step 2: 跑,确认失败**

- [ ] **Step 3: 服务端**

`start()`:把那句无条件抛错换成

```python
        # 没有 LED 不再是「不能标定」:INITIAL_SETUP 的第二条路是无灯空盘自动标定
        # (`calibration_registry.py`)。**空盘仍然是硬要求** —— 那条路要认整张网格。
        if not empty_confirmed:
            raise ValueError("empty board confirmation is required")
```

`_run` 里选路:

```python
            if self._led_available():
                calibrator = self.calibrator_factory(
                    led=self.led, capture=self.capture, cancel_event=self._cancel_event,
                    progress=self._progress, anchor_observer=self._anchor_observed,
                )
                result = calibrator.calibrate()
            else:
                # 无灯:走选择器的 INITIAL_SETUP —— led_anchor 因为没有 led 自行让位,
                # 落到 empty_board_autocal(产出完整 lock,含 baseline)。
                result = self._calibrate_no_led()
```

模块级(与 `AUTO_RELOCATE_ON_DRIFT` 放在一起,文件顶部 `from dataclasses import dataclass, field`):

```python
@dataclass
class _NoLedResult:
    """与 `LedGeometryCalibrator.calibrate()` 的返回**同形** —— `_run` 后半段
    (取消检查、持久化、状态、on_success)因此一行都不用改。"""

    ok: bool
    lock: object = None
    reason: str = ""
    attempts: tuple = ()
    fit: object = None
    exposure_stats: object = None
```

服务类里:

```python
    def _led_available(self) -> bool:
        return self.led is not None and self._is_ready(self.led)

    def _calibrate_no_led(self):
        """无灯首次标定。返回与 `LedGeometryCalibrator.calibrate()` **同形**的结果,
        这样 `_run` 后半段(取消检查、持久化、状态、on_success)一行都不用改。"""
        from katrain.vision.calibration_strategy import CalibrationContext, Scenario
        from katrain.vision.geometry_lock import GeometryLock

        grab = getattr(self.capture, "grab_fresh", None)
        if grab is None:
            return _NoLedResult(ok=False, reason="no_capture")
        frames = []
        for index in range(8):
            if self._cancel_event.is_set():
                return _NoLedResult(ok=False, reason="cancelled")
            frame, _seq, _ts = grab(settle_ms=0.0)
            if frame is not None:
                frames.append(frame)
            self._progress("flashing_corners", index + 1, 8)
        if not frames:
            return _NoLedResult(ok=False, reason="no_frame")
        ctx = CalibrationContext(
            frames=frames, board=None, geometry=None, led=None, capture=self.capture, out_size=950,
        )
        out = self._get_selector().calibrate(Scenario.INITIAL_SETUP, ctx)
        if not out.ok or out.points is None:
            # 策略回了个只有单应的结果(外框法)时也算失败:首次标定必须拿到整张网格与基线,
            # 否则识别没有 baseline 可用 —— 半个 lock 比没有更坏。
            return _NoLedResult(ok=False, reason=out.reason or "no_led_calibration_failed")
        lock = GeometryLock(
            corners=out.corners, points=out.points, xs=out.xs, ys=out.ys,
            M=out.M, Minv=out.Minv, out_size=int(ctx.out_size), baseline=out.baseline,
            confidence=float(out.confidence), diag={"strategy": out.strategy},
        )
        return _NoLedResult(ok=True, lock=lock)
```

⚠️ 写之前 `grep -n "class GeometryLock" -A 20 katrain/vision/geometry_lock.py` 回读一次字段名与是否有必填项(`source_width` / `source_height` 可选,但**能填就填** —— `warp.adjust_M_for_resolution` 靠它对齐分辨率)。

- [ ] **Step 4: 前端**

```tsx
  const canStart = cameraReady && !starting && !active;   // 去掉 ledReady
```

说明区(`.calib-note` 里,那条「LED 只在你按下之后才亮」之后)加:

```tsx
              {!ledReady && (
                <><br />这台盒子<b>没有灯带</b>或灯带没接上，将用<b>无灯方式</b>标定：靠棋盘外框和网格自己找位置，
                精度略低，而且<b>盘上不能有子</b>。</>
              )}
```

三格里 LED 那一格的措辞按 Task 7 一起改。

- [ ] **Step 5: 跑,确认通过 + 提交**

```bash
CI=true uv run pytest tests/test_geometry_calibration_service.py -q
cd katrain/web/ui && npx vitest run src/kiosk/__tests__/GeometryCalibrationScreen.test.tsx && npx tsc -b
cd /Users/fan/Repositories/katrain-kiosk-go-vision && uv run black -l 120 katrain/web/core/geometry_calibration_service.py
git add katrain/web/core/geometry_calibration_service.py tests/test_geometry_calibration_service.py \
  katrain/web/ui/src/kiosk/components/vision/GeometryCalibrationScreen.tsx katrain/web/ui/src/kiosk/__tests__/GeometryCalibrationScreen.test.tsx
git commit -m "$(cat <<'EOF'
feat(vision): 没有 LED 的盒子也能完成第一次标定

INITIAL_SETUP 的第二条路(empty_board_autocal)一直写着没接,生产零调用。
现在接上:没灯就走无灯,空盘要求不放开,有灯时 13 点流程一个字不变(有回归闸钉住)。

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 7: V4 措辞(标定屏 + 左栏 + 设计稿源头) + Z3 删死组件

**Files:**
- Modify: `GeometryCalibrationScreen.tsx`(三格 LED 那一格 + 说明一句)
- ~~Modify: `SettingsPage.tsx`~~ —— **2026-09-23 取消**:设置赛道已照 V4 改完(`SettingsPage.tsx:280-287`,`3b8af0a2`,key `settings:led_serial_connected` 11 语种已入库 `d3b446a8`)。
- Modify: `katrain/web/ui/src/kiosk/components/layout/GoConsoleRail.tsx:70`(「就绪」→「已连接」,**Fan 2026-09-23 裁定**)+ `GoConsoleRail.test.tsx:36`
- Modify(**另一个仓**):smartbox `superpowers/shared/kiosk-shell/sample-go/go-kiosk.tmpl.html:2484` + 重建的 `go-kiosk.html` / `go-kiosk-proto.html`(设计稿源头同步,**参考图不重拍**,PRD §3 V4)
- Delete: `src/kiosk/components/physical/PoseLostBanner.tsx`、`src/kiosk/__tests__/PoseLostBanner.test.tsx`

- [ ] **Step 1: 改词**

```tsx
    // 复用设置屏那个 key:同一件事只有一种说法,也不用新增译文。「未连接」照这一行原来的写法。
    { label: 'LED', value: ledReady ? t('settings:led_serial_connected', '串口已连接') : '未连接',
      tone: ledReady ? 'good' : 'bad' },
```

对应 vitest(追加到 `GeometryCalibrationScreen.test.tsx`;jsdom 里 `t()` 返回默认值,所以断言中文):

```tsx
  it('LED 那一格只说串口通了,不说「就绪」', () => {
    // 照该文件写法:改模块级 status(beforeEach 里 led_ready 已是 true),再无参 renderScreen();`cells()` 取三格文字
    renderScreen();
    expect(cells().some((c) => c.includes('串口已连接'))).toBe(true);
    expect(cells().some((c) => c.includes('就绪'))).toBe(false);
  });
```

说明区加一句(新文案走 `t()`,译文在 Task 7b 收口;不带 `<b>` 强调 —— `t()` 的默认值是纯文本):

```tsx
              <br />{t('vision:led_serial_note', 'LED 那一格只说串口通了，不代表每颗灯都亮；引导时发现某处不亮，多半是灯带那一段坏了。')}
```

> 为什么只改词不做自检:`led_service.py:199-200` 的 `is_connected()` 返回的就是串口状态。
> 真自检要相机逐颗扫描 361 点(`sbc-baipu-led-guide/prd.md:174`),要人在场、要空盘、一两分钟,
> 而 UR 段的硬件修复状态两个仓里都看不出来 —— **先把话说准,再谈自检**(PRD §4)。

- [ ] **Step 1b: 左栏那一格**(Fan 2026-09-23 裁定;左栏太窄放不下「串口已连接」,用和摄像头那格同样的三个字)

`GoConsoleRail.tsx:70`:

```tsx
    // 「已连接」而不是「就绪」:这一格读的是串口开没开(`led_service.is_connected()`),灯带某段坏了它照样是真 ——
    // 「就绪」声称的比它知道的多。宽度与摄像头那格同为三个字(Fan 2026-09-23,视觉赛道 V4)。
    : { label: 'LED', value: connected ? '已连接' : '未连接', tone: connected ? 'good' : 'warn' };
```

`GoConsoleRail.test.tsx:36` 那行 `expect(screen.getByText('就绪')).toBeInTheDocument();` 换成(按格取值 —— 摄像头那格在别的用例里也可能是「已连接」,别用全屏 `getByText`):

```tsx
    expect(screen.getByText('LED').parentElement?.querySelector('.kiosk-status__v')?.textContent).toBe('已连接');
    expect(screen.queryByText('就绪')).toBeNull();
```

验收(PRD §3 V4):

```bash
cd /Users/fan/Repositories/katrain-kiosk-go-vision
rg -n "LED.*就绪" katrain/web/ui/src --glob '!*.test.*'; echo "exit=$?"   # 预期:零命中,exit=1
```

- [ ] **Step 2: 删死组件**

```bash
cd /Users/fan/Repositories/katrain-kiosk-go-vision
git rm katrain/web/ui/src/kiosk/components/physical/PoseLostBanner.tsx \
       katrain/web/ui/src/kiosk/__tests__/PoseLostBanner.test.tsx
rg "PoseLostBanner" katrain/web/ui/src --glob '!*.md'; echo "exit=$?"
```

预期:只剩 `RecalibrationModal.tsx` 注释里那两处历史说明(它们解释的是「从哪来的」,留着)。

- [ ] **Step 3: 跑 + 提交**

```bash
cd katrain/web/ui && npx vitest run src/kiosk && npx tsc -b
cd /Users/fan/Repositories/katrain-kiosk-go-vision
# 精确列文件,**不许 `git add -A`**:并行 / 串行交接时工作树里可能有别的任务没收尾的改动
git add katrain/web/ui/src/kiosk/components/vision/GeometryCalibrationScreen.tsx \
        katrain/web/ui/src/kiosk/__tests__/GeometryCalibrationScreen.test.tsx \
        katrain/web/ui/src/kiosk/components/layout/GoConsoleRail.tsx \
        katrain/web/ui/src/kiosk/components/layout/GoConsoleRail.test.tsx
# PoseLostBanner 两个文件已由 Step 2 的 `git rm` 暂存为删除;再 `git add` 它们会报 pathspec did not match
git diff --cached --name-only      # 核对:恰好上面四个文件 + 两个删除
git commit -m "$(cat <<'EOF'
fix(vision): 「LED 就绪」改成「串口已连接」/「已连接」;删掉零消费者的 PoseLostBanner

is_connected() 说的就是串口开没开 —— 灯带坏一段时屏上照样绿,那句话是假的。
标定屏复用设置屏的 settings:led_serial_connected;左栏太窄,用和摄像头那格一样的「已连接」
(Fan 2026-09-23 裁定)。真自检(361 点扫描)等硬件 v4,见 PRD §4。

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>
EOF
)"
```

- [ ] **Step 4: 设计稿源头同步(smartbox 仓,只改一个常量,参考图不重拍)**

为什么只改源头(PRD §3 V4):`STATUS` 是五个屏共用的一个常量,而那几张参考图分别钉在 smartbox 的四条分支上,
几条分支上还有别的会话在干活。本步只让**稿子的源头**说对话;参考图等各分支下次合 main 重拍时自然带上,
在那之前四图里这一个词是已知差异。

```bash
cd /Users/fan/Repositories/smartbox-software
git branch --show-current                       # 预期 main;不是就停下来报告,别切分支(那是别人的工作树)
git status --short -- superpowers/shared/kiosk-shell/sample-go/   # 预期空;不空说明有人在改稿子,停下来报告
cd superpowers/shared/kiosk-shell/sample-go
# **不跑 build.py**:它不是字节可复现的 —— 2026-09-23 在副本里实测,模板一个字不改、直接重建,
# 内嵌字体子集那 134 行就和提交的版本不同。三份文件里是同一行 JS,直接逐字替换;
# 「已连接」三个字摄像头那格已经在用,字形本来就在子集里,渲染不受影响。
python3 - <<'EOF'
from pathlib import Path
old, new = '["LED", "就绪", "good"]', '["LED", "已连接", "good"]'
for name in ("go-kiosk.tmpl.html", "go-kiosk.html", "go-kiosk-proto.html"):
    p = Path(name); s = p.read_text()
    assert s.count(old) == 1, (name, s.count(old))
    p.write_text(s.replace(old, new))
EOF
cd /Users/fan/Repositories/smartbox-software
git diff --stat -- superpowers/shared/kiosk-shell/sample-go/
git diff -U0 -- superpowers/shared/kiosk-shell/sample-go/ | grep '^[+-][^+-]'
```

预期:只有 `go-kiosk.tmpl.html` / `go-kiosk.html` / `go-kiosk-proto.html` 三个文件,每个文件 `1 insertion(+), 1 deletion(-)`,就是 `就绪`→`已连接` 那一行。
不符就 `git checkout -- ` 这三个文件复原并报告,不要提交。

**不要跑 `node gate.mjs`**:它会重拍 `shots/` 下所有参考图(`screen-gate.mjs:814`),正是本步刻意不做的事。

```bash
cd /Users/fan/Repositories/smartbox-software
# main 工作树里有别人未提交的 vendor/*:只 add 这三个文件,绝不 -A
git add superpowers/shared/kiosk-shell/sample-go/go-kiosk.tmpl.html \
        superpowers/shared/kiosk-shell/sample-go/go-kiosk.html \
        superpowers/shared/kiosk-shell/sample-go/go-kiosk-proto.html
git commit -m "$(cat <<'EOF'
design(go): 状态格 LED 那一格「就绪」改「已连接」

那一格读的是串口开没开,灯带坏一段它照样为真 ——「就绪」声称的比它知道的多。
与同一栏摄像头那格同为三个字,实现侧 katrain feature/kiosk-go-vision 同步改(Fan 2026-09-23)。
只改源头与两份成品,参考图 shots/ 不重拍:它们钉在四条分支上,等各分支合 main 重拍时带上。

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>
EOF
)"
```

**不 push smartbox**(本轮只授权推 katrain 的 `feature/kiosk-go-vision`);交付说明里点名这一个本地提交,推不推由 Fan 定。

> Codex 第 1 轮对这一步的异议与处理:① 「绕过 build.py」—— 重建不是字节可复现的(见上),三份文件逐字换同一行与重建出的差别只在内嵌字体子集,不采纳;② 「四图不读本地 main」—— 对,四图按 `reference-shots.json` 的 `shotFrom + sha256` 取钉住的图,所以这次四图里仍是旧词,已记为已知差异(Task 8 Step 2/3);③ 「不 push 别的分支拿不到」—— smartbox 的各 worktree 共用同一个仓的 refs,本机其它分支合本地 `main` 就能拿到;推不推只影响别的机器,交 Fan 定。参考图真正重拍时,由那次重拍在同一次提交里更新 pin 与 sha(那是既有流程,不归本赛道)。

---

### Task 7b: 新文案 11 语种收口(i18n)

**为什么单列**:Task 2 / 5 / 7 都往 `src/kiosk` 加 `t('vision:…')`,分三次补译会三次改同一批 `.po`。
develop 的 `tests/web_ui/test_kiosk_i18n.py` 要求 `src/kiosk` 下每个 `t()` key 在 11 个语种里都有**真译文**(非空、非 TODO)。

**Files:** `katrain/i18n/locales/*/LC_MESSAGES/katrain.po`(11 份);`scripts/batch_translate_galaxy.py`(闸给的补法在这里登记译文)。
`.mo` 被 `.gitignore:43` 忽略 —— 本地 `uv run python i18n.py` 生成,**不提交**。

- [ ] **Step 1: 数出本赛道新增的 key**(不要凭记忆列)

```bash
cd /Users/fan/Repositories/katrain-kiosk-go-vision
git diff "$(git merge-base HEAD origin/develop)" -- katrain/web/ui/src/kiosk ':!*.test.*' ':!**/__tests__/**' \
  | grep '^+' | grep -o "t('vision:[a-z_]*'" | sort -u
CI=true uv run pytest -q tests/web_ui/test_kiosk_i18n.py 2>&1 | grep -o "'vision:[a-z_]*'" | sort -u   # 缺译的那几个
```

预期(按本计划):`vision:reuse_blocked_moved`、`vision:relocate`、`vision:relocating`、`vision:relocate_no_board`、`vision:relocate_failed`、
`vision:relocate_failed_title`、`vision:led_serial_note`。`settings:led_serial_connected` 是复用的,已有 11 语种,不用补。

- [ ] **Step 2: 用 `katrain-i18n-expert` skill 补 11 语种**(cn ≠ tw、jp ≠ ko;不许留 TODO、不许英文顶替)

照闸的提示:加进 `scripts/batch_translate_galaxy.py` 的 `GALAXY_TRANSLATIONS`,跑那个脚本,再 `uv run python i18n.py`。

- [ ] **Step 3: 验**

```bash
CI=true uv run pytest -q tests/web_ui/test_kiosk_i18n.py 2>&1 | tail -1                 # 预期全绿
CI=true uv run pytest -q tests/web_ui/test_kiosk_i18n.py 2>&1 | grep -c "'vision:"      # 预期 0
git status --short -- katrain/i18n | grep -v '\.po$'                                   # 预期空(没有误加 .mo)
```

- [ ] **Step 4: 提交**

```bash
git add katrain/i18n/locales/*/LC_MESSAGES/katrain.po scripts/batch_translate_galaxy.py
git commit -m "$(cat <<'EOF'
i18n(vision): 对齐外框 / 串口已连接 等 7 个新 key 补齐 11 语种

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 8: 屏 26 四图与承重实测

**Files:**
- Modify: `katrain/web/ui/tests/kiosk-shell-geometry.spec.ts`(在既有 `§11 标定屏` 那组里**加一态**,复用 `bootCalib` / `calibBoxes`;**不新建 spec** ——
  既有那组用的是对的滚动节点 `.calib-scroll .kiosk-side__scroll` 和真滚轮,另起一份只会把选择器写错一次)
- Modify: `katrain/web/ui/tests/kiosk-screen-26-calib.fourup.spec.ts`(只改图注)
- 四图产物:`superpowers/tracks/kiosk-go-shell-align/visual/<屏>/`(只留真变了的)

- [ ] **Step 1: 承重 —— 最满那一态,中文、德文各量一次**

最满 = `degraded` + 诊断卡 + 对齐失败那句 + **三颗键**(重新开始标定 / 沿用上次标定 / 对齐外框)。
「最空不塌」既有的 `§11 标定屏:头尾钉死…总高正好 460` 已经在量(`required` 常态),不重复写。

先给既有的两个辅助函数加一个语言参数(默认 `'cn'`,既有调用一个字不用改)。**不要靠再注册一个 init script 去覆盖语言** ——Playwright 不保证多个 init script 的执行顺序(Codex 第 2 轮):

```ts
// tests/kiosk-shell-geometry.spec.ts:21
const boot = async (page: Page, path: string, lang = 'cn') => {
  await page.addInitScript((l) => {
    localStorage.setItem('token', 'kiosk-shell-geometry');
    localStorage.setItem('katrain_language', l);
  }, lang);
  ...                                     // 其余一字不动

// :1705
const bootCalib = async (page: Page, over: Record<string, unknown>, lang = 'cn') => {
  ...
  await boot(page, '/kiosk/vision/setup', lang);
  ...                                     // 其余一字不动
```

```ts
// 追加到 tests/kiosk-shell-geometry.spec.ts,紧跟既有「§11 标定屏:失败时多一张诊断卡…」那条之后
for (const lang of ['cn', 'de'] as const) {
  test(`§11 标定屏(${lang}):degraded + 对齐外框失败 + 三颗键,键不溢出、不被顶出去,中段自己滚`, async ({ page }) => {
    await bootCalib(page, { phase: 'degraded', error: 'board_moved', last_valid: true }, lang);
    // **在 bootCalib 之后注册**:Playwright 后注册的先匹配,早注册会被 boot 的兜底路由盖掉(见 bootCalib 的注释)
    let relocateCalls = 0;
    await page.route('**/api/v1/geometry/relocate', (r) => {
      relocateCalls += 1;
      return r.fulfill({ status: 400, json: { detail: 'no_board_detected' } });
    });
    const acts = page.locator('.calib-acts');
    await expect(acts.locator('.kiosk-btn')).toHaveCount(3);
    await page.getByTestId('calib-relocate').click();             // 按 testid 找:顺序与德文文字都不可靠
    // degraded 态本来就有一张诊断卡 ⇒ 只等 testid 什么也证明不了;等的是「对齐失败」那一张
    await page.waitForSelector('[data-testid="geometry-diagnostic-card"][data-kind="relocate"]');
    expect(relocateCalls, '对齐外框没有真的打到 /geometry/relocate').toBe(1);

    const m = await calibBoxes(page);
    expect(m.rail.h, '右栏高度被诊断卡顶变了').toBe(460);
    expect(m.acts.bottom, '按钮被顶出右栏了').toBe(m.rail.bottom);
    expect(m.acts.h, '三颗键折成两行了 —— 按钮区不再是固定尾').toBe(44);
    expect(m.rows, '步骤行被压扁了').toEqual([52, 52, 52, 52]);
    expect(m.overflow, '没造到会溢出 —— 下面的滚动断言是空的').toBeGreaterThan(0);
    // 每颗键的字都装得下(`.calib-acts` 是等宽三列,约 146px;德文最容易撑破)
    const clipped = await acts.locator('.kiosk-btn').evaluateAll((els) =>
      els.filter((e) => e.scrollWidth > e.clientWidth + 1 || e.scrollHeight > e.clientHeight + 1).map((e) => e.textContent));
    expect(clipped, '有键的字被裁了').toEqual([]);

    const zone = page.locator('.calib-scroll .kiosk-side__scroll');
    const bb = (await zone.boundingBox())!;
    await page.mouse.move(bb.x + bb.width / 2, bb.y + bb.height / 2);
    await page.mouse.wheel(0, 200);
    await expect.poll(() => zone.evaluate((el) => el.scrollTop), { message: '中段滚不动' }).toBeGreaterThan(0);
  });
}
```

⚠️ **按钮文案收短**:三等分每列约 146px,中文「对齐外框（不亮灯）」九个字已经贴边,德文必然放不下。
所以 Task 5 那颗键的默认文案用 **`t('vision:relocate', '对齐外框')`**,「不亮灯、盘上有子也行」这层意思放进说明区那句
(`vision:reuse_blocked_moved` 的文案里已经说了「用『对齐外框』」,在它后面补「——不亮灯，盘上有子也能对」)。
德文若仍撑破,**回 Task 7b 选更短的译法**,不去改 `.calib-acts` 的等宽三列(那是屏 26 的承重结构,改了要重新过四图)。
⚠️ `m.overflow > 0` 若在最满态下仍不成立,说明诊断卡 + 三步 + 说明在 460 里装得下 —— 那就去掉这条与滚轮那条,
**并在测试里写明「此态不溢出,滚动由既有失败态那条守」**;不许把断言改弱成 `>= 0` 留着。

- [ ] **Step 1b: 屏 26 四图 spec 的实现侧图注跟上**

`tests/kiosk-screen-26-calib.fourup.spec.ts` 的 `implementationCaption` 里「沿用要 phase∈{required,failed} 否则服务端 ValueError」
在 V2 之后过期 —— 改成 `phase∈{required,failed,cancelled}`;并在图注末尾补一句「LED 那格写『串口已连接』(只说串口通了,视觉赛道 V4),
稿子那格还是『就绪』:稿子源头已改、参考图未重拍,这一个词是已知差异」。文件头那段 ④ 的同一句也改掉。只改文字,不改取图逻辑。

- [ ] **Step 2: 跑两次 fourup,排抖动,只提交真变了的**

预期**真变**的屏(其余全应是抖动,照 CLAUDE.md `git checkout HEAD -- <屏目录>` 还原):
- **26-calib**:LED 那格「就绪」→「串口已连接」+ 图注;
- **左栏 LED 那格在 fixture 里是「连上」的屏**:「就绪」→「已连接」。哪些屏是这样,先 `rg -n "led_connected: true" tests/*.fourup.spec.ts` 数出来
  (2026-09-24 核过有四个 spec:`01-play`、`11-training`、`07-09-platform`、`09-setup`),**再看那几屏是否真渲染 `GoConsoleRail`**,两条都成立的才算。

```bash
cd /Users/fan/Repositories/katrain-kiosk-go-vision/katrain/web/ui
npx playwright test --config=playwright.visual.config.ts tests/kiosk-shell-geometry.spec.ts -g '§11 标定屏'
VIS=../../../superpowers/tracks/kiosk-go-shell-align/visual
RUN1="$(mktemp -d)"
npm run fourup && cp -R "$VIS" "$RUN1/"
npm run fourup
# 每屏把两次的实现图互相 diff 得到本屏抖动底(canvas 屏 ~4500、DOM 屏 ~200,见 CLAUDE.md),
# 再与 HEAD 比:只有「与 HEAD 的差异远超本屏抖动底、且 bbox 聚在 LED 那格」的屏才留下。
git -C /Users/fan/Repositories/katrain-kiosk-go-vision status --short -- superpowers/tracks/kiosk-go-shell-align/visual
```

- [ ] **Step 3: 人眼四图 + 交 Fan 确认**(硬性关卡,未确认不得报完成)

每屏**四张一起看**(参考 / 实现 / 并排 / 叠加);LED 那一个词是已知差异,其余任何差异都要说得出来源。
同时把 Step 1 两条承重测试的原样输出贴给 Fan。

- [ ] **Step 4: 提交**(只提交真变了的屏目录 + 两个 spec 文件)

```bash
cd /Users/fan/Repositories/katrain-kiosk-go-vision
git add katrain/web/ui/tests/kiosk-shell-geometry.spec.ts katrain/web/ui/tests/kiosk-screen-26-calib.fourup.spec.ts \
        superpowers/tracks/kiosk-go-shell-align/visual/26-calib   # + Step 2 判定为真变的其它屏目录,逐个点名
git commit -m "$(cat <<'EOF'
test(vision): 屏 26 最满态承重(cn + de)+ 四图重取

degraded + 诊断 + 对齐失败原因 + 三颗键:键不溢出、不被顶出右栏,中段真滚轮能滚;
中德两种语言各量一次。四图只留真变了的屏(LED 那格措辞),其余抖动已还原。

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 8b: 精度工具加真帧模式(上板闸的量具)

**为什么有这个 Task**:`AUTO_RELOCATE_ON_DRIFT` 翻成 `True` 的前置是「满盘下外框法误差 < 0.12 格」。
但 `outer_corner_accuracy.py` 今天**只渲染合成棋盘**(`render_board`)、从不读相机 —— 在 RK3562 上跑和在 Mac 上跑,
输出一模一样。文件头自己也写了「Synthetic numbers are a LOWER BOUND … the real-hardware run is the blocking gate」,
而那个真机量法一直没写出来。本 Task 补上:**真值 = 空盘时 LED 13 点标定的角点,量的是外框法在真帧上找到的角点离它多远**。
两个输入都从正在跑的服务取,不用停服务、不用找 lock 文件在哪(盒上 lock 走 `hardware_vision_store`,不是 `~/.katrain/geometry_lock.npz`):

- 真值:`GET /api/v1/geometry/layout` 的 `corners`(就是 `lock.corners`,相机像素,左上/右上/右下/左下)与 `frame` 尺寸;
- 帧:`GET /api/v1/geometry/stream`(原始相机帧的 MJPEG,格式见 `endpoints/geometry.py` 的 `_mjpeg_part`)。

⚠️ **前置:LED 标定与这次量测在同一个分辨率下。** `/geometry/layout` 报的 `frame` 是**当前帧**尺寸,`corners` 却是锁**标定时**的像素坐标
(`geometry.py:179/194`,不做分辨率换算 —— 这是既有行为,记在 PRD §5,不在本赛道修)。所以真值必须是**这一次开机、同一个采集配置**下刚标出来的锁;
下面的 `--live` 会比 `frame` 与抓到的帧尺寸,但比不出「锁是别的分辨率下标的」—— 靠这条前置,不靠工具。
量测判据用 **19×19 网格最大误差**(`grid_error_cells`),不用四角中位数(Codex 第 1 轮:一个角坏、三个角好时中位数为 0)。

**Files:**
- Modify: `katrain/vision/tools/outer_corner_accuracy.py`
- Test: `tests/test_vision/test_outer_corner_accuracy.py`(追加)

- [ ] **Step 1: 写失败测试**

```python
# 追加到 tests/test_vision/test_outer_corner_accuracy.py
import io

from katrain.vision.tools.outer_corner_accuracy import corner_error_cells, grab_mjpeg_frames, grid_error_cells, live_gate, measure_real


def _blank_frames(n):
    return [np.zeros((720, 1280, 3), np.uint8) for _ in range(n)]


def test_measure_real_scores_every_frame_against_the_reference_quad():
    dets = iter([QUAD.copy(), QUAD + np.array([20, 0]), None])
    res = measure_real(_blank_frames(3), QUAD, detect_fn=lambda f: next(dets))
    assert res[0] < 1e-6
    assert res[1] > 0.12
    assert res[2] is None
    # 一帧超差整组就不过 —— 闸不许靠平均把坏帧抹掉
    assert gate(res, max_error_cells=0.12) is False


def test_measure_real_passes_when_every_detection_is_close():
    res = measure_real(_blank_frames(2), QUAD, detect_fn=lambda f: QUAD + np.array([1, 0]))
    assert gate(res, max_error_cells=0.12) is True


def test_live_gate_needs_most_frames_detected():
    """十帧里只认出一帧、那一帧还合格 —— 不许算过:`gate()` 会丢掉所有 None,样本太少的「过」不是证据。"""
    assert live_gate({0: 0.01, 1: None}) is False
    assert live_gate({i: 0.05 for i in range(8)} | {8: None, 9: None}) is True      # 8/10 且都合格
    assert live_gate({i: 0.05 for i in range(7)} | {i: None for i in range(7, 10)}) is False


def test_one_bad_corner_is_not_hidden_by_the_median():
    """**反向闸。** 一个角偏 20px、三个角全对:四角中位数是 0(2026-09-24 实测),
    网格最大误差是 0.55 格。真机闸量的必须是交叉点,不是四角的中位数。"""
    one_bad = QUAD.copy()
    one_bad[2] += np.array([20.0, 0.0])
    assert corner_error_cells(one_bad, QUAD) == 0.0            # 旧量法的盲区,钉住它存在
    assert grid_error_cells(one_bad, QUAD) > 0.12
    res = measure_real(_blank_frames(1), QUAD, detect_fn=lambda f: one_bad)
    assert gate(res, max_error_cells=0.12) is False


def test_grab_mjpeg_frames_reads_the_kiosk_stream_format(monkeypatch):
    # 用服务端真正写流的那个函数造字节 —— 流格式一改,这条就红
    from katrain.web.api.v1.endpoints.geometry import _mjpeg_part

    ok, jpg = cv2.imencode(".jpg", np.full((48, 64, 3), 128, np.uint8))
    assert ok
    body = b"".join(_mjpeg_part(jpg.tobytes()) for _ in range(3))

    class _Resp(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            self.close()

    monkeypatch.setattr("urllib.request.urlopen", lambda url, timeout=None: _Resp(body))
    frames = grab_mjpeg_frames("http://box/api/v1/geometry/stream", 2)
    assert len(frames) == 2
    assert frames[0].shape == (48, 64, 3)
```

同时在文件顶部的 import 里补 `import cv2`(现有测试没用到它)。

- [ ] **Step 2: 跑,确认因 ImportError 失败**

```bash
cd /Users/fan/Repositories/katrain-kiosk-go-vision
uv run pytest tests/test_vision/test_outer_corner_accuracy.py -q
```

预期:collection error,`cannot import name 'grab_mjpeg_frames'`。

- [ ] **Step 3: 实现**

在 `gate()` 之后、`if __name__ == "__main__":` 之前加:

```python
def grid_error_cells(detected_quad, true_quad) -> float:
    """Largest error over the 19x19 intersections (cells) between the grids the two quads imply.

    The corner median (``corner_error_cells``) reads 0 when three corners are right and one is
    20 px off, yet that homography moves a whole region of intersections by ~0.5 cell. Recognition
    works on intersections, so the real-board gate measures intersections."""
    from katrain.vision import geometry_calibrate

    a = geometry_calibrate.grid_points_from_corners(sort_corners(detected_quad), size=1000).reshape(-1, 2)
    b = geometry_calibrate.grid_points_from_corners(sort_corners(true_quad), size=1000).reshape(-1, 2)
    tq = sort_corners(true_quad).astype(np.float64)
    diag = 0.5 * (np.linalg.norm(tq[2] - tq[0]) + np.linalg.norm(tq[3] - tq[1]))
    cell_px = diag / (18.0 * np.sqrt(2.0))
    return float(np.max(np.linalg.norm(a.astype(np.float64) - b.astype(np.float64), axis=1)) / cell_px)


def live_gate(res, max_error_cells: float = 0.12, min_detect_ratio: float = 0.8) -> bool:
    """Real-board gate: at least ``min_detect_ratio`` of the frames must find the board AND every
    frame that did must be under ``max_error_cells``. ``gate()`` drops None, so one good frame out
    of ten would pass it -- too few samples to be evidence for turning the auto switch on."""
    found = [e for e in res.values() if e is not None]
    if not res or len(found) < min_detect_ratio * len(res):
        return False
    return all(e < max_error_cells for e in found)


def measure_real(frames, true_quad, detect_fn: Optional[Callable] = None):
    """Per-frame grid error (cells, max over 361 intersections) of the outer-quad detector
    against a REAL reference quad.

    ``true_quad`` is the LED 13-point lock's grid corners, calibrated on an EMPTY board just
    before the stones went down, with board and camera untouched since — the golden reference.
    Returns {frame_index: error_cells_or_None}; None = detector found no board in that frame.
    """
    detect = detect_fn or detect_board_raw
    out = {}
    for i, frame in enumerate(frames):
        det = detect(frame)
        out[i] = None if det is None else grid_error_cells(det, true_quad)
    return out


def grab_mjpeg_frames(url: str, n: int, timeout: float = 10.0):
    """Pull ``n`` frames off the kiosk's multipart MJPEG stream (``/api/v1/geometry/stream``).

    Splits on JPEG SOI/EOI markers. ``timeout`` bounds every socket read, so a stream that stops
    yielding raises instead of hanging the on-board run.
    """
    import urllib.request

    frames, buf = [], b""
    with urllib.request.urlopen(url, timeout=timeout) as resp:
        while len(frames) < n:
            chunk = resp.read(65536)
            if not chunk:
                break
            buf += chunk
            while len(frames) < n:
                start = buf.find(b"\xff\xd8")
                end = buf.find(b"\xff\xd9", start + 2) if start >= 0 else -1
                if start < 0 or end < 0:
                    break
                img = cv2.imdecode(np.frombuffer(buf[start : end + 2], np.uint8), cv2.IMREAD_COLOR)
                buf = buf[end + 2 :]
                if img is not None:
                    frames.append(img)
    return frames
```

把 `__main__` 段整段换成(不带参数时行为与今天逐字相同):

```python
if __name__ == "__main__":
    # synthetic (LOWER BOUND only):  python -m katrain.vision.tools.outer_corner_accuracy
    # real-board GATE:               python -m katrain.vision.tools.outer_corner_accuracy --live http://127.0.0.1:8081
    import argparse
    import json
    import urllib.request

    ap = argparse.ArgumentParser(description="Outer-corner accuracy: synthetic lower bound, or --live real-board gate.")
    ap.add_argument("--live", metavar="BASE_URL", help="running kiosk, e.g. http://127.0.0.1:8081")
    ap.add_argument("--frames", type=int, default=10)
    args = ap.parse_args()

    if not args.live:
        res = measure()
        for (fill, deg), err in sorted(res.items()):
            print(f"fill={fill:>4.0%}  rot={deg:>3.0f}deg  err={'DETECT_FAIL' if err is None else f'{err:.3f} cells'}")
        print(f"GATE(<0.12 cells) = {gate(res)}")
        raise SystemExit(0)

    base = args.live.rstrip("/")
    with urllib.request.urlopen(base + "/api/v1/geometry/layout", timeout=10) as r:
        layout = json.load(r)
    if layout["stale"]:
        raise SystemExit(f"geometry phase={layout['phase']}: finish an LED calibration on an EMPTY board first")
    true_quad = np.array([[c["x"], c["y"]] for c in layout["corners"]], np.float64)
    want = (layout["frame"]["height"], layout["frame"]["width"])
    frames = grab_mjpeg_frames(base + "/api/v1/geometry/stream", args.frames)
    if len(frames) < args.frames:
        raise SystemExit(f"stream gave {len(frames)}/{args.frames} frames")
    if any(f.shape[:2] != want for f in frames):
        raise SystemExit(f"frame size {frames[0].shape[:2]} != layout frame {want}: corners are in another resolution")
    res = measure_real(frames, true_quad)
    for i, err in sorted(res.items()):
        print(f"frame={i:>2}  err={'DETECT_FAIL' if err is None else f'{err:.3f} cells'}")
    found = [e for e in res.values() if e is not None]
    print(f"detected {len(found)}/{len(res)}  worst-intersection={max(found):.3f} cells" if found else "detected 0")
    print(f"GATE(<0.12 cells, >=80% frames detected) = {live_gate(res)}")
```

- [ ] **Step 4: 跑测试 + 合成模式没被改坏**

```bash
cd /Users/fan/Repositories/katrain-kiosk-go-vision
uv run pytest tests/test_vision/test_outer_corner_accuracy.py -q
uv run python -m katrain.vision.tools.outer_corner_accuracy | tail -1
uv run python -m katrain.vision.tools.outer_corner_accuracy --help | head -3
uv run black -l 120 katrain/vision/tools/outer_corner_accuracy.py tests/test_vision/test_outer_corner_accuracy.py
```

预期:新旧用例全过;合成模式最后一行仍是 `GATE(<0.12 cells) = ...`;`--help` 列出 `--live`。
`--live` 本身没有单测(几行胶水),它的测试就是上板清单第 1 项;若 Mac 上接着摄像头跑着 board 模式,可以顺手对本机服务地址跑一次看输出格式。

- [ ] **Step 5: 提交**

```bash
git add katrain/vision/tools/outer_corner_accuracy.py tests/test_vision/test_outer_corner_accuracy.py
git commit -m "$(cat <<'EOF'
feat(vision): 外框精度工具加真帧模式 --live

原工具只渲染合成棋盘、从不读相机,在板上跑与在 Mac 上跑结果相同,
当不了「满盘外框误差 < 0.12 格」那道上板闸。--live 以空盘 LED 13 点
标定的角点为真值(/geometry/layout),从 /geometry/stream 取真帧量误差;
不带参数时行为不变(合成下界)。

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 9: 产出上板清单 `board-checklist.md`

**Files:** Create `superpowers/tracks/kiosk-go-vision/board-checklist.md`

- [ ] **Step 1: 先把四份旧清单里仍然成立的项抄过来,过期的删掉并写明为什么**

```bash
cd /Users/fan/Repositories/katrain-kiosk-go-vision
sed -n '25,50p' superpowers/tracks/kiosk-physical-play/acceptance-checklist.md
rg -n "\[ \]" superpowers/tracks/kiosk-golaxy-physical-play/plan.md | sed -n '1,20p'
rg -n "上板|真机" superpowers/tracks/sbc-baipu-led-guide/plan.md | sed -n '1,20p'
```

**已知过期两项**(账本核过,直接删并注明):
- 「用横幅中的『重新定位』」—— `PoseLostBanner` 已被 `RecalibrationModal` 取代(本轮又把组件删了);
- 「SET_GEOMETRY 子进程缺失」—— 盒上走 `InProcessAdapter`,不成立。

- [ ] **Step 2: 按这个格式写,每项四栏**

```markdown
## 1. 满盘外框精度(V1 自动重定位的闸)

- **前置**:RK3562 + 摄像头 + 实体盘;**这台机器上只跑这一家服务**(2G 内存)。
  先在**空盘**上跑一次 LED 13 点标定并成功 —— 这次的角点就是真值;**之后盘和相机都不许再动**。
- **操作**(量具是 Task 8b 的真帧模式):
  1. 空盘先跑一次(对照):`uv run python -m katrain.vision.tools.outer_corner_accuracy --live http://127.0.0.1:8081`
  2. 轻手摆到约 60 子(别碰盘),再跑一次;有余力摆到约 150 子跑第三次。
  **不带 `--live` 跑出来的是合成图**,只是下界,不能当这道闸。
- **判据**:每一次都 `GATE(<0.12 cells, >=80% frames detected) = True`(`outer_corner_accuracy.py` 的 `live_gate`:19×19 网格最大误差,且至少八成帧认出盘)。
  空盘那次就已 ≥ 0.12 ⇒ 外框法与 LED 法本身有系统偏差,同样算不过。
  摆子时碰了盘 ⇒ 这组作废,回空盘重标重测。`detected k/n` 照实记;低于八成 `live_gate` 就判不过 —— 十帧只认出一两帧时「那一两帧合格」样本太少,算不了证据(Codex 第 2 轮)。
- **记录**:每次的 `detected` 与 `max` 写回本文件这一节 + 在 PR 里贴一行。**过了才允许把
  `AUTO_RELOCATE_ON_DRIFT` 翻成 `True`,并且要和结果同一次提交。**
```

其余各节按 PRD §7「上板清单」的 6 项写全(碰盘恢复 / 人工出口 / 无灯首标 / 取消后沿用 / LED 目视 bring-up)。
**2026-09-23 补**:第 2、3 项的判据**直接用 develop 已经在打的日志**,不另造量具:
- 朝向:`journalctl` 里 `vision parallax auto: nadir=(…)` 在重定位前后是同一条边(这台盒子 col 18 那条,≈ (19.61, 9.0));
- 幻影落子:从推盘到新锁生效这段窗口里,棋谱没有多出任何一手(PRD §2.1 R3,「不挂起识别」的代价在这里量);
- 端到端距离:重定位后 ≥ 30 手,`board delta:` 行里 `@<距离>` 的中位数照实记下,与 LED 锁下的数(09-22 那局 0.150 格)并排写 —— **只记录、不当开关判据**。
第 4 项(无灯首标)标「⛔ V3 本轮不做,留位」,只写一行将来要核的朝向判据(在 3-4 这种不对称的点摆一颗子,屏上必须是同一个点),不写操作步骤。
vision-optimizations 自己待上板的项(参照帧转正阈值、指引灯整局验证)只放一行指针到 `superpowers/tracks/vision-optimizations/README.md`,不抄。

- [ ] **Step 3: 提交**

```bash
git add superpowers/tracks/kiosk-go-vision/board-checklist.md
git commit -m "$(cat <<'EOF'
docs(vision): 上板清单(四份旧清单收成一份,删掉两条已过期项)

每项写全前置/操作/判据/记录位置;自动重定位的默认开关等第 1 项的数。

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 10: 收尾验证与交付说明

- [ ] **Step 1: 双基线 diff**

```bash
cd /Users/fan/Repositories/katrain-kiosk-go-vision
BASE="$(git rev-parse --absolute-git-dir)/vision-baseline"
CI=true uv run pytest tests --continue-on-collection-errors -q > "$BASE/after-py.log" 2>&1
grep '^FAILED\|^ERROR' "$BASE/after-py.log" | sort -u > "$BASE/after-py.txt"
comm -13 "$BASE/before-py.txt" "$BASE/after-py.txt"
cd katrain/web/ui
npx vitest run --reporter=json --outputFile="$BASE/after.json" > "$BASE/after.log" 2>&1
node "$BASE/failed-names.cjs" "$BASE/after.json" > "$BASE/after-failed.txt"
comm -13 "$BASE/before-failed.txt" "$BASE/after-failed.txt"
```

预期:两个都空。

- [ ] **Step 2: 类型 / 构建 / 格式 / 结构闸**

```bash
npx tsc -b && npm run build && npm run build:kiosk-2d; echo "exit=$?"
# 共享边界规则(src/kiosk ↔ src/galaxy ↔ 共享领地)只在 ESLint 里,tsc 与两套构建都替不了它。只查本赛道动过的文件,
# 免得把仓里别处的既有告警算到这里;预期 0 error。
npx eslint $(git diff --name-only "$(git merge-base HEAD origin/develop)" -- src | sed 's#^katrain/web/ui/##' | grep -E '\.(ts|tsx)$')
cd /Users/fan/Repositories/katrain-kiosk-go-vision
uv run black -l 120 --check katrain tests; echo "black=$?"
# 硬规矩的代码级痕迹:新增路径一处都不许把 led 交给策略
rg -n "CalibrationContext\(" katrain/web/core/geometry_calibration_service.py
```

预期:每一处 `CalibrationContext(` 都写着 `led=None`。

- [ ] **Step 2b: 识别优化零改动 + 回归集 + i18n**(PRD §2.1 R4 / R5、§7)

```bash
cd /Users/fan/Repositories/katrain-kiosk-go-vision
DEV="$(git merge-base HEAD origin/develop)"   # 合进来的 develop;再合一次 develop 也不会误报 develop 自己的改动
git diff --stat "$DEV" -- katrain/vision/worker_inprocess.py katrain/vision/board_state.py katrain/vision/parallax.py \
  katrain/vision/parallax_store.py katrain/vision/reference_frame.py katrain/vision/camera.py katrain/vision/service.py \
  katrain/web/core/led_service.py                                   # 预期:空
git diff --stat "$DEV" -- katrain/web/server.py                       # 预期:空(本赛道不改 server.py)
git diff "$DEV" -- katrain/web/ui/src/kiosk/components/vision/GeometryCalibrationScreen.tsx | grep -c '^[+-].*STREAM_SCALE'   # 预期:0
BASE="$(git rev-parse --absolute-git-dir)/vision-baseline"
xargs env CI=true uv run pytest -q < "$BASE/recog-tests.txt" 2>&1 | tail -1   # 预期:与 Task 1 Step 2b 同数全过(再加本赛道新增的用例)
CI=true uv run pytest -q tests/web_ui/test_kiosk_i18n.py 2>&1 | grep -c "'vision:"          # 预期:0
```

任何一条不符:先查是不是本赛道动了识别优化的东西,**不许**为了过闸去改那几个文件或它们的测试。

- [ ] **Step 3: 交付说明**

写清:① 做了 V1(默认关,含朝向对齐)、V2(含 V6 的前提更正)、V3(**Fan 裁定本轮不做**)、V4(标定屏「串口已连接」、左栏「已连接」、smartbox 设计稿源头一个词的本地提交 —— **未 push,点名交 Fan**;设置屏设置赛道已改;参考图不重拍,四图里那一个词是已知差异)、V5(清单)、Z3;
② 新增文案 key 清单;③ 四图与承重结论(附 Fan 确认);④ **`AUTO_RELOCATE_ON_DRIFT` 还是 `False`**,
翻开它要先跑 `board-checklist.md` 第 1–2 项;⑤ 给对弈赛道的一条登记:V1-b 落地后
`RecalibrationModal` 那句「重新标定(要清盘)」不再是唯一出路,文案该跟着改(A21);⑥ Step 2b 的识别优化零改动核对结果(贴原样输出);⑦ `test_kiosk_i18n.py` 的结果(整体 + `vision:` 那行);若收尾时它因别的赛道的 key 变红,点名是哪些 key、交回对应赛道,不在本赛道补。
