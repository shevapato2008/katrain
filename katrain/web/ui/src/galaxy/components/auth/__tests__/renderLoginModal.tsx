// LoginModal 的测试装配助手。Task 15/15.5 复用。
//
// 它**不是**测试文件（文件名不匹配 vitest 默认收集的 `*.{test,spec}.*`），但**会被 `tsc -b` 检查**
// —— `tsconfig.app.json:28` 的 exclude 只排掉 `src/**/*.test.ts(x)`。这正好是想要的：
// LoginModal 的 props 改了，这里会先红。
import { render, type RenderResult } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { SettingsProvider } from '../../../../context/SettingsContext';
import LoginModal from '../LoginModal';

/** 裸 `render(<LoginModal open .../>)` 跑不起来：LoginModal:14-15 一进来就调
 *  `useSettings()`（`SettingsContext.tsx:12-18`，`!context` 时 throw）与
 *  `useAuth()`（`AuthContext.tsx:208-214`，`context === undefined` 时 throw）。
 *  同目录 `AuthRequiredDialog.tsx:53-55` 的注释已经写过这个坑。
 *
 *  这里只装 Settings 与 Router。**AuthContext 必须由各测试文件自己 `vi.mock`** ——
 *  `vi.mock` 只有写在测试文件里才会被提升，写在这里对调用方无效。
 *  漏了它会当场抛 `useAuth must be used within an AuthProvider`。
 *
 *  用真 `SettingsProvider`（不 mock）是有意的：它挂载会走 `i18n.loadTranslations`，
 *  字典拿不到就留在空 `{}`，于是 `i18n.ts:52` 的 `translations[key] || defaultText || key`
 *  恒返默认值 —— 下游按中文默认值写的断言靠的是这个，不是靠 mock 掉 `useTranslation`
 *  （LoginModal 根本不用 `useTranslation`，它直接调 `i18n.t`）。 */
export const renderLoginModal = (
  props: { open?: boolean; onClose?: () => void } = {},
): RenderResult =>
  render(
    <MemoryRouter>
      <SettingsProvider>
        <LoginModal open={props.open ?? true} onClose={props.onClose ?? (() => {})} />
      </SettingsProvider>
    </MemoryRouter>,
  );
