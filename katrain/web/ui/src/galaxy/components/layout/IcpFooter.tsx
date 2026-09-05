import { Box, Link } from '@mui/material';
import { ICP_FILING_NUMBER, MIIT_FILING_URL, shouldShowIcpFooter } from './icpFiling';

/* 首页下方的 ICP 备案号（docs/superpowers/specs/2026-08-05-icp-footer-design.md）。
 *
 * 承重说明：它是 `galaxy-root`（`height:100dvh; overflow:hidden` 的竖向 flex）的
 * 最后一个子元素、`flex:none` —— 它**从内容行手里拿走自己那点高度**，不是浮在上面，
 * 所以永远盖不住棋盘或侧栏。真浏览器 1440x900 实测：root 900 = 视口；
 * main 52–872（820 高），页脚 872–900（28 高），两者边界相等即无重叠；
 * 把页脚摘掉 main 正好长回 848（+28），证明它是「拿走高度」不是「浮在上面」；
 * 造 3000px 溢出后 main 仍滚得动（client 820 / scroll 3096 / scrollTop 走到 2276）。
 *
 * 不设 `noWrap`/省略号：备案号必须完整可见（设计稿「窄屏更正」那一条）。
 * 900 宽 + 200% 文本缩放实测：页脚长到 42.6 高、文字完整、无横向滚动。
 *
 * 移动档（`useGalaxySidebar` 报 mobile，实测 ≤768）不挂这个页脚：那一档屏幕最下沿被
 * `position:fixed` 的 `GalaxyBottomNav` 占着，页脚放进去要么被盖住、要么得让棋盘
 * 再让出 92px（页脚 28 + 底栏 64）。见 MainLayout 里的注释。 */
const IcpFooter = () => {
  if (typeof window === 'undefined' || !shouldShowIcpFooter(window.location.hostname)) return null;

  return (
    <Box
      component="footer"
      data-testid="icp-footer"
      sx={{
        flex: 'none',
        minHeight: 28,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        px: 2,
        py: 0.5,
        borderTop: '1px solid',
        borderColor: 'divider',
        bgcolor: 'background.default',
        textAlign: 'center',
      }}
    >
      <Link
        href={MIIT_FILING_URL}
        target="_blank"
        rel="noopener noreferrer"
        underline="hover"
        sx={{ color: 'text.secondary', fontSize: 12, lineHeight: 1.4 }}
      >
        {ICP_FILING_NUMBER}
      </Link>
    </Box>
  );
};

export default IcpFooter;
