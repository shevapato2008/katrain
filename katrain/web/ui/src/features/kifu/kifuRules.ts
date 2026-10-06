export function kifuRulesLabel(rules: string | null | undefined, t: (key: string, fallback: string) => string): string {
  const known: Record<string, [string, string]> = {
    chinese: ['Chinese rules', '中国规则'], cn: ['Chinese rules', '中国规则'],
    japanese: ['Japanese rules', '日本规则'], jp: ['Japanese rules', '日本规则'],
    korean: ['Korean rules', '韩国规则'], ko: ['Korean rules', '韩国规则'],
    aga: ['AGA rules', 'AGA 规则'], 'aga-button': ['AGA button rules', 'AGA Button 规则'],
    'tromp-taylor': ['Tromp-Taylor rules', 'Tromp-Taylor 规则'],
    'new zealand': ['New Zealand rules', '新西兰规则'],
    'new-zealand': ['New Zealand rules', '新西兰规则'],
  };
  const label = known[rules?.trim().toLowerCase() ?? ''];
  return label ? t(...label) : t('kifu:rules_unresolved', '规则待核验');
}
