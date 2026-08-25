/* spec-sync: 3.2 rev=2026-08-22 sha=f861d7e1
 *
 * 这一行由 `superpowers/tracks/galaxy-ui-redesign/check_spec_sync.py` 对账：
 * `sha` 是规范 §3.2 正文的哈希。规范正文一改、这里没跟，闸就会指名道姓说
 * 「这一处没跟上规范」—— 2026-08-22 §2.4 改写时，冻结原型就是这样悄悄留在
 * 裁定前的形状、一路活到 S8 才被人工比对抓到。
 * 看过新条款、确认本文件确实跟上了，再跑 `check_spec_sync.py --update` 写回 sha。
 */
import { useCallback, useState } from 'react';

export function useBoardCoordinates(edge: number) {
  const [userOverride, setUserOverride] = useState<boolean | null>(null);
  const visible = userOverride ?? edge >= 500;

  const toggle = useCallback(() => {
    setUserOverride((currentOverride) => !(currentOverride ?? edge >= 500));
  }, [edge]);

  const resetToAutomatic = useCallback(() => {
    setUserOverride(null);
  }, []);

  return { visible, userOverride, toggle, resetToAutomatic };
}
