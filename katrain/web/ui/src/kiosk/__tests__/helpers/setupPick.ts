import { screen } from '@testing-library/react';
import type userEvent from '@testing-library/user-event';

type User = ReturnType<typeof userEvent.setup>;

/**
 * 开局设置那一格下拉:点开 → 按 `data-k` 选。
 *
 * **按 `data-k` 而不是文案** —— 「9 路」的文案同时也命中「19 路」,
 * 用文案挑会在两个选项之间静默选错一个。
 *
 * 弹层 portal 到 `.kiosk-rail`,所以 `screen` 找得到;但它的**位置**在 jsdom 里
 * 恒为 0(没有布局引擎),所以这两个助手只用来断言「有哪些项、哪一项灰着」,
 * 位置和会不会盖住棋盘归真浏览器那条闸。
 */
export const pick = async (user: User, testId: string, key: string) => {
  await user.click(screen.getByTestId(testId));
  const pop = await screen.findByTestId(`${testId}-pop`);
  await user.click(pop.querySelector(`[data-k="${key}"]`) as HTMLElement);
};

export const openPick = async (user: User, testId: string) => {
  await user.click(screen.getByTestId(testId));
  return screen.findByTestId(`${testId}-pop`);
};
