import { useTranslation } from '../../../hooks/useTranslation';
import { interpolate } from '../../utils/interpolate';
import { colsFor, handicapStones, rowsFor } from '../../shell/goBoard';
import { GoBoardSvg } from '../../shell/GoBoardSvg';

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
 * ⇒ 按稿子 `sample-go/go-kiosk.tmpl.html:850-880` 的算式另画一份,就是 `shell/GoBoardSvg`。
 *
 * ⚠️ Task 11 起**对局屏走的正是 `LiveBoard` 那条路的另一半**:它用共享 `Board`(canvas),
 * 靠一个默认 `false` 的 `externalRulers` 开关把边距切到 0.5、并把落子区**精确铺满** ——
 * 那是「盘上有子、要能点」的屏才必须付的代价。这一屏的盘是空的、也不可点,
 * 一块 SVG 就够,不必把 canvas 那套搬过来。
 */

// 盘面本身交给 `shell/GoBoardSvg`(Task 11 起对局屏、镜像栏、做题屏共用同一份)。
// 这里原来自己画了一遍线、星位和木底渐变 —— 算式虽然都从 `goBoard.ts` 取,
// **渐变的 id 是写死的字面量** `kiosk-setup-board-wood`;规范 §13① 说得很直白:
// `url(#id)` 永远解析到文档里第一个同名的 paint server,一页上出现第二块盘就会串。
// `GoBoardSvg` 用 `useId()` 加后缀,所以搬过去顺带把那颗雷拆了。
// 刻度带留在这儿:它是**外框**的一部分(`.kiosk-board` 的四条 28 带),不是盘面。

interface KioskSetupBoardProps {
  /**
   * 我执哪一色。**只用来标记这一屏当前的选择**(`data-color`),不改刻度方向 ——
   * 围棋记法绝对,理由见下面那段。留着它是因为「这块盘属于哪一次选择」在取图和断言里要认。
   */
  color: 'black' | 'white';
  /** 路数。自由对弈可选 9/13/19;升降级固定 19(`ladder:fixed_setup`)。 */
  size: number;
  /**
   * 让几子。**这块盘要画出来** —— 规范 `:512` 说它画的是「按下按钮后**真会出现**的
   * 那个局面」,而让子局的起始局面就是带着那几颗黑子的。
   *
   * 2026-08-23(屏 02)之前这里恒画空盘,注释里的理由是「围棋这一局的起始局面就是空盘」——
   * **那句话只对不让子的那一局成立**。四图一比就露了:稿子那一帧让了 2 子、盘上有 Q16 和 D4,
   * 实现画的是空盘。计分局一律 0 子,所以那一屏不受影响,这条只在自由对弈上看得见。
   */
  handicap?: number;
}

const KioskSetupBoard = ({ color, size, handicap = 0 }: KioskSetupBoardProps) => {
  const { t } = useTranslation();
  const cols = colsFor(size);
  const stones = handicapStones(size, handicap);
  // 行号 1 在最下(`spec:403` 那张表,五子棋那行写明了方向,围棋同向),所以从上往下读是 19…1。
  const rows = rowsFor(size);

  return (
    <div
      className="kiosk-board kiosk-setup-board"
      data-testid="kiosk-setup-board"
      data-color={color}
      role="img"
      data-handicap={handicap}
      aria-label={stones.length
        ? interpolate(t('setup:board_preview_handicap', '开局局面预览:让 {n} 子'), { n: handicap })
        : t('ladder:board_preview', '开局局面预览:空盘')}
    >
      <div className="kiosk-board__ruler kiosk-board__ruler--top">
        {cols.map((c) => <span key={`t${c}`}>{c}</span>)}
      </div>
      <div className="kiosk-board__ruler kiosk-board__ruler--left">
        {rows.map((r) => <span key={`l${r}`}>{r}</span>)}
      </div>
      <div className="kiosk-board__play">
        <GoBoardSvg size={size} black={stones} />
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
