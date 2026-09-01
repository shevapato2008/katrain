import { Box } from '@mui/material';

export interface SegmentedOption<T extends string> {
  value: T;
  label: string;
}

/**
 * 分段控件 —— 复盘报告右栏那两组筛选（全盘/布局/中盘/官子、双方/黑方/白方）。
 *
 * 2026-09-01 之前这两组是七个并排的 `Chip`。Fan：「全盘/布局/中盘/官子 可以做成一个
 * toggle 滑动按钮，同样 双方/黑方/白方 也可以做成一个类似的」。换成分段控件解决的是
 * 一个真问题：七个长得一样的胶囊挤在一行，**看不出它们其实是两组互不相干的筛选**，
 * 也看不出「同一组里只能选一个」。分段控件的外框把「一组」画了出来。
 *
 * 滑块用 `transform` 移动而不是改 `left`：transform 走合成层，不触发重排。
 * `prefers-reduced-motion` 下关掉过渡。
 *
 * 键盘：整条是一个 `radiogroup`，每格是 `radio`，左右键在 MUI 之外由浏览器的
 * 焦点顺序处理 —— 这里每格都是真的 `<button>`，Tab 可达、Enter/Space 可选。
 */
export default function Segmented<T extends string>({
  options,
  value,
  onChange,
  ariaLabel,
}: {
  options: readonly SegmentedOption<T>[];
  value: T;
  onChange: (v: T) => void;
  ariaLabel: string;
}) {
  const index = Math.max(0, options.findIndex((o) => o.value === value));
  return (
    <Box
      role="radiogroup"
      aria-label={ariaLabel}
      sx={{
        position: 'relative',
        display: 'inline-grid',
        gridAutoFlow: 'column',
        gridAutoColumns: '1fr',
        bgcolor: 'rgba(255,255,255,0.06)',
        borderRadius: '8px',
        p: '3px',
      }}
    >
      {/* 滑块。宽度按格数均分，位置按选中项平移 —— 两者都用百分比，
          所以栏宽一变（320 → 620）不用重新算。 */}
      <Box
        aria-hidden
        sx={{
          position: 'absolute',
          top: '3px',
          bottom: '3px',
          left: '3px',
          width: `calc((100% - 6px) / ${options.length})`,
          borderRadius: '6px',
          bgcolor: 'primary.dark',
          border: '1px solid',
          borderColor: 'primary.main',
          transform: `translateX(${index * 100}%)`,
          transition: 'transform 180ms cubic-bezier(0.4, 0, 0.2, 1)',
          '@media (prefers-reduced-motion: reduce)': { transition: 'none' },
        }}
      />
      {options.map((o) => {
        const on = o.value === value;
        return (
          <Box
            key={o.value}
            component="button"
            type="button"
            role="radio"
            aria-checked={on}
            onClick={() => onChange(o.value)}
            sx={{
              position: 'relative',
              zIndex: 1,
              border: 0,
              background: 'none',
              cursor: 'pointer',
              font: 'inherit',
              fontSize: '0.8125rem',
              fontWeight: on ? 600 : 400,
              color: on ? 'text.primary' : 'text.secondary',
              /* 32px = 规范 §4.4 的小按钮档。分段控件是筛选不是行动，用最小的那一档。 */
              height: 32,
              px: 1.5,
              borderRadius: '6px',
              whiteSpace: 'nowrap',
              transition: 'color 150ms',
              '&:hover': { color: 'text.primary' },
              '&:focus-visible': { outline: '2px solid', outlineColor: 'primary.light', outlineOffset: 1 },
            }}
          >
            {o.label}
          </Box>
        );
      })}
    </Box>
  );
}
