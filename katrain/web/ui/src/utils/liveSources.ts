import type { MatchSource, UpcomingSource } from '../types/live';

/**
 * 直播 / 预告那几家平台的**名字和颜色**,一处。
 *
 * ## 为什么要合
 *
 * 2026-08-26 之前这张表在四个地方各写了一遍(`MatchInfo` / `MatchCard` /
 * `UpcomingList` / `KifuPage` / `LiveMatchPage`),而它们**已经走散了**:
 * `pandanet` 在屏 15 棋谱上写「PandaNet」,在屏 18 直播和另外两处写「IGS」——
 * **同一个平台在两屏上是两个名字**,用户没有任何办法知道那是同一家。
 *
 * 定「IGS」:四处里三处这么写,而且中文围棋圈里通行的就是这两个字母。
 * (这一处两边都有能力说对,所以按多数取;**能力不齐时该做的是补齐弱的那家,不是各说各的**。)
 *
 * ## 两组 id 是**并集不是超集**
 *
 * `MatchSource`(直播)和 `UpcomingSource`(预告)是后端两条不同的枚举,只有 `yike` 重合,
 * 而 `fox` 那家在这两处叫 `foxwq`、在跨平台对弈那边叫 `fox`(`kiosk/constants/platforms.ts`)。
 * 这里**只管这两条枚举**,不去统一那第三套 id —— 那是后端的命名,改它要动接口。
 *
 * ## 认不出来的 id 原样吐出去
 *
 * 后端加了一家而前端还不认得时,屏上写那个 id(`sgf_archive` 这种)**比写「未知来源」好**:
 * 前者用户能拿去搜、能报给我们,后者把信息丢干净了。
 */
export const LIVE_SOURCE_META: Record<MatchSource | UpcomingSource, { label: string; color: string }> = {
  xingzhen: { label: '星阵', color: '#7b1fa2' },
  yike: { label: '弈客', color: '#1976d2' },
  pandanet: { label: 'IGS', color: '#e65100' },
  foxwq: { label: '野狐', color: '#2e7d32' },
  yugen: { label: '幽玄', color: '#c62828' },
  nihonkiin: { label: '棋院', color: '#e65100' },
};

/** 名字;认不出来就把 id 原样还回去。 */
export function liveSourceLabel(source: string): string {
  return LIVE_SOURCE_META[source as MatchSource]?.label ?? source;
}

/** 名字 + 颜色;认不出来返回 `null`,由调用方决定不画那个标还是画个素的。 */
export function liveSourceMeta(source: string): { label: string; color: string } | null {
  return LIVE_SOURCE_META[source as MatchSource] ?? null;
}
