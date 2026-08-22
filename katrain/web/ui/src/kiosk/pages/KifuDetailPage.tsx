import { useCallback, useEffect, useMemo, useRef, useState, type MutableRefObject } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { useTranslation } from '../../hooks/useTranslation';
import { KifuAPI } from '../../api/kifuApi';
import { BaipuAPI, cacheSgf, canonToGtp, type BaipuStep } from '../../api/baipuApi';
import { replayBaipuSteps } from '../../utils/baipuReplay';
import { translateResult } from '../../utils/resultTranslation';
import { colsFor, rowsFor } from '../shell/goBoard';
import { GoBoardSvg } from '../shell/GoBoardSvg';
import { KioskPagebar } from '../shell/KioskPagebar';
import { KioskActions, type KioskAction } from '../shell/KioskActions';
import { KioskFold } from '../shell/KioskFold';
import { Icon } from '../shell/icons';
import type { KifuAlbumDetail } from '../../types/kifu';

/**
 * 屏 16 · 棋谱详情 `/kiosk/kifu/:kifuId` —— L2 布局 A(盘 516 + 16 + 右栏 460)。
 *
 * 稿子 `sample-go/go-kiosk.tmpl.html` 的 `data-screen="kifu-detail"`。**它在计划书里没有
 * 对应的 Task**(计划的 Task 15 只到屏 15),和屏 13 一样是稿子后来长出来的一屏 ——
 * 记成 Task 15b。做它的直接理由:屏 15 那张列表点下去总得有个落点,而这一屏的三件事
 * (逐手回放 / 摆到实体盘 / 去研究)现在散在 `KifuPage` 的预览栏和 `BaipuListPage` 里。
 *
 * ## 盘为什么不复用 `LiveBoard`
 *
 * `LiveBoard` 会算提子,但它的 `calculateBoardLayout` 写死 **1.5 格**边距,而刻度带要求
 * **0.5 格**(`goBoard.ts` 里那段推导:两式相等当且仅当 margin = 0.5)。对局屏是靠给共享
 * `Board` 加一个默认 false 的 `externalRulers` 解决的 —— 那条路对 `LiveBoard` 也走得通,
 * 但要连 `boardUtils.calculateBoardLayout` 一起改,而**这一屏的盘根本不需要能点**。
 * ⇒ 用 `GoBoardSvg`(边距 0.5 由构造保证)+ **后端给的提子结果**。
 *
 * ## 提子不在前端算
 *
 * `/api/v1/baipu/load` 每一步都带 `removed[]` —— `baipuApi.ts` 开头那段决策 ② 写得很直白:
 * 「前端是 `steps[]` 的**笨播放器**,永远不自己重算提子」。这里逐字照办:本页只做
 * 「放一颗 → 按给定名单删几颗」,一条围棋规则都不实现。**多写一份气/提子的实现,
 * 就是本轮反复吃过的「两份并行实现」。**
 *
 * ## 和稿子的三处出入(都在四图的标签带里写明)
 *
 * ① 稿子右上角那枚 `界面未接` 蓝标是**说给读稿人听的**(它说的正是这一屏当时没接),
 *    接上了就不成立,不搬。
 * ② 稿子画了三个动作键,第三个是 `送去复盘` —— **不搬,但理由不是「做不到」**(2026-08-22 更正:
 *    上一版这段写的是「这条路不存在」,不准确)。准确的说法是:
 *    `POST /api/v1/reports/` 收的是 `user_game_id`,服务端 `reports.py:133` 拿它去 `UserGame`
 *    表里查这一局是不是你下的 —— 名局棋谱**在那张表里没有行**,所以要先复制一份进去。
 *    而**那件事已经有地方做了**:复盘屏的「从棋谱库导入」(`ReportLibraryImportDialog`
 *    + `toLibraryUserGameParams`)就是干这个的。在这儿再开一个入口 = 同一条路两个口。
 *    galaxy 那边的棋谱库(`galaxy/pages/KifuLibraryPage.tsx`)也只有「在研究中打开」一个出口。
 *    ⇒ 这里两个键;要把名局送去复盘,走复盘屏那个导入。
 * ③ 稿子 `.khero` 那行只有名字,实现里补了段位 —— 段位是库里真有的列
 *    (`black_rank` / `white_rank`),现有的 `KifuPage` 列表也一直在显示。
 *
 * ## 三个 key 是另起的,不是复用
 *
 * `kifu:library` / `kifu:loading` / `kifu:handicap` 在 cn PO 里分别是「棋谱库」「加载中...」
 * 「让子」——**PO 赢默认值**,复用它们屏上出来的会是另外三句话(返回键写「棋谱库」而
 * Dock 上那一格叫「棋谱」;一个标题位置塞进「加载中...」;「让子 2 子」)。
 * 这正是闸四(`kiosk-shell-contract.spec.ts`)守的那条,新 key 是它逼出来的。
 */

/** 一手棋在列表里的样子。`n` 是第几手(从 1 数,setup 不算)。 */
interface MoveEntry {
  n: number;
  coord: string | null;   // null = 虚手
  color: 'B' | 'W';
  stepIndex: number;
}

const rulesLabel = (rules: string | null, t: (k: string, d: string) => string): string | null => {
  if (!rules) return null;
  const r = rules.trim().toLowerCase();
  if (r === 'chinese' || r === 'cn') return t('Chinese rules', '中国规则');
  if (r === 'japanese' || r === 'jp') return t('Japanese rules', '日本规则');
  if (r === 'korean' || r === 'ko') return t('Korean rules', '韩国规则');
  if (r === 'aga') return t('AGA rules', 'AGA 规则');
  // 认不出来就**照原样印**,不猜也不吞:库里存的就是这个字符串。
  return rules;
};

const KifuDetailPage = () => {
  const { kifuId } = useParams<{ kifuId: string }>();
  const navigate = useNavigate();
  const { t } = useTranslation();

  const [album, setAlbum] = useState<KifuAlbumDetail | null>(null);
  const [steps, setSteps] = useState<BaipuStep[] | null>(null);
  const [boardSize, setBoardSize] = useState(19);
  const [error, setError] = useState<string | null>(null);
  const [reload, setReload] = useState(0);
  const [cursor, setCursor] = useState(0);   // 已经走到第几手(0 = 开局)
  const nowRef = useRef<HTMLSpanElement | null>(null);

  useEffect(() => {
    if (!kifuId) return;
    let cancelled = false;
    // ⚠️ 清空只能发生在异步回调里(`react-hooks/set-state-in-effect`) —— 效应体里同步
    // setState 会连锁重渲染。重试时那句 `setError(null)` 挂在按钮的点击处理里,那是事件不是效应。
    KifuAPI.getAlbum(Number(kifuId))
      .then(async (detail) => {
        if (cancelled) return;
        if (!detail.sgf_content) throw new Error('empty sgf');
        const loaded = await BaipuAPI.load({ sgf: detail.sgf_content });
        if (cancelled) return;
        setError(null);
        setAlbum(detail);
        setSteps(loaded.steps);
        setBoardSize(loaded.board_size || detail.board_size || 19);
        setCursor(0);
      })
      .catch((e: Error) => {
        if (!cancelled) setError(e.message);
      });
    return () => { cancelled = true; };
  }, [kifuId, reload]);

  // 手数表:只有 `move` / `pass` 算一手,让子的 setup 不算。
  const entries = useMemo<MoveEntry[]>(() => {
    if (!steps) return [];
    const out: MoveEntry[] = [];
    steps.forEach((s, i) => {
      if (s.kind !== 'move' && s.kind !== 'pass') return;
      const color = s.color ?? (out.length % 2 === 0 ? 'B' : 'W');
      out.push({
        n: out.length + 1,
        coord: s.row != null && s.col != null ? canonToGtp(s.row, s.col, boardSize) : null,
        color,
        stepIndex: i,
      });
    });
    return out;
  }, [steps, boardSize]);

  const total = entries.length;
  const at = Math.min(cursor, total);
  // 走到第 `at` 手 = 播到那一手所在的 step(含),开局则只播它前面的 setup。
  const stepCount = at === 0
    ? (entries[0]?.stepIndex ?? steps?.length ?? 0)
    : entries[at - 1].stepIndex + 1;
  const board = useMemo(
    () => (steps ? replayBaipuSteps(steps, stepCount, boardSize) : { black: [], white: [] }),
    [steps, stepCount, boardSize],
  );

  // 当前那一手要留在可视区里 —— 241 手的谱,不跟着滚等于翻不到。
  useEffect(() => {
    nowRef.current?.scrollIntoView({ block: 'nearest' });
  }, [at]);

  const goBaipu = useCallback(() => {
    if (!album?.sgf_content) return;
    const id = `kifu_${album.id}`;
    const name = [album.event, album.round_name].filter(Boolean).join(' · ')
      || `${album.player_black} vs ${album.player_white}`;
    cacheSgf(id, name, album.sgf_content);
    navigate(`/kiosk/baipu/session/${encodeURIComponent(id)}`, {
      state: { sgf: album.sgf_content, name },
    });
  }, [album, navigate]);

  const cols = colsFor(boardSize);
  const rows = rowsFor(boardSize);
  const title = album
    ? [album.event, album.round_name].filter(Boolean).join(' · ') || t('kifu:untitled_game', '无题名的一局')
    : t('kifu:back_kifu', '棋谱');

  const meta = album
    ? [
      album.date_played,
      `${boardSize} ${t('kifu:board_lines', '路')}`,
      rulesLabel(album.rules, t),
      album.komi != null ? `${t('kifu:komi_black', '黑贴')} ${album.komi} ${t('kifu:komi_unit', '目')}` : null,
      album.handicap > 0 ? `${t('kifu:handicap_pre', '让')} ${album.handicap} ${t('kifu:handicap_unit', '子')}` : null,
      album.result ? translateResult(album.result, t, album.rules) : null,
      `${album.move_count} ${t('kifu:moves_unit', '手')}`,
    ].filter(Boolean).join(' · ')
    : '';

  const actions: KioskAction[] = [
    {
      key: 'baipu',
      icon: 'grid-nine',
      label: t('kifu:place_on_board', '摆到实体盘'),
      onClick: goBaipu,
      disabled: !album?.sgf_content,
      reason: t('kifu:need_sgf', '这一局还没读到谱'),
    },
    {
      key: 'research',
      icon: 'magnifying-glass',
      label: t('kifu:to_research', '去研究'),
      onClick: () => navigate(`/kiosk/research?kifu_id=${album?.id}&analyze=1`),
      disabled: !album,
      reason: t('kifu:need_sgf', '这一局还没读到谱'),
    },
  ];

  // 一行两手:黑一格白一格。**不按下标奇偶分列** —— 让子局第一手是白,
  // 按奇偶排会把整份谱错开一格。
  const rowsOfMoves: (MoveEntry | null)[][] = [];
  for (const e of entries) {
    const tail = rowsOfMoves[rowsOfMoves.length - 1];
    if (e.color === 'B' || !tail || tail[1] !== null) rowsOfMoves.push([null, null]);
    const cur = rowsOfMoves[rowsOfMoves.length - 1];
    cur[e.color === 'B' ? 0 : 1] = e;
  }

  return (
    <div className="kiosk-layout-a">
      <div className="kiosk-board" data-testid="kifu-detail-board">
        <div className="kiosk-board__ruler kiosk-board__ruler--top">
          {cols.map((c) => <span key={`t${c}`}>{c}</span>)}
        </div>
        <div className="kiosk-board__ruler kiosk-board__ruler--left">
          {rows.map((r) => <span key={`l${r}`}>{r}</span>)}
        </div>
        <div className="kiosk-board__play">
          <GoBoardSvg
            size={boardSize}
            black={board.black}
            white={board.white}
            last={board.last}
            label={t('kifu:board_label', '棋谱回放盘面')}
          />
        </div>
        <div className="kiosk-board__ruler kiosk-board__ruler--right">
          {rows.map((r) => <span key={`r${r}`}>{r}</span>)}
        </div>
        <div className="kiosk-board__ruler kiosk-board__ruler--bottom">
          {cols.map((c) => <span key={`b${c}`}>{c}</span>)}
        </div>
      </div>

      <div className="kiosk-rail">
        <KioskPagebar
          testId="kifu-detail-pagebar"
          backLabel={t('kifu:back_kifu', '棋谱')}
          onBack={() => navigate('/kiosk/kifu')}
          title={title}
          sub={album ? `${t('kifu:replay', '逐手回放')} · ${t('kifu:move_ordinal', '第')} ${at} / ${total} ${t('kifu:moves_unit', '手')}` : undefined}
        />

        {error ? (
          <div className="empty" data-testid="kifu-detail-error">
            <h4>{t('kifu:load_failed', '这一局读不到')}</h4>
            <p>{error}</p>
            <button
              type="button"
              className="kiosk-btn kiosk-btn--pill pill"
              onClick={() => { setError(null); setReload((v) => v + 1); }}
            >
              {t('kifu:retry', '重试')}
            </button>
          </div>
        ) : !album ? (
          <div className="empty" data-testid="kifu-detail-loading">
            <h4>{t('kifu:loading_this_game', '正在读这一局')}</h4>
            <p>{t('kifu:loading_hint', '棋谱和逐手记录都要从服务器取。')}</p>
          </div>
        ) : (
          <>
            <div className="khero" data-testid="kifu-detail-hero">
              <b>
                {album.player_black}
                {album.black_rank && <em>{album.black_rank}</em>}
                <i>{t('kifu:versus', '对')}</i>
                {album.player_white}
                {album.white_rank && <em>{album.white_rank}</em>}
              </b>
              <p>{meta}</p>
            </div>

            <KioskFold
              fold="moves"
              grow
              testId="kifu-detail-moves"
              title={t('kifu:moves_title', '棋谱 · 交叉点坐标')}
              value={`${t('kifu:move_ordinal', '第')} ${at} ${t('kifu:moves_unit', '手')}`}
              bodyClassName="mvrows"
            >
              {rowsOfMoves.length === 0 ? (
                <span className="n">{t('kifu:no_moves', '这份谱里没有着法')}</span>
              ) : rowsOfMoves.map((pair, i) => (
                <RowOfMoves key={`r${i}`} index={i} pair={pair} at={at} nowRef={nowRef} onPick={setCursor} passLabel={t('kifu:pass', '虚手')} />
              ))}
            </KioskFold>

            <div className="kiosk-movenav" data-testid="kifu-detail-movenav">
              <button type="button" aria-label={t('kifu:to_start', '回到开局')} disabled={at === 0} onClick={() => setCursor(0)}>
                <Icon name="caret-double-left" />
              </button>
              <button type="button" aria-label={t('kifu:prev_move', '上一手')} disabled={at === 0} onClick={() => setCursor((v) => Math.max(0, Math.min(v, total) - 1))}>
                <Icon name="caret-left" />
              </button>
              <button type="button" aria-label={t('kifu:next_move', '下一手')} disabled={at >= total} onClick={() => setCursor((v) => Math.min(total, v + 1))}>
                <Icon name="caret-right" />
              </button>
              <button type="button" aria-label={t('kifu:to_end', '跳到最后')} disabled={at >= total} onClick={() => setCursor(total)}>
                <Icon name="caret-double-right" />
              </button>
            </div>

            <KioskActions
              testId="kifu-detail-actions"
              ariaLabel={t('kifu:detail_actions', '这一局能做什么')}
              actions={actions}
            />
          </>
        )}
      </div>
    </div>
  );
};

/** 一行两手。点一格 = 跳到那一手 —— 241 手的谱靠四个键一手手按太慢。 */
function RowOfMoves({ index, pair, at, nowRef, onPick, passLabel }: {
  index: number;
  pair: (MoveEntry | null)[];
  at: number;
  nowRef: MutableRefObject<HTMLSpanElement | null>;
  onPick: (n: number) => void;
  passLabel: string;
}) {
  return (
    <>
      <span className="n">{index + 1}</span>
      {[0, 1].map((slot) => {
        const e = pair[slot];
        if (!e) return <span className="mv" key={slot} />;
        const isNow = e.n === at;
        return (
          <span
            key={slot}
            ref={isNow ? nowRef : undefined}
            className={isNow ? 'mv now' : 'mv'}
            role="button"
            tabIndex={0}
            onClick={() => onPick(e.n)}
            onKeyDown={(ev) => { if (ev.key === 'Enter' || ev.key === ' ') { ev.preventDefault(); onPick(e.n); } }}
          >
            {e.coord ?? passLabel}
          </span>
        );
      })}
    </>
  );
}

export default KifuDetailPage;
