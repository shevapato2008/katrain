import { useState, useEffect, useCallback } from 'react';
import { useParams, useNavigate, useLocation } from 'react-router-dom';
import { backToState } from '../hooks/useBackTo';
import type { ProblemDetail } from '../../hooks/useTsumegoProblem';
import { useTranslation } from '../../hooks/useTranslation';
import { useTsumegoProgress } from '../../context/TsumegoProgressContext';
import { sgfToCoords } from '../../utils/sgfParser';
import {
  CATEGORY_META,
  UNIT_SIZE,
  fetchTsumegoSequence,
  isWrongEntry,
  levelChinese,
  loadErrorCopy,
  readSequence,
  writeLastCategory,
  writeSequence,
  writeWrongSequence,
} from './tsumegoUnits';
import { interpolate } from '../utils/interpolate';
import { KioskPagebar } from '../shell/KioskPagebar';
import { KioskScrollZone } from '../shell/KioskScrollZone';
import { KioskSecLabel } from '../shell/KioskSecLabel';
import { GoBoardSvg } from '../shell/GoBoardSvg';
import { GO_COLS, colsFor, rowsFor } from '../shell/goBoard';

const previewCoords = (stones: string[], size: number): string[] => stones.flatMap((stone) => {
  const point = sgfToCoords(stone, size);
  return point ? [`${GO_COLS[point[0]]}${point[1] + 1}`] : [];
});

/**
 * 屏 13 · 题目列表 `/kiosk/tsumego/:level/:category/:unit` —— **L2 布局 A**。
 * 1024×600 已确认设计稿在 `superpowers/tracks/kiosk-ui-redesign/artifacts/13-problems-split-preview.html`。
 *
 * ⚠️ **原来的稿子少画了这一层**(2026-08-21 才补上):单元卡本来直接跳到做题屏,
 * 而真前端里中间隔着这一屏 —— 先看见这 20 道题各是什么状态,再挑一道进去。
 * 少一层的后果不是少一屏,是**「做到第几题了」这件事无处安放**。
 *
 * 左侧是真实题目的初始棋形；右侧是进度、20 题、换一批和进入所选题。
 *
 * ── 题号常路从缓存取，选中题的棋形按需取 ───────────────────────────────
 * 屏 12 为了 prev/next 契约已经把**整类题号按顺序**写进 `sessionStorage` 了,
 * 本单元题号和整类错题数直接从中读取，不重复请求整类题目。
 * 只有**深链**进来(没经过屏 12)才自己取一次 `?limit=1000` 并回填那条顺序表。
 * 只对当前选中的题请求详情，并在本页缓存；切题时旧请求会中止，避免旧棋形盖住新选择。
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
 * ── 旧版无盘题目列表的文案取舍（错题页仍沿用）────────────────────────────
 * 1. 两条组标题右端的 `.secval` 去掉了(稿子上是「点一格直接进那一道」/「同一副骨架,
 *    只换题从哪儿来」)。`KioskSecLabel` 自己写着那一格**是数据不是旁注**,
 *    而这两句一句是操作说明、一句是在讲界面构造;Fan 2026-08-22:「不要写那么多解释文字」。
 * 2. 数据条第二、三格的标签去掉了「· 当前单元」——**这一屏本来就只有一个单元**,
 *    页控条已经写着是第几个。屏 12 那边留着「· 当前」是因为那一屏同时摆着十几个单元。
 * 3. 「只做错过的」那句写成「把**这一类**做错的重来一遍」:它上面一行是**整级**,
 *    scope 在这两行之间会跳,不点名的话「现在有 N 道」会被读成整级的数。
 *
 * ── 错题页(T1,2026-09-14)`set="wrong"` ─────────────────────────────────
 * 路由 `/kiosk/tsumego/:level/:category/wrong`。错题可能超过 20 道，继续沿用可滚动的无盘列表:
 *   · 格子 = 这一类里「试过、还没做对」的全部题(`isWrongEntry`),格上写**整类真题号**;
 *   · 数据条三格换成「现在有几道 / 平均尝试次数 / 这一类已做对」—— 「本单元已做对」恒 0、
 *     「平均用时」对没做对的题恒「—」,两格在这里没话可说;
 *   · 点格那一刻写快照(`writeWrongSequence`,**按账号存**),做题屏靠 `?set=wrong` 只在快照里翻页;
 *   · 「换一批」只留整级那一行 —— 错题那一行指向自己;
 *   · 一道错题都算不出来时分两种说:做题记录没读到(`serverLoadFailed`)⇒「做题记录没读到」+ 重试
 *     (Provider 不会自己重拉);读到了、真没有 ⇒「这一类现在没有做错过的题」。屏 13 那一行同一条。
 * 错题多于 20 道时这一屏**会滚**(屏 13 本来那一支断言的是「满编 20 格不滚」),
 * 能不能滚归 `tests/kiosk-tsumego-wrong.spec.ts` 那条真浏览器闸。
 */
const TsumegoUnitListPage = ({ set = 'unit' }: {
  /** `unit` = 第 N 单元那 20 道(屏 13 本来那一屏);`wrong` = 错题页(见文件头)。 */
  set?: 'unit' | 'wrong';
}) => {
  const { level, category, unit } = useParams<{ level: string; category: string; unit: string }>();
  const navigate = useNavigate();
  const location = useLocation();
  const { t } = useTranslation();
  const { progress, serverLoadFailed, refresh } = useTsumegoProgress();
  const isWrongSet = set === 'wrong';

  const [allIds, setAllIds] = useState<string[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [selectedProblemId, setSelectedProblemId] = useState<string | null>(null);
  const [previewCache, setPreviewCache] = useState<Record<string, ProblemDetail>>({});
  const [previewError, setPreviewError] = useState<{ id: string; message: string } | null>(null);
  const [previewRetry, setPreviewRetry] = useState(0);

  const unitNumber = Math.max(1, Number.parseInt(unit || '1', 10) || 1);
  const offset = (unitNumber - 1) * UNIT_SIZE;

  const load = useCallback((lvl: string, cat: string, signal: AbortSignal) => {
    setError(null);
    // 屏 12 刚写过这条顺序表 —— 题号常路到此为止，不重复取整类列表。
    const cached = readSequence(lvl, cat);
    if (cached && cached.length > 0) {
      setAllIds(cached);
      return;
    }
    setAllIds(null);
    fetchTsumegoSequence(lvl, cat, signal)
      .then((ids) => {
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
    // 读屏 12 写下的题号缓存是同步快路；保留它可避免列表闪回加载态。
    // eslint-disable-next-line react-hooks/set-state-in-effect
    load(level, category, controller.signal);
    return () => controller.abort();
  }, [level, category, load]);

  // 深链直接进这一层时,训练营那一排的 `is-current` 也要跟上。**指针不是进度**,按账号存(N10)。
  useEffect(() => {
    if (category) writeLastCategory(category);
  }, [category]);

  const isAll = category === 'all';
  const meta = category ? CATEGORY_META[category] : undefined;
  const categoryName = isAll
    ? t('Mixed training', '综合训练')
    : category ? t(`tsumego:${category}`, meta?.zh ?? category) : '';
  const levelName = level ? levelChinese(level) : '';
  const backToUnits = () => navigate(`/kiosk/tsumego/${level}/${category}`);

  const unitIds = allIds ? allIds.slice(offset, offset + UNIT_SIZE) : [];
  // 做错过的 = 试过、还没做对,整类口径(和屏 12 的卡同一个数)。错题页的格子就是它。
  const wrongIds = allIds ? allIds.filter((id) => isWrongEntry(progress[id])) : [];
  // 0 道而做题记录没读到 ⇒ 这个 0 是编的:错题页不说「没有」、屏 13 那一行不写「0 道」也不灰。见文件头。
  const wrongUnknown = serverLoadFailed && wrongIds.length === 0;
  const listIds = isWrongSet ? wrongIds : unitIds;
  const defaultProblemId = unitIds.find((id) => !progress[id]?.completed) ?? unitIds[0] ?? null;
  const previewId = !isWrongSet && selectedProblemId && unitIds.includes(selectedProblemId)
    ? selectedProblemId
    : !isWrongSet ? defaultProblemId : null;
  const preview = previewId ? previewCache[previewId] : null;
  const activePreviewError = previewError?.id === previewId ? previewError.message : null;
  const judged = t('Judged on placement', '落子即判');

  useEffect(() => {
    if (!previewId || previewCache[previewId]) return;
    const controller = new AbortController();
    fetch(`/api/v1/tsumego/problems/${previewId}`, { signal: controller.signal })
      .then((res) => {
        if (!res.ok) throw new Error(res.status === 404 ? 'Problem not found' : `HTTP ${res.status}`);
        return res.json() as Promise<ProblemDetail>;
      })
      .then((problem) => {
        if (!controller.signal.aborted && problem.id === previewId) {
          setPreviewCache((current) => ({ ...current, [previewId]: problem }));
        }
      })
      .catch((err: Error) => {
        if (!controller.signal.aborted) setPreviewError({ id: previewId, message: err.message });
      });
    return () => controller.abort();
  }, [previewId, previewCache, previewRetry]);

  const pagebar = (
    <KioskPagebar
      testId="problems-pagebar"
      title={
        isWrongSet
          ? `${levelName} · ${categoryName} · ${t('tsumego:wrongSet', '错题')}`
          : `${levelName} · ${categoryName} · ${interpolate(t('tsumego:unit_n', '第 {n} 单元'), { n: unitNumber })}`
      }
      // 题号范围 / 道数只在**真有**时写 —— 读不到 / 越界 / 0 道时写出来是在断言一件不知道的事。
      sub={
        listIds.length === 0
          ? undefined
          : isWrongSet
            ? `${interpolate(t('tsumego:wrong_now', '现在有 {n} 道'), { n: wrongIds.length })} · ${judged}`
            : `${interpolate(t('tsumego:problemRange', '第 {start}-{end} 题'), {
                start: offset + 1,
                end: offset + unitIds.length,
              })} · ${judged}`
      }
      backLabel={t('Units', '单元')}
      onBack={backToUnits}
    />
  );

  if (allIds === null || error || listIds.length === 0) {
    return (
      <div className="kiosk-layout-b">
        {pagebar}
        <KioskScrollZone>
          {error ? (
            <div className="empty" data-testid="problems-error">
              <h4>{loadErrorCopy(t, error).title}</h4>
              <p>{loadErrorCopy(t, error).body}</p>
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
            </div>
          ) : isWrongSet && wrongUnknown ? (
            // 做题记录没读到 ≠ 没有错题。Provider 读失败后不会自己重拉 ⇒ 这里给重试(`refresh`);
            // 重读途中 `serverLoadFailed` 保持为真(读成功才清),所以按下去不会闪一下「没有做错过的题」。
            // 返回走页控条的「单元」,这里不再摆第二颗键。
            <div className="empty" data-testid="problems-wrong-unknown">
              <h4>{t('tsumego:progressUnread', '做题记录没读到')}</h4>
              <p>{t('tsumego:progressUnreadBody', '读不到做题记录，就说不出这一类错过哪几道。等网络恢复后再点重试。')}</p>
              <button type="button" className="kiosk-btn kiosk-btn--pill pill" onClick={() => refresh()}>
                {t('Retry', '重试')}
              </button>
            </div>
          ) : isWrongSet ? (
            // 这一类里没有「试过、还没做对」的题,而且做题记录读到了(或本来就只有本机那份)。
            // 已知边角:初次读还在路上时这里会先说「没有」—— Provider 没有「在读」标志,读回来会自己重渲;
            // 那一刻入口(屏 12 卡 / 屏 13 行)按「0 道、没失败」是灰的,只有深链会先看到这一句。
            <div className="empty" data-testid="problems-no-wrong">
              <h4>{t('tsumego:noWrong', '这一类现在没有做错过的题')}</h4>
              <button type="button" className="kiosk-btn kiosk-btn--pill pill" onClick={backToUnits}>
                {t('Units', '单元')}
              </button>
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
  const solvedInCategory = allIds.filter((id) => progress[id]?.completed).length;
  // 「下一道要做的」= 本单元第一个还没做对的。全做完了就没有;错题页每一道都没做对,也不指。
  const nowId = isWrongSet ? null : unitIds.find((id) => !progress[id]?.completed) ?? null;

  const triedList = listIds.map(triesOf).filter((n) => n > 0);
  const avgTries = triedList.length > 0 ? triedList.reduce((a, b) => a + b, 0) / triedList.length : null;

  const durations = unitIds
    .map((id) => progress[id]?.lastDuration)
    .filter((v): v is number => typeof v === 'number' && v > 0);
  const avgSeconds =
    durations.length > 0 ? Math.round(durations.reduce((a, b) => a + b, 0) / durations.length) : null;

  const openProblem = (id: string) => {
    if (!isWrongSet) {
      navigate(`/kiosk/tsumego/problem/${id}${isAll ? '?set=all' : ''}`, { state: backToState(location) });
      return;
    }
    // 快照在**点下去那一刻**写:做题途中做对一道,它不会从上/下一题里消失(T1)。按账号存。
    if (level && category) writeWrongSequence(level, category, wrongIds);
    navigate(`/kiosk/tsumego/problem/${id}?set=wrong`, { state: backToState(location) });
  };

  if (!isWrongSet) {
    const selectedIndex = unitIds.indexOf(previewId ?? '');
    const selectedNumber = offset + selectedIndex + 1;
    const selectedNumberText = String(selectedNumber).padStart(2, '0');
    const boardSize = preview?.boardSize || 19;
    const selectedTries = previewId ? triesOf(previewId) : 0;
    const selectedState = previewId && progress[previewId]?.completed
      ? interpolate(t('tsumego:tries_n', '{n} 次'), { n: selectedTries })
      : previewId === nowId ? t('Next up', '下一道') : t('Not attempted', '还没做过');

    return (
      <div className="kiosk-layout-a tsumego-browser">
        <div className="kiosk-board tsumego-browser__board" data-testid="problem-preview-board">
          <div className="kiosk-board__ruler kiosk-board__ruler--top">
            {colsFor(boardSize).map((c) => <span key={`t${c}`}>{c}</span>)}
          </div>
          <div className="kiosk-board__ruler kiosk-board__ruler--left">
            {rowsFor(boardSize).map((r) => <span key={`l${r}`}>{r}</span>)}
          </div>
          <div className="kiosk-board__play">
            <GoBoardSvg
              size={boardSize}
              black={preview ? previewCoords(preview.initialBlack, boardSize) : []}
              white={preview ? previewCoords(preview.initialWhite, boardSize) : []}
              label={interpolate(t('tsumego:problem_no', '第 {n} 题'), { n: selectedNumber })}
            />
          </div>
          <div className="kiosk-board__ruler kiosk-board__ruler--right">
            {rowsFor(boardSize).map((r) => <span key={`r${r}`}>{r}</span>)}
          </div>
          <div className="kiosk-board__ruler kiosk-board__ruler--bottom">
            {colsFor(boardSize).map((c) => <span key={`b${c}`}>{c}</span>)}
          </div>
          {!preview && (
            <div className="tsumego-browser__board-message" role="status">
              {activePreviewError ? (
                <>
                  <span>{loadErrorCopy(t, activePreviewError).title}</span>
                  <button type="button" onClick={() => { setPreviewError(null); setPreviewRetry((n) => n + 1); }}>
                    {t('Retry', '重试')}
                  </button>
                </>
              ) : <span>{t('Loading problem set…', '正在读题库…')}</span>}
            </div>
          )}
        </div>

        <div className="tsumego-browser__rail">
          {pagebar}
          <div className="tsumego-browser__stats">
            <div className="tsumego-browser__stat"><strong>{solved}<small> / {unitIds.length}</small></strong><span>{t('Solved in this unit', '本单元已做对')}</span></div>
            <div className="tsumego-browser__stat"><strong>{avgTries == null ? '—' : avgTries.toFixed(1)}</strong><span>{t('Average tries', '平均尝试次数')}</span></div>
            <div className="tsumego-browser__stat"><strong>{avgSeconds == null ? '—' : avgSeconds < 60 ? <>{avgSeconds}<small> {t('sec', '秒')}</small></> : <>{Math.floor(avgSeconds / 60)}<small> {t('min', '分')} </small>{avgSeconds % 60}<small> {t('sec', '秒')}</small></>}</strong><span>{t('Average time', '平均用时')}</span></div>
          </div>
          <div className="tsumego-browser__section"><b>{interpolate(t('tsumego:these_n_problems', '这 {n} 道题'), { n: unitIds.length })}</b><em>Problems</em></div>
          <div className="qgrid tsumego-browser__grid" data-testid="problems-grid">
            {unitIds.map((id, i) => {
              const done = !!progress[id]?.completed;
              const isNow = !done && id === nowId;
              const tries = triesOf(id);
              const n = offset + i + 1;
              const state = done ? t('Solved', '做对了') : isNow ? t('Next up', '下一道') : t('Not attempted', '还没做过');
              return (
                <button
                  type="button"
                  key={id}
                  className={`${done ? 'ok' : isNow ? 'now' : ''}${id === previewId ? ' selected' : ''}`}
                  aria-pressed={id === previewId}
                  aria-current={isNow ? 'step' : undefined}
                  aria-label={`${interpolate(t('tsumego:problem_no', '第 {n} 题'), { n })}，${state}${tries > 0 ? `，${interpolate(t('tsumego:tries_n', '{n} 次'), { n: tries })}` : ''}`}
                  onClick={() => { setPreviewError(null); setSelectedProblemId(id); }}
                >
                  <b>{n}</b><em>{tries > 0 ? interpolate(t('tsumego:tries_n', '{n} 次'), { n: tries }) : isNow ? t('You are here', '在这儿') : '—'}</em>
                </button>
              );
            })}
          </div>
          {!isAll ? (
            <div className="tsumego-browser__alternatives">
              <button type="button" onClick={() => navigate(`/kiosk/tsumego/${level}/all`)}>
                <span className="tsumego-browser__alt-icon">全</span><span><b>{levelName}全部</b><small>{t('Mixed training', '综合训练')}</small></span><i aria-hidden="true">›</i>
              </button>
              <button type="button" disabled={wrongIds.length === 0 && !wrongUnknown} onClick={() => navigate(`/kiosk/tsumego/${level}/${category}/wrong`)}>
                <span className="tsumego-browser__alt-icon tsumego-browser__alt-icon--wrong">错</span><span><b>{t('Only the ones I got wrong', '只做错过的')}</b><small>{wrongUnknown ? t('tsumego:progressUnread', '做题记录没读到') : interpolate(t('tsumego:wrong_now', '现在有 {n} 道'), { n: wrongIds.length })}</small></span><i aria-hidden="true">›</i>
              </button>
            </div>
          ) : <div />}
          <div className="tsumego-browser__selection" data-testid="problem-selection">
            <span className="tsumego-browser__selection-dot" />
            <b>{interpolate(t('tsumego:problem_no', '第 {n} 题'), { n: selectedNumberText })}</b>
            <span>{selectedState}</span>
            <span className="tsumego-browser__selection-hint">{t('tsumego:boardPreview', '左侧为棋形预览')}</span>
          </div>
          <button type="button" className="tsumego-browser__enter" data-testid="problem-enter" onClick={() => previewId && openProblem(previewId)}>
            <small>{interpolate(t('tsumego:problem_no', '第 {n} 题'), { n: selectedNumberText })}</small>
            <b>{t('tsumego:enterProblem', '进入做题屏')}</b>
            <span aria-hidden="true">↗</span>
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="kiosk-layout-b">
      {pagebar}
      <KioskScrollZone resetKey={`${level}/${category}/${isWrongSet ? 'wrong' : unitNumber}`}>
        <div className="kiosk-stats">
          {isWrongSet ? (
            <div className="kiosk-stat">
              <div className="kiosk-stat__v" data-testid="stat-wrong-count">
                {wrongIds.length}<small> {t('tsumego:dao', '道')}</small>
              </div>
              <div className="kiosk-stat__k">{t('tsumego:wrongStatLabel', '做错过、还没做对')}</div>
            </div>
          ) : (
            <div className="kiosk-stat">
              <div className="kiosk-stat__v">
                {solved}<small> / {unitIds.length}</small>
              </div>
              <div className="kiosk-stat__k">{t('Solved in this unit', '本单元已做对')}</div>
            </div>
          )}
          <div className="kiosk-stat">
            {/* 一道都没试过时写「—」:平均值没有被测对象,写 `0.0` 是在断言「平均试了 0 次」。 */}
            <div className="kiosk-stat__v" data-testid="stat-avg-tries">
              {avgTries == null ? '—' : avgTries.toFixed(1)}
            </div>
            <div className="kiosk-stat__k">{t('Average tries', '平均尝试次数')}</div>
          </div>
          {isWrongSet ? (
            <div className="kiosk-stat">
              <div className="kiosk-stat__v" data-testid="stat-solved-in-category">
                {solvedInCategory}<small> / {allIds.length}</small>
              </div>
              <div className="kiosk-stat__k">{t('tsumego:solvedInCategory', '这一类已做对')}</div>
            </div>
          ) : (
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
          )}
        </div>

        <section className="kiosk-section">
          <KioskSecLabel
            zh={interpolate(t('tsumego:these_n_problems', '这 {n} 道题'), { n: listIds.length })}
            en="Problems"
          />
          <div className="qgrid" data-testid="problems-grid">
            {listIds.map((id, i) => {
              const done = !!progress[id]?.completed;
              const isNow = !done && id === nowId;
              const tries = triesOf(id);
              const triesText = interpolate(t('tsumego:tries_n', '{n} 次'), { n: tries });
              const state = done
                ? t('Solved', '做对了')
                : isNow
                  ? t('Next up', '下一道')
                  : isWrongSet
                    ? t('tsumego:wrongState', '做错过')
                    : t('Not attempted', '还没做过');
              // 错题页写这道题在**这一类里的真题号**,不写它在错题里排第几 —— 做题屏、单元页说的都是这个号。
              const n = isWrongSet ? allIds.indexOf(id) + 1 : offset + i + 1;
              const problemNo = interpolate(t('tsumego:problem_no', '第 {n} 题'), { n });
              return (
                <button
                  type="button"
                  key={id}
                  className={done ? 'ok' : isNow ? 'now' : undefined}
                  aria-current={isNow ? 'step' : undefined}
                  aria-label={tries > 0 ? `${problemNo}，${state}，${triesText}` : `${problemNo}，${state}`}
                  onClick={() => openProblem(id)}
                >
                  <b>{n}</b>
                  {/* 试过就写试了几次;一次没试过的那一格,只有「下一道」那张有话可说。 */}
                  <em>{tries > 0 ? triesText : isNow ? t('You are here', '在这儿') : '—'}</em>
                </button>
              );
            })}
          </div>
        </section>

        {!isAll && <section className="kiosk-section">
          <KioskSecLabel zh={t('Other sets', '换一批')} en="Other sets" />
          <div className="kiosk-rows">
            <div className="kiosk-row">
              <span className="kiosk-row__lead">{t('Mixed', '综合')}</span>
              <div className="kiosk-row__t">
                <b>{t('Mixed training', '综合训练')}</b>
                <em>{t('Mix all categories at this level in 20-problem units', '混合当前难度全部题型，每 20 题一单元')}</em>
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
            {/* 错题页上不画这一行:它指向自己。 */}
            {!isWrongSet && (
              <div className="kiosk-row" data-testid="row-wrong">
                <span className="kiosk-row__lead">{t('Wrong', '错题')}</span>
                <div className="kiosk-row__t">
                  <b>{t('Only the ones I got wrong', '只做错过的')}</b>
                  <em>
                    {t('Redo the ones you got wrong in this category', '把这一类做错的重来一遍')}
                    {' · '}
                    {wrongUnknown
                      ? t('tsumego:progressUnread', '做题记录没读到')
                      : interpolate(t('tsumego:wrong_now', '现在有 {n} 道'), { n: wrongIds.length })}
                  </em>
                </div>
                <div className="kiosk-row__end">
                  {/* 0 道时灰:没有可作用的对象。有就进错题页(T1)。
                      做题记录没读到时不灰:0 是算不出来,错题页那边有重试。 */}
                  <button
                    type="button"
                    className="kiosk-btn kiosk-btn--pill"
                    disabled={wrongIds.length === 0 && !wrongUnknown}
                    onClick={() => navigate(`/kiosk/tsumego/${level}/${category}/wrong`)}
                  >
                    {t('Start', '开始')}
                  </button>
                </div>
              </div>
            )}
          </div>
        </section>}
      </KioskScrollZone>
    </div>
  );
};

export default TsumegoUnitListPage;
