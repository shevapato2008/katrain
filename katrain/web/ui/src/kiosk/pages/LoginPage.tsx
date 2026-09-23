import { useState, useEffect, type KeyboardEvent } from 'react';
import { Box, TextField, Button, Typography, Alert, CircularProgress, useTheme } from '@mui/material';
import { alpha } from '@mui/material/styles';
import { Navigate, useNavigate } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import { useTranslation } from '../../hooks/useTranslation';
import { KIOSK_SERIF } from '../theme';
import { LAUNCHER_LOGIN_URL } from '../shell/boxUrls';

// Brand lockup matches the Header (智星盒 / StellaBox) — Newsreader serif, jade console palette.
const BRAND_SERIF = KIOSK_SERIF;

// Decision B (logout-then-register): in a strict box kiosk there is no local
// auth form at all — the box identity lives solely in the HttpOnly cookie set
// by the setup-wizard. Falling through here means that cookie is absent/expired,
// so send the user to the wizard's launcher gate via a top-level navigation
// instead of rendering a dead username/password form nobody can submit.
const LoginPage = () => {
  const theme = useTheme();
  const { login, isAuthenticated, isLoading, isStrictBoxKiosk } = useAuth();
  const navigate = useNavigate();
  const { t } = useTranslation();
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (isStrictBoxKiosk) {
      window.location.href = LAUNCHER_LOGIN_URL;
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  if (isStrictBoxKiosk) {
    return (
      <Box
        sx={{
          display: 'flex',
          width: '100%',
          height: '100%',
          alignItems: 'center',
          justifyContent: 'center',
          bgcolor: 'background.default',
        }}
      >
        <CircularProgress />
      </Box>
    );
  }

  const handleLogin = async () => {
    setError('');
    setLoading(true);
    try {
      await login(username, password);
      navigate('/kiosk/play', { replace: true });
    } catch {
      setError(t('Login failed', '登录失败'));
    } finally {
      setLoading(false);
    }
  };

  const handleKeyDown = (e: KeyboardEvent) => {
    if (e.key === 'Enter' && username && !loading) handleLogin();
  };

  // 左半边与 launcher 登录页(setup-wizard `launcher.html` 的 `.auth-gate` / `.ag-*`)逐项一致:
  // 用户刚从那一屏过来,这里长得不一样就像换了个产品。数值取自板上实测(1024×600)。
  // Faint go-board grid — full-page like launcher's `.ag-goboard`; the opaque brand panel hides it on the left.
  const gridBg = {
    position: 'absolute',
    inset: 0,
    pointerEvents: 'none',
    backgroundImage:
      `linear-gradient(${theme.palette.divider} 1px, transparent 1px),` +
      `linear-gradient(90deg, ${theme.palette.divider} 1px, transparent 1px)`,
    backgroundSize: '46px 46px',
    backgroundPosition: 'center',
    opacity: 0.24,
    maskImage: 'radial-gradient(ellipse 74% 64% at 50% 44%, #000 0%, transparent 78%)',
    WebkitMaskImage: 'radial-gradient(ellipse 74% 64% at 50% 44%, #000 0%, transparent 78%)',
  } as const;

  const inputSx = { '& .MuiOutlinedInput-root': { bgcolor: 'var(--raise2)' } };

  // 已经登录的人不该停在登录页。两个构建都需要这一条:盒端会在挂载探针跑完之前
  // 就把人弹到这里(守卫等 isLoading,但 `navigate('/kiosk/login')` 那几个调用点不等),
  // 非盒端则是「cookie 还有效却手敲了 /kiosk/login」。少了它,这一屏对已登录用户
  // 也是死的 —— 表单在盒端注定抛,在非盒端要他把已经有效的密码再输一遍。
  if (!isLoading && isAuthenticated) return <Navigate to="/kiosk/play" replace />;

  return (
    <Box
      data-testid="kiosk-login-page"
      sx={{
        position: 'relative',
        display: 'flex',
        width: '100%',
        height: '100%',
        background: `radial-gradient(120% 140% at 50% -20%, #16201d 0%, ${theme.palette.background.default} 55%)`,
      }}
    >
      <Box sx={gridBg} />
      {/* ── Left: brand panel — centered lockup, enlarged mark ── */}
      <Box
        sx={{
          position: 'relative',
          flexShrink: 0,
          // launcher 的 `.ag-brand` 是 content-box:42% + 左右各 40 内边距 + 1px 边线 = 板上 511px。
          width: 'calc(42% + 81px)',
          minWidth: 381,
          maxWidth: 521,
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          px: 5,
          borderRight: '1px solid',
          borderColor: 'divider',
          background: `linear-gradient(158deg, ${theme.palette.background.paper} 0%, ${theme.palette.background.default} 82%)`,
        }}
      >
        <Box
          sx={{
            position: 'absolute',
            inset: 0,
            pointerEvents: 'none',
            background: `radial-gradient(circle 220px at 50% 42%, ${alpha(theme.palette.primary.main, 0.14)}, transparent 68%)`,
          }}
        />

        <Box sx={{ position: 'relative', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '14px' }}>
          <Box
            component="img"
            src="/assets/img/logo-white.png"
            alt="智星盒 StellaBox"
            sx={{
              width: 146,
              height: 146,
              objectFit: 'contain',
              mb: '4px',
              filter: `drop-shadow(0 0 22px ${alpha(theme.palette.primary.main, 0.32)})`,
            }}
          />
          {/* top:6px —— launcher 的衬线栈里有思源宋体(CJK),撑高了行内内容区,基线比这里低 6px;
              盒上两边都没有同一套 CJK 衬线,只能按实测对齐。用 relative 不占位,不挪 logo。 */}
          <Box sx={{ position: 'relative', top: '6px', display: 'flex', alignItems: 'baseline', gap: '12px' }}>
            {/* 不能用 `.brand-zh` 类:它写的是 `var(--font-serif)`,而那个变量只定义在 `.kiosk` 上,
                这一屏在 KioskLayout 外面 ⇒ 整条 font-family 计算期失效、退回继承的无衬线(板上实测)。 */}
            <Box
              component="span"
              sx={{
                fontFamily: `"SmartBox Brand LongCang", ${KIOSK_SERIF}`,
                fontWeight: 400,
                fontStyle: 'normal',
                fontSynthesis: 'none',
                fontSize: 48,
                lineHeight: 1,
                letterSpacing: '3px',
                color: 'text.primary',
              }}
            >
              智星盒
            </Box>
            <Typography
              component="span"
              sx={{ fontFamily: BRAND_SERIF, fontStyle: 'italic', fontWeight: 500, fontSize: 19, color: 'text.secondary' }}
            >
              StellaBox
            </Typography>
          </Box>
        </Box>
      </Box>

      {/* ── Right: sign-in form — 或者，在出厂盒子上，一扇指回 launcher 的门 ── */}
      <Box sx={{ position: 'relative', flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', p: 3 }}>
        <Box
          sx={{
            width: '100%',
            maxWidth: 380,
            bgcolor: 'background.paper',
            border: '1px solid',
            borderColor: 'divider',
            borderRadius: '16px',
            p: 3.5,
            display: 'flex',
            flexDirection: 'column',
            gap: 2,
          }}
        >
          {isStrictBoxKiosk ? (
            /*
             * 出厂盒子上这里**不能画登录表单**：`login()` 第一行就抛
             * (`AuthContext.tsx` 的 strict 分支)，后端 `POST /api/v1/auth/login` 也恒 403。
             * 画了就是一个怎么填都只会跳「登录失败」的表单 ——
             * 而这一屏在 `KioskLayout` **外面**(`KioskApp.tsx` 里两者平级)，
             * 没顶栏、没 Dock、没主页键，人进来了就出不去。
             *
             * 没把 `signed_out` 与 `identity_unavailable` 分开画(横向规范 §8.1 规则 1)
             * 是有意的：那条规则的理由是「后者用户解决不了，给登录 CTA 等于推责任」，
             * 而在盒上两种情形的动作恰好相同且都有效：回主页。launcher 跑在另一个
             * 进程(:8080)上，围棋这边挂了它照样开。分两屏只会多一个状态，
             * 不多一条出路。(AuthContext 今天也区分不了这两者。)
             */
            <>
              <Typography sx={{ fontFamily: BRAND_SERIF, fontSize: 22, fontWeight: 500 }}>
                {t('login:box_gate_title', '请在智星盒主页登录')}
              </Typography>
              <Typography sx={{ fontSize: 14, color: 'text.secondary', lineHeight: 1.9 }}>
                {t(
                  'login:box_gate_body',
                  '智星盒的账号是整台设备共用的：在主页登录一次，围棋和其他棋类模块就都是同一个身份。',
                )}
              </Typography>
              <Typography sx={{ fontSize: 13, color: 'text.disabled', lineHeight: 1.8 }}>
                {t(
                  'login:box_gate_hint',
                  '如果你刚才还在下棋，多半是这台盒子上的会话过期了 —— 回主页重新进入围棋即可，已下的棋不会丢。',
                )}
              </Typography>
              {/* 写成 `<a href>` 而不是 `onClick` —— 目标在另一个源上，
                  这是一次**整页离开**，不是本 SPA 的路由。 */}
              <Button
                fullWidth
                component="a"
                href={LAUNCHER_LOGIN_URL}
                variant="contained"
                color="primary"
                data-testid="login-go-launcher"
                sx={{ minHeight: 52, mt: 0.5, fontSize: '1rem', letterSpacing: '0.1em' }}
              >
                {t('login:box_gate_cta', '前往智星盒主页')}
              </Button>
            </>
          ) : (
          <>
          {error && <Alert severity="error">{error}</Alert>}
          <TextField
            fullWidth
            label={t('Username', '用户名')}
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            onKeyDown={handleKeyDown}
            sx={inputSx}
          />
          <TextField
            fullWidth
            label={t('Password', '密码')}
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            onKeyDown={handleKeyDown}
            sx={inputSx}
          />
          <Button
            fullWidth
            variant="contained"
            color="primary"
            onClick={handleLogin}
            disabled={loading || !username}
            sx={{ minHeight: 52, mt: 0.5, fontSize: '1rem', letterSpacing: '0.1em' }}
          >
            {loading ? t('Logging in...', '登录中...') : t('Login', '登录')}
          </Button>
          </>
          )}
        </Box>
      </Box>
    </Box>
  );
};

export default LoginPage;
