import type { IconName } from '../shell/icons';
import { getCurrentKioskActivityStorage } from '../storage/kioskActivityStorage';

/**
 * Tsumego unit-grouping constants + the Phase 4 prev/next sequence contract.
 * Kept in a non-component module so the unit pages stay react-refresh clean.
 */

/** Problems per unit (matches galaxy D5). */
export const UNIT_SIZE = 20;

interface ProblemSummary {
  id: string;
}

interface ProblemPage {
  items: ProblemSummary[];
  total: number;
  page: number;
  page_size: number;
}

/**
 * Read one ordered practice sequence. Normal categories use their compact list
 * endpoint. `all` uses the paged whole-level endpoint and joins every page in
 * server order so it can follow the same 20-problem unit flow.
 */
export async function fetchTsumegoSequence(
  level: string,
  category: string,
  signal: AbortSignal,
): Promise<string[]> {
  if (category !== 'all') {
    const res = await fetch(`/api/v1/tsumego/levels/${level}/categories/${category}?limit=1000`, { signal });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json() as ProblemSummary[];
    return Array.isArray(data) ? data.map((problem) => problem.id) : [];
  }

  const pageSize = 200;
  const ids: string[] = [];
  let page = 1;
  let total = Number.POSITIVE_INFINITY;

  while (ids.length < total) {
    const res = await fetch(`/api/v1/tsumego/levels/${level}/problems?page=${page}&page_size=${pageSize}`, { signal });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json() as ProblemPage;
    const items = Array.isArray(data.items) ? data.items : [];
    total = Number.isFinite(data.total) ? Math.max(0, data.total) : ids.length + items.length;
    ids.push(...items.map((problem) => problem.id));
    if (items.length === 0 || items.length < pageSize) break;
    page += 1;
  }

  return ids.slice(0, total);
}

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
 * Identity-scoped key for the "auto-advance to next problem after solving" preference (D4).
 * Guest and unresolved identities use the in-memory kiosk activity store.
 */
export const AUTO_ADVANCE_KEY = 'kiosk_tsumego_autoadvance';

/** Read the auto-advance preference. Defaults to true when unset / unparseable. */
export function readAutoAdvance(): boolean {
  try {
    const v = getCurrentKioskActivityStorage().getItem(AUTO_ADVANCE_KEY);
    if (v === null) return true; // default ON
    return v === 'true';
  } catch {
    return true;
  }
}

/** Persist the auto-advance preference. */
export function writeAutoAdvance(enabled: boolean): void {
  try {
    getCurrentKioskActivityStorage().setItem(AUTO_ADVANCE_KEY, enabled ? 'true' : 'false');
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
 * 训练营的三样「上次」—— 上次那一档、上次那一类、接着上次 —— 走统一的
 * `kioskActivityStorage`:真实账号按 UUID 隔离，访客和身份未解析阶段只写内存。
 *
 * 实体开关 `kiosk_tsumego_physical` **不在这里,仍按盒存** —— 它说的是这台盒子那块盘接好没有,
 * 和谁登录无关。
 *
 * 这三样是**指针不是进度**(R2 / §3.5):不重新引入「每一档做完了多少」那个刻意没做的数。
 */
function readScoped(base: string): string | null {
  try {
    return getCurrentKioskActivityStorage().getItem(base);
  } catch {
    return null;
  }
}

function writeScoped(base: string, value: string): void {
  try {
    getCurrentKioskActivityStorage().setItem(base, value);
  } catch {
    /* best-effort */
  }
}

export const LAST_LEVEL_KEY = 'kiosk_tsumego_last_level';

/** 这个账号上次进的那一档,没有就 `null`。 */
export function readLastLevel(): string | null {
  return readScoped(LAST_LEVEL_KEY);
}

export function writeLastLevel(level: string): void {
  writeScoped(LAST_LEVEL_KEY, level);
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

export function readLastCategory(): string | null {
  return readScoped(LAST_CATEGORY_KEY);
}

export function writeLastCategory(category: string): void {
  writeScoped(LAST_CATEGORY_KEY, category);
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

export function readPracticeResume(): PracticeResume | null {
  const raw = readScoped(RESUME_KEY);
  if (!raw) return null;
  try {
    const p = JSON.parse(raw) as Partial<PracticeResume> | null;
    return p && typeof p.label === 'string' && typeof p.route === 'string' ? { label: p.label, route: p.route } : null;
  } catch {
    return null;
  }
}

export function writePracticeResume(resume: PracticeResume): void {
  writeScoped(RESUME_KEY, JSON.stringify({ label: resume.label, route: resume.route }));
}

/**
 * 「只做错过的」那份题单的**快照**(T1)。点错题页格子的**那一刻**写:
 * 做题途中做对一道,它不会从上/下一题的序列里消失;回到错题页时再按最新进度重算。
 * 形状和整类那条顺序表一样(`string[]`,整类顺序),钥匙多一个 `_wrong`。
 *
 * ⚠️ **按账号存**(和上面三样「上次」同一个 activity store)。整类顺序表不分人没问题 —— 那是题库的事实;
 * 错题快照是**这个人**做错了哪几道。盒端换人只导航、不重启 Chromium ⇒ 不分人的话,同一个标签页里甲→乙→甲:
 * 甲存下的「接着上次 · …?set=wrong」会读到乙写的快照,只要这道题两人都错过就过得了 `includes`,
 * 甲从此在乙的错题里翻页。
 */
export const wrongSequenceKey = (level: string, category: string): string =>
  `${sequenceKey(level, category)}_wrong`;

/** 读快照。读不到 / 没有账号返回 `null` —— 做题屏据此退回整类行为,不假装还在错题里。 */
export function readWrongSequence(level: string, category: string): string[] | null {
  const key = wrongSequenceKey(level, category);
  try {
    const raw = getCurrentKioskActivityStorage().getItem(key);
    if (raw === null) return null;
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed.filter((x): x is string => typeof x === 'string') : null;
  } catch {
    return null;
  }
}

export function writeWrongSequence(level: string, category: string, ids: string[]): void {
  const key = wrongSequenceKey(level, category);
  try {
    getCurrentKioskActivityStorage().setItem(key, JSON.stringify(ids));
  } catch {
    /* best-effort */
  }
}

/** 「做错过的」= 试过、还没做对。屏 12 的卡、屏 13 的行、错题页三处**同一个口径**,只许在这里写一次。 */
export const isWrongEntry = (entry: { attempts?: number; completed?: boolean } | undefined): boolean =>
  (entry?.attempts ?? 0) > 0 && !entry?.completed;

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
 *
 * `opts.retry`(默认 `true`)—— 有的屏(如做题屏)没有重试键(§ 见做题屏 error 块,
 * `useTsumegoProblem` 不出 reload,不在这个共用 hook 上加),503 那句话就不能叫人「点重试」。
 * 传 `{ retry: false }` 换一句不提「重试」的收尾;标题和非 503 的分支不变。
 */
export function loadErrorCopy(
  t: (key: string, defaultText?: string) => string,
  error: string,
  opts?: { retry?: boolean },
): { title: string; body: string } {
  const retry = opts?.retry ?? true;
  return isCloudUnreachable(error)
    ? {
        title: t('tsumego:cloudUnreachable', '连不上云端题库'),
        body: retry
          ? t('tsumego:cloudUnreachableBody', '题库在云端，盒子上不存题。等网络或云端恢复后再点重试。')
          : t('tsumego:cloudUnreachableBodyNoRetry', '题库在云端，盒子上不存题。等网络或云端恢复后，返回再进来。'),
      }
    : { title: t('Problem set unavailable', '题库读不到'), body: error };
}
