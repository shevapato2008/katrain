import { interpolate } from './interpolate';

/**
 * `/api/v1/health` 里 `engines.local` / `engines.cloud` 的值翻成设置屏「关于」那一行的人话。
 *
 * **四种值是四件事**(`endpoints/health.py`):
 *  · `reachable` —— 可用;
 *  · `unreachable` —— 连不上;
 *  · `unconfigured` —— 这台根本没配云端。说成「连不上」会让人去查网络,所以单独一句;
 *  · `error_<code>` —— 连上了但对方回了错。归「连不上」,把码留在副标里:
 *    屏上一行人话,底下一行报修时能念给客服听的证据。
 * 认不出来的值**原样写出来**,不猜。
 */
export interface EngineStatusLine {
  text: string;
  sub?: string;
  ok: boolean;
}

export function engineStatusLine(state: string, t: (key: string, fallback: string) => string): EngineStatusLine {
  if (state === 'reachable') return { text: t('settings:engine_ok', '可用'), ok: true };
  if (state === 'unreachable') return { text: t('settings:engine_down', '连不上'), ok: false };
  if (state === 'unconfigured') return { text: t('settings:engine_unset', '没配置'), ok: false };
  const code = /^error_(.+)$/.exec(state)?.[1];
  if (code) {
    return {
      text: t('settings:engine_down', '连不上'),
      sub: interpolate(t('settings:engine_code', '引擎回了 {code}'), { code }),
      ok: false,
    };
  }
  return { text: state, ok: false };
}
