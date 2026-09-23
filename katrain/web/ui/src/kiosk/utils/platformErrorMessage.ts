/**
 * 跨平台屏（连接/开局/大厅）报错时该读哪个字段。`ApiError.detail` 是后端 `HTTPException(detail=…)`
 * 原样透传的那一格 —— 409/403 这类「原因码出文案」的错误，`detail` 就是那句人话本身
 * （例如「这台盒子上现在连着别人的星阵账号 · 去设置里断开后再登录」）。
 *
 * `error.message` 是 `apiPost` 拼出来给日志看的 `Request failed 409: {"detail":"…"}`，
 * 整段原样印到屏上会把这句人话埋进 JSON 里（`api.ts` 里 `ApiError.detail` 的文档注释
 * 明确写着「按原因码出文案的一方读它,不要去 parse message」）。
 *
 * 不用 `e instanceof ApiError`:**这是 catch 块,它自己不许再抛**。`instanceof` 依赖那个
 * 类此刻真的是个构造函数 —— 这几屏的单测把 `../../api` 整个 mock 掉,`ApiError` 会是
 * `undefined`,`e instanceof undefined` 当场 TypeError（`AiSetupPage.tsx` 的同类注释踩过
 * 同一个坑）。改认形状:`status` 是数字、`detail` 是非空字符串,就当它是 `ApiError`。
 */
export function platformErrorMessage(error: unknown, fallback: string): string {
  const carrier = (typeof error === 'object' && error !== null ? error : {}) as {
    status?: unknown;
    detail?: unknown;
    message?: unknown;
  };
  if (typeof carrier.status === 'number') {
    // 是个 ApiError 形状的错误:detail 不是非空字符串(对象,或这一格根本没有)时,
    // .message 是那串带状态码 + JSON 的调试文本 —— 印它比印兜底文案更差,不当退路。
    return typeof carrier.detail === 'string' && carrier.detail ? carrier.detail : fallback;
  }
  return typeof carrier.message === 'string' && carrier.message ? carrier.message : fallback;
}
