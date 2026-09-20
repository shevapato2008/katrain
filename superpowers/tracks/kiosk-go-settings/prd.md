# 围棋 kiosk · 设置 赛道 PRD(kiosk-go-settings)

- 日期:2026-09-20
- 分支 / worktree(**待创建**):`feature/kiosk-go-settings` @ `/Users/fan/Repositories/katrain-kiosk-go-settings`,基线 develop `012e2a04`
- 输入:2026-09-14「围棋 kiosk 缺口账本」设置模块七条(ST1 ST2 ST3 ST4 ST5 ST6 ST7)
- **本文所有行号都在 develop `012e2a04` 上重核过(2026-09-20)**。账本成文于 `6f7dc629`,其后 develop 前进 234 个提交,**ST1 已被修掉一半**(见 §2),其余六条仍然成立;`SettingsPage.tsx`、`AccountSection.tsx`、`GeometryContext.tsx`、`OrientationContext.tsx` 相关段落逐行复核过。

---

## 1. 背景与目标

设置屏(屏 27)已经按外壳重画完了:左栏导航、五组内容、账号两行、三件器件读数、两把声音开关、十一种语言,滚动与高亮都对。

剩下四件用户碰得到的事:

1. **设置里关掉「落子音效」,研究屏和摆谱屏照响。** 对局屏那一半 2026-09 已经修好(`useGameSession` 读 `audioPrefs`),但**研究屏走的是另一个 hook**(`useSessionBase:49`,没有任何开关判断),摆谱的快门声是 WebAudio 直接发声(`BaipuSessionPage.tsx:31`)。屏上写着「关」,喇叭还在响 —— 这正是 `audioPrefs.ts` 文件头自己写下要避免的那种 bug。
2. **点「查看AI段位详情」弹出来的是一张 MUI 卡**,标题「AI段位详情」和按钮文案都是写死的中文、不走 `t()`;段位读不到时那张 MUI 卡还直接顶在设置列表里,和四周的 `.kiosk-row` 断层。
3. **没接摄像头的盒子上照样写「还没标定 · 开始标定」**,点进去只有一屏「没有摄像头」;开机还没问到状态那一瞬,三格先闪「未连接」—— 而 `GeometryContext` 专门为「还没问到」和「问到了没连上」准备了 `loaded`,这一屏没用。
4. **屏幕旋转的死代码还挂在整棵 kiosk 树上**:入口 2026-07-08 有意删了(硬件不再旋转),`OrientationProvider` / `RotationWrapper` / `katrain_kiosk_rotation` 还在,`setRotation` 生产代码零调用。同一族还有一个零消费者的 MUI 组件 `PhysicalBoardStatus.tsx`。
5. **屏上没有「关于」**:用户看不到这台盒子跑的是哪个版本、引擎连没连上 —— 出问题时连一句能报给客服的话都没有。**Fan 2026-09-21 裁定:先做「关于」这一组**(§3 ST3-关于)。

这一轮把这五件做掉。剩下三件(「棋盘外观」「对局默认值」两组、要不要写「系统设置在设置中心」那句、盒上偏好存哪)要 Fan 先裁,见 §4。

## 2. 已经做完、不要动的

| 内容 | 出处 |
|---|---|
| 屏 27 五组 + 左栏导航 + 高亮跟随滚动 + 尾部留白 | `SettingsPage.tsx:89-355` |
| 账号两行改成 `.kiosk-row`;盒端 SSO 下「在主页切账号」(不带 `?logout=1`) | `AccountSection.tsx:44-106` |
| 两把声音开关(音效 / 语音)走 `utils/audioPrefs` 的模块级状态,用 `useSyncExternalStore` 订阅 | `SettingsPage.tsx:151-154`、`utils/audioPrefs.ts` |
| **ST1 的一半已修**:对局屏(人机 / 本地 / 房间 / 星阵)的落子提子声改读 `audioPrefs` 的 `sfx`;屏 04「落子提示音」写的也是同一把键,`kioskPlaySound` 已退役 | `useGameSession.ts:64-67`、`PvpLocalSetupPage.tsx:81`、`useGameSession.sound.test.tsx:359` |
| `useSound`(做题、直播、报告回放)认 `sfx` | `hooks/useSound.ts:69` |
| 语言一行留在本屏并写明「将来会搬到设置中心」(已登记的规范偏差) | `SettingsPage.tsx:330-332` |
| 三件器件读数的注释口径「不拿一颗灰灯冒充未连接」 | `SettingsPage.tsx:243-244`(**注释对、实现没做到** —— 见 §3 ST5) |

---

## 3. 需求条目(本轮做)

### ST1(余下一半)· 研究屏与摆谱屏不认「落子音效」开关 —— P1

- **现象**:设置里把「落子音效」关掉,研究屏落子照响、摆谱每拍一帧照「叮」一声。
- **根因(已核实)**:
  - `hooks/useSessionBase.ts:49-56` 的 `playSound` **一句开关判断都没有**,而研究会话走的是这个 hook(`useResearchSession` → `useSessionBase`)。
  - `kiosk/pages/BaipuSessionPage.tsx:31-48` 的 `playShutter()` 用 WebAudio 直接发声,`:218` 在写完一帧后调用,同样不读偏好。
- **期望**:两处都在发声前 `readAudioPref('sfx')`,关掉就不响。
  - `useSessionBase` 是**共享领地**(galaxy 的研究页也用它)。galaxy 从不写这把键,而 `readAudioPref` 缺键当开 ⇒ **galaxy 行为不变**(`useGameSession` 那次已经这么办过,照抄它的注释口径)。
  - 摆谱快门是「可以摆下一颗了」的信号,它归**音效**(`sfx`)不归语音(`voice`):语音那把关的是那七句引导语。
- **验收**:
  1. 单测(`useSessionBase`):`kiosk_audio_sfx = 'false'` 时收到 `sound` 消息不调 `Audio.play`;缺键时照响。
  2. 单测(摆谱):关掉 `sfx` 后写完一帧不发声(桩掉 `AudioContext`,断言 `createOscillator` 没被调用);开着时发声。
  3. `rg "playSound = useCallback" katrain/web/ui/src/hooks` 的两处**都**有 `readAudioPref('sfx')`。
- **依赖**:无,纯前端。共享领地 ⇒ 两套构建都要绿。

### ST4 · 「AI 段位详情」还是 MUI 弹窗,文案写死 —— P2

- **现象**:`AccountSection.tsx:2` `import { Dialog, DialogContent, DialogTitle } from '@mui/material'`;`:141-144` 弹窗里装着共享件 `AiLadderStatusCard`(MUI `Card`/`Chip`/`LinearProgress` + MUI 图标);`:128` 的「查看AI段位详情」和 `:142` 的 `<DialogTitle>AI段位详情</DialogTitle>` 都是写死中文,不走 `t()`;`:135-139` 段位不是 `ready` 时那张 MUI 卡**直接顶在设置列表里**。
- **期望**:
  - 新建 `kiosk/components/settings/KioskAiLadderDetail.tsx`,**照 `kiosk/components/aiLadder/KioskAiLadderOpponent.tsx` 的做法**:另起一个外壳视图,不给共享件加 `variant`(那是一个 prop 兼管两件事,而且要换的不是尺寸是整套视觉语言);每一句都取自 `features/aiLadder/copy.ts` 的 `AI_LADDER_COPY`,判别位取自 `startGate.ts` 的纯函数,**不在这儿重写条件**;配一条 parity 测试断言两个视图说的是同一套话。
  - 展开方式用**就地展开**(`.kiosk-rows` 里多一块),不做遮罩弹层:这一屏本来就是滚动列表,展开代价最小,也不用做焦点陷阱。按钮文案在「查看AI段位详情」/「收起」之间切换,都走 `t()`。
  - 段位不是 `ready` 时,那一行改成外壳的 `.kiosk-row` + `AI_LADDER_COPY.loading` / `loadError` + 一颗永远画得出来的「重试」(拿不到 `onRetry` 时禁用)——和 `KioskAiLadderOpponent` 同一条口径。
  - **共享件 `AiLadderStatusCard` 不改**(galaxy 在用)。
- **验收**:
  1. 单测:`ready` 态点「查看AI段位详情」展开,展开后能看到档位名、认证状态、路由(本地 / 服务器)、净胜分;再点收起。
  2. 单测:`loading` / `error` 两态渲染的是 `.kiosk-row`,**不是** MUI 卡;`error` 态有「重试」并能调到 `onRetry`。
  3. parity 单测:六种 `view_state` 下,kiosk 视图与 `AiLadderStatusCard` 用的是同一组 `AI_LADDER_COPY` 文案键。
  4. `rg "@mui" katrain/web/ui/src/kiosk/components/settings/` 零命中。
  5. `rg "AI段位详情|查看AI段位" katrain/web/ui/src | rg -v "t\('"` 零命中(文案全部走 `t()`)。
- **依赖**:无,纯前端。

### ST5 · 设置页不看摄像头状态,也不分「还没问到」和「没连上」 —— P3

- **现象**:`SettingsPage.tsx:93` `const { status } = useGeometry();` **没取 `loaded`**;`:161-163`、`:230-241` 的「还没标定 · 开始标定」不看 `phase`;`:245-258` 三格直接用 `status.capabilities.*`,而 `DEFAULT_STATUS` 三个 capability 全是 `false`(`GeometryContext.tsx:4-9`)⇒ 开机还没问到时先闪「未连接」。
- **期望**:
  - 取 `loaded`:没读到之前三格一律写 `—` 且不给灯色(**照抄标定屏 `GeometryCalibrationScreen.tsx:325-331` 的写法**,同一件事只有一套写法)。
  - `phase === 'disabled'`(这台盒子没起采集服务 / 没摄像头):这一组的标定入口**不可点**并写明原因(「这台盒子没有接摄像头」),不把人送进一屏「没有摄像头」再退回来。三格照旧显示,但写 `—`。
  - 标定状态那一行的措辞与视觉赛道的标定屏保持一致(见 §6.0 第 2 条:措辞以视觉赛道为准)。
- **验收**:
  1. 单测:`loaded === false` 时三格是 `—`,没有 `kiosk-tag--win` 也没有「未连接」。
  2. 单测:`phase === 'disabled'` 时「开始标定」禁用且屏上有原因那句;点它不发生导航。
  3. 单测:`phase === 'ready' && session_calibrated` 时仍写「这次开机已标定」,按钮可点并导航到 `/kiosk/vision/setup`(**今天的行为不许退化**)。
- **依赖**:视觉赛道(措辞与 `GeometryContext` 归它改,本赛道只消费)。

### ST6 · 屏幕旋转死代码 + 一个零消费者的 MUI 组件 —— P3(清理)

- **事实(已核实)**:旋转入口是 `2bebfd5e`(Merge,2026-07-08)解决 `SettingsPage.tsx` 冲突时**有意**删的(合并说明:硬件不再旋转);`smartbox-kiosk.service:19` 也写着固定横屏。剩下的是清理:`KioskApp.tsx:34`、`:41`、`:202-214` 仍包着 `OrientationProvider` / `RotationWrapper`,`OrientationContext.tsx` 读写 `katrain_kiosk_rotation`,`setRotation` 生产代码零调用。
- **附带(同族)**:`kiosk/components/settings/PhysicalBoardStatus.tsx` 是一个 MUI 组件,**除了自己的测试没有任何消费者**(设置屏自己画那三格)。
- ⚠️ **它不是透传层。** `RotationWrapper.tsx:14-16` 即使在 `rotation = 0` 下也渲染一个
  `position: fixed; width: 100vw; height: 100vh; overflow: hidden; transform-origin: top left` 的 div ——
  **那是整棵 kiosk 树的高度来源和裁切边界**。按 CLAUDE.md 的反查(「把这次改动撤回去,有没有元素的高度来源或裁切边界会变?」)
  ⇒ 会变 ⇒ **这是承重改动,必须在真浏览器里量**,不许拿 jsdom 或一帧截图顶替。
- **期望**:
  - 删掉**旋转机器**:`OrientationContext.tsx`、`RotationWrapper.tsx` 及其测试
    (`OrientationContext.test.tsx`、`RotationWrapper.test.tsx`、`orientation.integration.test.tsx`),
    以及零消费者的 `PhysicalBoardStatus.tsx` + `PhysicalBoardStatus.test.tsx`。
  - **保留那只盒子**:`KioskApp.tsx` 里把 `<RotationWrapper>` 换成一个同样几何的
    `<div className="kiosk-viewport">`(fixed / 100vw / 100vh / overflow hidden),
    并在它旁边写明它是承重的、不是排版留白。删的是旋转,不是视口。
- **不做**:不去清 `localStorage` 里遗留的 `katrain_kiosk_rotation`(盒上是无痕,本来就不落盘;网页版留一个没人读的键无害,而写一段清理代码就是新增一条要维护的路径)。
- **验收**:
  1. `rg "OrientationProvider|RotationWrapper|useOrientation|PhysicalBoardStatus" katrain/web/ui/src` 零命中。
  2. `npx tsc -b` 绿;kiosk 全量单测按基线 diff 无新增失败(删测试会让**条数**变少 —— 判据是名字集合)。
  3. **承重实测(真浏览器)**:在一屏会滚的页面(设置屏、复盘列表)上,改前改后各量一次
     `documentElement.scrollWidth/ clientWidth`、`scrollHeight / clientHeight` 与 `.kiosk-screen` 的
     `getBoundingClientRect()`:页面仍不横向 / 纵向溢出,画布几何不变(关系式相等,不钉具体像素)。
- **依赖**:`KioskApp.tsx` 与未合并的 kifu 分支相邻但不重叠(§6.0 第 1 条)。


### ST3-关于 · 设置页补「关于」一组 —— P2(**Fan 2026-09-21 裁定:先做这一组**)

- **为什么是它先做**:三组里只有它**纯前端 + 一行后端**,而且后端数据都是现成的;另外两组各自卡着别的决定(见 §4)。象棋设置屏 2026-07-21 起就有「关于」,这也是「与三家一致」那条判据本来就指向的方向。
- **这一组画三行,一行都不许编**:
  - **版本**:真源是 `katrain/core/constants.py:2` `VERSION = "1.17.1"`。前端拿不到它(`katrain/web/ui/package.json` 的 `version` 是 `0.0.0`,不是产品版本)⇒ **由 `/api/v1/health` 带出来**(那个端点已有,加一个键)。拿不到就**不画这一行**,不写「未知」。
  - **引擎**:`/api/v1/health` 已经回 `{"engines": {"local": "reachable|unreachable|error_<code>", "cloud": "reachable|unconfigured|unreachable|error_<code>"}}`(`endpoints/health.py:10-30`)。屏上两行:本机引擎 / 云端引擎,三种状态照实翻(可用 / 连不上 / 没配置);`error_<code>` 归「连不上」,把码写在副标里给运维看。
  - **设备名 —— 本轮不画**。`settings.DEVICE_ID` 看着可用,但 `core/config.py:187-190` 在没有 `KATRAIN_DEVICE_ID` 时**每次启动自铸一个 uuid4**,它既不是出厂身份、也不跨重启稳定;出厂身份的权威是 launcher 持有的 `/etc/smartbox/device.json`(本仓读不到)。**显示一个自铸 id 就是编**,所以这一行等 launcher 给,不自己造。
- **屏上这一组的硬规矩(这一屏自己的文件头注写着)**:**导航项数 = 分组数,且词一一对应** ⇒ `GROUPS` 里加 `about`,右边那组标题逐字相同。另外**尾部留白**那个 `lastGroupRef` 现在挂在「语言」组上,新组成了最后一组就得跟着挪,否则高亮永远轮不到它。
- **验收**:
  1. 后端单测:`/api/v1/health` 回的 `version` 等于 `katrain.core.constants.VERSION`(不是硬编码的字符串)。
  2. 单测:`engines.local='reachable'` / `'unreachable'` / `'unconfigured'` / `'error_502'` 四种各自的屏上措辞;`error_502` 那条副标里出现 `502`。
  3. 单测:响应里没有 `version` 时,版本那一行**不渲染**(屏上不出现「未知」)。
  4. 单测:`GROUPS.length` 与导航项数相等,且第六项是「关于」;`data-group="about"` 存在。
  5. 单测:尾部留白 ref 挂在「关于」组上(点导航第 6 项后高亮停在「关于」,不弹回第 5 项)。
  6. 单测:**屏上不出现 `DEVICE_ID`**(`rg 'DEVICE_ID|device_id' katrain/web/ui/src/kiosk/pages/SettingsPage.tsx` 零命中)。
- **依赖**:无。后端一行 + 前端一组。

---

## 4. 待 Fan 拍板

### ST3(剩下两组)· 「棋盘外观」与「对局默认值」

- **已裁定的那一半**:「关于」本轮做(Fan 2026-09-21),见 §3 ST3-关于。
- **事实更正(账本核过)**:D10 在计划稿里明写选方案 (a)「只做有内容的组」,把「空组做成真功能」判为「五个新 feature,远超本轮」—— 性质是**本轮不做**,不是产品上决定不要。而 D10 引用的判据是 Fan 2026-08-20 的「和另三家一致」:**象棋设置屏 2026-07-21 起就有棋盘皮肤、默认难度、默认时间、关于,国象也有棋盘皮肤**。按同一判据量,这几项反而是该有的。
- **剩下两组各自卡在哪**:
  - **对局默认值**(默认时间 / 默认难度):要先定「默认值存哪」,而那正是 ST2 未决的那件事 ⇒ **建议等 ST2**。
  - **棋盘外观**:Fan 2026-08-26 亲裁的只是「盘面用和 galaxy 同一张 `board.png`、不引进 oak」,「五皮肤仍不做」是 track 从这句推出来的。**建议只做「坐标 / 最后一手」两个显示开关,皮肤不做** —— 前者要动共享 `Board.tsx`,得另起一条小计划。
- **不拍板时本轮怎么处理**:这两组不做。

### ST7 · 设置页底部要不要写「系统设置(网络 / 语言 / 输入法)在设置中心」

- **事实**:共享规范 `kiosk-shell-spec.md:612` 正文仍要求「棋类设置页底部固定写明这一句」;围棋稿子在 Fan 2026-08-22「不要写那么多解释文字」那次清理里把它收进了 HTML 注释;**象棋、五子棋、国象也都没有这句**。
- **两难**:写了就违背「少写解释文字」;不写,用户在围棋设置里找 WiFi / 蓝牙 / 亮度找不到,只能按顶栏主页键回 launcher(而那颗键本来就在)。
- **推荐**:**不写整句**,改为在「语言」那一行的副标里顺带一句(它今天已经写着「这一项将来会搬到设置中心」)——一行副标不是一段解释文字,而且它出现在用户真的会找的那一行旁边。规范 §12 与稿子的冲突建议由 Fan 一句话定,四家一起改。
- **不拍板时本轮怎么处理**:不动。

### ST2 · 盒上偏好存哪(声音两把开关、做对自动下一题、界面语言)

- **事实**:smartbox 的 kiosk chromium 带 `--incognito` 且 `HOME=/tmp`(`smartbox-kiosk.service:39`、`provision.sh:1659-1660`),`Restart=always` + `OOMScoreAdjust=200`,launcher 救援还会 `systemctl restart`。⇒ 浏览器一重启,`localStorage` 里的偏好全部回到出厂,而且**不分账号**。
- **三条路**:
  - A. smartbox 侧把 kiosk chromium 改成持久 profile —— 牵涉 box-sso 的「重启仍免登录」待定项,跨仓。
  - B. 偏好存到本机 katrain(新一张表或一份 JSON),按设备存 —— 本仓能闭环,和 `audioPrefs` 现有的「按设备不按用户」口径一致。
  - C. 存服务端、跟账号走 —— 与 `audioPrefs.ts` 里已写明的裁定(喇叭是**这个房间的**,跟账号走会在换人时突然响)**相反**,除非 Fan 改那条裁定。
- **推荐**:**B**。它不碰跨仓的登录问题,也不违反已有裁定;代价是多一个本机端点。
- **不拍板时本轮怎么处理**:不做。这一条是「重启就回到出厂」,不是「点了没反应」,优先级低于本轮四条。

---

## 5. 不在本轮

| 条目 | 类别 | 一句理由 |
|---|---|---|
| ST3 剩下两组(棋盘外观 / 对局默认值) | 待 Fan | 见 §4;「关于」已裁定做,在 §3。 |
| ST7 那句提示 | 待 Fan | 见 §4;四家一起改才有意义。 |
| ST2 偏好持久化 | 待 Fan | 见 §4;B 方案要一个新端点。 |
| 设置中心本身(WiFi / 蓝牙 / 亮度 / 设备名) | 归 smartbox | 不在本仓;`setup-wizard` 已实现蓝牙音频与设备名。 |
| 标定屏、`GeometryContext`、标定语义 | 归视觉赛道 | 见 §6.0 第 2 条。 |
| galaxy 的 `AiLadderStatusCard` | 归 galaxy | 本轮另起 kiosk 视图,不动共享件。 |

## 6. 与其它赛道的协调与共享文件

### 6.0 四条新赛道统一协调规则(2026-09-20 写定,四份 PRD 同文)

**基线**:直播 / 成长 / 设置 / 视觉四条赛道都从 develop `012e2a04` 开出。上一轮五条赛道里 4 条已并入 develop,只剩 **`feature/kiosk-go-kifu`(`bd30cc39`)未合并**,它改 `KioskApp.tsx` 的路由段(:133-150)与 `KifuPage.tsx`(顶部 import、搜索卡、列表错误块)。

**会撞的地方(按风险排序)**

1. **`KifuPage.tsx` / `KioskApp.tsx` 与未合并的 kifu 分支**:直播赛道要在 `KifuPage.tsx` 的直播那一段(:378-417)加一行入口,设置赛道要删 `KioskApp.tsx` 的 `OrientationProvider` / `RotationWrapper`(:34、:41、:202-214)。两处与 kifu 的 hunk 都不相邻,属文本冲突。**规则:先合 kifu,再合这两家**;谁后合谁负责 rebase。
2. **`GeometryContext` 的状态词(`phase` / `loaded` / `capabilities`)**:设置赛道 ST5 要在设置屏说「还没问到 / 没有摄像头」,视觉赛道 V2/V3 要改标定屏说「取消了还能沿用 / 这台盒子没有 LED」。**规则:`GeometryContext.tsx` 与 `geometryApi.ts` 归视觉赛道改,设置赛道只消费**;同一件事的措辞以视觉赛道为准,设置赛道照抄。
3. **`server.py`**:成长赛道 G2 只在 `_record_ai_game_locked` 的 `data` 字典(:1829-1843)与 `_record_platform_engine_game` 的 `data_overrides`(:3569)各加一个键,**不碰终局收尾入口 `_finish_ended_game`**(上一轮定的唯一入口);视觉赛道只改挂 `GeometryCalibrationService` 的那一段(:760-825)。两处不相邻。
4. **数据库迁移**:仓里**没有 alembic**(装着包但没有 env.py / 版本链)。加列只走 `katrain/web/core/migrations.py` 的 `add_missing_columns`(在模型上加一列可空列即可,它是幂等的 `ALTER TABLE ADD COLUMN`,SQLite / PG 双兼容)。本轮只有成长赛道 G2 加一列,其余三家零迁移。
5. **i18n**:四家都只写 `t('ns:key','中文默认')`,**本轮不改任何 `.po`**(并行改 11 份必冲突)。合并完统一交 `katrain-i18n-expert`,各赛道交付时附新增 key 清单。
6. **四图存档**:直播取屏 18 与新的直播列表屏、成长 22、设置 27、视觉 26,目录各不相同。重取前按 CLAUDE.md 跑**两次**比对排除抖动(canvas 屏抖动量级 ~4500 像素,DOM 屏 ~200)。
7. **两套构建**:四家只要碰了 `src/hooks/`、`src/api/`、`src/utils/`、`src/components/` 就必须 `npm run build` 与 `npm run build:kiosk-2d` 都绿;共享文件不许 import `src/kiosk/**`。

**合并顺序(默认)**:`kifu`(上一轮遗留) → **视觉** → **设置** → **成长** → **直播**。
理由:视觉改的是标定语义,设置屏要引用它的状态词;成长动数据库和云端,要按「先测试环境再生产」单独排期(见成长 PRD §7);直播要等 kifu 落地后才动 `KifuPage.tsx`。
例外:任一赛道里**不碰上面 1–4 条**的单个 Task 可以拆出来先合。

**每次合并前**:`git merge develop`,跑本赛道 plan 的 Global Constraints(两套构建 + `npx tsc -b` + 基线 diff),并对照本节查**语义**冲突 —— git 报「合得干净」不等于合得对。

### 6.1 本赛道会改、可能与别家重叠的文件

| 文件 | 本赛道改什么 | 可能重叠 |
|---|---|---|
| `katrain/web/ui/src/hooks/useSessionBase.ts`(**共享领地**) | ST1:发声前读 `audioPrefs('sfx')` | galaxy 研究页也用它(行为不变:它从不写这把键,缺键当开) |
| `katrain/web/ui/src/kiosk/pages/BaipuSessionPage.tsx` | ST1:快门声读同一把键 | **kifu 分支**改了这个文件(+180 行,摆谱流程重排)⇒ **先合 kifu** |
| `katrain/web/ui/src/kiosk/components/settings/KioskAiLadderDetail.tsx`(**新建**) | ST4 | 无 |
| `katrain/web/ui/src/kiosk/components/settings/AccountSection.tsx`(+`.test.tsx`) | ST4:去 MUI、就地展开、文案走 `t()` | 无 |
| `katrain/web/ui/src/kiosk/pages/SettingsPage.tsx`(+`__tests__/SettingsPage.test.tsx`) | ST5 | 无(视觉赛道不改这一屏) |
| `katrain/web/ui/src/kiosk/context/GeometryContext.tsx` | **不改**(只消费 `loaded` / `phase`) | **视觉赛道**归它改 |
| `katrain/web/ui/src/kiosk/KioskApp.tsx` | ST6:删两个 import 与两层包裹 | **kifu 分支**(路由段,hunk 不相邻) |
| `katrain/web/ui/src/kiosk/context/OrientationContext.tsx`、`components/layout/RotationWrapper.tsx`、`components/settings/PhysicalBoardStatus.tsx` 及四份测试 | ST6:删 | 无(零消费者) |
| `katrain/web/ui/src/features/aiLadder/*` | **不改** | galaxy |
| `katrain/web/api/v1/endpoints/health.py` | ST3-关于:响应加一个 `version` 键 | 无(其余三家不碰它) |
| `katrain/web/ui/src/kiosk/api/healthApi.ts`(**新建**) | ST3-关于:取 `/api/v1/health` | 无 |
| `katrain/i18n/locales/*/katrain.po` | **不改** | 全部 |

## 7. 验证方式

| 层 | 适用条目 | 做法 |
|---|---|---|
| 基线 diff | 全部 | 动手前跑全量 vitest 记失败用例**名字集合**;收尾再跑用 `comm` 比。ST6 删测试文件会让**条数**变少 —— 这正是「比名字不比条数」的理由。 |
| 单测 | ST1 ST4 ST5 | 见各条验收。 |
| parity 单测 | ST4 | 六种 `view_state` 下 kiosk 视图与共享卡用同一组 `AI_LADDER_COPY` 键(照抄 `KioskAiLadderOpponent.parity.test.tsx`)。 |
| 类型检查 | 全部 | `npx tsc -b`。ST6 删文件后若有残留 import,这一步会红。 |
| 两套构建 | ST1(共享领地)、ST6 | `npm run build` 与 `npm run build:kiosk-2d`。 |
| PO 闸 | ST4(新文案) | `npx playwright test --config=playwright.visual.config.ts tests/kiosk-shell-contract.spec.ts`。 |
| 四图对比 | **ST4 / ST3-关于 触发**(展开态是新的可见结构;「关于」是新的一组,导航与右栏都变了);ST5 只改状态文字,但它在屏 27 的正面 ⇒ 一并重取屏 27 | `npm run fourup`,跑**两次**排除抖动(屏 27 是 DOM 屏,底约 200 像素),四张一起看并**交 Fan 确认**。 |
| 承重结构实测 | ST4 | 展开 AI 段位详情是「会长的东西」:展开后量右栏 `scrollHeight > clientHeight` 且页面不横向溢出、左栏导航高亮仍指得对;再按「塌陷要在最空状态下量」量一次**未登录 / 无段位**那一态。jsdom 不作数。 |
| 承重结构实测 | **ST6** | `RotationWrapper` 是高度来源与裁切边界,不是透传层 ⇒ 删它属承重改动:改前改后在真浏览器里各量一次页面溢出与 `.kiosk-screen` 几何(见 §3 ST6 验收 3)。截图不能作证。 |
| 上板(建议,Fan 定时机) | ST1 ST5 | 盒上:关掉「落子音效」后去研究屏落子、去摆谱拍帧 —— 都不响;没接摄像头的机器上设置屏那一组说得对。RK3562 2G,一次只跑一家。 |
