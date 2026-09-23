import { i18n } from '../../i18n';

/** 按服务端 detail 分辨升降级 503；兼容旧测试桩中的完整错误文本。 */
export type AiLadderUnavailableReason = 'offline' | 'not_authoritative' | 'engine_cannot_serve' | 'cloud_unconfirmed' | 'unknown';

export function aiLadderUnavailableReason(detail: string): AiLadderUnavailableReason {
  if (detail.includes('Remote server unavailable')) return 'offline';
  if (detail.includes('authority is unavailable')) return 'not_authoritative';
  if (detail.includes('cannot serve the seated rung')) return 'engine_cannot_serve';
  if (detail.includes('awaiting cloud')) return 'cloud_unconfirmed';
  return 'unknown';
}

/** `/ai-ladder/status` 的 503 提示。 */
export function aiLadderStatusUnavailableMessage(detail: string): string {
  return aiLadderUnavailableReason(detail) === 'offline'
    ? i18n.t('ladder:status_offline', '连不上云端。升降级对弈要联网，检查网络后点「重试」')
    : i18n.t('ladder:load_error_not_authoritative', '本机不记升降级成绩，暂时无法开始升降级对弈');
}

/** `/ai-ladder/start` 的 503 提示。云端未确认时不能断言这一局没有开成。 */
export function aiLadderStartUnavailableMessage(detail: string): string {
  switch (aiLadderUnavailableReason(detail)) {
    case 'offline':
      return i18n.t('ladder:start_offline', '连不上云端。升降级对弈要联网，本次没有开局，也不影响你的段位；检查网络后再试');
    case 'engine_cannot_serve':
      return i18n.t('ladder:start_engine_cannot_serve', '这台盒子的引擎现在带不动这一档对手。本次没有开局，也不影响你的段位');
    case 'cloud_unconfirmed':
      return i18n.t('ladder:start_cloud_unconfirmed', '云端还没确认这一局的状态，先别重复开局；回到这一屏会显示它的状态');
    case 'not_authoritative':
      return i18n.t('ladder:load_error_not_authoritative', '本机不记升降级成绩，暂时无法开始升降级对弈');
    default:
      return i18n.t('ladder:engine_unavailable_start', '升降级引擎暂时不可用，本次没有开局，也不影响你的段位。请稍后再试。');
  }
}
