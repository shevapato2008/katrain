import type { ReactNode } from 'react';
import PhysicalBoardGuard from './PhysicalBoardGuard';
import { readPlayOnBoard } from '../../utils/playInput';

/**
 * 对局那四条路由外面的那一层。
 *
 * `PhysicalBoardGuard requireRecognition` 本身没错 —— 它守的是「要用实体盘就得先标定」。
 * 错的是**它被无条件套在对局上**:开局设置屏上人刚选了「屏幕」,进来还是被推去标定工作台,
 * 那颗开关就只做了半截。
 *
 * ⇒ 选了屏幕就不走那道守卫。**不改 `PhysicalBoardGuard` 自己** —— 做题屏也用它,
 * 而做题的偏好是另一把键(默认相反,理由见 `utils/playInput.ts`),
 * 在守卫内部读某一把键会让另一家跟着变。
 *
 * 偏好默认 `true`,所以什么都不选的用户走的还是原来那条路 —— 这一层是**纯增量**。
 *
 * ⚠️ 偏好在这里**只读一次**(渲染时同步读 localStorage,不订阅变化):这一局落在哪儿
 * 是开局那一刻定的(「开局后不可改」),中途换掉等于把人从一块已经摆着子的盘上赶下来。
 */
const PlayInputGuard = ({ children }: { children: ReactNode }) => (
  readPlayOnBoard()
    ? <PhysicalBoardGuard requireRecognition>{children}</PhysicalBoardGuard>
    : <>{children}</>
);

export default PlayInputGuard;
