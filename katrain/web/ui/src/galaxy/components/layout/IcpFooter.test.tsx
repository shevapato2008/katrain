import { render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it } from 'vitest';
import IcpFooter from './IcpFooter';
import { ICP_FILING_NUMBER, MIIT_FILING_URL, shouldShowIcpFooter } from './icpFiling';

/* jsdom 的 window.location 不能直接赋值，但可以整块替换。用完还原，
 * 免得污染同一进程里后面的用例（同族教训：进程级共享状态没还原）。 */
const realLocation = window.location;
const withHostname = (hostname: string) => {
  Object.defineProperty(window, 'location', {
    configurable: true,
    value: { ...realLocation, hostname, href: `https://${hostname}/` },
  });
};

afterEach(() => {
  Object.defineProperty(window, 'location', { configurable: true, value: realLocation });
});

describe('shouldShowIcpFooter', () => {
  it('只认备案主体域名与它的子域', () => {
    expect(shouldShowIcpFooter('modelstella.com')).toBe(true);
    expect(shouldShowIcpFooter('www.modelstella.com')).toBe(true);
  });

  it('不在这张备案下的域名一律不印', () => {
    // 测试环境与开发机 —— 印上去就是假信息。
    expect(shouldShowIcpFooter('go.sailorvoyage.top')).toBe(false);
    expect(shouldShowIcpFooter('localhost')).toBe(false);
    expect(shouldShowIcpFooter('127.0.0.1')).toBe(false);
    // 后缀匹配的坑：这个域名以 `modelstella.com` 结尾，但不是它的子域。
    expect(shouldShowIcpFooter('evilmodelstella.com')).toBe(false);
  });
});

describe('IcpFooter', () => {
  it('在备案域名上印出完整备案号，并链到工信部备案系统', () => {
    withHostname('modelstella.com');
    render(<IcpFooter />);

    const link = screen.getByRole('link', { name: ICP_FILING_NUMBER });
    expect(link).toHaveAttribute('href', MIIT_FILING_URL);
    expect(link).toHaveAttribute('target', '_blank');
    // 新标签页必须切断 opener 引用。
    expect(link.getAttribute('rel')).toContain('noopener');
    expect(link.getAttribute('rel')).toContain('noreferrer');
  });

  it('备案号不许被省略号截断 —— 窄屏折行,不截断', () => {
    withHostname('modelstella.com');
    render(<IcpFooter />);
    expect(screen.getByTestId('icp-footer')).not.toHaveStyle({ textOverflow: 'ellipsis' });
  });

  it('非备案域名上整个页脚不渲染', () => {
    withHostname('go.sailorvoyage.top');
    render(<IcpFooter />);
    expect(screen.queryByTestId('icp-footer')).toBeNull();
  });
});
