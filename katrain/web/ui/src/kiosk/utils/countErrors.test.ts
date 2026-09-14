import { describe, expect, it } from 'vitest';
import { ApiError } from '../../api';
import { countErrorCode, countErrorMessage } from './countErrors';

const t = (key: string, fallback?: string) => fallback ?? key;
const api400 = (detail: unknown) => new ApiError(400, 'Request failed 400: …', detail);

// 判据落在**屏上那句话**,不只落在 code 上:code 对了而文案接错一格,用户照样被说错原因。
describe('数子失败的原因 → 文案', () => {
  it.each([
    ['新后端 · analysis_pending', api400({ code: 'analysis_pending', message: 'x' }), 'analysis_pending', '还在算这一手的形势，稍等再数'],
    ['新后端 · below_min_moves', api400({ code: 'below_min_moves', message: 'x' }), 'below_min_moves', '手数还不够，暂时不能数子'],
    ['新后端 · game_over', api400({ code: 'game_over', message: 'x' }), 'game_over', '这一局已经结束了'],
    ['老后端 · 分析没回来', api400('Analysis not available yet. Please wait for KataGo analysis to complete.'), 'analysis_pending', '还在算这一手的形势，稍等再数'],
    ['老后端 · 手数不足', api400('Cannot count before 100 moves'), 'below_min_moves', '手数还不够，暂时不能数子'],
    ['老后端 · 已终局', api400('Game is already over'), 'game_over', '这一局已经结束了'],
    ['网络层(fetch 直接抛)', new TypeError('Failed to fetch'), 'network', '分析服务连不上'],
    ['其它 HTTP 拒绝', new ApiError(403, 'Request failed 403: …', 'Not authorized'), 'http', '数子失败（403），请重试'],
    ['400 但 code 不认识', api400({ code: 'something_new' }), 'http', '数子失败（400），请重试'],
  ] as const)('%s', (_name, err, code, message) => {
    expect(countErrorCode(err)).toBe(code);
    expect(countErrorMessage(err, t)).toBe(message);
  });
});
