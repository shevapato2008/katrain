import { useTranslation } from '../../../hooks/useTranslation';
import type { GrowthTrendPoint } from '../../api/growthApi';
import { TREND_H, TREND_W, trendGeometry } from './trendGeometry';

/** 服务端按 UTC 切天(`settled_at` 的日期),「今天」也按 UTC 取,两边才是同一根轴。 */
const todayUtc = () => new Date().toISOString().slice(0, 10);

/**
 * 左栏「近 30 天走势」—— 共享规范 §5:左栏装「大数 → 进度 → **近 30 天走势图** → 两格」,
 * 且**必须标出近 30 天最高**(绿点 + 标注,走 `--good`,不走棋种强调色)。
 * Fan 2026-09-21 裁定画**档位**不画净胜分:净胜分是 −2…+2 的锯齿,到 ±3 就清零,
 * 画成 30 天曲线读不出趋势。
 *
 * 构造照国象样稿 14 屏的 `.spark`:折线 + 淡填充 + 末端点 + 峰值点/标注。
 * **纯 SVG,不引图表库**:RK3562 上多一个包就多一份内存,而这里只是一条折线。
 * 末端点、峰值点、标注都是 HTML —— svg 被拉伸时圆会变椭圆、字会变宽。
 *
 * **没有对局的那天不补点**(后端就不给那天),所以折线会有长横段 —— 那是事实。
 */
const RungTrend = ({ points, days, placed }: { points: GrowthTrendPoint[]; days: number; placed: boolean }) => {
  const { t } = useTranslation();
  const geo = trendGeometry(points, { endDate: todayUtc(), days });
  const peakName = geo ? (geo.peak.point.rank_name ?? `#${geo.peak.point.rung}`) : '';

  // fragment 不是 div:小标题的样式是 `.panel > h3`,包一层就吃不到(第一版就是这样,标题变成了大号字)。
  return (
    <>
      <h3 className="gsec__h" data-testid="growth-trend-block">{t('growth:trend_title', '近 30 天走势')}</h3>
      {geo ? (
        <div className="gspark" data-testid="growth-trend">
          <svg
            viewBox={`0 0 ${TREND_W} ${TREND_H}`}
            preserveAspectRatio="none"
            role="img"
            aria-label={t('growth:trend_aria', '近 30 天档位走势，最高 {r}').replace('{r}', peakName)}
          >
            <path className="fill" d={geo.area} />
            <path className="line" d={geo.line} />
          </svg>
          <i className="gspark__end" style={{ left: `${geo.end.xPct}%`, top: `${geo.end.yPct}%` }} />
          <i className="gspark__peak" style={{ left: `${geo.peak.xPct}%`, top: `${geo.peak.yPct}%` }} />
          <b
            className="gspark__lbl"
            data-testid="growth-trend-peak"
            style={geo.peak.flip
              ? { right: `${100 - geo.peak.xPct}%`, top: `${geo.peak.yPct}%`, marginRight: 9 }
              : { left: `${geo.peak.xPct}%`, top: `${geo.peak.yPct}%`, marginLeft: 9 }}
          >
            {t('growth:trend_peak', '最高 {r}').replace('{r}', peakName)}
          </b>
        </div>
      ) : (
        // 一个点或没有点:**说一句话,不画一条没有斜率的线**(那会被读成「持平」)。
        <p className="setnote gtrend-note" data-testid="growth-trend-empty">
          {placed
            ? t('growth:trend_thin', '近 30 天定级后的升降级对局不到两天，还连不成线。')
            : t('growth:trend_unplaced', '定级完成后开始画：定级那几局的对手是在试你的水平，不是你的档位。')}
        </p>
      )}
    </>
  );
};

export default RungTrend;
