export interface ShellIdentity {
  username?: string;
}

/**
 * 顶栏右簇的身份呈现。规范 §6:头像是**强调色实底 + 深色首字**(没登录显示「访」),
 * 不是空心描边圈。
 *
 * 两处细节:
 * - 首字母大写只对拉丁生效 —— 中文 `toUpperCase()` 是恒等,写一次两边都对。
 * - 取首字用 `[...name][0]` 不是 `name[0]`:后者切的是 UTF-16 码元,
 *   遇到代理对(如 '𠮷')会切出半个,屏上渲成 �。
 */
export function identityPresentation(identity: ShellIdentity): { avatar: string; label: string } {
  const name = identity.username?.trim();
  if (!name) return { avatar: '访', label: '访客' };
  return { avatar: [...name][0].toUpperCase(), label: name };
}
