type TFn = (key: string, fallback?: string) => string;

/** Platform metadata describes provenance, never ownership or participation of imported records. */
export function reportPlatformLabel(game: { source: string | null; platform?: string | null }, t: TFn): string | null {
  if (game.source !== 'play_ai' && game.source !== 'play_human') return null;
  const platform = game.platform === 'golaxy' ? t('report:platform_golaxy', 'Golaxy')
    : game.platform === 'ogs' ? t('report:platform_ogs', 'OGS')
      : game.platform === 'fox' ? t('report:platform_fox', 'Fox') : null;
  return platform ? t('report:cross_platform', 'Cross-platform · {platform}').replace('{platform}', platform) : null;
}
