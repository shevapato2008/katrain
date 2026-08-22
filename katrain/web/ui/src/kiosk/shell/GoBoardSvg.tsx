import { useId } from 'react';
import { boardExtent, coordToXY, lineAt, starsFor } from './goBoard';

const U = 100;                 // SVG 内部单位
const LINE_W = U * 0.030;      // 19 路比 15 路密,线宽按格距收一档,否则盘面糊成一片
const EDGE_W = U * 0.048;      // 最外一圈粗一档,和真木盘一样
const STAR_R = U * 0.075;
const STONE_R = U * 0.47;

/**
 * 一块围棋盘的 SVG —— 镜像栏、对局屏、做题屏共用。
 * 算式全部来自 `goBoard.ts`;长相(线色、子色、标记)在 `go-screens.css` 的 `.gob` 一组。
 * 逐字对着稿子 `sample-go/go-kiosk.tmpl.html` 的 `gosvg()` 搬。
 *
 * ## 两条来自规范 §13 的硬要求
 *
 * ① **paint server 的 id 必须每个实例都不一样。** `url(#gr)` 永远解析到文档里**第一个**
 *    同名的;一页上有好几块盘时,一旦第一个落进 `display:none` 的那一台,**所有盘的浅色底
 *    一起失效** —— 象棋整块盘变黑褐就是这么来的。稿子用自增计数器,这里用 React `useId()`,
 *    它对 SSR 和并发渲染也成立。
 * ② **木纹那层 `mix-blend-mode: multiply` 必须有显式 `isolation: isolate` 祖先**,
 *    否则它不只跟盘面浅底相乘,而是一路穿透跟底下那圈深色木框一起相乘。
 *    `.gob { isolation: isolate }` 写在 `go-screens.css` 里 —— **即使现在没抄木纹也留着**,
 *    因为它同时是「这块盘自成一个混合上下文」这件事本身。
 *
 * 木纹贴图没抄:那张图在 `sample-go/board-assets.json` 里,不在共享资产包、也不在 MANIFEST
 * 管辖内,抄它等于往仓里塞一份没人核的二进制(D6 已登记)。
 */
export function GoBoardSvg({ size = 19, black = [], white = [], last, ghost = [], atari = [], muted = false, label }: {
  size?: number;
  /** 坐标写成 `"Q16"`,不是 `[x, y]` —— 记谱、接口、日志全是这套写法,少一层换算就少一处错。 */
  black?: readonly string[];
  white?: readonly string[];
  last?: string;
  /** 候选点(「下一手该落这儿」的灯位 / 题目提示):半透明青玉圈,**不画成棋子**。 */
  ghost?: readonly string[];
  /** 被叫吃的子:红方框,**不换子的颜色** —— 换颜色会和「这颗子是什么色」打架。 */
  atari?: readonly string[];
  /** 还没有真盘面可镜像时压暗。空盘和「看不到盘」是两回事,压暗说的是后者。 */
  muted?: boolean;
  label?: string;
}) {
  const uid = useId().replace(/:/g, '');
  const W = boardExtent(size, U);
  const P = (c: string) => {
    const { x, y } = coordToXY(c, size);
    return { x: lineAt(x, U), y: lineAt(y, U) };
  };

  const lines = [];
  for (let i = 0; i < size; i += 1) {
    const w = i === 0 || i === size - 1 ? EDGE_W : LINE_W;
    lines.push(
      <line key={`h${i}`} className="ln" x1={lineAt(0, U)} y1={lineAt(i, U)} x2={lineAt(size - 1, U)} y2={lineAt(i, U)} strokeWidth={w} />,
      <line key={`v${i}`} className="ln" x1={lineAt(i, U)} y1={lineAt(0, U)} x2={lineAt(i, U)} y2={lineAt(size - 1, U)} strokeWidth={w} />,
    );
  }

  const stone = (c: string, isBlack: boolean) => {
    const p = P(c);
    return (
      // `data-stone` / `data-at`:**给测试和几何闸用的把手**。子是画出来的圆,DOM 上问不出
      // 「Q16 上有没有黑子」—— 没有把手就只能去数 circle,而数出来的数字换个装饰就变。
      <g key={`${isBlack ? 'b' : 'w'}${c}`} data-stone={isBlack ? 'b' : 'w'} data-at={c}>
        {/* 落影:往下偏 3%,不是模糊 —— 7″ 屏上高斯模糊看不出来,只吃 GPU */}
        <circle cx={p.x} cy={p.y + U * 0.03} r={STONE_R} fill="rgba(40,20,8,.34)" />
        <circle cx={p.x} cy={p.y} r={STONE_R} fill={`url(#s${isBlack ? 'b' : 'w'}-${uid})`} />
      </g>
    );
  };

  return (
    <svg
      className={muted ? 'gob is-muted' : 'gob'}
      viewBox={`0 0 ${W} ${W}`}
      preserveAspectRatio="xMidYMid meet"
      role={label ? 'img' : undefined}
      aria-label={label}
      aria-hidden={label ? undefined : true}
    >
      <defs>
        <linearGradient id={`gr-${uid}`} x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="var(--gb-light)" />
          <stop offset="1" stopColor="var(--gb-dark)" />
        </linearGradient>
        <radialGradient id={`sb-${uid}`} cx="34%" cy="30%">
          <stop offset="0" stopColor="#585862" /><stop offset="1" stopColor="#0A0A0C" />
        </radialGradient>
        <radialGradient id={`sw-${uid}`} cx="34%" cy="30%">
          <stop offset="0" stopColor="#FFFFFF" /><stop offset="1" stopColor="#CFC9BB" />
        </radialGradient>
      </defs>
      <rect width={W} height={W} fill={`url(#gr-${uid})`} />
      {lines}
      {starsFor(size).map(([x, y]) => (
        <circle key={`s${x}-${y}`} className="star" cx={lineAt(x, U)} cy={lineAt(y, U)} r={STAR_R} />
      ))}
      {ghost.map((c) => {
        const p = P(c);
        return <circle key={`g${c}`} className="ghost" cx={p.x} cy={p.y} r={STONE_R * 0.62} />;
      })}
      {black.map((c) => stone(c, true))}
      {white.map((c) => stone(c, false))}
      {/* 最后一手:**圈在子上**,不是换颜色 */}
      {last && (() => { const p = P(last); return <circle className="mark" cx={p.x} cy={p.y} r={STONE_R * 0.55} />; })()}
      {atari.map((c) => {
        const p = P(c);
        const s = STONE_R * 1.15;
        return <rect key={`a${c}`} className="atari" x={p.x - s} y={p.y - s} width={s * 2} height={s * 2} rx={4} />;
      })}
    </svg>
  );
}
