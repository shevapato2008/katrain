import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { PlatformLoginAside } from './PlatformLoginAside';
import { KioskCard } from '../../shell/KioskCard';
import { PLATFORM_MARKS } from '../../constants/platformMarks';

/**
 * 平台品牌标记的两条闸。
 *
 * ## 为什么需要它们
 *
 * 换标记这件事**整套单测一条都没碰到** —— 1487 条全绿地走过了从地球换成三家真标记的
 * 改动。原因是标记只影响「画出来是什么」,而这两处的既有测试问的都是文案和跳转。
 * 于是「某家的标记悄悄没了、退回绿色地球」会是一次**静默降级**:屏上仍然有个图标、
 * 不报错、不变红,只是认不出是谁家了。
 *
 * ## 第二条测的是一条今天在生产里跑不到的分支
 *
 * `PLATFORM_MARKS` 查不到时回落到地球(而不是像 `Icon` 那样抛),是为了让服务端
 * `/platforms` 多下发一家新平台时不至于把首页打白。但今天下发的三家**都有标记**,
 * 所以那条 `else` 在真实运行里永远不执行 —— 不造状态就没有任何东西证明它是对的,
 * 而它恰恰是出事那天唯一挡在用户和白屏之间的东西。这里显式造出「不认识的平台」。
 */

describe('平台品牌标记', () => {
  it('三家各自渲染自己的标记,不是回落的地球', () => {
    // 表本身就是判据:测试不重抄一遍 src,否则改表时测试跟着改、永远不会红。
    for (const [platform, mark] of Object.entries(PLATFORM_MARKS)) {
      const { container, unmount } = render(
        <KioskCard title={platform} sub="" icon="globe-hemisphere-west" mark={mark} />,
      );
      const img = container.querySelector('.kiosk-card__mark');
      expect(img, `${platform} 没画出标记`).not.toBeNull();
      expect(img).toHaveAttribute('src', mark.src);
      // 回落的地球是内联 svg;标记在时不该同时出现。
      expect(container.querySelector('.kiosk-icon svg')).toBeNull();
      unmount();
    }
    // 三家都在表里 —— 少一家就是有人删了条目而没改调用方。
    expect(Object.keys(PLATFORM_MARKS).sort()).toEqual(['fox', 'golaxy', 'ogs']);
  });

  it('圆形标记(OGS)带 is-disc,自带方底的(星阵/野狐)不带', () => {
    // `is-disc` 决定缩到 62% 并加那圈分界环。丢了它,棋子黑的那半会融进深色衬,
    // 屏上只剩一个白色半圆 —— 这是视觉缺陷,四图能看见,但四图只在有人重拍时才看。
    const { container: ogs } = render(
      <KioskCard title="OGS" sub="" mark={PLATFORM_MARKS.ogs} />,
    );
    expect(ogs.querySelector('.kiosk-card__tile')?.className).toContain('is-disc');
    const { container: gx } = render(
      <KioskCard title="星阵" sub="" mark={PLATFORM_MARKS.golaxy} />,
    );
    expect(gx.querySelector('.kiosk-card__tile')?.className).not.toContain('is-disc');
  });

  it('登录页左栏:认识的平台画标记', () => {
    const { container } = render(<PlatformLoginAside platform="golaxy" />);
    const markEl = container.querySelector('.xpwho .mark');   // 见下一条里那段说明:不写三级后代选择器
    expect(markEl!.querySelector('img')).toHaveAttribute('src', PLATFORM_MARKS.golaxy.src);
    expect(markEl!.className).toContain('is-brand');
  });

  it('不认识的平台回落到地球,不抛 —— 这条分支今天在生产里跑不到', () => {
    // 服务端哪天多返回一家我们没有标记的平台是**正常事件**。照 `Icon` 那样抛,
    // 会因为服务端多了一行就把整屏打白。
    expect(() => render(<PlatformLoginAside platform="a-platform-we-have-never-seen" />)).not.toThrow();
    const { container } = render(<PlatformLoginAside platform="a-platform-we-have-never-seen" />);
    // ⚠️ 先取到 `.mark` 再在**它内部**查,不要写 `.xpwho .mark .kiosk-icon` 这种三级后代选择器:
    // jsdom 的选择器引擎在这份 DOM 上对它返回 null,而 `.xpwho .mark` 和 `.kiosk-icon`
    // 各自都命中(实测三者的字面量都是纯 ASCII,DOM 也确实是 .xpwho > .mark > .kiosk-icon)。
    // 真浏览器里这条是对的,所以它是测试环境的坑,不是产品缺陷 —— 但在这儿写下来,
    // 免得下一个人又花时间去追。**元素作用域的写法在两边都对**,一律用它。
    const markEl = container.querySelector('.xpwho .mark');
    expect(markEl).not.toBeNull();
    expect(markEl!.querySelector('img')).toBeNull();
    expect(markEl!.querySelector('.kiosk-icon')).not.toBeNull();
    // 回落时衬要保持原样(accent 染色的图标底衬),不能套上放外来物的凹槽。
    expect(markEl!.className).not.toContain('is-brand');
  });
});

describe('标记文件本身', () => {
  it('每一项都指向一个真的构建产物,不是空串', () => {
    // Vite 把图片 import 解析成 URL 字符串。表里写错路径时 import 会在构建期炸,
    // 但写成空串/undefined 不会 —— 那时屏上是个空衬,而空衬和「还没加载」长得一样。
    for (const [platform, mark] of Object.entries(PLATFORM_MARKS)) {
      expect(mark.src, `${platform} 的 src 是空的`).toBeTruthy();
      expect(typeof mark.src).toBe('string');
    }
  });
});

describe('screen 可及性', () => {
  it('标记是装饰:不进可及树,卡片的可及名由标题/副标/徽标给', () => {
    render(<KioskCard title="野狐围棋" sub="接口还没通" mark={PLATFORM_MARKS.fox} soon="暂不能对弈" />);
    const btn = screen.getByRole('button', { name: '野狐围棋，接口还没通，暂不能对弈' });
    expect(btn).toBeInTheDocument();
    // `alt=""` 的图片不该带 img role 出现在可及树里。
    expect(screen.queryByRole('img')).toBeNull();
  });
});
