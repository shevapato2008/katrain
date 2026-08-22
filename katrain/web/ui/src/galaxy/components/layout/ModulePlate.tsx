import type { ReactNode } from 'react';
import { Box, IconButton, Typography } from '@mui/material';
import ArrowBackIcon from '@mui/icons-material/ArrowBack';
import { useTranslation } from '../../../hooks/useTranslation';
import { useGameNavigation } from '../../context/GameNavigationContext';

interface ModulePlateProps {
  title: ReactNode;
  subtitle?: ReactNode;
  status?: ReactNode;
  backTo: string;
  showBack?: boolean;
  /**
   * 上一级页面的简称（「死活」「复盘」「升降级」…）。
   *
   * 2026-08-22 之前它会在页头**右侧**渲染成一个带文字的返回按钮；现在返回键一律是
   * 左上角的图标键（Fan 的裁定，见下），所以这个值不再上屏，只用来把无障碍名从泛泛的
   * 「返回」变成「返回复盘」—— 屏幕阅读器仍然听得出这一下会去哪里。
   */
  backLabel?: string;
  /**
   * 版式档位。`'rail'`（默认）是棋盘页右栏那一档：`h6`、定宽 320 里 `noWrap` 截断。
   * `'page'` 是无棋盘内容页那一档：字号照设计稿 `.cph h1`（2.125rem / 800 / -.02em，
   * 430 档降到 1.5rem），标题不截断而是 `text-wrap: balance` 换行 —— 内容区是整幅宽度，
   * 截断在这里既没必要也会丢信息。
   *
   * 两档共用**同一结构**（左上角箭头图标键 + 标题 + 状态），这正是 spec §2.4
   * 「无棋盘内容页把同一结构放在内容区顶端」要的：改这一处，两类页面一起生效。
   * 内容页的消费方是 `ContentPageHeader`，它只是这里的一层薄壳。
   */
  size?: 'rail' | 'page';
}

/**
 * 棋盘页右栏顶端的模块牌：返回键 + 标题 + 副标题 + 状态。
 *
 * **返回键在右栏的左上角**，图标键，标题跟在它右边。这是 Fan 2026-08-22 的裁定，
 * 原话「返回按钮都放到右边栏的左上角吧。不止限于复盘页面」，并授权「如果这一决定和
 * 其他文档有冲突，也把文档改了」—— 设计规范 §2.4 原来写的是「右侧显示『左箭头 + 上一级
 * 页面简称』」，已按此裁定改写。
 *
 * 改这里一处，所有消费方（升降级对局页 / 死活题页 / 复盘报告页 / 直播观战页 / 研究页）
 * 一起生效；这正是「不止限于复盘页面」要的效果。
 */
const ModulePlate = ({ title, subtitle, status, backTo, showBack = true, backLabel, size = 'rail' }: ModulePlateProps) => {
  const isPage = size === 'page';
  const { t } = useTranslation();
  const { requestNavigation } = useGameNavigation();

  return (
    <Box
      data-testid="module-plate"
      sx={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'flex-start',
        gap: 1.5,
        minWidth: 0,
        minHeight: isPage ? 48 : 52,
        px: 0,
      }}
    >
      {showBack && (
        <IconButton
          /* 有上一级简称时用 `back_to`（「返回{parent}」/「Back to {parent}」），
             没有就退回 `Back`。两个 key 都已补齐 11 种语言 —— 之前这里是硬编码的
             `返回${backLabel}`，英文界面下也会读出中文。 */
          aria-label={backLabel
            ? t('back_to', '返回{parent}').replace('{parent}', backLabel)
            : t('Back', '返回')}
          onClick={() => requestNavigation(backTo)}
          style={{ width: 40, height: 40 }}
          sx={{ flex: '0 0 40px' }}
        >
          <ArrowBackIcon />
        </IconButton>
      )}
      <Box sx={{ minWidth: 0, flex: 1 }}>
        <Typography
          component="h1"
          variant={isPage ? 'h4' : 'h6'}
          noWrap={!isPage}
          sx={isPage
            ? { fontWeight: 800, letterSpacing: '-0.02em', textWrap: 'balance', fontSize: { xs: '1.5rem', sm: '2.125rem' } }
            : undefined}
        >
          {title}
        </Typography>
        {subtitle != null && <Typography variant="body2" color="text.secondary" noWrap>{subtitle}</Typography>}
      </Box>
      {status != null && <Box sx={{ flex: 'none' }}>{status}</Box>}
    </Box>
  );
};

export default ModulePlate;
