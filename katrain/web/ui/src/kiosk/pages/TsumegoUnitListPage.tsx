import { useState, useEffect, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useTranslation } from '../../hooks/useTranslation';
import { useTsumegoProgress } from '../../context/TsumegoProgressContext';
import {
  CATEGORY_META,
  UNIT_SIZE,
  levelChinese,
  readSequence,
  writeLastCategory,
  writeSequence,
} from './tsumegoUnits';
import { interpolate } from '../utils/interpolate';
import { KioskPagebar } from '../shell/KioskPagebar';
import { KioskScrollZone } from '../shell/KioskScrollZone';
import { KioskSecLabel } from '../shell/KioskSecLabel';

interface ProblemSummary {
  id: string;
}

/**
 * 屏 13 · 题目列表 `/kiosk/tsumego/:level/:category/:unit` —— **L2 布局 B**。
 * 稿子 `data-screen="problems"`,参考图 `shots/13-problems.png`。
 *
 * ⚠️ **原来的稿子少画了这一层**(2026-08-21 才补上):单元卡本来直接跳到做题屏,
 * 而真前端里中间隔着这一屏 —— 先看见这 20 道题各是什么状态,再挑一道进去。
 * 少一层的后果不是少一屏,是**「做到第几题了」这件事无处安放**。
 *
 * 三块:数据条 3 格 → 这 20 道题(`.qgrid`) → 换一批(`.kiosk-rows`)。
 *
 * ── 一次接口都不取(常路)────────────────────────────────────────────────
 * 屏 12 为了 prev/next 契约已经把**整类题号按顺序**写进 `sessionStorage` 了,
 * 这一层要的东西(本单元那 20 个题号、整类的错题数)全在里面 ⇒ 直接读,不再请求。
 * 只有**深链**进来(没经过屏 12)才自己取一次 `?limit=1000` 并回填那条顺序表。
 * 旧实现取的是 `?offset&limit=20` 的**整题**(带 `initialBlack/initialWhite` 画缩略棋盘),
 * 这一版的格子里只有题号和状态,**不需要棋形** —— 630 道题的类目上这是一次实打实的省。
 *
 * ── 「N 次」是怎么算出来的:**`attempts` 数的是失败的那几次** ─────────────────
 * `useTsumegoProblem` 里 `setAttempts(prev => prev + 1)` 只在**走错**和**重摆**时发生
 * (`:418` / `:440` / `:618`),做对那一手不加。所以一道**第一次就做对**的题,
 * 存下来的 `attempts` 是 **0**,不是 1。
 * ⇒ 「试了几次」= `attempts + (做对了 ? 1 : 0)`:最后那次成了的话要把它算进去。
 * **这一步不做的话,屏上「1 次」的意思会从「试了一次就对了」变成「错了一次」** ——
 * 数还是那个数,标签把它讲成了另一件事。稿子上那三格 `1 次 / 1 次 / 3 次` 是按前一种意思画的。
 * 没做过的写「—」,**不写「0 次」**:0 次是一个次数,「没做过」不是。
 *
 * ── 和稿子的三处出入(都往「少写小字」那边)────────────────────────────────
 * 1. 两条组标题右端的 `.secval` 去掉了(稿子上是「点一格直接进那一道」/「同一副骨架,
 *    只换题从哪儿来」)。`KioskSecLabel` 自己写着那一格**是数据不是旁注**,
 *    而这两句一句是操作说明、一句是在讲界面构造;Fan 2026-08-22:「不要写那么多解释文字」。
 * 2. 数据条第二、三格的标签去掉了「· 当前单元」——**这一屏本来就只有一个单元**,
 *    页控条已经写着是第几个。屏 12 那边留着「· 当前」是因为那一屏同时摆着十几个单元。
 * 3. 「只做错过的」那句写成「把**这一类**做错的重来一遍」:它上面一行是**整级**,
 *    scope 在这两行之间会跳,不点名的话「现在有 N 道」会被读成整级的数。
 */
const TsumegoUnitListPage = () => {
  const { level, category, unit } = useParams<{ level: string; category: string; unit: string }>();
  const navigate = useNavigate();
  const { t } = useTranslation();
  const { progress } = useTsumegoProgress();

  const [allIds, setAllIds] = useState<string[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  const unitNumber = Math.max(1, Number.parseInt(unit || '1', 10) || 1);
  const offset = (unitNumber - 1) * UNIT_SIZE;

  const load = useCallback((lvl: string, cat: string, signal: AbortSignal) => {
    setError(null);
    // 屏 12 刚写过这条顺序表 —— 常路到此为止,一次接口都不取。
    const cached = readSequence(lvl, cat);
    if (cached && cached.length > 0) {
      setAllIds(cached);
      return;
    }
    setAllIds(null);
    fetch(`/api/v1/tsumego/levels/${lvl}/categories/${cat}?limit=1000`, { signal })
      .then((res) => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return res.json();
      })
      .then((data: ProblemSummary[]) => {
        const ids = Array.isArray(data) ? data.map((p) => p.id) : [];
        setAllIds(ids);
        writeSequence(lvl, cat, ids);
      })
      .catch((err: Error) => {
        if (err.name !== 'AbortError') setError(err.message);
      });
  }, []);

  useEffect(() => {
    if (!level || !category) return;
    const controller = new AbortController();
    load(level, category, controller.signal);
    return () => controller.abort();
  }, [level, category, load]);

  // 深链直接进这一层时,训练营那一排的 `is-current` 也要跟上。**指针不是进度。**
  useEffect(() => {
    if (category) writeLastCategory(category);
  }, [category]);

  const meta = category ? CATEGORY_META[category] : undefined;
  const categoryName = category ? t(`tsumego:${category}`, meta?.zh ?? category) : '';
  const levelName = level ? levelChinese(level) : '';
  const backToUnits = () => navigate(`/kiosk/tsumego/${level}/${category}`);

  const unitIds = allIds ? allIds.slice(offset, offset + UNIT_SIZE) : [];

  const pagebar = (
    <KioskPagebar
      testId="problems-pagebar"
      title={`${levelName} · ${categoryName} · ${interpolate(t('tsumego:unit_n', '第 {n} 单元'), { n: unitNumber })}`}
      // 题号范围只在**真有这一单元**时写 —— 读不到 / 越界时写「第 1-20 题」是在断言一件不知道的事。
      sub={
        unitIds.length > 0
          ? `${interpolate(t('tsumego:problemRange', '第 {start}-{end} 题'), {
              start: offset + 1,
              end: offset + unitIds.length,
            })} · ${t('Judged on placement', '落子即判')}`
          : undefined
      }
      backLabel={t('Units', '单元')}
      onBack={backToUnits}
    />
  );

  if (allIds === null || error || unitIds.length === 0) {
    return (
      <div className="kiosk-layout-b">
        {pagebar}
        <KioskScrollZone>
          {error ? (
            <div className="empty" data-testid="problems-error">
              <h4>{t('Problem set unavailable', '题库读不到')}</h4>
              <p>{error}</p>
              <button
                type="button"
                className="kiosk-btn kiosk-btn--pill pill"
                onClick={() => {
                  if (level && category) load(level, category, new AbortController().signal);
                }}
              >
                {t('Retry', '重试')}
              </button>
            </div>
          ) : allIds === null ? (
            <div className="empty" data-testid="problems-loading">
              <h4>{t('Loading problem set…', '正在读题库…')}</h4>
            </div>
          ) : allIds.length === 0 ? (
            <div className="empty" data-testid="problems-empty">
              <h4>{t('No problems in this category yet', '这一类下面还没有题')}</h4>
              <p>{t('The problem set syncs down from the cloud.', '题库随云端同步下来，同步过来才有题可做。')}</p>
            </div>
          ) : (
            // 单元号越界(手打的地址 / 题库缩了)。**说清楚一共有几个单元**,别只说「没有」。
            <div className="empty" data-testid="problems-out-of-range">
              <h4>{t('No such unit', '没有这一单元')}</h4>
              <p>
                {interpolate(
                  t('tsumego:unit_range', '这一类一共 {total} 道题，只有 {units} 个单元。'),
                  { total: allIds.length, units: Math.ceil(allIds.length / UNIT_SIZE) },
                )}
              </p>
              <button type="button" className="kiosk-btn kiosk-btn--pill pill" onClick={backToUnits}>
                {t('Units', '单元')}
              </button>
            </div>
          )}
        </KioskScrollZone>
      </div>
    );
  }

  // 「试了几次」—— 见文件头:`attempts` 数的是**失败**的那几次,做对的那一次要自己加回来。
  const triesOf = (id: string) => {
    const e = progress[id];
    if (!e) return 0;
    return (e.attempts ?? 0) + (e.completed ? 1 : 0);
  };

  const solved = unitIds.filter((id) => progress[id]?.completed).length;
  // 「下一道要做的」= 本单元第一个还没做对的。全做完了就没有 —— 那就一格 `now` 都不画。
  const nowId = unitIds.find((id) => !progress[id]?.completed) ?? null;

  const triedList = unitIds.map(triesOf).filter((n) => n > 0);
  const avgTries = triedList.length > 0 ? triedList.reduce((a, b) => a + b, 0) / triedList.length : null;

  const durations = unitIds
    .map((id) => progress[id]?.lastDuration)
    .filter((v): v is number => typeof v === 'number' && v > 0);
  const avgSeconds =
    durations.length > 0 ? Math.round(durations.reduce((a, b) => a + b, 0) / durations.length) : null;

  // 做错过的 = 试过、但还没做对。整类的数(和屏 12 同一个口径),不是本单元的。
  const wrongCount = (allIds ?? []).filter(
    (id) => (progress[id]?.attempts ?? 0) > 0 && !progress[id]?.completed,
  ).length;

  return (
    <div className="kiosk-layout-b">
      {pagebar}
      <KioskScrollZone resetKey={`${level}/${category}/${unitNumber}`}>
        <div className="kiosk-stats">
          <div className="kiosk-stat">
            <div className="kiosk-stat__v">
              {solved}<small> / {unitIds.length}</small>
            </div>
            <div className="kiosk-stat__k">{t('Solved in this unit', '本单元已做对')}</div>
          </div>
          <div className="kiosk-stat">
            {/* 一道都没试过时写「—」:平均值没有被测对象,写 `0.0` 是在断言「平均试了 0 次」。 */}
            <div className="kiosk-stat__v" data-testid="stat-avg-tries">
              {avgTries == null ? '—' : avgTries.toFixed(1)}
            </div>
            <div className="kiosk-stat__k">{t('Average tries', '平均尝试次数')}</div>
          </div>
          <div className="kiosk-stat">
            <div className="kiosk-stat__v" data-testid="stat-avg-time">
              {avgSeconds == null ? (
                '—'
              ) : avgSeconds < 60 ? (
                <>{avgSeconds}<small> {t('sec', '秒')}</small></>
              ) : (
                <>
                  {Math.floor(avgSeconds / 60)}<small> {t('min', '分')} </small>
                  {avgSeconds % 60}<small> {t('sec', '秒')}</small>
                </>
              )}
            </div>
            <div className="kiosk-stat__k">{t('Average time', '平均用时')}</div>
          </div>
        </div>

        <section className="kiosk-section">
          <KioskSecLabel
            zh={interpolate(t('tsumego:these_n_problems', '这 {n} 道题'), { n: unitIds.length })}
            en="Problems"
          />
          <div className="qgrid" data-testid="problems-grid">
            {unitIds.map((id, i) => {
              const done = !!progress[id]?.completed;
              const isNow = !done && id === nowId;
              const tries = triesOf(id);
              const triesText = interpolate(t('tsumego:tries_n', '{n} 次'), { n: tries });
              const state = done
                ? t('Solved', '做对了')
                : isNow
                  ? t('Next up', '下一道')
                  : t('Not attempted', '还没做过');
              const problemNo = interpolate(t('tsumego:problem_no', '第 {n} 题'), { n: offset + i + 1 });
              return (
                <button
                  type="button"
                  key={id}
                  className={done ? 'ok' : isNow ? 'now' : undefined}
                  aria-current={isNow ? 'step' : undefined}
                  aria-label={tries > 0 ? `${problemNo}，${state}，${triesText}` : `${problemNo}，${state}`}
                  onClick={() => navigate(`/kiosk/tsumego/problem/${id}`)}
                >
                  <b>{offset + i + 1}</b>
                  {/* 试过就写试了几次;一次没试过的那一格,只有「下一道」那张有话可说。 */}
                  <em>{tries > 0 ? triesText : isNow ? t('You are here', '在这儿') : '—'}</em>
                </button>
              );
            })}
          </div>
        </section>

        <section className="kiosk-section">
          <KioskSecLabel zh={t('Other sets', '换一批')} en="Other sets" />
          <div className="kiosk-rows">
            <div className="kiosk-row">
              <span className="kiosk-row__lead">{t('Whole level', '整级')}</span>
              <div className="kiosk-row__t">
                <b>{`${levelName}${t('all', '全部')}`}</b>
                <em>{t('All six categories mixed — practise telling them apart', '六类混在一起，练「认出这是哪一类」')}</em>
              </div>
              <div className="kiosk-row__end">
                <button
                  type="button"
                  className="kiosk-btn kiosk-btn--pill"
                  onClick={() => navigate(`/kiosk/tsumego/${level}/all`)}
                >
                  {t('Start', '开始')}
                </button>
              </div>
            </div>
            <div className="kiosk-row" data-testid="row-wrong">
              <span className="kiosk-row__lead">{t('Wrong', '错题')}</span>
              <div className="kiosk-row__t">
                <b>{t('Only the ones I got wrong', '只做错过的')}</b>
                {/* 数是真的,去处还没有(后端没有按错题筛的接口,做题屏的上/下一题也只认整类那条顺序表)。
                    ⇒ 不摆一个按不动的「开始」冒充有路可走:§14 那个琥珀标就是用来说这件事的。 */}
                <em>
                  {t('Redo the ones you got wrong in this category', '把这一类做错的重来一遍')}
                  {' · '}
                  {interpolate(t('tsumego:wrong_now', '现在有 {n} 道'), { n: wrongCount })}
                </em>
              </div>
              <div className="kiosk-row__end">
                <span className="kiosk-wip">{t('Not wired up yet', '还没接')}</span>
              </div>
            </div>
          </div>
        </section>
      </KioskScrollZone>
    </div>
  );
};

export default TsumegoUnitListPage;
