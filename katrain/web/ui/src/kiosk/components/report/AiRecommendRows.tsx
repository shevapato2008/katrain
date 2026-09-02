import { useTranslation } from '../../../hooks/useTranslation';

/**
 * AI 推荐表的表头与行 —— 屏 20 复盘和屏 21 研究**共用这一份**。
 *
 * ## 列名用 galaxy 那四个 msgid,不用 kiosk 自己那四个
 *
 * 2026-09-01 Fan 对着两端的截图说:「几个按钮的 icon 还有名称也和 galaxy 界面中的不一致,
 * 这是不能接受的。」这张表也是同一族:kiosk 原来写 `research:col_move` /
 * `research:col_score_diff`(cn PO:**着手** / **目差**),galaxy 写
 * `live:suggested_move` / `live:lead_pts`(cn PO:**着点** / **领先**)——
 * 同一张表在两端上是两组词。
 *
 * 修法不是改 PO、也不是铸新 key,而是**两端用同一组 msgid**:
 * 从此翻译改一次两边一起变,不会再漂。(与仓里另一处同形修法一致:kiosk 的删除对话框
 * 改用 galaxy 已有的 `report:delete_game`。)
 * `research:col_*` 四条随之退役 —— cn PO 里它们仍在,但没有消费者了。
 *
 * ## 为什么把行也一起收进来
 *
 * 两屏的数据源不同(屏 20 是 `currentAnalysis.top_moves`,屏 21 是扫描结果),
 * 但**行的画法必须一样**:首行走 `.best`、负目差一律走 `.neg`(绿色的负数是自相矛盾的)。
 * 上一版这两条各写各的,屏 20 那份就漏了「负目差」那一条。
 */

export interface AiRow {
  move: string;
  /** 推荐度 0–100。 */
  share: number;
  /** 领先目数,走子方视角。 */
  scoreLead: number;
  /** 胜率 0–1。 */
  winrate: number;
}

export function AiRecommendRows({ rows }: { rows: readonly AiRow[] }) {
  const { t } = useTranslation();
  return (
    <>
      <span className="hd">{t('live:suggested_move', '着点')}</span>
      <span className="hd">{t('live:recommendation', '推荐度')}</span>
      <span className="hd">{t('live:lead_pts', '领先')}</span>
      <span className="hd">{t('live:winrate', '胜率')}</span>
      {/* 有几行画几行,**下面留白,不补空行也不补占位** —— `.aitab` 的
          `align-content:start` 就是为这个写的。留白是真话:AI 只给出了这么多候选。 */}
      {rows.map((r, i) => {
        const best = i === 0 ? 'best' : '';
        // **负目差一律走 `.neg`,连首行也不例外** —— 绿色的负数是自相矛盾的。
        const scoreCls = r.scoreLead < 0 ? 'neg' : best;
        return (
          <span key={r.move} style={{ display: 'contents' }} data-testid="ai-recommend-row">
            <span className={best}>{r.move}</span>
            <span className={best}>{r.share.toFixed(0)}%</span>
            <span className={scoreCls}>{r.scoreLead >= 0 ? '+' : '−'}{Math.abs(r.scoreLead).toFixed(1)}</span>
            <span className={best}>{(r.winrate * 100).toFixed(1)}%</span>
          </span>
        );
      })}
    </>
  );
}
