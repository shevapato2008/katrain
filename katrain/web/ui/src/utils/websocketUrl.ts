/**
 * 构造带凭据的 WebSocket URL。
 *
 * 为什么必须收成一处：`/ws/lobby` 两个调用点一直写着 `?token=${token}`，而对局的
 * `/ws/{session_id}` 三个调用点（useGameSession / useSessionBase / ZenModeApp）
 * 一个都没带。2026-08-04 的 `c751e8dd` 把 `/ws/{session_id}` 的鉴权从
 * 「只在 strict box 模式下检查」改成**无条件**检查之后，这三处在任何
 * 非 127.0.0.1 的部署上全部被 `close(1008, "Invalid token")` 拒掉 ——
 * 于是 AI 走的每一手都推不到浏览器。同一条规则散在 5 处，这就是它漂移的代价。
 *
 * 服务端取凭据的顺序（`katrain/web/core/box_sso.py::resolve_websocket_token`）：
 *   · strict box 模式：**只认 cookie**，query 里的 token 被忽略 —— 所以带上它
 *     不会影响盒子；
 *   · 其余情况：**先看 query 里的 `token`**，没有才回落到 `sb_token` cookie。
 *     而那个 cookie 只在 hostname == 127.0.0.1 时才会被签发
 *     （`auth.py::_issue_loopback_sso_cookie` 的主机名闸），所以线上部署
 *     除了 query 这一条没有别的路。
 *
 * 浏览器的 WebSocket 构造函数不能自定义请求头，query 参数是唯一能带凭据的位置
 * —— 这也是 `/ws/lobby` 早就这么做的原因。
 *
 * token 缺席时**不拼**空参数：盒子上靠 cookie 认证，拼一个 `?token=undefined`
 * 反而会让服务端拿它去验签然后失败。
 */
export function websocketUrl(path: string, token?: string | null): string {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const base = `${protocol}//${window.location.host}${path}`;
    return token ? `${base}?token=${encodeURIComponent(token)}` : base;
}

/** 服务端在拒绝凭据时用的 close code（RFC 6455 的 policy violation）。 */
export const WS_POLICY_VIOLATION = 1008;

/** 服务端回收一局时在 1008 的 `reason` 里发的暗号（`katrain/web/session.py`）。 */
export const WS_SESSION_GONE_REASON = 'session_gone';

/* 这一局在服务器上已经没有了(闲置回收 / 盒子重启 / 被删)。三条通道都可能先发现它:
   WS 被 1008 "session_gone" 关掉、任何动作回 404、或 200 `session_gone` 体。
   文案放这里是因为 `/ws/{session_id}` 有三个消费者(useGameSession / useSessionBase /
   ZenModeApp),只改一个 = 另外两屏把内部暗号 `session_gone` 原样印给用户、还叫他去重新登录。
   说的是「本机没有这一局了」,不是「你认输了」—— 回收会话不会结束远端对局。 */
export const SESSION_GONE_MESSAGE = '这一局在服务器上已经没有了，可以离开这一页。';
