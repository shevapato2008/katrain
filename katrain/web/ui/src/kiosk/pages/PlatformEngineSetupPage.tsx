import { useEffect, useMemo, useState } from 'react';
import { Alert } from '@mui/material';
import { useNavigate, useParams, useLocation } from 'react-router-dom';
import { backToState } from '../hooks/useBackTo';
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
import AiOpponentPlate from '../components/setup/AiOpponentPlate';
import AiLevelSheet from '../components/setup/AiLevelSheet';
import { PLATFORM_META } from '../constants/platforms';
import { interpolate } from '../utils/interpolate';
import { platformErrorMessage } from '../utils/platformErrorMessage';
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
 *   (`app.js` 的口径)。「让子 · 我执」那一组的读数写的是**算出来的结果**,不是第二个控件。
 * · **不计时**:星阵这条链不带钟。
 *
 * ## 39 档怎么选:常驻的是步进器,全表是名牌点开的瞬态面板
 *
 * 稿子在步进器**下面**还摊开过一段常驻的 `.rows`(名字 / 展示 Elo / 对标棋力 / 「选它」)。
 * 那种**常驻**列表没有做,理由仍然成立、没有过期:
 *
 * ① **一屏一种选择手势。** 这一屏的选择组是 落子 / 对手 / 让子 / 我执;同为**有序档**的
 *    让子只有步进器,常驻对手再摊开一段带「选它」的列表,屏内自相矛盾。
 * ② **屏 02 的 29 档已经按同一条判过。** `KioskStepTrack` 的文件头写着为什么不是下拉:
 *    7″ 触屏上下拉要点两次才看得见选项。
 * ③ **摊开之后装不下。** 真浏览器量:39×52 + 38×8 ⇒ 那一段 390 高,而滚动视口只有 400 ——
 *    一段吃掉 97.5% 的视口,右栏 maxScroll 2627 ≈ 6.6 屏。
 *
 * 但 39 个值一个不少、全都走得到:`AiLevelSheet` 是名牌(`AiOpponentPlate`)点开才挂载的
 * 全表,`position:absolute` 相对 `.kiosk-rail`——**不盖左边那块盘**,关掉不留痕迹,不是
 * 「删掉又加回来」而是常驻列表和瞬态面板从一开始就是两件事。它能放行的原因是**手指跨不动
 * 那条轨**:39 档的 `KioskStepTrack` 每档约 8px,「换一档」按钮只能挪到相邻档,隔着十几档
 * 想跳过去只能长按连发;名牌点开是唯一能一步跳到任意一档的路。共享 `tokens.css` 已经在
 * `.kiosk-optseg` 规范上加了这条例外(2026-09-23),不再是这一屏单独违规。
 * `ref_rank`(名单上唯一不在步进器上的那一列)现在显示在名牌上(`AiOpponentPlate`),
 * 不在 `KioskStepTrack` 自带的 `.catmeta` 读数里 ——`readout={false}` 关掉了后者。
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
  const [handicapIdx, setHandicapIdx] = useState(0);
  const [humanColor, setHumanColor] = useState<'B' | 'W' | 'nigiri'>('nigiri');
  const [starting, setStarting] = useState(false);
  const [startError, setStartError] = useState('');
  const [sheetOpen, setSheetOpen] = useState(false);

  const handicap = HANDICAP_TRACK[handicapIdx];

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

  const handicapLabel = handicap === 0 ? t('setup:even', '分先')
    : handicap === -1 ? t('platform:black_first', '让先')
      : interpolate(t('setup:handicap_n', '让 {n} 子'), { n: handicap });
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
      navigate(`/kiosk/play/cross-platform/engine/game/${session_id}`, { state: backToState(location) });
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

      <div className="kiosk-rail">
        <KioskPagebar
          testId="platform-engine-pagebar"
          backLabel={t('platform:back_to_platforms', '跨平台')}
          onBack={() => navigate('/kiosk/play/cross-platform')}
          title={interpolate(t('platform:engine_title', '{name} · 人机'), { name: t(meta.label, meta.labelCn) })}
          sub={t('platform:engine_sub', '开局设置 · 不计入盒内段位')}
        />

        <KioskScrollZone className="setgrp-scroll">
          {/* ── 怎么落子 ── 开局后不可改的那一组,自带强调框。路数不占一行了:
              星阵只开 19 路,那句事实降进了提示行的半句(见下)。 */}
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
            {/* 路数不是控件也不占一行:星阵只开 19 路。这句提示同时替掉了原来
                「这一局会是」段里的规则/路数两项 —— 400px 视口装不下第五段。 */}
            <p className="kiosk-opthint" data-testid="setup-input-hint">
              {playInput.available
                ? interpolate(
                    t('platform:engine_fixed_hint', '{name}人机固定 19 路 · 中国规则，屏幕和实体盘走同一条隧道'),
                    { name: t(meta.label, meta.labelCn) },
                  )
                : t('setup:no_camera_hint', '这台盒子还没标定摄像头，实体盘这条路现在走不了')}
            </p>
          </section>

          {/* ── 对手 ── 39 档由平台下发;名牌收读数,轨只负责推档 */}
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
                <KioskStepTrack
                  count={sorted.length}
                  index={Math.max(0, currentIdx)}
                  onChange={(i) => setLevel(sorted[i].elo_score)}
                  value=""
                  readout={false}
                  decLabel={t('platform:weaker', '换弱一档的对手')}
                  incLabel={t('platform:stronger', '换强一档的对手')}
                  testId="setup-level"
                />
              </>
            )}
          </section>

          {/* ── 让子 · 我执 ── 贴目跟着让子算,写在组标题右端,不再单占一段 ── */}
          <section className="setgrp" data-testid="setup-handicap-side">
            <KioskSecLabel
              zh={t('setup:handicap_side', '让子 · 我执')}
              en="Handicap"
              value={<>{handicapLabel} · {komiLabel}</>}
            />
            <div className="twocol">
              <div className="tcol">
                <span className="iglab">{t('setup:handicap', '让子')}</span>
                <KioskStepTrack
                  count={HANDICAP_TRACK.length}
                  index={handicapIdx}
                  onChange={setHandicapIdx}
                  value=""
                  readout={false}
                  decLabel={t('setup:handicap_less', '少让一子')}
                  incLabel={t('setup:handicap_more', '多让一子')}
                  testId="setup-handicap-track"
                />
              </div>
              <div className="tcol">
                <span className="iglab">{t('setup:my_side', '我执')}</span>
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
              </div>
            </div>
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
      </div>
    </div>
  );
};

export default PlatformEngineSetupPage;
