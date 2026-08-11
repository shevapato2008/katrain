import { useState } from 'react';
import {
  Alert,
  Box,
  Button,
  Chip,
  CircularProgress,
  Dialog,
  DialogActions,
  DialogContent,
  DialogContentText,
  DialogTitle,
  Stack,
  Typography,
} from '@mui/material';
import {
  blockingCopy,
  blockingStateChip,
  displaceCopy,
  isResumableHere,
  isSyncRetryable,
  settlementSyncText,
} from '../../../features/aiLadder/blockingCopy';
import { useCountdown } from '../../../features/aiLadder/countdown';
import { useTranslation } from '../../../hooks/useTranslation';
import type { AiLadderBlockingGame } from '../../../features/aiLadder/types';

interface KioskAiLadderBlockingPanelProps {
  game: AiLadderBlockingGame;
  pending: boolean;
  /**
   * **必填,不是 `error?:`。** 可选 prop 看起来像契约,其实是个建议 —— 谁不传都编译得过,
   * 防御强度等于「写代码的人记得」。国象正是这么掉进去的:那块屏唯一的按钮按下去失败,
   * 错误写进了另一格的 state,屏上什么都不发生,按钮弹回可按。
   * 去掉 `?` 之后,将来有人加第三块挡局屏、忘了接错误出口,**编译当场拦住**。
   * (对照:`onRetrySettlement?` 的 `?` 保留 —— 那是真的可选**能力**。
   * 判据:可选的应该是「这块屏有没有这个能力」,不是「这块屏说不说实话」。)
   */
  error: string;
  syncRetryPending: boolean;
  onContinue: (sessionId: string) => void;
  onEndGame: (gameId: string) => void;
  /** 只有盒子有 outbox。网页直连时不传,「立即重试」就不出现。 */
  onRetrySettlement?: (gameId: string) => void;
}

/**
 * kiosk 上的「有一局挡着新局」。语义与 galaxy 那块屏逐字相同(共用
 * `features/aiLadder/blockingCopy`),视觉按 1024×600 触屏重做。
 *
 * **承重结构**:这块面板长在 kiosk 设置页那个 `overflow: hidden` 的右栏里,
 * 所以「装不下」在这里的默认后果是**裁切**,不是滚动 —— 而被裁掉的永远是最下面那一段,
 * 也就是按钮和代价行。所以这里把盒子链分成三段:
 *
 *   · 头部(对手 + 状态徽章)`flexShrink: 0`
 *   · 正文(状态说明 + 同步状态行 + 错误条)`flex: 1; minHeight: 0; overflowY: auto`
 *   · 动作(继续 / 立即重试 / 让掉·认输 + 代价行)`flexShrink: 0`
 *
 * 会溢出的只有正文,而正文全是叙述;**能改变什么的东西一个都不参与滚动**。这与 galaxy
 * 那块屏的取舍不同(1440×900 上要求整块面板一个像素都不许溢出),因为 600px 高的屏上
 * 强求不溢出只能靠删内容,而这里没有可删的 —— 每一行都在回答「按下去会发生什么」。
 *
 * **`minHeight: 0` 只有面板根上那一处是承重的**,而这句话我一开始写错了、是量出来才改的:
 * 我原本写「三处都不能省」,变异掉叙述区那处之后 9 条全绿 —— 因为 CSS 规定 flex 子项的
 * 自动最小尺寸**只对 `overflow: visible` 的项生效**,而叙述区自己带着 `overflow-y: auto`,
 * 它的 `min-height: auto` 本来就已经解析成 0 了。那处留着是防御(万一有人改掉 overflow),
 * 不是承重,别拿它当保证。
 *
 * 真正承重的是**面板根**那一处:它 `overflow: visible`,所以 `min-height: auto` 确实生效。
 * 变异掉它 ⇒「内容最多的那一格」当场红(面板长高去装内容,叙述区再没有理由滚,
 * 而长高的部分被右栏的 `overflow: hidden` 裁掉)。这条是量的,不是推的。
 */
const KioskAiLadderBlockingPanel = ({
  game,
  pending,
  error,
  syncRetryPending,
  onContinue,
  onEndGame,
  onRetrySettlement,
}: KioskAiLadderBlockingPanelProps) => {
  // blockingCopy/displaceCopy 每次 render 才查 i18n;没有这个订阅,切语言这块面板不动。
  useTranslation();
  // 举起的确认落在**哪一局**上,而不是一个裸的布尔。后台每 15 秒复查一次,弹窗开着的时候
  // 底下那一格会自己变:换成了另一局,这个 `armed` 自己就是假的(派生值,不需要 effect
  // 去追);还是同一局但状态变了,弹窗留着、而里面的每一句都从**当下**这份数据现算 ——
  // 「在下」变成「成绩未送达」时,多说的那句要从「还没下完」变成「会覆盖它真实的结果」。
  // 在按下的那一刻抄一份存起来,用户就会照着一句已经不成立的话按下不可撤销的按钮。
  const [armedGameId, setArmedGameId] = useState<string | null>(null);
  const armed = armedGameId === game.game_id;
  const remaining = useCountdown(
    game.sync?.state === 'waiting' ? game.sync.next_attempt_in_seconds : null,
  );

  const resumable = isResumableHere(game);
  const chip = blockingStateChip(game, resumable);
  const displace = displaceCopy(game);
  const canRetrySync = Boolean(onRetrySettlement)
    && game.state === 'pending_settlement'
    && isSyncRetryable(game.sync);

  return (
    <Box
      data-testid="kiosk-ladder-blocking-panel"
      sx={{ flex: 1, minHeight: 0, display: 'flex', flexDirection: 'column' }}
    >
      <Box data-testid="kiosk-ladder-blocking-header" sx={{ flexShrink: 0 }}>
        {/* **主角是「问题」,不是段位名。** 从前全屏最大的字是 `opponent_rank_name`,
            而那是**被挡住那一局**的对手段位 —— 用户会把它读成「我正要开的这局」,
            于是这块屏看起来像开局确认页,实际是在拦他。段位名降为副信息。 */}
        <Typography variant="overline" sx={{ color: 'text.secondary' }}>未完成对局</Typography>
        <Typography
          data-testid="kiosk-ladder-state-line"
          sx={{
            mt: 0.25,
            fontSize: 22,
            lineHeight: 1.2,
            fontWeight: 800,
            // 三行封顶。这句是**服务端文案**(走 i18n,换一门语言可以长几倍),而它现在住在
            // `flexShrink: 0` 的头部里 —— 不封顶就会重演档位名那个断点:12 倍长译文下头部
            // 涨到 299px、叙述区被压到 0、outbox 那一行被挤出静止帧。实测出来的,不是推的。
            display: '-webkit-box',
            WebkitLineClamp: 3,
            WebkitBoxOrient: 'vertical',
            overflow: 'hidden',
          }}
        >
          {blockingCopy(game, resumable)}
        </Typography>
        <Stack direction="row" gap={0.75} sx={{ mt: 0.75, flexWrap: 'wrap', alignItems: 'center' }}>
          <Chip size="small" label={chip.label} variant="outlined" color={chip.color} />
          <Chip
            size="small"
            label={game.ownership === 'current_device' ? '当前设备' : '其他设备'}
            variant="outlined"
          />
          <Chip size="small" label={game.user_color === 'B' ? '● 执黑' : '○ 执白'} variant="outlined" />
          {/* 段位名:副信息。两行封顶的理由见下 —— 它是服务端发的、前端不设界的字符串。 */}
          <Typography
            data-testid="kiosk-ladder-blocking-name"
            variant="body2"
            sx={{
              color: 'text.secondary',
              display: '-webkit-box',
              WebkitLineClamp: 2,
              WebkitBoxOrient: 'vertical',
              overflow: 'hidden',
              wordBreak: 'break-word',
            }}
          >
            对手 {game.opponent_rank_name}
          </Typography>
        </Stack>
      </Box>

      <Box
        data-testid="kiosk-ladder-blocking-body"
        sx={{ flex: 1, minHeight: 0, overflowY: 'auto', mt: 1.25, pr: 0.5 }}
      >
        {/* 「这是哪一局 / 为什么挡着」那句现在是标题,而标题在**不参与滚动**的头部 ——
            必需信息由此从可滚区搬进了固定区,比原来更强。代价那句在按钮下面(按下之前就说),
            所以这里只剩 outbox 实况和错误条。 */}
        {game.sync && (
          <Typography
            data-testid="kiosk-ladder-sync-line"
            variant="body2"
            sx={{
              mt: 1,
              color: game.sync.state === 'refused' || game.sync.state === 'exhausted'
                ? 'warning.main'
                : 'text.secondary',
              fontVariantNumeric: 'tabular-nums',
            }}
          >
            {settlementSyncText(game.sync, remaining)}
          </Typography>
        )}
        {/* **错误条只有三个去处,各有一种失效方式**,必须量完再选、不能默认:
              ① 钉进动作区 ⇒ 挤掉别的必需信息;
              ② 放进可滚区 ⇒ 自己可能不在第一屏;
              ③ **根本没有可滚区** ⇒ 装不下的东西不是「滚一下能看到」,是没了,用户无法恢复。
            第三种最危险,因为它**长得像第一种** —— 写代码的人以为自己做了权衡,其实没有权衡
            可做。国象那块屏实测从错误条往上每一层都 `overflow: hidden`、`sh == ch` 到顶。
            这里选的是 ②,而「② 成立」这个前提由 spec 里那条「叙述区必须真的能滚」钉着 ——
            哪天有人把 `overflowY` 改成 hidden,这个取舍就退化成 ③,而屏上什么都不会说。

            以下是量出来的取舍,不是省事:
            把它钉进动作区之后,动作区从 144px 涨到 200px、叙述区被压到 105px,于是
            `narrativeSlackPx` 从 +53 掉到 **-3**,outbox 那一行(重试几次 / 还有多久)在静止帧里
            被裁掉。而「先去重试」这句话能不能据以决定,全靠那一行;错误条只是刚按下的那个
            按钮的回执,晚半秒看到不改变任何决定。
            代价老实记在这里:最坏那一格(6 倍长译文)错误条底边比裁切线低 5px。想把这 5px
            补回来的人请先读这段 —— 钉上去会用一行必需信息换一行回执。 */}
        {error && <Alert severity="error" sx={{ mt: 1.25 }}>{error}</Alert>}
      </Box>

      {/* 能改变什么的东西全在这里,而这里不参与滚动 —— 见组件注释的承重段。 */}
      <Stack data-testid="kiosk-ladder-blocking-actions" spacing={1} sx={{ flexShrink: 0, pt: 1.25 }}>
        {resumable && (
          <Button
            variant="contained"
            size="large"
            fullWidth
            onClick={() => game.session_id && onContinue(game.session_id)}
            disabled={pending}
            startIcon={pending ? <CircularProgress size={16} color="inherit" /> : undefined}
            sx={{ minHeight: 48, py: 1, fontWeight: 800 }}
          >
            继续对局
          </Button>
        )}
        {canRetrySync && (
          // 守卫 2:站在**有在途结算的这台盒子**前的人,第一个看到的必须是「把成绩救回去」,
          // 不是「认输」。云端只知道「成绩还没到」,是排队、退避、试完了还是被拒收全在这台
          // 机器的 outbox 里 —— 而那恰好是他唯一想问的事,也是上面那行字在回答的。
          <Button
            variant="contained"
            size="large"
            fullWidth
            onClick={() => onRetrySettlement?.(game.game_id)}
            disabled={syncRetryPending}
            startIcon={syncRetryPending ? <CircularProgress size={16} color="inherit" /> : undefined}
            sx={{ minHeight: 48, py: 1, fontWeight: 800 }}
          >
            {syncRetryPending ? '正在重试…' : '立即重试'}
          </Button>
        )}
        <Box>
          <Button
            variant="outlined"
            size="large"
            fullWidth
            color={displace.color}
            onClick={() => setArmedGameId(game.game_id)}
            disabled={pending}
            // 骨架断言当场量出来的:这块屏已验收的主按钮是 `minHeight: 48, py: 1`(常态那个
            // 「开始对弈」),量出来正好 48。我原本只写 `minHeight: 46` 而没写 `py` ——
            // `size="large"` 的固有纵向 padding 把它顶到 **54px**,比常态高 6px。
            // 七寸触屏上按钮高度就是可点面积,不该因为换了内容而变;`minHeight` 单独一个
            // **管不住**它,得连 `py` 一起抄过来。
            sx={{ minHeight: 48, py: 1, fontWeight: 750 }}
          >
            {displace.button}
          </Button>
          {/* 代价写在按钮下面,不写在二次确认里 —— 写在弹窗里等于按下之后才说。 */}
          <Typography
            variant="caption"
            component="p"
            sx={{ mt: 0.5, textAlign: 'center', color: 'text.secondary', lineHeight: 1.3 }}
          >
            {displace.cost}
          </Typography>
        </Box>
      </Stack>

      <Dialog open={armed} onClose={() => setArmedGameId(null)} aria-labelledby="kiosk-ladder-exit-title">
        <DialogTitle id="kiosk-ladder-exit-title">{displace.title}</DialogTitle>
        <DialogContent>
          <DialogContentText>{displace.body}</DialogContentText>
        </DialogContent>
        <DialogActions>
          <Button autoFocus onClick={() => setArmedGameId(null)} sx={{ minHeight: 44 }}>取消</Button>
          <Button
            color={displace.color}
            disabled={pending}
            onClick={() => {
              setArmedGameId(null);
              // 打的是同一个 `/end`:记负还是什么都不记,由**服务端按那一行的状态**决定。
              // 前端只负责把后果说对 —— 让它自己选路,就等于把同一个判断又实现了一遍。
              onEndGame(game.game_id);
            }}
            sx={{ minHeight: 44 }}
          >
            {displace.confirm}
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};

export default KioskAiLadderBlockingPanel;
