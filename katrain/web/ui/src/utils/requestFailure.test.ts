import { describe, expect, it } from 'vitest';

import { cacheBackedReadFailureKind, requestFailureKind } from './requestFailure';

const httpError = (status: number, body = '') =>
  Object.assign(new Error(`Request failed ${status}: ${body}`), { status, body });

describe('requestFailureKind —— 请求失败分几类', () => {
  // 盒上报告 / 对局接口经本机服务代理云端,云端连不上时本机回 503「Remote … unavailable」。
  it('502 / 503 / 504 是连不上', () => {
    expect(requestFailureKind(httpError(503, '{"detail":"Remote report service unavailable"}'))).toBe('offline');
    expect(requestFailureKind(httpError(502))).toBe('offline');
    expect(requestFailureKind(httpError(504))).toBe('offline');
  });

  it('404 是找不到 —— 和连不上分开说', () => {
    expect(requestFailureKind(httpError(404, '{"detail":"Report task not found"}'))).toBe('not_found');
  });

  // 计费闸今天关着(BILLING_ENFORCED 默认 False 且读不到 env);开闸后创建报告会回这个。
  it('402 且 code 是 insufficient_credits 才算积分不足', () => {
    expect(requestFailureKind(httpError(402, '{"detail":{"code":"insufficient_credits","need":125,"have":0}}')))
      .toBe('no_credits');
    expect(requestFailureKind(httpError(402, 'Payment Required'))).toBe('other');
  });

  it('400 且 code 是 unparsable_sgf 是谱读不出来', () => {
    expect(requestFailureKind(httpError(400, '{"detail":{"code":"unparsable_sgf","message":"bad"}}'))).toBe('bad_sgf');
    expect(requestFailureKind(httpError(400, '{"detail":"Only failed tasks can be retried"}'))).toBe('other');
  });

  // 分不出就说分不出:不许把一个没有状态码的错猜成「连不上」。
  it('没有数字 status 的错、以及其余状态码,一律 other', () => {
    expect(requestFailureKind(new Error('boom'))).toBe('other');
    expect(requestFailureKind(new TypeError('Failed to fetch'))).toBe('other');
    expect(requestFailureKind('no details')).toBe('other');
    expect(requestFailureKind(null)).toBe('other');
    expect(requestFailureKind(Object.assign(new Error('x'), { status: '503' }))).toBe('other');
    expect(requestFailureKind(httpError(409, 'report already exists'))).toBe('other');
  });

  // `api.ts` 的 `ApiError`、`features/aiLadder` 的 `AiLadderApiError` 只带 status 不带 body。
  it('只带 status 不带 body 的错(ApiError 形状)也能分', () => {
    expect(requestFailureKind(Object.assign(new Error('Request failed 503: x'), { status: 503 }))).toBe('offline');
  });
});

describe('cacheBackedReadFailureKind —— 读的是「云端失败退本机缓存」的接口', () => {
  // 盒上 GET /user-games/{id}:云端连不上 / 超时 / 回任何 HTTP 错都退本机缓存,缓存里没有也回 404。
  // 这条 404 证明不了「云端没有这一局」,不许被说成「已经不在了」。
  it('404 降为 other,其余照 requestFailureKind', () => {
    expect(cacheBackedReadFailureKind(httpError(404, '{"detail":"Game not found"}'))).toBe('other');
    expect(cacheBackedReadFailureKind(httpError(503))).toBe('offline');
    expect(cacheBackedReadFailureKind(new Error('boom'))).toBe('other');
  });
});
