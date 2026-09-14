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
 * 训练营的三样「上次」—— 上次那一档、上次那一类、接着上次 —— **按账号存**(N10)。
 * 盒子是共用设备:不分人的话,乙登录会看到甲的「接着上次 · 15 级 · 吃子 · 第 3 题」。
 * 钥匙照做题进度那把的命名(`TsumegoProgressContext` 的 `tsumego_progress:u<id>`)。
 * 2026-09-14 之前那几把不分人的旧钥匙**不迁移、不再读**:它们没有主人。
 *
 * 实体开关 `kiosk_tsumego_physical` **不在这里,仍按盒存** —— 它说的是这台盒子那块盘接好没有,
 * 和谁登录无关。
 *
 * 这三样是**指针不是进度**(R2 / §3.5):不重新引入「每一档做完了多少」那个刻意没做的数。
 */
export type TsumegoUserId = number | string | null | undefined;

const scopedKey = (base: string, userId: TsumegoUserId): string | null =>
  userId === null || userId === undefined ? null : `${base}:u${userId}`;

function readScoped(base: string, userId: TsumegoUserId): string | null {
  const key = scopedKey(base, userId);
  if (!key) return null;
  try {
    return localStorage.getItem(key);
  } catch {
    return null;
  }
}

function writeScoped(base: string, userId: TsumegoUserId, value: string): void {
  const key = scopedKey(base, userId);
  if (!key) return;
  try {
    localStorage.setItem(key, value);
  } catch {
    /* best-effort */
  }
}

export const LAST_LEVEL_KEY = 'kiosk_tsumego_last_level';

/** 这个账号上次进的那一档,没有就 `null`。 */
export function readLastLevel(userId: TsumegoUserId): string | null {
  return readScoped(LAST_LEVEL_KEY, userId);
}

export function writeLastLevel(userId: TsumegoUserId, level: string): void {
  writeScoped(LAST_LEVEL_KEY, userId, level);
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
 * 这个账号上次做的那一类(训练营「按分类」那一排的 `is-current`)。和上次那一档同一种东西:
 * **指针不是进度**,也按账号存 —— 见 `LAST_LEVEL_KEY` 上面那段。
 */
export const LAST_CATEGORY_KEY = 'kiosk_tsumego_last_category';

export function readLastCategory(userId: TsumegoUserId): string | null {
  return readScoped(LAST_CATEGORY_KEY, userId);
}

export function writeLastCategory(userId: TsumegoUserId, category: string): void {
  writeScoped(LAST_CATEGORY_KEY, userId, category);
}

/**
 * 训练营「接着上次」那一条。原来借 `utils/activeSession.ts` 的 `practice` 槽存,那把钥匙不分人;
 * 挪到这里按账号存。`activeSession.ts` 本身不动(对弈也用它),`practice` 槽从此没有消费者 —— 已登记。
 */
export const RESUME_KEY = 'kiosk_tsumego_resume';

export interface PracticeResume {
  /** 屏上那一行,如「15 级 · 吃子 · 第 3 题」。 */
  label: string;
  /** 点「继续」去哪儿,如 `/kiosk/tsumego/problem/1014`(错题模式带 `?set=wrong`)。 */
  route: string;
}

export function readPracticeResume(userId: TsumegoUserId): PracticeResume | null {
  const raw = readScoped(RESUME_KEY, userId);
  if (!raw) return null;
  try {
    const p = JSON.parse(raw) as Partial<PracticeResume> | null;
    return p && typeof p.label === 'string' && typeof p.route === 'string' ? { label: p.label, route: p.route } : null;
  } catch {
    return null;
  }
}

export function writePracticeResume(userId: TsumegoUserId, resume: PracticeResume): void {
  writeScoped(RESUME_KEY, userId, JSON.stringify({ label: resume.label, route: resume.route }));
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

/**
 * 盒上题库读取为什么失败(N9)。盒上题库是**在线直读**的(`core/repository.py` 的 `tsumego_*`
 * 走 `_remote_only`):盒子上不存题,也没有任何同步。连不上云端 / 云端 5xx ⇒ 后端回 503。
 * 各页 fetch 失败时抛的都是 `HTTP <status>`,所以判别就是这一个字面量。
 */
export const isCloudUnreachable = (error: string | null | undefined): boolean => error === 'HTTP 503';

/**
 * 错误块的两行字。503 说「连不上」并说清题在哪;其它错误照旧「读不到」+ 原因,
 * **不许把所有错误都说成没网** —— 404 / 500 各有各的原因。
 */
export function loadErrorCopy(
  t: (key: string, defaultText?: string) => string,
  error: string,
): { title: string; body: string } {
  return isCloudUnreachable(error)
    ? {
        title: t('tsumego:cloudUnreachable', '连不上云端题库'),
        body: t('tsumego:cloudUnreachableBody', '题库在云端，盒子上不存题。等网络或云端恢复后再点重试。'),
      }
    : { title: t('Problem set unavailable', '题库读不到'), body: error };
}
