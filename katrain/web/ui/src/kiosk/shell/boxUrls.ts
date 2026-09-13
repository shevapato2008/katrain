// 盒子上 setup-wizard(launcher)的源。围棋模块页跑在 :8081、launcher 在 :8080 ——
// **同主机不同端口 ⇒ 跨源**,不是路由:去那边只能整页离开,react-router 到不了。
//
// 横向规范 §8.1 规则 3「登录跳转目标由外壳提供,不许各棋类硬编码」
// (`smartbox-software/superpowers/shared/ranked-play-unified-architecture-2026-08-09.md`,
// 被点名的反例是国象 `chess/ui/src/rated/RatingPlayPage.tsx`)。围棋的外壳就是 kiosk
// 自己,所以**这个文件是全仓唯一持有这个地址的地方**;五子棋对应的那份是
// `gomoku/ui/src/shell/loginTarget.ts`。2026-09-13 收编前,地址写在 `KioskLayout` 的
// 主页键里(那时只有一个消费者;登录页要用第二次,再抄一遍迟早分叉)。
const WIZARD_ORIGIN = 'http://127.0.0.1:8080';

/** 「返回智星盒主页」的落点。 */
export const LAUNCHER_URL = `${WIZARD_ORIGIN}/launcher`;

/**
 * 「去登录」的落点。
 *
 * 🔴 **绝不能带 `?logout=1`**,哪怕从围棋这边看语义更贴切。板上实测
 * (`setup-wizard/app/static/js/launcher.js:378-390`):`logout=1` 走
 * `performLogoutThenGate()`,而 `POST /api/auth/logout` 在没有 `sb_session` 时回 401,
 * 前端随即 `showRetirementError()` —— 那是一块**故意不暴露登录表单**的 fail-closed
 * 错误屏(注释写明是 R2-F3 的决定)。而围棋走到登录页时恰恰**不知道**盒上还有没有
 * wizard 会话:它只知道自己的 `/me` 401 了,那两件事有各自的生命周期。
 *
 * `?authmode=login` 两种情形都安全:有会话 → `checkAuth()` 落回 launcher 主页
 * (那页永远有出口),没会话 → 直接出登录表单。
 */
export const LAUNCHER_LOGIN_URL = `${LAUNCHER_URL}?authmode=login`;

/**
 * 严格盒端(出厂盒子)那一档。
 *
 * 这一档里 JS 永远拿不到 token、`POST /api/v1/auth/login` 恒 403
 * (`katrain/web/api/v1/endpoints/auth.py:231-234`),身份的唯一权威是 launcher。
 *
 * ⚠️ **判据必须是它,不能是 `__KIOSK_2D_ONLY__`。** 非严格的 kiosk 包可能跑在别的
 * 机器上,那里 `127.0.0.1:8080` 什么都没有 —— 把人导过去是浏览器错误页,比今天更糟。
 */
export const isStrictBoxKiosk =
  __KIOSK_2D_ONLY__ && import.meta.env.VITE_BOX_SSO_STRICT === 'true';

/** 整页导航。目标是另一个源上的应用,`navigate()` 到不了。 */
export function leaveToLauncher(url: string = LAUNCHER_URL): void {
  window.location.assign(url);
}
