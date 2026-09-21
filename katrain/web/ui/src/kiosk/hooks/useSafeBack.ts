import { useCallback, useEffect, useRef } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';

/**
 * 「返回」的安全版:退一步,但**只在 katrain 自己的历史里退,且一次进入只退一次**。
 *
 * 盒子上启动器、象棋、围棋共用一个浏览器 ⇒ 历史里夹着别家 app 的页面,而启动器切走时
 * 会把那家服务停掉。裸 `navigate(-1)` 在 RK3562 上(2026-09-21)这样出过事:标定收尾时
 * 板子卡住 6–8 s,用户连点 3 下没反应,点击排队,恢复后每一下都在**还没换走的这一页**上
 * 各退一步 ⇒ 连退 4 步退出 katrain,落到已停的象棋页「无法访问此网站」。
 *
 * `history.state.idx` 是 React Router 给本 app 每条历史记的序号,0 = 进 app 的第一条,
 * 在它上面再退就是退出 katrain ⇒ 改去 `fallback`(本模块首页)。
 */
export function useSafeBack(fallback: string): () => void {
  const navigate = useNavigate();
  const { key } = useLocation();
  const leaving = useRef(false);
  // 换了一条历史才重新允许(同一组件换参数时组件不卸载,不重置就会把返回键锁死)。
  useEffect(() => { leaving.current = false; }, [key]);
  return useCallback(() => {
    if (leaving.current) return;
    leaving.current = true;
    const idx = (window.history.state as { idx?: number } | null)?.idx ?? 0;
    if (idx > 0) navigate(-1);
    else navigate(fallback, { replace: true });
  }, [navigate, fallback]);
}
