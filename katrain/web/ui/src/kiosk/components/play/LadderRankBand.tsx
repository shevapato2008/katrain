import { Box, Typography } from '@mui/material';
import type { LadderMe } from '../../../api';
import { useTranslation } from '../../../hooks/useTranslation';

/**
 * 你的段位 — the top band of the kiosk 升降级对弈 setup page.
 *
 * Purely presentational; every value comes from `GET /api/ladder/me`. The
 * opponent rung is decided server-side and there is deliberately no control here
 * that could pick an easier one — that is what makes the promotion ledger mean
 * anything.
 *
 * Horizontal rather than the galaxy card's tall column: the kiosk screen is a
 * 1024x600 landscape panel with no board preview to fill a left rail, so the same
 * content laid out vertically leaves ~180px of void (see
 * superpowers/tracks/golaxy-ai-ladder-parity/artifacts/kiosk-ladder-setup.html,
 * variants A vs B). Sibling of galaxy's LadderRankCard rather than a shared
 * component: kiosk code may not import from src/galaxy/**, and the two layouts
 * agree on nothing but the words.
 *
 * Two shapes, one band:
 *  - placement in progress (`me.placement !== null`) → the 5-game binary search
 *  - placed → the rung rail, the net-win bar, and recent form
 */

// Kiosk greys with no palette slot (theme.ts covers jade/amber/ice/sub/dim but
// not the rail, the unlit bar cell, or the zero tick).
const C = {
    rail: '#33433d',
    segOff: '#2f3d38',
    zero: '#4e605a',
    stepOff: '#45534e',
};

const SEG_SX = { p: '12px 20px', display: 'flex', flexDirection: 'column', justifyContent: 'center' } as const;

const SegLabel = ({ children }: { children: React.ReactNode }) => (
    <Typography sx={{ fontSize: 11, fontWeight: 700, letterSpacing: '1.5px', color: 'text.secondary', mb: '8px' }}>
        {children}
    </Typography>
);

/** The tier above, the one you stand on, and the one below, threaded on one rail. */
const RungRail = ({ above, now, below }: { above: string | null; now: string; below: string | null }) => (
    <Box sx={{ position: 'relative', pl: '24px' }}>
        <Box sx={{ position: 'absolute', left: '4px', top: '9px', bottom: '9px', width: '2px', bgcolor: C.rail }} />
        <Typography sx={{ fontSize: 14, color: 'text.disabled', lineHeight: '21px', letterSpacing: '.5px' }}>
            {above ?? ' '}
        </Typography>
        <Box sx={{ position: 'relative', my: '2px' }}>
            <Box
                sx={{
                    position: 'absolute', left: '-24px', top: '12px', width: '11px', height: '11px',
                    borderRadius: '50%', bgcolor: 'primary.main', boxShadow: '0 0 0 4px rgba(88,181,122,.20)',
                }}
            />
            <Typography sx={{ fontSize: 31, fontWeight: 700, lineHeight: '38px', letterSpacing: '.5px' }}>
                {now}
            </Typography>
        </Box>
        <Typography sx={{ fontSize: 14, color: 'text.disabled', lineHeight: '21px', letterSpacing: '.5px' }}>
            {below ?? ' '}
        </Typography>
    </Box>
);

/**
 * Net wins — the only thing that moves you a rung. `threshold` cells each side of
 * a zero tick, filled from the centre outward.
 */
export const NetWinBar = ({ netWins, threshold }: { netWins: number; threshold: number }) => {
    const cell = (side: -1 | 1, i: number) => {
        // i counts outward from the centre, 0-based.
        const lit = side > 0 ? netWins > i : netWins < -i;
        return (
            <Box
                key={`${side}-${i}`}
                sx={{ flex: 1, borderRadius: '3px', bgcolor: lit ? (side > 0 ? 'primary.main' : 'warning.main') : C.segOff }}
            />
        );
    };
    return (
        <Box sx={{ display: 'flex', alignItems: 'stretch', height: '14px', gap: '5px', maxWidth: 340 }}>
            {Array.from({ length: threshold }, (_, i) => cell(-1, threshold - 1 - i))}
            <Box sx={{ width: '2px', flex: 'none', bgcolor: C.zero, borderRadius: '1px', my: '-4px', mx: '4px' }} />
            {Array.from({ length: threshold }, (_, i) => cell(1, i))}
        </Box>
    );
};

/** The 5-game binary placement. A real sequence, so the step numbering earns its place. */
export const PlacementSteps = ({ done, total }: { done: number; total: number }) => (
    <Box sx={{ display: 'flex', alignItems: 'center', maxWidth: 420, mt: '2px' }}>
        {Array.from({ length: total }, (_, i) => {
            const state = i < done ? 'done' : i === done ? 'now' : 'todo';
            return (
                <Box key={i} sx={{ display: 'contents' }}>
                    {i > 0 && <Box sx={{ height: '2px', flex: 1, bgcolor: i <= done ? 'primary.main' : C.segOff }} />}
                    <Box
                        sx={{
                            width: '14px', height: '14px', borderRadius: '50%', flex: 'none', border: '2px solid',
                            borderColor: state === 'done' ? 'primary.main' : state === 'now' ? 'text.primary' : C.stepOff,
                            bgcolor: state === 'done' ? 'primary.main' : state === 'now' ? 'text.primary' : 'transparent',
                            boxShadow: state === 'now' ? '0 0 0 4px rgba(88,181,122,.25)' : 'none',
                        }}
                    />
                </Box>
            );
        })}
    </Box>
);

const LadderRankBand = ({ me }: { me: LadderMe }) => {
    const { t } = useTranslation();
    const placing = me.placement !== null;

    return (
        <Box
            data-testid="ladder-rank-band"
            sx={{
                display: 'flex', bgcolor: 'background.paper', border: '1px solid', borderColor: 'divider',
                borderRadius: '16px', '& > * + *': { borderLeft: '1px solid', borderColor: 'divider' },
            }}
        >
            {placing ? (
                <>
                    <Box sx={{ ...SEG_SX, width: 262, flex: 'none' }}>
                        <SegLabel>{t('ladder:placement', '定级赛')}</SegLabel>
                        <Typography sx={{ fontSize: 29, fontWeight: 700, lineHeight: '34px' }}>
                            {t('ladder:placement_game_n', '第 {n} 局').replace('{n}', String(me.placement!.games_done + 1))}
                            <Box component="span" sx={{ fontSize: 14, color: 'text.disabled', fontWeight: 400, ml: '7px' }}>
                                {t('ladder:placement_of_total', '/ 共 {n} 局').replace('{n}', String(me.placement!.games_total))}
                            </Box>
                        </Typography>
                    </Box>
                    <Box sx={{ ...SEG_SX, flex: 1, minWidth: 0 }}>
                        <SegLabel>{t('ladder:placement_progress', '进度')}</SegLabel>
                        <PlacementSteps done={me.placement!.games_done} total={me.placement!.games_total} />
                        <Typography sx={{ fontSize: 11.5, color: 'text.disabled', mt: '12px' }}>
                            {t('ladder:placement_note', '每一局的胜负都会缩小范围。')}
                            {/* Both keys are whole sentences ending in 。 — joining them with
                                a middle dot produced "范围。 · 再打". They sit next to each
                                other unseparated instead, which reads correctly in any
                                language whose sentences carry their own terminator. */}
                            {/* "再打 N 局" counts the game you are about to start; "还剩 N 局"
                                leaves that ambiguous. N is games_total - games_done. */}
                            {t('ladder:placement_left', '再打 {n} 局定下你的段位。').replace(
                                '{n}',
                                String(me.placement!.games_total - me.placement!.games_done),
                            )}
                        </Typography>
                    </Box>
                </>
            ) : (
                <>
                    <Box sx={{ ...SEG_SX, width: 262, flex: 'none' }}>
                        <SegLabel>{t('ladder:your_rank', '你的段位')}</SegLabel>
                        <RungRail
                            above={me.rung_above?.rank_name ?? null}
                            now={me.rank_name!}
                            below={me.rung_below?.rank_name ?? null}
                        />
                    </Box>

                    <Box sx={{ ...SEG_SX, flex: 1, minWidth: 0 }}>
                        <SegLabel>{t('ladder:net_wins', '净胜')}</SegLabel>
                        <Box sx={{ display: 'flex', alignItems: 'baseline', gap: '10px', mb: '9px' }}>
                            <Typography
                                data-testid="ladder-net-wins"
                                sx={{
                                    fontSize: 23, fontWeight: 700, lineHeight: '23px',
                                    color: me.net_wins < 0 ? 'warning.main' : 'primary.main',
                                }}
                            >
                                {me.net_wins > 0 ? `+${me.net_wins}` : me.net_wins}
                            </Typography>
                            <Typography sx={{ fontSize: 12.5, color: 'text.primary' }}>
                                {me.net_wins < 0 && me.rung_below
                                    ? t('ladder:to_demote', '再负 {n} 局降 {rank}')
                                          .replace('{n}', String(me.threshold + me.net_wins))
                                          .replace('{rank}', me.rung_below.rank_name)
                                    : me.rung_above
                                      ? t('ladder:to_promote', '再胜 {n} 局升 {rank}')
                                            .replace('{n}', String(me.threshold - me.net_wins))
                                            .replace('{rank}', me.rung_above.rank_name)
                                      : t('ladder:top_rung', '已是最高档')}
                            </Typography>
                        </Box>
                        <NetWinBar netWins={me.net_wins} threshold={me.threshold} />
                        <Box
                            sx={{
                                display: 'flex', justifyContent: 'space-between', maxWidth: 340,
                                mt: '7px', fontSize: 11, color: 'text.disabled',
                            }}
                        >
                            <span>{t('ladder:demote_one', '降一档')}</span>
                            <span>{t('ladder:promote_one', '升一档')}</span>
                        </Box>
                    </Box>

                    <Box sx={{ ...SEG_SX, width: 230, flex: 'none' }}>
                        <SegLabel>
                            {t('ladder:recent_n', '最近 {n} 局').replace('{n}', String(me.recent.length))}
                        </SegLabel>
                        {me.recent.length > 0 ? (
                            <>
                                {/* Words, not dots: a row of dots reads as a progress meter, and
                                    3 wins + 2 losses does NOT promote you. */}
                                <Box sx={{ display: 'flex', gap: '11px', fontSize: 16 }}>
                                    {me.recent.map((g, i) => (
                                        <Box
                                            component="span"
                                            key={i}
                                            sx={{ color: g.won ? 'primary.main' : 'text.disabled', fontWeight: g.won ? 600 : 400 }}
                                        >
                                            {g.won ? t('ladder:win', '胜') : t('ladder:loss', '负')}
                                        </Box>
                                    ))}
                                </Box>
                                <Typography sx={{ fontSize: 11.5, color: 'text.disabled', mt: '9px' }}>
                                    {t('ladder:recent_note', '只统计升降级对弈')}
                                </Typography>
                            </>
                        ) : (
                            <Typography sx={{ fontSize: 12.5, color: 'text.disabled' }}>
                                {t('ladder:recent_none', '还没有已结算的对局')}
                            </Typography>
                        )}
                    </Box>
                </>
            )}
        </Box>
    );
};

export default LadderRankBand;
