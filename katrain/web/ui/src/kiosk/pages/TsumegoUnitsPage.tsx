import { useState, useEffect, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useTranslation } from '../../hooks/useTranslation';
import { useTsumegoProgress } from '../../context/TsumegoProgressContext';
import { CATEGORY_META, UNIT_SIZE, levelChinese, readAutoAdvance, writeLastCategory, writeSequence } from './tsumegoUnits';
import { interpolate } from '../utils/interpolate';
import { KioskPagebar } from '../shell/KioskPagebar';
import { KioskScrollZone } from '../shell/KioskScrollZone';
import { KioskSecLabel } from '../shell/KioskSecLabel';
import { KioskCard } from '../shell/KioskCard';

interface ProblemSummary {
  id: string;
}

/**
 * 屏 12 · 单元列表 `/kiosk/tsumego/:level/:category` —— **L2 布局 B**(无棋盘 ⇒ 页控条通栏 x16,
 * 下面是通栏 992×460 的滚动区,没有 Dock)。稿子 `data-screen="units"`,参考图 `shots/12-units.png`。
 *
 * ⚠️ **屏号是 12 不是 04**(计划书那个号是十屏时代的)。
 *
 * 四块:数据条 3 格 → 开始条 → 单元(进度环卡) → 整级一起做。
 *
 * ── 这一屏和训练营(屏 11)的**关键差别**:环里写的是真 `0%`,不是「—」──────────
 * 做题进度**真存下来**:做对没有、试了几次、上次用了多久,都在 `/api/v1/tsumego/progress`,
 * 换台盒子登录也还在(`TsumegoProgressContext` 本地 + 服务端逐字段合并)。
 * 而这一层已经把这一类的**全部题号**取回来了(prev/next 契约本来就要),所以每个单元做完几道
 * 是**算得出来的**。⇒ `0%` = 「真的一道没做」,不是「读不到」。
 * **屏 11 那边写「—」是因为那一层算不到这个数,两屏的差别不许抹平。**
 *
 * ── 「只做错过的」为什么是灰的 ────────────────────────────────────────
 * 「做错过的」这个集合**算得出来**(本地进度里 `attempts > 0 && !completed`),但**没有地方去**:
 * 后端没有按错题筛的接口,前端也没有一条能只播这批题的路由 —— 做题屏的上/下一题读的是
 * `sessionStorage` 里那条**整类**的顺序表(`sequenceKey`),塞一份筛过的进去会把正常的上下一题弄坏。
 * ⇒ 卡照画(§14:后端没有的块要标出来,不是藏起来),标成「还没接」,
 * **但副标里写真数**——「现在有 N 道」是这一层真的知道的事。
 */
const TsumegoUnitsPage = () => {
  const { level, category } = useParams<{ level: string; category: string }>();
  const navigate = useNavigate();
  const { t } = useTranslation();
  const { unitProgress, progress } = useTsumegoProgress();

  const [problemIds, setProblemIds] = useState<string[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  const loadUnits = useCallback((lvl: string, cat: string, signal: AbortSignal) => {
    setProblemIds(null);
    setError(null);
    fetch(`/api/v1/tsumego/levels/${lvl}/categories/${cat}?limit=1000`, { signal })
      .then((res) => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return res.json();
      })
      .then((data: ProblemSummary[]) => {
        const ids = Array.isArray(data) ? data.map((p) => p.id) : [];
        setProblemIds(ids);
        // Phase 4 契约:把**按顺序**的整类题号存下来 —— 做题屏靠它算上/下一题,
        // 屏 13(题目列表)靠它连一次接口都不用取。
        writeSequence(lvl, cat, ids);
      })
      .catch((err: Error) => {
        if (err.name !== 'AbortError') setError(err.message);
      });
  }, []);

  useEffect(() => {
    if (!level || !category) return;
    const controller = new AbortController();
    loadUnits(level, category, controller.signal);
    return () => controller.abort();
  }, [level, category, loadUnits]);

  // 进了这一类就记下来 —— 训练营那一排的 `is-current` 靠它。**指针不是进度。**
  useEffect(() => {
    if (category) writeLastCategory(category);
  }, [category]);

  const meta = category ? CATEGORY_META[category] : undefined;
  const categoryName = category ? t(`tsumego:${category}`, meta?.zh ?? category) : '';
  const levelName = level ? levelChinese(level) : '';
  const backToLevel = () => navigate(`/kiosk/tsumego/${level}`);

  const pagebar = (
    <KioskPagebar
      testId="units-pagebar"
      title={`${levelName} · ${categoryName}`}
      sub={t('Judged on placement · a wrong move is taken straight back', '落子即判 · 走错当场退回')}
      backLabel={t('Training', '训练营')}
      onBack={backToLevel}
    />
  );

  if (problemIds === null || error || problemIds.length === 0) {
    return (
      <div className="kiosk-layout-b">
        {pagebar}
        <KioskScrollZone>
          {error ? (
            <div className="empty" data-testid="units-error">
              <h4>{t('Problem set unavailable', '题库读不到')}</h4>
              <p>{error}</p>
              <button
                type="button"
                className="kiosk-btn kiosk-btn--pill pill"
                onClick={() => {
                  if (level && category) loadUnits(level, category, new AbortController().signal);
                }}
              >
                {t('Retry', '重试')}
              </button>
            </div>
          ) : problemIds === null ? (
            <div className="empty" data-testid="units-loading">
              <h4>{t('Loading problem set…', '正在读题库…')}</h4>
            </div>
          ) : (
            <div className="empty" data-testid="units-empty">
              <h4>{t('No problems in this category yet', '这一类下面还没有题')}</h4>
              <p>{t('The problem set syncs down from the cloud.', '题库随云端同步下来，同步过来才有题可做。')}</p>
            </div>
          )}
        </KioskScrollZone>
      </div>
    );
  }

  const total = problemIds.length;
  const units = Array.from({ length: Math.ceil(total / UNIT_SIZE) }, (_, i) => {
    const start = i * UNIT_SIZE;
    const end = Math.min(start + UNIT_SIZE, total);
    const ids = problemIds.slice(start, end);
    const { completed } = unitProgress(ids);
    return { n: i + 1, start, end, ids, completed, size: end - start };
  });

  // 「当前单元」= 第一个没做完的;全做完了就指最后一个(**不许指向一个不存在的单元**)。
  const current = units.find((u) => u.completed < u.size) ?? units[units.length - 1];
  const firstUnsolved = current.ids.findIndex((id) => !progress[id]?.completed);
  const resumeIndex = firstUnsolved < 0 ? 0 : firstUnsolved;

  // 做错过的 = 试过、但还没做对。这个数算得出来,去处没有 —— 见文件头。
  const wrongCount = problemIds.filter((id) => (progress[id]?.attempts ?? 0) > 0 && !progress[id]?.completed).length;

  return (
    <div className="kiosk-layout-b">
      {pagebar}
      <KioskScrollZone resetKey={`${level}/${category}`}>
        <div className="kiosk-stats">
          <div className="kiosk-stat">
            <div className="kiosk-stat__v">{UNIT_SIZE}</div>
            <div className="kiosk-stat__k">{t('Problems per unit · current', '每单元题数 · 当前')}</div>
          </div>
          <div className="kiosk-stat">
            {/* 值自带分母时**不必再在标签里写口径** —— 分母本身就是口径。 */}
            <div className="kiosk-stat__v">
              {current.completed}<small> / {current.size}</small>
            </div>
            <div className="kiosk-stat__k">{t('Solved in this unit', '本单元已做对')}</div>
          </div>
          <div className="kiosk-stat">
            <div className="kiosk-stat__v">{readAutoAdvance() ? t('On', '开') : t('Off', '关')}</div>
            <div className="kiosk-stat__k">{t('Auto-advance after solving · current', '做对后自动下一题 · 当前')}</div>
          </div>
        </div>

        <div className="kiosk-resume" data-testid="units-start">
          <span className="bar" />
          <div>
            <h4>{t('Start', '开始')} · {interpolate(t('tsumego:unit_n', '第 {n} 单元'), { n: current.n })}</h4>
            <p>{levelName} · {categoryName} · {interpolate(t('tsumego:problem_no', '第 {n} 题'), { n: current.start + resumeIndex + 1 })}</p>
          </div>
          <button
            type="button"
            className="kiosk-btn kiosk-btn--pill pill"
            onClick={() => navigate(`/kiosk/tsumego/${level}/${category}/${current.n}`)}
          >
            {t('Start', '开始')}
          </button>
        </div>

        <section className="kiosk-section">
          <KioskSecLabel
            zh={t('Units', '单元')}
            en="Units"
            value={interpolate(t('tsumego:unit_size', '每 {n} 题一单元'), { n: UNIT_SIZE })}
          />
          <div className="kiosk-cards">
            {units.map((u) => (
              <KioskCard
                key={u.n}
                // 环是**真进度**(见文件头):这里的 0% 是「真的一道没做」。
                ring={(u.completed / u.size) * 100}
                title={interpolate(t('tsumego:unit_n', '第 {n} 单元'), { n: u.n })}
                // `tsumego:problemRange` 是 galaxy 也在用的那一个,照它原来的占位符名 `{start}/{end}`。
                // 渲染出来是「第 1-20 题」(PO 里的写法),稿子上是「第 1 – 20 题」——
                // **两处口径统一比对上稿子的破折号更要紧**,差别登记在四图的标签带里。
                sub={interpolate(t('tsumego:problemRange', '第 {start}-{end} 题'), { start: u.start + 1, end: u.end })}
                current={u.n === current.n}
                onClick={() => navigate(`/kiosk/tsumego/${level}/${category}/${u.n}`)}
              />
            ))}
          </div>
        </section>

        <section className="kiosk-section">
          <KioskSecLabel zh={t('Whole level', '整级一起做')} en={'Whole level'} />
          <div className="kiosk-cards">
            <KioskCard
              title={`${levelName}${t('all', '全部')}`}
              sub={t('All categories mixed, no units', '六类混在一起，不分单元')}
              icon="squares-four"
              onClick={() => navigate(`/kiosk/tsumego/${level}/all`)}
            />
            <KioskCard
              title={t('Only the ones I got wrong', '只做错过的')}
              // 数是真的,去处还没有 —— 两件事都说出来,不含糊成一个灰按钮。
              sub={interpolate(t('tsumego:wrong_now', '现在有 {n} 道'), { n: wrongCount })}
              icon="arrow-clockwise"
              soon={t('Not wired up yet', '还没接')}
            />
          </div>
        </section>
      </KioskScrollZone>
    </div>
  );
};

export default TsumegoUnitsPage;
