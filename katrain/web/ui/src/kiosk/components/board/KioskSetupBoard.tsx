import { useTranslation } from '../../../hooks/useTranslation';
import './kioskSetupBoard.css';

/**
 * 开局设置屏左边那块盘 —— 规范 §8 的 516 外框 + §11 布局 A。
 *
 * **它画的不是这台机器上那块真盘。** 规范 `kiosk-shell-spec.md:512` 逐字:
 * 「左边那块盘画的是**按下按钮后真会出现的那个局面**,视角跟着「执棋方」翻 ——
 * 那是这次选择唯一立刻看得见的后果,画示意局面等于用假数据充门面。」
 * 围棋这一局的起始局面就是**空盘 19×19**,所以这里一颗子都不摆 —— 空不是占位,是答案。
 *
 * 摄像头镜像那块是 **L1**(`SmartBoardConsole`,296 宽,`spec:139`),不是这一屏的东西。
 *
 * ## 为什么不复用 `LiveBoard`
 *
 * `LiveBoard` 的 `calculateBoardLayout` 写死 `gridMargins = 1.5 格`
 * (`components/board/boardUtils.ts:34`),而规范 `:432` 要求交叉点棋盘取 **0.5 格**:
 * 刻度带把 19 个字**均分**在 460 上、第 i 个字心在 `(i+0.5)/19`,盘上第 i 条线在
 * `(0.5+i)/19` —— **两式相等当且仅当 margin = 0.5**。拿 1.5 的盘配 0.5 的刻度带,
 * 字和线会整整错开一格(≈24px),不是「差几个像素」。
 * 改 `LiveBoard` 的边距是动**共享**组件(galaxy 和对局屏都在用),blast radius 远大于
 * 这里自己画一块空盘。⇒ 按稿子 `sample-go/go-kiosk.tmpl.html:850-880` 的算式重写一份。
 *
 * 与稿子的**唯一**出入:稿子在渐变之上还叠了一层 `--oak` 木纹(`mix-blend-mode:multiply`),
 * 那张贴图在 `sample-go/board-assets.json` 里、**不在共享资产包**,也不在 MANIFEST 管辖内。
 * 没抄 —— 抄它等于往仓里塞一份没人核的二进制。记账在 `kiosk-design-alignment.md` §12。
 */

// `spec:403` 围棋:上下 A–T(**跳 I**),左右 1–19。跳 I 之后正好 19 个字母。
// 9 路 / 13 路取前 9 / 前 13 个,跳 I 这条一样成立。
const COLS = 'ABCDEFGHJKLMNOPQRST';
// `spec:432`:没有外双框的棋种(围棋、五子棋)一律 0.5 格,这样刻度字和线逐条对齐。
const MARGIN = 0.5;
const U = 100; // SVG 内部单位;19 路外框 viewBox 边长 = (18 + 2×0.5) × 100 = 1900

/** 星位按路数换,不是同一组坐标缩放:9 路的星在 3-3,19 路在 4-4(这里是 0 起索引)。 */
const STARS_BY_SIZE: Record<number, [number, number][]> = {
  9: [[2, 2], [2, 6], [6, 2], [6, 6], [4, 4]],
  13: [[3, 3], [3, 9], [9, 3], [9, 9], [6, 6]],
  19: [[3, 3], [3, 9], [3, 15], [9, 3], [9, 9], [9, 15], [15, 3], [15, 9], [15, 15]],
};
// 稿子 `:852`:19 路比 15 路密,线宽按格距收一档;最外一圈粗一档,和真木盘一样。
const LINE_W = U * 0.03;
const EDGE_W = U * 0.048;
const STAR_R = U * 0.075;

const at = (i: number) => (MARGIN + i) * U;

interface KioskSetupBoardProps {
  /**
   * 我执哪一色。**只用来标记这一屏当前的选择**(`data-color`),不改刻度方向 ——
   * 围棋记法绝对,理由见下面那段。留着它是因为「这块盘属于哪一次选择」在取图和断言里要认。
   */
  color: 'black' | 'white';
  /** 路数。自由对弈可选 9/13/19;升降级固定 19(`ladder:fixed_setup`)。 */
  size: number;
}

const KioskSetupBoard = ({ color, size }: KioskSetupBoardProps) => {
  const { t } = useTranslation();
  const W = (size - 1 + 2 * MARGIN) * U;
  const stars = STARS_BY_SIZE[size] ?? [];
  // 刻度**不跟着执棋方翻**。这不是给规范开例外,是规范里更具体的那条本来就管这件事:
  //
  //   §8 `:414` 已经立过刻度方向的法,而且**立法依据就是记法** —— 「象棋两条刻度数值不同向:
  //   同一列,下面写「九」时上面写「1」…**看到某个实现把上面那行也写成 9…1,那是错的**」。
  //   ⇒ 规范自己的口径是:**刻度是记法的函数,不是执棋方的函数。**
  //   围棋的记法是**绝对**的(A1 永远是那一个角,SGF 记谱、棋谱库、对局屏都按它),
  //   ⇒ 刻度不倒。
  //
  // §11 `:514`「视角跟着执棋方翻」那句是从**国象**那一版推出来的(v1.21 改动记录自陈,
  // 起因是国象把开局设置做成了无盘卡片墙),而围棋稿子里**根本没有开局设置屏** ——
  // 这条规则从来没有被它的作者在围棋上应用过。本仓按 §8 `:414` 执行,
  // **`:514` 的措辞已由协调方提请澄清**;那份文档四家共读,不是这里能改的。
  //
  // ⚠️ 别把理由写成「围棋空盘 180° 对称所以翻不翻都一样」—— **那句是错的**:
  // 空盘对,**让子局不对**(3 子让子是右上/左下/左上,转 180° 变成左下/右上/右下,
  // 不是同一个局面)。理由是记法绝对,不是图形对称。
  const cols = [...COLS].slice(0, size);
  // 行号 1 在最下(`spec:403` 那张表,五子棋那行写明了方向,围棋同向),所以从上往下读是 19…1。
  const rows = Array.from({ length: size }, (_, i) => size - i);

  const lines = [];
  for (let i = 0; i < size; i += 1) {
    const w = i === 0 || i === size - 1 ? EDGE_W : LINE_W;
    lines.push(
      <line key={`h${i}`} className="ln" x1={at(0)} y1={at(i)} x2={at(size - 1)} y2={at(i)} strokeWidth={w} />,
      <line key={`v${i}`} className="ln" x1={at(i)} y1={at(0)} x2={at(i)} y2={at(size - 1)} strokeWidth={w} />,
    );
  }

  return (
    <div
      className="kiosk-board kiosk-setup-board"
      data-testid="kiosk-setup-board"
      data-color={color}
      role="img"
      aria-label={t('ladder:board_preview', '开局局面预览:空盘')}
    >
      <div className="kiosk-board__ruler kiosk-board__ruler--top">
        {cols.map((c) => <span key={`t${c}`}>{c}</span>)}
      </div>
      <div className="kiosk-board__ruler kiosk-board__ruler--left">
        {rows.map((r) => <span key={`l${r}`}>{r}</span>)}
      </div>
      <div className="kiosk-board__play">
        <svg className="gob" viewBox={`0 0 ${W} ${W}`} preserveAspectRatio="xMidYMid meet" aria-hidden="true">
          <defs>
            <linearGradient id="kiosk-setup-board-wood" x1="0" y1="0" x2="1" y2="1">
              <stop offset="0" stopColor="var(--gb-light)" />
              <stop offset="1" stopColor="var(--gb-dark)" />
            </linearGradient>
          </defs>
          <rect width={W} height={W} fill="url(#kiosk-setup-board-wood)" />
          {lines}
          {stars.map(([x, y]) => (
            <circle key={`s${x}-${y}`} className="star" cx={at(x)} cy={at(y)} r={STAR_R} />
          ))}
        </svg>
      </div>
      <div className="kiosk-board__ruler kiosk-board__ruler--right">
        {rows.map((r) => <span key={`r${r}`}>{r}</span>)}
      </div>
      <div className="kiosk-board__ruler kiosk-board__ruler--bottom">
        {cols.map((c) => <span key={`b${c}`}>{c}</span>)}
      </div>
    </div>
  );
};

export default KioskSetupBoard;
