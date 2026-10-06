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

/** Event naming is display-only; analysis always retains its verified wire preset. */
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

export function kifuRulesLabel(rules: string | null | undefined, t: (key: string, fallback: string) => string): string {
  const key = rules?.trim().toLowerCase() ?? '';
  const label = Object.hasOwn(known, key) ? known[key] : undefined;
  return label ? t(...label) : t('kifu:rules_unresolved', '规则待核验');
}
