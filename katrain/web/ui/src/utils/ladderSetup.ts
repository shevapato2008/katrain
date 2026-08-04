import type { LadderGameSetup } from '../api';

/**
 * One line describing the game a 升降级对弈 will be played under.
 *
 * The values come from `GET /api/ladder/me` (`game_setup`), never from the page:
 * the ladder fixes board size, ruleset and komi at the conditions its rungs were
 * measured under, so this is a read-out, not a summary of anything the user
 * picked. Shared because both the galaxy and the kiosk setup pages show it, and
 * a ruleset spelled differently on the two screens would read as two different
 * games earning one rank.
 */
export const formatLadderSetup = (
    setup: LadderGameSetup,
    t: (key: string, fallback: string) => string,
): string => {
    // Own keys, not the bare `chinese`/`japanese` ruleset keys the setup dropdowns
    // use: those are translated as menu options ("中国"), which reads as
    // "19 路 · 中国 · 贴 7.5 目" here — a list of three things rather than a
    // sentence about the game.
    const rules: Record<string, string> = {
        chinese: t('ladder:rules_chinese', '中国规则'),
        japanese: t('ladder:rules_japanese', '日本规则'),
        korean: t('ladder:rules_korean', '韩国规则'),
        aga: t('ladder:rules_aga', 'AGA 规则'),
    };
    // replaceAll, not replace: the English form of this one is "{n}×{n}", and a
    // single replace would render "19×{n}".
    const size = t('ladder:setup_size', '{n} 路').replaceAll('{n}', String(setup.size));
    const komi = t('ladder:setup_komi', '贴 {n} 目').replaceAll('{n}', String(setup.komi));
    return `${size} · ${rules[setup.rules] ?? setup.rules} · ${komi}`;
};
