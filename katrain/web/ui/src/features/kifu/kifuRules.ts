import type { VerifiedAnalysisParameters } from '../../types/kifu';

const known: Record<string, [string, string]> = {
  chinese: ['Chinese rules', '中国规则'], cn: ['Chinese rules', '中国规则'],
  japanese: ['Japanese rules', '日本规则'], jp: ['Japanese rules', '日本规则'],
  korean: ['Korean rules', '韩国规则'], ko: ['Korean rules', '韩国规则'],
  aga: ['AGA rules', 'AGA 规则'], 'aga-button': ['AGA button rules', 'AGA Button 规则'],
  'tromp-taylor': ['Tromp-Taylor rules', 'Tromp-Taylor 规则'],
  'new zealand': ['New Zealand rules', '新西兰规则'],
  'new-zealand': ['New Zealand rules', '新西兰规则'],
};

/** Event naming is display-only; analysis always retains its wire preset. */
export function kifuEventRules(parameters: VerifiedAnalysisParameters | null | undefined, rawRules: string | null | undefined): string | null | undefined {
  const wireRules = parameters?.rules ?? rawRules;
  const provenance = parameters?.provenance;
  const evidence = provenance?.evidence;
  if (parameters?.verified !== true || provenance?.source !== 'verified_evidence'
    || !evidence || typeof evidence !== 'object' || !('event_rules' in evidence) || typeof evidence.event_rules !== 'string') return wireRules;
  const eventRules = evidence.event_rules.trim().toLowerCase();
  if (!Object.hasOwn(known, eventRules)) return wireRules;
  const wire = parameters.rules.trim().toLowerCase();
  const japaneseOrKorean = ['japanese', 'jp', 'korean', 'ko'];
  return eventRules === wire || (japaneseOrKorean.includes(eventRules) && japaneseOrKorean.includes(wire)) ? eventRules : wireRules;
}

function isDefaultRules(parameters: VerifiedAnalysisParameters | null | undefined): boolean {
  return parameters?.version === 3 && parameters.verified === false && parameters.provenance.source === 'komi_default';
}

export function kifuRulesLabel(rules: string | null | undefined, t: (key: string, fallback: string) => string, parameters?: VerifiedAnalysisParameters | null): string {
  const key = rules?.trim().toLowerCase() ?? '';
  if (isDefaultRules(parameters)) {
    if (key === 'japanese' || key === 'jp') return t('kifu:japanese_rules_default', '日本规则（默认）');
    if (key === 'chinese' || key === 'cn') return t('kifu:chinese_rules_default', '中国规则（默认）');
  }
  const label = Object.hasOwn(known, key) ? known[key] : undefined;
  return label ? t(...label) : t('kifu:rules_unresolved', '规则待核验');
}

export function kifuDefaultRulesSource(parameters: VerifiedAnalysisParameters | null | undefined, t: (key: string, fallback: string) => string): string | null {
  if (!isDefaultRules(parameters)) return null;
  if (parameters?.rules === 'japanese') return t('kifu:japanese_rules_default_source', 'SGF 未记录规则；按贴目 6.5 默认采用日本规则，未核验赛事实际规则。');
  if (parameters?.rules === 'chinese') return t('kifu:chinese_rules_default_source', 'SGF 未记录规则；按贴目 7.5 默认采用中国规则，未核验赛事实际规则。');
  return null;
}
