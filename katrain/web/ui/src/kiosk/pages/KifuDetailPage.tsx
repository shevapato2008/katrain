import { useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { useReplayStoneSound } from '../../hooks/useReplayStoneSound';
import { useTranslation } from '../../hooks/useTranslation';
import { ApiError } from '../../api';
import { KifuAPI } from '../../api/kifuApi';
import { BaipuAPI, canonToGtp, type BaipuStep } from '../../api/baipuApi';
import { replayBaipuSteps } from '../../utils/baipuReplay';
import { translateResult } from '../../utils/resultTranslation';
import { formatRank } from '../../utils/rank';
import { colsFor, rowsFor } from '../shell/goBoard';
import { GoBoardSvg } from '../shell/GoBoardSvg';
import { KioskPagebar } from '../shell/KioskPagebar';
import PhysicalBoardButton from '../components/PhysicalBoardButton';
import './kifuLibrary.css';
import { Icon } from '../shell/icons';
import type { KifuAlbumDetail } from '../../types/kifu';

interface MoveEntry {
  n: number;
  coord: string | null;
  color: 'B' | 'W';
  stepIndex: number;
}

/** Professional SGF replay keeps the recorded moves separate from AI analysis. */
const rulesLabel = (rules: string | null, t: (k: string, d: string) => string): string | null => {
  if (!rules) return t('kifu:rules_unresolved', '规则待核验');
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
  const { t, lang } = useTranslation();

  const [loadedAlbum, setLoadedAlbum] = useState<KifuAlbumDetail | null>(null);
  const [loadedLang, setLoadedLang] = useState<string | null>(null);
  const [steps, setSteps] = useState<BaipuStep[] | null>(null);
  const [boardSize, setBoardSize] = useState(19);
  const [error, setError] = useState<string | null>(null);
  const [failure, setFailure] = useState<'unreachable' | 'service' | 'other'>('other');
  const [reload, setReload] = useState(0);
  const [infoOpen, setInfoOpen] = useState(false);
  const [cursor, setCursor] = useState(0);   // 已经走到第几手(0 = 开局)
  const loadedIdRef = useRef<number | null>(null);

  useEffect(() => {
    if (!kifuId) return;
    let cancelled = false;
    // ⚠️ 清空只能发生在异步回调里(`react-hooks/set-state-in-effect`) —— 效应体里同步
    // setState 会连锁重渲染。重试时那句 `setError(null)` 挂在按钮的点击处理里,那是事件不是效应。
    KifuAPI.getAlbum(Number(kifuId), lang)
      .then(async (detail) => {
        if (cancelled) return;
        if (!detail.sgf_content) throw new Error('empty sgf');
        const loaded = await BaipuAPI.load({ sgf: detail.sgf_content });
        if (cancelled) return;
        setError(null);
        setLoadedAlbum(detail);
        setLoadedLang(lang);
        setSteps(loaded.steps);
        setBoardSize(loaded.board_size || detail.board_size || 19);
        if (loadedIdRef.current !== detail.id) setCursor(loaded.steps.filter(step => step.kind === 'move' || step.kind === 'pass').length);
        loadedIdRef.current = detail.id;
      })
      .catch((e: Error) => {
        if (!cancelled) {
          setError(e.message);
          const detail = e instanceof ApiError ? e.detail : null;
          const unreachable = e instanceof ApiError && e.status === 503
            && typeof detail === 'object' && detail !== null
            && 'code' in detail && detail.code === 'kifu_cloud_unreachable';
          setFailure(unreachable ? 'unreachable' : e instanceof ApiError && e.status >= 500 ? 'service' : 'other');
        }
      });
    return () => { cancelled = true; };
  }, [kifuId, reload, lang]);

  const album = loadedLang === lang ? loadedAlbum : null;

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
  useReplayStoneSound({ identity: album?.id ?? null, cursor: at, move: entries[at - 1]?.coord ?? undefined,
    ready: !!album && album.id === Number(kifuId) && steps !== null, selected: true, boardSize });
  // 走到第 `at` 手 = 播到那一手所在的 step(含),开局则只播它前面的 setup。
  const stepCount = at === 0
    ? (entries[0]?.stepIndex ?? steps?.length ?? 0)
    : entries[at - 1].stepIndex + 1;
  const board = useMemo(
    () => (steps ? replayBaipuSteps(steps, stepCount, boardSize) : { black: [], white: [] }),
    [steps, stepCount, boardSize],
  );

  const cols = colsFor(boardSize);
  const rows = rowsFor(boardSize);
  const title = album
    ? [album.display_event ?? album.event, album.display_round_name ?? album.round_name].filter(Boolean).join(' · ') || t('kifu:untitled_game', '无题名的一局')
    : t('kifu:back_kifu', '棋谱');

  const meta = album
    ? [
      album.date_played,
      `${boardSize} ${t('kifu:board_lines', '路')}`,
      rulesLabel(album.rules, t),
      album.komi != null ? `${t('report:sgf_komi', 'SGF 贴目')} ${album.komi} ${t('kifu:komi_unit', '目')}` : null,
      album.handicap > 0 ? `${t('kifu:handicap_pre', '让')} ${album.handicap} ${t('kifu:handicap_unit', '子')}` : null,
      album.result ? translateResult(album.result, t, album.rules) : null,
      `${album.move_count} ${t('kifu:moves_unit', '手')}`,
    ].filter(Boolean).join(' · ')
    : '';

  const recentEntries = entries.slice(Math.max(0, at - 6), at);

  return (
    <div className="kiosk-layout-a kifu-replay-reviewed">
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

      {infoOpen && album && <div className="kifu-replay-info" role="dialog" aria-modal="true" aria-label={t('kifu:game_details', '棋局详情')}>
        <div className="kifu-replay-info__panel"><h2>{t('kifu:game_details', '棋局详情')}</h2><p>{title}</p><p>{meta}</p>
          <button type="button" onClick={() => setInfoOpen(false)}>{t('common:close', '关闭')}</button>
        </div>
      </div>}
      <div className="kiosk-rail">
        <KioskPagebar
          testId="kifu-detail-pagebar"
          backLabel={t('kifu:back_kifu', '棋谱')}
          onBack={() => navigate('/kiosk/kifu')}
          title={t('kifu:professional_library', '职业棋谱')}
          sub={undefined}
          action={{ icon: 'info', label: t('kifu:game_details', '棋局详情'), onClick: () => setInfoOpen(true) }}
        />

        {error ? (
          <div className="empty" data-testid="kifu-detail-error">
            <h4>{failure === 'unreachable'
              ? t('kifu:detail_offline', '无法连接棋谱库')
              : failure === 'service'
                ? t('kifu:service_unavailable', '棋谱库暂时不可用')
                : t('kifu:load_failed', '这一局读不到')}</h4>
            <p>{failure === 'unreachable'
              ? t('kifu:detail_offline_hint', '请检查网络连接或稍后重试。')
              : failure === 'service'
                ? t('kifu:service_unavailable_hint', '云端服务暂时出了问题，请稍后重试。')
                : error}</p>
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
            <section className="kifu-replay-match" data-testid="kifu-detail-hero" title={meta}>
              <strong>{title}</strong>
              <div className="kifu-replay-players">
                <span><i className="kifu-record__stone kifu-record__stone--black" />{album.display_player_black ?? album.player_black ?? t('game:black_side', '黑方')}{album.display_black_rank && <small>{formatRank(album.display_black_rank, t)}</small>}</span>
                <em>{t('kifu:versus', '对')}</em>
                <span>{album.display_player_white ?? album.player_white ?? t('game:white_side', '白方')}{album.display_white_rank && <small>{formatRank(album.display_white_rank, t)}</small>}<i className="kifu-record__stone kifu-record__stone--white" /></span>
              </div>
              <small>{[album.date_played, `${total} ${t('kifu:moves_unit', '手')}`, translateResult(album.result, t, album.rules)].filter(Boolean).join(' · ')}</small>
            </section>
            <section className="kifu-replay-pending" role="status">
              <strong>{album.has_analysis ? t('kifu:replay_only', '棋谱回放') : t('kifu:not_analyzed_yet', '尚未分析')}</strong>
              <span>{album.has_analysis ? t('kifu:replay_available_analysis_hint', '当前显示原始棋谱。分析数据可从棋谱列表的「查看分析」进入。') : t('kifu:replay_analysis_hint', '这局的棋谱已经收录，可以逐手查看。胜率、推荐和失误需要分析后才会显示。')}</span>
            </section>
            <section className="kifu-replay-recent" data-testid="kifu-detail-moves">
              <div><strong>{t('kifu:recent_moves', '最近落子')}</strong><span>{t('kifu:move_ordinal', '第')} {at} / {total} {t('kifu:moves_unit', '手')}</span></div>
              <div className="kifu-replay-move-grid">
                {recentEntries.length ? recentEntries.map(entry => <button key={entry.n} type="button" aria-pressed={entry.n === at} onClick={() => setCursor(entry.n)}>
                  <b>{entry.n}</b><i className={`kifu-record__stone kifu-record__stone--${entry.color === 'B' ? 'black' : 'white'}`} />{entry.coord ?? t('kifu:pass', '虚手')}
                </button>) : <span>{t('kifu:opening_position', '开局盘面')}</span>}
              </div>
            </section>
            <div className="kifu-replay-actions" data-testid="kifu-detail-actions">
              <PhysicalBoardButton source={`kifu_${album.id}`} name={title} sgf={album.sgf_content} boardSize={boardSize} />
            </div>
            <div className="kifu-replay-playback" data-testid="kifu-detail-movenav">
              <button type="button" aria-label={t('kifu:to_start', '回到开局')} disabled={at === 0} onClick={() => setCursor(0)}><Icon name="caret-double-left" /></button>
              <button type="button" aria-label={t('kifu:prev_move', '上一手')} disabled={at === 0} onClick={() => setCursor(value => Math.max(0, value - 1))}><Icon name="caret-left" /></button>
              <input type="range" min="0" max={total} value={at} aria-label={t('kifu:move_slider', '棋谱手数')} onChange={event => setCursor(Number(event.target.value))} />
              <button type="button" aria-label={t('kifu:next_move', '下一手')} disabled={at >= total} onClick={() => setCursor(value => Math.min(total, value + 1))}><Icon name="caret-right" /></button>
              <button type="button" aria-label={t('kifu:to_end', '跳到最后')} disabled={at >= total} onClick={() => setCursor(total)}><Icon name="caret-double-right" /></button>
            </div>
          </>
        )}
      </div>
    </div>
  );
};

export default KifuDetailPage;
