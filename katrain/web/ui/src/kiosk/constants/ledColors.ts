/** Fixed LED colour semantics for physical play / tsumego / baipu (§5.2, §5.5). */
export type LedIntent = 'black' | 'white' | 'remove' | 'hint';

export const LED_HEX: Record<LedIntent, string> = {
  black: '#ff3b30',  // 红
  white: '#34c759',  // 绿
  remove: '#2f6fff', // 蓝
  hint: '#ffffff',   // 白 (提示 / 庆祝)
};

export const LED_LABEL: Record<LedIntent, string> = {
  black: '红',
  white: '绿',
  remove: '蓝',
  hint: '白',
};
