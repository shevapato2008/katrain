import { useState } from 'react';
import { useTranslation } from '../../../hooks/useTranslation';
import { localDate, type GrowthActivity } from '../../api/growthApi';
import { calendarGrid } from './calendarGrid';

/** 53 周始终占满同一宽度；窗口以外及今天以后只留格位，不伪装成零次练习。 */
const WEEKS = 53;

const ActivityCalendar = ({ activity, failed }: { activity: GrowthActivity | null; failed: boolean }) => {
  const { t } = useTranslation();
  const [helpOpen, setHelpOpen] = useState(false);
  const grid = activity ? calendarGrid(activity.days, { endDate: localDate(), windowDays: activity.window_days }) : null;
  const cells = grid ? Array.from({ length: WEEKS * 7 }, (_, index) => grid.cells[index] ?? null) : [];

  return (
    <section className="panel gcal" data-testid="growth-cal" aria-label={t('growth:cal_aria', '近一年练棋日历')}>
      <div className="gcal__head">
        <strong>{t('growth:cal_title', '近一年练棋')}</strong>
        {!failed && <span className="gcal__total">
          <b data-testid="growth-cal-days">{grid ? grid.activeDays : '—'}</b>
          {t('growth:cal_days_unit', ' 天')}
        </span>}
        <button
          type="button"
          className="growth-help"
          aria-label={t('growth:cal_help_label', '近一年练棋说明')}
          aria-expanded={helpOpen}
          onClick={() => setHelpOpen((open) => !open)}
        >
          <svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="9" /><path d="M12 11v6m0-10h.01" /></svg>
        </button>
      </div>
      {helpOpen && <p className="gcal__help" role="note">
        {t('growth:cal_help', '每格一天，统计当天下完的对局与新解出的题；颜色越亮，完成越多。白框标出今天。')}
      </p>}
      {failed ? <p className="gcal__state" data-testid="growth-cal-error">
        {t('growth:cal_failed', '日历没读到，稍后再看一次。')}
      </p> : !grid ? <p className="gcal__state" data-testid="growth-cal-loading">
        {t('growth:cal_loading', '正在读练棋记录…')}
      </p> : <>
        <div className="gcal__plot">
          <div className="gcal__months" aria-hidden="true">
            {grid.months.map((month, index) => (
              <span
                key={`${month.col}-${month.month}`}
                data-week={month.col}
                style={{ gridColumn: `${month.col + 1} / ${Math.min(WEEKS + 1, (grid.months[index + 1]?.col ?? WEEKS) + 1)}` }}
              >
                {t('growth:cal_month', '{m}月').replace('{m}', String(month.month))}
              </span>
            ))}
          </div>
          <div className="gcal__days" aria-hidden="true">
            <span>{t('growth:cal_mon', '一')}</span><span />
            <span>{t('growth:cal_wed', '三')}</span><span />
            <span>{t('growth:cal_fri', '五')}</span><span />
            <span>{t('growth:cal_sun', '日')}</span>
          </div>
          <div
            className="gcal__grid"
            role="img"
            aria-label={t('growth:cal_grid_aria', '近一年有 {n} 天练棋记录，每列一周，从周一至周日；白框表示今天').replace('{n}', String(grid.activeDays))}
          >
            {cells.map((cell, index) => (
              <i
                key={index}
                className={`gcal__c${cell?.level ? ` l${cell.level}` : ''}${cell?.today ? ' is-today' : ''}${!cell || cell.void ? ' is-void' : ''}`}
                data-date={cell && !cell.void ? cell.date : undefined}
                data-level={cell && !cell.void ? cell.level : undefined}
                title={cell && !cell.void ? `${cell.date} · ${cell.count}` : undefined}
              />
            ))}
          </div>
        </div>
        <div className="gcal__footer">
          <span>{activity?.authority === 'local_cache'
            ? t('growth:cal_local', '本机记录')
            : t('growth:cal_week', '每列一周 · 周一至周日')}</span>
          <div className="gcal__legend" aria-label={t('growth:cal_legend', '练棋次数由少至多')}>
            {['0', '1–2', '3–5', '6–9', '10+'].map((label, level) => (
              <span key={label}><i className={`gcal__c${level ? ` l${level}` : ''}`} />{label}</span>
            ))}
          </div>
        </div>
      </>}
    </section>
  );
};

export default ActivityCalendar;
