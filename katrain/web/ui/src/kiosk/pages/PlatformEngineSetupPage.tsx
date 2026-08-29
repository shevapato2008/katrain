import { useEffect, useMemo, useState } from 'react';
import { Alert } from '@mui/material';
import { useNavigate, useParams } from 'react-router-dom';
import { API, type EngineLevel } from '../../api';
import { useTranslation } from '../../hooks/useTranslation';
import { useAuth } from '../../context/AuthContext';
import { useVision } from '../context/VisionContext';
import { KioskOptSeg } from '../shell/KioskOptSeg';
import { KioskPagebar } from '../shell/KioskPagebar';
import { KioskScrollZone } from '../shell/KioskScrollZone';
import { KioskSecLabel } from '../shell/KioskSecLabel';
import { KioskStepTrack } from '../shell/KioskStepTrack';
import KioskSetupBoard from '../components/board/KioskSetupBoard';
import { PLATFORM_META } from '../constants/platforms';
import { interpolate } from '../utils/interpolate';
import { playInputState, writePlayOnBoard } from '../utils/playInput';

/**
 * 屏 09 跨平台 · 人机开局(`sample-go/shots/09-platform-engine.png`,L2 布局 A)。
 *
 * 星阵 `supports_engine_play`,所以屏 07 上它那张卡进的是这一屏而不是大厅 ——
 * 星阵能给的对手是那 39 档 bot,不是人(它的 `get_online_users` 直接 `return []`)。
 *
 * **和「自由对弈 · 开局设置」(屏 02)同一副骨架**(左盘 516 + 16 + 右栏 460,右栏整栏滚,
 * 主行动键钉栏底),但配的是**别人家的引擎**:
 *
 * · **棋力档由那边下发** —— `API.platformEngineLevels` 拉的是 `GOLAXY_AI_LEVELS`
 *   那 39 档(星猛虎 / 星壮牛 / 星皮猴 …,每档带 `level_name` / `display_elo` / `ref_rank`)。
 *   **加载失败就是加载失败**,不给一份写死的兜底表 —— 那会让人选中一个星阵不认识的档。
 * · **让子和贴目是联动的**,贴目不是第二个可选项:分先→黑贴 7.5,让先→贴 0,让 N 子→黑贴 N 子
 *   (`app.js` 的口径)。所以「这一局会是」那一行写的是**算出来的结果**。
 * · **不计时**:星阵这条链不带钟。
 *
 * ## ⚠️ 稿子画的那段「39 档名单」**不做**(2026-08-24 裁定)
 *
 * 稿子在步进器**下面**还摊开了一段 `.rows`(名字 / 展示 Elo / 对标棋力 / 「选它」)。
 * 不照做,三条理由,每条都能落到仓里一条已经落过锤的判例或一个量出来的数上:
 *
 * ① **规范逐字禁掉了这一处。** 共享 `tokens.css` 在 `.kiosk-optseg` 上面写着:
 *    「一屏里所有选择组必须用同一种控件,**不许难度用列表**、执棋方用宫格、时间用 2×2 ——
 *    那是一屏三套选择手势」。这一屏的选择组是 落子 / 对手 / 让子 / 我执;同为**有序档**的
 *    让子只有步进器,给对手再加一段带「选它」的列表,屏内自相矛盾。
 * ② **屏 02 的 29 档已经按同一条判过。** `KioskStepTrack` 的文件头写着为什么不是下拉、
 *    不是分段:7″ 触屏上下拉要点两次,而弹层正好盖住左边那块盘。39 档同理。
 * ③ **摊开之后装不下。** 真浏览器量:39×52 + 38×8 ⇒ 那一段 390 高,而滚动视口只有 400 ——
 *    一段吃掉 97.5% 的视口,右栏 maxScroll 2627 ≈ 6.6 屏。
 *
 * **不掉功能**:39 个值一个不少、全都走得到。删的是**控件**不是**值** ——
 * 这条 track 自己的定义在 `AiSetupPage`:「把 15 档收成 3 档是删功能,不是重画」。
 * 名单上唯一不在步进器上的那一列(`ref_rank`)已经并进 `.catmeta`。
 *
 * ## 这一版改掉的三样
 *
 * ① **那块自己画的 300px `<svg>` 棋盘预览没了**,换成共享的 `KioskSetupBoard` ——
 *    布局 A 的左栏是 516 的真盘,四棋类同一套刻度带与木框;原来那块是这一屏自己发明的。
 * ② **两个 MUI `Menu` 下拉换成档位轨**(`KioskStepTrack`)。理由和屏 02 一样:
 *    7″ 触屏上下拉要点两次才看得见选项,而弹层正好盖住左边那块盘 —— 那块盘画的就是
 *    「按下开始之后会出现的局面」,调让子时它是唯一的反馈。
 * ③ **补上「怎么落子」那颗开关**。屏 02/03/04 已经接了(`utils/playInput`),
 *    这一屏之前漏了 —— 于是同一台盒子上,自由对弈选得了屏幕,跨平台却选不了。
 *    这一屏路数恒 19(星阵只开 19 路),所以 `notNineteen` 那一条永远不成立。
 */

/** 让子 10 挡:分先 / 让先 / 让 2 – 让 9 子。**两头禁用不回绕** —— 见 `KioskStepTrack`。 */
const HANDICAP_TRACK = [0, -1, 2, 3, 4, 5, 6, 7, 8, 9] as const;

const PlatformEngineSetupPage = () => {
  const { platform = 'golaxy' } = useParams<{ platform: string }>();
  const navigate = useNavigate();
  const { t } = useTranslation();
  const { token } = useAuth();
  const { isVisionEnabled } = useVision();
  const meta = PLATFORM_META[platform] ?? { label: platform, labelCn: platform, color: '#888' };

  const [levels, setLevels] = useState<EngineLevel[]>([]);
  const [levelsLoading, setLevelsLoading] = useState(true);
  // ⚠️ `null` = 没失败;`''` = 失败了但服务端没给话。**存的不是译文** ——
  // `useTranslation()` 的 `t` 每次渲染都是新函数,把它放进 effect 依赖,这个 effect
  // 每帧重跑一次(屏 06 刚栽过同一个:`networkidle` 永远等不到)。
  const [levelsError, setLevelsError] = useState<string | null>(null);
  const [level, setLevel] = useState<number | null>(null);
  const [handicapIdx, setHandicapIdx] = useState(0);
  const [humanColor, setHumanColor] = useState<'B' | 'W' | 'nigiri'>('nigiri');
  const [starting, setStarting] = useState(false);
  const [startError, setStartError] = useState('');

  const handicap = HANDICAP_TRACK[handicapIdx];

  useEffect(() => {
    let cancelled = false;
    if (!platform || !token) return () => { cancelled = true; };
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
        if (!cancelled) setLevelsError(e instanceof Error ? e.message : '');
      })
      .finally(() => { if (!cancelled) setLevelsLoading(false); });
    return () => { cancelled = true; };
  }, [platform, token]);

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

  const handicapLabel = handicap === 0 ? t('setup:even', '分先')
    : handicap === -1 ? t('platform:black_first', '让先')
      : interpolate(t('setup:handicap_n', '让 {n} 子'), { n: handicap });
  const komiLabel = handicap === 0 ? t('platform:komi_75', '黑贴 7.5 目')
    : handicap === -1 ? t('platform:komi_0', '不贴目')
      : interpolate(t('platform:komi_n', '黑贴 {n} 子'), { n: handicap });
  const colorLabel = humanColor === 'nigiri' ? t('platform:nigiri', '猜先')
    : humanColor === 'B' ? t('setup:take_black', '执黑') : t('setup:take_white', '执白');

  const start = async () => {
    if (!token || level === null) return;
    setStartError('');
    setStarting(true);
    try {
      const { session_id } = await API.platformEngineStart(
        platform, { level, human_color: humanColor, handicap }, token,
      );
      navigate(`/kiosk/play/cross-platform/engine/game/${session_id}`);
    } catch (e) {
      setStartError(e instanceof Error ? e.message : t('Failed to start game', '创建对局失败'));
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

      <div className="kiosk-rail">
        <KioskPagebar
          testId="platform-engine-pagebar"
          backLabel={t('platform:back_to_platforms', '跨平台')}
          onBack={() => navigate('/kiosk/play/cross-platform')}
          title={interpolate(t('platform:engine_title', '{name} · 人机'), { name: t(meta.label, meta.labelCn) })}
          sub={t('platform:engine_sub', '开局设置 · 不计入盒内段位')}
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
              <KioskOptSeg
                ariaLabel={t('setup:input_where', '落子')}
                testId="setup-input"
                value={playInput.onBoard ? 'board' : 'screen'}
                onChange={(v) => { writePlayOnBoard(v === 'board'); setInputTick((n) => n + 1); }}
                options={[
                  { value: 'screen', label: t('setup:on_screen', '屏幕') },
                  { value: 'board', label: t('setup:on_board', '实体盘'), disabled: !playInput.available },
                ]}
              />
            </div>
            <div className="igrow">
              <span className="iglab">{t('setup:size', '路数')}</span>
              {/* 读数不是控件:星阵只开 19 路,画成一格可选的分段等于承诺一个不存在的选项。 */}
              <span className="igfix" data-testid="setup-size-fixed">
                <b>{t('19x19', '19 路')}</b>
                {interpolate(t('platform:only_19', '{name}只开 19 路 · 中国规则'), { name: t(meta.label, meta.labelCn) })}
              </span>
            </div>
            {!playInput.available && (
              <p className="kiosk-opthint">
                {t('setup:no_camera_hint', '这台盒子还没标定摄像头，实体盘这条路现在走不了')}
              </p>
            )}
          </section>

          {/* ── 对手 ── 39 档由平台下发 */}
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
                <KioskStepTrack
                  label={t('platform:opponent', '对手')}
                  en="Opponent"
                  secval={interpolate(
                    t('platform:levels_from', '{name}下发 {n} 档'),
                    { name: t(meta.label, meta.labelCn), n: sorted.length },
                  )}
                  count={sorted.length}
                  index={Math.max(0, currentIdx)}
                  onChange={(i) => setLevel(sorted[i].elo_score)}
                  value={current ? `${current.name} · ${current.level_name}` : ''}
                  meta={current ? (
                    <>
                      {interpolate(t('platform:rung_n', '第 {i} / {n} 档'), { i: currentIdx + 1, n: sorted.length })}
                      {' · '}
                      <b>{interpolate(t('platform:display_elo', '展示 Elo {v}'), { v: current.display_elo })}</b>
                      {/* `ref_rank` 是那份名单里**唯一不在步进器上的一列** —— 顶上六档是
                          「野狐 9D」「职业 / 野狐 9D+」,掉了就是掉事实。名单不做了,它得搬到这儿。 */}
                      {current.ref_rank ? <> · {interpolate(t('platform:ref_rank', '对标{r}'), { r: current.ref_rank })}</> : null}
                    </>
                  ) : undefined}
                  decLabel={t('platform:weaker', '换弱一档的对手')}
                  incLabel={t('platform:stronger', '换强一档的对手')}
                  testId="setup-level"
                />
              </>
            )}
          </section>

          {/* ── 让子 ── */}
          <section className="setgrp" data-testid="setup-handicap">
            <KioskStepTrack
              label={t('setup:handicap', '让子')}
              en="Handicap"
              count={HANDICAP_TRACK.length}
              index={handicapIdx}
              onChange={setHandicapIdx}
              value={handicapLabel}
              meta={interpolate(
                t('platform:handicap_range', '{n} 挡 · 分先 / 让先 / 让 2 – 让 9 子'),
                { n: HANDICAP_TRACK.length },
              )}
              decLabel={t('setup:handicap_less', '少让一子')}
              incLabel={t('setup:handicap_more', '多让一子')}
              testId="setup-handicap-track"
            />
          </section>

          {/* ── 我执 ── 顺序照实现:猜先 / 执黑 / 执白 */}
          <section className="setgrp" data-testid="setup-side">
            <KioskSecLabel zh={t('setup:my_side', '我执')} en="Side" />
            <KioskOptSeg
              ariaLabel={t('setup:my_side', '我执')}
              testId="setup-side-seg"
              value={humanColor}
              onChange={setHumanColor}
              options={[
                { value: 'nigiri', label: <><span className="disc rnd" />{t('platform:nigiri', '猜先')}</> },
                { value: 'B', label: <><span className="disc b" />{t('setup:take_black', '执黑')}</> },
                { value: 'W', label: <><span className="disc w" />{t('setup:take_white', '执白')}</> },
              ]}
            />
          </section>

          {/* ── 这一局会是 ── 贴目跟着让子算,不是另一个可选项 */}
          <section className="setgrp" data-testid="setup-summary">
            <KioskSecLabel zh={t('setup:this_game', '这一局会是')} en="Result" />
            <p className="setexplain" data-testid="setup-summary-line">
              <b>
                {t('setup:chinese_rules', '中国规则')} · {handicapLabel} · {komiLabel} · {t('19x19', '19 路')}
                {' · '}{t('platform:untimed', '不计时')} · {colorLabel}
              </b>
              <br />
              {interpolate(
                t('platform:summary_note', '贴目跟着让子算，不是另一个可选项；胜负只进{name}那边的账。'),
                { name: t(meta.label, meta.labelCn) },
              )}
            </p>
          </section>
        </KioskScrollZone>

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
      </div>
    </div>
  );
};

export default PlatformEngineSetupPage;
