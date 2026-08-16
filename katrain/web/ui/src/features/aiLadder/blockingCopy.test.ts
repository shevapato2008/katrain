import { describe, expect, it, vi } from 'vitest';
import {
  blockingCopy,
  blockingStateChip,
  displaceCopy,
  heartbeatLabel,
  isResumableHere,
  ownershipLabel,
} from './blockingCopy';
import type { AiLadderBlockingGame } from './types';

/**
 * 挡局屏上每一句话对 `ownership` 三个取值各说了什么。
 *
 * 这一格从前是布尔(`current_device | other_device`),而后端能答出「不知道」——
 * 网页直连云端时请求根本不带设备身份,没有两个 id 可比。**布尔装不下这件事**:多出来的
 * 那个取值会静默落进每个 `=== 'other_device'` 的 else,于是屏上言之凿凿地说一个
 * 它压根没查过的位置。这个文件钉的就是「三个取值各有各的话,而且互不相同」。
 */

const game = (overrides: Partial<AiLadderBlockingGame> = {}): AiLadderBlockingGame => ({
  game_id: 'game-1',
  state: 'active',
  ownership: 'unknown',
  user_color: 'B',
  opponent_rank_name: '5段',
  ...overrides,
});

/**
 * 下面每条 `it.each` 遍历的取值表。
 *
 * ⚠️ **这里没有类型关卡,别把它当成一道。** `Record<...['ownership'], true>` 写在测试文件里
 * 是死的:`tsconfig.app.json` 的 `exclude` 列着 `src/**\/*.test.ts`,测试文件根本不参与类型
 * 检查。实测 —— 把 `unknown: true` 那一行删掉,`npx tsc -b --force` 照样 exit 0。
 * (再顺带一条:`npx tsc --noEmit` 在这个仓一个文件都不检查,根 tsconfig 是 `files: []` +
 * references,而命令行 `--noEmit` 不跟 references。真正在检查的是 `npx tsc -b`。)
 *
 * 真正的穷尽性闸在 `blockingCopy.ts` 的 `unhandledOwnership(ownership: never, ...)` ——
 * 那是被检查的源文件。这张表只管**运行时**那一半:新增取值时不给它写一格期望,
 * 表就少一行,下面 `toHaveLength(3)` 那条会红,逼出一次取舍。
 */
const OWNERSHIPS: Record<AiLadderBlockingGame['ownership'], true> = {
  current_device: true,
  other_device: true,
  unknown: true,
};

const ALL_OWNERSHIPS = Object.keys(OWNERSHIPS) as AiLadderBlockingGame['ownership'][];

describe('ownership 是三值,不是布尔', () => {
  it('三个取值一个都不少 —— 少一个,下面所有 it.each 都会少跑一格而不报错', () => {
    expect(ALL_OWNERSHIPS).toHaveLength(3);
    expect(new Set(ALL_OWNERSHIPS)).toEqual(new Set(['current_device', 'other_device', 'unknown']));
  });

  it.each(ALL_OWNERSHIPS)('%s 有自己的设备标签', (ownership) => {
    expect(ownershipLabel(game({ ownership }))).toBe(
      { current_device: '当前设备', other_device: '其他设备', unknown: '设备未知' }[ownership],
    );
  });

  it('三个标签互不相同 —— `unknown` 并进「其他设备」正是要拆的那句假话', () => {
    const labels = ALL_OWNERSHIPS.map((ownership) => ownershipLabel(game({ ownership })));
    expect(new Set(labels).size).toBe(3);
  });

  it.each(ALL_OWNERSHIPS)('%s 的心跳标签不替它认领一台机器', (ownership) => {
    expect(heartbeatLabel(game({ ownership }))).toBe(
      { current_device: '本机心跳', other_device: '对方设备心跳', unknown: '对局设备心跳' }[ownership],
    );
  });
});

describe('blockingCopy —— 证不出来的位置不许说', () => {
  it('unknown:只说那件确实成立的事,一个位置都不提', () => {
    expect(blockingCopy(game({ ownership: 'unknown' }), false)).toBe(
      '这一局还没了结，但本机认不出它在哪一台设备上。',
    );
  });

  it('other_device:问到了、答案是别台', () => {
    expect(blockingCopy(game({ ownership: 'other_device' }), false)).toBe(
      '这一局在你的另一台设备上，还没了结。',
    );
  });

  it('current_device:比对说就在这台,而这台没有它的记录', () => {
    expect(blockingCopy(game({ ownership: 'current_device' }), false)).toBe(
      '这一局就在这台设备上，只是本机没有它的记录。',
    );
  });

  it('三句互不相同 —— 任何一格塌进另一格都会红', () => {
    const lines = ALL_OWNERSHIPS.map((ownership) => blockingCopy(game({ ownership }), false));
    expect(new Set(lines).size).toBe(3);
  });

  it.each(ALL_OWNERSHIPS)('%s:接得回来的时候位置让位给「还没下完」', (ownership) => {
    // `resumable` 是这几格里唯一被证出来的那件事(这个节点此刻真握着那个会话),
    // 所以它排在位置前面 —— 网页直连云端的每一局都是 `unknown`,而它们全都接得回来。
    expect(blockingCopy(game({ ownership, session_id: 's' }), true)).toBe('你有一局正式对局尚未结束。');
  });

  it.each(ALL_OWNERSHIPS)('%s:state 压过 ownership,reserved / 成绩未送达两格不谈位置', (ownership) => {
    expect(blockingCopy(game({ ownership, state: 'reserved' }), false)).toBe(
      '这一局登记了，但棋盘没能开起来 —— 两边都没有人在下。',
    );
    expect(blockingCopy(game({ ownership, state: 'pending_settlement' }), false)).toBe(
      '这一局已经下完，成绩还没送到云端。',
    );
  });
});

describe('两根轴的顺序:`state` 必须先判', () => {
  /**
   * 这一组守的不是某一句文案,是**分支顺序**本身。
   *
   * `state`(下过没下过)和 `ownership`(归属)是两根独立的轴。今天每个函数都先判 `state`
   * 再判 `ownership`,所以 `unknown` 只有在 `active` 时才到得了 —— 但**这个顺序是被顺手
   * 写对的**:类型系统不管顺序,穷尽性闸也不管。顺序一旦反过来,`unknown` 会拿到
   * `reserved` 那一格的话:「棋盘没能在任何设备上开起来」+「让掉它不会记成绩」。
   *
   * 而一局在另一台盒子上正下着的棋,在网页端**恒为** `unknown`(浏览器从不发设备头)。
   * 于是屏上会把一局正在进行的棋说成从未发生,还免费让掉它 —— 而后端照记一场负。
   * 这几条就是在守那个顺序。
   */
  it('reserved 那句「棋盘没能开起来」三个取值逐字相同 —— ownership 碰不到它', () => {
    const lines = ALL_OWNERSHIPS.map((ownership) => blockingCopy(game({ ownership, state: 'reserved' }), false));
    expect(new Set(lines)).toEqual(new Set(['这一局登记了，但棋盘没能开起来 —— 两边都没有人在下。']));
  });

  it('reserved 的「免费」承诺三个取值逐字相同 —— 这是后果最重的一格', () => {
    const copies = ALL_OWNERSHIPS.map((ownership) => displaceCopy(game({ ownership, state: 'reserved' })));
    expect(new Set(copies.map((c) => c.cost))).toEqual(new Set(['那一局没能开起来，让掉它不记成绩']));
    expect(new Set(copies.map((c) => c.body))).toEqual(new Set([
      '那一局只在云端登记过，棋盘没能在任何设备上开起来。让掉它不会记成绩，也不影响升降级。',
    ]));
    expect(new Set(copies.map((c) => c.button))).toEqual(new Set(['让掉它，在这里开新局']));
  });

  it('unknown 永远拿不到 reserved 的话 —— 反过来说:它下的是 active,不是「从没下过」', () => {
    // 顺序若反了,这两条会各自变成 reserved 那一句。
    expect(blockingCopy(game({ ownership: 'unknown', state: 'active' }), false))
      .not.toContain('棋盘没能开起来');
    expect(displaceCopy(game({ ownership: 'unknown', state: 'active' })).cost)
      .not.toContain('不记成绩');
  });

  it('active 的 unknown 必须记一场负 —— 价钱来自 state,不是位置', () => {
    expect(displaceCopy(game({ ownership: 'unknown', state: 'active' })).cost).toContain('记为本局负');
  });

  it('成绩未送达那一格同理,三个取值逐字相同', () => {
    const lines = ALL_OWNERSHIPS.map((o) => blockingCopy(game({ ownership: o, state: 'pending_settlement' }), false));
    expect(new Set(lines)).toEqual(new Set(['这一局已经下完，成绩还没送到云端。']));
  });

  /**
   * 上面几条钉的是「`reserved` 那几句不许变」;这一条钉**反面** —— 那几句**只属于**
   * `reserved`,棋盘真开过的两格里一个字都不许出现。
   *
   * 两个方向都要钉,因为它们坏的方式不同:正面挡的是「`reserved` 被 ownership 改口」,
   * 反面挡的是「一局真棋被说成从没发生」。后者更贵 —— 它同时附赠一个「不记成绩」的
   * 假承诺,而后端照记一场负。
   */
  it.each([
    ['active' as const],
    ['pending_settlement' as const],
  ])('%s:棋盘真开过 —— 三个取值都不许说「没能开起来 / 没有人在下」', (state) => {
    for (const ownership of ALL_OWNERSHIPS) {
      const line = blockingCopy(game({ ownership, state }), false);
      expect(line).not.toContain('没能开起来');
      expect(line).not.toContain('没有人在下');
      const copy = displaceCopy(game({ ownership, state }));
      expect(copy.cost).not.toContain('不记成绩');
      expect(copy.body).not.toContain('没能在任何设备上开起来');
      expect(copy.body).not.toContain('不会记成绩');
    }
  });
});

describe('blockingStateChip', () => {
  it('unknown 不冒充「对局中」—— 云端只知道预约还在', () => {
    expect(blockingStateChip(game({ ownership: 'unknown' }), false)).toEqual({
      label: '未了结',
      color: 'warning',
    });
  });

  it('other_device 同一格', () => {
    expect(blockingStateChip(game({ ownership: 'other_device' }), false)).toEqual({
      label: '未了结',
      color: 'warning',
    });
  });

  it('current_device 接不回来时才是「已中断」—— 它是唯一查得出「就在这台」的那格', () => {
    expect(blockingStateChip(game({ ownership: 'current_device' }), false)).toEqual({
      label: '已中断',
      color: 'warning',
    });
  });

  it.each(ALL_OWNERSHIPS)('%s:握着会话时一律「对局中」', (ownership) => {
    expect(blockingStateChip(game({ ownership, session_id: 's' }), true)).toEqual({
      label: '对局中',
      color: 'success',
    });
  });
});

describe('位置与代价是正交两轴', () => {
  it.each(ALL_OWNERSHIPS)('%s:价钱一个字都不随位置变', (ownership) => {
    // 三个取值下 `cost` 必须逐字相同。价钱由 `state` 决定(reserved 不记成绩 / 其余记一场负);
    // 把 `ownership` 搬去决定价钱,就是把两轴接在一起 —— 同一处境两个价钱,
    // 贵的那条会自然消亡(劣势时换台设备免罚,不需要恶意、只需要看得见)。
    expect(displaceCopy(game({ ownership, session_id: 's' })).cost).toBe('那一局会记为本局负，并计入升降级');
    expect(displaceCopy(game({ ownership, state: 'reserved' })).cost).toBe('那一局没能开起来，让掉它不记成绩');
  });

  it.each(ALL_OWNERSHIPS)('%s:看不见进度时补的是风险披露,不是另一个价钱', (ownership) => {
    // 分叉的判据是 `session_id`(看不看得见那一局的进度),不是位置。`unknown` 在这里
    // 和 `other_device` 一样拿到披露 —— 它知道的只会更少,这条风险只会更成立。
    expect(displaceCopy(game({ ownership })).cost).toBe('那一局会记为本局负；它若其实已下完，真实结果会被顶掉');
  });

  it.each(ALL_OWNERSHIPS)('%s:按钮与二次确认的措辞不随位置变', (ownership) => {
    const copy = displaceCopy(game({ ownership }));
    expect(copy.button).toBe('认输那一局，在这里开新局');
    expect(copy.confirm).toBe('确认认输');
    expect(copy.title).toBe('认输那一局？');
    expect(copy.color).toBe('error');
  });
});

describe('displaceCopy.body —— 不可撤销的那一按之前说的话', () => {
  it('unknown:不指认一台机器,但那条会被顶掉的风险一个字不能少', () => {
    expect(displaceCopy(game({ ownership: 'unknown' })).body).toBe(
      '本机接不回来这一局，也看不到它的进度。在这里开新局需要先认输它，它将计为本局负并计入升降级。'
      + '如果它其实已经下完、结果还没传上来，那个结果会被这一场负顶掉。此操作不可撤销。',
    );
  });

  it('current_device 但接不回来:走同一句 —— 位置上面已经说过了,这里只讲后果', () => {
    expect(displaceCopy(game({ ownership: 'current_device' })).body).toBe(
      displaceCopy(game({ ownership: 'unknown' })).body,
    );
  });

  it('other_device:那台的发送队列这台架构上看不见,必须点名是「另一台设备」', () => {
    expect(displaceCopy(game({ ownership: 'other_device' })).body).toBe(
      '你在另一台设备上还有一局没有了结。在这里开新局需要先认输那一局，它将计为本局负并计入升降级。'
      + '如果那台设备上这局其实已经下完、结果还没传上来，那个结果会被这一场负顶掉。此操作不可撤销。',
    );
  });

  it.each(ALL_OWNERSHIPS)('%s:握着会话时才敢说「没有下完」', (ownership) => {
    expect(displaceCopy(game({ ownership, session_id: 's' })).body).toBe(
      '你还有一局正式对局没有下完。在这里开新局需要先认输那一局，它将计为本局负并计入升降级。此操作不可撤销。',
    );
  });

  it.each(ALL_OWNERSHIPS)('%s:成绩在送的那一格三个取值同一句', (ownership) => {
    expect(displaceCopy(game({ ownership, state: 'pending_settlement' })).body).toBe(
      '那一局已经下完了，成绩还没送到云端。认输会以一场负替换它真实的结果，并计入升降级。'
      + '若想保住那一局的成绩，请先用「立即重试」把它送上去。此操作不可撤销。',
    );
  });
});

describe('isResumableHere 不搭 ownership 的便车', () => {
  it.each(ALL_OWNERSHIPS)('%s:有会话就接得回来,除非那台明说是别人的', (ownership) => {
    // 从前这里要求 `ownership === 'current_device'`。三态一上,网页直连云端的每一局都是
    // `unknown` ⇒ 恒为 false ⇒ galaxy 那块屏的「继续对局」整个消失。**位置说不清,不该
    // 让一条已经查实的出路跟着消失** —— 主判据只能是 `session_id`,它是这个节点自己发的。
    //
    // `other_device` 仍然一票否决,而这不是「搭便车」是一条独立的拒绝:那台的会话不在
    // 这个节点上,「另一台设备 + 带着 session_id」是自相矛盾的载荷,能拼出它的只有服务端
    // 的 bug。宁可不给出路,也不拿一个接不上的 id 去调 `onContinue`。
    expect(isResumableHere(game({ ownership, session_id: 's' }))).toBe(ownership !== 'other_device');
  });

  it.each(ALL_OWNERSHIPS)('%s:没有会话就接不回来', (ownership) => {
    expect(isResumableHere(game({ ownership }))).toBe(false);
  });

  it.each(ALL_OWNERSHIPS)('%s:没在下的棋一律接不回来', (ownership) => {
    expect(isResumableHere(game({ ownership, state: 'reserved', session_id: 's' }))).toBe(false);
    expect(isResumableHere(game({ ownership, state: 'pending_settlement', session_id: 's' }))).toBe(false);
  });
});

describe('服务端发来一个前端不认识的取值', () => {
  // 类型只是编译期的承诺,而这个字段来自 Python 服务端 —— 它可以发任何字符串(旧版前端
  // 撞上新版后端就是这一格)。这里钉的是**运行时**那一半:穷尽性闸不许把面板炸掉,
  // 而兜底那句不许替它认领一台机器。
  const alien = () => ({ ...game(), ownership: 'teleported' } as unknown as AiLadderBlockingGame);

  it('不抛 —— 这块屏是被挡住的人唯一的出路,炸了他连认输让位都做不到', () => {
    expect(() => ownershipLabel(alien())).not.toThrow();
    expect(() => heartbeatLabel(alien())).not.toThrow();
    expect(() => blockingCopy(alien(), false)).not.toThrow();
  });

  it('兜底一个位置都不说', () => {
    expect(blockingCopy(alien(), false)).toBe('这一局还没了结，但本机认不出它在哪一台设备上。');
    expect(ownershipLabel(alien())).toBe('设备未知');
    expect(heartbeatLabel(alien())).toBe('对局设备心跳');
  });

  it('但要留下痕迹 —— 静默兜底会让这件事永远没人知道', () => {
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => {});
    ownershipLabel(alien());
    expect(warn).toHaveBeenCalledWith('unhandled ai-ladder ownership', 'teleported');
    warn.mockRestore();
  });
});
