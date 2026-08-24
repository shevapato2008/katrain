import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useLocation, useNavigate, useParams } from 'react-router-dom';

import { TutorialReadAPI } from '../../api/tutorialApi';
import { useTranslation } from '../../hooks/useTranslation';
import type { BoardPayload, TutorialFigure, TutorialSectionDetail } from '../../types/tutorial';
import TutorialVideoPlayer from '../../components/tutorials/TutorialVideoPlayer';
import { GoBoardSvg } from '../shell/GoBoardSvg';
import { GO_COLS, xyToCoord, type GoWindow } from '../shell/goBoard';
import { KioskActions } from '../shell/KioskActions';
import { KioskFold } from '../shell/KioskFold';
import { KioskPagebar } from '../shell/KioskPagebar';
import { KioskStepTrack } from '../shell/KioskStepTrack';
import type { SectionNavState } from '../types/tutorialNav';
import { interpolate } from '../utils/interpolate';

/**
 * 屏 25 · 课程 · 小节讲解 `/kiosk/tutorial/section/:sectionId` —— L2 布局 A
 * (盘 516 + 16 + 右栏 460)。课程这条路最里面那一层。
 *
 * 和别的布局 A 屏比,这一屏**左边画的不是一局棋而是一张变化图**:图上有手数号、
 * 字母(书正文里的「A 方面」)和记号,而且书上印的大多只是棋盘一角。
 *
 * ## 那块盘为什么还是 `GoBoardSvg`
 *
 * 上一版这里用的是 galaxy 那块 `components/tutorials/SGFBoard`。它画得出标注,
 * 但**边距是 0.75 格**(`SGFBoard.tsx:28`),而 kiosk 的刻度带按 0.5 格算
 * (`goBoard.ts` 的 `GO_MARGIN` 那段推导)—— 460 的落子区上两端各差 **5.59px**,
 * 而几何闸的容差是 1.5(`kiosk-shell-geometry.spec.ts`)。另外两条:
 * 它的九星写死 19 路(而 `models.py:89` 允许 9 / 13 / 19),
 * 它的木底是 `#dcb468` 平色(同一台盒子上两跳之内会出现两种盘)。
 * ⇒ 把**标注层**加到 `GoBoardSvg` 上,不换盘。四个既有消费者一个都不传那几个参数。
 *
 * ## 「局部 / 全盘」:没有 viewport 时整个开关不画
 *
 * 上一版那个二选一**在三个以上象限有子的图上是死的**:`SGFBoard.tsx:42-46` 里
 * `showFullBoard` 为假且 `viewport` 为 `null` 时**也**走全盘,按了没反应。
 * 现在:没有 `viewport` ⇒ 开关整个不渲染(不是灰掉,那一屏根本没有第二种画法);
 * 有 `viewport` ⇒ **默认落在「局部」**,依据是稿子自己那句「入门书的图大多只画棋盘一角,
 * 全盘显示会把那一角缩成指甲盖」,而且书上印的本来就是局部。
 * ⚠️ 这一条改了上一版的默认值(`showFull = true`),**最可能被 Fan 推回来** ——
 * 改回去只动一个初值。
 *
 * ## 刻度带按**节距**摆,不按等分
 *
 * 后端 `viewport.py:31` 只产四种形状:全盘 / 10×10 方窗 / 19×10 上下半盘 / 10×19 左右半盘。
 * 方窗那三种下「节距 = 落子区 / n」和共享包那条 `1fr` 等分**数学上完全一致**;
 * 只有半盘会真的用上 `max(cols, rows)` —— 短轴那条带于是只占一部分、居中留白,
 * 和盘自己 `xMidYMid meet` 留出来的白对齐。
 * **不许「撑成最小包含正方形」**:半盘长轴恰好 19,包成方形就是全盘,
 * 那会让半盘图上的「局部」和「全盘」画出同一张。
 *
 * ## 手数用档位轨,不是滑条
 *
 * `.kiosk-slider` 本仓有,但规范把它限定在**连续量**(`tokens.css:777`「落子确认速度这类
 * 连续量不许用分段控件硬掰成三档」)——手数是离散整数。稿子那个拇指是 16px,
 * 远低于 44;`.catpick` 的 ± 是 44×44。`maxStep === 0`(无编号的死活图)⇒ 整块不渲染,
 * 不摆一个 0/0 的控件。
 *
 * ## 「讲解」是三级阶梯,四个词一个都不共用
 *
 * 判别位顺序 `video_asset` → `audio_asset` → `narration`,行尾标依次是
 * **视频讲解 / 语音讲解 / 文字讲解 / 暂无讲解**。稿子那对「有讲解 / 本图暂无视频」作废 ——
 * 它把「有没有旁白」和「有没有视频」两根轴当成一根二值轴用(同一份列表里
 * 图4「有讲解」对 图6「本图暂无视频」)。
 *
 * **有视频时视频占左边那块 516 的盘位**,同一颗键切回棋图。量出来的理由:右栏 516 摊完
 * 之后折叠块只剩 ~120(两行),而 460 宽的 16:9 视频要 259 高。
 * 有视频时**不另放旁白** —— `scripts/generate_video.py:667` 已经把同一条旁白混进视频了。
 */

/** 图上编号最大的那一手(没有编号时 0)。 */
function maxMoveOf(fig: TutorialFigure | null): number {
  const labels = fig?.board_payload?.labels ?? {};
  return Math.max(0, ...Object.values(labels).map(Number).filter((n) => !Number.isNaN(n)));
}

type Teach = 'video' | 'audio' | 'text' | 'none';
const teachOf = (f: TutorialFigure): Teach =>
  (f.video_asset ? 'video' : f.audio_asset ? 'audio' : f.narration ? 'text' : 'none');

/** `"3,15"` → `[3, 15]`。后端那三张表(labels / letters / shapes)的键都是这个形状。 */
const parseKey = (k: string): [number, number] => {
  const [c, r] = k.split(',').map(Number);
  return [c, r];
};

const TutorialSectionPage = () => {
  const { sectionId } = useParams<{ sectionId: string }>();
  const navigate = useNavigate();
  const location = useLocation();
  const { t } = useTranslation();
  const nav = (location.state ?? null) as SectionNavState | null;

  const [section, setSection] = useState<TutorialSectionDetail | null>(null);
  // ⚠️ `null` = 没失败;`''` = 失败了但服务端没给话。**存的不是译文** ——
  // `useTranslation()` 的 `t` 每次渲染都是新函数,放进 effect 依赖这个 effect 每帧重跑。
  const [failed, setFailed] = useState<string | null>(null);
  const [reload, setReload] = useState(0);
  const [index, setIndex] = useState(0);

  // 下面这四个都**跟着当前那张图**:换图时它们自动失效,所以不需要一个「换图就清状态」
  // 的 effect(那种写法要么违反 `react-hooks/set-state-in-effect`,要么会多渲一帧旧值)。
  const [stepFor, setStepFor] = useState<{ id: number; step: number } | null>(null);
  const [fullFor, setFullFor] = useState<number | null>(null);
  const [videoFor, setVideoFor] = useState<number | null>(null);
  const [audioFor, setAudioFor] = useState<number | null>(null);
  const audioEl = useRef<HTMLAudioElement | null>(null);

  useEffect(() => {
    if (!sectionId) return;
    let cancelled = false;
    TutorialReadAPI.getSection(Number(sectionId))
      .then((data) => {
        if (cancelled) return;
        setSection(data);
        setFailed(null);
        setIndex(0);
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        setSection(null);
        setFailed(err instanceof Error ? err.message : '');
      });
    return () => { cancelled = true; };
  }, [sectionId, reload]);

  // 能画的图 = 有盘面的那些。翻页和「第 i / N 图」都按这一份数。
  const figures = useMemo(
    () => (section?.figures ?? []).filter((f) => f.board_payload),
    [section],
  );
  const current: TutorialFigure | null = figures[index] ?? null;
  const maxStep = useMemo(() => maxMoveOf(current), [current]);

  const effStep = stepFor && current && stepFor.id === current.id ? stepFor.step : maxStep;
  const full = current != null && fullFor === current.id;
  const onVideo = current != null && videoFor === current.id && Boolean(current.video_asset);
  const onAudio = current != null && audioFor === current.id;

  // 换图 / 离开时把音频停掉 —— 不停的话上一张图的旁白会一路念到下一张。
  useEffect(() => {
    if (onAudio) return;
    audioEl.current?.pause();
  }, [onAudio, index]);

  const backToToc = useCallback(() => {
    if (!nav?.category || !nav.bookId) { navigate('/kiosk/tutorial'); return; }
    const ch = nav.chapterId ? `&ch=${nav.chapterId}` : '';
    navigate(`/kiosk/tutorial/${encodeURIComponent(nav.category)}?book=${nav.bookId}${ch}`);
  }, [nav, navigate]);

  // ── 盘面:把 `[col,row]` 换成 `"Q16"`,只在这一处 ──
  const board = useMemo(() => {
    const p = current?.board_payload as BoardPayload | undefined;
    if (!p) return null;
    const size = p.size ?? 19;
    const at = (c: number, r: number) => xyToCoord(c, r, size);
    const labels = p.labels ?? {};
    const numAt = new Map<string, string>();
    for (const [k, v] of Object.entries(labels)) {
      const [c, r] = parseKey(k);
      numAt.set(at(c, r), v);
    }
    /** 编号大于当前手数的子**整颗不画**;没编号的子是这张图的底子,永远画。 */
    const visible = (coord: string) => {
      const n = Number(numAt.get(coord));
      return Number.isNaN(n) ? true : n <= effStep;
    };
    const black = (p.stones?.B ?? []).map(([c, r]) => at(c, r)).filter(visible);
    const white = (p.stones?.W ?? []).map(([c, r]) => at(c, r)).filter(visible);
    const numbers: Record<string, string> = {};
    numAt.forEach((v, coord) => { if (visible(coord)) numbers[coord] = v; });
    const letters: Record<string, string> = {};
    for (const [k, v] of Object.entries(p.letters ?? {})) {
      const [c, r] = parseKey(k); letters[at(c, r)] = v;
    }
    const shapes: Record<string, string> = {};
    for (const [k, v] of Object.entries(p.shapes ?? {})) {
      const [c, r] = parseKey(k); shapes[at(c, r)] = v;
    }
    const highlights = (p.highlights ?? []).map(([c, r]) => at(c, r));

    const vp = p.viewport ?? null;
    const win: GoWindow | null = vp && !full
      ? {
        col: vp.col, row: vp.row,
        cols: vp.cols ?? vp.size ?? size,
        rows: vp.rows ?? vp.size ?? size,
      }
      : null;
    const cols = win ? win.cols : size;
    const rows = win ? win.rows : size;
    return {
      size, black, white, numbers, letters, shapes, highlights,
      win, cols, rows, hasViewport: vp != null,
      // 刻度带写的是**这个窗口里的那几个坐标**,不是恒 A–T / 19–1。
      colLabels: [...GO_COLS].slice(win ? win.col : 0, (win ? win.col : 0) + cols),
      rowLabels: Array.from({ length: rows }, (_, i) => size - (win ? win.row : 0) - i),
    };
  }, [current, effStep, full]);

  // ── 三级阶梯:动作区中间那格恒存在、图标恒 speaker-high,标签随状态换 ──
  const teach: Teach = current ? teachOf(current) : 'none';
  const teachAction = () => {
    if (!current) return;
    if (teach === 'video') { setVideoFor(onVideo ? null : current.id); return; }
    if (teach === 'audio') {
      if (onAudio) { audioEl.current?.pause(); setAudioFor(null); return; }
      setAudioFor(current.id);
      // 播放要等 `<audio>` 的 src 挂上 —— 这一帧它才刚被渲出来。
      requestAnimationFrame(() => { void audioEl.current?.play().catch(() => setAudioFor(null)); });
    }
  };
  const teachLabel = teach === 'video'
    ? (onVideo ? t('tutorial:back_to_diagram', '回到棋图') : t('tutorial:watch_video', '看视频讲解'))
    : teach === 'audio'
      ? (onAudio ? t('tutorial:stop_audio', '停下') : t('tutorial:play_audio', '播放语音讲解'))
      : teach === 'text'
        ? t('tutorial:text_only', '只有文字讲解')
        : t('tutorial:teach_none', '暂无讲解');
  const teachReason = teach === 'text'
    ? t('tutorial:text_only_reason', '这张图只有文字讲解，已经写在上面了')
    : teach === 'none'
      ? t('tutorial:teach_none_reason', '这张图还没有录讲解，云端同步下来才会有')
      : undefined;

  const tagOf = (f: TutorialFigure) => {
    const k = teachOf(f);
    if (k === 'video') return { cls: 'kiosk-tag kiosk-tag--win', text: t('tutorial:tag_video', '视频讲解') };
    if (k === 'audio') return { cls: 'kiosk-tag kiosk-tag--win', text: t('tutorial:tag_audio', '语音讲解') };
    if (k === 'text') return { cls: 'kiosk-tag', text: t('tutorial:tag_text', '文字讲解') };
    return { cls: 'kiosk-tag', text: t('tutorial:tag_none', '暂无讲解') };
  };

  const crumb = nav?.chapterNumber
    ? `${nav.chapterNumber} · ${interpolate(t('tutorial:section_n', '第 {n} 节'), { n: section?.section_number ?? '' })} ${section?.title ?? ''}`
    : `${interpolate(t('tutorial:section_n', '第 {n} 节'), { n: section?.section_number ?? '' })} ${section?.title ?? ''}`;

  // ── 读不到 / 还在读 / 这一节没有图:三句话,布局 B(没有盘可画) ──
  if (!section || !current || !board) {
    const state = failed !== null
      ? { id: 'tutorial-section-error', h: t('tutorial:section_failed', '没读到这一节'), p: failed }
      : !section
        ? { id: 'tutorial-section-loading', h: t('tutorial:section_loading', '正在读这一节'), p: '' }
        : { id: 'tutorial-section-empty', h: t('tutorial:no_figures', '这一节还没有棋图'), p: t('tutorial:no_figures_hint', '目录里有这一节，正文还没同步下来；这不是你这台盒子的问题。') };
    return (
      <div className="kiosk-layout-b" data-testid="tutorial-section-page">
        <KioskPagebar
          testId="tutorial-section-pagebar"
          backLabel={t('tutorial:back_toc', '目录')}
          onBack={backToToc}
          title={section?.title ?? t('tutorial:title_cn', '课程')}
        />
        <div className="empty" data-testid={state.id}>
          <h4>{state.h}</h4>
          {state.p && <p>{state.p}</p>}
          {failed !== null && (
            <button
              type="button"
              className="kiosk-btn kiosk-btn--pill pill"
              onClick={() => { setFailed(null); setReload((v) => v + 1); }}
            >
              {t('kifu:retry', '重试')}
            </button>
          )}
        </div>
      </div>
    );
  }

  const explain = current.narration || current.book_text || '';

  return (
    <div className="kiosk-layout-a" data-testid="tutorial-section-page">
      {onVideo && current.video_asset ? (
        // 视频占的就是那块 516 —— 右栏摊完之后折叠块只剩两行,460 宽的 16:9 要 259 高。
        <div className="figvideo" data-testid="tutorial-figure-video">
          <TutorialVideoPlayer
            fill
            src={TutorialReadAPI.assetUrl(current.video_asset)}
            poster={TutorialReadAPI.assetUrl(current.video_asset.replace(/\.mp4$/, '.jpg'))}
          />
        </div>
      ) : (
        <div
          className="kiosk-board figure-board"
          data-testid="tutorial-figure-board"
          data-window={board.win ? `${board.cols}x${board.rows}` : 'full'}
          // 刻度带的节距 = 盘的线节距。方窗时它和共享包那条 `1fr` 等分算出同一个数。
          style={{ ['--gb-axis' as string]: String(Math.max(board.cols, board.rows)) }}
        >
          <div className="kiosk-board__ruler kiosk-board__ruler--top">
            {board.colLabels.map((c) => <span key={`t${c}`}>{c}</span>)}
          </div>
          <div className="kiosk-board__ruler kiosk-board__ruler--left">
            {board.rowLabels.map((r) => <span key={`l${r}`}>{r}</span>)}
          </div>
          <div className="kiosk-board__play">
            <GoBoardSvg
              size={board.size}
              black={board.black}
              white={board.white}
              numbers={board.numbers}
              letters={board.letters}
              shapes={board.shapes}
              highlights={board.highlights}
              window={board.win ?? undefined}
              label={interpolate(t('tutorial:board_label', '{label}：这一节的变化图'), { label: current.figure_label })}
            />
          </div>
          <div className="kiosk-board__ruler kiosk-board__ruler--right">
            {board.rowLabels.map((r) => <span key={`r${r}`}>{r}</span>)}
          </div>
          <div className="kiosk-board__ruler kiosk-board__ruler--bottom">
            {board.colLabels.map((c) => <span key={`b${c}`}>{c}</span>)}
          </div>
        </div>
      )}

      <div className="kiosk-rail">
        <KioskPagebar
          testId="tutorial-section-pagebar"
          backLabel={t('tutorial:back_toc', '目录')}
          onBack={backToToc}
          title={crumb}
          sub={interpolate(t('tutorial:figure_ordinal', '第 {i} / {n} 图'), { i: index + 1, n: figures.length })}
          // 没有 viewport 就没有第二种画法 —— 摆一个按了不动的二选一,比不摆更坏。
          segment={board.hasViewport ? {
            value: full ? 'full' : 'part',
            options: [
              ['part', t('tutorial:partial', '局部')],
              ['full', t('tutorial:fullBoard', '全盘')],
            ],
            onChange: (v) => setFullFor(v === 'full' ? current.id : null),
            ariaLabel: t('tutorial:board_view', '看多大'),
          } : undefined}
        />

        {explain ? (
          <p className="setexplain figexplain" data-testid="tutorial-figure-explain">{explain}</p>
        ) : (
          <p className="setexplain figexplain" data-testid="tutorial-figure-explain">
            {t('tutorial:no_explain', '这张图书上没有配文字，也还没有录讲解。')}
          </p>
        )}

        {/* ── 这一节的图 ── */}
        <KioskFold
          fold="figures"
          grow
          testId="tutorial-figures-fold"
          title={t('tutorial:figures_in_section', '这一节的图')}
          // 收起的是明细不是结论 —— 「第 5 / 12 图」收起后照旧显示。
          value={interpolate(t('tutorial:figure_ordinal', '第 {i} / {n} 图'), { i: index + 1, n: figures.length })}
          bodyClassName="foldrows"
        >
            {figures.map((f, i) => {
              const tag = tagOf(f);
              const moves = maxMoveOf(f);
              const secs = f.video_duration_ms ? Math.round(f.video_duration_ms / 1000) : null;
              return (
                <button
                  key={f.id}
                  type="button"
                  className="kiosk-row figrow"
                  data-selected={i === index ? 'true' : undefined}
                  data-testid="tutorial-figure-row"
                  onClick={() => setIndex(i)}
                >
                  {/* 序号那一格按规范放的是**等宽序号**(`tokens.css:175`「23 手」);
                      图的名字是 `figure_label`,名字归标题位,一个值不摆两处。 */}
                  <span className="kiosk-row__lead">
                    {moves > 0
                      ? interpolate(t('tutorial:moves_n', '{n} 手'), { n: moves })
                      : '—'}
                  </span>
                  <span className="kiosk-row__t">
                    <b>{f.figure_label}</b>
                    {/* 秒数**只在 `video_duration_ms` 非空时出** —— 那一列量的是视频长度,
                        音频没有对应列,所以语音图不写秒数(写了就是编一个时长)。 */}
                    {secs != null && (
                      <em>{interpolate(t('tutorial:seconds_n', '{n} 秒'), { n: secs })}</em>
                    )}
                  </span>
                  <span className="kiosk-row__end">
                    <span className={tag.cls}>{tag.text}</span>
                  </span>
                </button>
              );
            })}
        </KioskFold>

        {/* ── 手数 ── 无编号的死活图整块不渲染,不摆一个 0/0 的控件 */}
        {maxStep > 0 && (
          <section className="setgrp" data-testid="tutorial-step-group">
            <KioskStepTrack
              label={t('tutorial:moves', '手数')}
              en="Moves"
              count={maxStep + 1}
              index={effStep}
              onChange={(i) => setStepFor({ id: current.id, step: i })}
              value={effStep === 0
                ? t('tutorial:step_zero', '只摆底子')
                : interpolate(t('tutorial:step_n', '走到第 {n} 手'), { n: effStep })}
              meta={interpolate(t('tutorial:step_total', '这张图共 {n} 手'), { n: maxStep })}
              decLabel={t('tutorial:step_back', '退一手')}
              incLabel={t('tutorial:step_fwd', '进一手')}
              testId="tutorial-step-track"
            />
          </section>
        )}

        {/* 灰了就得有人说为什么 —— 但**屏上已经说过的话不说第二遍**:
            `none` 那一档上面那段讲解块写的就是「书上没有配文字,也还没有录讲解」,
            再挂一行等于同一句话占两处(Fan 8-22:「不要写那么多解释文字」)。
            读屏那一侧不受影响 —— `reason` 照旧挂在按钮的 `title` 上。 */}
        {teach === 'text' && teachReason && <p className="kiosk-opthint">{teachReason}</p>}

        {/* 语音那一档:元素常挂着,`src` 跟着当前图走。 */}
        {teach === 'audio' && current.audio_asset && (
          <audio
            ref={audioEl}
            key={current.audio_asset}
            src={TutorialReadAPI.assetUrl(current.audio_asset)}
            preload="none"
            onEnded={() => setAudioFor(null)}
            data-testid="tutorial-figure-audio"
          />
        )}

        <KioskActions
          testId="tutorial-section-actions"
          ariaLabel={t('tutorial:figure_actions', '翻图与讲解')}
          actions={[
            {
              key: 'prev',
              icon: 'caret-left',
              label: t('tutorial:prev_figure', '上一图'),
              disabled: index === 0,
              onClick: () => setIndex((i) => Math.max(0, i - 1)),
            },
            {
              key: 'teach',
              icon: 'speaker-high',
              label: teachLabel,
              pressed: teach === 'video' ? onVideo : teach === 'audio' ? onAudio : undefined,
              disabled: teach === 'text' || teach === 'none',
              reason: teachReason,
              onClick: teachAction,
            },
            {
              key: 'next',
              icon: 'caret-right',
              label: t('tutorial:next_figure', '下一图'),
              disabled: index >= figures.length - 1,
              onClick: () => setIndex((i) => Math.min(figures.length - 1, i + 1)),
            },
          ]}
        />
      </div>
    </div>
  );
};

export default TutorialSectionPage;
