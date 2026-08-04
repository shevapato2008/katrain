import { Box, Button, Dialog, Typography } from '@mui/material';
import type { LadderSettlement } from '../../../api';
import { useTranslation } from '../../../hooks/useTranslation';
import { C, NetWinBar, PlacementSteps } from './LadderRankCard';

/**
 * What the 升降级对弈 game you just finished did to your rank.
 *
 * Purely presentational: every number comes from GET /api/ladder/session-result.
 * Nothing here is derived by diffing two reads of /api/ladder/me — a game that
 * did not score has to say so, and a zero diff cannot tell "you broke even" from
 * "it wasn't counted".
 *
 * The rung move is the hero when there is one, because moving a rung is the only
 * thing the whole ledger exists to do. When the rung did not move, the net-win
 * bar carries the moment instead; when the game did not score at all, the dialog
 * says that plainly and shows no counters.
 */

// The paper is the scroll container: MUI's scroll="paper" default already gives
// it max-height calc(100% - 64px) with overflow-y:auto, so a card taller than the
// viewport scrolls rather than pushing the dismiss button out of reach. Measured
// at 1440x200: scrollHeight 295 / clientHeight 136, a real wheel reaches the end.
// Do not set overflow here — overriding it to hidden is what would break it.
const PAPER_SX = { bgcolor: '#252525', borderRadius: 4, p: '34px 34px 26px' } as const;

const Hero = ({ children }: { children: React.ReactNode }) => (
    <Typography sx={{ fontSize: '36px', fontWeight: 700, color: C.fg, lineHeight: '46px', mt: '10px' }}>
        {children}
    </Typography>
);

// Letter-spacing stays at .5px: these labels are 2–6 Chinese characters, and the
// wide tracking that makes a Latin eyebrow read as a label just pulls 定级赛 第 3 局
// apart into loose glyphs.
const Eyebrow = ({ text, tone }: { text: string; tone: string }) => (
    <Typography sx={{ fontSize: '14px', fontWeight: 600, letterSpacing: '.5px', color: tone }}>{text}</Typography>
);

const Note = ({ children }: { children: React.ReactNode }) => (
    <Typography sx={{ fontSize: '13.7px', color: C.fg3, mt: '18px', lineHeight: 1.7 }}>{children}</Typography>
);

const LadderSettlementDialog = ({
    result,
    onClose,
}: {
    result: LadderSettlement;
    onClose: () => void;
}) => {
    const { t } = useTranslation();

    const notSettledText = (reason: string) => {
        switch (reason) {
            case 'inconclusive':
                return t('ladder:unscored_inconclusive', '这局没有分出胜负，不计入升降级，也不占定级赛的局数。');
            case 'already_settled':
                return t('ladder:unscored_already', '这局已经结算过了，段位没有再变。');
            case 'in_progress':
                return t('ladder:unscored_in_progress', '这局还没结束。');
            default:
                // no_seated_rung / no_human_seat / not_recorded / error — all mean the
                // same thing to the player, and all are our fault, so say so.
                return t('ladder:unscored_error', '这局没能记进升降级账本，段位没有变动。请把这一局报给我们。');
        }
    };

    let body: React.ReactNode;

    if (!result.settled) {
        body = (
            <>
                <Eyebrow text={t('ladder:unscored', '本局未计入升降级')} tone={C.warn} />
                <Note>{notSettledText(result.reason)}</Note>
            </>
        );
    } else if (result.moved !== 0 && result.rung_before && result.rung_after) {
        const up = result.moved > 0;
        body = (
            <>
                <Eyebrow
                    text={up ? t('ladder:promoted', '升段') : t('ladder:demoted', '降段')}
                    tone={up ? C.jadeLt : C.warn}
                />
                <Hero>
                    <Box component="span" sx={{ color: C.fg3, fontSize: '26px', fontWeight: 600 }}>
                        {result.rung_before.rank_name}
                    </Box>
                    <Box component="span" sx={{ color: C.fg3, fontSize: '22px', mx: '14px' }}>→</Box>
                    <Box component="span" sx={{ color: up ? C.jadeLt : C.warn }}>{result.rung_after.rank_name}</Box>
                </Hero>
                <Note>
                    {up
                        ? t('ladder:promoted_note', '净胜 +{n}，升一档，计数归零。').replace(
                              '{n}',
                              String(result.threshold),
                          )
                        : t('ladder:demoted_note', '净胜 -{n}，降一档，计数归零。').replace(
                              '{n}',
                              String(result.threshold),
                          )}
                </Note>
            </>
        );
    } else if (result.is_placement) {
        const done = result.placement?.games_done ?? 0;
        const total = result.placement?.games_total ?? 5;
        const finished = result.rung_after !== null;
        body = (
            <>
                <Eyebrow
                    text={
                        finished
                            ? t('ladder:placement_done', '定级完成')
                            : t('ladder:placement_game_done', '定级赛 第 {n} 局').replace('{n}', String(done))
                    }
                    tone={C.jadeLt}
                />
                <Hero>
                    {finished
                        ? result.rung_after!.rank_name
                        : result.won
                          ? t('ladder:this_game_win', '本局胜')
                          : t('ladder:this_game_loss', '本局负')}
                </Hero>
                <Box sx={{ mt: '4px' }}>
                    <PlacementSteps done={done} total={total} />
                </Box>
                <Note>
                    {finished
                        ? t('ladder:placement_done_note', '之后每一局都按净胜 ±{n} 升降一档。').replace(
                              '{n}',
                              String(result.threshold),
                          )
                        : t('ladder:placement_left', '再打 {n} 局定下你的段位。').replace('{n}', String(total - done))}
                </Note>
            </>
        );
    } else {
        const before = result.net_wins_before;
        const after = result.net_wins_after;
        const sign = (n: number) => (n > 0 ? `+${n}` : String(n));
        const toPromote = result.threshold - after;
        const toDemote = result.threshold + after;
        body = (
            <>
                <Eyebrow
                    text={result.won ? t('ladder:this_game_win', '本局胜') : t('ladder:this_game_loss', '本局负')}
                    tone={result.won ? C.jadeLt : C.fg2}
                />
                <Hero>
                    <Box component="span" sx={{ fontSize: '13.7px', color: C.fg2, mr: '14px', verticalAlign: '10px' }}>
                        {t('ladder:net_wins', '净胜')}
                    </Box>
                    <Box component="span" sx={{ color: C.fg3, fontSize: '26px' }}>{sign(before)}</Box>
                    <Box component="span" sx={{ color: C.fg3, fontSize: '22px', mx: '14px' }}>→</Box>
                    <Box component="span" sx={{ color: after < 0 ? C.warn : C.jadeLt }}>{sign(after)}</Box>
                </Hero>
                <Box sx={{ mt: '22px' }}>
                    <NetWinBar netWins={after} threshold={result.threshold} />
                </Box>
                <Note>
                    {after < 0
                        ? t('ladder:to_demote_plain', '再负 {n} 局降一档。').replace('{n}', String(toDemote))
                        : t('ladder:to_promote_plain', '再胜 {n} 局升一档。').replace('{n}', String(toPromote))}
                </Note>
            </>
        );
    }

    return (
        <Dialog
            open
            onClose={onClose}
            maxWidth="xs"
            fullWidth
            PaperProps={{ sx: PAPER_SX }}
        >
            {body}
            <Box sx={{ display: 'flex', justifyContent: 'flex-end', mt: '30px' }}>
                <Button onClick={onClose} variant="contained" sx={{ textTransform: 'none', px: '22px' }}>
                    {t('ladder:got_it', '知道了')}
                </Button>
            </Box>
        </Dialog>
    );
};

export default LadderSettlementDialog;
