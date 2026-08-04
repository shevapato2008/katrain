import { useCallback, useEffect, useState } from 'react';
import { Box, Typography, Button, ButtonBase, Alert, CircularProgress } from '@mui/material';
import { useNavigate } from 'react-router-dom';
import { PlayArrow } from '@mui/icons-material';
import SubPageBar from '../components/layout/SubPageBar';
import LadderRankBand from '../components/play/LadderRankBand';
import { API, type LadderMe } from '../../api';
import { formatLadderSetup } from '../../utils/ladderSetup';
import { useTranslation } from '../../hooks/useTranslation';
import { useAuth } from '../../context/AuthContext';
import { writeActiveSession } from '../utils/activeSession';

/**
 * Route: play/ai/setup/ranked — 升降级对弈 on the kiosk.
 *
 * This replaces a page that let the player pick the AI's strength on a 20k→9d
 * dropdown and then stored the game as `game_type: "ranked"`, which moved no
 * rank at all. Everything that decides the game is now server-side: the opponent
 * rung comes from the player's own ledger, and the board / ruleset / komi are
 * fixed at the conditions the rungs were calibrated under. What is left on this
 * screen is the seat and the clock.
 *
 * Layout is variant B of
 * superpowers/tracks/golaxy-ai-ladder-parity/artifacts/kiosk-ladder-setup.html:
 * horizontal bands rather than the usual 322px-console + form skeleton, because
 * a ladder game has no board setup to preview.
 */

// Kiosk clocks are short: this is a 7" terminal in a shop, not a tournament hall.
// main_time is in MINUTES (the unit `timer/main_time` is stored in).
const TIME_PRESETS = (t: (en: string, zh: string) => string) => [
    { key: 'byo', label: t('Byoyomi only 30s x3', '仅读秒'), main: 0, byo: 30, periods: 3 },
    { key: '10', label: t('10 min + 3x30s', '10分+3×30秒'), main: 10, byo: 30, periods: 3 },
    { key: '20', label: t('20 min + 3x30s', '20分+3×30秒'), main: 20, byo: 30, periods: 3 },
    { key: '30', label: t('30 min + 3x30s', '30分+3×30秒'), main: 30, byo: 30, periods: 3 },
];

const BAND_SX = {
    bgcolor: 'background.paper', border: '1px solid', borderColor: 'divider', borderRadius: '16px',
} as const;
// 12px vertical, not 16: at 1024x600 the tallest state (placed + uncertified, so
// the rank band, the net-win bar, recent form AND the blocked note are all on
// screen) overflowed the 481px content box by 43px, which put the start button
// below the fold. Measured in tests/ladder-kiosk-setup.spec.ts.
const SEG_SX = { p: '12px 20px', display: 'flex', flexDirection: 'column', justifyContent: 'center' } as const;

const SegLabel = ({ children }: { children: React.ReactNode }) => (
    <Typography sx={{ fontSize: 11, fontWeight: 700, letterSpacing: '1.5px', color: 'text.secondary', mb: '8px' }}>
        {children}
    </Typography>
);

/** Chips that share a row equally — the artifact's `.bchips`. */
function ChipRow<T extends string>({ options, value, onChange }: {
    options: { value: T; label: string }[];
    value: T;
    onChange: (v: T) => void;
}) {
    return (
        <Box sx={{ display: 'flex', gap: '7px' }}>
            {options.map((opt) => {
                const on = opt.value === value;
                return (
                    <ButtonBase
                        key={opt.value}
                        onClick={() => onChange(opt.value)}
                        sx={{
                            flex: 1, minHeight: 40, px: '6px', borderRadius: '10px', border: '1px solid',
                            borderColor: on ? 'primary.main' : 'divider',
                            bgcolor: on ? 'primary.dark' : 'var(--raise2)',
                            color: on ? 'text.primary' : 'text.secondary',
                            fontSize: 13, fontWeight: on ? 600 : 400, whiteSpace: 'nowrap',
                            '&:active': { transform: 'scale(0.96)' },
                        }}
                    >
                        {opt.label}
                    </ButtonBase>
                );
            })}
        </Box>
    );
}

const LadderSetupPage = () => {
    const navigate = useNavigate();
    const { t } = useTranslation();
    const { token } = useAuth();

    const [me, setMe] = useState<LadderMe | null>(null);
    // null while loading; 'unauthenticated' and a message string are different
    // failures and neither one is a playable page.
    const [loadError, setLoadError] = useState<string | null>(null);
    const [loading, setLoading] = useState(true);

    const [color, setColor] = useState<'B' | 'W'>('B');
    const [timeKey, setTimeKey] = useState('10');

    const [starting, setStarting] = useState(false);
    const [startError, setStartError] = useState('');

    const load = useCallback(() => {
        if (!token) {
            setMe(null);
            setLoading(false);
            setLoadError('unauthenticated');
            return;
        }
        setLoading(true);
        setLoadError(null);
        API.getLadderMe(token)
            .then((data) => {
                setMe(data);
                setLoading(false);
            })
            .catch((e) => {
                setMe(null);
                setLoading(false);
                setLoadError(e instanceof Error ? e.message : 'unavailable');
            });
    }, [token]);

    useEffect(load, [load]);

    const timePresets = TIME_PRESETS(t);
    const preset = timePresets.find((p) => p.key === timeKey) ?? timePresets[1];

    const handleStart = async () => {
        if (!token || !me?.playable) return;
        setStartError('');
        setStarting(true);
        try {
            const { session_id } = await API.createSession(token);
            await API.startLadderGame(token, {
                session_id,
                color,
                main_time_minutes: preset.main,
                byo_length_seconds: preset.byo,
                byo_periods: preset.periods,
            });
            writeActiveSession({
                kind: 'game',
                label: `${t('Ranked Game', '升降级对弈')} · ${me.next_opponent.rank_name}`,
                route: `/kiosk/play/ai/game/${session_id}`,
                ts: Date.now(),
            });
            navigate(`/kiosk/play/ai/game/${session_id}`);
        } catch (e) {
            setStartError(e instanceof Error ? e.message : t('Failed to create game', '创建对局失败'));
        } finally {
            setStarting(false);
        }
    };

    const opponent = me?.next_opponent;
    const uncertified = !!opponent && (opponent.certification_status !== 'certified' || opponent.availability !== 'available');

    return (
        <Box sx={{ display: 'flex', flexDirection: 'column', height: '100%', minHeight: 0 }}>
            <SubPageBar title={t('Ranked Game', '升降级对弈')} to="/kiosk/play" />

            {/* The scroll owner. Everything below the SubPageBar lives here, so this
                is the element that must scroll when a state with the blocked note is
                rendered at 1024x600 — see tests/ladder-kiosk-setup.spec.ts. */}
            <Box
                data-testid="ladder-setup-scroll"
                sx={{ flex: 1, minHeight: 0, overflow: 'auto', display: 'flex', flexDirection: 'column', gap: '10px', p: '12px 20px' }}
            >
                {/* Loading, signed out and failed are three different things, and none
                    of them is a playable page. Never show a placeholder rank. */}
                {loading ? (
                    <Box sx={{ ...BAND_SX, ...SEG_SX, flexDirection: 'row', alignItems: 'center', gap: 2 }}>
                        <CircularProgress size={20} />
                        <Typography sx={{ fontSize: 14, color: 'text.secondary' }}>
                            {t('ladder:loading', '正在读取你的段位…')}
                        </Typography>
                    </Box>
                ) : !me ? (
                    <Alert
                        severity={loadError === 'unauthenticated' ? 'info' : 'error'}
                        action={
                            loadError === 'unauthenticated' ? (
                                <Button color="inherit" size="small" onClick={() => navigate('/kiosk/login')}>
                                    {t('Login', '登录')}
                                </Button>
                            ) : (
                                <Button color="inherit" size="small" onClick={load}>
                                    {t('retry', '重试')}
                                </Button>
                            )
                        }
                    >
                        {loadError === 'unauthenticated'
                            ? t('ladder:need_login', '登录后才能参加升降级对弈。')
                            : t('ladder:load_failed', '读取段位失败，暂时开不了局。')}
                    </Alert>
                ) : (
                    <LadderRankBand me={me} />
                )}

                {/* 本局对手 + 我执 */}
                <Box sx={{ display: 'flex', gap: 1.5 }}>
                    <Box
                        data-testid="ladder-opponent-band"
                        sx={{
                            ...BAND_SX, flex: 1, minWidth: 0,
                            ...(uncertified && {
                                borderColor: 'rgba(224,162,74,.4)',
                                backgroundImage: 'linear-gradient(90deg, rgba(224,162,74,.08), transparent)',
                            }),
                        }}
                    >
                        <Box sx={{ ...SEG_SX, flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', gap: 2 }}>
                            <Box>
                                <SegLabel>{t('ladder:this_game_opponent', '本局对手')}</SegLabel>
                                <Typography sx={{ fontSize: 12, color: 'text.disabled', mt: '-5px' }}>
                                    {me ? formatLadderSetup(me.game_setup, t) : '—'}
                                </Typography>
                            </Box>
                            <Typography component="div" sx={{ fontSize: 30, fontWeight: 700, lineHeight: '34px', textAlign: 'right' }}>
                                {opponent?.rank_name ?? '—'}
                                {uncertified && (
                                    <Box
                                        component="span"
                                        sx={{
                                            display: 'inline-block', ml: '10px', px: '8px', py: '3px', borderRadius: '5px',
                                            fontSize: 11.5, fontWeight: 600, letterSpacing: '.5px', verticalAlign: '7px',
                                            color: 'warning.main', border: '1px solid rgba(224,162,74,.45)',
                                        }}
                                    >
                                        {t('ladder:uncertified', '未标定')}
                                    </Box>
                                )}
                            </Typography>
                        </Box>
                    </Box>

                    <Box sx={{ ...BAND_SX, width: 236, flexShrink: 0 }}>
                        <Box sx={SEG_SX}>
                            <SegLabel>{t('My Color', '我执')}</SegLabel>
                            <ChipRow
                                options={[
                                    { value: 'B' as const, label: t('Black Stone', '● 黑') },
                                    { value: 'W' as const, label: t('White Stone', '○ 白') },
                                ]}
                                value={color}
                                onChange={setColor}
                            />
                        </Box>
                    </Box>
                </Box>

                {/* 用时 — kept in every state so the layout does not reflow when the
                    ladder becomes playable while the screen is being looked at. */}
                <Box sx={BAND_SX}>
                    <Box sx={SEG_SX}>
                        <SegLabel>{t('Time Control', '用时')}</SegLabel>
                        <ChipRow
                            options={timePresets.map((p) => ({ value: p.key, label: p.label }))}
                            value={timeKey}
                            onChange={setTimeKey}
                        />
                    </Box>
                </Box>

                {me && !me.playable && (
                    <Box
                        data-testid="ladder-blocked-note"
                        sx={{
                            p: '10px 14px', borderRadius: '11px', fontSize: 13, lineHeight: 1.55,
                            color: 'warning.main', bgcolor: 'rgba(224,162,74,.08)', border: '1px solid rgba(224,162,74,.3)',
                        }}
                    >
                        {me.blocked_reason === 'engine_unavailable'
                            ? `${t('ladder:blocked_engine', '引擎当前不可用，暂时开不了局。')}${t('ladder:blocked_engine_2', '引擎恢复后即可对局。')}`
                            : `${t('ladder:blocked_uncertified', '{rank} 的棋力配置还在标定中，现在开不了局。').replace('{rank}', opponent?.rank_name ?? '')}${t('ladder:blocked_uncertified_2', '标定完成后即可对局。')}`}
                    </Box>
                )}

                {startError && <Alert severity="error">{startError}</Alert>}

                <Button
                    data-testid="ladder-start-button"
                    variant="contained"
                    fullWidth
                    // No play arrow next to "暂时开不了局": an icon that promises the
                    // action the label is refusing.
                    startIcon={me?.playable ? <PlayArrow /> : undefined}
                    disabled={!me?.playable || starting}
                    onClick={handleStart}
                    sx={{ mt: 'auto', flexShrink: 0, minHeight: 56, fontSize: '1.05rem', fontWeight: 700 }}
                >
                    {starting
                        ? t('Creating...', '创建中...')
                        : !me
                          ? t('ladder:cannot_start', '暂时开不了局')
                          : !me.playable
                            ? t('ladder:cannot_start', '暂时开不了局')
                            : me.placement
                              ? t('ladder:start_placement', '开始定级赛')
                              : t('Start Game', '开始对弈')}
                </Button>
            </Box>
        </Box>
    );
};

export default LadderSetupPage;
