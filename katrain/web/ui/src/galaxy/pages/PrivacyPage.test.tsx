import { render, screen } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { describe, it, expect, beforeEach, vi } from 'vitest';
import { AuthProvider } from '../../context/AuthContext';
import { SettingsProvider } from '../../context/SettingsContext';
import { PRIVACY_PATH, PRIVACY_CONTENT } from '../../legal/privacy';
import GalaxyApp from '../../GalaxyApp';

/* 判据落在**路由**上，不落在链接文本上：grep 一个自己刚写进去的 href="/galaxy/privacy"
   必然命中、必然报绿，它量的是链接不是可达性。
   这里把 GalaxyApp 挂在它在生产里的同一个挂载点 /galaxy/*（AppRouter.tsx:39）下。
   路由表少了那一条时，GalaxyApp.tsx:83 的 `*` → <Navigate to="/galaxy"> 会把它兜回 Dashboard，
   断言当场红 —— 注意那条兜底**在 MainLayout 里面**（GalaxyApp.tsx:61-84），
   所以命中它时先渲染 MainLayout 再跳，galaxy-main 全程在文档里。

   ⚠️ AuthProvider 不是可省的：GalaxyApp.tsx:59 无条件包 <TsumegoProgressProvider>，
   它主体第一句就是 useAuth()（TsumegoProgressContext.tsx:292），没有 AuthProvider 直接抛
   `useAuth must be used within an AuthProvider`（AuthContext.tsx:211）。
   src/galaxy/theme.test.tsx:90-97 那个"裸渲染 GalaxyApp"的先例不能照抄 ——
   它在 :28-45 把 TsumegoProgressContext 等四个模块整个 vi.mock 掉了，走的不是同一条路。 */
const renderAt = (path: string) =>
  render(
    <MemoryRouter initialEntries={[path]}>
      <AuthProvider>
        <SettingsProvider>
          <Routes>
            <Route path="/galaxy/*" element={<GalaxyApp />} />
          </Routes>
        </SettingsProvider>
      </AuthProvider>
    </MemoryRouter>,
  );

describe('隐私策略页', () => {
  beforeEach(() => {
    /* 渲染一次会打三个 fetch（/api/translations、/api/v1/auth/me、/api/v1/live/translations），
       全走全局 fetch，一个桩全覆盖。**必须是纯对象**：抄 features/aiLadder/api.test.ts:29 那种
       `mockResolvedValue(new Response(...))` 会让同一个 Response 实例被返回三次，
       第二个消费者当场 `Body is unusable: Body has already been read`。 */
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, json: async () => ({ translations: {} }) }));
  });

  it('PRIVACY_PATH 这条路由渲染的是政策页，不是别的页面', () => {
    renderAt(PRIVACY_PATH);
    expect(screen.getByTestId('privacy-page')).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: /隐私/ })).toBeInTheDocument();
  });

  it('政策正文写了手机号：收集、用途、撤回与删除', () => {
    /* 断言收窄到**含「手机号」的那几行**里。计划原稿是对整篇 PRIVACY_CONTENT 断
       /删除|注销/ —— 那条今天就已经绿（章四第 3 条「注销账号后…删除或匿名化」、
       章六第 3 条「删除您的个人信息」），把本轮新插的整段删掉它依旧绿，零分辨力。 */
    const phoneLines = PRIVACY_CONTENT.split('\n').filter((l) => l.includes('手机号'));
    expect(phoneLines.length).toBeGreaterThan(0);
    const joined = phoneLines.join('\n');
    expect(joined).toMatch(/身份验证/);
    expect(joined).toMatch(/撤回/);
    expect(joined).toMatch(/删除|匿名化/);
  });

  it('政策页在 MainLayout 之外 —— 外链打开时用户按定义还没登录', () => {
    /* 断言落在 MainLayout 自己那个容器上（MainLayout.tsx:24 data-testid="galaxy-main"），
       **不落在侧栏上**：jsdom 没有 matchMedia，MUI 的 useMediaQuery 一律回落 false
       ⇒ useGalaxySidebar 判成 'mobile' ⇒ 侧栏本来就不渲染，拿它当判据是恒绿的（已实测）。
       理由是**不该套导航壳**，不是"会被登录守卫拦"—— MainLayout 全文 55 行没有任何 auth 守卫。 */
    renderAt(PRIVACY_PATH);
    expect(screen.queryByTestId('galaxy-main')).toBeNull();
  });
});
