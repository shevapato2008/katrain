import { Box, Paper, Typography, Divider } from '@mui/material';
import type { LadderMe } from '../../../api';
import { useTranslation } from '../../../hooks/useTranslation';

/**
 * The 升降级对弈 rank card — the whole right-hand column of the rated setup page.
 *
 * Purely presentational: every value comes from `GET /api/ladder/me`. The opponent
 * rung is decided server-side and is NOT selectable here; that is what makes the
 * promotion ledger meaningful, so this component deliberately offers no control
 * over it.
 *
 * Two states, one card:
 *  - placement in progress (`me.rung === null`) → the 5-game binary search
 *  - placed → the rung rail, the net-win bar, recent form, and this game's opponent
 *
 * `me.playable === false` renders honestly: the reason is shown and the caller
 * disables the start button. There is no fallback to another AI.
 */

// Zen Precision tokens (katrain/web/ui/src/theme.ts + styles/theme.css). Written
// literally rather than through the palette because several of these (fg-3,
// rail grey, the amber wash) have no MUI palette slot.
const C = {
    fg: '#f5f3f0',
    fg2: '#b8b5b0',
    fg3: '#7a7772',
    fgOff: '#4a4845',
    jade: '#4a6b5c',
    jadeLt: '#5d8270',
    warn: '#e89639',
    rail: '#3a3a3a',
    segOff: '#333',
    zero: '#5a5754',
    divider: 'rgba(255,255,255,0.05)',
};

const Rule = () => <Divider sx={{ my: '26px', borderColor: C.divider }} />;

/** The tier above, the one you stand on, and the one below, threaded on one rail. */
const RungRail = ({ above, now, below }: { above: string | null; now: string; below: string | null }) => (
    <Box sx={{ mt: '20px', position: 'relative', pl: '26px' }}>
        <Box sx={{ position: 'absolute', left: '4px', top: '12px', bottom: '12px', width: '2px', bgcolor: C.rail }} />
        <Typography sx={{ fontSize: '17.14px', color: C.fg3, letterSpacing: '.5px', lineHeight: '26px' }}>
            {above ?? ' '}
        </Typography>
        <Box sx={{ position: 'relative', my: '4px' }}>
            <Box
                sx={{
                    position: 'absolute', left: '-26px', top: '17px', width: '11px', height: '11px',
                    borderRadius: '50%', bgcolor: C.jadeLt, boxShadow: `0 0 0 4px rgba(93,130,112,.22)`,
                }}
            />
            <Typography sx={{ fontSize: '36px', fontWeight: 700, color: C.fg, lineHeight: '46px' }}>{now}</Typography>
        </Box>
        <Typography sx={{ fontSize: '17.14px', color: C.fg3, letterSpacing: '.5px', lineHeight: '26px' }}>
            {below ?? ' '}
        </Typography>
    </Box>
);

/**
 * Net wins — the ONLY thing that moves you a rung, so it carries the visual
 * weight. `threshold` segments each side of a zero tick; filled from the centre
 * outward toward the current value.
 */
const NetWinBar = ({ netWins, threshold }: { netWins: number; threshold: number }) => {
    const cell = (side: -1 | 1, i: number) => {
        // i counts outward from the centre, 0-based.
        const lit = side > 0 ? netWins > i : netWins < -i;
        return (
            <Box
                key={`${side}-${i}`}
                sx={{
                    flex: 1, borderRadius: '3px',
                    bgcolor: lit ? (side > 0 ? C.jadeLt : C.warn) : C.segOff,
                }}
            />
        );
    };
    const left = Array.from({ length: threshold }, (_, i) => cell(-1, threshold - 1 - i));
    const right = Array.from({ length: threshold }, (_, i) => cell(1, i));
    return (
        <Box sx={{ display: 'flex', alignItems: 'stretch', height: '16px', gap: '5px' }}>
            {left}
            <Box sx={{ width: '2px', flex: 'none', bgcolor: C.zero, borderRadius: '1px', my: '-4px', mx: '5px' }} />
            {right}
        </Box>
    );
};

/** The 5-game binary placement. A real sequence, so the step numbering earns its place. */
const PlacementSteps = ({ done, total }: { done: number; total: number }) => (
    <Box sx={{ display: 'flex', alignItems: 'center', m: '20px 0 6px' }}>
        {Array.from({ length: total }, (_, i) => {
            const state = i < done ? 'done' : i === done ? 'now' : 'todo';
            return (
                <Box key={i} sx={{ display: 'contents' }}>
                    {i > 0 && (
                        <Box sx={{ height: '2px', flex: 1, bgcolor: i <= done ? C.jadeLt : C.segOff }} />
                    )}
                    <Box
                        sx={{
                            width: '13px', height: '13px', borderRadius: '50%', flex: 'none', border: '2px solid',
                            borderColor: state === 'done' ? C.jadeLt : state === 'now' ? C.fg : C.fgOff,
                            bgcolor: state === 'done' ? C.jadeLt : state === 'now' ? C.fg : 'transparent',
                            boxShadow: state === 'now' ? '0 0 0 4px rgba(93,130,112,.25)' : 'none',
                        }}
                    />
                </Box>
            );
        })}
    </Box>
);

const LadderRankCard = ({ me }: { me: LadderMe }) => {
    const { t } = useTranslation();
    const placing = me.placement !== null;
    const opp = me.next_opponent;
    const uncertified = opp.certification_status !== 'certified' || opp.availability !== 'available';

    return (
        <Paper sx={{ p: 4, borderRadius: 4 }}>
            <Typography variant="h6" gutterBottom>
                {placing ? t('ladder:placement', '定级赛') : t('ladder:your_rank', '你的段位')}
            </Typography>

            {placing ? (
                <>
                    <Box sx={{ mt: '18px' }}>
                        <Typography component="span" sx={{ fontSize: '30px', fontWeight: 700 }}>
                            {t('ladder:placement_game_n', '第 {n} 局').replace('{n}', String(me.placement!.games_done + 1))}
                        </Typography>
                        <Typography component="span" sx={{ fontSize: '17.14px', color: C.fg3, ml: '6px' }}>
                            {t('ladder:placement_of_total', '/ 共 {n} 局').replace('{n}', String(me.placement!.games_total))}
                        </Typography>
                    </Box>
                    <PlacementSteps done={me.placement!.games_done} total={me.placement!.games_total} />
                    <Typography sx={{ fontSize: '13.7px', color: C.fg3, mt: '14px', lineHeight: 1.6 }}>
                        {t('ladder:placement_note', '每一局的胜负都会缩小范围。')}
                        <br />
                        {/* "再打 N 局" counts the game you are about to start; "还剩 N 局"
                            leaves that ambiguous. N is games_total - games_done. */}
                        {t('ladder:placement_left', '再打 {n} 局定下你的段位。').replace(
                            '{n}',
                            String(me.placement!.games_total - me.placement!.games_done),
                        )}
                    </Typography>
                </>
            ) : (
                <>
                    <RungRail
                        above={me.rung_above?.rank_name ?? null}
                        now={me.rank_name!}
                        below={me.rung_below?.rank_name ?? null}
                    />

                    <Rule />

                    <Box sx={{ display: 'flex', alignItems: 'baseline', gap: '10px', mb: '12px' }}>
                        <Typography sx={{ fontSize: '13.7px', color: C.fg2, letterSpacing: '.5px' }}>
                            {t('ladder:net_wins', '净胜')}
                        </Typography>
                        <Typography
                            sx={{
                                fontSize: '26px', fontWeight: 700, lineHeight: '26px',
                                color: me.net_wins < 0 ? C.warn : C.jadeLt,
                            }}
                        >
                            {me.net_wins > 0 ? `+${me.net_wins}` : me.net_wins}
                        </Typography>
                        <Typography sx={{ ml: 'auto', fontSize: '13.7px', color: C.fg }}>
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

                    <Box sx={{ display: 'flex', justifyContent: 'space-between', mt: '9px', fontSize: '12px', color: C.fg3 }}>
                        <span>{t('ladder:demote_one', '降一档')}</span>
                        <span>{t('ladder:promote_one', '升一档')}</span>
                    </Box>

                    {me.recent.length > 0 && (
                        <Box sx={{ mt: '22px', display: 'flex', alignItems: 'baseline', gap: '12px' }}>
                            <Typography sx={{ fontSize: '13.7px', color: C.fg3 }}>
                                {t('ladder:recent_n', '最近 {n} 局').replace('{n}', String(me.recent.length))}
                            </Typography>
                            {/* Words, not dots: a row of dots reads as a progress meter, and
                                3 wins + 2 losses does NOT promote you. */}
                            <Box sx={{ display: 'flex', gap: '9px', fontSize: '13.7px' }}>
                                {me.recent.map((g, i) => (
                                    <Box component="span" key={i} sx={{ color: g.won ? C.jadeLt : C.fg3 }}>
                                        {g.won ? t('ladder:win', '胜') : t('ladder:loss', '负')}
                                    </Box>
                                ))}
                            </Box>
                        </Box>
                    )}
                </>
            )}

            <Rule />

            <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <Typography sx={{ fontSize: '13.7px', color: C.fg2 }}>
                    {t('ladder:this_game_opponent', '本局对手')}
                </Typography>
                <Typography component="span" sx={{ fontSize: '20px', fontWeight: 600 }}>
                    {opp.rank_name}
                    {uncertified && (
                        <Box
                            component="span"
                            sx={{
                                display: 'inline-block', ml: '10px', px: '8px', py: '3px', borderRadius: '4px',
                                fontSize: '11.5px', fontWeight: 600, letterSpacing: '.5px', verticalAlign: '2px',
                                color: C.warn, border: '1px solid rgba(232,150,57,.45)',
                            }}
                        >
                            {t('ladder:uncertified', '未标定')}
                        </Box>
                    )}
                </Typography>
            </Box>

            {!me.playable && (
                <Box
                    sx={{
                        mt: '22px', p: '14px 16px', borderRadius: '8px',
                        bgcolor: 'rgba(232,150,57,.08)', border: '1px solid rgba(232,150,57,.3)',
                        fontSize: '14px', color: C.warn, lineHeight: 1.55,
                    }}
                >
                    {me.blocked_reason === 'engine_unavailable'
                        ? t('ladder:blocked_engine', '引擎当前不可用，暂时开不了局。')
                        : t('ladder:blocked_uncertified', '{rank} 的棋力配置还在标定中，现在开不了局。').replace(
                              '{rank}',
                              opp.rank_name,
                          )}
                    <br />
                    {me.blocked_reason === 'engine_unavailable'
                        ? t('ladder:blocked_engine_2', '引擎恢复后即可对局。')
                        : t('ladder:blocked_uncertified_2', '标定完成后即可对局。')}
                </Box>
            )}
        </Paper>
    );
};

export default LadderRankCard;
