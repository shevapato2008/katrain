import type { GameState } from '../../../api';
import { useTranslation } from '../../../hooks/useTranslation';

const W = 382;   // 460(右栏)− 2(折叠块描边)− 2×38(两条刻度带)
const H = 96;    // --eval-graph-h
const PAD = 4;   // 两端各留 4,端点的圆不被裁掉

/**
 * §8 胜率走势 —— 围棋是**双轴**:左边胜率、右边目差。
 *
 * 两条都是 KataGo **原生**吐的量(一次 `analyze_current` 同时给 winrate 和 score_lead),
 * galaxy 的 `ScoreGraph` 也是这么画的。所以规范 §8 第三种口径:标题写「原生通道」,
 * 右端**不摆「换算前的原始评分」** —— 原生通道里没有换算这一步。
 *
 * **上黑下白**,与 galaxy 同向:`models_db.py:373` 写着 winrate 是**黑方的** 0–1,
 * `ScoreGraph` 把 1.0 画在顶上。复盘屏那条曲线同向,**同一局在两屏之间不许上下颠倒**
 * (五子棋 2026-08-02 踩过)。
 *
 * ## 为什么不直接用共享的 `ScoreGraph`
 *
 * 它把刻度**画在 svg 里面**(13px 文字)、外面还顶着一行 14px 的数值,整块 180 高 ——
 * 而这一屏的账只有 96 + 30。稿子的做法是把刻度移到 svg **外面**两条 38 的 DOM 带里
 * (`.kiosk-eval__axis` / `.gevax`),svg 里只剩线。两者是**同一份数据的两种版式**,
 * 不是两套算法:取数、上黑下白、点击跳手全都照抄。
 *
 * ## 目差轴跟着数据放大
 *
 * 稿子上写死 ±10。真打到 +40 时线会贴着顶飞出去,所以这里按 `ScoreGraph` 的口径取
 * `max(10, ceil(max|score|/10)*10)`,**并且把刻度带上那两个字一起改掉** ——
 * 轴变了而字不变,是「数字漂亮、结论全假」的经典形状。
 */
export function GoEvalGraph({ gameState, onNavigate }: {
  gameState: GameState;
  onNavigate: (nodeId: number) => void;
}) {
  const { t } = useTranslation();
  const history = gameState.history ?? [];
  const currentIndex = gameState.current_node_index ?? -1;

  const scores = history.map((h) => h.score).filter((s): s is number => s !== null && s !== undefined);
  const scale = Math.max(10, Math.ceil(Math.max(0, ...scores.map(Math.abs)) / 10) * 10);

  // 短棋谱不把线拉满整块画布:15 是 `ScoreGraph` 用的同一个下界。
  const xStep = (W - 2 * PAD) / Math.max(history.length - 1, 15);
  const xAt = (i: number) => PAD + i * xStep;
  const wrY = (wr: number) => (1 - wr) * H;                         // 黑 100% 在顶上
  const slY = (s: number) => H / 2 - Math.max(-scale, Math.min(scale, s)) * (H / 2 / scale);

  const wrPts = history
    .map((h, i) => (h.winrate === null || h.winrate === undefined ? null : `${xAt(i)},${wrY(h.winrate)}`))
    .filter((p): p is string => p !== null)
    .join(' ');
  const slPts = history
    .map((h, i) => (h.score === null || h.score === undefined ? null : `${xAt(i)},${slY(h.score)}`))
    .filter((p): p is string => p !== null)
    .join(' ');

  const cur = currentIndex >= 0 && currentIndex < history.length ? history[currentIndex] : null;
  const curWr = cur?.winrate ?? null;

  const jump = (e: React.MouseEvent<SVGSVGElement>) => {
    const rect = e.currentTarget.getBoundingClientRect();
    const x = ((e.clientX - rect.left) / rect.width) * W;
    const i = Math.round((x - PAD) / xStep);
    if (i >= 0 && i < history.length) onNavigate(history[i].node_id);
  };

  return (
    <div className="kiosk-eval kiosk-eval--dual" data-testid="score-graph">
      <div className="kiosk-eval__axis">
        <i>{t('game:eval_black_100', '黑 100')}</i>
        <i>50</i>
        <i>{t('game:eval_white_100', '白 100')}</i>
      </div>
      <div className="kiosk-eval__plot">
        <svg
          viewBox={`0 0 ${W} ${H}`}
          preserveAspectRatio="none"
          data-eval
          onClick={jump}
          aria-label={t('game:eval_graph', '本局胜率与目差走势')}
        >
          <line className="grid" x1="0" y1={H / 4} x2={W} y2={H / 4} />
          <line className="grid" x1="0" y1={(H * 3) / 4} x2={W} y2={(H * 3) / 4} />
          <line className="mid" x1="0" y1={H / 2} x2={W} y2={H / 2} />
          {slPts && <polyline className="sl" points={slPts} />}
          {wrPts && <polyline className="wr" points={wrPts} />}
          {curWr !== null && currentIndex >= 0 && (
            <circle className="now" cx={xAt(currentIndex)} cy={wrY(curWr)} r="4" />
          )}
        </svg>
      </div>
      <div className="gevax">
        <i>{t('game:eval_black_lead', '黑+{n}').replace('{n}', String(scale))}</i>
        <i>0</i>
        <i>{t('game:eval_white_lead', '白+{n}').replace('{n}', String(scale))}</i>
      </div>
    </div>
  );
}

/**
 * 折叠块标题行右端那个**结论**:「黑 37.4% · 白 +4.8 目」。
 * 收起明细之后它照旧显示(§11 第 2 条),所以它不能长在图里面。
 * 取不到就是 `—` —— 「后端还没给这一手的分析」不是「均势」。
 *
 * 和图放同一个文件是**有意的**:它俩共用「当前是哪一手」和「winrate 是黑方的」这两条口径,
 * 分开放迟早会各自算一遍而漂掉。`GamePage.tsx` 的两个纯函数也是同样的理由留在原地。
 */
// eslint-disable-next-line react-refresh/only-export-components
export function goEvalSummary(
  gameState: GameState,
  t: (key: string, fallback?: string) => string,
): string {
  const history = gameState.history ?? [];
  const i = gameState.current_node_index ?? -1;
  const cur = i >= 0 && i < history.length ? history[i] : null;
  const wr = cur?.winrate;
  const sl = cur?.score;
  const wrText = wr === null || wr === undefined
    ? '—'
    : `${t('game:black', '黑')} ${(wr * 100).toFixed(1)}%`;
  const slText = sl === null || sl === undefined
    ? '—'
    : `${sl >= 0 ? t('game:black', '黑') : t('game:white', '白')} +${Math.abs(sl).toFixed(1)} ${t('game:points_unit', '目')}`;
  return `${wrText} · ${slText}`;
}
