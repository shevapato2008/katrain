import { Box, Typography } from '@mui/material';
import type { LadderSettlement } from '../../../api';
import { useTranslation } from '../../../hooks/useTranslation';
import { NetWinBar, PlacementSteps } from './LadderRankBand';

/**
 * What the 升降级对弈 game that just ended did to your rank — a strip inside the
 * kiosk endgame card, not a dialog.
 *
 * A modal here would land on top of the result card the player is already reading,
 * on a 7" screen, with a physical board in front of them; the rank change belongs
 * next to the result, not stacked over it.
 *
 * Every number comes from GET /api/ladder/session-result. Nothing is derived by
 * diffing two reads of /api/ladder/me: a game that did not score has to say so,
 * and a zero diff cannot tell "you broke even" from "it wasn't counted".
 */

const Eyebrow = ({ text, tone }: { text: string; tone: string }) => (
    <Typography sx={{ fontSize: 12.5, fontWeight: 600, letterSpacing: '.5px', color: tone }}>{text}</Typography>
);

const Note = ({ children }: { children: React.ReactNode }) => (
    <Typography sx={{ fontSize: 11.5, color: 'text.disabled', mt: '6px', lineHeight: 1.55 }}>{children}</Typography>
);

const Hero = ({ children }: { children: React.ReactNode }) => (
    <Typography sx={{ fontSize: 22, fontWeight: 700, lineHeight: '28px', mt: '4px' }}>{children}</Typography>
);

const LadderSettlementNote = ({ result }: { result: LadderSettlement }) => {
    const { t } = useTranslation();

    const notSettledText = (reason: string) => {
        switch (reason) {
            case 'inconclusive':
                return t('ladder:unscored_inconclusive', '这局没有分出胜负，不计入升降级，也不占定级赛的局数。');
            case 'already_settled':
                return t('ladder:unscored_already', '这局已经结算过了，段位没有再变。');
            case 'in_progress':
                return t('ladder:unscored_in_progress', '这局还没结束。');
            case 'engine_unavailable':
                return t(
                    'ladder:unscored_engine',
                    '这局的对手没能以标定强度落子，所以不算数——段位没有变动，也不占定级赛的局数。',
                );
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
                <Eyebrow text={t('ladder:unscored', '本局未计入升降级')} tone="warning.main" />
                <Note>{notSettledText(result.reason)}</Note>
            </>
        );
    } else if (result.moved !== 0 && result.rung_before && result.rung_after) {
        const up = result.moved > 0;
        body = (
            <>
                <Eyebrow
                    text={up ? t('ladder:promoted', '升段') : t('ladder:demoted', '降段')}
                    tone={up ? 'primary.main' : 'warning.main'}
                />
                <Hero>
                    <Box component="span" sx={{ color: 'text.disabled', fontSize: 17, fontWeight: 600 }}>
                        {result.rung_before.rank_name}
                    </Box>
                    <Box component="span" sx={{ color: 'text.disabled', fontSize: 15, mx: '10px' }}>→</Box>
                    <Box component="span" sx={{ color: up ? 'primary.main' : 'warning.main' }}>
                        {result.rung_after.rank_name}
                    </Box>
                </Hero>
                <Note>
                    {(up
                        ? t('ladder:promoted_note', '净胜 +{n}，升一档，计数归零。')
                        : t('ladder:demoted_note', '净胜 -{n}，降一档，计数归零。')
                    ).replace('{n}', String(result.threshold))}
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
                    tone="primary.main"
                />
                <Hero>
                    {finished
                        ? result.rung_after!.rank_name
                        : result.won
                          ? t('ladder:this_game_win', '本局胜')
                          : t('ladder:this_game_loss', '本局负')}
                </Hero>
                <Box sx={{ mt: '8px' }}>
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
        const after = result.net_wins_after;
        const sign = (n: number) => (n > 0 ? `+${n}` : String(n));
        body = (
            <>
                <Eyebrow
                    text={result.won ? t('ladder:this_game_win', '本局胜') : t('ladder:this_game_loss', '本局负')}
                    tone={result.won ? 'primary.main' : 'text.secondary'}
                />
                <Hero>
                    <Box component="span" sx={{ fontSize: 12.5, color: 'text.secondary', mr: '10px', verticalAlign: '6px' }}>
                        {t('ladder:net_wins', '净胜')}
                    </Box>
                    <Box component="span" sx={{ color: 'text.disabled', fontSize: 17 }}>
                        {sign(result.net_wins_before)}
                    </Box>
                    <Box component="span" sx={{ color: 'text.disabled', fontSize: 15, mx: '10px' }}>→</Box>
                    <Box component="span" sx={{ color: after < 0 ? 'warning.main' : 'primary.main' }}>{sign(after)}</Box>
                </Hero>
                <Box sx={{ mt: '10px' }}>
                    <NetWinBar netWins={after} threshold={result.threshold} />
                </Box>
                <Note>
                    {after < 0
                        ? t('ladder:to_demote_plain', '再负 {n} 局降一档。').replace('{n}', String(result.threshold + after))
                        : t('ladder:to_promote_plain', '再胜 {n} 局升一档。').replace('{n}', String(result.threshold - after))}
                </Note>
            </>
        );
    }

    return (
        <Box
            data-testid="ladder-settlement-note"
            sx={{
                alignSelf: 'stretch', mt: '2px', pt: '12px', borderTop: '1px solid', borderColor: 'divider',
            }}
        >
            {body}
        </Box>
    );
};

export default LadderSettlementNote;
