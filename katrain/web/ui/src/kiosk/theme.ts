import { createTheme } from '@mui/material';

// 共享外壳的字体表(自托管,无 CDN)。规范 §9 把字族定死:「智星盒」= 龙藏行楷、
// 其余所有中文 = 霞鹜文楷、拉丁与数字 = Geist / Newsreader、等宽 = JetBrains Mono。
// 这里 import 一次就够 —— `kiosk/theme.ts` 是整个 kiosk 应用和全部 kiosk 测试的共同入口。
import '../kiosk-shell/fonts.css';

// 三个字族栈**逐字**取自 `kiosk-shell/tokens.css:21-23`,不要在这里另起一套。
//
// 为什么不是「删掉 go-tokens.css 里覆盖 --font-* 的三行」就完事:MUI 组件的字体走的是
// `typography.fontFamily`(emotion 类),**根本不读 `var(--font-*)`**,而 kiosk 屏上绝大多数
// 文字是 MUI 渲染的。只删那三行,屏上一个字都不会变 —— 生效点在这里。
//
// 撤掉的是 `@fontsource` 那 11 行:Noto Sans SC / Noto Serif SC 在规范 §9 里是**退役字库**
// (`kiosk-shell-spec.md:648`),Hanken Grotesk 从来不在字库表里。Newsreader 和 JetBrains Mono
// 没有消失,它们由 `fonts.css` 以 "SmartBox Serif" / "SmartBox Mono" 的族名自托管同一款。
//
// 中西文靠**栈的回退**分开,不靠同族内的声明顺序:拉丁面带显式 latin `unicode-range`,
// 中文码点在那儿匹配不到面,自然落到下一个族 "SmartBox Kai"。**顺序不可调** —— 把 Kai 提前,
// 它会连 ASCII 一起抢走。
// 导出:kiosk 里有 22 处 `sx={{ fontFamily: … }}` 绕开主题直接写字体栈(标题、品牌行、
// 棋钟、SGF 文本…)。它们**不受 `typography` 管**,所以只改上面的主题它们一个都不会变 ——
// 字体闸第一次跑出来的就是这个:「智星盒」「晚上好」还落在 Songti SC 上。
// 让它们 import 同一个常量,而不是各写各的字符串。
export const KIOSK_SANS = '"SmartBox Sans", "SmartBox Kai", "Kaiti SC", system-ui, sans-serif';
export const KIOSK_SERIF = '"SmartBox Serif", "SmartBox Kai", "Kaiti SC", Georgia, serif';
export const KIOSK_MONO = '"SmartBox Mono", "SmartBox Kai", ui-monospace, monospace';

const SANS = KIOSK_SANS;
const SERIF = KIOSK_SERIF;
const MONO = KIOSK_MONO;

export const kioskTheme = createTheme({
  palette: {
    mode: 'dark',
    primary:   { main: '#58b57a', light: '#7ec994', dark: '#26463a' }, // jade / jade-deep
    secondary: { main: '#caa66f' }, // §4.3 --wood (board fallback)
    background: { default: '#0f1416', paper: '#18211f' }, // --slate / --raise
    text:      { primary: '#eef3f1', secondary: '#93a49d', disabled: '#5f716b' }, // ice/sub/dim
    divider:   '#2b3a35', // --hair
    success:   { main: '#58b57a' },
    warning:   { main: '#e0a24a' }, // THE single amber token
    error:     { main: '#e2685c' },
    info:      { main: '#5b9bd5' },
  },
  typography: {
    fontFamily: SANS,
    fontSize: 16,
    h1: { fontFamily: SERIF, fontWeight: 500 }, // brand / greeting
    h2: { fontFamily: SANS, fontWeight: 600 },
    h3: { fontFamily: SANS, fontWeight: 600 },
    h4: { fontFamily: SANS, fontWeight: 600 },
    h5: { fontFamily: SANS, fontWeight: 600 },
    h6: { fontFamily: SANS, fontWeight: 600 },
    body1: { fontFamily: SANS, fontSize: 16 },
    body2: { fontFamily: SANS, fontSize: 14 },
    button: { fontFamily: SANS, fontWeight: 600 },
    caption: { fontFamily: MONO, fontSize: 12 },
  },
  shape: { borderRadius: 12 },
  components: {
    MuiCssBaseline: {
      styleOverrides: { ':root': { '--raise2': '#1d2725' } },
    },
    MuiButton: {
      styleOverrides: {
        root: {
          textTransform: 'none' as const,
          borderRadius: '12px',
          padding: '12px 24px',
          fontSize: '1rem',
          transition: 'transform 100ms ease-out, background-color 150ms',
          '&:active': { transform: 'scale(0.96)' },
        },
      },
    },
    MuiIconButton: {
      styleOverrides: {
        root: { minWidth: 48, minHeight: 48, '&:active': { transform: 'scale(0.96)' } },
      },
    },
    MuiPaper: { styleOverrides: { root: { backgroundImage: 'none' } } },
  },
});
