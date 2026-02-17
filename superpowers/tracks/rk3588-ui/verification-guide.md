# RK3588 Kiosk UI Verification Guide

> Manual verification steps for each phase, on both MacBook (dev) and RK3588 (target device).

## Prerequisites

### MacBook

```bash
cd katrain/web/ui
npm install
npm run dev          # Dev server at http://localhost:5173
```

Chrome kiosk mode (optional, for kiosk 体验验证):

```bash
/Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome \
  --kiosk --noerrdialogs --disable-infobars \
  http://localhost:5173/kiosk/
```

用 `Cmd+Q` 退出 kiosk 模式。

模拟目标分辨率: Chrome DevTools (`Cmd+Option+I`) → Device Mode → 自定义 `1024x600`。

### RK3588

```bash
cd katrain/web/ui
npm install
npm run dev -- --host 0.0.0.0   # 局域网可访问
```

Firefox kiosk mode:

```bash
firefox --kiosk http://localhost:5173/kiosk/
```

用 `Alt+F4` 退出 kiosk 模式。

> **注意:** RK3588 上 Chromium 存在白屏问题，请使用 Firefox。

---

## Phase 1: Foundation (Task 1-2)

**验证内容:** Kiosk 主题 + 本地字体 + Mock 认证 + 登录页

### 自动化测试

```bash
cd katrain/web/ui
npx vitest run src/kiosk/__tests__/theme.test.ts
npx vitest run src/kiosk/__tests__/KioskAuth.test.tsx
```

预期: 8 + 3 = 11 tests PASS

### MacBook 手动验证

1. 打开 http://localhost:5173/kiosk/
2. 检查登录页:
   - [ ] 背景色为墨黑 (`#1a1714`)，不是纯黑
   - [ ] "KaTrain" 标题为翡翠绿 (`#5cb57a`)
   - [ ] "用户名" 和 "PIN" 输入框正常显示
   - [ ] "登录" 按钮为绿色，高度较大 (56px)
   - [ ] 字体为 Noto Sans SC（中文无衬线字体，非浏览器默认宋体）
3. 输入任意用户名 + PIN，点击登录:
   - [ ] 成功跳转到主界面（不报错）
4. 打开 DevTools → Network:
   - [ ] 字体文件从本地加载（`/@fontsource/...`），无外部 CDN 请求

### RK3588 额外验证

- [ ] Firefox 上字体渲染正常（FreeType 下 Noto Sans SC 无异常）
- [ ] 登录页在 1024x600 分辨率下布局居中，无溢出

---

## Phase 2: Layout Shell (Task 3-6)

**验证内容:** StatusBar + NavigationRail + KioskLayout + KioskApp 路由接入

### 自动化测试

```bash
cd katrain/web/ui
npx vitest run src/kiosk/__tests__/StatusBar.test.tsx
npx vitest run src/kiosk/__tests__/NavigationRail.test.tsx
npx vitest run src/kiosk/__tests__/KioskLayout.test.tsx
npx vitest run src/kiosk/__tests__/KioskApp.test.tsx
```

预期: 4 + 5 + 1 + 3 = 13 tests PASS

### MacBook 手动验证

登录后进入主界面:

1. StatusBar (顶部 40px):
   - [ ] 左侧: "KaTrain" 文字 + 绿色引擎状态圆点
   - [ ] 右侧: 用户名 + 当前时间 (HH:MM)
   - [ ] 底部有分割线

2. NavigationRail (左侧 72px):
   - [ ] 6 个图标+文字: 对弈、死活、研究、棋谱、直播 + 分割线 + 设置
   - [ ] 当前页面对应项高亮为绿色
   - [ ] 点击各项能切换页面，高亮跟随

3. 布局整体:
   - [ ] StatusBar + NavigationRail + 主内容区三部分完整
   - [ ] 无滚动条溢出
   - [ ] 页面不闪烁

4. 路由:
   - [ ] 直接访问 http://localhost:5173/kiosk/ → 跳转登录页
   - [ ] 登录后 /kiosk/ → 自动跳转到 /kiosk/play
   - [ ] 访问 /kiosk/nonexistent → 重定向到 /kiosk/play
   - [ ] SPA 深链接: 直接访问 /kiosk/tsumego → 跳转登录页（不是 404）

5. Galaxy 未被破坏:
   - [ ] http://localhost:5173/galaxy/ 正常加载，与 kiosk 无关

### RK3588 额外验证

- [ ] NavigationRail 72px 在 1024x600 下不显得过宽
- [ ] 棋盘区域 (主内容减去 72px) 仍有足够空间
- [ ] 触屏点击 NavigationRail 各项响应正常（按下有 scale 动画）

---

## Phase 3: Reusable Components (Task 7-8)

**验证内容:** ModeCard + OptionChips 触控友好组件

### 自动化测试

```bash
cd katrain/web/ui
npx vitest run src/kiosk/__tests__/ModeCard.test.tsx
npx vitest run src/kiosk/__tests__/OptionChips.test.tsx
```

预期: 2 + 2 = 4 tests PASS

### MacBook 手动验证

1. 对弈页 (PlayPage) 中的 ModeCard:
   - [ ] 4 张卡片有图标 + 标题 + 副标题
   - [ ] 鼠标点击有 scale(0.96) 按下动画
   - [ ] 卡片有边框，背景色区别于页面背景

2. AI 设置页中的 OptionChips (点击"自由对弈"进入):
   - [ ] 棋盘选项 (9路/13路/19路) 显示为横排按钮
   - [ ] 选中项有绿色边框和深色背景
   - [ ] 点击切换选中状态
   - [ ] 每个 chip 最小高度 48px（触控友好）

### RK3588 额外验证

- [ ] 触屏点击 ModeCard 响应灵敏，scale 动画流畅
- [ ] OptionChips 触控区域足够大，不会误触相邻选项

---

## Phase 4: Pages (Task 9-13)

**验证内容:** PlayPage + AiSetupPage + GamePage + TsumegoPage + ResearchPage + KifuPage + LivePage + SettingsPage

### 自动化测试

```bash
cd katrain/web/ui
npx vitest run src/kiosk/__tests__/PlayPage.test.tsx
npx vitest run src/kiosk/__tests__/AiSetupPage.test.tsx
npx vitest run src/kiosk/__tests__/GamePage.test.tsx
npx vitest run src/kiosk/__tests__/TsumegoPage.test.tsx
npx vitest run src/kiosk/__tests__/ResearchPage.test.tsx
npx vitest run src/kiosk/__tests__/KifuPage.test.tsx
npx vitest run src/kiosk/__tests__/LivePage.test.tsx
npx vitest run src/kiosk/__tests__/SettingsPage.test.tsx
```

预期: 2 + 5 + 5 + 3 + 1 + 1 + 1 + 1 = 19 tests PASS

### MacBook 手动验证

**PlayPage (对弈):**
- [ ] 两个区块标题: "人机对弈" 和 "人人对弈"
- [ ] 4 张 ModeCard: 自由对弈、升降级对弈、本地对局、在线大厅

**AiSetupPage (自由对弈 → 设置):**
- [ ] 左侧棋盘占位 (土黄色，显示 "19x19")
- [ ] 右侧表单: 棋盘 / 我执 / AI 强度 / 让子 / 用时
- [ ] 有返回按钮
- [ ] 底部 "开始对弈" 绿色大按钮
- [ ] 升降级模式 (`/kiosk/play/ai/setup/ranked`): **无** AI 强度滑块

**GamePage (全屏对局):**
- [ ] 点击 "开始对弈" 后进入全屏
- [ ] **无** NavigationRail 和 StatusBar
- [ ] 左侧棋盘占位显示 "第42手"
- [ ] 右侧面板: 玩家名 (张三 / KataGo)、胜率 56.3%、AI 推荐 (R16)
- [ ] 6 个控制按钮 (3x2): 悔棋 / 跳过 / 计数 / 认输 / 设置 / 退出

**TsumegoPage (死活):**
- [ ] 左侧题目预览占位
- [ ] 右上筛选条: 全部 / 入门 / 初级 / 中级 / 高级
- [ ] 12 道题目按钮网格
- [ ] 已解题目有绿色背景
- [ ] 点击 "入门" 筛选 → 只显示 4 题，"高级" 题目消失
- [ ] 点击 "全部" → 恢复 12 题

**ResearchPage (研究):**
- [ ] 左侧棋盘占位
- [ ] 右侧分析面板有 "研究" 相关内容

**KifuPage (棋谱):**
- [ ] 3 条棋谱记录: 柯洁 vs 申真谞、李昌镐 vs 曹薰铉、张三 vs KataGo
- [ ] 每条显示赛事名 + 结果

**LivePage (直播):**
- [ ] 3 场比赛: 2 场 live + 1 场 upcoming
- [ ] live 场次显示手数 (127手、89手)

**SettingsPage (设置):**
- [ ] 语言选择器
- [ ] 外部平台区域 (99围棋、野狐围棋、腾讯围棋、新浪围棋)

### RK3588 额外验证

- [ ] GamePage 全屏对局在 1024x600 下: 棋盘占位 560x560，右侧面板 ~392px
- [ ] 控制按钮 3x2 网格触控不误触
- [ ] TsumegoPage 题目网格在小屏上自适应列数
- [ ] 各页面切换无明显卡顿

---

## Phase 5: Verification (Task 14-15)

**验证内容:** 导航集成测试 + 全量回归 + 端到端流程

### 自动化测试

```bash
cd katrain/web/ui
# 仅 kiosk 测试
npx vitest run src/kiosk/
# 全量测试 (含 Galaxy，确认无回归)
npx vitest run
```

预期: kiosk 全部 52 tests PASS，Galaxy 原有测试不受影响

### MacBook 手动验证 — 端到端流程

完整走一遍:

1. **登录流程:**
   - [ ] 打开 /kiosk/ → 登录页
   - [ ] 输入用户名 "张三" → 点击登录 → 进入主界面

2. **对弈流程:**
   - [ ] 对弈 → 自由对弈 → 设置页 → 调整参数 → 开始对弈 → 全屏 GamePage
   - [ ] 浏览器后退 → 回到设置页
   - [ ] 后退 → 回到 PlayPage
   - [ ] 升降级对弈 → 设置页 (无 AI 强度滑块) → 开始 → 全屏

3. **死活流程:**
   - [ ] 点击 NavigationRail "死活" → TsumegoPage
   - [ ] 筛选 → 点击题目

4. **各页面切换:**
   - [ ] 研究 → 棋谱 → 直播 → 设置，NavigationRail 高亮正确跟随
   - [ ] 每个页面渲染无报错 (DevTools Console 无红色错误)

5. **SPA fallback:**
   - [ ] 直接访问 /kiosk/tsumego/problem/beginner-1 → 不是 404，正常进入 app

6. **Galaxy 隔离:**
   - [ ] /galaxy/ 正常，不受 kiosk 任何影响

### RK3588 额外验证

- [ ] Firefox `--kiosk` 全屏效果正常
- [ ] 全部流程在触屏操作下完成，无需键盘 (登录页除外，需虚拟键盘)
- [ ] 无白屏、无崩溃

---

## Phase 6: Shared Layer Extraction (Future)

**验证内容:** Board.tsx、hooks、API types 提取到 `src/shared/`

### 自动化测试

```bash
cd katrain/web/ui
npx vitest run              # 全量: kiosk + galaxy 均不能有回归
```

### MacBook 手动验证

- [ ] Galaxy 和 Kiosk 两个入口均正常工作
- [ ] Galaxy 中的棋盘组件 (`Board.tsx`) 仍正常渲染
- [ ] Kiosk 中能 import shared 层的组件/hooks (替换 mock 时验证)
- [ ] `npm run build` 成功，无 import 报错

### RK3588 额外验证

- [ ] 与 MacBook 相同验证项，无平台差异

---

## Phase 7: Backend Integration (Future)

**验证内容:** 真实对局 + WebSocket + 认证 + 死活题 API

### Prerequisites

```bash
# 启动后端
python -m katrain --ui web --host 0.0.0.0 --port 8001
# 启动前端 (proxy /api → :8001)
cd katrain/web/ui && npm run dev
```

### MacBook 手动验证

- [ ] 登录页使用真实用户认证 (非 mock)
- [ ] 对弈: 开始对弈 → 棋盘真实渲染 → 落子 → KataGo 回应
- [ ] 悔棋/认输等控制按钮功能正常
- [ ] 死活题: 从 API 加载真实题目，答题有正误反馈
- [ ] 棋谱: 从 API 加载真实对局记录
- [ ] WebSocket 连接状态: StatusBar 引擎状态指示灯反映真实状态
- [ ] 断网后重连恢复

### RK3588 额外验证

- [ ] KataGo 引擎在 RK3588 CPU 上正常运行
- [ ] 落子后 AI 响应延迟可接受 (< 3s for CPU)
- [ ] WebSocket 在局域网内稳定

---

## Phase 8: Kiosk Infrastructure (Future)

**验证内容:** systemd 自启 + 浏览器 kiosk + 虚拟键盘 + 镜像部署

### MacBook 手动验证 (有限)

macOS 无法验证 systemd，仅验证:
- [ ] `npm run build` 产物完整 (`katrain/web/static/` 包含 index.html + assets)
- [ ] 静态文件通过 FastAPI 服务: `python -m katrain` 后访问 /kiosk/ 可用
- [ ] SPA fallback: FastAPI 对 /kiosk/* 返回 index.html

### RK3588 验证 (核心)

**开机自启:**
- [ ] 重启设备 → 自动进入 kiosk 登录页 (无需手动操作)
- [ ] `systemctl status katrain-server` → active
- [ ] `systemctl status katrain-kiosk` → active

**浏览器 kiosk:**
- [ ] Firefox 全屏，无地址栏、无标签栏、无窗口装饰
- [ ] 用户无法通过触屏退出 kiosk (无关闭按钮、无手势退出)

**虚拟键盘 (onboard):**
- [ ] 点击登录页用户名输入框 → 虚拟键盘自动弹出
- [ ] 能输入中文和英文
- [ ] 点击输入框外 → 键盘收起
- [ ] 键盘不遮挡登录按钮

**崩溃恢复:**
- [ ] `kill` Firefox 进程 → systemd 自动重启 → 回到登录页
- [ ] `kill` katrain-server → systemd 自动重启 → 前端短暂断连后恢复

**屏幕保护:**
- [ ] 闲置 N 分钟后屏幕变暗或显示屏保
- [ ] 触屏唤醒后回到之前页面

**镜像部署:**
- [ ] 制作 eMMC/SD 卡镜像
- [ ] 在全新 RK3588 设备上烧录镜像
- [ ] 开机直接进入 kiosk 登录页，无需任何手动配置

---

## Phase 9: Hardware Integration (Future)

**验证内容:** 实体棋盘传感器 + WebSocket 输入协议

### MacBook 手动验证 (模拟)

macOS 无实体棋盘，使用模拟:
- [ ] WebSocket `board_input` 消息格式正确 (用测试脚本发送)
- [ ] 前端收到模拟落子信号 → 棋盘正确更新

### RK3588 验证 (核心)

**传感器驱动:**
- [ ] 棋盘传感器连接 → 设备识别
- [ ] 放置棋子 → 系统检测到交叉点坐标

**输入协议:**
- [ ] 放置棋子 → WebSocket 发送 `board_input` → 前端棋盘更新
- [ ] 提子 → 前端同步移除棋子

**输入仲裁 (触屏 vs 实体棋盘):**
- [ ] 实体棋盘落子时，触屏点击棋盘无效 (防冲突)
- [ ] 实体棋盘不活跃时，触屏操作控制面板正常
- [ ] 规则说明: 同一时刻只有一种输入源有效

---

## Phase 10: Performance Baseline (Future)

**验证内容:** 首屏时间 + FPS + 内存 + WebSocket 延迟

### MacBook 参考基线

MacBook 性能远超目标设备，数据仅作参考:
- [ ] `npm run build` 产物体积记录 (gzip 后)
- [ ] Lighthouse 性能分数 (Chrome DevTools → Lighthouse)
- [ ] 代码分割有效: kiosk 和 galaxy 为独立 chunk

### RK3588 验证 (核心指标)

**首屏时间 (Cold Start):**
- [ ] 从 Firefox 启动到登录页可交互: 目标 < 3s
- [ ] 登录后到主界面渲染完成: 目标 < 1s

**帧率:**
- [ ] NavigationRail 页面切换: 目标 60fps (无掉帧)
- [ ] 对局页棋盘交互 (落子动画): 目标 >= 30fps
- [ ] 死活题网格滚动: 目标 >= 30fps

**内存:**
- [ ] Firefox 进程内存: 目标 < 300MB
- [ ] KataGo 进程内存: 记录基线值
- [ ] 长时间运行 (1 小时) 后无内存泄漏

**WebSocket 延迟:**
- [ ] 落子 → AI 响应显示: 记录端到端延迟
- [ ] WebSocket 心跳: 记录 round-trip time

**发热:**
- [ ] 连续对局 30 分钟后 SoC 温度: 记录值
- [ ] 无因过热导致的降频卡顿

---

## Quick Reference: 一键运行全部测试

```bash
cd katrain/web/ui

# 全部 kiosk 测试
npx vitest run src/kiosk/

# 全量测试 (含 Galaxy)
npx vitest run

# 构建检查
npm run build
```
