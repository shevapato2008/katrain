import { useTranslation } from '../../../hooks/useTranslation';
import { localDate, type GrowthActivity } from '../../api/growthApi';
import { calendarGrid } from './calendarGrid';

/**
 * 屏 22 右栏「近一年练棋日历」—— 构造照稿子(smartbox `go-kiosk.tmpl.html` 屏 22,Fan 2026-09-22 定):
 * 左边一栏摘要(近一年练过几天 + 图例),右边 53 周 × 7 行的格子,顶上标月份。
 *
 * 格子只有 8px,**不可点**(触控下限 44px);摘要里那个天数就是它的文字等价物。
 *
 * 三种「没有格子」各说各的:还在读(不画格子,也不写 0 —— 一张全空的格子读起来就是「一天没练」)、
 * 读失败(照实说没读到)、真的一天没练(照画一张全空的格子,天数写 0)。
 */
const ActivityCalendar = ({ activity, failed }: { activity: GrowthActivity | null; failed: boolean }) => {
  const { t } = useTranslation();
  const grid = activity ? calendarGrid(activity.days, { endDate: localDate(), windowDays: activity.window_days }) : null;
  const local = activity?.authority === 'local_cache';

  return (
    <section className="panel gcal" data-testid="growth-cal" aria-label={t('growth:cal_aria', '近一年练棋日历')}>
      <div className="gcal__sum">
        <span className="gcal__k">{t('growth:cal_title', '近一年')}</span>
        {failed ? (
          <span className="gcal__sub gcal__err" data-testid="growth-cal-error">
            {t('growth:cal_failed', '日历没读到，稍后再看一次。')}
          </span>
        ) : (
          <>
            <b className="gcal__v">
              <span data-testid="growth-cal-days">{grid ? grid.activeDays : '—'}</span>
              <small>{t('growth:cal_days_unit', '天')}</small>
            </b>
            <span className="gcal__sub">
              {local
                // 盒子拿不到云端时退回本机那一份:别的设备上下的局、做的题这里没有。
                // 只写四个字:摘要栏 84px 宽,再长就折成两行,把整块日历撑高 15px(承重实测)。
                ? t('growth:cal_local', '本机记录')
                : t('growth:cal_sub', '下过棋或解过题')}
            </span>
          </>
        )}
        {grid && (
          <span className="gcal__legend" aria-hidden="true">
            <span>{t('growth:cal_less', '少')}</span>
            <i className="gcal__c" /><i className="gcal__c l1" /><i className="gcal__c l2" />
            <i className="gcal__c l3" /><i className="gcal__c l4" />
            <span>{t('growth:cal_more', '多')}</span>
          </span>
        )}
      </div>
      <div className="gcal__plot">
        {grid && (
          <>
            <div className="gcal__months" aria-hidden="true">
              {grid.months.map((m) => (
                <span key={`${m.col}-${m.month}`} style={{ left: m.col * 10 }}>
                  {t('growth:cal_month', '{m}月').replace('{m}', String(m.month))}
                </span>
              ))}
            </div>
            <div className="gcal__body">
              <div className="gcal__days" aria-hidden="true">
                <span>{t('growth:cal_mon', '一')}</span><span />
                <span>{t('growth:cal_wed', '三')}</span><span />
                <span>{t('growth:cal_fri', '五')}</span><span /><span />
              </div>
              <div className="gcal__grid">
                {grid.cells.map((c) => (
                  <i
                    key={c.date}
                    className={`gcal__c${c.level ? ` l${c.level}` : ''}${c.today ? ' is-today' : ''}${c.void ? ' is-void' : ''}`}
                    data-date={c.void ? undefined : c.date}
                    data-level={c.void ? undefined : c.level}
                  />
                ))}
              </div>
            </div>
          </>
        )}
      </div>
    </section>
  );
};

export default ActivityCalendar;
