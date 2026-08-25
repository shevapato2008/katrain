/* 死活题阶梯页的三条守卫 —— 只断言**渲染结构**，不断言布局结论。
 *
 * 版式那一半（行铺不铺得开、条会不会被 hidden 切掉、22 行滚不滚得动）由
 * `superpowers/tracks/galaxy-ui-redesign/loadbearing_tsumego_ladder.js` 在真浏览器里量。
 * 判据「把它原样搬进真浏览器，还有可能失败吗」：下面三条都会 —— 它们量的是
 * DOM 里有什么、顺序是什么、可及名是什么，不是浏览器算出来的盒子。
 *
 * 变异实跑（改坏 → 变红，还原 → 变绿），三条逐条真跑过：
 *   1. 排序改成按接口原样输出（去掉 kyu/dan 分组与排序） → 「顺序」那条红
 *   2. `isMine` 恒 false                                → 「你的水平」那条红
 *   3. 分布条的 `aria-label` 去掉                        → 「颜色不是唯一线索」那条红
 */
import { render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { SettingsProvider } from '../../context/SettingsContext';
import { GameNavigationProvider } from '../context/GameNavigationContext';
import TsumegoLevelsPage from './TsumegoLevelsPage';

/* 接口按**乱序**回，好让「顺序」那条真的在守排序，而不是在守接口碰巧的输出。 */
const LEVELS = [
  { level: '3d', total: 999, categories: { 'life-death': 868, tesuji: 76 } },
  { level: '15k', total: 1000, categories: { capturing: 630, 'life-death': 167, tesuji: 139, semeai: 63, endgame: 1 } },
  { level: '1d', total: 898, categories: { 'life-death': 732, tesuji: 85 } },
  { level: '5k', total: 987, categories: { 'life-death': 645, tesuji: 198, semeai: 141 } },
  { level: '1k', total: 986, categories: { 'life-death': 796, tesuji: 116 } },
];

vi.mock('../../context/AuthContext', () => ({
  useAuth: () => ({ token: 'token', isAuthenticated: true, user: { id: 1, username: 'p', rank: '5k' } }),
}));

const renderPage = () => render(
  <MemoryRouter>
    <SettingsProvider>
      <GameNavigationProvider>
        <TsumegoLevelsPage />
      </GameNavigationProvider>
    </SettingsProvider>
  </MemoryRouter>,
);

describe('TsumegoLevelsPage · 阶梯', () => {
  beforeEach(() => {
    /* fetch 必须按 URL 分流：`SettingsProvider` 会去拉 `/api/translations`，
       无差别返回 LEVELS 会让 i18n 把一个数组当成词表，`i18n.t` 直接抛
       `Cannot read properties of undefined`。第一版就是这么整体假红的。 */
    vi.stubGlobal('fetch', vi.fn((url: string) => {
      if (String(url).includes('/tsumego/levels')) {
        return Promise.resolve({ ok: true, json: async () => LEVELS });
      }
      /* 形状必须对得上真接口：`i18n.loadTranslations` 取的是 `data.translations`，
         回一个裸 `{}` 会把 `this.translations` 设成 undefined，`t()` 当场抛。 */
      return Promise.resolve({ ok: true, json: async () => ({ translations: {}, players: {}, tournaments: {}, rounds: {}, rules: {} }) });
    }));
  });

  it('渲染成一条有序的阶梯：级位整段在前（弱→强），段位整段在后（弱→强）', async () => {
    renderPage();
    await waitFor(() => expect(screen.getAllByTestId('tsumego-rung')).toHaveLength(5));
    /* 取徽章那个盒子的文本，不取整行 textContent —— 徽章和题数之间没有空白节点，
       `textContent` 会连成 `15K1000`。承重脚本上踩过同一个坑。 */
    const badges = screen.getAllByTestId('tsumego-rung')
      .map((row) => (row.firstElementChild?.textContent || '').trim());
    expect(badges).toEqual(['15K', '5K', '1K', '1D', '3D']);
  });

  it('自己那一档带**文字**标记，不只靠颜色', async () => {
    renderPage();
    await waitFor(() => expect(screen.getAllByTestId('tsumego-rung')).toHaveLength(5));
    const mine = screen.getAllByTestId('tsumego-rung')[1];   // 5K
    expect(within(mine).getAllByText('你的水平').length).toBeGreaterThan(0);
    // 别的档不许带
    expect(within(screen.getAllByTestId('tsumego-rung')[0]).queryAllByText('你的水平')).toHaveLength(0);
  });

  it('分布条挂完整可及名（颜色不是唯一线索）', async () => {
    renderPage();
    await waitFor(() => expect(screen.getAllByTestId('tsumego-rung')).toHaveLength(5));
    const bar = within(screen.getAllByTestId('tsumego-rung')[0]).getByRole('img');
    const label = bar.getAttribute('aria-label') || '';
    // 15K 有五类，条上必须逐类报数，不能只画颜色
    expect(label).toContain('630');
    expect(label).toContain('167');
    expect(label.split('、').length).toBe(5);
  });
});
