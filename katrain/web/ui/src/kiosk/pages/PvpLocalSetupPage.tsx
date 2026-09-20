import { useMemo, useState } from 'react';
import { Alert } from '@mui/material';
import { useNavigate } from 'react-router-dom';
import { useVision } from '../context/VisionContext';
import { KioskPagebar } from '../shell/KioskPagebar';
import { KioskScrollZone } from '../shell/KioskScrollZone';
import { KioskSecLabel } from '../shell/KioskSecLabel';
import KioskSetupBoard from '../components/board/KioskSetupBoard';
import { interpolate } from '../utils/interpolate';
import {
  FREE_KOMI_MAX, FREE_KOMI_VALUES, HANDICAP_LABEL, RULES, RULE_LABEL,
  TIME_PRESETS, TIME_TRACK_ORDER, handicapKeysFor, resolveGameTerms,
  type HandicapKey,
} from '../utils/setupOptions';
import { SetupPopoverHost } from '../components/setup/SetupPopoverHost';
import { SetupSelect } from '../components/setup/SetupSelect';
import { SetupDerived } from '../components/setup/SetupDerived';
import { komiReadout } from '../components/setup/komiReadout';
import { playInputState, writePlayOnBoard } from '../utils/playInput';
import { API } from '../../api';
import { useTranslation } from '../../hooks/useTranslation';
import { useAuth } from '../../context/AuthContext';
import { writeActiveSession } from '../utils/activeSession';

/**
 * 屏 04 本地对局 · 开局设置(`sample-go/shots/04-setup-local.png`,L2 布局 A)。
 *
 * 首页「本地对局」那张卡唯一的落点。**和屏 02/03 同一副骨架**(左盘 516 + 16 + 右栏 460,
 * 右栏整栏滚,主行动键钉在栏底),差别是这一边**没有引擎对手**:没有棋力、没有 AI 策略、
 * 也没有「我执」—— 两个人面对面坐着,谁执黑是他们自己坐好的,不是这块屏上的一次选择。
 * 多出来的是**两个姓名输入**:四家里只有围棋有,因为面对面下完要记谱,谱上得有名字。
 *
 * ## 稿子这一屏有两处不成立,都按仓里的事实写
 *
 * ① **`.setnote` 第一句**。稿子写「这一边不接引擎,**没有提示也没有形势判断**」——
 *    前半句对、后半句不对。`interface.py:253` 的 `SCORING_GAME_TYPES` 只有
 *    `rated / ranked / ai_ladder_ranked` 三种,`pvp_local` **不在里面** ⇒
 *    `analysis_allowed` 为真,对局屏上那颗「领地」键照样能按,而领地就是形势判断。
 *    真正关掉的是另外两样:`GameControlPanel.tsx:113` 的 `evalAllowed` 把
 *    `pvp_local` 排除在外 ⇒ **胜负走势图整块不渲染**;`GamePage.tsx:451` 的
 *    `hintVisible` 要求 `game_type === 'free'` ⇒ **AI 支招是灰的**。
 *
 * ② **`.setnote` 第二句的后半**。稿子写「段位只有**在线大厅的定级队列**会改」——
 *    定级赛不在在线大厅,在「升降级对弈」:`LobbyPage.tsx:151` 那句挡人的话原文是
 *    「先在『升降级对弈』打完 5 局定级赛,才能进行人人排位」。而权威在
 *    `interface.py:258`:`RANK_MOVING_GAME_TYPES = ("ai_ladder_ranked",)`,注释逐字写着
 *    「Exactly one, by design」。照稿子写会把人指去一个改不了段位的地方。
 *
 * ③ **「白方 · 贴目的一方」反了**(稿子那一行)。贴目是**黑方贴给白方**的 ——
 *    `core/game.py:372` 里黑棋的分数减去 komi,少的那一边是黑。白方是**收**的那一方。
 *
 * ## 「怎么落子」是**真开关**(2026-08-23 改回来的)
 *
 * 这一屏第一版把它画成了一格读数,理由写的是「全仓没有任何地方能让用户切」——
 * **那句话是错的**:做题屏早就有这颗开关。设备能不能(`isVisionEnabled`)和这一局想不想
 * 是两段,第一版把后一段抹掉了。现在两段都在:`utils/playInput.ts` 存偏好,
 * `KioskApp` 的 `PlayInputGuard` 和 `GamePage` 都认它。
 *
 * 选中的是**这一局实际会落在哪**(`onBoard`),不是偏好本身 —— 屏上那块盘画的是
 * 「按下按钮后真会出现的局面」,同一屏的控件不能说另一件事。
 */
const PvpLocalSetupPage = () => {
  const navigate = useNavigate();
  const { t } = useTranslation();
  const { token } = useAuth();
  const { isVisionEnabled } = useVision();

  // Board & rules
  const [boardSize, setBoardSize] = useState(19);
  const [rules, setRules] = useState<string>('chinese');

  // Player names — 留空就不写 SGF 的 PB/PW(`server.py:1093`),对局屏回落到「黑方 / 白方」
  // (`GameControlPanel.tsx:66`)。**不替用户编一个名字。**
  const [blackName, setBlackName] = useState('');
  const [whiteName, setWhiteName] = useState('');

  /* 让子与贴目是**一个**枚举 —— 见 `utils/setupOptions.ts`,和屏 02 同一份模型。
     两人面对面下,终局怎么算是开局前必须谈好的事,所以这一屏的推导条尤其要说清。 */
  const [handicapKey, setHandicapKey] = useState<HandicapKey>('even');
  const [freeKomi, setFreeKomi] = useState(FREE_KOMI_MAX);

  // Time control
  const [timeEnabled, setTimeEnabled] = useState(false);
  const [mainTime, setMainTime] = useState(0);
  const [byoyomiTime, setByoyomiTime] = useState(30);
  const [byoyomiPeriods, setByoyomiPeriods] = useState(3);

  // Move sound — client-side preference, persisted in localStorage (shared useGameSession.playSound reads it).
  // Box-SSO guest mode (client-side zero-persistence, 4th layer, R9-F1): deliberately LEFT
  // GLOBAL — a mute/audio preference tied to the physical kiosk's environment (e.g. a quiet
  // room), not per-account activity or content, so it carries no identity-linkable residue.
  const [confirmSound, setConfirmSound] = useState(localStorage.getItem('kioskPlaySound') !== '0');

  /** 下拉弹层的宿主 —— 见 `components/setup/SetupPopoverHost.tsx`。 */
  const [railEl, setRailEl] = useState<HTMLDivElement | null>(null);

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const timePresets = TIME_PRESETS(t);
  const currentTimeKey = !timeEnabled ? 'untimed' : mainTime === 0 ? 'byoOnly' : String(mainTime);
  const timeTrack = [...TIME_TRACK_ORDER].map((key) => timePresets.find((p) => p.key === key)!);
  const applyTimePreset = (key: string) => {
    const preset = timePresets.find((p) => p.key === key);
    if (!preset) return;
    setTimeEnabled(preset.enabled);
    setMainTime(preset.main);
    setByoyomiTime(preset.byo);
    setByoyomiPeriods(preset.periods);
  };


  // 三段:设备能不能 / 这一局想不想 / 实际落在哪。`bumpInput` 只是为了让偏好写进
  // localStorage 之后这一屏重算一次 —— 偏好不在 React state 里,它跨屏活着。
  const [inputTick, setInputTick] = useState(0);
  const playInput = useMemo(
    () => playInputState(isVisionEnabled, boardSize),
    // eslint-disable-next-line react-hooks/exhaustive-deps -- inputTick 就是「偏好刚被改过」这个信号
    [isVisionEnabled, boardSize, inputTick],
  );
  const setPlayOnBoard = (next: boolean) => {
    writePlayOnBoard(next);
    setInputTick((n) => n + 1);
  };

  /* 换规则时顺手收拾让子:AI 赛规则只给分先(见 `handicapKeysFor`),
     不收拾的话 state 会停在一个这条规则下**不存在**的档上,
     屏上读数和可选项对不上,而送出去的仍是那个旧档。 */
  /* 换路数同理:13 路封到让 5 子、9 路封到让 4 子且没有倒贴。 */
  const pickSize = (next: number) => {
    setBoardSize(next);
    if (!handicapKeysFor(next, rules).includes(handicapKey)) setHandicapKey('even');
  };

  const pickRules = (next: string) => {
    setRules(next);
    if (!handicapKeysFor(boardSize, next).includes(handicapKey)) setHandicapKey('even');
  };

  const ruleLabels = RULE_LABEL(t);
  const handicapLabels = HANDICAP_LABEL(t);
  const terms = resolveGameTerms(rules, handicapKey, freeKomi);
  const ruleDef = RULES.find((r) => r.key === rules) ?? RULES[0];
  const pickKomi = handicapKey === 'free';
  const freeKomiOptions = FREE_KOMI_VALUES.map((v) => ({
    key: String(v),
    label: interpolate(t('setup:komi_points', '{n} 目'), { n: v }),
  }));
  const seatHint = playInput.available
    ? t('local:seat_hint_ready', '钟在玩家卡上倒数 · 读秒用完判超时负 · 不限时就只记谱')
    : playInput.reason === 'notNineteen'
      ? t('setup:seat_hint_not19', '这一局不是 19 路,只能下在屏幕上')
      : t('setup:seat_hint_uncalibrated', '这台机器没标定过摄像头,只能下在屏幕上');

  const handleStart = async () => {
    setError('');
    setLoading(true);
    try {
      localStorage.setItem('kioskPlaySound', confirmSound ? '1' : '0');
      const { session_id } = await API.createSession(token ?? undefined);
      await API.gameSetup(session_id, 'pvp_local', {
        board_size: boardSize,
        rules: ruleDef.wire,
        handicap: terms.handicap,
        komi: terms.komi,
        black_name: blackName,
        white_name: whiteName,
        time_enabled: timeEnabled,
        main_time: mainTime,
        byo_length: byoyomiTime,
        byo_periods: byoyomiPeriods,
      });
      writeActiveSession({
        kind: 'game',
        // 铸的是新键,不套 PO 里的 `Black` / `White` —— 那两条是「黑棋 / 白棋」(说的是子),
        // 这里说的是**人**(黑方 / 白方),和对局屏上那两张卡的回落值是同一句话。
        label: `${blackName || t('setup:black_side', '黑方')} vs ${whiteName || t('setup:white_side', '白方')}`,
        route: `/kiosk/play/pvp/local/game/${session_id}`,
        ts: Date.now(),
      });
      navigate(`/kiosk/play/pvp/local/game/${session_id}`);
    } catch (e) {
      setError(e instanceof Error ? e.message : t('Failed to create game', '创建对局失败'));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="kiosk-layout-a" data-testid="pvp-local-setup-page">
      {/* 左栏 = 按下「开始对局」后真会出现的那个局面(规范 `:512`)。
          `color` 不传:这一屏没有「我执」那一次选择,见 `KioskSetupBoard` 的 prop 注释。 */}
      <KioskSetupBoard size={boardSize} handicap={terms.handicap} />

      {/* `data-su`:紧排 + 给弹层当定位原点。见 `components/setup/SetupPopoverHost.tsx`。 */}
      <div className="kiosk-rail" data-su="local" ref={setRailEl}>
        <SetupPopoverHost.Provider value={railEl}>
        <KioskPagebar
          testId="kiosk-setup-pagebar"
          backLabel={t('Back to play', '返回对弈')}
          onBack={() => navigate('/kiosk/play')}
          title={t('game:local_pvp', '本地对局')}
          sub={t('local:setup_sub', '开局设置 · 两人面对面')}
        />

        <KioskScrollZone className="setgrp-scroll">
          {/* ── 这局棋 ── 和屏 02 同一副件、同一份模型(`utils/setupOptions.ts`)。
              两个人面对面下,**终局怎么算是开局前必须谈好的事** —— 所以贴目在这一屏
              尤其要说得出口,而不是藏在一条轨的读数里。 */}
          <section className="setgrp" data-testid="setup-game-group">
            <KioskSecLabel
              zh={t('setup:game_terms', '这局棋')}
              en="Game"
              value={t('local:agree_first', '下之前先谈好')}
            />
            <div className="su-row">
              <SetupSelect
                testId="setup-size"
                label={t('setup:size', '路数')}
                value={String(boardSize)}
                options={[19, 13, 9].map((n) => ({
                  key: String(n),
                  label: interpolate(t('setup:size_n', '{n} 路'), { n }),
                }))}
                onChange={(k) => pickSize(Number(k))}
              />
              <SetupSelect
                testId="setup-rules"
                label={t('Rules', '规则')}
                value={rules}
                options={RULES.map((r) => ({ key: r.key, label: ruleLabels[r.key] }))}
                onChange={pickRules}
              />
              <SetupSelect
                testId="setup-handicap"
                label={t('Handicap', '让子')}
                value={handicapKey}
                columns={2}
                options={handicapKeysFor(boardSize, rules).map((k) => ({ key: k, label: handicapLabels[k] }))}
                onChange={(k) => setHandicapKey(k as HandicapKey)}
              />
            </div>
            <SetupDerived
              testId="setup-komi"
              label={t('Komi', '贴目')}
              note={pickKomi
                ? t('setup:komi_pick', '点此改贴目')
                : t('setup:komi_derived', '随规则和让子定')}
              options={pickKomi ? freeKomiOptions : undefined}
              value={String(freeKomi)}
              onChange={pickKomi ? (k) => setFreeKomi(Number(k)) : undefined}
            >
              {komiReadout(t, rules, handicapKey, freeKomi)}
            </SetupDerived>
          </section>

          {/* ── 对局双方 ── 压成一行两格。它是两个同类输入,不是两条并列的内容。
              留空就不写 SGF 的 PB/PW(`server.py:1093`),对局屏回落到「黑方 / 白方」。 */}
          <section className="setgrp" data-testid="setup-players-group">
            <KioskSecLabel
              zh={t('local:players', '对局双方')}
              en="Players"
              value={t('local:written_into_sgf', '会写进棋谱')}
            />
            <div className="su-row su-row--2">
              <label className="su-cell su-cell--input">
                <span className="su-cell__k">
                  <span className="disc b" /> {t('setup:black_side', '黑方')} · {t('local:black_role_short', '先行')}
                </span>
                <input
                  className="su-cell__v su-nameinput"
                  data-testid="black-name-input"
                  aria-label={t('local:black_name', '黑方姓名')}
                  placeholder={t('local:tap_to_type', '点此输入')}
                  maxLength={16}
                  value={blackName}
                  onChange={(e) => setBlackName(e.target.value)}
                />
              </label>
              <label className="su-cell su-cell--input">
                {/* 稿子这一行写的是「贴目的一方」—— **反了**:贴目是黑方贴给白方的
                    (`core/game.py:372` 黑棋分数减 komi),白方是**收**的那一方。 */}
                <span className="su-cell__k">
                  <span className="disc w" /> {t('setup:white_side', '白方')} · {t('local:white_role_short', '后行')}
                </span>
                <input
                  className="su-cell__v su-nameinput"
                  data-testid="white-name-input"
                  aria-label={t('local:white_name', '白方姓名')}
                  placeholder={t('local:tap_to_type', '点此输入')}
                  maxLength={16}
                  value={whiteName}
                  onChange={(e) => setWhiteName(e.target.value)}
                />
              </label>
            </div>
            <p className="su-hint">{t('local:names_hint', '留空就记成「黑方 / 白方」,不编名字')}</p>
          </section>

          {/* ── 怎么坐 ── 这一屏没有「我执」:两个人面对面,谁执黑是他们自己坐好的。
              空出来的那一格给落子提示音 —— 它是这一局的开关,和用时同级。 */}
          <section className="setgrp" data-testid="setup-seat-group">
            <KioskSecLabel zh={t('setup:seat', '怎么坐')} en="Seat" />
            <div className="su-row">
              <SetupSelect
                testId="setup-input"
                label={t('setup:input_where', '落子')}
                value={playInput.onBoard ? 'board' : 'screen'}
                options={[
                  { key: 'screen', label: t('setup:on_screen', '屏幕') },
                  {
                    key: 'board',
                    label: t('setup:on_board', '实体盘'),
                    disabled: !playInput.available,
                    reason: playInput.reason === 'notNineteen'
                      ? t('setup:board_only_19', '盘上那块是 19 路')
                      : t('setup:board_not_ready', '没标定过摄像头'),
                  },
                ]}
                onChange={(k) => setPlayOnBoard(k === 'board')}
              />
              <SetupSelect
                testId="setup-clock"
                label={t('Time Control', '用时')}
                value={currentTimeKey}
                columns={2}
                options={timeTrack.map((p) => ({ key: p.key, label: p.label }))}
                onChange={applyTimePreset}
              />
              <SetupSelect
                testId="setup-sound"
                label={t('local:move_sound_short', '落子音')}
                value={confirmSound ? 'on' : 'off'}
                options={[
                  { key: 'on', label: t('On', '开') },
                  { key: 'off', label: t('Off', '关') },
                ]}
                onChange={(k) => setConfirmSound(k === 'on')}
              />
            </div>
            <p className="su-hint" data-testid="setup-seat-hint">{seatHint}</p>
          </section>
        </KioskScrollZone>

        {/* 出错横幅在滚动区**外面** —— 它说的是「刚才那次开局失败了」,跟着设置滚走就等于没说。 */}
        {error && <Alert severity="error" sx={{ mb: 1 }}>{error}</Alert>}

        <p className="setnote" data-testid="setup-note">
          {t('local:note_a', '这一边')}
          <b>{t('local:note_b', '没有引擎对手')}</b>
          {t('local:note_c', ':AI 支招关着、不画胜负走势,')}
          <b>{t('local:note_d', '终局死活两人自己确认')}</b>
          {t('local:note_e', '。')}
          <br />
          {t('local:note_f', '这一局')}
          <b>{t('local:note_g', '只留档,不动段位')}</b>
          {t('local:note_h', '——段位只由「升降级对弈」那条阶梯决定。')}
        </p>

        <button
          type="button"
          className="kiosk-primary-action"
          data-testid="local-start-action"
          disabled={loading}
          onClick={handleStart}
        >
          {loading ? t('Creating...', '创建中...') : t('setup:start', '开始对局')}
        </button>
        </SetupPopoverHost.Provider>
      </div>
    </div>
  );
};

export default PvpLocalSetupPage;
