# 平台选型调研报告 · 跨平台真人对弈

- **日期**：2026-07-12
- **分支**：`feature/kiosk-play-xplatform`
- **方法**：三轮 deep-research（多角度并行检索 → 抓取一手来源 → 每条断言 3 票对抗验证，2/3 驳回即淘汰 → 归组综合），共 ~330 个子代理、~70 条断言存活；关键承重结论（野狐官方下载页）由人工额外一手核实。
- **口径**：第一阶段主打**中国大陆**用户 → 最大的大陆真人对弈池在同分时胜出；**排除商务合作路径**（野狐/弈城/弈客最初按此排除，第三轮改为重点调研，因其大陆用户量最大）。

---

## 一、结论

**下一个对接【野狐围棋 / 腾讯围棋（FoxWQ）】。**

野狐同时满足三个条件，是最接近"像星阵一样顺利对接"的大陆平台：

1. **大陆最大真人对弈池**（约 3000 万用户，顶尖职业棋手 + 绝艺主场）——完全契合"第一阶段服务大陆"目标。
2. **有官方许可的自助接入通道**（非商务谈判）：官方可公开下载的 **FoxGTP 连接器**（GTP 协议，桥接 KataGo/LeelaZero 等第三方引擎）+ 客户端内自助开通「AI 认证」。结构上 = KGS 的 `kgsGtp` = 我们**已跑通的星阵 genmove 隧道**，现有 GTP 管线可复用，工程量最小。
3. **走官方 AI 认证路径封号风险低**，可持续；不像弈城需在 ToS 对立面运营 burner 账号。

### 一手核实（人工，非仅调研）

- 官方下载页 `https://www.foxwq.com/soft/aiprogramandmanual.html` 真实存在（HTTP 200）。
- 直链 `https://www.foxwq.com/Public/Soft/aiProgramAndManual.zip` 可下载（HTTP 200，`application/zip`）。
- 官方 AI 支持通道：`ai@foxwq.com` / QQ群 `727170525`。
- 注意：下载页本身只是入口，**GTP / 引擎协议细节在压缩包手册内**（见 §四 待验证项）。

---

## 二、总排序（大陆用户优先）

| # | 平台 | 大陆用户量 | 官方路径 | 非官方路径 | 封号风险 | 结论 |
|---|---|---|---|---|---|---|
| **1** | **野狐 / 腾讯围棋** (FoxWQ) | ⭐ 最大 ~30M | ✅ 官方 FoxGTP + AI认证（自助） | 有逆向参考(openfoxwq/qGo) | 官方=低 | **下一个就做** · 复用 GTP 管线 |
| **2** | **弈城** (eweiqi / Tygem 家族) | 第二 | ❓ 无官方通道 | ⚠️ qGo `TygemConnection`（已过期） | 高（封 AI + 连坐关联 ID） | 第二优先 · 先重验协议 |
| — | 星阵 Golaxy | AI 对弈 | ✅ 官方 REST | — | — | ✅ 已接入（人机） |
| — | OGS | 西方池 | ✅ 官方 OAuth2 | — | — | ✅ 已接入 |
| 3 | KGS | 大陆量小 | ✅ 官方 kgsGtp | — | 低 | 最干净但量小 · 留待 phase-2 国际化 |
| 4 | GoQuest（棋问） | 移动快棋 | ❌ 无 | 需逆向 socket.io | 中 | 需逆向 · 用户量不及前二 |
| 5 | 弈客 | 内容/直播为主 | ❓ 无公开 API | 无实现 · 需逆向 | 未知 | 实时对弈价值存疑 · 低优先 |
| 6 | IGS / Pandanet | 大陆量小 | telnet 协议 | — | 裁量封号无申诉 | 可行但政策风险不可控 |
| — | DGS / 新博 / 忘忧 / BadukPop / 99 | 小 / 细分 | 回合制 / 封闭 | 无从下手 | — | 形态不匹配或封闭 · 不投入 |

**可对接性图例**：官方 `open-api`（有公开 API/开放平台/自助）· `business-only`（仅商务）· `none`（无对外）；非官方 `ref-impl-exists`（有逆向参考可借鉴）· `needs-reverse`（需自行逆向）· `dead-end`（封闭无从下手）。

---

## 三、三家详情（官方 / 非官方双轴）

### 野狐围棋 / 腾讯围棋（第一优先）

- **用户量/定位**：大陆第一大在线围棋平台，约 3000 万用户（运营方北京野狐世纪）。顶尖职业与腾讯绝艺均在此对弈，是大陆最大、最核心的人类对弈池。
- **官方路径 = open-api（自助）**：foxwq.com 提供可公开下载的官方「AI 接入程序」（**FoxGTP**，GTP 协议，stdio/TCP 桥接第三方引擎）+ 使用手册；任意 **3D+ 账号**（新账号可自助调至 3D）在电脑客户端右上角开通「AI 认证」（填 `foxgtp`/`gtp` 并勾选协议）即可合法用 AI 对弈；官方支持 `ai@foxwq.com` / QQ群 `727170525`。**这是官方 GTP 连接器程序 + 自助授权，而非文档化 REST 开放平台**——是 KGS kgsGtp 模型，不是 OGS OAuth 模型。
- **先例辨析**：绝艺自 2016-11 在野狐公测 = 腾讯**自研 AI 的官方部署**先例，**不是第三方可接入的先例**；民间逆向先例是 openfoxwq / qGo。两类价值不同，勿混。
- **非官方路径 = ref-impl-exists（但无必要）**：`openfoxwq/api`（逆向代理，Basic Auth + 需 Discord 私下索取的 X-APP-ID/X-API-KEY，后端闭源，2024 已归档）、`openfoxwq/openfoxwq_client`（Flutter，MIT，依赖闭源代理）、Walrus Weiqi、WeiqiHub 等可借鉴但非开箱即用，且违反 ToS。**官方通道已开放 → 逆向不划算。**
- **封号风险**：走官方 AI 认证 = **低**（AI 对弈被明确合法化）。走民间逆向 = 高：用户协议 §7.2 禁未授权 AI/逆向/第三方软件登录，可永久封号。

### 弈城围棋（eweiqi / TongYang·Tygem 家族）（第二优先）

- **用户量/定位**：大陆主力平台之一，野狐崛起前的核心职业对弈服务器，中韩职业与高段基数大；现被野狐超越但仍为第二大大陆人类池。
- **官方路径 = unknown（实践近似 none）**：未发现任何官方开发者门户 / 公开 API / AI 认证通道。官方 ToS 限制注册（1 手机号≤3 账号等）并严禁假棋/枪手/助升段，判定后账号及**所有关联 ID 永久封号**——立场明显反自动化。
- **非官方路径 = ref-impl-exists（但已过期，须重验）**：`qGo`（pzorin/qgo，GPLv2 开源 Qt 客户端）在 `login.cpp` 实现独立的 `TygemConnection` 类（硬编码 `121.189.9.52:80` 明文 HTTP，韩国 IP）。**两个坑**：① qGo 把 Tygem 与 eWeiQi 视为两个独立连接类型，`TygemConnection` 指向**韩国 TongYang**，而弈城=eweiqi.com 是同族但独立的中国站点，未必 1:1 映射；② Issue #44 显示协议曾漂移致断连，**参考实现已过期，必须重新验证**。
- **封号风险 = 高**：ToS 明令禁 AI/AI 辅助/枪手/假棋，判定后账号及所有关联 ID 永久封号（连坐），注册数量受限。任何 AI/自动化接入均违规 → 需 burner 账号且先验协议再投入。

### 弈客围棋（Yikeweiqi）（低优先）

- **用户量/定位**：以围棋资讯 / 职业对局直播 / 死活题 / SGF 社区为主的大型 App；实时人类对弈池相对野狐/弈城更小、非平台核心场景。
- **官方路径 = unknown（倾向 none）**：官网首页仅消费者向条目（软件下载/弈客围棋/弈客少儿/弈课堂/五子棋/赛事合作），零提及开放平台/API/SDK/开发者；两轮检索均未发现开发者门户或 API 文档。不排除私下商务通道。
- **非官方路径 = needs-reverse**：未发现任何第三方客户端或逆向参考，需从零逆向。且实时对弈面价值存疑（重心在内容/直播/题库），接入**性价比低**。

### 其余（不投入）

- **KGS**：官方 kgsGtp（GTP 桥接）+ 排位需邮件申请 Ranked Robot（账号变 bot-only），封号风险低——是最规范的官方路径，但**大陆用户量小**，降为 phase-2 国际化。
- **GoQuest（棋问）**：需逆向 socket.io（`wars.fm:3002`），有参考实现 `github.com/mihhailnovik/questGo`，但 token 需从 App 流量取得；移动快棋池中等。
- **IGS/Pandanet**：telnet 协议可行（第三方 Electron 客户端可参考），但 ToS 给管理员**无申诉封号绝对裁量权**；大陆量小。
- **DGS**：回合制（邮件式），与实时对弈形态不匹配。
- **新博 / 忘忧 / BadukPop / 99 / 101**：封闭无接口或仅 HTML 抓取先例，无落子级逆向参考；规模不值，第一阶段不投入。
- **开源自建（govariants 等）**：变体/教学向、不成熟、无外部 bot/联邦；且 OGS 后端闭源，不能像 Lichess 整体自建。

---

## 四、动工前必须验证（头号未决问题）

> 这几条决定野狐是否真的是"干净的 KGS 等价路径"，**落地前必须拿到答案**。

1. **自动化边界**：官方 FoxGTP 手册允许**全自动 bot 对弈**，还是仅限**人在环的 AI 辅助**？
2. **账号限制**：开通「AI 认证」后账号是否被标记/限制为 `bot-only` 或仅非排位（类似 KGS Ranked Robot）？
3. **human-relay 定性**：我们的智能棋盘是**人在实体棋盘真实落子、程序转发**（human-relay），比 AI 对弈更"良性"——这种形态是否被野狐接受？
4. **协议细节**（手册内）：stdio 还是 TCP、握手流程、坐标与落子/提子格式、对局生命周期。
5. **商用授权**：用于商用硬件产品是否需额外授权或商务合作。
6. **使用限制**：账号段位/数量、并发对局数上限。

---

## 五、验证清单（用户配合）

1. ✅ 已有野狐账号 → 确认段位可自助调至 **3D+**（AI 认证前置）。
2. 下载 **FoxGTP 程序 + 使用手册**：`https://www.foxwq.com/Public/Soft/aiProgramAndManual.zip`（页面入口 `https://www.foxwq.com/soft/aiprogramandmanual.html`）。
3. 在电脑客户端右上角**开通「AI 认证」**（填 `foxgtp`/`gtp` 并勾选协议）。
4. 就 §四 的 human-relay 合规性 + 账号限制发邮件问 `ai@foxwq.com` / QQ群 `727170525`（咨询邮件草稿已备）。
5. 把手册（zip 内容）交给开发 → 据实际协议评估工程量、设计 GTP 适配器（复用 Golaxy 隧道架构）。

---

## 六、方法与局限

- **不可证伪的负面断言**："无公开 API / 未被逆向"只代表"公开渠道与检索未发现"，**不能证明确无**私下商务通道或未文档化的内部 HTTP/WS 协议（任何 App/网页平台必然有，只是未对外披露）。
- **野狐"官方"的性质**：是 GTP 连接器程序 + 自助授权，**非 REST 开放平台**，勿按 REST API 预期设计。
- **弈城 Tygem/eWeiQi 混同风险**：qGo 参考指向韩国 TongYang，与中国弈城 eweiqi.com 未必同协议，且已漂移过期，**推进前必须重新抓包验证**。
- **~30M 用户量**为多来源综合估算，非官方精确口径，仅作量级参考。
- **大陆可访问性未实测**：KGS/IGS 是否被墙/延迟须在 kiosk 设备侧验证（本机 Mac 测试因全局代理 + 伪 IP DNS 无效）。
- **时效**：平台 ToS 与连接器协议随版本变更（野狐 release note 显示协议随版本更新，旧版会失效），结论截至 2026-07 检索时点。
- **未覆盖**：99 围棋 / 爱思通 / 围棋宝典未产出可验证一手证据。

---

## 七、主要来源

**野狐**
- `https://www.foxwq.com/soft/aiprogramandmanual.html`（官方 AI 接入程序 + 手册下载页，一手核实）
- `https://www.foxwq.com/soft/userguide.html`
- `https://edu.foxwq.com/complex/useragreement.html`（用户协议 §7.2/§7.5）
- `https://github.com/openfoxwq/api` · `https://github.com/openfoxwq/openfoxwq_client` · `https://walruswq.com/foxwq-api`（民间逆向参考）

**弈城**
- `https://github.com/pzorin/qgo`（`src/network/login.cpp` 的 `TygemConnection`）
- `https://shop.eweiqi.com/article.php?id=6`（服务条款）

**弈客**
- `https://www.yikeweiqi.com/`

**参照系（已接入）**
- `https://github.com/online-go/gtp2ogs` · `https://docs.online-go.com/`（OGS）
- KGS：`https://www.gokgs.com/help/faq_en.html` · `https://www.weddslist.com/kgs/how/kgsGtp.html`

> 完整逐条证据（含被驳回断言）见本 session 的三轮调研任务输出：round-1 `wvrxdch1g`（西方平台）、round-2 `w61hdnel0`（中国/移动/自建）、round-3 `w0obpyd32`（野狐/弈城/弈客）。
