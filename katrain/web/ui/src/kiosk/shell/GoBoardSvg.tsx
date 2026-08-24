import { useId } from 'react';
import { boardExtent, coordToXY, lineAt, starsFor, windowViewBox, type GoWindow } from './goBoard';

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
export function GoBoardSvg({
  size = 19, black = [], white = [], last, ghost = [], ghostFor, atari = [], muted = false, label,
  numbers, letters, shapes, highlights = [], window: win,
}: {
  size?: number;
  /** 坐标写成 `"Q16"`,不是 `[x, y]` —— 记谱、接口、日志全是这套写法,少一层换算就少一处错。 */
  black?: readonly string[];
  white?: readonly string[];
  last?: string;
  /** 候选点(「下一手该落这儿」的灯位 / 题目提示):半透明圈,**不画成棋子**。 */
  ghost?: readonly string[];
  /**
   * 候选点画成哪一色。**摆谱屏(屏 17)必须传** —— 那一屏的圈说的是「这儿要放一颗什么子」,
   * 而实体盘上的灯同时在那个点亮着,规范给这一屏定死了「**屏上高亮色必须和灯同色**」:
   * 黑子亮红灯、白子亮绿灯(`constants/ledColors.ts` 的 `LED_HEX`,四处独立来源一致)。
   * 不传时沿用原来那圈青玉色 —— 做题屏的「提示落这儿」没有灯,不该借用灯的语义。
   */
  ghostFor?: 'B' | 'W';
  /** 被叫吃的子:红方框,**不换子的颜色** —— 换颜色会和「这颗子是什么色」打架。 */
  atari?: readonly string[];
  /** 还没有真盘面可镜像时压暗。空盘和「看不到盘」是两回事,压暗说的是后者。 */
  muted?: boolean;
  label?: string;
  /* ── 以下五个 2026-08-24(屏 25 课程 · 小节讲解)加,**四个既有消费者一个都不传** ──
     教程图不是一局棋:它带手数号、字母、记号,而且书上印的大多只是棋盘一角。
     这几样落在这块盘上而不是另开一块,理由在 `goBoard.ts` 的文件头:
     跳 I、行号 1 在最下、九星按路数换、留白 0.5 格 —— 每一条都容易抄错,抄错了还挺像。
     (`components/tutorials/SGFBoard.tsx` 画得出这些,但它的边距是 0.75 格 ——
      配 kiosk 那条 0.5 格的刻度带,两端各差 5.59px,而几何闸的容差是 1.5。) */
  /** 手数号,`{ "Q16": "1" }`。**画在子上** —— 调用方负责只传这一步该显示的那些。 */
  numbers?: Readonly<Record<string, string>>;
  /** 空交叉点上的字母(书正文里的「A 方面」)。 */
  letters?: Readonly<Record<string, string>>;
  /** 空交叉点上的记号:`triangle` / `square` / `circle` / `cross`。 */
  shapes?: Readonly<Record<string, string>>;
  /** 「说的就是这几颗」——子上加一个三角,**不换子的颜色**(同 `atari` 那条理由)。 */
  highlights?: readonly string[];
  /** 只看一角。不传 = 全盘。线照全盘画,由 viewBox 裁 —— 见 `windowViewBox`。 */
  window?: GoWindow;
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

  const blackSet = new Set(black);
  /** 子上的号和三角取**对比色**:黑子上白、白子上深。空点上的字/记号走墨色。 */
  const onBlack = (c: string) => blackSet.has(c);

  /** 空点上的字母和记号:先垫一颗盘色小圆,不然 24px 的格线从字底下穿过去,7″ 屏读不出。 */
  const inkPad = (x: number, y: number, key: string) => (
    <circle key={key} className="pad" cx={x} cy={y} r={STONE_R * 0.62} fill={`url(#gr-${uid})`} />
  );

  return (
    <svg
      className={muted ? 'gob is-muted' : 'gob'}
      viewBox={win ? windowViewBox(win, U) : `0 0 ${W} ${W}`}
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
        // `ghost--b` / `ghost--w` 只改颜色,几何一个字不动 —— 见 `ghostFor` 那段。
        const cls = ghostFor ? `ghost ghost--${ghostFor.toLowerCase()}` : 'ghost';
        return <circle key={`g${c}`} className={cls} cx={p.x} cy={p.y} r={STONE_R * 0.62} />;
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
      {/* 空点上的记号:先垫盘色圆,再画。放在字母前面 —— 同一个点上不会两者都有。 */}
      {shapes && Object.entries(shapes).flatMap(([c, kind]) => {
        const p = P(c);
        const r = STONE_R * 0.5;
        const cls = 'shape';
        const node = kind === 'square'
          ? <rect key={`sh${c}`} className={cls} x={p.x - r} y={p.y - r} width={r * 2} height={r * 2} />
          : kind === 'circle'
            ? <circle key={`sh${c}`} className={cls} cx={p.x} cy={p.y} r={r} fill="none" />
            : kind === 'cross'
              ? (
                <g key={`sh${c}`} className={cls}>
                  <line x1={p.x - r * .7} y1={p.y - r * .7} x2={p.x + r * .7} y2={p.y + r * .7} />
                  <line x1={p.x - r * .7} y1={p.y + r * .7} x2={p.x + r * .7} y2={p.y - r * .7} />
                </g>
              )
              : (
                <polygon
                  key={`sh${c}`} className={cls}
                  points={`${p.x},${p.y - r} ${p.x - r * .866},${p.y + r * .5} ${p.x + r * .866},${p.y + r * .5}`}
                />
              );
        return [inkPad(p.x, p.y, `shp${c}`), node];
      })}
      {letters && Object.entries(letters).flatMap(([c, ch]) => {
        const p = P(c);
        return [
          inkPad(p.x, p.y, `ltp${c}`),
          <text key={`lt${c}`} className="letter" x={p.x} y={p.y} data-at={c}>{ch}</text>,
        ];
      })}
      {/* 手数号画在子上 —— 所以排在子后面。 */}
      {numbers && Object.entries(numbers).map(([c, n]) => {
        const p = P(c);
        return (
          <text
            key={`nm${c}`} className={onBlack(c) ? 'num on-b' : 'num on-w'}
            x={p.x} y={p.y} data-at={c}
          >{n}</text>
        );
      })}
      {highlights.map((c) => {
        const p = P(c);
        const r = STONE_R * 0.6;
        return (
          <polygon
            key={`hl${c}`} className={onBlack(c) ? 'hl on-b' : 'hl on-w'} data-at={c}
            points={`${p.x},${p.y - r} ${p.x - r * .866},${p.y + r * .5} ${p.x + r * .866},${p.y + r * .5}`}
          />
        );
      })}
    </svg>
  );
}
