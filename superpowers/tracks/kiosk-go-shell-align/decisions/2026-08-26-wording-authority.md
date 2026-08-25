# 文案正本 · 裁定（2026-08-26）

## 裁定

**方向三，但不是「一条一条拍脑袋」——是一条默认规则加一类例外：默认 PO 是正本（31 条里 24 条把代码 fallback 改成 PO 那句）；例外只有一种形状，即「同一个 key 兼管两个概念」，那 7 条的修法是铸新 key，不是改 PO。全程一个 PO 条目都不动。**

---

## 理由

**① PO 是 galaxy 唯一的中文来源，代码 fallback 只是 kiosk 的第二套说法。**
争议的 20 个 `report:*` / `tsumego:*` key **每一个都有 galaxy 消费者**，而 galaxy 那边的 fallback 全是英文（`galaxy/components/report/ReportLibraryImportDialog.tsx:141` 写 `t('report:import_and_normal', 'Import & generate normal report')`；`galaxy/pages/TsumegoCategoriesPage.tsx:59` 甚至一个 fallback 都不给）。⇒ **改 PO = 改 galaxy 的中文；改 kiosk fallback = 屏上一个像素都不变，而且两套 UI 从此说同一句话。** 判哪边对之前，先看清哪边改动会波及别人：PO 那边会。

**② 逐条查完，PO 说得对的是压倒性多数，而且它对在事实上、不是对在好听上。**
最典型的三条：
- `report:territory`（`kiosk/pages/ReportDetailPage.tsx:498`）那颗键 `onClick` 翻 `showTerritory`，而 `:350` 把它喂给 `ownership={showTerritory ? ownership : null}`，`:495` 还写着 `disabled={!ownership}`——**它开的就是 ownership 色块**。PO 说「领地」，代码说「形势」。**PO 对。** 而且同一个概念在仓里已经有**三处独立收敛到「领地」**：`Territory`→领地、`live:territory`→领地、`report:territory`→领地，只有屏 20 这一处写「形势」是孤例。
- `report:deep` / `report:normal`：kiosk 自己把两个词分得很清——`shell/dockRoutes.ts:25` 的 Dock 标签是「**复盘**」（模块名），而 `pages/ReportsPage.tsx:602` 的组标题是「生成**报告**」、`:744` 的键是「查看**报告**」（产物名）。PO 说「深度报告 / 普通报告」，正落在产物那一侧；代码 fallback 说「深度复盘」，等于在「生成报告」这一组里管产物叫模块名。**PO 对。**
- `tsumego:selectCategory`：`pages/TsumegoCategoriesPage.tsx:22` 的 `CATEGORY_ICONS` 列的是 `life-death` / `tesuji` / `endgame`——死活、手筋、官子，这是**题型**不是泛指的「分类」。PO 说「选择题型」。**PO 对。**

**③ 剩下那 7 条，两边说的都对——错的是「一个 key 兼管两件事」，所以两边都不该改，该铸新 key。**
`Territory` 在 kiosk 有 5 个消费者：`components/game/GameControlPanel.tsx:244`（`key:'ownership'`）、`:298`（`kind:'area'`）、`pages/GamePage.tsx:523`（`area:`）三处都要「领地」，只有 `pages/AiSetupPage.tsx:458` 的 `{ value:'ai:territory' }` 要的是**AI 棋风**、和隔壁 `Influence`→「厚势」配对，那一侧的行话是「实地」。同理 `Live` 在 `pages/LivePage.tsx:142` 是页标题「直播」、在 `:81` 是只在 `status==='live'` 时才渲染的状态 chip（要「直播中」）；`Black`/`White` 在 `GameControlPanel.tsx:129` 是**人名占位**（黑棋/白棋，`components/game/PlatformTimer.tsx:105` 已经这么写了），在 `GamePage.tsx:127`「提子 黑 3 / 白 5」和 `TsumegoProblemPage.tsx:587`「黑 D4」是**紧凑内联**（要单字）。**这正是「一个 prop 兼管两件事，逼调用方撒谎」的字符串版本**——为了让棋风说「实地」，调用方被迫去改一个四处在用的「领地」。

**④ 那张清单我逐条重跑核实过了，是**当前**的、不是过期的——但守着它的那条闸有个洞在别处。**
拿闸四同样的算法重扫了一遍 `src/kiosk`，得到的 31 条与 `tests/kiosk-shell-contract.spec.ts:305-340` 的 `PO_OVERRIDES_DEFAULT_BASELINE` **逐字相同**（我另跑了一版放宽到跨行 `t(` 调用的扫描，`GATE-MISS` 数 0，所以那条闸的单行正则目前没漏）。**真正过期的是别处的散文**：`tests/kiosk-screen-20-report.fourup.spec.ts:129` 的批注写「实现跟着『形势 / 手数』两个开关走」——四图那张截图里那颗键**其实印的是「领地」**（四图跑真服务器、不挡 `/api/translations`）。

**⑤ 拿代码 fallback 当正本的那条路，还得先把一批「证明了断路」的测试一起拆掉。**
`tests/report-kiosk.spec.ts:140` 是 `const TRANSLATIONS: Record<string, string> = {}`，`:166` 拿它整个顶掉 `/api/translations`。于是 `:491`/`:497`/`:516`/`:520` 断言「导入并生成普通复盘」、`:546` 断言开关叫「形势」——**这五处断言的字符串设备上从来没出现过**，测试只是在给自己造的空目录发通行证。选方向二（改 fallback 跟 PO）这些断言自然要改；选方向一（改 PO 跟代码）则等于把这批假证据扶正。

---

## 逐条清单

判据栏：**PO** = 采用 PO 那句、改代码 fallback；**新键** = 两边都对但撞概念，铸 kiosk 自己的 key。

| # | 文件:行 | key | PO 说 | 代码说 | 哪边对 | 为什么 |
|---|---|---|---|---|---|---|
| 1 | `src/kiosk/components/game/GameControlPanel.tsx:129` | `Black` | 黑棋 | 黑方 | **PO** | 这里是 `info.name` 缺失时的**人名占位**；同文件族的 `PlatformTimer.tsx:105` 已经写 `t('Black','黑棋')`。一个概念一套词。 |
| 2 | 同上 | `White` | 白棋 | 白方 | **PO** | 同上。 |
| 3 | `src/kiosk/components/report/ReportImportMenu.tsx:57` | `report:import_local` | 从本地导入 SGF | 导入本地 SGF | **PO** | 两句都真（en「Import local SGF」）。平局按默认规则归 PO——galaxy 的 `ReportImportMenu.tsx:32`、`ReportLocalImportDialog.tsx:88` 也吃这一条。 |
| 4 | `src/kiosk/components/report/ReportLibraryImportDialog.tsx:259` | `report:import_and_deep` | 导入并生成深度报告 | 导入并生成深度复盘 | **PO** | 产物叫「报告」（`ReportsPage.tsx:602` 组标题「生成报告」/`:744`「查看报告」），「复盘」是 Dock 上的模块名（`dockRoutes.ts:25`）。 |
| 5 | `…ReportLibraryImportDialog.tsx:256` | `report:import_and_normal` | 导入并生成普通报告 | 导入并生成普通复盘 | **PO** | 同 #4。 |
| 6 | `…ReportLibraryImportDialog.tsx:253` | `report:importing` | 导入中... | 正在导入… | **PO** | 两句都真。平局归 PO。（PO 用的是 ASCII `...`，见「遗留项」。） |
| 7 | `…ReportLibraryImportDialog.tsx:162` | `report:loading` | 加载中... | 正在加载 | **PO** | 两句都真（这是 `CircularProgress` 的 `aria-label`）。平局归 PO。 |
| 8 | `…ReportLibraryImportDialog.tsx:172` | `report:no_results` | 没有搜索到棋谱。 | 没有找到棋谱。 | **PO** | 这个空态只出现在**搜索之后**（`:140` 是搜索框）。PO 那句多说了「为什么空」，更贴事实。 |
| 9 | `…ReportLibraryImportDialog.tsx:140` | `report:search_placeholder_lib` | 按棋手、赛事、日期搜索 | 搜索棋手、赛事或日期 | **PO** | 两句都真（en「Search by player, event, date」）。平局归 PO。 |
| 10 | `src/kiosk/components/report/ReportLocalImportDialog.tsx:309` | `report:choose_file_hint` | 选择本地 SGF 文件，或直接粘贴 SGF 内容。 | 可选择文件，也可直接粘贴 SGF 内容。 | **PO** | en 原句是「Select a local SGF file, or paste SGF content directly.」，PO 是忠译；代码那句把「本地 SGF」缩成了「文件」，信息更少。 |
| 11 | `…ReportLocalImportDialog.tsx:376` | `report:import_and_deep` | 导入并生成深度报告 | 导入并生成深度复盘 | **PO** | 同 #4。 |
| 12 | `…ReportLocalImportDialog.tsx:373` | `report:import_and_normal` | 导入并生成普通报告 | 导入并生成普通复盘 | **PO** | 同 #4。 |
| 13 | `…ReportLocalImportDialog.tsx:270` | `report:import_local` | 从本地导入 SGF | 导入本地 SGF | **PO** | 同 #3。 |
| 14 | `…ReportLocalImportDialog.tsx:370` | `report:importing` | 导入中... | 正在导入… | **PO** | 同 #6。 |
| 15 | `src/kiosk/pages/AiSetupPage.tsx:458` | `Territory` | 领地 | 实地 | **新键** | **代码的概念对、key 选错了。** 这一项是 AI **棋风** `ai:territory`，和隔壁 `Influence`→「厚势」配对，行话是「实地」。而 `Territory` 这个 msgid 在 kiosk 另有三个消费者全指 ownership 色块（`GameControlPanel.tsx:244`/`:298`、`GamePage.tsx:523`），都要「领地」。⇒ 铸 `setup:style_territory`。 |
| 16 | `src/kiosk/pages/GamePage.tsx:127` | `Black` | 黑棋 | 黑 | **新键** | 「提子 黑 3 / 白 5」要的是**单字**；`Black` 已被 #1 的人名占位占用。⇒ 铸 `game:black_short`。 |
| 17 | 同上 | `White` | 白棋 | 白 | **新键** | 同 #16 ⇒ `game:white_short`。 |
| 18 | `src/kiosk/pages/LivePage.tsx:81` | `Live` | 直播 | 直播中 | **新键** | 这颗 chip 只在 `selectedMatch.status === 'live'` 时渲染（`:78`），说的是**进行中**；而同文件 `:142` 的页标题用同一个 key 要的是「直播」，galaxy 导航 `galaxyNavigation.tsx:26` 也是「直播」。⇒ 铸 `live:status_live`。 |
| 19 | `src/kiosk/pages/ReportDetailPage.tsx:112` | `report:deep` | 深度报告 | 深度复盘 | **PO** | 同 #4。 |
| 20 | `…ReportDetailPage.tsx:283` | `report:login_required_detail` | 请先登录后查看报告详情。 | 请登录后查看复盘详情。 | **PO** | en「view report details」，宾语就是报告；同 #4 的词。 |
| 21 | `…ReportDetailPage.tsx:307` | `report:no_sgf` | 没有可用于复盘展示的 SGF 数据。 | 暂无棋谱数据，无法复盘。 | **PO** | 两句都真。平局归 PO（galaxy `pages/report/ReportDetailPage.tsx:221` 同键）。 |
| 22 | `…ReportDetailPage.tsx:113` | `report:normal` | 普通报告 | 普通复盘 | **PO** | 同 #4。 |
| 23 | `…ReportDetailPage.tsx:498` | `report:territory` | 领地 | 形势 | **PO** | **这一条是判据本身。** 那颗键 `:350` 喂的是 `ownership`、`:495` 按 `!ownership` 置灰——开的就是 ownership 色块 ⇒ 叫「领地」。仓里另两处同义键（`Territory`、`live:territory`）也都是「领地」。 |
| 24 | `…ReportDetailPage.tsx:80` | `report:unknown_status` | 未知状态 | 状态未知 | **PO** | 两句都真。平局归 PO。 |
| 25 | `src/kiosk/pages/ReportsPage.tsx:668` | `report:delete_confirm_body` | 删除后棋局及所有关联分析数据将不可恢复，确认删除？ | 删除后将无法恢复，关联复盘数据也会一并删除。 | **PO** | **两句都属实**——`core/models_db.py:733-734` 上 `analysis_records` 和 `report_tasks` 都是 `cascade="all, delete-orphan"`，`core/user_game_repo.py:333` 一句 `session.delete(game)` 确实连着分析数据一起删。PO 那句用的是「分析数据」（和 #4 的词一致），代码那句用「复盘数据」。 |
| 26 | `src/kiosk/pages/ReportsPage.tsx:665`、`:667` | `report:delete_confirm_title` | 确认删除 | 确认删除棋谱 | **PO + 换按钮键** | 代码写长是为了躲一个**真碰撞**：同一个对话框 `:679` 的危险键 `report:confirm_delete` 是 kiosk 自铸的、PO 里没有，fallback 也是「确认删除」⇒ 采用 PO 后标题和按钮会同字。修法不是把标题写长，是**按钮改用 galaxy 已有的 `report:delete_game`**（PO=「删除棋局」，galaxy `pages/report/ReportsPage.tsx:610` 就是这么用的），标题回到 PO 的「确认删除」。见「需要 Fan 回答的」第 2 条。 |
| 27 | `src/kiosk/pages/ReportsPage.tsx:399` | `report:login_required` | 请先登录后查看和生成复盘报告。 | 请先登录后查看复盘。 | **PO** | 这一屏**确实又看又生成**（`:602` 就是「生成报告」那一组）。代码那句说少了。 |
| 28 | `src/kiosk/pages/TsumegoCategoriesPage.tsx:117` | `tsumego:selectCategory` | 选择题型 | 选择分类 | **PO** | 列的是 `life-death`/`tesuji`/`endgame`（`:22` 的 `CATEGORY_ICONS`）——死活/手筋/官子，是题型。而且 galaxy `pages/TsumegoCategoriesPage.tsx:59` 用这个 key **不带 fallback**，PO 是它唯一的中文来源。 |
| 29 | `src/kiosk/pages/TsumegoProblemPage.tsx:587` | `Black` | 黑棋 | 黑 | **新键** | 手数表里「黑 D4」，同 #16 ⇒ 复用 `game:black_short`。 |
| 30 | 同上 | `White` | 白棋 | 白 | **新键** | ⇒ 复用 `game:white_short`。 |
| 31 | `src/kiosk/utils/setupOptions.ts:25` | `Byoyomi only 30s x3` | 仅读秒 | 仅读秒 30秒×3 | **新键** | **msgid 自己就带着「30s x3」，而 en 译文是「Byo-yomi only」——PO 两侧都把秒数丢了。** 同一张表其余六档（`5 min + 3x30s` 等）**都不在 PO 里**、fallback 直接生效，全都写着几分几秒；只有这一档被 PO 削平，一条 −/＋ 轨上出现一个不说秒数的档 ⇒ 铸 `setup:time_byo_only`。 |

小计：**24 条改 fallback 跟 PO**（含 #26 的标题），**7 条走新键**（#15/16/17/18/29/30/31，共 **5 个新 key**）。

---

## 要改的话，具体改什么

### A. 24 处：把代码 fallback 原字照抄成 PO 那句（**只动 `.tsx`/`.ts`，PO 一个字不改**）

涉及 **9 个源文件**：
```
src/kiosk/components/game/GameControlPanel.tsx        #1 #2      黑方/白方 → 黑棋/白棋
src/kiosk/components/report/ReportImportMenu.tsx      #3
src/kiosk/components/report/ReportLibraryImportDialog.tsx  #4-#9
src/kiosk/components/report/ReportLocalImportDialog.tsx    #10-#14
src/kiosk/pages/ReportDetailPage.tsx                  #19-#24
src/kiosk/pages/ReportsPage.tsx                       #25 #26 #27
src/kiosk/pages/TsumegoCategoriesPage.tsx             #28
```
逐条的目标字面量见上表「PO 说」栏，**一字不改地照抄**（含 PO 的 ASCII `...` 和全角逗号——要改标点是另一件事，见「遗留项」）。

### B. 5 个新 key（**不进 PO**，理由见 C）

| 新 key | 中文 fallback | 替换掉 | 位置 |
|---|---|---|---|
| `setup:style_territory` | 实地 | `t('Territory','实地')` | `pages/AiSetupPage.tsx:458` |
| `game:black_short` | 黑 | `t('Black','黑')` | `pages/GamePage.tsx:127`、`pages/TsumegoProblemPage.tsx:587` |
| `game:white_short` | 白 | `t('White','白')` | 同上 |
| `live:status_live` | 直播中 | `t('Live','直播中')` | `pages/LivePage.tsx:81`（`:142` 的页标题**保持** `t('Live','直播')`） |
| `setup:time_byo_only` | 仅读秒 30秒×3 | `t('Byoyomi only 30s x3', …)` | `utils/setupOptions.ts:25` |

外加 #26 的一处**换键**（不是新键）：`pages/ReportsPage.tsx:679` 的 `t('report:confirm_delete','确认删除')` → `t('report:delete_game','删除棋局')`，与 galaxy 对齐。

### C. 11 种语言怎么办：**这一版一条都不用碰**

- 方案 A/B **不改任何 PO 条目**，所以 `cn/de/en/es/fr/jp/ko/ru/tr/tw/ua` 十一份 `.po` 全部原封不动，`i18n.py` 也不用跑。
- 新键**故意不进 PO**，跟 kiosk 本轮已有的 `setup:*` / `settings:*` / `review:*` 三族一个待遇——那三族在 cn PO 里**各 0 条**（`grep -c 'msgid "settings:'` = 0，`setup:` = 0，`review:` = 0），整屏跑的就是 fallback。进 PO 的门槛应当是「galaxy 或桌面端也要用这句」，这 5 条只有围棋 kiosk 一个消费者。
- **假如**将来要把某条塞进 PO：`i18n.py:125` 是 `sys.exit(int(errors))`，而 `.github/workflows/test_and_build.yaml:59` 跑 `uv run python i18n.py -todo`。只往 `cn` 加一条 msgid ⇒ 「found as … but missing in default en」⇒ **CI 直接红**。正确流程是 en+cn 各加一条、本地跑一次 `uv run python i18n.py`（它会把 en 那条带 `TODO` 注释复制进其余 9 份并落盘），**把 11 份 `.po` 一起提交**，第二次跑才干净。`es` 在 `i18n.py:19` 的 `INACTIVE_LANGS` 里，不参与。
- **改一条已存在的 cn msgstr 是便宜的**（msgid 各语言都已存在 ⇒ `i18n.py` 不报 error、CI 不红），但它会**同时改掉 galaxy 的中文**——这正是本裁定不走那条路的原因，不是因为它贵。

### D. 闸和测试要跟着动（这部分不改会红）

1. `tests/kiosk-shell-contract.spec.ts:305-340` 的 `PO_OVERRIDES_DEFAULT_BASELINE` 是 `toEqual` 双向棘轮——31 条**全部删掉**，只留一个空数组（或把 `expect` 连同名单一起收成 `toEqual([])`）。**修好了不划账一样红**，这是它的设计。
2. `tests/report-kiosk.spec.ts` 那五处断言的是被 `:140` 空 `TRANSLATIONS` 顶出来的 fallback：`:491`/`:497`（「导入并生成普通复盘」）、`:516`/`:520`（「导入并生成深度复盘」）、`:546`（开关「形势」）。改完 A 之后这些字面量要跟着改。
   **更该做的是把 `:140` 那个空字典换成真 PO 的子集**——否则这条 e2e 永远在验一条设备上不存在的路径。
3. `src/kiosk/components/report/ReportImportMenu.test.tsx:43` 断言「导入本地 SGF」（jsdom，翻译表本来就不加载 ⇒ 恒等于 fallback），跟着 #3 改。
4. `tests/kiosk-screen-20-report.fourup.spec.ts:129` 那句批注里的「形势 / 手数」是**过期的断言散文**，顺手改成「领地 / 手数」。

### E. 一个与本裁定无关、但顺路查出来的部署洞（建议单独修，不要塞进这一版）

`.gitignore:43` 是 `*.mo`，只有 `.po` 进仓（`git ls-files katrain/i18n/locales/cn/LC_MESSAGES/` 只有 `katrain.po`）。而 `Dockerfile.web` 只有一句 `COPY . /app`（第 12 行）、**没有 `RUN python3 i18n.py`**。⇒ 在一份干净 checkout 上构建，容器里没有 `.mo`，`katrain/core/lang.py:59` 的 `gettext.translation(...)`（没带 `fallback=True`）会抛，`server.py:2172` 的 `/api/translations` 500，前端 `src/i18n.ts:28` catch 掉 ⇒ **全站退回代码 fallback**。
也就是说，**今天「PO 赢还是代码赢」取决于构建上下文里有没有一个 gitignored 的产物**。本裁定把两边统一之后这件事不再影响屏上的字，但那条 500 仍然该修（`Dockerfile.web` 加一行 `RUN python3 i18n.py`，或给 `gettext.translation` 加 `fallback=True`）。

### F. 遗留项（本裁定**不**处理，登记备查）
- PO 里 `report:importing`/`report:loading` 用 ASCII `...`。中文 UI 该用 `…`。这是**排版**不是**真伪**，且要改就得连 galaxy 一起改 ⇒ 单独一轮 cn-only 标点整理。
- `en` PO 里 `report:confirm_delete` 不存在、`report:delete_confirm_body` 的 en msgstr 靠多行续写（`en/…/katrain.po:2536-2539`）。en 环境下 kiosk 有若干位置会掉进**中文 fallback**——独立问题，与本裁定无关。

---

## 需要 Fan 本人回答的（2 条）

**1. 围棋 kiosk 本轮新写的三族文案（`setup:` / `settings:` / `review:`，cn PO 里各 0 条）要不要补进 PO？**
不补 = 这些屏**只有中文**，换语言不跟着变（现状就是这样，且本裁定的 5 个新 key 按这个惯例办）；补 = 每条要过 11 种语言、每次加 key 都得跑 `i18n.py` 并提交 11 份 `.po`，否则 CI 红。**这是唯一没法从代码里读出答案的地方**——它决定「以后新键往哪边写」。

**2. 屏 19 删除对话框里，那个被删的东西叫「棋局」还是「对局」？**
我的方案是标题收成 PO 的「确认删除」、危险键改用 galaxy 已有的 `report:delete_game`（PO=「**删除棋局**」）。但同屏 `ReportsPage.tsx:474` 的组标题是 `review:sec_games`→「历史**对局**」，而「棋谱」是屏 15 那一族的词。三个词现在同屏并存，需要定一个。
