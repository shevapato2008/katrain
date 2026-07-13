# 设置页硬化:设备名脱敏 + 蓝牙音频输出 — Plan

**Date:** 2026-07-13
**Status:** Design locked, not started
**Repo touched:** 主要 `smartbox-software`/setup-wizard + provisioning;katrain 侧只是音频消费方(无需改)
**Confirmed decision (user, 2026-07-13):** 蓝牙要**真正支持音频输出**(配对 AirPods,把本机语音提示 + 棋声路由到耳机),不是只修显示。

Related: [audio stack + bluetooth investigation, this session]。Mockup-first + superpowers-plan per user pref;语言中文默认(见 [[feedback_language_zh_en]] / kiosk i18n 架构)。

---

## 1. Why

两个"设置页"问题:

- **① 蓝牙列表全是 MAC**:用户找不到近在咫尺的 AirPods 是哪一个。根因两层 —(a) 这页当初只为**键鼠(HID)**设计,会主动排斥音频设备;(b) BlueZ 被动扫描下,没解析到真名时 `Alias` 会自动编成一串 **MAC 样子的字符串**,取 `Name or Alias` 的兜底反把"假名字"当真名显示。AirPods 不在配对模式时只广播 Apple Continuity(无标准 Name 字段),被动扫描永远拿不到名。用户真实诉求 = **配对 AirPods 当音频输出**(把物理对弈语音 / 棋声送到耳机)。
- **② 关于本机显示 "gzpeite"**:泄露主板厂商(广州佩特)。根因 = 直接把 **Linux 主机名**当设备名显示,而这台开发板 hostname 仍是厂商出厂默认 `gzpeite`。

## 2. Current state (grounded)

### 音频栈 —— 关键纠偏:A2DP 能力**真机已具备**(厂商镜像自带),但 provisioning 没装
真机探测(`ssh rk3562-direct`,2026-07-13):
- `pulseaudio 14.2` 在跑(root 系统级)+ `pactl` + **`pulseaudio-module-bluetooth 14.2`(A2DP 模块,已装)** + `bluez 5.55`(active/enabled)+ `blueman 2.1.4`(状态 `hi`=held)+ XFCE 桌面(`xfce4-pulseaudio-plugin`)。
- ALSA:card0 = `rockchiprk809`(板载 DAC),card1 = `HBV HD CAMERA`(USB 麦)。内核 `bluetooth`/`btusb` 已加载。
- chromium 进程参数扫到 `--mute-audio` 与 `autoplay-policy=...`、`--incognito`、`--kiosk`、`--no-sandbox`(需核实主渲染进程是否真被静音)。
- **provisioning 未安装任何音频服务器 / BT 音频模块** —— 仅 `configure_bluetooth()`(`provision.sh:933-941`)设 `AutoEnable=true` + `systemctl enable --now bluetooth`;音量走 `amixer -c 0 sset DAC`(`services/system.py:61-65`,绕过 pulseaudio)。

→ **结论:不是"从零搭栈",是"打通集成"。** 硬基建(sound server + A2DP module)已在,但**金板不该赌厂商镜像**,provisioning 要显式化。

### 现有蓝牙配对功能(HID 专用,会拒音频设备)
- 后端:`setup-wizard/app/services/bluetooth.py`,`DbusBackend` 用 `dbus_fast` 打 `org.bluez`(mock 后端供 dev,`BT_BACKEND` 选)。扫描 `StartDiscovery()`(`do_scan` 790,**无 SetDiscoveryFilter**)。
- 标签:`_raw_to_device_info`(159)`name = raw.get("name") or raw.get("alias") or ""` —— BlueZ 未解析名时 `Alias` = MAC 形字符串,兜底反显 MAC。
- 分类:`_classify`(89-115)→ keyboard/mouse/hid/unknown_type/other。
- 过滤:`list_devices(hid_only=True)`(229-235)默认丢弃 `type=="other"` → 音频设备今天根本**不进列表**。
- 授权:`authorize_service`(359-370)`AuthorizeService` Agent 回调**拒绝**非 HID 白名单 UUID。
- 白名单:`config.py:45` `BT_ALLOWED_SERVICE_UUID_FRAGMENTS = ("1124","1812")`(仅 HID / HID-over-GATT)。
- 前端:`static/js/bluetooth.js:94` `name.textContent = device.name || device.address`(同款兜底 anti-pattern)。文案 `i18n.py:52` "连接键盘或鼠标"。
- 无任何 friendly-name / alias 映射;无 default-sink / 音频路由逻辑。

### 关于本机
- 后端:`services/system.py:87-99` `system_info()` → `hostname = socket.gethostname()`;路由 `routers/system.py:51-53` `GET /api/system/info`。**全仓库无 DMI / board_vendor / product_name 读取。**
- 前端:`templates/settings/index.html:281` 与 `static/js/settings.js:122` 均 `info.hostname + " · 智星盒 v" + info.version` → 现显示 `gzpeite · 智星盒 v1.0.0`。
- provisioning:`smartbox-firstboot.sh:36-54` `set_unique_hostname()` 本应改成 `smartbox-<mac6>`;golden-image track 记录该板被**手动改回 `gzpeite`** 做开发。

## 3. Desired end state
- **① 蓝牙**:设置→蓝牙能扫到 AirPods 并显示**真实名称**(拿不到名时显示"解析中…"而非 MAC);提示"把 AirPods 放进配对模式";配对成功后**音频自动路由到耳机**(本机语音提示 + 棋声从耳机出),断开自动回板载喇叭;蓝牙音量可调。
- **② 关于本机**:显示品牌名(如 "智星盒 · v1.0.0"),**永不暴露原始 OS 主机名**;需要机器标识时用 MAC 派生编号。provisioning 保证量产设备 hostname 也不是 `gzpeite`。

## 4. Tasks(分阶段)

### Phase 0 — Mockups(先出图,签字后再写码)
- frontend-design 出两张 mockup:(a) 关于本机卡片(品牌化、无原始 hostname);(b) 蓝牙页显示音频设备 + 真实名 / "解析中…" + 配对模式提示 + 已连耳机的音量/断开。7" 1024×600、智星盒外框、中文默认。
- **Gate:** 用户确认后进 Phase 1+。产出 artifact 链接。

### Phase 1 — 设备名脱敏(最小、独立可先发)
- 后端 `services/system.py:system_info()`:新增 `display_name` 字段 —— `hostname.startswith("smartbox-")` 时可用派生编号,否则回退品牌占位("智星盒");**不再把原始 hostname 直接外显**(hostname 仍保留在 API 供诊断)。
- 前端两处 `info.hostname + " · 智星盒 v"` → 改用 `info.display_name`(`templates/settings/index.html:281`、`static/js/settings.js:122`)。用户那行变 "智星盒 · v1.0.0"。
- provisioning:确认 `smartbox-firstboot.service` gate 正确(`ConditionPathExists=!/var/lib/smartbox/firstboot.done`)、`set_unique_hostname()` 一定在 setup-wizard 起前跑,量产设备诊断 hostname 也是 `smartbox-<mac6>` 而非 `gzpeite`。
- 单测:`system_info()` 在 hostname=`gzpeite` / `smartbox-xxxx` 两种下的 `display_name` 断言。

### Phase 2 — 蓝牙:让音频设备可见 + 名字解析(配对面)
- 白名单 `config.py:45` 增 A2DP/AVRCP:`110B`(A2DP Sink)、`110D`(Audio Sink profile)、`110E`(AVRCP),可选 `111E`(HFP,若要用耳机麦)。
- `_classify`(`bluetooth.py:89`):新增 `"audio"` 类型 —— icon `audio-headphones`/`audio-card`、CoD major class `0x04`(Audio/Video)、appearance / UUID 命中。
- `list_devices` 调用点:蓝牙页改为**同时展示 audio 设备**(不再只 `hid_only=True`);UI 分组"音频设备 / 键鼠"。
- `authorize_service`(359):对 audio UUID 放行。
- **名字解析**:
  - `do_scan` 前 `SetDiscoveryFilter({"Transport":"auto","DuplicateData":true})` → 持续重处理广播,提升名解析概率。
  - `_raw_to_device_info`(159):检测 `alias` 是否等于 `address` 的 MAC 形(去分隔符比对)—— 相等则视 name 为空,前端显示"解析中…"(已有 `PropertiesChanged` on Name/Alias 订阅,解析到真名会自动刷新行)。
  - 前端加"请把 AirPods 放进配对模式(长按至白灯闪烁)再扫描"提示(已有 `bt.hint_proximity` 可复用/扩写)。
- i18n:新增音频相关静态串走 katrain-i18n-expert(11 语);运行时不入库的动态名不译。
- 单测:audio 设备分类 / 出现在列表 / MAC-alias→"解析中" / 授权放行。

### Phase 3 — 蓝牙:音频路由(输出面)
- 连接成功(`Connected` + A2DP profile 就绪)后:把该 BT sink 设为 **pulseaudio 默认 sink**(`pactl set-default-sink <bt_sink>` + `pactl list short sink-inputs` 逐个 `move-sink-input` 到 BT)。断开 → 回 `rockchiprk809` 板载 DAC。新增路由逻辑(后端 service,调用 pactl;确认 setup-wizard 进程 uid 能触达 root 系统级 pulseaudio,必要时 `sudo -u`/`PULSE_SERVER`)。
- **音量**:BT sink 用 pulseaudio sink 音量(`pactl set-sink-volume`),不用 `amixer DAC`(那只控板载 codec)。设置页音量控件按当前默认 sink 分流(BT 时走 pulseaudio,板载时可继续 amixer 或统一走 pulseaudio)。
- **核实 chromium 音频**:确认主渲染进程**没有** `--mute-audio`(否则 web audio 全哑,蓝牙也没声);确认 chromium 走 pulseaudio(已装 libpulse;pulseaudio 在跑)。若发现主进程被静音,改 `smartbox-kiosk.service` 启动参数。
- 设备验证:真机配 AirPods,播放物理对弈语音 + 落子声,确认从耳机出;断开回喇叭;音量可调。

### Phase 4 — provisioning 显式化(金板不赌厂商镜像)
- `provision.sh` 音频 section:显式 `apt-get install` 保证 `pulseaudio`、`pulseaudio-module-bluetooth`、`pulseaudio-utils`、`alsa-utils`、`blueman`(取消 hold);配置 pulseaudio 系统模式(现状 root 系统级)+ 默认路由;`configure_bluetooth()` 之外确认 A2DP profile 默认可用。
- README 记:BT 音频依赖清单 + 默认 sink 行为 + chromium 非静音要求。

### Deploy
- setup-wizard 侧 rsync `app/`(含 `services/bluetooth.py`、`config.py`、`services/system.py`、`templates/`、`static/js/`)、重启 `setup-wizard`;provisioning 变更纳入 golden image。katrain 无需改(音频是它经 chromium 播的静态文件,默认 sink 一切它自动跟随)。

## 5. Risks / open questions
- **pulseaudio 以 root 系统级跑**(非常规):`pactl` 需正确 `PULSE_SERVER` / uid,setup-wizard 调用要验证权限路径。
- **AirPods 名解析**:非配对模式的 Continuity 广播无 Name,可能始终"解析中…"—— 靠配对模式提示兜底;可评估"发现即 best-effort connect 读 GATT 0x2A00 名"作为增强(更重)。
- **chromium `--mute-audio`**:先核实;若主进程静音,是"连喇叭都没声"的更基础 bug,优先修。
- **blueman held**:`hi` 状态,provisioning 里 `apt-mark unhold` 或忽略(我们走 pactl,不一定需要 blueman GUI)。
- **amixer vs pulseaudio 音量并存**:统一到 pulseaudio 更干净,但要保证板载路径回归时音量控件仍工作。

## 6. Verification checklist(完工判据)
- [ ] 关于本机不再显示 `gzpeite`,显示 "智星盒 · v1.0.0";量产 firstboot 后诊断 hostname 也非 gzpeite。
- [ ] 蓝牙页能看到 AirPods,显示真实名(或"解析中…"而非 MAC);有配对模式提示。
- [ ] 配对 AirPods 成功,物理对弈语音 + 落子声从耳机出;断开自动回喇叭;蓝牙音量可调。
- [ ] chromium 主进程非静音、走 pulseaudio(已核实)。
- [ ] provisioning 显式装齐音频 / BT 依赖;金板不依赖厂商镜像自带。
- [ ] setup-wizard 单测绿;真机 AirPods 端到端通过。
