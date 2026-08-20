import { Icon } from './icons';
import { DOCK_TABS, dockActiveOf } from './dockRoutes';

/**
 * §7 Dock:通栏贴底、高 82、≤7 项等宽、图标 24、标签 12.5px Sans 600、
 * 选中 = 强调色实底 + `translateY(-2px)`。全部由 `tokens.css:377-412` 给,
 * 这里只负责结构、词、图标和高亮 —— **一行 sx / style 都不写**。
 *
 * 用 `<button>` 不用 `<a>`:稿子就是 button,tokens.css 因此从没写 `text-decoration`,
 * 换成 `<a>` 会平白多出一条下划线。
 *
 * 高亮走 `aria-current="page"` 而不是一个 `is-active` 类:tokens.css 的选择器就是
 * `[aria-current="page"]`,而且它同时是**说给读屏听**的那一份 —— 两件事一个属性办了。
 */
export function KioskDock({ pathname, onTab }: {
  pathname: string;
  onTab: (path: string) => void;
}) {
  const active = dockActiveOf(pathname);
  return (
    <nav className="kiosk-dock" aria-label="主导航">
      {DOCK_TABS.map((tab) => {
        const on = active === tab.path;
        return (
          <button
            key={tab.path}
            type="button"
            className="kiosk-dock__item"
            aria-current={on ? 'page' : undefined}
            onClick={() => onTab(tab.path)}
          >
            <Icon name={tab.icon} filled={on} />
            <span className="kiosk-dock__label">{tab.label}</span>
          </button>
        );
      })}
    </nav>
  );
}
