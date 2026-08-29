import { describe, expect, it, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { KioskTopbar } from './KioskTopbar';

/**
 * 这份**替换**了 `__tests__/Header.test.tsx`(替换不是叠加)。
 *
 * 原来那 10 条里有 3 条的断言对象是**布局结论** —— `toHaveStyle({height:'56px'})`、
 * 主页键的 `minWidth/minHeight/fontSize`、齿轮的 48×48。jsdom 没有布局引擎,
 * 那几个数是它照着内联样式字符串回读的,**把它原样搬进真浏览器不可能失败**,
 * 所以按判据删掉,搬到 `tests/kiosk-shell-geometry.spec.ts` 里由浏览器量。
 *
 * 留在这里的都是 jsdom 有权作证的:渲染了什么、顺序如何、点了触发什么。
 */
describe('KioskTopbar', () => {
  it('品牌两段都在,「智星盒」挂着龙藏那条类(字族由真浏览器闸核)', () => {
    render(<KioskTopbar identity={{ username: '张三' }} />);
    const zh = screen.getByTestId('kiosk-brand-zh');
    expect(zh).toHaveTextContent('智星盒');
    expect(zh).toHaveClass('kiosk-topbar__brand-zh');
    expect(screen.getByText('StellaBox')).toBeInTheDocument();
  });

  it('棋类名是「围棋」—— 顶栏这一格四家各写各的', () => {
    render(<KioskTopbar identity={{}} />);
    expect(screen.getByText('围棋')).toBeInTheDocument();
  });

  it('登录名与头像首字同源', () => {
    render(<KioskTopbar identity={{ username: '张三' }} />);
    expect(screen.getByTestId('header-username')).toHaveTextContent('张三');
    expect(screen.getByText('张')).toBeInTheDocument();
  });

  it('没登录也**照样有**身份位 —— 显示访客,不是整块消失', () => {
    // 旧 Header 是 `{username && …}`:没登录时那一格塌掉,右簇整体左移。
    // 防跳铁律 2 要的是**位置恒定**,所以这里恒渲染。
    render(<KioskTopbar identity={{}} />);
    expect(screen.getByTestId('header-username')).toHaveTextContent('访客');
  });

  it('时钟带 dateTime,且和正文是同一份格式化结果', () => {
    render(<KioskTopbar identity={{}} />);
    const clock = screen.getByTestId('clock');
    expect(clock.getAttribute('datetime')).toBe(clock.textContent);
    expect(clock.textContent).toMatch(/^\d{2}:\d{2}$/);
  });

  it('给了 onHome 才有主页键,点了会触发,且排在登录名**前面**', () => {
    const onHome = vi.fn();
    render(<KioskTopbar identity={{ username: '张三' }} onHome={onHome} />);
    const home = screen.getByRole('button', { name: '返回智星盒主页' });
    expect(home).toHaveTextContent('主页');
    expect(
      home.compareDocumentPosition(screen.getByTestId('header-username'))
        & Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();
    fireEvent.click(home);
    expect(onHome).toHaveBeenCalledOnce();
  });

  it('没给 onHome 就没有主页键', () => {
    render(<KioskTopbar identity={{ username: '张三' }} />);
    expect(screen.queryByRole('button', { name: '返回智星盒主页' })).not.toBeInTheDocument();
  });

  it('homeBusy 时主页键禁用 —— 返回主页要打一次上游,连点会打两次', () => {
    render(<KioskTopbar identity={{}} onHome={() => {}} homeBusy />);
    expect(screen.getByRole('button', { name: '返回智星盒主页' })).toBeDisabled();
  });

  it('顶栏上一个按钮都不许多出来 —— 齿轮/摄像头/标定/引擎点全拆(D9)', () => {
    // 这条锁的是**裁定**,不是样式:规范 §1「顶栏只放这些」,而三家顶栏都零指示器。
    // 只断言「没有齿轮」挡不住下一个人再挂一个别的,所以按钮总数一起钉死。
    render(<KioskTopbar identity={{ username: '张三' }} onHome={() => {}} />);
    expect(screen.getAllByRole('button')).toHaveLength(1);
    expect(screen.queryByRole('button', { name: '设置' })).not.toBeInTheDocument();
    expect(screen.queryByTestId('engine-status')).not.toBeInTheDocument();
  });
});
