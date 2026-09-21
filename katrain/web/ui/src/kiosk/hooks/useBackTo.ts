import { useCallback } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';

/**
 * 「返回」**只去写明的那一页,不走浏览器历史**。
 *
 * 盒子上启动器、象棋、围棋共用一个浏览器 ⇒ 历史里夹着别家 app 的页面,而启动器切走时
 * 会把那家服务停掉。按历史后退在 RK3562 上(2026-09-21)这样出过事:标定收尾时板子卡住
 * 6–8 s,用户连点 3 下,点击排队,恢复后连退 4 步退出 katrain,落到已停的象棋页
 * 「无法访问此网站」。(排队的点击只算一次,是 `KioskPagebar` 返回键自己挡的。)
 *
 * 大多数屏只有一个上一级,直接写死在 `onBack` 里。这个 hook 给**能从好几处进来**的屏用
 * (对局/做题/摆谱前面拦下来的标定台、设置里的标定页):去哪儿由**打开它的那一页**
 * 用 `backToState` 写进导航 state;没写(继续上一局、从别处直接进)就去 `fallback`
 * (本模块首页)。只认 `/kiosk/` 开头的路径 ⇒ 返回出不了 katrain。
 */
export function backToState({ pathname, search }: { pathname: string; search: string }) {
  return { backTo: pathname + search };
}

export function readBackTo(state: unknown): string | null {
  const to = (state as { backTo?: unknown } | null)?.backTo;
  return typeof to === 'string' && to.startsWith('/kiosk/') ? to : null;
}

export function useBackTo(fallback: string): () => void {
  const navigate = useNavigate();
  const target = readBackTo(useLocation().state) ?? fallback;
  return useCallback(() => navigate(target), [navigate, target]);
}
