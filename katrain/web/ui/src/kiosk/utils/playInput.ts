/**
 * 「这一局落在哪儿」——**用户偏好**那一半。
 *
 * ## 为什么需要它:一个问题有三段,不是两段
 *
 * 2026-08-23(屏 02/04)第一版把「落子」画成了一格读数,理由写的是
 * 「`isVisionEnabled` 由后端给,全仓没有任何地方能让用户切」。**后半句是错的** ——
 * 做题屏早就有这颗开关(`TsumegoProblemPage.tsx` 的 `role="switch"`),而且正是稿子
 * 画的那个语义。真实情况是三段:
 *
 *   ① **这台盒子能不能** —— `visionStatus.enabled && recognitionReady`,后端说了算,只读
 *   ② **这一局想不想** —— 用户偏好,就是这个文件
 *   ③ **实际落在哪** —— ① 且 ②
 *
 * 第一版把 ② 整个抹掉了,于是屏上那格读数只答得出 ③,而 ② 在别的屏上明明存在。
 *
 * ## 为什么**不**和做题屏共用一个键
 *
 * 因为两边的默认值必须相反,而默认值是这两个偏好的**全部区别**:
 *
 *   · 做题(`kiosk_tsumego_physical`)默认 **关** —— 摆题要先把盘清空、按引导摆子,
 *     那是一件要主动选的事。
 *   · 对弈(这里)默认 **开** —— 一台标定过的盒子,盘就摆在人面前;而且这**正是今天的行为**
 *     (`GamePage` 直接拿 `isVisionEnabled` 当开关)。默认值取 `true`,这次改动对
 *     现有用户就是**纯增量**:什么都不选,和以前一模一样。
 *
 * 硬凑成一个键的话,总有一家的默认值是错的 —— 而错的那一家不会报错,只会静默地
 * 把人放到另一块盘上。**两个问题、两个默认值 ⇒ 两个键。**
 * (把两边统一成一颗「这台盒子我用实体盘」的总开关是另一个设计,登记,不在这一轮。)
 *
 * ## 可用性里为什么带上「19 路」
 *
 * 盒子上那块实体盘是 19 路的。选了 9 路或 13 路,实体盘这条路根本不成立 ——
 * 做题屏的 `physicalAvailable` 里本来就有这一条(`boardSize === 19`),对弈同理。
 */

/** localStorage 键。**和做题屏那把是两把** —— 默认值相反,理由见文件头。 */
export const PLAY_ON_BOARD_KEY = 'kiosk_play_on_board';

/**
 * 读「对弈时用实体盘」偏好。**默认 `true`** —— 那是这次改动之前的行为,
 * 不选就等于没变。读不到 localStorage(隐私模式 / 被禁)时同样回 `true`:
 * 回落到「和以前一样」,不是回落到「把人从实体盘上踢下来」。
 */
export function readPlayOnBoard(): boolean {
  try {
    return localStorage.getItem(PLAY_ON_BOARD_KEY) !== 'false';
  } catch {
    return true;
  }
}

/** 写偏好。写不进去是尽力而为 —— 这一局仍按刚选的走,只是下一局记不住。 */
export function writePlayOnBoard(v: boolean): void {
  try {
    localStorage.setItem(PLAY_ON_BOARD_KEY, v ? 'true' : 'false');
  } catch {
    /* best-effort */
  }
}

export interface PlayInputState {
  /** 设备这一段:摄像头 + 识别就绪,且这一局是 19 路。 */
  available: boolean;
  /** 用户这一段:存下来的偏好。 */
  wanted: boolean;
  /** 两段都成立才为真 —— **屏上那两段控件选中的就是它**,不是 `wanted`。 */
  onBoard: boolean;
  /**
   * 「实体盘」为什么现在选不了。`null` = 选得了(或者已经选上了)。
   * **灰而不说原因**是这套稿子在别处专门骂过的事。
   */
  reason: 'noCamera' | 'notNineteen' | null;
}

/**
 * 把三段合成一次。`visionEnabled` 传 `useVision().isVisionEnabled`。
 *
 * ⚠️ **选中态取 `onBoard`,不取 `wanted`。** 开局设置屏那块盘画的是「按下按钮后**真会
 * 出现**的局面」,同一屏上的控件也得说同一件事:偏好留着(调回 19 路它自己就回来了),
 * 但**这一局到底落在哪儿**只有 `onBoard` 答得对。显示 `wanted` 会让屏上写着「实体盘」
 * 而这一局其实下在屏幕上。
 */
export function playInputState(visionEnabled: boolean, boardSize: number): PlayInputState {
  const wanted = readPlayOnBoard();
  const reason = !visionEnabled ? 'noCamera' as const
    : boardSize !== 19 ? 'notNineteen' as const
      : null;
  const available = reason === null;
  return { available, wanted, onBoard: wanted && available, reason };
}
