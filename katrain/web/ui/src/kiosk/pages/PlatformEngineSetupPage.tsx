import { useEffect, useMemo, useState } from 'react';
import { Alert } from '@mui/material';
import { useNavigate, useParams, useLocation } from 'react-router-dom';
import { backToState } from '../hooks/useBackTo';
import { API, type EngineLevel } from '../../api';
import { useTranslation } from '../../hooks/useTranslation';
import { useAuth } from '../../context/AuthContext';
import { useVision } from '../context/VisionContext';
import { KioskPagebar } from '../shell/KioskPagebar';
import { KioskScrollZone } from '../shell/KioskScrollZone';
import { KioskSecLabel } from '../shell/KioskSecLabel';
import KioskSetupBoard from '../components/board/KioskSetupBoard';
import AiOpponentPlate from '../components/setup/AiOpponentPlate';
import AiLevelSheet from '../components/setup/AiLevelSheet';
import { SetupPopoverHost } from '../components/setup/SetupPopoverHost';
import { SetupSelect } from '../components/setup/SetupSelect';
import { SetupDerived, SetupFixed } from '../components/setup/SetupDerived';
import { PLATFORM_META } from '../constants/platforms';
import { RULE_LABEL } from '../utils/setupOptions';
import { interpolate } from '../utils/interpolate';
import { platformErrorMessage } from '../utils/platformErrorMessage';
import { playInputState, writePlayOnBoard } from '../utils/playInput';
import { writeActiveSession } from '../utils/activeSession';

/** 星阵固定 19 路、中国规则；档位来自平台，让子与贴目沿用平台原有对应关系。 */
const HANDICAP_TRACK = [0, -1, 2, 3, 4, 5, 6, 7, 8, 9] as const;

const PlatformEngineSetupPage = () => {
  const { platform = 'golaxy' } = useParams<{ platform: string }>();
  const navigate = useNavigate();
  const location = useLocation();
  const { t } = useTranslation();
  // token 只当**凭据**用（严格盒端恒为 null，身份在 HttpOnly sb_go_token cookie 里）；
  // 「认没认证」一律判 isAuthenticated —— 判 token 会让盒上每个已登录用户都进不来。
  const { token, isAuthenticated } = useAuth();
  const { isVisionEnabled } = useVision();
  const meta = PLATFORM_META[platform] ?? { label: platform, labelCn: platform, color: '#888' };

  const [levels, setLevels] = useState<EngineLevel[]>([]);
  const [levelsLoading, setLevelsLoading] = useState(true);
  // ⚠️ `null` = 没失败;`''` = 失败了但服务端没给话。**存的不是译文** ——
  // `useTranslation()` 的 `t` 每次渲染都是新函数,把它放进 effect 依赖,这个 effect
  // 每帧重跑一次(屏 06 刚栽过同一个:`networkidle` 永远等不到)。
  const [levelsError, setLevelsError] = useState<string | null>(null);
  const [level, setLevel] = useState<number | null>(null);
  const [handicap, setHandicap] = useState<number>(0);
  const [humanColor, setHumanColor] = useState<'B' | 'W' | 'nigiri'>('nigiri');
  const [starting, setStarting] = useState(false);
  const [startError, setStartError] = useState('');
  const [sheetOpen, setSheetOpen] = useState(false);
  const [railEl, setRailEl] = useState<HTMLDivElement | null>(null);

  useEffect(() => {
    let cancelled = false;
    if (!platform || !isAuthenticated) return () => { cancelled = true; };
    setLevelsLoading(true);
    setLevelsError(null);
    API.platformEngineLevels(platform, token)
      .then(({ levels: fetched }) => {
        if (cancelled) return;
        setLevels(fetched);
        const sorted = [...fetched].sort((a, b) => a.elo_score - b.elo_score);
        // 默认停在最弱那一档 —— 一个没打过的人被默认丢给中盘 bot,第一局就没法看。
        if (sorted.length) setLevel(sorted[0].elo_score);
      })
      .catch((e: unknown) => {
        if (!cancelled) setLevelsError(platformErrorMessage(e, ''));
      })
      .finally(() => { if (!cancelled) setLevelsLoading(false); });
    return () => { cancelled = true; };
  }, [isAuthenticated, platform, token]);

  const sorted = useMemo(() => [...levels].sort((a, b) => a.elo_score - b.elo_score), [levels]);
  const currentIdx = sorted.findIndex((l) => l.elo_score === level);
  const current = currentIdx >= 0 ? sorted[currentIdx] : null;

  // 三段:设备能不能 / 这一局想不想 / 实际落在哪。路数恒 19,所以只剩摄像头那一条。
  const [inputTick, setInputTick] = useState(0);
  const playInput = useMemo(
    () => playInputState(isVisionEnabled, 19),
    // eslint-disable-next-line react-hooks/exhaustive-deps -- inputTick 就是「偏好刚被改过」这个信号
    [isVisionEnabled, inputTick],
  );

  const komiLabel = handicap === 0 ? t('platform:komi_75', '黑贴 7.5 目')
    : handicap === -1 ? t('platform:komi_0', '不贴目')
      : interpolate(t('platform:komi_n', '黑贴 {n} 子'), { n: handicap });

  const start = async () => {
    if (!isAuthenticated || level === null) return;
    setStartError('');
    setStarting(true);
    try {
      const { session_id } = await API.platformEngineStart(
        platform, { level, human_color: humanColor, handicap }, token,
      );
      const route = `/kiosk/play/cross-platform/engine/game/${session_id}`;
      writeActiveSession({
        kind: 'game',
        label: interpolate(t('platform:engine_title', '{name} · 人机'), { name: t(meta.label, meta.labelCn) }),
        route,
        ts: Date.now(),
        onBoard: playInput.onBoard,
      });
      navigate(route, { state: backToState(location) });
    } catch (e) {
      setStartError(platformErrorMessage(e, t('Failed to start game', '创建对局失败')));
    } finally {
      setStarting(false);
    }
  };

  return (
    <div className="kiosk-layout-a" data-testid="platform-engine-setup-page">
      {/* 左栏 = 按下「开始对局」后真会出现的那个局面。让先(−1)盘上不摆子。 */}
      <KioskSetupBoard
        size={19}
        handicap={handicap > 0 ? handicap : 0}
        color={humanColor === 'B' ? 'black' : humanColor === 'W' ? 'white' : undefined}
      />

      <div className="kiosk-rail" data-su="platform" ref={setRailEl}>
        <SetupPopoverHost.Provider value={railEl}>
        <KioskPagebar
          testId="platform-engine-pagebar"
          backLabel={t('platform:back_to_platforms', '跨平台')}
          onBack={() => navigate('/kiosk/play/cross-platform')}
          title={interpolate(t('platform:engine_title', '{name} · 人机'), { name: t(meta.label, meta.labelCn) })}
          sub={t('platform:engine_sub', '开局设置 · 不计入盒内段位')}
        />

        <KioskScrollZone className="setgrp-scroll">
          <section className="setgrp" data-testid="setup-game-group">
            <KioskSecLabel
              zh={t('setup:game_terms', '这局棋')}
              en="Game"
              value={t('setup:locked_after_start', '开局后不可改')}
            />
            <div className="su-row">
              <SetupFixed label={t('setup:size', '路数')} value={t('setup:size_19', '19 路')} testId="setup-size" />
              <SetupFixed label={t('Rules', '规则')} value={RULE_LABEL(t).chinese} testId="setup-rules" />
              <SetupSelect
                testId="setup-handicap"
                label={t('Handicap', '让子')}
                value={String(handicap)}
                columns={2}
                options={HANDICAP_TRACK.map((n) => ({
                  key: String(n),
                  label: n === 0 ? t('setup:even', '分先')
                    : n === -1 ? t('platform:black_first', '让先')
                      : interpolate(t('setup:handicap_n', '让 {n} 子'), { n }),
                }))}
                onChange={(k) => setHandicap(Number(k))}
              />
            </div>
            <SetupDerived
              testId="setup-komi"
              label={t('Komi', '贴目')}
              note={t('setup:komi_derived', '随规则和让子定')}
            >
              {komiLabel}
            </SetupDerived>
          </section>

          {/* 棋力档只从平台名单选，名牌点开完整菜单。 */}
          <section className="setgrp" data-testid="setup-opponent">
            {levelsLoading ? (
              <>
                <KioskSecLabel zh={t('platform:opponent', '对手')} en="Opponent" />
                <p className="lobbyempty">{t('lobby:loading', '正在读…')}</p>
              </>
            ) : levelsError !== null ? (
              <>
                <KioskSecLabel zh={t('platform:opponent', '对手')} en="Opponent" />
                {/* **不给兜底表。** 编一份档次出来,人选中的会是星阵不认识的那一档。 */}
                <Alert severity="error" sx={{ fontSize: '0.75rem' }}>
                  {levelsError || t('platform:levels_failed', '没能从平台取回棋力档')}
                </Alert>
              </>
            ) : (
              <>
                <KioskSecLabel
                  zh={t('platform:opponent', '对手')}
                  en="Opponent"
                  value={interpolate(
                    t('platform:levels_from', '{name}下发 {n} 档'),
                    { name: t(meta.label, meta.labelCn), n: sorted.length },
                  )}
                />
                {current && (
                  <AiOpponentPlate
                    name={current.name}
                    levelName={current.level_name}
                    displayElo={current.display_elo}
                    refRank={current.ref_rank || undefined}
                    index={Math.max(0, currentIdx)}
                    total={sorted.length}
                    onOpen={() => setSheetOpen(true)}
                    testId="setup-opponent-plate"
                  />
                )}
              </>
            )}
          </section>

          <section className="setgrp" data-testid="setup-seat-group">
            <KioskSecLabel zh={t('setup:seat', '怎么坐')} en="Seat" />
            <div className="su-row su-row--2">
              <SetupSelect
                testId="setup-input"
                label={t('setup:input_where', '落子')}
                value={playInput.onBoard ? 'board' : 'screen'}
                options={[
                  { key: 'screen', label: t('setup:on_screen', '屏幕') },
                  {
                    key: 'board', label: t('setup:on_board', '实体盘'),
                    disabled: !playInput.available,
                    reason: t('setup:board_not_ready', '没标定过摄像头'),
                  },
                ]}
                onChange={(k) => { writePlayOnBoard(k === 'board'); setInputTick((n) => n + 1); }}
              />
              <SetupSelect
                testId="setup-side"
                label={t('setup:my_side', '我执')}
                value={humanColor}
                options={[
                  { key: 'nigiri', label: <><span className="disc rnd" />{t('platform:nigiri', '猜先')}</> },
                  { key: 'B', label: <><span className="disc b" />{t('setup:take_black', '执黑')}</> },
                  { key: 'W', label: <><span className="disc w" />{t('setup:take_white', '执白')}</> },
                ]}
                onChange={(k) => setHumanColor(k as 'B' | 'W' | 'nigiri')}
              />
            </div>
            <p className="su-hint" data-testid="setup-input-hint">
              {playInput.available
                ? interpolate(
                    t('platform:engine_fixed_hint', '{name}人机固定 19 路 · 中国规则，屏幕和实体盘走同一条隧道'),
                    { name: t(meta.label, meta.labelCn) },
                  )
                : t('setup:no_camera_hint', '这台盒子还没标定摄像头，实体盘这条路现在走不了')}
            </p>
          </section>
        </KioskScrollZone>

        {sheetOpen && current && (
          <AiLevelSheet
            levels={sorted}
            currentElo={level}
            onPick={(elo) => setLevel(elo)}
            onClose={() => setSheetOpen(false)}
            testId="setup-level-sheet"
          />
        )}

        {startError && <Alert severity="error" sx={{ mb: 1 }}>{startError}</Alert>}

        <button
          type="button"
          className="kiosk-primary-action"
          data-testid="platform-engine-start"
          disabled={starting || level === null}
          onClick={() => { void start(); }}
        >
          {starting ? t('Creating...', '创建中...') : t('setup:start', '开始对局')}
        </button>
        </SetupPopoverHost.Provider>
      </div>
    </div>
  );
};

export default PlatformEngineSetupPage;
