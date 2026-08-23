import { useState } from 'react';
import { Alert } from '@mui/material';
import { useNavigate } from 'react-router-dom';
import { useVision } from '../context/VisionContext';
import { KioskOptSeg } from '../shell/KioskOptSeg';
import { KioskPagebar } from '../shell/KioskPagebar';
import { KioskScrollZone } from '../shell/KioskScrollZone';
import { KioskSecLabel } from '../shell/KioskSecLabel';
import { KioskStepTrack } from '../shell/KioskStepTrack';
import KioskSetupBoard from '../components/board/KioskSetupBoard';
import OptionChips from '../components/common/OptionChips';
import { interpolate } from '../utils/interpolate';
import { RULES_HINT, TIME_PRESETS, TIME_TRACK_ORDER } from '../utils/setupOptions';
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
 * ## 「怎么落子」那一组:读数,不是设置项(同屏 02)
 *
 * `isVisionEnabled` 由后端 `/api/v1/vision/status` 给,全仓没有任何地方能让用户切它。
 * 这一屏尤其不能画成可选:本地对局那条路由外面套着
 * `<PhysicalBoardGuard requireRecognition>`,盘没标定过时进去的是标定工作台,
 * 不是对局 —— 屏上摆一个「实体盘 / 屏幕」的开关,等于让人以为自己选得了。
 */
const PvpLocalSetupPage = () => {
  const navigate = useNavigate();
  const { t } = useTranslation();
  const { token } = useAuth();
  const { isVisionEnabled } = useVision();

  // Board & rules
  const [boardSize, setBoardSize] = useState(19);
  const [rules, setRules] = useState<'chinese' | 'japanese' | 'korean' | 'aga'>('chinese');

  // Player names — 留空就不写 SGF 的 PB/PW(`server.py:1093`),对局屏回落到「黑方 / 白方」
  // (`GameControlPanel.tsx:66`)。**不替用户编一个名字。**
  const [blackName, setBlackName] = useState('');
  const [whiteName, setWhiteName] = useState('');

  // Handicap & komi
  const [handicap, setHandicap] = useState(0);
  const [komi, setKomi] = useState(6.5);

  // Time control
  const [timeEnabled, setTimeEnabled] = useState(false);
  const [mainTime, setMainTime] = useState(0);
  const [byoyomiTime, setByoyomiTime] = useState(30);
  const [byoyomiPeriods, setByoyomiPeriods] = useState(3);

  // Move sound — client-side preference, persisted in localStorage (shared useGameSession.playSound reads it)
  const [confirmSound, setConfirmSound] = useState(localStorage.getItem('kioskPlaySound') !== '0');

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const timePresets = TIME_PRESETS(t);
  const currentTimeKey = !timeEnabled ? 'untimed' : mainTime === 0 ? 'byoOnly' : String(mainTime);
  const timeTrack = [...TIME_TRACK_ORDER].map((key) => timePresets.find((p) => p.key === key)!);
  const timeIndex = Math.max(0, timeTrack.findIndex((p) => p.key === currentTimeKey));
  const applyTimePreset = (key: string) => {
    const preset = timePresets.find((p) => p.key === key);
    if (!preset) return;
    setTimeEnabled(preset.enabled);
    setMainTime(preset.main);
    setByoyomiTime(preset.byo);
    setByoyomiPeriods(preset.periods);
  };

  // 贴目 15 档(0.5 – 7.5,半目一档)—— 和屏 02 同一条轨、同一份档,理由写在那一屏。
  const KOMI_MIN = 0.5;
  const KOMI_STEP = 0.5;
  const komiIndex = Math.round((komi - KOMI_MIN) / KOMI_STEP);

  const onPhysicalBoard = isVisionEnabled;

  const handleStart = async () => {
    setError('');
    setLoading(true);
    try {
      localStorage.setItem('kioskPlaySound', confirmSound ? '1' : '0');
      const { session_id } = await API.createSession(token ?? undefined);
      await API.gameSetup(session_id, 'pvp_local', {
        board_size: boardSize,
        rules,
        handicap,
        komi,
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
      <KioskSetupBoard size={boardSize} handicap={handicap} />

      <div className="kiosk-rail">
        <KioskPagebar
          testId="kiosk-setup-pagebar"
          backLabel={t('Back to play', '返回对弈')}
          onBack={() => navigate('/kiosk/play')}
          title={t('game:local_pvp', '本地对局')}
          sub={t('local:setup_sub', '开局设置 · 两人面对面')}
        />

        <KioskScrollZone className="setgrp-scroll">
          {/* ── 怎么落子 ── 开局后不可改的那一组,自带强调框 */}
          <section className="setgrp inputgrp" data-testid="setup-input-group">
            <KioskSecLabel
              zh={t('setup:input', '怎么落子')}
              en="Input"
              value={t('setup:locked_after_start', '开局后不可改')}
            />
            <div className="igrow">
              <span className="iglab">{t('setup:input_where', '落子')}</span>
              <span className="igfix" data-testid="setup-input-readout">
                <b>{onPhysicalBoard ? t('setup:on_board', '实体盘') : t('setup:on_screen', '屏幕')}</b>
                {onPhysicalBoard
                  ? t('setup:on_board_hint', '摄像头已标定,落子直接下在盘上')
                  : t('setup:on_screen_hint', '这台机器没有标定过摄像头')}
              </span>
            </div>
            <div className="igrow">
              <span className="iglab">{t('setup:size', '路数')}</span>
              <KioskOptSeg
                ariaLabel={t('setup:size', '路数')}
                testId="setup-size"
                value={boardSize}
                onChange={setBoardSize}
                options={[
                  { value: 19, label: t('19x19', '19 路') },
                  { value: 13, label: t('13x13', '13 路') },
                  { value: 9, label: t('9x9', '9 路') },
                ]}
              />
            </div>
            <p className="kiosk-opthint">
              {onPhysicalBoard
                ? t('local:input_hint_board', '两人面对面下在这块盘上,屏幕只记谱和读秒;9 路和 13 路只有屏幕上有')
                : t('setup:size_hint', '9 路和 13 路只有屏幕上有 —— 盘上那块是 19 路')}
            </p>
          </section>

          {/* ── 对局双方 ── 稿子那两颗「点此输入」药丸,在真页面上必须**真能输入** */}
          <section className="setgrp" data-testid="setup-players-group">
            <KioskSecLabel
              zh={t('local:players', '对局双方')}
              en="Players"
              value={t('local:written_into_sgf', '会写进棋谱')}
            />
            <div className="kiosk-rows">
              <div className="kiosk-row">
                <span className="disc b" />
                <div className="kiosk-row__t">
                  <b>{t('setup:black_side', '黑方')}</b>
                  <em>{t('local:black_role', '先行 · 让子局里摆子的一方')}</em>
                </div>
                <div className="kiosk-row__end">
                  <input
                    className="nameinput"
                    data-testid="black-name-input"
                    aria-label={t('local:black_name', '黑方姓名')}
                    placeholder={t('local:tap_to_type', '点此输入')}
                    maxLength={16}
                    value={blackName}
                    onChange={(e) => setBlackName(e.target.value)}
                  />
                </div>
              </div>
              <div className="kiosk-row">
                <span className="disc w" />
                <div className="kiosk-row__t">
                  <b>{t('setup:white_side', '白方')}</b>
                  {/* 稿子这一行写的是「贴目的一方」—— **反了**:贴目是黑方贴给白方的
                      (`core/game.py:372` 黑棋分数减 komi),白方是**收**的那一方。 */}
                  <em>{t('local:white_role', '后行 · 收下贴目的一方')}</em>
                </div>
                <div className="kiosk-row__end">
                  <input
                    className="nameinput"
                    data-testid="white-name-input"
                    aria-label={t('local:white_name', '白方姓名')}
                    placeholder={t('local:tap_to_type', '点此输入')}
                    maxLength={16}
                    value={whiteName}
                    onChange={(e) => setWhiteName(e.target.value)}
                  />
                </div>
              </div>
            </div>
            <p className="kiosk-opthint">
              {t('local:names_hint', '留空就记成「黑方 / 白方」,不编名字')}
            </p>
          </section>

          <section className="setgrp">
            <OptionChips
              label={t('Rules', '规则')}
              en="Rules"
              testId="setup-rules"
              secval={t('local:agree_first', '下之前先谈好')}
              value={rules}
              onChange={setRules}
              options={[
                { value: 'chinese' as const, label: t('Chinese', '中国') },
                { value: 'japanese' as const, label: t('Japanese', '日本') },
                { value: 'korean' as const, label: t('Korean', '韩国') },
                { value: 'aga' as const, label: 'AGA' },
              ]}
              hint={RULES_HINT(t)[rules] ?? ''}
            />
          </section>

          <section className="setgrp" data-testid="setup-handicap-group">
            <KioskStepTrack
              label={t('Handicap', '让子')}
              en="Handicap"
              testId="setup-handicap"
              count={10}
              index={handicap}
              onChange={setHandicap}
              decLabel={t('setup:handicap_down', '少让一子')}
              incLabel={t('setup:handicap_up', '多让一子')}
              value={handicap === 0
                ? t('setup:no_handicap', '不让子')
                : interpolate(t('setup:handicap_value', '让 {n} 子'), { n: handicap })}
              meta={t('local:handicap_meta', '0 – 9 子 · 两人棋力差时用')}
            />
          </section>

          <section className="setgrp" data-testid="setup-komi-group">
            <KioskSecLabel
              zh={t('Komi', '贴目')}
              en="Komi"
              value={handicap > 0 ? t('setup:not_applicable', '本局不适用') : undefined}
            />
            {handicap > 0 ? (
              <p className="setexplain" data-testid="setup-komi-explain">
                {interpolate(
                  t('setup:komi_explain', '已经让了 {n} 子,这一局不贴目。让子和贴目是同一件事的两种做法——补的都是先行那一方的便宜,两样一起用会补两遍。'),
                  { n: handicap },
                )}
                <br />
                {t('setup:komi_explain_back', '把让子调回 0,这一组会变回可选的贴目档。')}
              </p>
            ) : (
              <KioskStepTrack
                testId="setup-komi"
                count={15}
                index={komiIndex}
                onChange={(i) => setKomi(KOMI_MIN + i * KOMI_STEP)}
                decLabel={t('setup:komi_down', '减少贴目')}
                incLabel={t('setup:komi_up', '增加贴目')}
                value={interpolate(t('setup:komi_value', '贴 {n} 目'), { n: komi })}
                meta={t('setup:komi_meta', '0.5 – 7.5 · 中国规则常用 7.5')}
              />
            )}
          </section>

          <section className="setgrp" data-testid="setup-clock-group">
            <KioskStepTrack
              label={t('Time Control', '用时')}
              en="Clock"
              testId="setup-clock"
              count={timeTrack.length}
              index={timeIndex}
              onChange={(i) => applyTimePreset(timeTrack[i].key)}
              decLabel={t('setup:clock_down', '减少用时')}
              incLabel={t('setup:clock_up', '增加用时')}
              value={timeTrack[timeIndex]?.label ?? '—'}
              meta={interpolate(t('local:clock_meta', '{n} 档 · 两边同一套用时'), { n: timeTrack.length })}
              hint={t('local:clock_hint', '走完一步换对方的钟;不限时就只记谱不读秒')}
            />
          </section>

          <section className="setgrp" data-testid="setup-sound-group">
            <OptionChips
              label={t('local:move_sound', '落子提示音')}
              en="Sound"
              testId="setup-sound"
              value={confirmSound ? 'on' : 'off'}
              onChange={(v) => setConfirmSound(v === 'on')}
              options={[
                { value: 'on', label: t('local:sound_on', '开') },
                { value: 'off', label: t('local:sound_off', '关') },
              ]}
              hint={t('local:sound_hint', '实体盘上落子后,屏幕出一声确认它已经认到了')}
            />
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
      </div>
    </div>
  );
};

export default PvpLocalSetupPage;
