import { useMemo, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';

import { useLiveMatches } from '../../hooks/live/useLiveMatches';
import { useUpcomingMatches } from '../../hooks/live/useUpcomingMatches';
import { useTranslation } from '../../hooks/useTranslation';
import { liveSourceLabel } from '../../utils/liveSources';
import { translateResult } from '../../utils/resultTranslation';
import { backToState } from '../hooks/useBackTo';
import { KioskPagebar } from '../shell/KioskPagebar';
import { KioskScrollZone } from '../shell/KioskScrollZone';
import { KioskSecLabel } from '../shell/KioskSecLabel';
import { scheduleLabel } from '../utils/scheduleLabel';
import { whenLabel } from '../utils/whenLabel';

type Tab = 'live' | 'finished' | 'upcoming';

/**
 * 屏「直播列表」`/kiosk/live` —— L2 布局 B(通栏)。**稿子里没有这一屏**:
 * 它属于 Fan 2026-08-20 裁的「稿外五屏,只接壳不重排」那一组,所以这次只换壳
 * (页控条 + 分段 + 滚动区 + `.kiosk-row`),信息结构照旧是「一列比赛 + 一段赛程」。
 *
 * ## 为什么它以前等于不存在
 *
 * 全 kiosk 没有一处跳到这条路由,它自己也没有返回键、没有 Dock(L2)—— 进去出不来。
 * 棋谱屏只画前 4 行、没有「更多」,赛程只在这一页渲染。2026-09-22 补了棋谱屏的入口
 * (`KifuPage.tsx` 直播那一组末行),这一屏才真正上线。
 *
 * ## 上线前去掉的三样东西
 *
 * ① **棋盘预览**(`LiveBoard`):canvas,盒上那一族实测只有 6–15fps,而列表页不需要盘。
 * ② **胜率条**:`current_winrate` 在 pandanet 源里恒为写死的 `0.5`、xingzhen 取不到时也退回
 *    `0.5` —— 「真的均势」和「没有这个数」在库里是同一个值。屏 18 已经为同一件事裁过一次。
 * ③ **`target="_blank"` 外链**:盒上 chromium 跑 `--kiosk`,新标签页没有地址栏也没有返回键。
 *    赛程的来源改成一行字。
 *
 * ## 行首那一格只放手数
 *
 * `.kiosk-row__lead` 是 46px 的等宽格,规范给它的定义就是「23 手」。日期(`09-23 11:00`)
 * 放进去会溢出压到标题上 ⇒ 比赛行的日期进副行;赛程还没有手数,行首空着,开赛时刻进行尾。
 *
 * ## 「没有」和「读不到」是两句话
 *
 * 取数失败时说「读不到」并给重试,不说「现在没有比赛在下」—— 后者是替上游断言。
 */
const LivePage = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const { t } = useTranslation();
  const [tab, setTab] = useState<Tab>('live');

  const { matches, loading, error, refresh } = useLiveMatches({ limit: 50 });
  const { upcoming, loading: upLoading, error: upError, refresh: upRefresh } = useUpcomingMatches({ limit: 20 });

  const live = useMemo(() => matches.filter((m) => m.status === 'live'), [matches]);
  const finished = useMemo(() => matches.filter((m) => m.status !== 'live'), [matches]);
  const rows = tab === 'live' ? live : finished;
  const count = tab === 'upcoming' ? upcoming.length : rows.length;

  const failed = (testId: string, title: string, retry: () => void) => (
    <div className="empty" data-testid={testId}>
      <h4>{title}</h4>
      <button type="button" className="kiosk-btn kiosk-btn--pill pill" onClick={() => { void retry(); }}>
        {t('kifu:retry', '重试')}
      </button>
    </div>
  );
  const note = (text: string) => <div className="empty"><h4>{text}</h4></div>;

  const secLabel = {
    live: { zh: t('kifu:live_now', '直播中'), en: 'Live' },
    finished: { zh: t('kifu:ended', '已结束'), en: 'Finished' },
    upcoming: { zh: t('live:tab_upcoming', '即将开始'), en: 'Upcoming' },
  }[tab];

  return (
    <div className="kiosk-layout-b" data-testid="live-page">
      <KioskPagebar
        testId="live-list-pagebar"
        backLabel={t('live:back_kifu', '棋谱')}
        onBack={() => navigate('/kiosk/kifu')}
        title={t('kifu:pro_live', '职业直播')}
        sub="Live"
        segment={{
          value: tab,
          options: [
            ['live', t('kifu:live_now', '直播中')],
            ['finished', t('kifu:ended', '已结束')],
            ['upcoming', t('live:tab_upcoming', '即将开始')],
          ],
          onChange: (next) => setTab(next as Tab),
          ariaLabel: t('kifu:pro_live', '职业直播'),
        }}
      />

      <KioskScrollZone resetKey={tab}>
        <section className="kiosk-section">
          <KioskSecLabel
            zh={secLabel.zh}
            en={secLabel.en}
            value={count > 0 ? `${count} ${t('kifu:games_unit', '局')}` : undefined}
          />

          {tab === 'upcoming' ? (
            upError && upcoming.length === 0 ? failed('upcoming-error', t('live:upcoming_failed', '赛程读不到'), upRefresh)
            : upLoading && upcoming.length === 0 ? note(t('live:loading_upcoming', '正在读赛程'))
            : upcoming.length === 0 ? note(t('live:no_upcoming', '暂无赛事预告'))
            : (
              <div className="kiosk-rows">
                {upcoming.map((u) => (
                  /* 赛程行**不可点**:这一场还没开始,没有可看的谱。来源写成字,不做外链(见头注 ③)。 */
                  <div className="kiosk-row" key={u.id} data-testid="upcoming-row">
                    <span className="kiosk-row__t">
                      <b>{[u.tournament, u.round_name].filter(Boolean).join(' · ')}</b>
                      <em>
                        {u.player_black && u.player_white
                          ? `${u.player_black} ${t('kifu:versus', '对')} ${u.player_white}`
                          : t('live:pairing_tbd', '对阵未定')}
                        {' · '}
                        {liveSourceLabel(u.source)}
                      </em>
                    </span>
                    <span className="kiosk-row__end">
                      <span className="kiosk-tag">{scheduleLabel(new Date(u.scheduled_time).getTime(), t)}</span>
                    </span>
                  </div>
                ))}
              </div>
            )
          ) : error && matches.length === 0 ? failed('live-list-error', t('live:list_failed', '直播读不到'), refresh)
            : loading && matches.length === 0 ? note(t('live:loading_list', '正在读直播'))
            : rows.length === 0 ? note(tab === 'live'
              ? t('live:none_live', '现在没有比赛在下')
              : t('live:none_finished', '最近没有结束的比赛'))
            : (
              <div className="kiosk-rows">
                {rows.map((m) => (
                  <button
                    type="button"
                    className="kiosk-row"
                    key={m.id}
                    data-testid="live-row"
                    onClick={() => navigate(`/kiosk/live/${m.id}`, { state: backToState(location) })}
                  >
                    <span className="kiosk-row__lead">{m.move_count} {t('kifu:moves_unit', '手')}</span>
                    <span className="kiosk-row__t">
                      <b>{[m.tournament, m.round_name].filter(Boolean).join(' · ')}</b>
                      <em>
                        {`${m.player_black} ${t('kifu:versus', '对')} ${m.player_white}`}
                        {' · '}
                        {liveSourceLabel(m.source)}
                        {m.status !== 'live' && m.result ? ` · ${translateResult(m.result, t, m.rules)}` : ''}
                        {m.status !== 'live' ? ` · ${whenLabel(new Date(m.date).getTime(), t)}` : ''}
                      </em>
                    </span>
                    <span className="kiosk-row__end">
                      {m.status === 'live'
                        ? <span className="kiosk-tag kiosk-tag--live">{t('kifu:live_now', '直播中')}</span>
                        : <span className="kiosk-tag">{t('kifu:ended', '已结束')}</span>}
                    </span>
                  </button>
                ))}
              </div>
            )}
        </section>
      </KioskScrollZone>
    </div>
  );
};

export default LivePage;
