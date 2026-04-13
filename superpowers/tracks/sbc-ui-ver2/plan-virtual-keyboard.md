# Plan: Kiosk 虚拟键盘集成 (simple-keyboard)

> **目标**: 在 KaTrain Kiosk 模式下集成 `simple-keyboard` 虚拟键盘，解决 RK3576/RK3562 单板机 Chromium Kiosk 模式无物理键盘时的文字输入问题。支持中/英/日/韩/西/俄/法/德/土/乌克兰等多语言布局。

## 现状分析

### Kiosk 模式输入场景清单

| 页面 | 输入类型 | 文件路径 |
|------|----------|----------|
| LoginPage | 用户名、密码 | `kiosk/pages/LoginPage.tsx` |
| ResearchPage | 黑方/白方名字、贴目(数字) | `kiosk/pages/ResearchPage.tsx` |
| KifuPage | 搜索框 | `kiosk/pages/KifuPage.tsx` |
| SettingsPage | 无文本输入(全选项) | `kiosk/pages/SettingsPage.tsx` |
| LobbyPage | 无文本输入 | `kiosk/pages/LobbyPage.tsx` |

**共 ~7 个 MUI TextField**，全部在 Kiosk 路由下。

### 架构约束

- Kiosk 模式独立于 Galaxy/Zen 模式，有自己的 `KioskApp.tsx`、`kioskTheme`、`OrientationProvider`
- 所有输入均使用 MUI `<TextField>`
- 语言系统通过 `SettingsContext` + `i18n.ts` 管理，支持 11 种语言
- 屏幕 7-10 寸，landscape 为主，支持旋转 (0°/90°/180°/270°)
- 暗色主题 (ink-black 背景, jade-glow 主色)

---

## 设计方案

### 核心思路

创建 `VirtualKeyboardProvider` 包裹 Kiosk 应用，通过全局 focus/blur 事件监听自动弹出键盘。键盘布局跟随 app 语言设置，用户也可手动切换。

### 架构图

```
KioskApp.tsx
└─ OrientationProvider
   └─ VirtualKeyboardProvider     ← 新增
      └─ RotationWrapper
         └─ KioskRoutes
            └─ 各页面 TextField
         └─ VirtualKeyboard       ← 固定底部浮层
```

### 键盘布局映射

| KaTrain 语言码 | simple-keyboard-layouts 布局 | 说明 |
|----------------|------------------------------|------|
| `en` | 内置默认 (english) | 无需额外 import |
| `cn` | `chinese` | 拼音字母键盘 |
| `tw` | `chinese` | 同简中，注音需另议 |
| `jp` | `japanese` | 日文假名 |
| `ko` | `korean` | 韩文 |
| `es` | `spanish` | 西班牙文 |
| `ru` | `russian` | 俄文 |
| `fr` | `french` | 法文 |
| `de` | `german` | 德文 |
| `tr` | `turkish` | 土耳其文 |
| `ua` | `ukrainian` | 乌克兰文 |

> 注：`simple-keyboard` 的中/日/韩布局提供字母/假名/字母键盘，不含 IME 输入法。对于 Kiosk 场景下主要输入用户名、搜索关键词等短文本，字母键盘已足够。

---

## 实施步骤

### Step 1: 安装依赖

```bash
cd katrain/web/ui
npm install simple-keyboard simple-keyboard-layouts
```

**产出**: `package.json` 新增两个依赖

---

### Step 2: 创建键盘布局映射工具

**新建文件**: `src/kiosk/utils/keyboardLayouts.ts`

功能：
- 导出 `getLayoutForLanguage(langCode: string)` 函数
- 将 KaTrain 语言码映射到 simple-keyboard-layouts 的 layout 对象
- 默认回退到英文布局
- 导出 `KEYBOARD_LANGUAGES` 数组，用于键盘上的语言切换按钮

```typescript
// 核心接口
export interface KeyboardLayoutConfig {
  layout: Record<string, string[]>;
  display?: Record<string, string>;
}

export function getLayoutForLanguage(lang: string): KeyboardLayoutConfig;
export const KEYBOARD_LANGUAGES: { code: string; label: string }[];
```

---

### Step 3: 创建 VirtualKeyboardContext

**新建文件**: `src/kiosk/context/VirtualKeyboardContext.tsx`

职责：
- `isVisible`: 键盘当前是否可见
- `activeInput`: 当前聚焦的 `HTMLInputElement | null`
- `keyboardLang`: 键盘当前布局语言（默认跟随 app 语言）
- `setKeyboardLang`: 手动切换键盘语言
- `enabled`: 虚拟键盘总开关（localStorage 持久化，key: `katrain_kiosk_vkb`）
- `setEnabled`: 开关切换

核心逻辑：
1. 在 `document` 上监听 `focusin` / `focusout` 事件
2. `focusin` 时检查 target 是否为 `input[type=text|password|search|number]` 或 `textarea`
3. 匹配则设置 `activeInput` 并显示键盘
4. `focusout` 时延迟 100ms 隐藏（防止点击键盘本身触发 blur）
5. 键盘语言默认跟随 `SettingsContext.language`，用户也可临时切换

```typescript
interface VirtualKeyboardContextType {
  isVisible: boolean;
  activeInput: HTMLInputElement | HTMLTextAreaElement | null;
  keyboardLang: string;
  setKeyboardLang: (lang: string) => void;
  enabled: boolean;
  setEnabled: (enabled: boolean) => void;
}
```

---

### Step 4: 创建 VirtualKeyboard 组件

**新建文件**: `src/kiosk/components/common/VirtualKeyboard.tsx`

**新建文件**: `src/kiosk/components/common/VirtualKeyboard.css`

功能：
- 渲染 `simple-keyboard` 实例
- 固定在屏幕底部，半透明暗色背景
- 从 `VirtualKeyboardContext` 读取状态
- 按键时通过 `activeInput` 的 React setter 注入字符（需触发 `input` 事件以兼容 React 受控组件）
- 顶部工具栏包含：
  - 语言切换按钮（循环切换可用布局）
  - 键盘类型切换（字母/数字/符号）
  - 关闭按钮
- 动画：slide-up 进入 / slide-down 退出
- 密码输入时自动切到英文布局

关键实现细节：

```typescript
// 触发 React 受控组件更新
const nativeInputValueSetter = Object.getOwnPropertyDescriptor(
  HTMLInputElement.prototype, 'value'
)!.set!;
nativeInputValueSetter.call(input, newValue);
input.dispatchEvent(new Event('input', { bubbles: true }));
```

样式要点：
- 键盘高度：landscape 模式 ~40% 屏高，portrait 模式 ~35%
- 按键最小触摸区域 44x44px
- 深色半透明背景 `rgba(26, 23, 20, 0.95)` 配合 backdrop-filter blur
- 按键颜色与 kioskTheme 一致 (jade-glow hover, stone-white text)
- 特殊键 (Shift, Backspace, Enter, Space) 加宽加高

---

### Step 5: 集成到 KioskApp

**修改文件**: `src/kiosk/KioskApp.tsx`

变更：
1. 导入 `VirtualKeyboardProvider`
2. 导入 `VirtualKeyboard` 组件
3. 在 `OrientationProvider` 内、`RotationWrapper` 外包裹 `VirtualKeyboardProvider`
4. 在 `RotationWrapper` 内底部放置 `<VirtualKeyboard />`

```tsx
const KioskApp = () => (
  <ThemeProvider theme={kioskTheme}>
    <CssBaseline />
    <OrientationProvider>
      <VirtualKeyboardProvider>
        <RotationWrapper>
          <KioskRoutes />
          <VirtualKeyboard />
        </RotationWrapper>
      </VirtualKeyboardProvider>
    </OrientationProvider>
  </ThemeProvider>
);
```

---

### Step 6: 页面适配 — 键盘弹出时内容上推

**修改文件**: `src/kiosk/components/layout/KioskLayout.tsx`

变更：
- 从 `VirtualKeyboardContext` 读取 `isVisible`
- 当键盘可见时，主内容区域添加 `paddingBottom` 等于键盘高度
- 使用 CSS transition 平滑过渡

**修改文件**: `src/kiosk/pages/LoginPage.tsx`

变更：
- LoginPage 不在 KioskLayout 内（全屏页面），需单独处理
- 当键盘可见时，整个表单容器上移，确保当前输入框不被遮挡

---

### Step 7: Settings 页面添加虚拟键盘开关

**修改文件**: `src/kiosk/pages/SettingsPage.tsx`

变更：
- 新增一组 OptionChips：`虚拟键盘` / `Virtual Keyboard`
  - 选项：`开启` / `关闭`
- 读写 `VirtualKeyboardContext.enabled`

---

### Step 8: 处理 RotationWrapper 兼容性

**检查文件**: `src/kiosk/components/layout/RotationWrapper.tsx`

确保：
- 键盘在旋转 90°/270° (portrait) 时正确定位
- fixed 定位在 CSS transform 旋转容器内的表现（可能需要用 Portal 渲染到 body）
- 如果 transform 影响 fixed 定位，改用 `ReactDOM.createPortal` 将键盘渲染到 `document.body`

---

### Step 9: 测试

**手动测试清单**:

- [ ] LoginPage: 点击用户名输入框 → 键盘弹出，输入字符 → 字段更新
- [ ] LoginPage: 点击密码输入框 → 键盘弹出且自动切英文布局，显示为 password dots
- [ ] LoginPage: 点击键盘外区域 → 键盘收起
- [ ] ResearchPage: 黑方/白方名字输入 → 键盘弹出，支持中日韩字母
- [ ] ResearchPage: 贴目数字输入 → 键盘弹出数字模式
- [ ] KifuPage: 搜索框输入 → 键盘弹出
- [ ] 语言切换: 键盘上切换语言按钮 → 布局实时变化
- [ ] Settings 开关: 关闭虚拟键盘 → 所有输入框不再弹出键盘
- [ ] 屏幕旋转: 0°/90°/180°/270° 下键盘均正确显示和定位
- [ ] Galaxy 模式: 访问 /galaxy/* → 不出现虚拟键盘（仅 Kiosk 生效）

**构建验证**:

```bash
cd katrain/web/ui
npm run build   # TypeScript 编译 + Vite 构建无错误
```

---

## 文件变更汇总

| 操作 | 文件 | 说明 |
|------|------|------|
| 修改 | `package.json` | 添加 simple-keyboard 依赖 |
| 新建 | `src/kiosk/utils/keyboardLayouts.ts` | 语言→布局映射 |
| 新建 | `src/kiosk/context/VirtualKeyboardContext.tsx` | 键盘状态管理 |
| 新建 | `src/kiosk/components/common/VirtualKeyboard.tsx` | 键盘 UI 组件 |
| 新建 | `src/kiosk/components/common/VirtualKeyboard.css` | 键盘样式 |
| 修改 | `src/kiosk/KioskApp.tsx` | 集成 Provider + 组件 |
| 修改 | `src/kiosk/components/layout/KioskLayout.tsx` | 键盘弹出时内容上推 |
| 修改 | `src/kiosk/pages/LoginPage.tsx` | 全屏页面键盘适配 |
| 修改 | `src/kiosk/pages/SettingsPage.tsx` | 添加键盘开关 |

**新增文件**: 4 个  
**修改文件**: 4 个  
**新增依赖**: `simple-keyboard`, `simple-keyboard-layouts`

---

## 风险与注意事项

1. **React 受控组件**: `simple-keyboard` 直接操作 DOM value 不会触发 React 的 onChange。必须通过 `nativeInputValueSetter` + `dispatchEvent` 方式注入，确保 React state 同步。

2. **CSS transform + fixed 定位**: `RotationWrapper` 使用 CSS transform 旋转整个应用，这会创建新的 containing block，使 `position: fixed` 失效。解决方案：用 `createPortal` 渲染键盘到 body，手动计算旋转后的位置。

3. **中文输入**: `simple-keyboard` 提供拼音字母键盘，不含中文 IME 候选词功能。如果未来需要拼音输入法联想，需额外集成 `pinyin-engine` 或类似方案。当前阶段字母键盘满足用户名/搜索等场景。

4. **性能**: `simple-keyboard` 使用 DOM 渲染（非 canvas），在 RK3576 的 Mali G52 GPU 上应无性能问题。slide 动画使用 CSS transform 而非 height/margin 变化。
