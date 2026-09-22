/**
 * kiosk 的活动数据**不在裸 `localStorage` 里**。
 *
 * `1d5f67a0`(盒子 SSO 的第 4 层零留存)之后,摆谱缓存 / 摆谱进度 / 最近摆过 /
 * 死活进度 / 活动会话一律走 `kioskActivityStorage(identityKey, isGuest)`:
 *
 *   · 访客,**或身份未解析(`user.uuid` 取不到)** → 内存 Map,一个字节都不碰 localStorage
 *   · 真用户 → localStorage,每个键后缀 `:${user.uuid}`
 *
 * 于是 e2e 里「种子写裸键 + `/me` 不给 uuid」这个老写法**两头都断**:写进去的读不到,
 * 页面渲染它**正确的**空态,而断言停在一个永远不出现的选择器上超时 30 秒 ——
 * 报错指向选择器,看起来像被测页面挂了。
 *
 * 2026-09-21 实测:`baipu.spec.ts` 8 条 + 屏 15 / 屏 17 两张四图,共 10 条就是这样红的,
 * 而仓里屏 15 / 屏 17 的实现图是 `1d5f67a0` 之前拍的 —— **存档画着代码已经产不出来的内容**。
 *
 * 用法:`/me` 回 `kioskMeJson()`,种子键用 `scopedKey()` 包一层。两者缺一不可。
 */

/**
 * e2e 统一的身份键。`/me` 给的 `uuid` 和种子键的后缀**必须是同一个**。
 *
 * 取值 `'u1'` 是**故意跟旧写法对齐**:`1d5f67a0` 之前后缀是 `u${user.id}`,
 * 而 `/me` 一直回 `id: 1` ⇒ 仓里一大批夹具的种子键写死成 `...:u1`。
 * 把 uuid 也定成 `'u1'`,那些键名一个字都不用改,只补 `/me` 里缺的那个字段。
 */
export const KIOSK_E2E_UUID = 'u1';

/** 把一个逻辑键变成它在 localStorage 里的真实键名。 */
export const scopedKey = (key: string, uuid: string = KIOSK_E2E_UUID) => `${key}:${uuid}`;

/**
 * `/api/v1/auth/me` 的载荷。
 *
 * ⚠️ `username` 不能是 `'guest'` —— `AuthContext` 用 `user?.username === 'guest'` 判访客,
 * 判成访客就又回内存 Map 了。想拍「访客」那一态的屏,传 `{ username: 'guest' }`,
 * 并且别指望种子能读到(那正是访客该看到的)。
 */
export const kioskMeJson = (over: Record<string, unknown> = {}) => ({
  id: 1,
  uuid: KIOSK_E2E_UUID,
  username: 'tester',
  rank: '5段',
  credits: 0,
  ...over,
});
