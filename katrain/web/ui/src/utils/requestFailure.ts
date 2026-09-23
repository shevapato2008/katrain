/**
 * 请求失败分几类 —— **屏上怎么说由调用方定,这里只分类**。
 *
 * 为什么要分:盒上报告与对局接口经本机服务代理云端(`RepositoryDispatcher._remote_only`),
 * 云端真连不上、和云端自己回 ≥500 这两种情况都落回同一个 503(`_remote_only` 两条都抛
 * `RemoteServiceUnavailableError`,分不出到底是哪一种,所以这一档只敢说「暂时不可用」,
 * 不敢说「连不上」)。屏 20 以前一律写「未找到复盘。」,再把 `Request failed 503: {…}`
 * 印在下面:「服务不可用」被说成「找不到」,那段原文用户也看不懂(2026-09-14 调研 N24)。
 *
 * 判据只认**数字 `status`**,不认类。`reportApi` / `userGamesApi` 的 `authFetch`、`api.ts` 的
 * `ApiError`、`AiLadderApiError` 都带它。在 catch 块里做 `instanceof`,模块被 mock 掉时会自己抛
 * (`kiosk/pages/AiSetupPage.tsx` 那段注释踩过)。没有 status 的一律 `other`,**不猜**:
 * `fetch` 自己抛的 TypeError 在盒上意味着本机服务没起,那时这一屏本身就不在了。
 *
 * 这个文件在共享领地(两个构建都打进去),不许 import `src/kiosk/**` / `src/galaxy/**`。
 */
export type RequestFailureKind = 'offline' | 'not_found' | 'no_credits' | 'bad_sgf' | 'other';

/** 后端 `HTTPException(detail={"code": …})` 的那个 code。body 不是这个形状就是 null。 */
function detailCode(body: unknown): string | null {
  if (typeof body !== 'string' || body === '') return null;
  try {
    const parsed = JSON.parse(body) as { detail?: { code?: unknown } } | null;
    const code = parsed?.detail?.code;
    return typeof code === 'string' ? code : null;
  } catch {
    return null;
  }
}

export function requestFailureKind(error: unknown): RequestFailureKind {
  const carrier = (typeof error === 'object' && error !== null ? error : {}) as {
    status?: unknown;
    body?: unknown;
  };
  if (typeof carrier.status !== 'number') return 'other';
  const { status } = carrier;
  if (status === 502 || status === 503 || status === 504) return 'offline';
  if (status === 404) return 'not_found';
  const code = detailCode(carrier.body);
  // 402 来自 `endpoints/reports.py` 的计费闸(今天关着);只认 code,不认状态码本身。
  if (status === 402 && code === 'insufficient_credits') return 'no_credits';
  if (status === 400 && code === 'unparsable_sgf') return 'bad_sgf';
  return 'other';
}

/**
 * 读的是「云端失败就退本机缓存」的接口时用这个。今天只有盒上的 `GET /user-games/{id}`:
 * `core/repository.py` 的 `user_games_get` 在云端连不上 / 超时 / 回任何 HTTP 错时都退回本机缓存,
 * 缓存里没有,`endpoints/user_games.py` 的 `get_user_game` 也回 404。
 * ⇒ 这条 404 **证明不了云端没有这一局**(列表从云端读到、随后断网、点一局本机没缓存过的,就是它),
 * 说「已经不在了」是编原因。降为 `other`,屏上只说「做什么没成」。
 *
 * 报告接口(`endpoints/reports.py` 的 `_dispatch_remote_only`)与删除(`_remote_only`)不退缓存,
 * 上游 404 原码透传,那里的 404 是云端说的,照用 `requestFailureKind`。
 */
export function cacheBackedReadFailureKind(error: unknown): RequestFailureKind {
  const kind = requestFailureKind(error);
  return kind === 'not_found' ? 'other' : kind;
}
