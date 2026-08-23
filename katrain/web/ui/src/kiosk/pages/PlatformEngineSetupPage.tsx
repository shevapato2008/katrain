import { useEffect, useMemo, useState } from 'react';
import { Box, Typography, Button, Alert, CircularProgress, ButtonBase, Menu, MenuItem, useTheme } from '@mui/material';
import { useParams, useNavigate } from 'react-router-dom';
import { PlayArrow, ChevronLeft, ChevronRight, SmartToy } from '@mui/icons-material';
import { API, type EngineLevel } from '../../api';
import { useTranslation } from '../../hooks/useTranslation';
import { useAuth } from '../../context/AuthContext';
import { KioskPagebar } from '../shell/KioskPagebar';

type Translate = (en: string, zh: string) => string;

// Board wood — the goban surface, not a UI chrome color, so it stays a local literal
// (not a theme token) even after the const-C palette reconcile below.
const WOOD = '#d8b47e';

// 让子 (handicap) options — mirrors Golaxy's 自由对弈 labels: 分先, 让先, 让2子..让9子 (no 1).
const handicapOptions = (t: Translate): { value: number; label: string }[] => [
  { value: 0, label: t('Even', '分先') },
  { value: -1, label: t('Black first', '让先') },
  { value: 2, label: t('Handicap 2', '让2子') },
  { value: 3, label: t('Handicap 3', '让3子') },
  { value: 4, label: t('Handicap 4', '让4子') },
  { value: 5, label: t('Handicap 5', '让5子') },
  { value: 6, label: t('Handicap 6', '让6子') },
  { value: 7, label: t('Handicap 7', '让7子') },
  { value: 8, label: t('Handicap 8', '让8子') },
  { value: 9, label: t('Handicap 9', '让9子') },
];

// Derived komi label (display-only; server derives the actual komi). Matches the approved
// mockup: 分先→黑贴 7.5, 让先→贴 0, 让N子→黑贴 N 子 (Golaxy app.js: komi 7.5/0/N chinese).
const komiLabel = (handicap: number, t: Translate): string => {
  if (handicap === 0) return t('Black komi 7.5', '黑贴 7.5');
  if (handicap === -1) return t('No komi', '贴 0');
  return t(`Black komi ${handicap}`, `黑贴 ${handicap} 子`);
};

const handicapShort = (handicap: number, t: Translate): string => {
  if (handicap === 0) return t('Even', '分先');
  if (handicap === -1) return t('Black first', '让先');
  return t(`Handicap ${handicap} stones`, `让 ${handicap} 子`);
};

// (col, row) of the N standard handicap star points — same placement as the backend
// (near=3, far=15, middle=9). Star points are symmetric, so orientation is irrelevant here.
const handicapPoints = (n: number): [number, number][] => {
  if (n < 2) return [];
  const near = 3, far = 15, mid = 9;
  const pts: [number, number][] = [[far, far], [near, near], [far, near], [near, far]];
  if (n % 2 === 1) pts.push([mid, mid]);
  pts.push([near, mid], [far, mid], [mid, near], [mid, far]);
  return pts.slice(0, n);
};

const PREVIEW = 300;

const BoardPreview = ({ handicap }: { handicap: number }) => {
  const N = 19, pad = 14, S = PREVIEW;
  const step = (S - pad * 2) / (N - 1);
  const pt = (i: number) => pad + i * step;
  const stars = [3, 9, 15];
  const rad = step * 0.46;
  const black = handicapPoints(handicap);
  const white: [number, number][] = handicap >= 2 ? [[16, 3]] : []; // illustrative AI 白应手

  return (
    <Box
      component="svg"
      viewBox={`0 0 ${S} ${S}`}
      sx={{ width: '100%', height: 'auto', display: 'block', borderRadius: 1, bgcolor: WOOD }}
      role="img"
      aria-label="19 路棋盘预览"
    >
      {Array.from({ length: N }).map((_, i) => (
        <g key={i}>
          <line x1={pt(0)} y1={pt(i)} x2={pt(N - 1)} y2={pt(i)} stroke="#7a5c34" strokeWidth={1} />
          <line x1={pt(i)} y1={pt(0)} x2={pt(i)} y2={pt(N - 1)} stroke="#7a5c34" strokeWidth={1} />
        </g>
      ))}
      {stars.map((r) => stars.map((c) => (
        <circle key={`s${r}-${c}`} cx={pt(c)} cy={pt(r)} r={2.6} fill="#5a4022" />
      )))}
      {black.map(([c, r], i) => (
        <circle key={`b${i}`} cx={pt(c)} cy={pt(r)} r={rad} fill="#141414" stroke="#000" strokeWidth={0.6} />
      ))}
      {white.map(([c, r], i) => (
        <circle key={`w${i}`} cx={pt(c)} cy={pt(r)} r={rad} fill="#efeae0" stroke="#9c9484" strokeWidth={0.6} />
      ))}
    </Box>
  );
};

const PlatformEngineSetupPage = () => {
  const { platform } = useParams<{ platform: string }>();
  const navigate = useNavigate();
  const { t } = useTranslation();
  const { token } = useAuth();
  const theme = useTheme();

  const [levels, setLevels] = useState<EngineLevel[]>([]);
  const [levelsLoading, setLevelsLoading] = useState(true);
  const [levelsError, setLevelsError] = useState('');

  const [level, setLevel] = useState<number | null>(null);
  const [handicap, setHandicap] = useState<number>(0);
  const [humanColor, setHumanColor] = useState<'B' | 'W' | 'nigiri'>('nigiri');

  const [hcAnchor, setHcAnchor] = useState<null | HTMLElement>(null);
  const [lvAnchor, setLvAnchor] = useState<null | HTMLElement>(null);

  const [starting, setStarting] = useState(false);
  const [startError, setStartError] = useState('');

  useEffect(() => {
    let cancelled = false;
    const fetchLevels = async () => {
      if (!platform || !token) return;
      setLevelsLoading(true);
      setLevelsError('');
      try {
        const { levels: fetched } = await API.platformEngineLevels(platform, token);
        if (cancelled) return;
        setLevels(fetched);
        // Default to a mid/weak level: prefer level_name === '1级', else first row.
        const defaultRow = fetched.find((l) => l.level_name === '1级') || fetched[0];
        if (defaultRow) setLevel(defaultRow.elo_score);
      } catch (e: any) {
        if (!cancelled) setLevelsError(e.message || t('Failed to load levels', '加载棋力等级失败'));
      } finally {
        if (!cancelled) setLevelsLoading(false);
      }
    };
    fetchLevels();
    return () => { cancelled = true; };
  }, [platform, token]);

  // Levels sorted weak→strong for the ◀ ▶ stepper.
  const sortedLevels = useMemo(
    () => [...levels].sort((a, b) => a.elo_score - b.elo_score),
    [levels],
  );
  const currentIdx = sortedLevels.findIndex((l) => l.elo_score === level);
  const currentLevel = currentIdx >= 0 ? sortedLevels[currentIdx] : null;
  const stepLevel = (delta: number) => {
    const next = currentIdx + delta;
    if (next >= 0 && next < sortedLevels.length) setLevel(sortedLevels[next].elo_score);
  };

  const currentHandicapLabel = handicapOptions(t).find((o) => o.value === handicap)?.label ?? '';
  const colorOptions = [
    { value: 'nigiri' as const, label: t('Nigiri', '猜先') },
    { value: 'B' as const, label: t('Take Black', '执黑') },
    { value: 'W' as const, label: t('Take White', '执白') },
  ];
  const colorShort = humanColor === 'nigiri' ? t('Nigiri', '猜先')
    : humanColor === 'B' ? t('Take Black', '执黑') : t('Take White', '执白');

  const boardNote = handicap >= 2
    ? t(`Preview handicap ${handicap}`, `当前：让 ${handicap} 子（黑先摆 ${handicap} 星位，AI 白先应手）`)
    : handicap === 0
      ? t('Preview even', '当前：分先（黑先行 · 黑贴 7.5）')
      : t('Preview sente', '当前：让先（黑先行 · 不贴目）');

  const handleStart = async () => {
    if (!platform || !token || level === null) return;
    setStartError('');
    setStarting(true);
    try {
      const { session_id } = await API.platformEngineStart(
        platform,
        { level, human_color: humanColor, handicap },
        token,
      );
      navigate(`/kiosk/play/cross-platform/engine/game/${session_id}`);
    } catch (e: any) {
      setStartError(e.message || t('Failed to start game', '创建对局失败'));
    } finally {
      setStarting(false);
    }
  };

  // ---- small styled control fragments (match mockup .dd / .chip / .level) ----
  const fixedDd = (cap: string, val: string) => (
    <Box sx={{
      display: 'inline-flex', alignItems: 'center', gap: 1.25, minHeight: 46, px: 1.75,
      borderRadius: 2.5, border: '1px dashed', borderColor: 'divider', bgcolor: 'var(--raise2)',
    }}>
      <Typography sx={{ color: 'text.disabled', fontSize: 13 }}>{cap}</Typography>
      <Typography sx={{ color: 'text.secondary', fontSize: 15, fontWeight: 500 }}>{val}</Typography>
    </Box>
  );

  const hint = (text: string) => (
    <Typography sx={{ color: 'text.disabled', fontSize: 12, mt: 1, width: '100%' }}>{text}</Typography>
  );

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      <KioskPagebar
        title={t('Play vs AI', '人机对弈')}
        backLabel={t('Back', '返回')}
        onBack={() => navigate('/kiosk/play/cross-platform')}
      />
      <Box sx={{ display: 'flex', flex: 1, minHeight: 0 }}>
        {/* Left: board preview console — fixed width, mirrors AiSetupPage's compact layout. */}
        <Box
          sx={{
            width: 322, flexShrink: 0, overflow: 'hidden', m: 2, mr: 0,
            bgcolor: 'background.paper', border: '1px solid', borderColor: 'divider',
            borderRadius: 3, p: 2, display: 'flex', flexDirection: 'column',
          }}
        >
          <Typography variant="overline" sx={{ color: 'text.secondary', mb: 0.5 }}>
            {t('Board preview', '盘面预览')}
          </Typography>
          <Typography sx={{ color: 'text.disabled', fontSize: 12.5, mb: 1.5 }}>{boardNote}</Typography>
          <BoardPreview handicap={handicap} />
          <Box sx={{ display: 'flex', gap: 2, mt: 1.5, fontSize: 12.5, color: 'text.secondary' }}>
            <Box component="span" sx={{ display: 'inline-flex', alignItems: 'center', gap: 0.75 }}>
              <Box sx={{ width: 12, height: 12, borderRadius: '50%', bgcolor: '#141414', boxShadow: '0 0 0 1px #000' }} />
              {t('Handicap (black)', '让子(黑)')}
            </Box>
            <Box component="span" sx={{ display: 'inline-flex', alignItems: 'center', gap: 0.75 }}>
              <Box sx={{ width: 12, height: 12, borderRadius: '50%', bgcolor: '#efeae0' }} />
              {t('AI (white)', 'AI(白)')}
            </Box>
          </Box>
        </Box>

        {/* Right: compact 2-column settings — structurally no-scroll (overflow:hidden). */}
        <Box
          data-testid="engine-setup-noscroll-root"
          sx={{ flex: 1, p: 3, overflow: 'hidden', display: 'flex', flexDirection: 'column', minHeight: 0 }}
        >
          <Typography sx={{ color: 'text.disabled', fontSize: 13, mb: 1.5 }}>
            {t('Golaxy', '星阵围棋')} · <Box component="span" sx={{ color: 'primary.light', fontWeight: 600 }}>{t('Free game', '自由对弈')}</Box>
          </Typography>

          {levelsLoading ? (
            <Box sx={{ display: 'flex', justifyContent: 'center', p: 6 }}><CircularProgress /></Box>
          ) : levelsError ? (
            <Alert severity="error">{levelsError}</Alert>
          ) : (
            <>
              <Box sx={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 2, alignContent: 'start' }}>
                {/* Board — fixed */}
                {fixedDd(t('Board', '棋盘'), t('19 lines', '19 路'))}

                {/* Handicap — dropdown trigger */}
                <ButtonBase
                  aria-label={t('Select handicap', '选择让子')}
                  onClick={(e) => setHcAnchor(e.currentTarget)}
                  sx={{
                    display: 'inline-flex', alignItems: 'center', gap: 1.25, minHeight: 46, px: 1.75,
                    borderRadius: 2.5, border: '1px solid', borderColor: 'primary.main', bgcolor: 'background.paper',
                    boxShadow: '0 0 0 1px rgba(93,130,112,.3)', justifyContent: 'space-between',
                  }}
                >
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.25 }}>
                    <Typography sx={{ color: 'text.disabled', fontSize: 13 }}>{t('Handicap', '让子')}</Typography>
                    <Typography sx={{ color: 'text.primary', fontSize: 15, fontWeight: 600 }}>{currentHandicapLabel}</Typography>
                  </Box>
                  <Typography sx={{ color: 'text.disabled', fontSize: 12 }}>▾</Typography>
                </ButtonBase>
                <Menu anchorEl={hcAnchor} open={Boolean(hcAnchor)} onClose={() => setHcAnchor(null)}>
                  {handicapOptions(t).map((o) => (
                    <MenuItem
                      key={o.value}
                      selected={o.value === handicap}
                      onClick={() => { setHandicap(o.value); setHcAnchor(null); }}
                    >
                      {o.label}
                    </MenuItem>
                  ))}
                </Menu>

                {/* Komi — fixed, derived from handicap */}
                {fixedDd(t('Komi points', '贴目'), komiLabel(handicap, t))}

                {/* Timing — fixed */}
                {fixedDd(t('Timing', '计时'), t('Untimed', '不计时'))}

                {/* Take color — segmented, spans both columns */}
                <Box sx={{ gridColumn: '1 / -1' }}>
                  <Typography sx={{ fontSize: 13, color: 'text.disabled', mb: 0.5 }}>{t('First move', '先手')}</Typography>
                  <Box sx={{ display: 'flex', gap: 1 }}>
                    {colorOptions.map((o) => {
                      const sel = humanColor === o.value;
                      return (
                        <ButtonBase
                          key={o.value}
                          onClick={() => setHumanColor(o.value)}
                          sx={{
                            flex: 1, py: 1.25, px: 1.75, borderRadius: 2.5, fontSize: 15,
                            border: '1px solid', borderColor: sel ? 'primary.main' : 'divider',
                            bgcolor: sel ? 'primary.dark' : 'background.paper', color: sel ? '#fff' : 'text.secondary',
                            fontWeight: sel ? 600 : 400, transition: 'all 100ms ease-out',
                            '&:active': { transform: 'scale(0.96)' },
                          }}
                        >
                          {o.label}
                        </ButtonBase>
                      );
                    })}
                  </Box>
                </Box>

                {/* Opponent level — stepper, spans both columns */}
                <Box sx={{ gridColumn: '1 / -1' }}>
                  <Typography sx={{ fontSize: 13, color: 'text.disabled', mb: 0.5 }}>{t('Opponent', '对手')}</Typography>
                  <Box sx={{
                    display: 'flex', alignItems: 'center', gap: 1.75, bgcolor: 'background.paper',
                    border: '1px solid', borderColor: 'divider', borderRadius: 3, p: '10px 14px', width: '100%',
                  }}>
                    <ButtonBase
                      aria-label={t('Weaker level', '降低等级')}
                      disabled={currentIdx <= 0}
                      onClick={() => stepLevel(-1)}
                      sx={{ color: 'text.secondary', borderRadius: 1.5, p: 0.5, '&.Mui-disabled': { color: 'text.disabled', opacity: 0.4 } }}
                    >
                      <ChevronLeft />
                    </ButtonBase>
                    <ButtonBase
                      aria-label={t('Choose opponent level', '选择对手等级')}
                      onClick={(e) => setLvAnchor(e.currentTarget)}
                      sx={{ display: 'flex', alignItems: 'center', gap: 1.5, flex: 1, justifyContent: 'flex-start', borderRadius: 2, py: 0.5 }}
                    >
                      <Box sx={{ width: 44, height: 44, borderRadius: 2.5, bgcolor: 'var(--raise2)', display: 'grid', placeItems: 'center', color: 'text.secondary' }}>
                        <SmartToy fontSize="small" />
                      </Box>
                      <Box sx={{ textAlign: 'left' }}>
                        <Typography sx={{ fontSize: 16, fontWeight: 600, color: 'text.primary' }}>{currentLevel?.name ?? '—'}</Typography>
                        <Typography sx={{ fontSize: 12.5, color: 'text.secondary' }}>
                          {currentLevel
                            ? `${currentLevel.level_name} · 展示Elo ${currentLevel.display_elo} · ${currentLevel.ref_rank}`
                            : ''}
                        </Typography>
                      </Box>
                    </ButtonBase>
                    <ButtonBase
                      aria-label={t('Stronger level', '提高等级')}
                      disabled={currentIdx < 0 || currentIdx >= sortedLevels.length - 1}
                      onClick={() => stepLevel(1)}
                      sx={{ color: 'text.secondary', borderRadius: 1.5, p: 0.5, '&.Mui-disabled': { color: 'text.disabled', opacity: 0.4 } }}
                    >
                      <ChevronRight />
                    </ButtonBase>
                  </Box>
                  <Menu anchorEl={lvAnchor} open={Boolean(lvAnchor)} onClose={() => setLvAnchor(null)}>
                    {sortedLevels.map((l) => (
                      <MenuItem
                        key={l.elo_score}
                        selected={l.elo_score === level}
                        onClick={() => { setLevel(l.elo_score); setLvAnchor(null); }}
                      >
                        {`${l.name} · ${l.level_name} · 展示Elo ${l.display_elo}`}
                      </MenuItem>
                    ))}
                  </Menu>
                </Box>
              </Box>

              {hint(t(
                'Handicap dropdown: even / black-first / 2..9 stones. Komi follows handicap automatically. Board 19 is Chinese-rules only; 39-level Golaxy bots.',
                '让子下拉：分先 / 让先 / 让2子…让9子。贴目随让子自动定，不单独设。19 路仅中国规则；星阵 39 级 bot。',
              ))}

              <Box sx={{ mt: 'auto', pt: 2 }}>
                {startError && <Alert severity="error" sx={{ mb: 1.5 }}>{startError}</Alert>}
                <Button
                  fullWidth
                  startIcon={<PlayArrow />}
                  disabled={starting || level === null}
                  onClick={handleStart}
                  sx={{
                    py: 2, borderRadius: 3.25, fontSize: 18, fontWeight: 650, letterSpacing: '2px', color: '#fff',
                    background: `linear-gradient(180deg, ${theme.palette.primary.main}, ${theme.palette.primary.dark})`,
                    '&:hover': { background: `linear-gradient(180deg, ${theme.palette.primary.light}, ${theme.palette.primary.main})` },
                    '&.Mui-disabled': { color: 'text.disabled', background: 'var(--raise2)' },
                  }}
                >
                  {starting ? t('Creating...', '创建中...') : t('setup:start', '开始对局')}
                </Button>
                <Typography sx={{ color: 'text.disabled', fontSize: 12.5, textAlign: 'center', mt: 1.5 }}>
                  {`${t('Chinese rules', '中国规则')} · ${handicapShort(handicap, t)} · ${komiLabel(handicap, t)} · ${t('19 lines', '19 路')} · ${t('Untimed', '不计时')} · ${colorShort}`}
                </Typography>
              </Box>
            </>
          )}
        </Box>
      </Box>
    </Box>
  );
};

export default PlatformEngineSetupPage;
