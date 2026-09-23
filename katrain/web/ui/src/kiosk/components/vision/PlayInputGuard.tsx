import type { ReactNode } from 'react';
import { useLocation } from 'react-router-dom';
import PhysicalBoardGuard from './PhysicalBoardGuard';
import { readSessionPlayOnBoard } from '../../utils/playInput';

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
 * ⚠️ 读的是**开局那一刻定下的值**(`readSessionPlayOnBoard`):活动会话就是当前这一局时,
 * 用开局屏算好的 `onBoard`(设备 ∧ 偏好 ∧ 19 路)—— 9/13 路的局偏好开着也不会被拦去标定(P8);
 * 否则回落偏好。与 `GamePage` 的 `physicalPlay` 读同一个函数,两边不许给出两个答案。
 * 只在渲染时同步读,不订阅变化:这一局落在哪儿开局后不可改。
 */
const PlayInputGuard = ({ children }: { children: ReactNode }) => {
  const { pathname } = useLocation();
  return readSessionPlayOnBoard(pathname).onBoard
    ? <PhysicalBoardGuard requireRecognition sub="在实体盘上对弈，要先让摄像头看清盘面">{children}</PhysicalBoardGuard>
    : <>{children}</>;
};

export default PlayInputGuard;
