/* spec-sync: 2.4 rev=2026-08-22 sha=2c267c58 —— 见 check_spec_sync.py；规范 §2.4 一改这里就红。 */
import { fireEvent, render, screen, within } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import ContentPageHeader from './ContentPageHeader';

const requestNavigation = vi.fn();
vi.mock('../../context/GameNavigationContext', () => ({
  useGameNavigation: () => ({ requestNavigation }),
}));
vi.mock('../../../hooks/useTranslation', () => ({
  useTranslation: () => ({ t: (_key: string, fallback: string) => fallback }),
}));

/**
 * 这三条守的是 spec §2.4 在 2026-08-22 修订后的形状，**不是**冻结原型 `cph()` 画的旧形状
 * （标题在左 + 右侧带文字的返回按钮）。原型那一处没跟上当日裁定，规范权威更高。
 *
 * 变异验证（2026-08-22）：
 *  M1 把 `size="page"` 去掉 → 前两条仍绿（结构不变，只是字号档），第三条也绿。
 *     字号档不在这里断言 —— 它是像素结论，归真浏览器那一关，jsdom 无权作证。
 *  M2 把 `showBack={Boolean(parentTo)}` 写成 `showBack`（恒真）→ 第二条红
 *     （根级页面画出了一个 backTo='' 的返回键）。
 *  M3 把 `backLabel={parentLabel}` 删掉 → 第一条红（无障碍名退回「返回」）。
 *  M4 把 parentLabel 也渲染上屏 → 第一条红（`queryByText('对局')` 命中）。
 */
describe('ContentPageHeader', () => {
  it('puts the back arrow before the title and folds the parent name into its accessible name only', () => {
    requestNavigation.mockClear();
    render(<ContentPageHeader title="升降级对弈" parentLabel="对局" parentTo="/galaxy/play" />);

    const plate = screen.getByTestId('module-plate');
    const heading = screen.getByRole('heading', { name: '升降级对弈' });
    const back = screen.getByRole('button', { name: '返回对局' });

    expect(back.compareDocumentPosition(heading) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(within(plate).queryByText('对局')).not.toBeInTheDocument();

    fireEvent.click(back);
    expect(requestNavigation).toHaveBeenCalledWith('/galaxy/play');
  });

  it('draws no back control on a root-level page', () => {
    render(<ContentPageHeader title="死活题" />);
    expect(screen.getByRole('heading', { name: '死活题' })).toBeInTheDocument();
    expect(screen.queryByRole('button')).not.toBeInTheDocument();
  });

  it('renders a single status slot after the title', () => {
    render(<ContentPageHeader title="第 3 单元" parentLabel="死活" parentTo="/x" status={<span>3/12</span>} />);
    const heading = screen.getByRole('heading', { name: '第 3 单元' });
    const status = screen.getByText('3/12');
    expect(heading.compareDocumentPosition(status) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  });
});
