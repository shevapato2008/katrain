import type { MouseEvent, ReactNode } from 'react';
import { ButtonBase, Tooltip, keyframes } from '@mui/material';

const blink = keyframes`
  0%, 100% { opacity: 1; }
  50% { opacity: 0.4; }
`;

interface ToolGridButtonProps {
  icon: ReactNode;
  /** 格子上的短标签。开关类按钮的标签**不随状态改变** —— 按下态由外观表达，
   *  跟着改文字会让格子宽度跳动，也和对局室那组开关不一致。 */
  label: string;
  /** 无障碍名。不传就用 label；只有在 label 本身说不清时才传。 */
  ariaLabel?: string;
  /**
   * 悬浮提示。不传时用可及名，且 `disabled` 下不显示（死键上挂个复读标签没有意义）。
   * 传了就**连 disabled 一起显示** —— 这一支是给「为什么这个键是灰的」准备的：
   * 那句解释恰恰只在键失效时才有用（例：领地键要有 ownership 才能按）。
   */
  tooltip?: string;
  active?: boolean;
  /** true 时按 `aria-pressed` 报告开关状态；一次性动作（撤销/重置）不要传。 */
  toggle?: boolean;
  /** 透传原生事件 —— 有的调用方要拿 currentTarget 当菜单锚点。忽略它的调用方不受影响。 */
  onClick: (event: MouseEvent<HTMLElement>) => void;
  disabled?: boolean;
  loading?: boolean;
  isDestructive?: boolean;
}

/**
 * 统一版式里棋盘右栏的工具格按钮。
 *
 * 尺寸与配色照搬设计稿冻结版（原型 `03-app.css` 的 `.tbtn` 在 `data-mode="new"` 下那一档）：
 * 四列一行、格高 54、图标 18px 在上、标签 .66rem 在下、透明底 + 1px 描边、
 * 按下态是暗玉底 + 玉色描边。原型里那几个 token 与本仓 `theme.ts` 一一对应
 * （jade #4a6b5c = primary.main，jade-d #2f4539 = primary.dark，
 *   tx2 #b8b5b0 = text.secondary，tx3 #4a4845 = text.disabled），所以这里直接用主题值，
 * 不再抄一遍十六进制。
 *
 * Fan 的裁定：「除『离开对局』这种按钮和滑轨类以外，其他按钮一律按这个方式设计」。
 * 对局室右栏那组开关（原 `RightSidebarPanel.ItemToggle`）和变化图的编辑工具条
 * （原 `BoardEditToolbar.ToolButton`）都已折叠到这里；只剩研究页的 `ResearchToolbar.ToolButton`
 * 还是一份独立实现，排在 S9 收口。
 *
 * 一处**有意不同**：这里渲染的是真的 `<button>`（`ButtonBase`），不是挂了 onClick 的 `<div>`。
 * 原因有两条：死活题页那四个控件本来就是 `Button`/`IconButton`，换成 div 是键盘可达性的倒退；
 * 而且控件账本只认得真控件，换成 div 会让它们从账本里消失 —— 闸看不见的东西等于没有闸。
 */
const ToolGridButton = ({
  icon,
  label,
  ariaLabel,
  tooltip,
  active = false,
  toggle = false,
  onClick,
  disabled = false,
  loading = false,
  isDestructive = false,
}: ToolGridButtonProps) => (
  <Tooltip title={tooltip ?? (disabled ? '' : (ariaLabel ?? label))}>
    <span style={{ display: 'flex' }}>
      <ButtonBase
        aria-label={ariaLabel ?? label}
        aria-pressed={toggle ? active : undefined}
        onClick={onClick}
        disabled={disabled}
        sx={{
          flex: 1,
          height: 54,
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          gap: '3px',
          padding: '6px 2px',
          fontSize: '0.66rem',
          lineHeight: 1.1,
          borderRadius: '8px',
          border: '1px solid',
          transition: 'background 150ms, color 150ms',
          bgcolor: active && !disabled
            ? (isDestructive ? 'rgba(225, 107, 92, 0.15)' : 'primary.dark')
            : 'transparent',
          color: disabled
            ? 'text.disabled'
            : active
              ? (isDestructive ? 'error.main' : 'text.primary')
              : (isDestructive ? 'error.main' : 'text.secondary'),
          borderColor: active && !disabled
            ? (isDestructive ? 'error.main' : 'primary.main')
            : (isDestructive ? 'rgba(225, 107, 92, 0.32)' : 'rgba(255, 255, 255, 0.10)'),
          animation: loading ? `${blink} 1s ease-in-out infinite` : 'none',
          '& .MuiSvgIcon-root': { fontSize: 18 },
          '&:hover': {
            bgcolor: isDestructive ? 'rgba(225, 107, 92, 0.12)' : 'rgba(255, 255, 255, 0.06)',
            color: isDestructive ? 'error.main' : 'text.primary',
          },
          '&.Mui-disabled': { color: 'text.disabled' },
        }}
      >
        {icon}
        <span>{label}</span>
      </ButtonBase>
    </span>
  </Tooltip>
);

export default ToolGridButton;
