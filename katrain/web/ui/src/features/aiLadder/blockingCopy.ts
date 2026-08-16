import { i18n } from '../../i18n';
import { formatCountdown } from './countdown';
import type { AiLadderBlockingGame, AiLadderSettlementSync } from './types';

/**
 * 「有一局挡着新局」这块面板上的每一句话 —— galaxy 和 kiosk 共用同一份。
 *
 * 两块屏视觉完全不同(1440x900 的双栏卡片 / 1024x600 的触屏),但它们说的**后果**必须
 * 逐字相同:同一个账号、同一把占位锁,按下去发生的事是同一件。曾经这几个函数只长在
 * galaxy 里,kiosk 那块屏干脆没有这一格;补 kiosk 的时候把文案抄一份过去,就等于给
 * 「按下去会发生什么」立了两个版本 —— 而 eslint 的 kiosk↛galaxy 边界保证了它们再也
 * 不会互相看见,漂了也没人会发现。
 *
 * 每句都走 `i18n.t(key, 中文)`:中文同时是源文和兜底,所以现在一个 .po 都不用改,
 * 而 kiosk 那块按语言切换的屏不会漏掉这一格。读这些字符串的组件**必须**调
 * `useTranslation()`,那个 hook 才是语言切换时让它重渲染的东西。
 */

/**
 * `ownership` 的穷尽性闸 —— union 长出第四个取值而某处分支没跟上时,`tsc` 当场红在这里
 * ("Argument of type '\"x\"' is not assignable to parameter of type 'never'")。
 *
 * ⚠️ **闸必须待在源文件里,放测试文件是假的。** `tsconfig.app.json` 的 `exclude` 列着
 * `src/**\/*.test.ts`,测试文件根本不参与类型检查;实测把同样的穷尽性检查写进
 * `blockingCopy.test.ts` 再故意漏掉一个取值,`tsc -b` 照样 exit 0。
 * (顺带:`npx tsc --noEmit` 在这个仓一个文件都不检查 —— 根 tsconfig 是 `files: []` +
 * references,而命令行 `--noEmit` 不跟 references。真正在检查的是 `npx tsc -b`。)
 *
 * **运行时不抛。** 类型是编译期的承诺,而这个字段是 Python 服务端发来的,它可以发任何
 * 字符串。抛出去会把整块面板换成白屏 —— 而这块屏正是被挡住的那个人唯一的出路,
 * 屏没了他连认输让位都做不到。所以运行时退回一句**不声称位置**的兜底,只把这件事
 * 记进控制台给排错用。
 */
const unhandledOwnership = (ownership: never, fallback: string): string => {
  console.warn('unhandled ai-ladder ownership', ownership);
  return fallback;
};

/**
 * ⚠️ **这块屏上有两根**互相独立**的轴,底下每个函数都必须先判 `state`、再判 `ownership`。**
 *
 * | 轴 | 取值 | 它决定 |
 * |---|---|---|
 * | 下过没下过 (`state`) | `reserved` / `active` / `pending_settlement` | **价钱**,以及「棋起没起来」这句事实 |
 * | 归属 (`ownership`) | `current_device` / `other_device` / `unknown` | **只决定「在哪台设备上」那一句** |
 *
 * `state` 是服务端靠心跳自己知道的,**与归属无关**;`ownership` 是两个设备身份比出来的,
 * **与下没下过无关**。所以 `unknown`(这次请求没带设备身份)**只该影响位置那一句**,
 * 不该碰到其它任何一句。
 *
 * **顺序反过来会造出一句最贵的假话。** 若哪天有人把 `ownership` 判到 `state` 前面,
 * `unknown` 就会拿到 `reserved` 那一格的文案 ——
 * 「棋盘没能在任何设备上开起来 / 让掉它不会记成绩」。而一局在另一台盒子上正下得好好的棋,
 * 在网页端**恒为** `unknown`(浏览器从不发 `X-StellaBox-Device-ID`,全仓只有
 * `remote_client.py` 那个盒子客户端发)。于是屏上会**把一局正在进行的棋说成从未发生**,
 * 还附赠一个「免费」的假承诺 —— 比单纯把位置说错更糟。
 *
 * 今天这个顺序是对的,但它是**被顺手写对的**:类型系统不管顺序,穷尽性闸也不管。
 * 守着它的只有 `blockingCopy.test.ts` 里那几条 `state 压过 ownership` 的用例。
 */

/** 状态徽章:一个词说清这一局现在是什么。 */
export const blockingStateChip = (game: AiLadderBlockingGame, resumable: boolean) => {
  // 两根轴的顺序:`state` 先判 —— 理由见上面那段。下面两个 `state` 分支不许挪到
  // `ownership` 后面去。
  // 「结算中」这三个字对送不出去的成绩是句假话 —— 没有人在结算,是送不到。
  if (game.state === 'pending_settlement') {
    return { label: i18n.t('ladder:blocking_chip_undelivered', '成绩未送达'), color: 'warning' as const };
  }
  if (game.state === 'reserved') {
    return { label: i18n.t('ladder:blocking_chip_never_started', '未开始'), color: 'default' as const };
  }
  // `resumable` 排在最前面,因为它是这几格里**唯一被证出来的**那件事:这个节点此刻真的
  // 握着那个会话。位置不确定的时候它照样成立(网页直连云端的每一局都是 `unknown`,
  // 而它们全都接得回来),所以不能让位置的不确定盖掉一件已经查实的事。
  if (resumable) {
    return { label: i18n.t('ladder:blocking_chip_playing', '对局中'), color: 'success' as const };
  }
  if (game.ownership === 'current_device') {
    return { label: i18n.t('ladder:blocking_chip_interrupted', '已中断'), color: 'warning' as const };
  }
  // **不能说「对局中」。** 云端知道的只有「预约还在」,它**不知道那台机器上棋下没下完** ——
  // 已经下完、结果卡在那台自己的发送队列里时,云端照样报 `active`。
  // 通则:描述「这台设备能不能做某事」的徽标是安全的;描述「那个远端对象是什么状态」的
  // 会变成假话。换个两种情形下都真的词,而不是加一层分支 —— 分支是可以被写错的东西。
  // (`unknown` 走同一格:它知道的只会更少,不会更多。)
  return { label: i18n.t('ladder:blocking_chip_unsettled', '未了结'), color: 'warning' as const };
};

/**
 * 这一局现在是怎么回事 —— 一句陈述,不含动作。
 *
 * 铁律:**不许声称一个证不出来的位置;证得出来就必须说。** 这块屏是被挡住的人唯一的出路,
 * 他要先知道那一局在哪,才谈得上怎么了结它。指错一台机器的代价不是「说得含糊」,
 * 是他会走开去找一台不存在的设备。
 */
export const blockingCopy = (game: AiLadderBlockingGame, resumable: boolean): string => {
  if (game.state === 'pending_settlement') {
    return i18n.t('ladder:blocking_body_undelivered', '这一局已经下完，成绩还没送到云端。');
  }
  // **这一句是两根轴里最不能被 `ownership` 碰到的一句**(理由见文件上方那段):它说的是
  // 「棋从没起来过」。`unknown` 只是没查出位置,不是没下过 —— 把这一格让给它,就是把一局
  // 正在别台进行的棋说成从未发生。`state` 判在前面,`unknown` 就永远到不了这里。
  //
  // **这句话在围棋是查得出来的,而这一点不可外借。** 围棋 `/start` 的顺序是
  // reserve → 建 session → activate → 才把 `session_id` 交给玩家,activate 失败时会话会被
  // 拆掉、玩家手上一无所有(后端 `test_a_failed_activation_hands_the_player_no_board_so_reserved_means_no_game`
  // 钉的就是这个)⇒ `reserved` 严格等于「玩家从没拿到过棋盘」。
  // **判据是「activate 挂不挂在建棋盘那一刻」,不是「大家都这么写」** —— 五子棋的
  // `reserved → active` 发生在 `record_heartbeat` 里,它的 `reserved` 里可能有人正在下,
  // 同一句话搬过去就是假的。往别家搬这句之前,先去查那一家的状态是在哪一步翻的。
  if (game.state === 'reserved') {
    return i18n.t('ladder:blocking_body_never_started', '这一局登记了，但棋盘没能开起来 —— 两边都没有人在下。');
  }
  if (resumable) {
    return i18n.t('ladder:blocking_body_unfinished', '你有一局正式对局尚未结束。');
  }
  if (game.ownership === 'current_device') {
    // **第三态。** 设备身份比对说了它就在这台上,而这台接不回来 —— 库被清过、换过盒子、
    // 重装过系统,本机那份记录没了。曾经这里写「本机的对局进程已经不在了」:进程是不是
    // 还活着,这一格根本查不到(能查到就有 `session_id`、就走上面那一格了),它只是
    // 「接不回来」的一种可能原因,被当成结论说了出来。
    //
    // 更要紧的是**别把这一格并进「另一台设备」**:两句话都通向出口,但那一句会让人
    // 离开这台机器去找第二台。四家统一说这一句。
    return i18n.t('ladder:blocking_body_no_local_record', '这一局就在这台设备上，只是本机没有它的记录。');
  }
  if (game.ownership === 'unknown') {
    // 「问到了、答案是别台」和「压根没问到」是两件事。这一格是后者:这次请求没带设备身份,
    // 一个位置都证不出来 —— 那就一个位置都不说,只说那件确实成立的事。
    return i18n.t('ladder:blocking_body_unknown_device', '这一局还没了结，但本机认不出它在哪一台设备上。');
  }
  if (game.ownership === 'other_device') {
    // 同上:「正在进行」是云端猜不出来的。它可能已经下完了,只是结果还没传上来。
    // 而这句假话偏偏是在用户要为它付一场负的那一刻说的。
    return i18n.t('ladder:blocking_body_other_device', '这一局在你的另一台设备上，还没了结。');
  }
  // 兜底那句是 `unknown` 那一句的复制:新取值同样是「没查出位置」,那就同样一个位置都别说。
  return unhandledOwnership(
    game.ownership,
    i18n.t('ladder:blocking_body_unknown_device', '这一局还没了结，但本机认不出它在哪一台设备上。'),
  );
};

/**
 * 那一格「设备」标签。三个取值各有各的词 —— **`unknown` 不许并进「其他设备」**:
 * 两块屏原来都写着 `ownership === 'current_device' ? '当前设备' : '其他设备'`,
 * 一个三值字段撞上一个二分支,多出来的那一格会静默落到「其他设备」——
 * 那正是这一轮要拆掉的那句假话,而且是以不报错的方式长回来。
 */
export const ownershipLabel = (game: AiLadderBlockingGame): string => {
  if (game.ownership === 'current_device') return i18n.t('ladder:ownership_current', '当前设备');
  if (game.ownership === 'other_device') return i18n.t('ladder:ownership_other', '其他设备');
  if (game.ownership === 'unknown') return i18n.t('ladder:ownership_unknown', '设备未知');
  return unhandledOwnership(game.ownership, i18n.t('ladder:ownership_unknown', '设备未知'));
};

/**
 * 心跳那一格的**标签**(值另算)。心跳是 origin 自己上报的,所以它永远是「那一局所在那台」
 * 的心跳;标签只负责说清那是谁 —— 位置证不出来的时候就别替它认领一台机器。
 */
export const heartbeatLabel = (game: AiLadderBlockingGame): string => {
  if (game.ownership === 'current_device') return i18n.t('ladder:heartbeat_label_current', '本机心跳');
  if (game.ownership === 'other_device') return i18n.t('ladder:heartbeat_label_other', '对方设备心跳');
  if (game.ownership === 'unknown') return i18n.t('ladder:heartbeat_label_unknown', '对局设备心跳');
  return unhandledOwnership(game.ownership, i18n.t('ladder:heartbeat_label_unknown', '对局设备心跳'));
};

export interface AiLadderDisplaceCopy {
  color: 'warning' | 'error';
  button: string;
  cost: string;
  title: string;
  confirm: string;
  body: string;
}

/**
 * 让位这件事按下去会发生什么 —— 按钮、代价、二次确认,五句话一起算,免得它们各自漂走。
 *
 * **有棋盘的那两格只有一个价钱。** 曾经这里按「成绩还在送」分过一次叉(那条什么都不记),
 * 而同一处境两个价钱会让贵的那条自然消亡:劣势局面下走另一台设备免罚,严格优于当场认输,
 * 不需要恶意、只需要看得见。2026-08-11 合成一条。
 *
 * **`reserved` 不是第二个价钱,是另一件事。** 那一格云端登记了、棋盘没能开起来,两端都
 * 还没有人拿到这盘棋。让掉它确实不记成绩;照另外两格写「记为本局负」是一句关于后果的假话,
 * 而且往贵了说 —— 用户会因此干等那 5 分钟的自动回收,或者以为自己必须先输一场。
 *
 * 成绩已在传输的那一格必须明说「会覆盖真实结果」,并把用户指回「立即重试」:那才是保住
 * 那一局的路,认输是放弃它。少了这句,用户会在不知道自己有别的选择时按下不可撤销的按钮。
 */
export const displaceCopy = (game: AiLadderBlockingGame): AiLadderDisplaceCopy => {
  // **免费的那一格,判据只能是 `state`,一个字都不许沾 `ownership`。** 这是两根轴里
  // 后果最重的一处(见文件上方那段):`reserved` 说的是「两端都还没拿到这盘棋」⇒ 让掉不记
  // 成绩。`unknown` 只是没查出位置 —— 一局在别台正下着的棋在网页端恒为 `unknown`,
  // 若它落进这里,用户会读到「不记成绩」然后免费让掉一局真棋,而后端照记一场负。
  if (game.state === 'reserved') {
    return {
      color: 'warning',
      button: i18n.t('ladder:displace_release_button', '让掉它，在这里开新局'),
      cost: i18n.t('ladder:displace_release_cost', '那一局没能开起来，让掉它不记成绩'),
      title: i18n.t('ladder:displace_release_title', '让掉那一局？'),
      confirm: i18n.t('ladder:displace_release_confirm', '确认让掉'),
      body: i18n.t(
        'ladder:displace_release_body',
        '那一局只在云端登记过，棋盘没能在任何设备上开起来。让掉它不会记成绩，也不影响升降级。',
      ),
    };
  }
  return {
    color: game.state === 'pending_settlement' ? 'warning' : 'error',
    button: i18n.t('ladder:displace_resign_button', '认输那一局，在这里开新局'),
    cost: game.state === 'active' && !heldHere(game)
      ? i18n.t('ladder:displace_resign_cost_remote', '那一局会记为本局负；它若其实已下完，真实结果会被顶掉')
      : i18n.t('ladder:displace_resign_cost', '那一局会记为本局负，并计入升降级'),
    title: i18n.t('ladder:displace_resign_title', '认输那一局？'),
    confirm: i18n.t('ladder:displace_resign_confirm', '确认认输'),
    body: displaceBody(game),
  };
};

/**
 * 这一局**此刻由这个节点亲手拿着**吗 —— 「还没下完」这句话能不能说,判据只有它。
 *
 * 曾经这里问的是 `ownership === 'current_device'`,理由是「本机的棋自己下没下完自己知道,
 * 而且真下完了状态会是 `pending_settlement`、根本到不了这一格」。那个推理成立,但它悄悄多用
 * 了一个前提:**本机那个进程还在**。前提不成立的那一格恰好存在(库被清过、盒子重启过 ——
 * 屏上那句「这一局就在这台设备上，只是本机没有它的记录」说的正是它),那时本机既看不见它
 * 的进度,也可能有一份成绩卡在自己的发送队列里没送出去。
 *
 * `session_id` 在 ⇒ 这个节点真的握着那个会话 ⇒ 进度看得见 ⇒ 「还没下完」是查出来的。
 * 不在 ⇒ 一律披露「它若其实已下完，真实结果会被顶掉」。
 */
const heldHere = (game: AiLadderBlockingGame): boolean => Boolean(game.session_id);

/**
 * 二次确认里多说的那一句 —— `active` 这一格分三种,因为**这一格实际知道什么**分三种。
 *
 * 判据:**分叉的每一侧都必须说得出「这一格实际知道什么」。** 照顾不确定的那一侧而让确定的
 * 那一侧也含糊,是另一个方向的不诚实;反过来把不确定的那格套上确定的话术,就是这块屏最贵的
 * 那种错 —— 用户照着一句证不出来的话按下不可撤销的按钮。
 */
const displaceBody = (game: AiLadderBlockingGame): string => {
  if (game.state === 'pending_settlement') {
    return i18n.t(
      'ladder:displace_resign_body_undelivered',
      '那一局已经下完了，成绩还没送到云端。认输会以一场负替换它真实的结果，并计入升降级。'
      + '若想保住那一局的成绩，请先用「立即重试」把它送上去。此操作不可撤销。',
    );
  }
  if (heldHere(game)) {
    return i18n.t(
      'ladder:displace_resign_body_active_local',
      '你还有一局正式对局没有下完。在这里开新局需要先认输那一局，它将计为本局负并计入升降级。此操作不可撤销。',
    );
  }
  if (game.ownership === 'other_device') {
    // 这条代价**消不掉,只能说出来**:发起认输的这台机器,架构上不可能看见另一台的发送队列
    // (守卫 2 只看本机 outbox)。所以它不是可以修的缺陷,是必须披露的代价。
    return i18n.t(
      'ladder:displace_resign_body_active_remote',
      '你在另一台设备上还有一局没有了结。在这里开新局需要先认输那一局，它将计为本局负并计入升降级。'
      + '如果那台设备上这局其实已经下完、结果还没传上来，那个结果会被这一场负顶掉。此操作不可撤销。',
    );
  }
  // 位置**不许在这里说** —— 它上面那一句已经按各自查得出的东西说过了(在这台但没记录 /
  // 认不出在哪台)。这一句只讲后果,而它对两格都成立:接不回来 ⇒ 看不见进度 ⇒ 必须披露。
  return i18n.t(
    'ladder:displace_resign_body_active_unheld',
    '本机接不回来这一局，也看不到它的进度。在这里开新局需要先认输它，它将计为本局负并计入升降级。'
    + '如果它其实已经下完、结果还没传上来，那个结果会被这一场负顶掉。此操作不可撤销。',
  );
};

/**
 * outbox 对这一局成绩的据实交代那一行 —— 数全部来自盒子,一个都不是前端推的。
 *
 * `remaining` 由调用方的 `useCountdown` 在**本地**走秒(它数的是时长,所以盒子的钟偏
 * 不进这个数)。数到 0 之后改说「即将重试」而不是「正在重试」:队列是每 60 秒排空一次的
 * (`SYNC_DRAIN_INTERVAL`),到期只保证「下一轮会带上它」,不保证此刻正在发。也不许停在
 * 一个 0:00 —— 那是这块屏唯一会被当成卡死的画面。
 */
export const settlementSyncText = (sync: AiLadderSettlementSync, remaining: number | null): string => {
  const counting = remaining !== null && remaining > 0;
  if (sync.state === 'refused') {
    // **HTTP 码不上屏。** 它对棋手没有信息量,却让他以为那是「更严重」的一种错误。
    // 码仍在载荷里(`sync.last_http_status`)供排错,只是不进这句话。
    // 注意这里**没有分支** —— 无论有没有码都是同一句,所以不存在「云端不给人话就整格沉默」
    // 那个洞(去码的那一刀最容易在这里把静默漏回来)。
    return i18n.t('ladder:sync_refused', '云端拒收了这一局的成绩，再试也是同一个答复。');
  }
  if (sync.state === 'exhausted') {
    return i18n
      .t('ladder:sync_exhausted', '连试 {max} 次都没送到。恢复联网后会自动继续送。')
      .replace('{max}', String(sync.max_attempts));
  }
  if (sync.state === 'waiting' && counting) {
    return i18n
      .t('ladder:sync_waiting', '重试 {n}/{max} · {countdown} 后自动重试')
      .replace('{n}', String(sync.attempt))
      .replace('{max}', String(sync.max_attempts))
      .replace('{countdown}', formatCountdown(remaining ?? 0));
  }
  if (sync.state === 'synced') {
    return i18n.t('ladder:sync_synced', '成绩已送达，正在更新段位…');
  }
  return sync.attempt > 0
    ? i18n
      .t('ladder:sync_imminent', '重试 {n}/{max} · 即将重试…')
      .replace('{n}', String(sync.attempt))
      .replace('{max}', String(sync.max_attempts))
    : i18n.t('ladder:sync_sending', '正在把成绩送到云端…');
};

/** 这一行值不值得再按一次 —— `exhausted`(网络坏了一阵)值得,`refused`(事实上被拒)不值得。 */
export const isSyncRetryable = (sync?: AiLadderSettlementSync): boolean =>
  sync?.state === 'waiting' || sync?.state === 'exhausted';

/**
 * 这一局还能不能在**这台机器上**接着下。
 *
 * 主判据是 `session_id`:它是这个节点自己发的,只在它此刻真的握着那个会话时才发
 * (云端 `_blocking_payload` / 盒子 `/status` 的本机会话核对)。**不再要求
 * `ownership === 'current_device'`** —— 那样写的话,网页直连云端的每一局(位置一律
 * `unknown`)都会恒为 false,galaxy 那块屏的「继续对局」整个消失:位置说不清,不该
 * 让一条已经查实的出路跟着消失。
 *
 * `other_device` 仍然一票否决,而这不是搭便车,是一条独立的拒绝:那台的会话不在这个
 * 节点上,一个「另一台设备 + 带着 session_id」的载荷是自相矛盾的,能拼出它的只有
 * 服务端的 bug。这一格宁可不给出路,也不拿一个接不上的 id 去调 `onContinue`。
 *
 * ⚠️ **同一个 `session_id` 在两种部署下答的是两个不同的问题 —— 读代码看不出来,所以写在这:**
 *
 * 后端 `_active_session`(`ai_ladder.py`)查的是 `app.state.session_manager._sessions`,
 * **本进程的会话表**。于是:
 * · **盒子上** = 「这台盒子的进程握着那个会话」。盒端 `/status` 会先把云端那个
 *   `session_id` 丢掉,再补上自己 pending 表里的那个 —— 一台盒子一个进程,等于「就是这台」。
 * · **云端网页版** = 「那台云主机握着那个会话」。而**所有浏览器共用同一个节点**,
 *   ⇒ 同账号另一个标签页起的局,在这个标签页上也满足条件、也会给出「继续对局」。
 *
 * **那是对的,而且不是这次改动带来的行为变更。** 网页版的会话活在服务器上、不在浏览器里,
 * 同一个账号从哪个标签页接回去都是接回同一盘棋。改动之前浏览器拿到的 `origin_device_id`
 * 和 `device_id` 都是同一个哨兵 `"cloud-local"` ⇒ 比出 `current_device` ⇒ 那时**同样**
 * 把另一个标签页的局判为可续。所以这一格的行为前后一致,变的只是它不再靠一个撒谎的哨兵。
 */
export const isResumableHere = (game: AiLadderBlockingGame): boolean =>
  game.state === 'active' && game.ownership !== 'other_device' && Boolean(game.session_id);
