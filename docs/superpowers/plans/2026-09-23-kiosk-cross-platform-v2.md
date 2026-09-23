# 跨平台对弈 v2 实施计划（屏 09 重画 · 登录独立成页 · 每平台专属大厅 · 星阵人人对弈）

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 2026-09-23 Fan 审核通过的 36 屏跨平台设计稿，按「一个用户旅程一个垂直切片」落到 kiosk 上：屏 09 一屏放得下、登录各自成页、每家平台进自己的大厅、星阵人人对弈接通。

**Architecture:** 前端全部落在 `katrain/web/ui/src/kiosk/`（共享territory 只读不改，除非任务明写）；后端全部落在既有的 `katrain/web/platforms/<平台>/adapter.py` + 通用 `/{platform}/...` 路由，**不新增按平台分叉的路由**。每个切片按 vertical-slice 七步走，第 3 步的四图对比与承重实测**不得省略**。

**Tech Stack:** React 19 + TypeScript + Vite（kiosk-2d 构建，无 three.js）· FastAPI + httpx · Playwright（四图与几何闸）· vitest（纯逻辑单测）· pytest（后端）· GNU gettext `.po`（11 语种）

**Spec:**
- 设计稿 artifact（第 33 版，36 屏）：`https://claude.ai/code/artifact/e4d3c7ef-82dd-4a5e-a7b0-42db6b4ad731`
- 设计源：`smartbox-software` 仓 worktree `.worktrees/kiosk-go-cross-platform-design`，分支 `feat/kiosk-go-cross-platform-design-2026-09-22`，文件 `superpowers/shared/kiosk-shell/sample-go/go-kiosk.tmpl.html`
- 协议事实：`katrain/web/platforms/golaxy/PROTOCOL.md`、`katrain/web/platforms/ogs/PROTOCOL.md`，以及稿子里屏 07a / 07c / 08a 上方那三段 HTML 注释（**扫码五步链、taste 匹配常量、OGS 只列实时局**都写在那里，逐字照做）

---

## Global Constraints

以下每条对**每个任务**都成立，任务里不再重复。

1. **语言**：界面字符串一律 `t('namespace:key', '中文默认')`，两个参数都必须是**单引号字面量**——闸 `tests/web_ui/test_kiosk_i18n.py` 的正则 `\bt\(\s*'([^']+)'\s*,\s*'([^']*)'\s*\)` 只认这一种写法，模板串或双引号会让闸**看不见**这个 key（假绿）。
2. **11 个语种**：`en cn tw jp ko de es fr ru tr ua`。注意 **`cn` 不是 `zh`、`jp` 不是 `ja`**。每个新 key 都要在这 11 份 `katrain/i18n/locales/<lang>/LC_MESSAGES/katrain.po` 里有**真译文**——非空**且**不带 `TODO` 注释（`i18n.py:76/78` 会拿英文顶上并打 TODO，闸专门挡这个）。
3. **命名空间**：跨平台模块统一用 `platform:`。develop 上已有 87 个 `platform:*` key，**先 grep 再新增**，不要造同义重复 key。
4. **插值**：`{n}` / `{name}` 这种占位符用 `interpolate()`（`katrain/web/ui/src/kiosk/utils/interpolate.ts`）。同一 key 在 11 个语种里的占位符集合必须一致——`i18n.py:44-51` 会报不一致。
5. **构建边界**：`src/kiosk/**` 不得 import `src/galaxy/**`、`src/components/Board3D/**`、`src/pages/VideoRecorderPage*`。改动共享目录（`src/components/`、`src/hooks/`、`src/api.ts` 等）要同时跑 `npm run build` 和 `npm run build:kiosk-2d`。
6. **目标 viewport**：1024×600。L2 布局 A = 左盘 516 + 间距 16 + 右栏 460；右栏纵向 516 = 页控条 44 + 12 + 内容视口 **400** + 12 + 主按钮 48。
7. **按钮给了背景就必须同时给 `color`**。`.aiplate` 是 `<button>`，给背景不给 `color` ⇒ 内部 `h4` 继承浏览器默认纯黑，闸不查字色，只能靠看图。这是 Fan 2026-09-23 亲自逮到的那个缺陷。
8. **状态诚实**：没接通的功能不摆灰按钮等人点，也不写「即将上线」（没人给过日期＝预测不是状态）。照屏 07 已落锤的口径，写**它今天是什么**（例：「星阵人人对弈还没接通」）。稿子上那枚 `.wip` 琥珀标是给读稿人看的进度标注，**不上屏**。
9. **不给兜底表**：平台下发的数据（棋力档、对局列表、用户列表）取不到就显示取不到。编一份假的会让人选中平台不认识的值。
10. **提交**：每个 Task 末尾提交一次，消息用中文祈使句 + 一句为什么。提交末尾加：
    ```
    Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
    ```
11. **跑全量 pytest 之前，环境必须是 `uv sync --extra web --extra vision`。**
    少了 `--extra web` 缺 fastapi，整套测试塌成一个空的 FAILED 基线（看起来像全绿）；
    少了 `--extra vision` 缺 opencv-python，**约 40 个 vision 测试文件变成 collection ERROR** ——
    那看起来像是你这次改动造成的回归，其实只是依赖没装。develop 自己的 CI 是
    `sync-groups: dev` 再加一个单独的 `--extra vision` job，两边合起来才是完整环境。
    （Task 0 实测得出，2026-09-23。）
12. **`sample-go/gate.mjs` 每跑一次都会把 36 屏全部重新截图**，不是只做校验。
    所以「跑一次闸」会把设计仓里那些本来不该变的图重新弄脏。跑完闸之后要
    **再还原一次**没改过的那些屏，否则它们会带着抖动被提交进去，
    而四图的参考物就此悄悄换了。（Task 0 实测得出，2026-09-23。）

---

## Review Focus

这五类输入/失败模式，规范里隐含但**没有任何一个任务的测试天然覆盖**，按「最可能咬到真人」排序。每一条都在下面指定的任务里补了测试。

1. **平台只下发 0 档或 1 档棋力**（`GET /{platform}/engine/levels` 返回空数组）。今天 `KioskStepTrack count={sorted.length}` 会拿到 0，点位除零、`currentIdx` 恒 −1、名牌无名字可显示，而主按钮的 `disabled` 只判 `level === null`。→ 测试归 **Task 2**。
2. **扫码取不到 uuid**（盒子连不上星阵）。稿子明写这一态要变虚线框 + 「连不上星阵，检查网络」+「重试」，**不摆一张扫不动的假码**。轮询也必须停。→ 测试归 **Task 6**。
3. **共用盒子换人**：`PlatformManager` 一个平台**只有一个全局 adapter**（`manager.py:34`），`list_platforms()` 直接吐 `adapter.is_connected` 而不看调用者（`:48-60`），`disconnect_platform()` 签名里根本没有 `user_id`（`:91`），端点只有 `Depends(get_current_user)`（那是认证不是授权）。⇒ 用户 2 看得见、用得上、还能断开用户 1 的平台会话。→ 测试归 **Task 4.5**（发布阻断项，切片 A 第一个做）。
   > 注意判据落点：只测 `PlatformCredentialStore` 是**无效**的——那一层本来就按 user_id 分行，一测就绿，而堵点在更外面。
4. **39 档选择面板开着时，实体盘上有人落子**（或视觉同步事件到达）。面板是全栏覆盖层，落子事件不该被它吞掉，也不该在面板上「穿透」到底下的轨。→ 测试归 **Task 3**。
5. **语种切到韩文**：新 key 没进 `.po` 就静默显示中文——屏上每个字都在，只是语言不对，**读代码和跑单测都看不出来**（jsdom 里翻译表没加载，`t()` 恒返回默认值）。更窄的一种：key 从常量表用**变量**传进 `t()`，闸的正则（只认两个单引号字面量）**整个看不见它**。→ 目录闸归 **Task 1 起每个任务的收尾步**，「屏上真是译文」的组件测试归 **Task 5 Step 6b**，韩文冒烟是**每个含动态 key 的切片自己的完成条件**（不是推到 Task 16）。

---

## 文件结构

**新建**

| 文件 | 职责 |
|---|---|
| `src/kiosk/components/setup/AiOpponentPlate.tsx` | 屏 09 签名件「对手名牌」：头像 + 名字·段位 + 展示 Elo·对标 + 第 N/39 档；点开面板 |
| `src/kiosk/components/setup/AiLevelSheet.tsx` | 39 档全表覆盖层（名牌点开后出现），按段位分组，单选即关 |
| `src/kiosk/pages/PlatformLoginPage.tsx` | 屏 07a/07b/08：一家平台一页登录，左栏 300 讲「登录之前要知道的」，右栏 520 放表单 |
| `src/kiosk/components/platform/PlatformLoginAside.tsx` | 登录页左栏（identity + 三/四条 facts），按平台取文案 |
| `src/kiosk/components/platform/GolaxyScanPanel.tsx` | 星阵扫码标签页：本地画二维码 + 五态状态行 + 轮询 |
| `src/kiosk/pages/GolaxyHomePage.tsx` | 屏 07 星阵大厅：落子/路数 + 开一局三张卡 + 棋友名单 |
| `src/kiosk/constants/platformLoginFacts.ts` | 各平台登录页左栏文案的 key 表（**只放 key，不放中文**，中文在 `.po`） |
| `katrain/web/platforms/golaxy/scan_login.py` | 星阵扫码登录五步链（code / state / token / username） |
| `tests/web_ui/test_platform_scan_login.py` | 扫码链的后端契约测试 |
| `katrain/web/ui/tests/kiosk-screen-09-setup.fourup.spec.ts` | 屏 09 四图（从 `07-09` 那个文件拆出来，因为这一屏要单独量几何） |
| `katrain/web/ui/tests/kiosk-geometry-platform.spec.ts` | 跨平台各屏的真浏览器几何闸（可滚性/不溢出/落点） |

**修改**

| 文件 | 改什么 |
|---|---|
| `src/kiosk/pages/PlatformEngineSetupPage.tsx` | 五段压成三段、路数降为提示行、接名牌与面板、去掉「这一局会是」段 |
| `src/kiosk/shell/KioskStepTrack.tsx` | 加 `readout={false}`（读数搬进名牌后不再画那一行）——**共享件，改完要回看 `AiSetupPage` 那三条轨** |
| `src/kiosk/KioskApp.tsx` | 新增 `play/cross-platform/login/:platform`、`play/cross-platform/golaxy` 两条路由 |
| `src/kiosk/pages/PlayPage.tsx` | 未连接的平台卡改为跳**那一家的**登录页；已连接的星阵跳 `golaxy` 首页而不是直接 engine |
| `src/kiosk/pages/PlatformConnectPage.tsx` | 撤掉页内登录段（搬进登录页），只留平台清单 + 登出 |
| `src/kiosk/pages/PlatformLobbyPage.tsx` | 改成 OGS 专用：名单换成公开挑战、**只列实时局**、非 19 路挑战在实体盘模式下不给接受键 |
| `src/kiosk/pages/SettingsPage.tsx` | 账号与平台一节只列**已连接**的平台，副文案改成「现在挂着谁的账号」 |
| `src/api.ts` | 新增 `platformScanStart` / `platformScanPoll` / `platformScanConfirm` 等 |
| `katrain/web/platforms/golaxy/adapter.py` | 接上扫码登录；Slice D 里接 `get_online_users` / `send_challenge` / `start_automatch` / 房间 |
| `katrain/web/api/v1/endpoints/platforms.py` | 新增扫码三个端点 |
| `katrain/i18n/locales/*/LC_MESSAGES/katrain.po` | 每个切片新增的 key × 11 语种 |
| `katrain/web/ui/tests/helpers/reference-shots.json` | 新屏登记指纹，改过的屏更新指纹 |

---

## Task 0: 对齐基线 —— 追 develop、把设计稿钉进四图闸

**这个任务必须第一个做完，后面每一个任务都踩在它上面。**

**Files:**
- Modify: `katrain/web/ui/tests/helpers/reference-shots.json`
- Commit in another repo: `~/Repositories/smartbox-software` 的 worktree `.worktrees/kiosk-go-cross-platform-design`

**Interfaces:**
- Produces: 一条与 `origin/develop` 对齐的分支；`reference-shots.json` 里 36 屏各有指纹；设计分支已提交且可被 `git show <branch>:<path>` 读到

- [ ] **Step 1: 确认这条分支相对 develop 的位置**

```bash
cd ~/Repositories/katrain-kiosk-go-cross-platform
git rev-list --left-right --count origin/develop...HEAD
```
Expected: `266	0` 这样的形状——**右边必须是 0**。右边不是 0 说明这条分支上有 develop 没有的提交，**停下来问 Fan**，不要自己合并。

- [ ] **Step 2: 记下基线失败集合（不是条数）**

```bash
cd ~/Repositories/katrain-kiosk-go-cross-platform
CI=true uv run pytest tests --continue-on-collection-errors -q 2>&1 | grep '^FAILED\|^ERROR' | sort > /tmp/baseline-before.txt
wc -l /tmp/baseline-before.txt
```
判据是**名字集合**不是条数。后面每次跑全量都和这份 `comm` 比，新增的才算自己造的。

- [ ] **Step 3: 快进到 develop**

```bash
cd ~/Repositories/katrain-kiosk-go-cross-platform
git merge --ff-only origin/develop
```
Expected: `Fast-forward`。报错就回到 Step 1 的判断。

- [ ] **Step 4: 重新装依赖并重跑基线**

```bash
cd ~/Repositories/katrain-kiosk-go-cross-platform
uv sync --extra web --extra vision
CI=true uv run pytest tests --continue-on-collection-errors -q 2>&1 | grep '^FAILED\|^ERROR' | sort > /tmp/baseline-after.txt
comm -13 /tmp/baseline-before.txt /tmp/baseline-after.txt
```
Expected: 追 develop 之后新增的失败应当为空。有就先查清楚再往下走。

- [ ] **Step 5: 确认 i18n 闸现在是绿的**

```bash
cd ~/Repositories/katrain-kiosk-go-cross-platform
uv run pytest tests/web_ui/test_kiosk_i18n.py -q
```
Expected: PASS。这条闸从现在起是每个任务的收尾判据。

- [ ] **Step 6: 在设计仓里把 jitter-only 的图还原**

设计工作树里 27 张老图全是 `M`，多数只是重建抗锯齿抖动（实测量级 ~135/614400 像素）。只留**真改过**的那几屏：`07-platform` `08-platform-lobby` `09-platform-engine` `10-platform-game` `27-settings`，其余 `git checkout` 还原。

```bash
cd ~/Repositories/smartbox-software/.worktrees/kiosk-go-cross-platform-design/superpowers/shared/kiosk-shell/sample-go
# 先看每张图改了多少，确认哪些是抖动
for f in shots/*.png; do printf "%-34s %s\n" "$(basename $f)" "$(git diff --numstat -- $f | cut -f1-2)"; done
```
判据不是像素数（canvas 屏抖动可达 ~4500），是**这一屏的设计到底改没改**：对着 `go-kiosk.tmpl.html` 的 git diff 看哪些 `data-screen` 段被动过。没动过的还原：

```bash
git checkout -- shots/<没动过的那些>.png
```

- [ ] **Step 7: 删掉一张过期的图**

`shots/08a-platform-challenge.png` 是早前命名下的残留（现在那一屏叫 `08b-platform-challenge`）。闸的 `shotNames` 里没有它，留着会让下一个人以为少画了一屏。

```bash
git rm shots/08a-platform-challenge.png
```

- [ ] **Step 8: 跑闸，确认 36 屏全过**

```bash
cd ~/Repositories/smartbox-software/.worktrees/kiosk-go-cross-platform-design/superpowers/shared/kiosk-shell/sample-go
python3 build.py && python3 build.py --proto
KIOSK_PLAYWRIGHT=~/Repositories/smartbox-software/chess/ui/node_modules/@playwright/test node gate.mjs
```
Expected: `936/936`、36 张图。

- [ ] **Step 9: 提交设计源**

```bash
cd ~/Repositories/smartbox-software/.worktrees/kiosk-go-cross-platform-design
git add -A superpowers/shared/kiosk-shell/sample-go
git commit -m "$(cat <<'EOF'
feat(kiosk-go): 跨平台 v2 设计稿 36 屏 —— 登录独立成页、OGS 登录屏、屏 09/10 照真实现回写

Fan 2026-09-23 审核通过。四条裁定:登录独立成页(左栏答「登录之前要知道的」)、
OGS 盒上只做用户名+密码、屏 10 按 9e71a942 的真实现回写、屏 09 一屏放得下。
设置页账号一节只列已连接的平台。

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
EOF
)"
git rev-parse HEAD
```

- [ ] **Step 10: 更新四图指纹**

`katrain/web/ui/tests/helpers/fourup.ts:377-401` 按 `{sha256, shotFrom}` 从设计仓 git 里取参考图；**没有登记项会直接抛错**（`fourup.ts:379`）。36 屏里目前只登记了 27 个名字，新增的 9 屏一个都没有。

```bash
cd ~/Repositories/smartbox-software/.worktrees/kiosk-go-cross-platform-design/superpowers/shared/kiosk-shell/sample-go
BR=feat/kiosk-go-cross-platform-design-2026-09-22
for f in shots/*.png; do
  printf '  "%s": { "sha256": "%s", "shotFrom": "%s" },\n' \
    "$(basename $f)" "$(shasum -a 256 $f | cut -d' ' -f1)" "$BR"
done
```
把输出贴进 `katrain/web/ui/tests/helpers/reference-shots.json`，**保持已有的 `shotFrom` 不动**——没改过的屏还指向它原来那条分支，改成新分支等于悄悄换了参考物。

- [ ] **Step 11: 验指纹确实能取回**

```bash
cd ~/Repositories/katrain-kiosk-go-cross-platform/katrain/web/ui
npx playwright test tests/kiosk-screen-07-09-platform.fourup.spec.ts --reporter=line
```
Expected: 三条四图都跑起来（差异会很大，因为稿子改了而实现还没改——**这正是对的**，说明参考物换成了新稿）。

- [ ] **Step 12: 提交**

```bash
cd ~/Repositories/katrain-kiosk-go-cross-platform
git add katrain/web/ui/tests/helpers/reference-shots.json
git commit -m "$(cat <<'EOF'
test(kiosk-go): 跨平台 v2 设计稿 36 屏登记指纹

新增 9 屏(登录三屏/匹配/房间/邀请/OGS 登录/OGS 大厅/人人对局)此前没有登记项,
按 fourup.ts:379 会直接抛错。改过的五屏更新指纹,没改过的保持原 shotFrom ——
换分支等于悄悄换参考物。

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
EOF
)"
```

---

# 切片 C：屏 09 一屏放得下

**用户旅程：** 「我要跟星阵的 bot 下一盘」——进设置页，四件事一屏看完，按开始。

**为什么排第一：** 纯前端闭环、当天能上板看见；且它是这一版里唯一一个**改既有页**而不是新建页的切片，风险最小。

> ⚠️ **这一屏不是从零开发。** `/kiosk/play/cross-platform/engine/golaxy` 已经实现了档位轨、39 档、「怎么落子」开关。`PlatformEngineSetupPage.tsx` 的文件头注释里写着 2026-08-24 那条裁定：**稿子上那段 39 行摊开的名单不做**，理由三条（规范禁止一屏两种选择控件 / 屏 02 的 29 档已按同一条判过 / 摊开后一段吃掉 97.5% 视口）。新稿把名单收进「点名牌展开」，**与那条裁定一致**——收起来的是常驻控件，不是值。不要推倒重来。

## Task 1: 「对手名牌」组件

**Files:**
- Create: `katrain/web/ui/src/kiosk/components/setup/AiOpponentPlate.tsx`
- Create: `katrain/web/ui/src/kiosk/components/setup/AiOpponentPlate.test.tsx`
- Modify: `katrain/web/ui/src/kiosk-shell/go-screens.css`（新增 `.aiplate` 一族）

**Interfaces:**
- Produces:
  ```ts
  interface AiOpponentPlateProps {
    name: string;            // 「星皮猴」
    levelName: string;       // 「2 段」
    displayElo: number;      // 1500
    refRank?: string;        // 「业余 2 段」,平台没给就不画那一段
    index: number;           // 0 起
    total: number;           // 39
    onOpen: () => void;      // 点开全表
    testId?: string;
  }
  const AiOpponentPlate: (p: AiOpponentPlateProps) => JSX.Element;
  ```

- [ ] **Step 1: 写失败测试**

```tsx
// katrain/web/ui/src/kiosk/components/setup/AiOpponentPlate.test.tsx
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import AiOpponentPlate from './AiOpponentPlate';

describe('AiOpponentPlate', () => {
  it('把档位读数放在名牌上,不再单独占一行', () => {
    render(<AiOpponentPlate
      name="星皮猴" levelName="2 段" displayElo={1500} refRank="业余 2 段"
      index={21} total={39} onOpen={() => {}} testId="plate"
    />);
    expect(screen.getByTestId('plate')).toHaveTextContent('星皮猴');
    expect(screen.getByTestId('plate')).toHaveTextContent('第 22 / 39 档');
    expect(screen.getByTestId('plate')).toHaveTextContent('1500');
  });

  it('平台没给对标棋力就不画那一段,不写「未知」', () => {
    render(<AiOpponentPlate
      name="星猛虎" levelName="9 段" displayElo={3000}
      index={38} total={39} onOpen={() => {}} testId="plate"
    />);
    expect(screen.getByTestId('plate')).not.toHaveTextContent('对标');
  });

  it('点名牌打开全表', async () => {
    const onOpen = vi.fn();
    render(<AiOpponentPlate
      name="星皮猴" levelName="2 段" displayElo={1500}
      index={0} total={39} onOpen={onOpen} testId="plate"
    />);
    await userEvent.click(screen.getByTestId('plate'));
    expect(onOpen).toHaveBeenCalledOnce();
  });
});
```

- [ ] **Step 2: 跑它确认它红**

Run: `cd katrain/web/ui && npx vitest run src/kiosk/components/setup/AiOpponentPlate.test.tsx`
Expected: FAIL，`Cannot find module './AiOpponentPlate'`

- [ ] **Step 3: 写组件**

```tsx
// katrain/web/ui/src/kiosk/components/setup/AiOpponentPlate.tsx
import { useTranslation } from '../../../hooks/useTranslation';
import { interpolate } from '../../utils/interpolate';

/**
 * 屏 09 的签名件 —— 一张 56 高的「当前对手名牌」。
 *
 * ## 为什么读数要搬到名牌上
 *
 * `KioskStepTrack` 自带一行 `.catmeta` 读数(「第 22 / 39 档 · 展示 Elo 1500」)。
 * 屏 09 要在 400px 视口里放下四组设置,那一行 20px 省下来正好是「怎么落子」
 * 那句提示的位置。更要紧的是:**读数和对手是同一件事**,分两行写,推轨的时候
 * 眼睛要在两处之间来回跳。
 *
 * ## 为什么是 `<button>`
 *
 * 39 档的轨每档约 8px,跨到远处只能长按连发。名牌点开是**唯一**能一步跳到
 * 任意一档的路。⚠️ 它是 `<button>`,给了背景就必须同时给 `color` ——
 * 不给的话 `h4` 继承浏览器默认纯黑,在青毡底上看不见(2026-09-23 实际发生过)。
 */
interface AiOpponentPlateProps {
  name: string;
  levelName: string;
  displayElo: number;
  refRank?: string;
  index: number;
  total: number;
  onOpen: () => void;
  testId?: string;
}

const AiOpponentPlate = ({
  name, levelName, displayElo, refRank, index, total, onOpen, testId,
}: AiOpponentPlateProps) => {
  const { t } = useTranslation();
  const rung = interpolate(t('platform:rung_n', '第 {i} / {n} 档'), { i: index + 1, n: total });
  return (
    <button
      type="button"
      className="aiplate"
      data-testid={testId}
      aria-live="polite"
      aria-label={interpolate(
        t('platform:plate_aria', '当前对手 {name} {level}，{rung}；点开看全部'),
        { name, level: levelName, rung },
      )}
      onClick={onOpen}
    >
      <span className="av" aria-hidden="true">{name.slice(0, 1)}</span>
      <div>
        <h4>{name} · {levelName}</h4>
        <p>
          {interpolate(t('platform:display_elo', '展示 Elo {v}'), { v: displayElo })}
          {refRank ? <> · {interpolate(t('platform:ref_rank', '对标{r}'), { r: refRank })}</> : null}
        </p>
      </div>
      <b className="rung">{rung}</b>
    </button>
  );
};

export default AiOpponentPlate;
```

- [ ] **Step 4: 写样式**

在 `katrain/web/ui/src/kiosk-shell/go-screens.css` 里新增。**先 grep 确认 `.aiplate` / `.av` / `.rung` 在这份表里没被别人用过**——同一份样式表里的同名类只覆盖它自己写了的属性，漏一条就撑破另一屏。

```bash
grep -n '\.aiplate\|\.rung' katrain/web/ui/src/kiosk-shell/go-screens.css
```
命中就改名（例如 `.aiplate__rung`）。没命中再写：

```css
/* 屏 09 对手名牌 —— <button> 给了背景就必须给 color,否则 h4 继承浏览器默认黑 */
.aiplate {
  display: flex; align-items: center; gap: 12px; width: 100%;
  height: 56px; padding: 0 12px; margin-bottom: 10px;
  border: 1px solid var(--hair); border-radius: 10px;
  background: color-mix(in srgb, var(--accent) 7%, transparent);
  color: var(--text);
  text-align: left; cursor: pointer;
}
.aiplate h4 { margin: 0; font-size: 15px; color: var(--text); }
.aiplate p  { margin: 2px 0 0; font-size: 12px; color: var(--dim); }
.aiplate .rung { margin-left: auto; font-size: 13px; color: var(--dim); white-space: nowrap; }
```
两条核过的事实，别改：
- **`--dim` 才是次文本的 token**（`tokens.css:238` / `go-tokens.css:28`）。`--text-dim` / `--on-accent` **这个仓里不存在**——写了浏览器会静默丢弃整条 `color` 声明，副文案就继承成别的颜色。强调底上的字色是 `--ink`（`tokens.css:987` 的 `.kiosk-btn--primary` 就是 `background:var(--accent); color:var(--ink)`）。
- **`.av` 已经存在**（`go-screens.css:1187`，30px 圆点、发丝描边、`--panel` 底、`--accent` 字、衬线体）。**直接复用，不要写 `.aiplate .av` 去覆盖**——同一份样式表里的同名类只覆盖你写了的那几条属性，剩下的漏过去，两屏的头像会长得半像不像。

- [ ] **Step 5: 跑测试确认绿**

Run: `cd katrain/web/ui && npx vitest run src/kiosk/components/setup/AiOpponentPlate.test.tsx`
Expected: 3 passed

- [ ] **Step 6: 补 i18n key**

新增 key：`platform:plate_aria`。其余（`platform:rung_n` / `platform:display_elo` / `platform:ref_rank`）develop 上已有，先确认：

```bash
cd ~/Repositories/katrain-kiosk-go-cross-platform
for k in platform:plate_aria platform:rung_n platform:display_elo platform:ref_rank; do
  printf '%-26s %s\n' "$k" "$(grep -c "^msgid \"$k\"$" katrain/i18n/locales/cn/LC_MESSAGES/katrain.po)"
done
```
缺的那个要写进 **11 份** `.po`。译文要**真翻**，不许拿英文顶。参考已有条目的风格：
```po
msgid "platform:plate_aria"
msgstr "当前对手 {name} {level}，{rung}；点开看全部"
```
11 个语种的译法由**懂那门语言的人或翻译工具**给，不要自己编。`{name}` `{level}` `{rung}` 三个占位符每种语言都必须出现，否则 `i18n.py:44-51` 报不一致。

- [ ] **Step 7: 跑 i18n 闸**

```bash
uv run pytest tests/web_ui/test_kiosk_i18n.py -q && uv run python i18n.py -todo
```
Expected: 两条都 PASS / 无 TODO 输出

- [ ] **Step 8: 提交**

```bash
git add katrain/web/ui/src/kiosk/components/setup/AiOpponentPlate.tsx \
        katrain/web/ui/src/kiosk/components/setup/AiOpponentPlate.test.tsx \
        katrain/web/ui/src/kiosk-shell/go-screens.css \
        katrain/i18n/locales/*/LC_MESSAGES/katrain.po
git commit -m "$(cat <<'EOF'
feat(kiosk-go): 屏 09 对手名牌 —— 档位读数从单独一行搬进名牌

400px 视口里省下 20px 给「怎么落子」那句提示;更要紧的是读数和对手是同一件事,
分两行写推轨时眼睛要来回跳。名牌是 <button>,背景和 color 一起给 ——
只给背景会让 h4 继承浏览器默认纯黑(2026-09-23 实际发生过)。

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
EOF
)"
```

## Task 2: 39 档全表面板

**Files:**
- Create: `katrain/web/ui/src/kiosk/components/setup/AiLevelSheet.tsx`
- Create: `katrain/web/ui/src/kiosk/components/setup/AiLevelSheet.test.tsx`
- Modify: `katrain/web/ui/src/kiosk-shell/go-screens.css`

**Interfaces:**
- Consumes: `EngineLevel` from `src/api.ts`（字段 `elo_score` / `level_name` / `name` / `display_elo` / `ref_rank`）
- Produces:
  ```ts
  interface AiLevelSheetProps {
    levels: EngineLevel[];   // 已按 elo_score 升序
    currentElo: number | null;
    onPick: (elo: number) => void;   // 选中即关
    onClose: () => void;
    testId?: string;
  }
  ```

> ## ⛔ Step 0（闸）：这一交互要先裁定，裁定之前不写代码
>
> **不要把这一条放到第 3 步的视觉关卡再问。** 那是「先实现再确认规则」——做完的东西会给裁定施压。
>
> 仓里的原话（`tokens.css` `.kiosk-optseg` 上方）是：**「一屏里所有选择组必须用同一种控件，不许难度用列表」**。它**没有**写「只要不同时可见就可以有第二套」。而且 `KioskStepTrack` 的文件头把**弹层**明确列为被否掉的方案之一（理由是 7″ 触屏上弹层盖住左边那块盘）。
>
> 所以「面板不违反那条裁定」是**我的重新解释，不是仓里的既有依据**。三选一，请 Fan 拍：
>
> **(a) 放行，并把规范改写清楚** —— 在 `tokens.css` 那段注释里补一句「常驻的第二套选择控件禁止；点开即用、选完即关、且不遮挡棋盘的临时跳转器不在此列」，把例外写进规范而不是留在某个组件的注释里。
> **(b) 否掉面板** —— 名牌改成不可点的只读读数，**去掉 caret**（caret 承诺展开，不给展开就是撒谎）。39 档只能靠 −/＋ 长按连发跨越，接受这个代价。
> **(c) 换一种跨越方式** —— 例如名牌上加「最弱 / 最强 / 回到默认」三颗快捷键，不引入第二套「选择」控件。
>
> **裁定结果写进本任务的验收记录。选 (b) 或 (c) 时，Task 2 整个作废，Task 3 里所有 `AiLevelSheet` 相关代码一并删掉，Task 4 的「面板」那几条几何断言换成对应的形状。**
>
> 下面的 Step 1 起，**只有 Fan 选了 (a) 才执行**。

- [ ] **Step 1: 写失败测试**

```tsx
// katrain/web/ui/src/kiosk/components/setup/AiLevelSheet.test.tsx
import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import AiLevelSheet from './AiLevelSheet';
import type { EngineLevel } from '../../../api';

const mk = (n: number): EngineLevel[] => Array.from({ length: n }, (_, i) => ({
  elo_score: 100 + i * 10, level_name: `${i + 1} 段`, name: `星阵 ${i + 1}`,
  goal_difference: 0, timing: '', display_elo: 400 + i * 50, ref_rank: `业余 ${i + 1}`,
}));

describe('AiLevelSheet', () => {
  it('39 档一个不少', () => {
    render(<AiLevelSheet levels={mk(39)} currentElo={null} onPick={() => {}} onClose={() => {}} testId="sheet" />);
    expect(screen.getAllByTestId('level-row')).toHaveLength(39);
  });

  it('选中的那一行带 aria-current', () => {
    render(<AiLevelSheet levels={mk(39)} currentElo={310} onPick={() => {}} onClose={() => {}} testId="sheet" />);
    const rows = screen.getAllByTestId('level-row');
    expect(within(rows[21]).getByRole('button')).toHaveAttribute('aria-current', 'true');
  });

  it('点一行就回传并关闭', async () => {
    const onPick = vi.fn(); const onClose = vi.fn();
    render(<AiLevelSheet levels={mk(39)} currentElo={100} onPick={onPick} onClose={onClose} testId="sheet" />);
    await userEvent.click(within(screen.getAllByTestId('level-row')[5]).getByRole('button'));
    expect(onPick).toHaveBeenCalledWith(150);
    expect(onClose).toHaveBeenCalledOnce();
  });

  // Review Focus #1:平台只下发 0 档
  it('一档都没有时,面板说明白是平台没给,不画空列表', () => {
    render(<AiLevelSheet levels={[]} currentElo={null} onPick={() => {}} onClose={() => {}} testId="sheet" />);
    expect(screen.queryAllByTestId('level-row')).toHaveLength(0);
    expect(screen.getByTestId('sheet')).toHaveTextContent('没能从平台取回棋力档');
  });
});
```

- [ ] **Step 2: 跑它确认它红**

Run: `cd katrain/web/ui && npx vitest run src/kiosk/components/setup/AiLevelSheet.test.tsx`
Expected: FAIL

- [ ] **Step 3: 写组件**

```tsx
// katrain/web/ui/src/kiosk/components/setup/AiLevelSheet.tsx
import { useEffect, useRef } from 'react';
import type { EngineLevel } from '../../../api';
import { useTranslation } from '../../../hooks/useTranslation';
import { interpolate } from '../../utils/interpolate';

/**
 * 39 档全表 —— 名牌点开后覆盖在右栏上的一层。
 *
 * ## 为什么它不违反「一屏一种选择手势」
 *
 * 2026-08-24 那条裁定禁的是**两套选择控件同时摆在屏上**(轨 + 摊开的列表)。
 * 这一层点开即用、选完即关,任一时刻屏上只有一种手势。它解决的是轨解决不了的
 * 那件事:39 档每档约 8px,跨到远处只能长按连发。
 *
 * ## 只盖右栏,不盖盘
 *
 * `position:absolute` 相对 `.kiosk-rail`,不是 `fixed` —— 左边那块盘画的是
 * 「按下开始之后会出现的局面」,盖住它就没了反馈。这也是当初撤掉 MUI Select 的理由。
 */
interface AiLevelSheetProps {
  levels: EngineLevel[];
  currentElo: number | null;
  onPick: (elo: number) => void;
  onClose: () => void;
  testId?: string;
}

const AiLevelSheet = ({ levels, currentElo, onPick, onClose, testId }: AiLevelSheetProps) => {
  const { t } = useTranslation();
  const currentRef = useRef<HTMLButtonElement>(null);

  // 打开时把当前那一档滚到可视区 —— 39 档里第 22 档在默认视口外。
  useEffect(() => { currentRef.current?.scrollIntoView({ block: 'center' }); }, []);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose(); };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [onClose]);

  return (
    <div
      className="aisheet"
      data-testid={testId}
      role="dialog"
      aria-modal="true"
      aria-label={t('platform:level_sheet', '全部棋力档')}
    >
      <div className="aisheet__head">
        <b>{t('platform:level_sheet', '全部棋力档')}</b>
        <button type="button" className="kiosk-btn kiosk-btn--pill" onClick={onClose}>
          {t('platform:close', '收起')}
        </button>
      </div>
      {levels.length === 0 ? (
        <p className="lobbyempty">{t('platform:levels_failed', '没能从平台取回棋力档')}</p>
      ) : (
        <div className="aisheet__body" data-scrollbar>
          {levels.map((l, i) => (
            <div className="aisheet__row" data-testid="level-row" key={l.elo_score}>
              <button
                type="button"
                ref={l.elo_score === currentElo ? currentRef : undefined}
                aria-current={l.elo_score === currentElo ? 'true' : undefined}
                onClick={() => { onPick(l.elo_score); onClose(); }}
              >
                <span className="idx">{i + 1}</span>
                <span className="nm">{l.name} · {l.level_name}</span>
                <span className="el">
                  {interpolate(t('platform:display_elo', '展示 Elo {v}'), { v: l.display_elo })}
                  {l.ref_rank ? ` · ${interpolate(t('platform:ref_rank', '对标{r}'), { r: l.ref_rank })}` : ''}
                </span>
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

export default AiLevelSheet;
```

- [ ] **Step 4: 写样式**

先 grep 冲突（同 Task 1 Step 4 的做法），再写。面板要 `position:absolute; inset:0;` 相对 `.kiosk-rail`。

> ## ⚠️ 这一处已经 grep 过了，**命中**，所以承重实测是必做的，不是「视察一下」
>
> ```
> katrain/web/ui/src/kiosk/shell/scrollSync.ts:38
>     bar.style.top = `${scroll.offsetTop}px`;
> ```
> `offsetTop` 是相对 `offsetParent` 量的。`.kiosk-rail` 今天**没有 `position`**（`tokens.css:616` 只有 `display/flex-direction/gap/min-width`），所以滚动区的 `offsetParent` 是更外面某一层。一旦给 rail 加 `position: relative`，**`offsetParent` 就换人了**，`scroll.offsetTop` 跟着变 ⇒ **滚动条拇指错位**。
>
> 三条要求：
> 1. **作用域必须限定在这一屏**：`[data-testid="platform-engine-setup-page"] .kiosk-rail { position: relative; }`。
>    **绝不能裸写 `.kiosk-rail { position: relative }`** —— 那个类是全部 L2/L3 屏共用的，裸加等于一次改掉每一屏的拇指位置。
> 2. Task 4 的几何闸**补一条拇指断言**（见那边的清单）。
> 3. **变异**：把作用域去掉改成裸 `.kiosk-rail`，再跑屏 02/03/04 的四图 —— 拇指应当移位。不移位说明那条闸没量到东西。

```css
.aisheet {
  position: absolute; inset: 44px 0 48px; z-index: 20;
  display: flex; flex-direction: column; gap: 8px;
  padding: 12px; border-radius: 12px;
  background: var(--panel); border: 1px solid var(--hair);
}
.aisheet__head { display: flex; align-items: center; justify-content: space-between; }
.aisheet__body { flex: 1; min-height: 0; overflow-y: auto; }
.aisheet__row > button {
  display: flex; align-items: center; gap: 10px; width: 100%;
  min-height: 44px; padding: 0 10px; border: 0; border-radius: 8px;
  background: transparent; color: var(--text); text-align: left; cursor: pointer;
}
.aisheet__row > button[aria-current="true"] {
  background: color-mix(in srgb, var(--accent) 16%, transparent);
}
.aisheet__row .idx { width: 26px; color: var(--dim); font-size: 12px; }
.aisheet__row .nm  { flex: 1; font-size: 14px; }
.aisheet__row .el  { color: var(--dim); font-size: 12px; white-space: nowrap; }
```

- [ ] **Step 5: 跑测试确认绿**

Run: `cd katrain/web/ui && npx vitest run src/kiosk/components/setup/AiLevelSheet.test.tsx`
Expected: 4 passed

- [ ] **Step 6: 补 i18n key 并跑闸**

新增：`platform:level_sheet`、`platform:close`。11 语种，做法同 Task 1 Step 6–7。

- [ ] **Step 7: 提交**

```bash
git add katrain/web/ui/src/kiosk/components/setup/AiLevelSheet.tsx \
        katrain/web/ui/src/kiosk/components/setup/AiLevelSheet.test.tsx \
        katrain/web/ui/src/kiosk-shell/go-screens.css \
        katrain/i18n/locales/*/LC_MESSAGES/katrain.po
git commit -m "$(cat <<'EOF'
feat(kiosk-go): 39 档全表面板 —— 轨跨不到远处的那条路

2026-08-24 裁定禁的是两套选择控件同屏并存;这一层点开即用、选完即关,
任一时刻屏上只有一种手势。只盖右栏不盖盘 —— 左边那块盘是调让子时唯一的反馈。
0 档时说明白是平台没给,不画空列表(空列表和「这儿本来就没有」长得一样)。

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
EOF
)"
```

## Task 3: 屏 09 重排 —— 五段压成三段

**Files:**
- Modify: `katrain/web/ui/src/kiosk/pages/PlatformEngineSetupPage.tsx`
- Modify: `katrain/web/ui/src/kiosk/shell/KioskStepTrack.tsx`（加 `readout` 开关）
- Modify: `katrain/web/ui/src/kiosk/pages/PlatformEngineSetupPage.test.tsx`
- Modify: `katrain/web/ui/src/kiosk-shell/go-screens.css`（`.twocol` / `.tcol`）

**Interfaces:**
- Consumes: `AiOpponentPlate`（Task 1）、`AiLevelSheet`（Task 2）
- Produces: 三段版面，右栏内容高度在最坏内容量下 ≤ 400px

版面对照（稿子 `data-screen="platform-engine"`）：

| 段 | 内容 | 约高 |
|---|---|---|
| 怎么落子 | 组标题（secval「开局后不可改」）+ 落子分段 + **一行提示**「星阵人机固定 19 路 · 中国规则，屏幕和实体盘走同一条隧道」 | 120 |
| 对手 | 组标题（secval「星阵下发 39 档」）+ 名牌 56 + 轨 44（**无读数行**） | 128 |
| 让子 · 我执 | 组标题（secval「让 2 子 · 黑贴 2 目」= 算出来的）+ 两列（让子轨 / 我执分段） | 90 |

撤掉的两样：**路数那一行 igrow**（降成提示行里的半句）、**整个「这一局会是」段**（贴目进组标题 secval，规则/路数/不计时进提示行，「胜负只进星阵那边的账」页控条副标已经在说）。

- [ ] **Step 1: 给 KioskStepTrack 加 `readout` 开关，先写失败测试**

在 `katrain/web/ui/src/kiosk/shell/KioskStepTrack.test.tsx`（没有就建）里加：

```tsx
it('readout={false} 时不画读数行 —— 屏 09 把读数搬进了名牌', () => {
  render(<KioskStepTrack
    count={39} index={0} onChange={() => {}}
    value="星猛虎 · 9 段" meta="第 1 / 39 档"
    readout={false}
    decLabel="弱一档" incLabel="强一档" testId="trk"
  />);
  expect(screen.queryByText('第 1 / 39 档')).toBeNull();
});
```

- [ ] **Step 2: 跑它确认它红**

Run: `cd katrain/web/ui && npx vitest run src/kiosk/shell/KioskStepTrack.test.tsx`
Expected: FAIL（`readout` 不是合法 prop / 读数还在）

- [ ] **Step 3: 改 KioskStepTrack**

interface 加一行，默认 `true` 保持既有三个调用点行为不变：

```ts
  /**
   * 要不要画读数那一行（`value` / `meta`）。默认画。
   * 屏 09 把读数搬进了「对手名牌」，那里再画一遍就是同一件事说两遍。
   */
  readout?: boolean;
```
渲染处包一层 `{readout !== false && (...)}`。

- [ ] **Step 4: 回看所有调用点**

```bash
grep -rln "KioskStepTrack" katrain/web/ui/src --include="*.tsx" --include="*.ts" | grep -v "\.test\."
```
已经替你查过（2026-09-23）：非测试消费者**只有两个** —— `pages/PlatformEngineSetupPage.tsx`（本屏）和 **`pages/TutorialSectionPage.tsx`**。
⚠️ **`AiSetupPage.tsx` 没有 import 它**——早先的调研说它用了，那是错的，别去那儿找。

逐个确认没传 `readout` ⇒ 行为不变，并**把 `TutorialSectionPage` 的测试跑一遍**。**这是共享件，改完不回看就是把风险留给别的屏。**

- [ ] **Step 5: 跑测试确认绿**

Run: `cd katrain/web/ui && npx vitest run src/kiosk/shell/KioskStepTrack.test.tsx src/kiosk/pages/AiSetupPage.test.tsx`
Expected: 全绿

- [ ] **Step 6: 改 PlatformEngineSetupPage —— 段一**

把「路数」那个 `igrow` 整块删掉，提示行改成无条件渲染：

```tsx
            {/* 路数不是控件也不占一行:星阵只开 19 路。这句提示同时替掉了原来
                「这一局会是」段里的规则/路数两项 —— 400px 视口装不下第五段。 */}
            <p className="kiosk-opthint" data-testid="setup-input-hint">
              {playInput.available
                ? interpolate(
                    t('platform:engine_fixed_hint', '{name}人机固定 19 路 · 中国规则，屏幕和实体盘走同一条隧道'),
                    { name: t(meta.label, meta.labelCn) },
                  )
                : t('setup:no_camera_hint', '这台盒子还没标定摄像头，实体盘这条路现在走不了')}
            </p>
```

- [ ] **Step 7: 改段二 —— 接名牌与面板**

组件顶部加状态：

```tsx
  const [sheetOpen, setSheetOpen] = useState(false);
```

`setup-opponent` 那一段的正常分支（`levelsError === null && !levelsLoading`）改成：

```tsx
              <>
                <KioskSecLabel
                  zh={t('platform:opponent', '对手')}
                  en="Opponent"
                  value={interpolate(
                    t('platform:levels_from', '{name}下发 {n} 档'),
                    { name: t(meta.label, meta.labelCn), n: sorted.length },
                  )}
                />
                {current && (
                  <AiOpponentPlate
                    name={current.name}
                    levelName={current.level_name}
                    displayElo={current.display_elo}
                    refRank={current.ref_rank || undefined}
                    index={Math.max(0, currentIdx)}
                    total={sorted.length}
                    onOpen={() => setSheetOpen(true)}
                    testId="setup-opponent-plate"
                  />
                )}
                <KioskStepTrack
                  count={sorted.length}
                  index={Math.max(0, currentIdx)}
                  onChange={(i) => setLevel(sorted[i].elo_score)}
                  value=""
                  readout={false}
                  decLabel={t('platform:weaker', '换弱一档的对手')}
                  incLabel={t('platform:stronger', '换强一档的对手')}
                  testId="setup-level"
                />
              </>
```

面板挂在 `.kiosk-rail` 里、`KioskScrollZone` 外（它是覆盖层不是内容）：

```tsx
        {sheetOpen && (
          <AiLevelSheet
            levels={sorted}
            currentElo={level}
            onPick={setLevel}
            onClose={() => setSheetOpen(false)}
            testId="setup-level-sheet"
          />
        )}
```
给 `.kiosk-rail` 加 `position: relative`（在 `go-screens.css` 里，**只在这一屏的作用域下**：`[data-testid="platform-engine-setup-page"] .kiosk-rail { position: relative; }`，避免污染别的屏）。

- [ ] **Step 8: 改段三 —— 让子与我执并成两列**

删掉原来的 `setup-handicap`、`setup-side`、`setup-summary` 三段，换成一段：

```tsx
          {/* ── 让子 · 我执 ── 贴目跟着让子算,写在组标题右端,不再单占一段 ── */}
          <section className="setgrp" data-testid="setup-handicap-side">
            <KioskSecLabel
              zh={t('setup:handicap_side', '让子 · 我执')}
              en="Handicap"
              value={<>{handicapLabel} · {komiLabel}</>}
            />
            <div className="twocol">
              <div className="tcol">
                <span className="iglab">{t('setup:handicap', '让子')}</span>
                <KioskStepTrack
                  count={HANDICAP_TRACK.length}
                  index={handicapIdx}
                  onChange={setHandicapIdx}
                  value=""
                  readout={false}
                  decLabel={t('setup:handicap_less', '少让一子')}
                  incLabel={t('setup:handicap_more', '多让一子')}
                  testId="setup-handicap-track"
                />
              </div>
              <div className="tcol">
                <span className="iglab">{t('setup:my_side', '我执')}</span>
                <KioskOptSeg
                  ariaLabel={t('setup:my_side', '我执')}
                  testId="setup-side-seg"
                  value={humanColor}
                  onChange={setHumanColor}
                  options={[
                    { value: 'nigiri', label: <><span className="disc rnd" />{t('platform:nigiri', '猜先')}</> },
                    { value: 'B', label: <><span className="disc b" />{t('setup:take_black', '执黑')}</> },
                    { value: 'W', label: <><span className="disc w" />{t('setup:take_white', '执白')}</> },
                  ]}
                />
              </div>
            </div>
          </section>
```

- [ ] **Step 9: 两列的样式**

```css
/* 标签要离自己的控件近、离邻列的控件远。2026-09-23 量过一次反例:
   列间距 16 时,标签到邻列的 ＋ 号只有 16px、到自己的控件 8px —— 差距不够,
   眼睛会把标签配给邻列。列间距拉到 26、标签下边距 30 才拉开。 */
.twocol { display: grid; grid-template-columns: 1fr 1fr; gap: 26px; }
.tcol { display: flex; flex-direction: column; gap: 6px; min-width: 0; }
.tcol .iglab { font-size: 12px; color: var(--dim); }
```

- [ ] **Step 10: 补 Review Focus #1 的测试（0 档）**

在 `PlatformEngineSetupPage.test.tsx` 里加：

```tsx
it('平台一档都没下发时,开始键按不下去,也不画名牌', async () => {
  vi.mocked(API.platformEngineLevels).mockResolvedValue({ levels: [] });
  renderPage();
  await screen.findByTestId('platform-engine-start');
  expect(screen.getByTestId('platform-engine-start')).toBeDisabled();
  expect(screen.queryByTestId('setup-opponent-plate')).toBeNull();
});
```

- [ ] **Step 11: 补 Review Focus #4 的测试（面板开着时落子事件）**

```tsx
it('全表面板开着时,视觉同步事件照样到得了页面', async () => {
  renderPage();
  await userEvent.click(await screen.findByTestId('setup-opponent-plate'));
  expect(screen.getByTestId('setup-level-sheet')).toBeInTheDocument();
  // 真派一次事件,而不是「看看面板在不在」。
  act(() => { visionBus.emit({ type: 'pose_lost' }); });
  // 摄像头掉了 ⇒ 落子那一格的「实体盘」要变成不可选,哪怕面板正开着。
  await waitFor(() => {
    expect(screen.getByRole('button', { name: /实体盘/ })).toBeDisabled();
  });
});
```
> **不要写 `expect(...).not.toBeVisible()` 去断言「面板盖住了轨」。** jsdom 只看 `display`/`visibility`/`hidden`，看不出 `z-index` 覆盖——那条断言按本计划的实现**必然失败**，而且即使它绿了也证明不了覆盖。「盖没盖住」是布局结论，**归 Task 4 的真浏览器几何闸**，jsdom 对布局事实无权作证。
>
> 上面这条测试断言的是**事件到没到**（一个纯状态问题），那是 jsdom 答得了的。`visionBus` 的真实名字照 `src/kiosk/context/VisionContext` 里的 mock 写法取，先读 `GamePage.test.tsx` 里现成的那一套。

- [ ] **Step 12: 跑全部相关单测**

Run: `cd katrain/web/ui && npx vitest run src/kiosk/pages/PlatformEngineSetupPage.test.tsx src/kiosk/shell/KioskStepTrack.test.tsx`
Expected: 全绿

- [ ] **Step 13: 补 i18n key 并跑闸**

新增：`platform:engine_fixed_hint`、`setup:handicap_side`。11 语种。跑 `uv run pytest tests/web_ui/test_kiosk_i18n.py -q && uv run python i18n.py -todo`。

- [ ] **Step 14: 提交**

```bash
git add -A katrain/web/ui/src/kiosk katrain/i18n/locales
git commit -m "$(cat <<'EOF'
feat(kiosk-go): 屏 09 五段压成三段 —— 一屏放得下,不用滚轮

Fan 2026-09-23:「对局设置页要和自由对弈一致,所有右栏内容在一页内展示出来」。
撤掉两样:路数那一行(降成提示行里的半句)、整个「这一局会是」段(贴目进组标题 secval,
规则/路数/不计时进提示行)。让子与我执并成两列,列间距 26 —— 16 时标签离邻列的 ＋
只有 16px 而离自己的控件 8px,眼睛会配错。

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
EOF
)"
```

## Task 4: 屏 09 的视觉关卡与承重实测

> **这一步是 vertical-slice 第 3 步，两项都过了才请 Fan 确认，确认之前不得进后端/下一切片。**

**Files:**
- Create: `katrain/web/ui/tests/kiosk-screen-09-setup.fourup.spec.ts`
- Create: `katrain/web/ui/tests/kiosk-geometry-platform.spec.ts`
- Modify: `katrain/web/ui/tests/kiosk-screen-07-09-platform.fourup.spec.ts`（把 09 那条搬走）

**承重触发判断（反查）：** 把这次改动撤回去，右栏内容的高度来源会不会变？**会**——删了两段、加了一个 `position:absolute` 的覆盖层、给 `.kiosk-rail` 加了 `position:relative`。⇒ **触发，必须量。**

**要量的清单**（先写死关系式，再读数；具体像素只记录不作判据）：

| 量什么 | 关系式期望 |
|---|---|
| 该滚的是谁 | `.kiosk-side__scroll`（`KioskScrollZone` 内层），不是它的任何祖先 |
| 最坏内容量下不溢出 | 39 档 + 最长档名 + 摄像头不可用（多一行提示）时，该元素 `scrollHeight <= clientHeight` |
| 视口没被撑破 | `.kiosk-rail` 的 `clientHeight` 恒 516；内容区 `clientHeight` 恒 400 |
| 覆盖层真的盖住 | 面板打开后，在轨的中心点做 `elementFromPoint`，命中的必须是面板子树里的元素 |
| 覆盖层不盖盘 | 面板 border box 完整落在 `.kiosk-rail` 的裁切框内，与 `.kiosk-board` 无交集 |
| 面板自己能滚 | 39 档时面板 body `scrollHeight > clientHeight`；派发一次**真实触摸**拖动，`scrollTop` 变化不为 0 |
| **滚动条拇指没被 `position:relative` 挪走** | 不溢出时 `bar.style.display === 'none'`（`syncScrollbar` 早返回那一支）；溢出时拇指顶边与滚动区顶边之差 < 1px。**理由见 Task 2 那段警告**：`scrollSync.ts:38` 读 `scroll.offsetTop`，而 `offsetTop` 随 `offsetParent` 变 |

- [ ] **Step 1: 写几何闸**

```ts
// katrain/web/ui/tests/kiosk-geometry-platform.spec.ts
import { expect, test, type Page } from '@playwright/test';
import { freezeClock, KIOSK_VIEWPORT, stubBackendStatics } from './helpers/fourup';

test.use({ viewport: KIOSK_VIEWPORT });

/**
 * 屏 09 的承重链 —— 右栏 516 = 页控条 44 + 12 + 内容 400 + 12 + 主按钮 48。
 *
 * 这条闸量的是**交互之后**对不对,四图对比看的是静止一帧对不对,互不替代。
 * 「能不能滚」永远归这一关。
 *
 * ⚠️ 造数据要造到**最坏**:39 档 + 最长档名 + 摄像头不可用(多一行提示)。
 * 装得下的数据量下量出来的数字一概不算。
 */

/** 比真实最长的档名还长,守边界。真实最长的在 GOLAXY_AI_LEVELS 里,先 grep 出来对一下。 */
const LONGEST = '星阵超级究极加强版机器人';

const LEVELS = {
  levels: Array.from({ length: 39 }, (_, i) => ({
    elo_score: 100 + i * 10, level_name: `第 ${i + 1} 档`, name: LONGEST,
    goal_difference: 0, timing: '', display_elo: 400 + i * 50, ref_rank: '职业 / 野狐 9D+',
  })),
};

/** 完整 boot —— 不许留「同 fourup spec」这种占位:占位会让下一个人自己编一套,两处量的不是同一个页面。 */
async function boot(page: Page, opts: { camera: boolean }) {
  await freezeClock(page);
  await page.addInitScript(() => {
    localStorage.setItem('token', 'geom');
    localStorage.setItem('katrain_language', 'cn');
  });
  await stubBackendStatics(page);
  await page.route('**/api/v1/auth/me', (r) => r.fulfill({ json: { id: 1, username: '访客', rank: '20k', credits: 0 } }));
  await page.route('**/api/v1/platforms/status', (r) => r.fulfill({
    json: { platforms: [{ platform: 'golaxy', connected: true, saved_username: 'fan',
      supports_live_play: true, supports_automatch: false, supports_rooms: true,
      supports_seek_graph: false, supports_engine_play: true }] },
  }));
  await page.route('**/api/v1/platforms/golaxy/engine/levels', (r) => r.fulfill({ json: LEVELS }));
  await page.route('**/api/v1/vision/status', (r) => r.fulfill({
    json: { enabled: opts.camera, camera_connected: opts.camera, pose_locked: opts.camera,
      sync_state: 'idle', bound_session_id: null, recognition_ready: opts.camera, led_connected: opts.camera },
  }));
  await page.goto('/kiosk/play/cross-platform/engine/golaxy');
  await page.waitForSelector('[data-testid="platform-engine-start"]');
  await page.waitForLoadState('networkidle');
}

test('屏 09 最坏内容量下,整条链上没有任何一层在滚', async ({ page }) => {
  // 摄像头不可用 ⇒ 多一行提示,这是内容最多的那一态。
  await boot(page, { camera: false });

  const m = await page.evaluate(() => {
    const scroll = document.querySelector('.kiosk-side__scroll') as HTMLElement;
    // 从滚动容器一路往上数到 .kiosk-screen —— 同一条链上可以有不止一处断点,
    // 只量最里面那一层,外面某一层在滚照样绿。
    const chain: { sel: string; sh: number; ch: number }[] = [];
    let el: HTMLElement | null = scroll;
    while (el && !el.classList.contains('kiosk-screen')) {
      chain.push({
        sel: el.className || el.tagName,
        sh: el.scrollHeight, ch: el.clientHeight,
      });
      el = el.parentElement;
    }
    const rail = document.querySelector('.kiosk-rail') as HTMLElement;
    return { chain, railH: rail.clientHeight, viewportH: scroll.clientHeight };
  });
  console.log('[geom 09 chain]', JSON.stringify(m, null, 1));

  expect(m.railH).toBe(516);          // tokens.css:69 --content-h-l2
  expect(m.viewportH).toBe(400);      // 516 − 44 页控条 − 12 − 12 − 48 主按钮
  for (const n of m.chain) {
    expect(n.sh, `${n.sel} 在滚`).toBeLessThanOrEqual(n.ch);
  }
});

test('39 档面板:完整落在右栏内、与棋盘无交集、轨的四角都被盖住、手指拨得动', async ({ page }) => {
  await boot(page, { camera: true });
  await page.click('[data-testid="setup-opponent-plate"]');
  const sheet = page.locator('[data-testid="setup-level-sheet"]');
  await expect(sheet).toBeVisible();

  const box = await page.evaluate(() => {
    const s = document.querySelector('[data-testid="setup-level-sheet"]')!.getBoundingClientRect();
    const rail = document.querySelector('.kiosk-rail')!.getBoundingClientRect();
    const b = document.querySelector('.kiosk-board')!.getBoundingClientRect();
    const trk = document.querySelector('[data-testid="setup-level"]')!.getBoundingClientRect();
    const sheetEl = document.querySelector('[data-testid="setup-level-sheet"]')!;
    // 轨的四角 + 中心,五个点都要命中面板 —— 只测中心一个点,局部露出照样绿。
    const pts: [number, number][] = [
      [trk.left + 2, trk.top + 2], [trk.right - 2, trk.top + 2],
      [trk.left + 2, trk.bottom - 2], [trk.right - 2, trk.bottom - 2],
      [trk.left + trk.width / 2, trk.top + trk.height / 2],
    ];
    return {
      // 完整包含于 rail(四条边都要,不能只比 left)
      inRail: s.left >= rail.left && s.right <= rail.right && s.top >= rail.top && s.bottom <= rail.bottom,
      // 与棋盘矩形无交集(两轴都判,只比 left/right 挡不住纵向压到盘上的情形)
      noOverlapBoard: !(s.left < b.right && s.right > b.left && s.top < b.bottom && s.bottom > b.top),
      hits: pts.map(([x, y]) => sheetEl.contains(document.elementFromPoint(x, y))),
    };
  });
  console.log('[geom sheet]', JSON.stringify(box));
  expect(box.inRail).toBe(true);
  expect(box.noOverlapBoard).toBe(true);
  expect(box.hits).toEqual([true, true, true, true, true]);

  // 能滚 + **手指**拨得动。鼠标滚轮拨得动 ≠ 触屏拨得动。
  const body = sheet.locator('.aisheet__body');
  const overflow = await body.evaluate((el) => { el.scrollTop = 0; return el.scrollHeight - el.clientHeight; });
  expect(overflow, '39 档没撑出溢出 ⇒ 这条闸量的不是滚动').toBeGreaterThan(0);

  // ⚠️ **不能用 page.evaluate 里 dispatchEvent 合成的 TouchEvent。**
  //    脚本造的事件是 untrusted,**不驱动 Chromium 的原生触摸滚动** ——
  //    实现完全正确时 scrollTop 照样是 0,这条会永久假红。
  //    `page.touchscreen` 在本仓这版 Playwright 里只有 tap(),没有 swipe。
  //    真正的手指拖动只能走 CDP。
  const r = (await body.boundingBox())!;
  const cx = Math.round(r.x + r.width / 2);
  const cdp = await page.context().newCDPSession(page);
  const pt = (y: number) => [{ x: cx, y: Math.round(y), radiusX: 8, radiusY: 8, force: 1 }];
  await cdp.send('Input.dispatchTouchEvent', { type: 'touchStart', touchPoints: pt(r.y + r.height - 20) });
  for (const y of [r.y + r.height - 80, r.y + r.height - 160, r.y + 20]) {
    await cdp.send('Input.dispatchTouchEvent', { type: 'touchMove', touchPoints: pt(y) });
  }
  await cdp.send('Input.dispatchTouchEvent', { type: 'touchEnd', touchPoints: [] });
  await page.waitForTimeout(150);            // 触摸滚动由浏览器自己做,给它几帧

  const after = await body.evaluate((el) => el.scrollTop);
  console.log('[geom sheet scrollTop after swipe]', after);
  expect(after, '手指拨不动').toBeGreaterThan(0);
});
```
> **要在这个 spec 里 `test.use({ hasTouch: true })`**（先看 `playwright.config.ts` 里 kiosk 那个 project 有没有开），否则页面根本不认为自己在触屏设备上。
>
> **变异**：给 `.aisheet__body` 临时加 `touch-action: none`（或把 `overflow-y` 改成 `hidden`），这条必须红。不红说明 CDP 那串事件没真送到——**那时候是闸没做完，不是被测的东西对了**。

- [ ] **Step 2: 跑几何闸**

Run: `cd katrain/web/ui && npm run build && npx playwright test tests/kiosk-geometry-platform.spec.ts --reporter=line`
Expected: 全绿。**Playwright 打的是构建产物，改了源码不重建等于没改。**
把 `console.log` 打出来的数字抄进本任务的验收记录。

- [ ] **Step 3: 变异测试这条闸（两处）**

① 把 `AiLevelSheet` 的 `z-index: 20` 临时改成 `z-index: 0`，重建，重跑 —— 「盖住轨」那条**必须变红**。
② 把 `position: relative` 的作用域去掉，改成裸 `.kiosk-rail { position: relative }`，重建，**跑屏 02/03/04 的四图** —— 拇指应当移位。
两处都验完再改回去。不红说明闸量错了对象。

- [ ] **Step 4: 拆出屏 09 的四图 spec**

从 `kiosk-screen-07-09-platform.fourup.spec.ts` 里把第三条 test 整体搬到新文件 `kiosk-screen-09-setup.fourup.spec.ts`，参考图指向 `shots/09-platform-engine.png`。`implementationCaption` 要写清这一版改了什么、为什么（照既有那两条的风格，**把裁定和量出来的数写进去**）。

- [ ] **Step 5: 取四图**

Run: `cd katrain/web/ui && npx playwright test tests/kiosk-screen-09-setup.fourup.spec.ts --reporter=line`
产物落在 `superpowers/tracks/kiosk-go-shell-align/visual/07-09-platform/1024x600/09-platform-engine--{reference,implementation,side-by-side,diff}.png`。

- [ ] **Step 6: 自己先看一遍四图**

逐项对：构图 · 几何间距 · 组件层级 · 字体/色彩/材质 · 图标素材 · 文案 · 状态语义。
**特别看名牌上的字是不是白的**——闸不查字色。

- [ ] **Step 7: 请 Fan 确认**

把四张图和这两条一起交给他：
1. **39 档面板这个交互对不对**（Task 2 那条待裁定：如果他认为它也在「一屏一种手势」的禁令内，就退回成名牌不可点、去掉 caret）。
2. 几何闸量出来的数字。

**他确认之前不进下一个切片。**

- [ ] **Step 8: 提交**

```bash
git add katrain/web/ui/tests superpowers/tracks/kiosk-go-shell-align/visual
git commit -m "$(cat <<'EOF'
test(kiosk-go): 屏 09 四图 + 真浏览器几何闸

几何闸量的是交互之后对不对(面板盖不盖得住、盖不盖到盘、拨不拨得动),
四图看的是静止一帧对不对,互不替代。造的是最坏内容量:39 档 + 最长档名 +
摄像头不可用多一行提示 —— 装得下的数据量下量出来的数不作数。
变异实测:z-index 改 0 时「盖住轨」那条变红。

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
EOF
)"
```

---

# 切片 A：登录各自成页

**用户旅程：** 「我要把我的星阵号／OGS 号连到这台盒子上」。

Fan 2026-09-23 裁定：登录页太宽、下面挂「登录之后」逻辑不通 ⇒ **登录独立成页**，左栏 300 答「登录之前要知道的」，右栏定宽 520 放标签 + 表单。登录之后有什么，屏 07 / 08a 自己说。

分四个任务：**A0 平台连接按用户隔离（发布阻断项，必须先做）**、A1 密码/验证码（后端现成）、A2 扫码（后端要新写）、A3 OGS 用户名+密码。

## Task 4.5: 平台连接按用户隔离 —— 发布阻断项

> **为什么它在这里而不是「以后再说」。** 这是**既有缺陷**，不是这次改出来的。但切片 A 把「登录平台」从一个藏在三家并列页里的小表单，变成盒子上的一等公民流程——而盒子是**共用的**。放大一个已知的越权面，按 CLAUDE.md 的升级判据（鉴权 / 权限边界）就必须在同一片里补上。本计划原来的 Review Focus #3 只测了 SQLite 那一层，**而堵点按定义总在更外面**——到达性测试给断路发了通行证。

**Files:**
- Modify: `katrain/web/platforms/manager.py`
- Modify: `katrain/web/api/v1/endpoints/platforms.py`
- Create: `tests/platforms/test_platform_user_isolation.py`

**核过的事实（不要再查，直接用）：**
- `manager.py:34` `_adapters: dict[str, PlatformAdapter]` —— **一个平台全局只有一个 adapter**。
- `manager.py:37` `_platform_user_ids: dict[str, int]` 记了 owner，但**全仓只在两处被读写**：`:72` 写、`:377` 读。
- `manager.py:48-60` `list_platforms()` 直接把 `adapter.is_connected` 吐出去，**不看调用者是谁**。
- `manager.py:91` `disconnect_platform(self, platform)` —— **签名里根本没有 user_id**。
- `endpoints/platforms.py` 里每个端点都只有 `Depends(get_current_user)`，那是**认证**不是**授权**。

⇒ 用户 2 登录这台盒子后：在状态里看得见用户 1 的连接、能拿用户 1 的会话去调 users / challenge / engine、还能把用户 1 断开。

- [ ] **Step 1: 先写会红的集成测试（两个真用户走 API，不是只测 store）**

```python
# tests/platforms/test_platform_user_isolation.py
"""共用盒子换人:用户 2 看不到、动不了、断不掉用户 1 的平台连接。

## 为什么不测凭据表

凭据表 `PlatformCredentialStore` 本来就按 user_id 分行,单测它一定是绿的 ——
**堵点在更外面**:运行时的 adapter 是按平台全局一个,`list_platforms()` 不看调用者。
只测最里面那一层,等于给断掉的那一段发通行证。
"""
import pytest


@pytest.mark.asyncio
async def test_user2_does_not_see_user1_connection(client, user1_token, user2_token, connected_golaxy_for_user1):
    r1 = await client.get("/api/v1/platforms/status", headers={"Authorization": f"Bearer {user1_token}"})
    r2 = await client.get("/api/v1/platforms/status", headers={"Authorization": f"Bearer {user2_token}"})
    g1 = next(p for p in r1.json()["platforms"] if p["platform"] == "golaxy")
    g2 = next(p for p in r2.json()["platforms"] if p["platform"] == "golaxy")
    assert g1["connected"] is True
    assert g2["connected"] is False, "用户 2 看见了用户 1 的连接"
    assert "saved_username" not in g2 or not g2["saved_username"]


@pytest.mark.asyncio
async def test_user2_cannot_disconnect_user1(client, user1_token, user2_token, connected_golaxy_for_user1):
    r = await client.delete("/api/v1/platforms/golaxy/logout", headers={"Authorization": f"Bearer {user2_token}"})
    assert r.status_code in (403, 404), f"用户 2 把用户 1 断开了(HTTP {r.status_code})"
    r1 = await client.get("/api/v1/platforms/status", headers={"Authorization": f"Bearer {user1_token}"})
    assert next(p for p in r1.json()["platforms"] if p["platform"] == "golaxy")["connected"] is True


@pytest.mark.asyncio
@pytest.mark.parametrize("method,path", [
    ("GET", "/api/v1/platforms/golaxy/users"),
    ("GET", "/api/v1/platforms/golaxy/challenges"),
    ("GET", "/api/v1/platforms/golaxy/engine/items"),
    ("POST", "/api/v1/platforms/golaxy/engine/start"),
])
async def test_user2_cannot_act_through_user1_session(client, user2_token, connected_golaxy_for_user1, method, path):
    r = await client.request(method, path, headers={"Authorization": f"Bearer {user2_token}"}, json={})
    assert r.status_code in (403, 404), f"{method} {path} 让用户 2 用上了用户 1 的会话"


# ——— 下面三条是第 2 轮审核逼出来的。前三条**全都不让用户 2 去登录**,
#     而串写恰恰只在「用户 2 登录」这条路径上发生 —— 取样把会坏的那个东西排除掉了。

@pytest.mark.asyncio
async def test_user2_login_while_user1_connected_is_refused_before_touching_adapter(
    client, user2_token, connected_golaxy_for_user1, golaxy_adapter_spy,
):
    """异主登录要在**碰 adapter 之前**就被拒。

    拒得晚一点点(先 connect 再判)就来不及了:adapter 登录过程中会发 token_refreshed,
    那一刻 owner 还记着用户 1 ⇒ 用户 2 的新 token 落进用户 1 的凭据行。
    """
    r = await client.post("/api/v1/platforms/golaxy/login",
                          headers={"Authorization": f"Bearer {user2_token}"},
                          json={"username": "13900000000", "password": "x"})
    assert r.status_code == 409
    assert golaxy_adapter_spy.connect_calls == 0, "已经去连了 —— 拒得太晚"


@pytest.mark.asyncio
async def test_token_refresh_during_user2_login_never_writes_into_user1_row(
    client, credential_store, user1_id, user2_id, golaxy_adapter_emitting_token_refresh,
):
    """就算将来放开了换人,刷新出来的 token 也必须落在**发起这次连接**的人头上。"""
    before = credential_store.load_credentials(user1_id, "golaxy")
    ...  # 驱动用户 2 的连接(经明确的断开→再连流程)
    after = credential_store.load_credentials(user1_id, "golaxy")
    assert after.auth_data == before.auth_data, "用户 2 的 token 被写进了用户 1 那一行"


@pytest.mark.asyncio
async def test_callbacks_are_wired_once(manager, golaxy_adapter_spy, user1_id):
    """`_setup_callbacks` 原来每次连接都再挂一遍 ⇒ 回调累积 ⇒ 一次刷新写 N 遍。"""
    for _ in range(3):
        await manager.connect_platform("golaxy", creds(), user1_id)
    assert golaxy_adapter_spy.token_refreshed_handlers == 1


@pytest.mark.asyncio
async def test_box_user_logout_releases_the_platform(client, user1_token, user2_token, connected_golaxy_for_user1):
    """不清运行时归属的话:上一个人登出了,下一个人登录平台被 409 挡住,而屏上没有任何解释。"""
    await client.post("/api/v1/auth/logout", headers={"Authorization": f"Bearer {user1_token}"})
    r = await client.post("/api/v1/platforms/golaxy/login",
                          headers={"Authorization": f"Bearer {user2_token}"},
                          json={"username": "13900000000", "password": "x"})
    assert r.status_code != 409, "上一个人登出了,平台还占着"
```
> 409 的屏上文案要说清楚**怎么办**：「这台盒子上现在连着别人的星阵账号 · 去设置里断开后再登录」。光报一个错误码，用户只会反复点。

- [ ] **Step 2: 跑它，确认它红**

Run: `CI=true uv run pytest tests/platforms/test_platform_user_isolation.py -q`
Expected: **多条 FAIL**。一上来就全绿 ⇒ 夹具没真把用户 1 连上，回去修夹具——**不许改绿**。

- [ ] **Step 3: 定一个完整的单-owner 生命周期（不只是读的时候过滤）**

> ⚠️ **只在读的地方加过滤是不够的，而且会制造一条更坏的路径。** 核过的四行代码：
> - `manager.py:70-72`：`await adapter.connect(credentials)` **在前**，`self._platform_user_ids[platform] = user_id` **在后**。
> - `manager.py:376-377`：`_on_token_refreshed` 事后去 `self._platform_user_ids.get(platform)` 读 owner。
> - `manager.py:73`：`_setup_callbacks(adapter)` **每次连接都再挂一遍**，回调会累积。
> - `manager.py:91-95`：`disconnect_platform` **不清** `_platform_user_ids`。
>
> ⇒ 用户 1 连着的时候用户 2 去登录：adapter 登录**过程中**发出的 `token_refreshed`，此刻查到的 owner 还是用户 1，**用户 2 的新 token 会被写进用户 1 的凭据行**。这比「看得见别人连着」严重一个量级——那是读，这是写。

最小但完整的模型，五件事一起做：

```python
# manager.py
class PlatformManager:
    def __init__(self, ...):
        ...
        self._locks: dict[str, asyncio.Lock] = {}
        self._callbacks_wired: set[str] = set()

    def owner_of(self, platform: str) -> int | None:
        return self._platform_user_ids.get(platform)

    async def connect_platform(self, platform, credentials, user_id) -> bool:
        adapter = self._adapters.get(platform)
        if adapter is None:
            raise ValueError(f"Unknown platform: {platform}")
        lock = self._locks.setdefault(platform, asyncio.Lock())
        async with lock:                       # ① 按平台串行:并发登录不许交错
            owner = self._platform_user_ids.get(platform)
            # ② **在碰 adapter 之前**就拒绝异主登录。
            #    全局只有一个 adapter,盒子上同一时刻只有一个人在用;悄悄顶掉别人的
            #    会话,会让上一个人的对局在无提示下断线。要换人,先明确断开。
            if owner is not None and owner != user_id and adapter.is_connected:
                raise PlatformBusyError(platform, owner)   # 端点转 409
            # ③ 回调只挂一次,而且 token 的落账用户在**这次连接**时就钉死,
            #    不是事后去读一个会变的字典。
            if platform not in self._callbacks_wired:
                self._setup_callbacks(adapter)
                self._callbacks_wired.add(platform)
            self._pending_owner[platform] = user_id        # 供本次连接期间的回调使用
            try:
                success = await adapter.connect(credentials)
            finally:
                self._pending_owner.pop(platform, None)
            if success:
                self._platform_user_ids[platform] = user_id
                ... # 存凭据,原样
            return success

    async def disconnect_platform(self, platform: str, user_id: int) -> None:
        lock = self._locks.setdefault(platform, asyncio.Lock())
        async with lock:
            if self._platform_user_ids.get(platform) not in (None, user_id):
                raise PermissionError(platform)            # 端点转 403
            adapter = self._adapters.get(platform)
            if adapter and adapter.is_connected:
                await adapter.disconnect()
            self._platform_user_ids.pop(platform, None)    # ④ 清掉,否则下一个人撞 409

    async def release_user(self, user_id: int) -> None:
        """⑤ 盒端换人 / 登出时清运行时归属。

        不清的话:上一个人登出了,平台连接还挂着、owner 还记着他,
        下一个人登录平台会被 409 挡住,而屏上没有任何东西解释为什么。
        """
        for platform, owner in list(self._platform_user_ids.items()):
            if owner == user_id:
                await self.disconnect_platform(platform, user_id)

    async def _on_token_refreshed(self, platform: str, new_auth_data: dict) -> None:
        # 连接进行中用 pending,连接完成后用已定的 owner。**不再是「事后读一个会变的字典」**。
        user_id = self._pending_owner.get(platform) or self._platform_user_ids.get(platform)
        if user_id is None:
            logger.debug(...); return
        ...
```
`list_platforms(user_id)` 同时按 owner 过滤 `connected` 与 `saved_username`。

`release_user` 要挂到盒端登出/换人那条路径上——**先 grep 出那条路径在哪**：
```bash
grep -rn "logout\|active_generation\|def .*sign_out" katrain/web/api/v1/endpoints/auth.py katrain/web/core/ | head
```
挂不上就写清楚为什么挂不上，**不要装作挂上了**。

端点侧加一个依赖，每个**动作类**端点都过它一道：

```python
def require_platform_owner(platform: str, request: Request, user: User = Depends(get_current_user)):
    mgr = request.app.state.platform_manager
    if mgr.owner_of(platform) != user.id:
        raise HTTPException(status_code=403, detail="这台盒子上现在连的不是你的账号")
    return user
```

- [ ] **Step 4: 数一遍，别漏端点**

```bash
grep -n "^@router\.\(get\|post\|delete\|put\)" katrain/web/api/v1/endpoints/platforms.py
```
逐个分类：**登录类**（还没有 owner，不能过这道闸）/ **只读自己状态类**（`/status`，按 user_id 过滤即可）/ **动作类与读平台数据类**（全部过 `require_platform_owner`）。分类结果写进提交消息——漏掉一个就是漏掉一条越权路径。

> `engine_analysis` 在 `manager.py:258` 那段注释里写着「read-only, no ownership check」。**那条注释现在不成立了**：它读的是**别人会话里那局棋**的引擎分析。一起收进闸，并把注释改掉。

- [ ] **Step 5: 跑测试确认绿**

Run: `CI=true uv run pytest tests/platforms/ -q`

- [ ] **Step 6: 跑全量，和基线 `comm` 比**

```bash
CI=true uv run pytest tests --continue-on-collection-errors -q 2>&1 | grep '^FAILED\|^ERROR' | sort > /tmp/after-a0.txt
comm -13 /tmp/baseline-after.txt /tmp/after-a0.txt
```
Expected: 空。非空的每一条都要看——`list_platforms()` 改了签名，调用点可能不止一处。

- [ ] **Step 7: 提交**

```bash
git add katrain/web/platforms/manager.py katrain/web/api/v1/endpoints/platforms.py tests/platforms/test_platform_user_isolation.py
git commit -m "$(cat <<'EOF'
fix(platforms): 平台连接按用户隔离 —— 共用盒子上换个人就能用上一个人的账号

manager 里一个平台只有一个全局 adapter,list_platforms() 直接吐 adapter.is_connected
而不看调用者,disconnect_platform 签名里根本没有 user_id ⇒ 用户 2 看得见、
用得上、还能断开用户 1 的平台会话。端点只有 Depends(get_current_user),
那是认证不是授权。

补 require_platform_owner 到全部动作类与读平台数据类端点;/status 按 user_id 过滤。
engine_analysis 那句「read-only 不用查 owner」的注释一并改掉 ——
它读的是别人会话里那局棋。

测试用两个真用户走 API,不是只测凭据表:凭据表本来就按 user_id 分行,
堵点在更外面。

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
EOF
)"
```

## Task 5: 登录页骨架 + 星阵密码/验证码（后端现成）

**Files:**
- Create: `katrain/web/ui/src/kiosk/pages/PlatformLoginPage.tsx`
- Create: `katrain/web/ui/src/kiosk/pages/PlatformLoginPage.test.tsx`
- Create: `katrain/web/ui/src/kiosk/components/platform/PlatformLoginAside.tsx`
- Create: `katrain/web/ui/src/kiosk/constants/platformLoginFacts.ts`
- Modify: `katrain/web/ui/src/kiosk/KioskApp.tsx`（加路由）
- Modify: `katrain/web/ui/src/kiosk/pages/PlatformConnectPage.tsx`（撤页内登录段）
- Modify: `katrain/web/ui/src/kiosk-shell/go-screens.css`（`.xplogin` 一族）

**Interfaces:**
- Consumes: `API.platformLogin(platform, body, token)`、`API.platformSmsRequest(platform, phone, token)`（`katrain/web/api/v1/endpoints/platforms.py:190-263` 已有）
- Produces: 路由 `/kiosk/play/cross-platform/login/:platform`；组件 `PlatformLoginPage`

- [ ] **Step 1: 写文案 key 表**

```ts
// katrain/web/ui/src/kiosk/constants/platformLoginFacts.ts
/**
 * 登录页左栏那几条「登录之前要知道的」。
 *
 * **这里只放 key,中文在 `.po` 里** —— 闸 `test_kiosk_i18n.py` 认的是
 * `t('key','中文')` 这个调用形状,把中文摆在常量表里它看不见,于是这几段
 * 永远不会被翻译,在韩文界面上安静地显示中文。
 */
export interface LoginFact { titleKey: string; titleZh: string; bodyKey: string; bodyZh: string; }

export const LOGIN_FACTS: Record<string, LoginFact[]> = {
  golaxy: [
    { titleKey: 'platform:fact_whose', titleZh: '用谁的账号',
      bodyKey: 'platform:fact_whose_golaxy',
      bodyZh: '星阵自己的账号，不是智星盒的。没有就在手机上的星阵 APP 注册——盒上注册不了。' },
    { titleKey: 'platform:fact_three_ways', titleZh: '三种都能用',
      bodyKey: 'platform:fact_three_ways_body',
      bodyZh: '扫码一个字都不用打；验证码等一条短信；密码最快，但要在触屏上敲。' },
    { titleKey: 'platform:fact_stored', titleZh: '盒上留下什么',
      bodyKey: 'platform:fact_stored_golaxy',
      bodyZh: '只留星阵发的登录令牌，不留密码。想断开随时去设置里。' },
  ],
  ogs: [
    { titleKey: 'platform:fact_whose', titleZh: '用谁的账号',
      bodyKey: 'platform:fact_whose_ogs',
      bodyZh: 'online-go.com 的账号。注册要在浏览器里做，盒上做不了。' },
    { titleKey: 'platform:fact_only_one', titleZh: '盒上只做这一种',
      bodyKey: 'platform:fact_only_one_body',
      bodyZh: 'OGS 网页上还能用 Google、Apple 等账号；那条要跳浏览器，留给出海版。' },
    { titleKey: 'platform:fact_third_party', titleZh: '用第三方注册的',
      bodyKey: 'platform:fact_third_party_body',
      bodyZh: '那种账号没有 OGS 密码，得先去 OGS 网页上设一个。' },
    { titleKey: 'platform:fact_stored', titleZh: '盒上留下什么',
      bodyKey: 'platform:fact_stored_ogs',
      bodyZh: '只留登录后的会话，不留密码。想断开随时去设置里。' },
  ],
};
```
> ⚠️ 上面这张表里的 `titleZh`/`bodyZh` 是给组件当 `t()` 第二个参数用的。组件里必须写成 `t(f.titleKey, f.titleZh)` —— **但闸的正则只认字面量**，变量形式它看不见。所以**这几条 key 要在 Step 6 手工补进 `.po` 并在闸里加一条白名单式的显式断言**（见 Step 6），不能指望闸自动发现。

- [ ] **Step 2: 写失败测试**

```tsx
// katrain/web/ui/src/kiosk/pages/PlatformLoginPage.test.tsx 摘要
it('星阵登录页有三个标签,密码是其中之一', async () => { /* 扫码/验证码/密码 */ });
it('提交密码走 API.platformLogin,成功后跳到一条真渲染得出来的路由', async () => {
  // ⚠️ 切片 A 里跳 /kiosk/play/cross-platform/engine/golaxy(今天就存在)。
  //    **不要跳 /kiosk/play/cross-platform/golaxy** —— 那条路由 Task 9 才建,
  //    切片 A 自己的完成定义会全绿,而用户登录完落在 404。Task 10 再把它切过去。
});
it('登录失败时把平台给的话原样显示,不换成自己编的', async () => {});
it('OGS 登录页只有用户名+密码,没有标签栏', async () => {});
it('左栏那几条 fact 按平台换', async () => {});

// 用**真 Router**渲染,断言跳过去那条路由确实渲染得出来 ——
// mock 掉 navigate 只能证明「我调了这个字符串」,证明不了那头有东西。
it('登录成功后的目标路由在当前这一版里真的存在', async () => {
  render(
    <MemoryRouter initialEntries={['/kiosk/play/cross-platform/login/golaxy']}>
      <KioskRoutes />
    </MemoryRouter>,
  );
  await userEvent.click(await screen.findByRole('button', { name: /登录星阵/ }));
  expect(await screen.findByTestId('platform-engine-setup-page')).toBeInTheDocument();
});
```
（其余照 `PlatformConnectPage.test.tsx` 的 mock 风格写。）

- [ ] **Step 3: 跑它确认它红**

Run: `cd katrain/web/ui && npx vitest run src/kiosk/pages/PlatformLoginPage.test.tsx`
Expected: FAIL

- [ ] **Step 4: 写页面**

结构照稿子 `data-screen="platform-login-pw"`：

```
<div className="xp">
  <KioskPagebar back="返回对弈" title={平台名} sub={未连接 · 用…登录} />
  <section className="setgrp inputgrp xplogin">
    <PlatformLoginAside platform={platform} />
    <div className="xplogin__main"><div className="xpcol">
      <KioskSecLabel zh="登录星阵" en="Sign in" value={…} />
      {tabs.length > 1 && <KioskOptSeg className="xptabs" …/>}
      …字段…
      <div className="igrow"><span className="iglab" />
        <button className="kiosk-btn kiosk-btn--primary xpgo">登录{平台}</button></div>
    </div></div>
  </section>
</div>
```
要点：
- 标签集合按平台推导：`golaxy` → 扫码/验证码/密码；`ogs` → 只有密码一种，**此时整条标签栏不渲染**（一个选项的分段控件是假的选择）。
- 「登录」按钮放在一个 `.igrow` 里、配一个**空的** `.iglab`，这样它和上面的字段左边缘对齐。
- 字段用既有的「点此输入」药丸（判例：屏 04）——**真页面上它必须真能输入**，不做「点药丸弹一层」。
- **软键盘避让必须一起搬过来。** `PlatformConnectPage.tsx:114/131` 里有一段现成的逻辑：盒上的软键盘是挂在 `body` 上的 `.skbd`，**在缩放画布之外**，所以聚焦时要按缩放比例给滚动区加 padding，字段才不会被盖住。把它从 `PlatformConnectPage` 里**提成一个共享 hook**（`src/kiosk/hooks/useKeyboardInset.ts`），登录页和原页都用它。
  > 不搬的后果：表单换了页就没有避让，真机上点最下面那个字段，键盘正好盖住它。**而缩小 viewport 复现不出来**——`.skbd` 是 overlay，不改变 viewport 高度。

- [ ] **Step 4b: 软键盘的真浏览器实测**

这是承重（裁切边界随聚焦改变），归几何闸不归四图：

```ts
test('登录页:聚焦最下面那个字段时,它没有被软键盘盖住,提交键仍够得到', async ({ page }) => {
  await bootLogin(page, 'golaxy');
  // 真挂一个固定高度的 .skbd,而不是把 viewport 改矮 —— 键盘是 overlay,不改 viewport。
  await page.evaluate(() => {
    const kb = document.createElement('div');
    kb.className = 'skbd';
    Object.assign(kb.style, { position: 'fixed', left: '0', right: '0', bottom: '0', height: '260px', zIndex: '999' });
    document.body.appendChild(kb);
  });
  const field = page.locator('[data-testid="login-field-password"]');
  await field.click();
  await page.waitForTimeout(150);
  const ok = await page.evaluate(() => {
    const kb = document.querySelector('.skbd')!.getBoundingClientRect();
    const f = document.querySelector('[data-testid="login-field-password"]')!.getBoundingClientRect();
    const go = document.querySelector('.xpgo')!.getBoundingClientRect();
    return { fieldClear: f.bottom <= kb.top, goClear: go.bottom <= kb.top, f: f.bottom, kb: kb.top, go: go.bottom };
  });
  console.log('[geom login keyboard]', JSON.stringify(ok));
  expect(ok.fieldClear, '字段被键盘盖住').toBe(true);
  expect(ok.goClear, '提交键被键盘盖住').toBe(true);
});
```
**变异：** 把 hook 的 padding 计算临时改成恒 0，这两条必须红。

- [ ] **Step 5: 写左栏与样式**

`PlatformLoginAside.tsx` 读 `LOGIN_FACTS[platform]`，渲染 `.xpwho` + `.xpfacts`。样式照稿子（`.xplogin` 分栏、aside 定宽 300、main 里 `.xpcol` 定宽 520）。

- [ ] **Step 6: 补 i18n key + 给闸补一条显式断言**

把 `platformLoginFacts.ts` 里全部 key 写进 11 份 `.po`。然后在 `tests/web_ui/test_kiosk_i18n.py` 里加一条：

```python
def test_login_facts_keys_are_translated():
    """`platformLoginFacts.ts` 里的 key 是**变量**传给 `t()` 的，闸的正则看不见它们。

    看不见 ⇒ 少翻一条不会红 ⇒ 韩文界面上那一段安静地显示中文。
    所以这张表要单独点名。表变了这条会红，那是对的：提醒把新 key 也补进 .po。
    """
    src = (UI / "constants" / "platformLoginFacts.ts").read_text(encoding="utf-8")
    keys = sorted(set(re.findall(r"Key:\s*'([^']+)'", src)))
    assert len(keys) >= 12, f"只扫到 {len(keys)} 个 key,正则和表对不上了"
    for lang in LANGS:
        po = polib.pofile(str(REPO / "katrain" / "i18n" / "locales" / lang / "LC_MESSAGES" / "katrain.po"))
        have = {e.msgid: e for e in po}
        for k in keys:
            assert k in have, f"{lang}.po 缺 {k}"
            e = have[k]
            assert e.msgstr.strip(), f"{lang}.po 的 {k} 是空的"
            assert "TODO" not in (e.comment or ""), f"{lang}.po 的 {k} 被英文顶上了(TODO)"
```

- [ ] **Step 6b: 再加一条「屏上真的是译文」的组件测试**

上面那条**只证明目录里有条目**。组件若直接渲染 `f.titleZh`、或漏了某一条 `t(f.bodyKey, ...)`，它照样全绿——**存在性不是可用性**。所以还要一条在**非中文**翻译表下渲染、逐条断言屏上是译文而不是中文兜底的测试：

```tsx
// PlatformLoginAside.test.tsx
it('装着韩文表时,左栏每一条都是韩文,不是中文兜底', () => {
  // i18n 的实现是 this.translations[key] || defaultText || key(i18n.ts:52-54),
  // 所以喂一张韩文表进去,屏上还出现 titleZh/bodyZh 就说明那一条没走 t()。
  i18n.__setTranslationsForTest(Object.fromEntries(
    LOGIN_FACTS.golaxy.flatMap((f) => [[f.titleKey, `KO:${f.titleKey}`], [f.bodyKey, `KO:${f.bodyKey}`]]),
  ));
  render(<PlatformLoginAside platform="golaxy" />);
  for (const f of LOGIN_FACTS.golaxy) {
    expect(screen.getByText(`KO:${f.titleKey}`)).toBeInTheDocument();
    expect(screen.queryByText(f.titleZh)).toBeNull();   // ← 中文兜底不许出现
    expect(screen.getByText(`KO:${f.bodyKey}`)).toBeInTheDocument();
    expect(screen.queryByText(f.bodyZh)).toBeNull();
  }
});
```

- [ ] **Step 7: 变异测试这两条断言**

① 从 `cn.po` 里临时删掉 `platform:fact_whose_golaxy` ⇒ **目录那条必须红**。
② 把组件里某一条改成直接渲染 `f.titleZh` ⇒ **屏上那条必须红**。
两条都红了再改回来。**只做①不做②**，就正好漏掉这一族缺陷里更常见的那一半。

> **同形漏洞还有三处**（`SettingsPage` 的 `AUDIO_ROWS`、`MoveGradePanel` 的 `row.i18nKey`、`PLATFORM_META`）——全树正则同样看不见它们。**本切片不顺手去修**（不在本轮风险边界内），但要开一条非阻塞记录，建议之后把「动态 key 的来源表」统一成一份 manifest 交给闸扫，而不是每发现一处就写一条特例。

- [ ] **Step 8: 加路由，改 PlayPage 与 PlatformConnectPage**

`KioskApp.tsx`：
```tsx
<Route path="play/cross-platform/login/:platform" element={<PlatformLoginPage />} />
```
`PlayPage.tsx:150-154` 的 target 改成：
```tsx
const target = p.connected
  ? (p.supports_engine_play
      ? `/kiosk/play/cross-platform/${p.platform}`   // 星阵进自己的首页(切片 B 建)
      : `/kiosk/play/cross-platform/lobby?platform=${p.platform}`)
  : `/kiosk/play/cross-platform/login/${p.platform}`;  // ← 不再是三家并列的连接页
```
> ⚠️ 切片 B 之前 `/kiosk/play/cross-platform/golaxy` 还不存在。**这一步先只改「未连接」那一支**，已连接那一支保持原样，等 Task 10 再改。不然这里会指向一条 404 路由。

`PlatformConnectPage.tsx`：删掉 `platform-login-section` 整段，每行的「连接」改成跳那一家的登录页。

- [ ] **Step 9: 跑测试 + 两个构建**

```bash
cd katrain/web/ui
npx vitest run src/kiosk
npm run build && npm run build:kiosk-2d
```

- [ ] **Step 10: 提交**

## Task 6: 星阵扫码登录（后端新写）

**Files:**
- Create: `katrain/web/platforms/golaxy/scan_login.py`
- Create: `tests/web_ui/test_platform_scan_login.py`
- Modify: `katrain/web/platforms/golaxy/adapter.py`
- Modify: `katrain/web/api/v1/endpoints/platforms.py`
- Modify: `katrain/web/ui/src/api.ts`
- Create: `katrain/web/ui/src/kiosk/components/platform/GolaxyScanPanel.tsx`

**协议（稿子屏 07a 上方注释，2026-09-23 浏览器实测 + bundle 逐条核过）：**

| 步 | 请求 | 返回 |
|---|---|---|
| ① | `GET /api/auth/scan/code`（不需要登录态） | `{"code":"0","data":"<uuid>"}` |
| ② | 二维码内容 = 字符串 `golaxy_url&&&<uuid>` | **星阵没有「给我一张图」的接口，图在本地画** |
| ③ | 每秒 `GET /api/auth/scan/state?uuid=` | `0` 未扫 / `1` 扫描成功 / `2` 已确认 / `6016` 已失效 / `6019` 已取消 |
| ④ | 拿到 `2` → `POST /api/auth/oauth/token {uuid, grant_type:"scan_code"}` | 与短信登录同一端点 |
| ⑤ | `GET /api/auth/scan/username?uuid=` | 昵称；之后和短信登录走同一套存 token |

- [ ] **Step 1: 写后端失败测试**

```python
# tests/web_ui/test_platform_scan_login.py
"""星阵扫码登录五步链的契约。

**存在性不是可用性**:`/api/auth/scan/code` 返回 200 不等于我们拿到了 uuid ——
星阵的 code 字段是字符串 "0" 表示成功,非 "0" 的 200 一样是失败。
"""
import pytest
from katrain.web.platforms.golaxy.scan_login import GolaxyScanLogin, ScanState


@pytest.mark.asyncio
async def test_start_returns_uuid_and_payload(httpx_mock):
    httpx_mock.add_response(
        url=f"{GOLAXY_API_BASE}/api/auth/scan/code",
        json={"code": "0", "data": "abc-123"},
    )
    s = GolaxyScanLogin()
    r = await s.start()
    assert r.uuid == "abc-123"
    # 二维码里编的是这个字符串,不是一张图的 URL
    assert r.payload == "golaxy_url&&&abc-123"


@pytest.mark.asyncio
async def test_non_zero_code_is_a_failure_even_with_http_200(httpx_mock):
    httpx_mock.add_response(
        url=f"{GOLAXY_API_BASE}/api/auth/scan/code",
        json={"code": "5001", "msg": "服务忙"},
    )
    with pytest.raises(RuntimeError):
        await GolaxyScanLogin().start()


@pytest.mark.asyncio
@pytest.mark.parametrize("raw,expected", [
    (0, ScanState.WAITING), (1, ScanState.SCANNED), (2, ScanState.CONFIRMED),
    (6016, ScanState.EXPIRED), (6019, ScanState.CANCELLED),
])
async def test_poll_maps_every_documented_state(httpx_mock, raw, expected):
    httpx_mock.add_response(
        url=f"{GOLAXY_API_BASE}/api/auth/scan/state?uuid=abc-123",
        json={"code": "0", "data": raw},
    )
    assert await GolaxyScanLogin().poll("abc-123") == expected


@pytest.mark.asyncio
async def test_unknown_state_is_not_silently_treated_as_waiting(httpx_mock):
    """星阵加了一个新状态码时,我们必须能看出来。

    映射成 WAITING 会让用户对着一个永远转圈的二维码等下去 ——
    坏了和好着在用户那里长得一模一样。
    """
    httpx_mock.add_response(
        url=f"{GOLAXY_API_BASE}/api/auth/scan/state?uuid=abc-123",
        json={"code": "0", "data": 7777},
    )
    assert await GolaxyScanLogin().poll("abc-123") == ScanState.UNKNOWN
```

- [ ] **Step 2: 跑它确认它红**

Run: `uv run pytest tests/web_ui/test_platform_scan_login.py -q`
Expected: FAIL, `ModuleNotFoundError: katrain.web.platforms.golaxy.scan_login`

- [ ] **Step 3: 写 `scan_login.py`**

```python
"""星阵扫码登录 —— 五步链。

## 为什么二维码在本地画

星阵**没有**「给我一张二维码图片」的接口。`GET /api/auth/scan/code` 只给一个 uuid,
真正要编进码里的是字符串 `golaxy_url&&&<uuid>`。所以后端只负责 uuid 和状态,
画码是前端的事。

## 为什么状态要有 UNKNOWN 这一档

把没见过的码映射成「还在等」,会让用户对着一个永远不动的二维码等下去 ——
坏了和好着在用户那里长得一模一样。不认识就说不认识。
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

import httpx

from katrain.web.platforms.golaxy.adapter import GOLAXY_API_BASE   # adapter.py:69 = "https://api.19x19.com"

QR_PREFIX = "golaxy_url&&&"


class ScanState(str, Enum):
    WAITING = "waiting"      # 0
    SCANNED = "scanned"      # 1 手机扫到了,还没点确认
    CONFIRMED = "confirmed"  # 2 可以换 token 了
    EXPIRED = "expired"      # 6016
    CANCELLED = "cancelled"  # 6019
    UNKNOWN = "unknown"      # 星阵加了新码


_STATES = {
    0: ScanState.WAITING, 1: ScanState.SCANNED, 2: ScanState.CONFIRMED,
    6016: ScanState.EXPIRED, 6019: ScanState.CANCELLED,
}


@dataclass(frozen=True)
class ScanStart:
    uuid: str
    payload: str


class GolaxyScanLogin:
    def __init__(self, client: httpx.AsyncClient | None = None) -> None:
        self._client = client

    async def _get(self, path: str, **params) -> dict:
        # ⚠️ **注入进来的 client 不归我们关。** `async with` 一个共享的 AsyncClient
        # 会在第一次调用后把它关掉,后面每一次都 RuntimeError —— 而单测里每个用例
        # 各注一个新的,恰好看不出来。只有自己 new 的那个才由自己关。
        owned = self._client is None
        c = self._client or httpx.AsyncClient(timeout=10.0)
        try:
            r = await c.get(f"{GOLAXY_API_BASE}{path}", params=params or None)
            r.raise_for_status()
            body = r.json()
        finally:
            if owned:
                await c.aclose()
        # 200 不等于成功:星阵用字符串 code 报错。
        if str(body.get("code")) != "0":
            raise RuntimeError(body.get("msg") or f"星阵返回 code={body.get('code')}")
        return body

    async def start(self) -> ScanStart:
        body = await self._get("/api/auth/scan/code")
        uuid = str(body["data"])
        return ScanStart(uuid=uuid, payload=f"{QR_PREFIX}{uuid}")

    async def poll(self, uuid: str) -> ScanState:
        body = await self._get("/api/auth/scan/state", uuid=uuid)
        return _STATES.get(int(body["data"]), ScanState.UNKNOWN)

    async def username(self, uuid: str) -> str:
        body = await self._get("/api/auth/scan/username", uuid=uuid)
        return str(body["data"])
```
`confirm()`（第 ④ 步换 token）复用 `adapter.py` 里既有的 token 存储路径——**不要另写一份**，`grant_type` 换成 `"scan_code"`、参数换成 `uuid` 即可。先读 `adapter.py` 里短信登录那一段，照着它接；同一个 `GolaxyRestClient` 的客户端生命周期也照它。

- [ ] **Step 3b: 补一条走完全链的测试**

上面四条只测了单步。**「每一步单独对」推不出「连起来对」**——真正会咬人的是 confirmed 之后那三件事（换 token / 取昵称 / 按**当前 user_id** 存进凭据表）有没有串到别人身上。

```python
@pytest.mark.asyncio
async def test_full_chain_persists_under_the_calling_user(httpx_mock, credential_store):
    """start → poll(2) → token → username → 存进 **当前用户** 那一行。

    ⚠️ 这条要断言的是 `save_credentials` 拿到的 user_id 就是发起这次扫码的那个人。
    扫码这条链上 uuid 是唯一的串联物,而 uuid 不带身份 —— 身份只能来自我们这一侧的会话。
    """
    ...
    saved = credential_store.load_credentials(user_id=7, platform="golaxy")
    assert saved is not None and saved.username == "fan"
    assert credential_store.load_credentials(user_id=8, platform="golaxy") is None


@pytest.mark.asyncio
async def test_confirm_twice_does_not_double_bind(httpx_mock, credential_store):
    """确认重试(网络抖动时前端会重发)不许绑出第二个账号或换掉已有的。"""
```

- [ ] **Step 4: 跑测试确认绿**

Run: `uv run pytest tests/web_ui/test_platform_scan_login.py -q`
> `credential_store` 夹具的真实 API 是 `PlatformCredentialStore(db_path=...)` / `save_credentials(user_id, credentials)` / `load_credentials(user_id, platform)` / `delete_credentials` / `list_platforms(user_id)`（`credentials.py:91/113/131/147/159`）。**不是** `path=` / `save` / `load`。

- [ ] **Step 5: 加三个端点，并且给扫码会话一个服务端身份**

```
POST /{platform}/scan/start    → {scan_id, payload, expires_at}
GET  /{platform}/scan/state    → {state}            （带 scan_id）
POST /{platform}/scan/confirm  → {connected, display_name}   （带 scan_id）
```

> ⚠️ **不要把星阵的 uuid 直接发给前端、也不要用「当次请求的登录用户」当身份。**
> 那三个端点各自 `Depends(get_current_user)` 看起来像鉴权，其实**每次请求各判各的**：用户 1 发起扫码，盒子切到用户 2，用户 2 拿同一个 uuid 去 confirm，凭据就按**确认时**的身份落到用户 2 头上。uuid 本身不带身份——**这条链上唯一的串联物不带身份，身份只能由我们这一侧钉住**。
>
> 服务端存一张短命的会话表（内存即可，盒子上不需要持久化）：
> ```python
> @dataclass
> class ScanSession:
>     scan_id: str            # 不透明,发给前端的是它,不是星阵的 uuid
>     golaxy_uuid: str
>     initiating_user_id: int # ← 钉在这里
>     expires_at: float
>     state: ScanState
>     consumed: bool = False
>     result: dict | None = None   # confirm 的结果,供重试幂等返回
> ```
> - `poll` / `confirm` 都要校验 `initiating_user_id == current_user.id`，不等就 403。
> - `confirm` **在锁里原子消费**：`consumed` 已置位就直接返回缓存的 `result`，**不再换一次 token**。星阵那个 token 是一次性的，第二次换会失败或把共享 adapter 改写成别的状态；而前端在网络抖动时**一定会重发**。
> - 过期的会话直接删，`poll` 返回 `expired`。

- [ ] **Step 5b: 把「昵称」和「登录 principal」分开**

> ⚠️ **`/scan/username` 给的是昵称，不是登录 principal。** 核过：`adapter.py:403-412` 的 `set_username()` 会把裸值规范化成 `0086-{username}`，而 `engine_client.py:46-49/461` 明写 `/items/{username}` 要的是 `0086-{phone}` 那种登录 principal。把昵称存进 `PlatformCredentials.username`，重连之后道具查询就会去请求 `/items/0086-fan` —— **道具角标全线坏掉，而全链测试照样绿**。
>
> `PlatformCredentials` 今天**只有一个 `username` 字段**。两条路选一条，在本步里定死并写进注释：
> 1. **能从已核实的响应里拿到 principal**（token 响应体或 `/scan/username` 之外的某个接口）⇒ 存 principal，昵称另存一个展示字段。
> 2. **拿不到** ⇒ **不许猜**。扫码会话的 `username` 留空，屏上道具角标显示 `—`（稿子已定义：`—` 是「这次没取到数」，和 `0` 不是一回事），并在 adapter 里写明「扫码登录拿不到 principal，道具次数不可用」。
>
> **判据**：加一条集成测试——存完凭据后**重新构造一个 adapter、从存储恢复、再调 engine items**。走 1 就断言请求打到了正确的 principal；走 2 就断言它诚实地返回「不可用」而不是打一个 `0086-{昵称}` 出去。

- [ ] **Step 6: 写 `GolaxyScanPanel.tsx`**

- 本地画码：用 `qrcode` 这个纯前端库（`npm i qrcode`）或手写。**先确认它进不进 kiosk-2d 包**：`npm run build:kiosk-2d && npm run verify:kiosk-2d`。
- 轮询每秒一次，**组件卸载和拿到终态时必须停**。
- 五态文案：等待扫描 / 已扫描，请在手机上确认 / 手机上取消了登录 / 二维码已失效（+「换一张」）/ **取不到 uuid**：虚线框 + 「连不上星阵，检查网络」+「重试」，**不摆一张扫不动的假码**（Review Focus #2）。

- [ ] **Step 7: 补 Review Focus #2 的前端测试**

```tsx
it('取不到 uuid 时不画二维码,画虚线框 + 重试;轮询不启动', async () => {
  vi.mocked(API.platformScanStart).mockRejectedValue(new Error('连不上'));
  render(<GolaxyScanPanel platform="golaxy" onDone={() => {}} />);
  expect(await screen.findByTestId('scan-unavailable')).toBeInTheDocument();
  expect(screen.queryByTestId('scan-qr')).toBeNull();
  vi.advanceTimersByTime(5000);
  expect(API.platformScanPoll).not.toHaveBeenCalled();
});
```

- [ ] **Step 8: 补 i18n、跑闸、跑两个构建、提交**

## Task 7: OGS 登录页

**Files:**
- Modify: `katrain/web/ui/src/kiosk/pages/PlatformLoginPage.tsx`（`ogs` 分支）
- Modify: `katrain/web/ui/src/kiosk/pages/PlatformLoginPage.test.tsx`

后端现成（`katrain/web/platforms/ogs/rest_client.py:47` `POST /api/v0/login` → `GET /api/v1/ui/config` 取 `user_jwt`）。这一任务只做前端。

- [ ] **Step 1: 写失败测试** —— OGS 页无标签栏、字段是用户名+密码、左栏四条 fact、按钮写「登录 OGS」
- [ ] **Step 2: 跑它确认它红**
- [ ] **Step 3: 实现** —— `tabs` 推导为 `['password']` 时不渲染 `KioskOptSeg`
- [ ] **Step 4: 跑测试确认绿**
- [ ] **Step 5: 补 i18n、跑闸**
- [ ] **Step 6: 提交**

## Task 8: 切片 A 的视觉关卡 + 共用盒子换人的测试

> Review Focus #3（共用盒子换人）**已经上移到 Task 4.5**，并且换成了两个真用户走 API 的集成测试。原来写在这里那条只测 `PlatformCredentialStore` 的用例**作废**——它测的是最里面那一层，而堵点在更外面（全局 adapter），一上来就是绿的。这是「到达性测试给断路发通行证」的教科书形状，留着比没有更坏。

- [ ] **Step 1: 确认 Task 4.5 那三组测试仍然绿**

Run: `CI=true uv run pytest tests/platforms/test_platform_user_isolation.py -q`
登录页换了入口，`/status` 的调用路径变了，这里再跑一次不是重复——是确认新入口没绕过那道闸。

- [ ] **Step 2: 取四图**：07a 扫码 / 07b 密码 / 08 OGS 三屏
- [ ] **Step 3: 承重实测**：登录页是**新页**，高度链全新 ⇒ 触发。要量的清单：
  - 该滚的是谁：`.xplogin__main` 内的滚动容器（先写下来，再读数）
  - 横向：`.xpcol` 520 + aside 300 + 两侧 padding ≤ 1024，`document.documentElement.scrollWidth <= 1024`
  - 纵向：三/四条 fact 全展开时 aside 自身 `scrollHeight <= clientHeight`
  - **软键盘**：Task 5 Step 4b 那条（真挂 `.skbd`，不是缩 viewport）
  - 不适用的写「不适用 + 一句为什么」，**不许空过**
- [ ] **Step 4: 请 Fan 确认四图**
- [ ] **Step 5: 提交**

---

# 切片 B：每平台进自己的大厅

**用户旅程：** 「我点了星阵，就该进星阵的页」——Fan 2026-09-22 的原始问题。

## Task 9: 星阵首页（屏 07）

**Files:**
- Create: `katrain/web/ui/src/kiosk/pages/GolaxyHomePage.tsx`
- Create: `katrain/web/ui/src/kiosk/pages/GolaxyHomePage.test.tsx`
- Modify: `katrain/web/ui/src/kiosk/KioskApp.tsx`

**Interfaces:**
- Consumes: `API.platformStatus(token)`（判是否已连接、取账号名）、`playInputState` / `writePlayOnBoard`（`src/kiosk/utils/playInput.ts`）
- Produces: 路由 `/kiosk/play/cross-platform/:platform`（`platform` 今天只会是 `golaxy`；OGS 走 `/lobby?platform=ogs`，因为它没有人机那条路）

内容（稿子 `data-screen="platform"`）：落子/路数两行 → 「开一局」三张卡（快速匹配 / 房间 / 人机对弈）→ 「棋友」名单。

**今天只有「人机对弈」有后端。** 按 Global Constraint #8：
- 「快速匹配」「房间」两张卡：**不可点**，卡上写它今天是什么（`platform:pvp_not_wired`「星阵人人对弈还没接通」），不写「即将上线」——挡路的是协议还没抓包核实（Task 13），没人给过日期，那是预测不是状态。
- 「棋友」整段：`GolaxyAdapter.get_online_users` 没重写 ⇒ 基类返回 `[]`（`katrain/web/platforms/base.py:61-66`）。**空列表和「这儿本来就没有」长得一样** ⇒ 这一段在切片 D 之前**整段不渲染**，而不是渲染成一张空表。

- [ ] **Step 1: 写失败测试**

```tsx
// katrain/web/ui/src/kiosk/pages/GolaxyHomePage.test.tsx 关键三条
// KioskCard 没有 testId prop（核过 shell/KioskCard.tsx），所以按可及名取。
// 它的 aria-label = [title, sub, soon].filter(Boolean).join('，')，所以状态就在名字里。
it('三张卡里只有人机可点,另两张不可点且写明今天是什么', async () => {
  renderPage();
  await screen.findByTestId('golaxy-home-page');
  expect(screen.getByRole('button', { name: /人机对弈/ })).toBeEnabled();
  expect(screen.getByRole('button', { name: /快速匹配/ })).toBeDisabled();
  expect(screen.getByRole('button', { name: /房间/ })).toBeDisabled();
  // 不是光灰着 —— 灰按钮会让人一直按。原因要在可及名里。
  expect(screen.getByRole('button', { name: /快速匹配/ })).toHaveAccessibleName(/还没接通/);
  // 也不许写「即将上线」:没人给过日期,那是预测不是状态
  expect(screen.getByTestId('golaxy-home-page')).not.toHaveTextContent('即将');
});

it('棋友名单为空时整段不渲染,不画一张空表', async () => {
  vi.mocked(API.platformUsers).mockResolvedValue({ users: [] });
  renderPage();
  await screen.findByTestId('golaxy-home-page');
  expect(screen.queryByTestId('golaxy-players')).toBeNull();
});

it('人机卡进的是这一家的开局设置', async () => {
  renderPage();
  await userEvent.click(await screen.findByRole('button', { name: /人机对弈/ }));
  expect(navigate).toHaveBeenCalledWith(
    '/kiosk/play/cross-platform/engine/golaxy', expect.anything(),
  );
});
```

- [ ] **Step 2: 跑它确认它红**

Run: `cd katrain/web/ui && npx vitest run src/kiosk/pages/GolaxyHomePage.test.tsx`
Expected: FAIL, `Cannot find module './GolaxyHomePage'`

- [ ] **Step 3: 写页面**

骨架照稿子 `data-screen="platform"`：`.xp` 外壳 + `KioskPagebar` + `KioskScrollZone`，里面三段。

> ⚠️ **页控条副标不要照抄稿子那句「已连接 · fan · 星阵号 61707593」。** 核过：`PlatformInfo` 里**只有 `saved_username`，没有 usercode**；后端 `/status` 也只合了 username；`GolaxyRestClient` 虽有 `_user_code` 字段，但**全仓没有赋值路径**。照抄等于在屏上编一个号码。
>
> 这一版副标写 **`已连接 · {saved_username}`**。星阵号要显示的话，它是一次**数据契约变更**（adapter 从已核实的响应里取 user_code → 按用户持久化 → `/status` 带出来 → 缺失时诚实留白），**单独一个任务**，不夹带在这一屏里。这条要在 Task 12 的视觉关卡上向 Fan 说明：稿子上那个号今天给不出，是补契约还是就不显示。

```tsx
{/* 落子 / 路数 —— 和屏 09 同一副骨架,复用 playInputState */}
<section className="setgrp inputgrp xpin" data-testid="golaxy-input">…</section>

{/* 开一局 —— 三张卡,两张今天点不了 */}
<section className="kiosk-section" data-testid="golaxy-start">
  <KioskSecLabel zh={t('platform:start_a_game', '开一局')} en="Start"
    value={t('platform:result_goes_to_golaxy', '胜负记在星阵账上')} />
  <div className="kiosk-cards">
    {/* `soon` 的文案由调用方给(KioskCard 自己的注释:「不许写『锁定』」),
        且它自带 disabled —— 正好是我们要的「不可点 + 写明今天是什么」。
        **不要传「即将上线」**:挡路的是协议没抓包核实,没人给过日期。 */}
    <KioskCard
      icon="users" title={t('platform:automatch', '快速匹配')}
      sub={t('platform:automatch_sub', '按星阵等级配一个对手')}
      soon={t('platform:pvp_not_wired', '人人对弈还没接通')} />
    <KioskCard
      icon="list-numbers" title={t('platform:room', '房间')}
      sub={t('platform:room_sub', '开一个房间，或输入房间号')}
      soon={t('platform:pvp_not_wired', '人人对弈还没接通')} />
    <KioskCard
      icon="robot" title={t('platform:vs_ai', '人机对弈')}
      sub={t('platform:vs_ai_sub', '星阵 39 档 AI · 可用道具')}
      onClick={() => navigate(`/kiosk/play/cross-platform/engine/${platform}`, { state: backToState(location) })} />
  </div>
</section>

{/* 棋友 —— users 为空就整段不渲染 */}
{users.length > 0 && (
  <section className="kiosk-section" data-testid="golaxy-players">…</section>
)}
```
核过的三件事，照做即可、不用再查：
- `KioskCard` **没有** `testId` prop（`shell/KioskCard.tsx:24`），测试按可及名取。
- `KioskCard` 的 `soon?: string` **自带 `disabled`**（`:51` `disabled={Boolean(soon || todo || disabled)}`），且文案由调用方给——正合用，不必新加 prop。
- `backToState` 在 `src/kiosk/hooks/useBackTo.ts`，`PlatformEngineSetupPage.tsx:4` 已在用。

- [ ] **Step 4: 跑测试确认绿**

Run: `cd katrain/web/ui && npx vitest run src/kiosk/pages/GolaxyHomePage.test.tsx`
Expected: 3 passed

- [ ] **Step 5: 加路由**

```tsx
// KioskApp.tsx,放在 lobby / engine 两条之后,避免 :platform 把它们吃掉
<Route path="play/cross-platform/:platform" element={<GolaxyHomePage />} />
```
> ⚠️ 路由顺序：`:platform` 是通配段，放在 `lobby` 和 `engine/:platform` **之前**会把它们一起吃掉。加完跑一遍 `PlatformLobbyPage.test.tsx` 和 `PlatformEngineSetupPage.test.tsx` 确认没被抢。

- [ ] **Step 6: 补 i18n key 并跑闸**

新增：`platform:start_a_game`、`platform:result_goes_to_golaxy`、`platform:pvp_not_wired`、`platform:room`、`platform:room_sub`、`platform:vs_ai`、`platform:vs_ai_sub`、`platform:automatch_sub`。`platform:automatch` develop 上已有，先 grep 再决定要不要新增。11 语种。

- [ ] **Step 7: 提交**

```bash
git add -A katrain/web/ui/src/kiosk katrain/i18n/locales
git commit -m "$(cat <<'EOF'
feat(kiosk-go): 星阵首页 —— 点了星阵就进星阵的页

Fan 2026-09-22 的原始问题:选了星阵,二级页为什么还是所有平台。
今天只有人机那条有后端,另两张卡不可点且写明「还没接通」——
不写「即将上线」(挡路的是协议没抓包核实,没人给过日期)。
棋友名单为空时整段不渲染:空列表和「这儿本来就没有」长得一样。

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
EOF
)"
```

## Task 10: 路由收口

**Files:**
- Modify: `katrain/web/ui/src/kiosk/pages/PlayPage.tsx`
- Modify: `katrain/web/ui/src/kiosk/pages/PlatformConnectPage.tsx`
- Modify: `katrain/web/ui/src/kiosk/pages/SettingsPage.tsx`

- [ ] **Step 1:** `PlayPage` 已连接的星阵 → `/kiosk/play/cross-platform/golaxy`（Task 9 建好了才改，见 Task 5 Step 8 的注）
- [ ] **Step 2:** 设置页「账号与平台」一节：只列**已连接**的平台；副文案从「怎么登」换成「现在挂着谁的账号」；撤掉「连接」键与「野狐」行（都是第二个入口）；**保留「断开」**——它全稿只有这一处，且屏 07a/07b/08 的左栏都写着「想断开随时去设置里」。
- [ ] **Step 3:** 空态：「还没有连接任何平台 · 在对弈页连接」
- [ ] **Step 4–6:** 测试 / i18n / 提交

## Task 11: OGS 大厅改造（屏 08a）

**Files:**
- Modify: `katrain/web/ui/src/kiosk/pages/PlatformLobbyPage.tsx` + `.test.tsx`
- Modify: `katrain/web/platforms/ogs/adapter.py`（挑战列表加实时局过滤）

四条改动，每条都有实测依据（`reference_ogs_platform_facts`）：
1. 名单从「在线用户」换成 **公开挑战**（OGS 的 seek graph，`_on_seekgraph` 已在收），每行就是一局现成的条件，「接受」即开局。
2. **只列实时局**。2026-09-23 实看：实时局 5 条，通信局（3 天/手）三十多条，外加一整段联棋。盒子边上站着人等着下，列一局「每手 3 天」没有意义。**这是过滤条件，不是没实现**——要在代码注释里写明，别让下一个人以为漏了。
3. 选了实体盘时，**非 19 路的挑战行尾换成「实体盘只下 19 路」，不给接受键**（接了也摆不上去）。
4. **屏 08b「发起挑战」**（稿子 `data-screen="platform-challenge"`）：按用户名搜到人之后，行尾「挑战」进的那一屏。今天 `platformSendChallenge` 的三项条件在实现里**写死**（既有 08 四图的 caption 已记下这一条），所以这一屏的条件区**画成只读读数**，不画成可选项——画成可选项等于承诺一个不存在的开关。**这一屏此前没有任何任务覆盖**，是自查时补上的。

- [ ] **Step 1:** 后端过滤的 pytest：实时局进来、通信局不进来、**联棋（rengo）不进来**；再补一条变异——把过滤条件去掉，这三条必须红
- [ ] **Step 2:** 跑它确认它红
- [ ] **Step 3:** 实现后端过滤（`katrain/web/platforms/ogs/adapter.py` 的 `get_open_challenges`），注释里写明「这是过滤条件不是没实现」
- [ ] **Step 4:** 前端失败测试：公开挑战行的形状、实体盘下非 19 路不给接受键、08b 条件区是只读
- [ ] **Step 5:** 实现前端（改 `PlatformLobbyPage`，新增 08b 的挑战屏）
- [ ] **Step 6:** 承重实测：挑战列表灌到两屏以上（**装得下的数据量下量出来的数不作数**），按六条判据逐项量——该滚的是谁 / 能不能滚 / 手指拨得动吗 / 没被祖先裁掉 / 坐标系 / 落点
- [ ] **Step 7:** 取四图 08a、08b
- [ ] **Step 8:** i18n + 跑闸
- [ ] **Step 9:** 提交

## Task 12: 切片 B 的视觉关卡

- [ ] **Step 1:** 取 07 / 08a / 08b / 27 四组四图
- [ ] **Step 2:** 自己逐项对一遍（构图 · 几何间距 · 组件层级 · 字体色彩 · 图标 · 文案 · 状态语义）
- [ ] **Step 3:** 请 Fan 确认。这一切片有两处要他拍板：
  1. 星阵首页上那两张不可点的卡，措辞是否可接受
  2. 设置页「账号与平台」只列已连接的平台之后，空态那句「还没有连接任何平台 · 在对弈页连接」够不够
- [ ] **Step 4:** 提交

---

# 切片 D：星阵人人对弈

**最重、且协议里有未核实项。先抓包，抓不到就停。**

`GolaxyAdapter` 今天**完全没有** PvP：`get_rooms()` 写死 `return []`（`golaxy/adapter.py:666-668`），`get_online_users` / `send_challenge` / `start_automatch` 都没重写，落到基类的 `[]` 和 `NotImplementedError`（`platforms/base.py:61-89`）。

> **Task 14–16 在这里是提纲，不是可执行任务。** 把它们现在展开成带代码的分步，等于照着三条**标着「推断 / 未知」**的协议事实写实现——`reference_golaxy_pvp_protocol` 明写那三条来自大厅观察 + bundle 静态分析，没抓过包。Task 13 出 GO 之后，**先把 Task 14–16 按本文件前面那些任务的粒度重写一遍**（Files / Interfaces / 每步一个动作 / 真代码 / 跑什么 / 期望什么 / 提交），再交给执行者。这是本计划自查时刻意留的一处空白，不是漏写。

## Task 13: 抓包 spike（GO / NO-GO 闸）

`reference_golaxy_pvp_protocol` 里标了「推断/未知」的三条，开工前必须抓一次真包核实：

1. **快速匹配是不是升降战**（bundle 里 `levelType:"upgrade"`、让子写死 0 —— 大厅观察 + 静态分析得出，**未抓包**）
2. **邀请局算不算升降战**（`gameType` 有 competitive / placement / casual 三种，不知道邀请走哪个）
3. **STOMP 帧结构**（订阅路径已知，帧体没抓过）

- [ ] **Step 1:** 在自己的星阵账号上抓一次真包，产出一张**事实表**（端点 · 请求体 · 响应体 · 触发时机），写进 `katrain/web/platforms/golaxy/PROTOCOL.md`
- [ ] **Step 2:** 对照 `reference_golaxy_pvp_protocol`，逐条把「推断」改成「已核实」或「推断错了，实际是 X」
- [ ] **Step 3:** **GO / NO-GO**：三条里有任何一条抓不到，把结果交给 Fan 再定，不要按推断开写
- [ ] **Step 4:** 提交 PROTOCOL.md

> ⚠️ 抓包时**不要**点「创建房间」「邀请对局」「快速匹配」以外的东西，那些动作对真人可见。匹配到真人就立刻认输或退出，别让对方空等。

## Task 14: 快速匹配（taste）

端点 `POST /api/social/gamezone/game/taste/match|heartbeat|cancel/{usercode}`，参数 `tasteOptionFast/Normal/Slow/Ai`（**三档用时可多选** + 允许配 AI）。常量：`taste_invite_timeout` **8 秒**、`taste_max_wait` 30。屏 07c（弹层）+ 07d（配到对手）。

- [ ] 后端 adapter 方法 + pytest → 前端弹层 + 测试 → 四图 07c/07d → i18n → 提交

## Task 15: 邀请与房间

`/gamezone/game/invite`（+accept/reject/cancel/ack，`invite_timeout` **30 秒**）；`/gameroom/reserve` 等。屏 07e（邀请棋友）+ 07f（房间）。
**网页版「创建房间」是一按就建**（不先问条件），盒上照做还是先问，要在四图那一步请 Fan 定。

- [ ] 后端 → 前端 → 四图 07e/07f → i18n → 提交

## Task 16: 对局中（屏 10a）+ 读秒珠 + 韩文实测

`/wsgame/genmove|backmove|judge/data|game/end/{id}`；请求类动作（悔棋 / 停一手 / 数子）走 `/wsgame/action/accept|reject`，`actionCountdown` **10 秒**；`user_disconnect_wait` 10。

签名件**读秒珠**：一次读秒 = 一颗白子。⚠️ 星阵的钟是日式读秒（`mainTime / countdownNum / countdownTime`）——**费舍尔加秒那种没有珠子**，OGS 那边两种都有，组件要能不画珠子。

- [ ] **Step 1–6:** 后端 → 前端 → 四图 10a → 承重（棋谱长列表滚动 + 当前手贴底，六条判据逐项量）→ i18n
- [ ] **Step 7: Review Focus #5 —— 韩文实测**
  ```bash
  # 把 kiosk 语言切成 ko,跑一遍跨平台全部屏,截图人眼看有没有中文漏出来
  ```
  闸只能挡「key 不在 .po 里」，挡不住「翻译写错了语种」。这一步是人眼看一遍。
- [ ] **Step 8: 提交**

---

## 每个切片的完成定义

五条全中才算完成（vertical-slice）：

- [ ] 真实可部署
- [ ] 状态诚实（加载 / 错误 / 空态 / 重试不伪装成功）
- [ ] **每一条导航目标都真渲染得出来**（用真 Router 断言过，不是只断言 navigate 收到了哪个字符串）
- [ ] 所需后端已集成（不是「待接」）
- [ ] 验收通过：`CI=true uv run pytest tests` 的 FAILED 集合与基线 `comm` 无新增；`npx vitest run src/kiosk` 全绿；四图已请 Fan 确认
- [ ] 生产代码中无模拟业务数据，Fixture 已删
- [ ] 触发承重关卡的切片：实测清单逐项有数字或「不适用 + 理由」；量出过错误数值的那条行为已留断言进真浏览器几何闸
- [ ] **本切片引入了动态 key（key 从常量表/变量传进 `t()`）时**：韩文冒烟过了——切到 `ko` 把本切片的每一屏看一遍，屏上没有中文漏出来。不能推到 Task 16：那之前切片 A / B 会先被判完成。

## 并行在制品

**共享基础未稳定时不同时铺开多个未完成切片。** 具体到这份计划：

- **Task 2 的 Step 0 是一道人裁的闸**：Fan 没在 (a)/(b)/(c) 里选之前，Task 2 一行代码都不写，Task 3 也不能动到 `AiLevelSheet` 那部分。
- Task 1 可以和 Task 2 的 Step 0 并行（Task 1 不依赖那个裁定）。
- Task 3 必须等 1、2 都合了才开始（它 import 两者；若裁定是 (b)/(c)，等 1 即可）。
- **Task 4.5 是切片 A 的第一个任务，且它改的是后端共享面**（`manager.py` / `platforms.py`）。它在制期间，切片 A 的其它任务不要同时动那两个文件。
- Task 5 / 6 / 7 内部串行（同一个页面文件）。
- 切片 C 的 Task 4（Fan 确认）没过，不开切片 A。
- **`KioskStepTrack` 是共享件**（Task 3 Step 3 会改它），改动期间不要有别的任务同时动它。

## 给执行者的三条硬提醒

1. **不要把「计划里写了」当成「仓里有」。** 这份计划第 1 轮对抗式审核逮到 8 条，其中 4 条正是这种形状：写了不存在的 CSS token（`--text-dim`/`--on-accent`）、写了被仓里协议否掉的域名（`19x19.com` 而非 `api.19x19.com`）、写了不存在的凭据表 API（`path=`/`save`/`load`）、写了不存在的字段（`usercode`）。**每一个你要 import / 引用 / 传参的名字，动手前 grep 一次。**
2. **改绿是最后手段，改闸是禁止的。** 测试一上来就绿，先怀疑它量错了对象——把被测的那行代码破坏掉，看它红不红。不红就是这条闸瞎了。
3. **jsdom 对布局事实无权作证。** 「盖没盖住 / 滚不滚得动 / 有没有被裁掉」一律归真浏览器几何闸。在 jsdom 里写这类断言，不是弱一点，是**错的**。
