type Translate = (key: string, fallback?: string) => string;

/** API source keys are provenance identifiers, not user-facing labels. */
export function kifuSourceLabel(source: string, t: Translate, lang: string): string {
  switch (source.toLowerCase()) {
    case 'golaxy': return t('kifu:source_golaxy', lang === 'cn' ? '星阵' : lang === 'tw' ? '星陣' : 'GoLaxy');
    case 'cwi': return 'CWI';
    case '19x19': return '19x19';
    default: return t('kifu:source_unknown', lang === 'cn' ? '来源待核实' : lang === 'tw' ? '來源待核實' : 'Source unverified');
  }
}
