import type { IconName } from '../shell/icons';

/**
 * Tsumego unit-grouping constants + the Phase 4 prev/next sequence contract.
 * Kept in a non-component module so the unit pages stay react-refresh clean.
 */

/** Problems per unit (matches galaxy D5). */
export const UNIT_SIZE = 20;

/**
 * sessionStorage key for the ordered full-category problem-id sequence.
 * Value = JSON.stringify(string[]) — problem ids in display order.
 * Phase 4 (TsumegoProblemPage) reads this to compute prev/next + boundaries.
 *
 * NOTE: the `kiosk_` prefix deliberately differs from galaxy's `problems_${level}_${category}`
 * key (galaxy stores ProblemListItem[] objects, kiosk stores string[]). Keeping them distinct
 * prevents the two build outputs from corrupting each other's cache if ever loaded in the same
 * browser (e.g. during dev), since the shared-zone hook is used by both.
 */
export const sequenceKey = (level: string, category: string) => `kiosk_problems_${level}_${category}`;

/**
 * 读那条顺序表。**读不到和读到一条空的是两回事**:前者返回 `null`(该去取),
 * 后者返回 `[]`(这一类真的没题)—— 合成一个值会让「还没取过」被当成「取过了,是空的」。
 */
export function readSequence(level: string, category: string): string[] | null {
  try {
    const raw = sessionStorage.getItem(sequenceKey(level, category));
    if (raw === null) return null;
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? (parsed as string[]) : null;
  } catch {
    return null;
  }
}

/** 写那条顺序表。写不进去(隐私模式 / 配额)不算错 —— 消费方各自还有自己取一次的退路。 */
export function writeSequence(level: string, category: string, ids: string[]): void {
  try {
    sessionStorage.setItem(sequenceKey(level, category), JSON.stringify(ids));
  } catch {
    /* best-effort */
  }
}

/**
 * localStorage key for the "auto-advance to next problem after solving" preference (D4).
 * Default is ON (true) when unset.
 */
export const AUTO_ADVANCE_KEY = 'kiosk_tsumego_autoadvance';

/** Read the auto-advance preference. Defaults to true when unset / unparseable. */
export function readAutoAdvance(): boolean {
  try {
    const v = localStorage.getItem(AUTO_ADVANCE_KEY);
    if (v === null) return true; // default ON
    return v === 'true';
  } catch {
    return true;
  }
}

/** Persist the auto-advance preference. */
export function writeAutoAdvance(enabled: boolean): void {
  try {
    localStorage.setItem(AUTO_ADVANCE_KEY, enabled ? 'true' : 'false');
  } catch {
    /* best-effort */
  }
}

/** True when `level` (e.g. '3d') is a dan level, as opposed to a kyu level (e.g. '15k'). */
export function isDanLevel(level: string): boolean {
  return level.trim().toLowerCase().endsWith('d');
}

/** Chinese label for a level string, e.g. '15k' → '15 级', '3d' → '3 段'. */
export function levelChinese(level: string): string {
  const n = level.replace(/[^0-9]/g, '');
  return isDanLevel(level) ? `${n} 段` : `${n} 级`;
}

/**
 * localStorage key for the last difficulty level the user browsed into (hub 上次 highlight).
 * Single string, cheap to store — does NOT reintroduce the deliberately-omitted per-level
 * completion stat (R2 / §3.5): it's just a pointer, not progress data.
 */
export const LAST_LEVEL_KEY = 'kiosk_tsumego_last_level';

/** Read the last-practiced level, or null if never set / unavailable. */
export function readLastLevel(): string | null {
  try {
    return localStorage.getItem(LAST_LEVEL_KEY);
  } catch {
    return null;
  }
}

/** Persist the last-practiced level. */
export function writeLastLevel(level: string): void {
  try {
    localStorage.setItem(LAST_LEVEL_KEY, level);
  } catch {
    /* best-effort */
  }
}

/**
 * localStorage key for the "use physical board" preference (Phase B / Phase D).
 * Default is OFF (false) — opt-in for physical mode.
 */
export const PHYSICAL_MODE_KEY = 'kiosk_tsumego_physical';

/** Read the "use physical board" preference. Defaults to FALSE (opt-in, T1). */
export function readPhysicalMode(): boolean {
  try {
    return localStorage.getItem(PHYSICAL_MODE_KEY) === 'true';
  } catch {
    return false;
  }
}

/** Persist the "use physical board" preference. */
export function writePhysicalMode(v: boolean): void {
  try {
    localStorage.setItem(PHYSICAL_MODE_KEY, v ? 'true' : 'false');
  } catch {
    /* best-effort */
  }
}

/**
 * localStorage key for the last category the user practised in (训练营 hub 的 `is-current`).
 * Same shape and same rationale as {@link LAST_LEVEL_KEY}: **a pointer, not progress** —
 * it says "这是你上次做的那一类", never "你做完了多少". The hub cannot compute per-category
 * completion without pulling every problem id for the level (R2 / §3.5), and it doesn't try.
 */
export const LAST_CATEGORY_KEY = 'kiosk_tsumego_last_category';

/** Read the last-practised category key (e.g. 'capturing'), or null if never set. */
export function readLastCategory(): string | null {
  try {
    return localStorage.getItem(LAST_CATEGORY_KEY);
  } catch {
    return null;
  }
}

/** Persist the last-practised category key. */
export function writeLastCategory(category: string): void {
  try {
    localStorage.setItem(LAST_CATEGORY_KEY, category);
  } catch {
    /* best-effort */
  }
}

/**
 * 题库自带的六个标签(`life-death / tesuji / semeai / capturing / endgame / opening`),
 * 从每道题的 SGF 注释里解析出来 —— **不是界面自己分的**。所以这张表只负责给它们配
 * 中文名、图标和一句话说明,**有哪几类由 `/levels` 说了算**:表里有、题库里没有的不画,
 * 题库里有、表里没有的照画(标题退回原始 key,副标写题量)。
 * 中文名与 cn PO 的 `tsumego:*` msgstr 一致,拿来当 `t()` 的兜底,翻译表没到位时也读得通。
 */
export const CATEGORY_META: Record<string, { zh: string; sub: string; icon: IconName }> = {
  'life-death': { zh: '死活', sub: '做活 / 杀棋', icon: 'puzzle-piece' },
  tesuji: { zh: '手筋', sub: '局部那一手妙手', icon: 'hand-pointing' },
  semeai: { zh: '对杀', sub: '两块棋比气', icon: 'users' },
  capturing: { zh: '吃子', sub: '怎么把子吃下来', icon: 'grid-nine' },
  endgame: { zh: '官子', sub: '收官那几目', icon: 'squares-four' },
  opening: { zh: '布局', sub: '开局怎么占', icon: 'crown-simple' },
};

const CATEGORY_ORDER = Object.keys(CATEGORY_META);

/** 表里的排前面(照稿子那六张的顺序),表外的按 key 排在后面 —— 不让未知分类插队。 */
export const categoryRank = (key: string) => {
  const i = CATEGORY_ORDER.indexOf(key);
  return i < 0 ? CATEGORY_ORDER.length : i;
};
