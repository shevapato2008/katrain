// Cross-platform Go-server metadata shared by PlatformConnectPage (login flow) and
// PlayPage (对弈 hub 跨平台对弈 section). Kept here instead of duplicated so both
// pages agree on labels/colors when a new platform is added.
import type { PlatformInfo } from '../../api';
export type LoginFieldConfig = {
  userLabel: string; userLabelCn: string;
  passLabel: string; passLabelCn: string;
  userType?: string;  // input type, default "text"
};

export type PlatformMeta = {
  label: string;
  labelCn: string;
  color: string;
  login?: LoginFieldConfig;
  comingSoon?: boolean;
};

export const PLATFORM_META: Record<string, PlatformMeta> = {
  ogs: {
    label: 'OGS', labelCn: 'OGS', color: '#4a90d9',
    login: { userLabel: 'Username', userLabelCn: '用户名', passLabel: 'Password', passLabelCn: '密码' },
  },
  fox: {
    label: 'Fox Weiqi', labelCn: '野狐围棋', color: '#e67e22',
    login: { userLabel: 'Username', userLabelCn: '用户名', passLabel: 'Password', passLabelCn: '密码' },
    comingSoon: true,
  },
  golaxy: {
    label: 'Golaxy', labelCn: '星阵围棋', color: '#2ecc71',
    login: { userLabel: 'Phone Number', userLabelCn: '手机号', passLabel: 'Verification Code', passLabelCn: '验证码', userType: 'tel' },
  },
};

// 顺序照稿子:**能用的排前面,「即将上线」排最后**。后端注册序是 ogs → fox → golaxy
// (`katrain/web/server.py` 三家一起 `register_adapter`),直接 `platforms.map` 会让连不上的
// 野狐夹在两个能用的中间 —— 一排卡里最先撞见的是那张按不动的。
// **屏 01 和屏 07 共读这一份** —— 两屏各写一遍,总有一天只改了其中一处。
export const PLATFORM_CATALOGUE = ['ogs', 'golaxy', 'fox'] as const;

/** 一条「问不到这家能力」的记录:能力标全暗、行尾只给登录。**不是乐观默认**。 */
export const defaultPlatform = (platform: string): PlatformInfo => ({
  platform,
  connected: false,
  supports_live_play: false,
  supports_automatch: false,
  supports_rooms: false,
  supports_seek_graph: false,
  supports_engine_play: false,
});

/**
 * 把 `/platforms` 回来的名单摆成目录顺序,**顺带补齐它少下发的那几家**。
 *
 * 少下发时补一条**全 false** 的记录:那说的是「这台盒子问不到这家的能力」,
 * 于是能力标全暗、行尾只给登录 —— 不是伪造一个「什么都支持」的乐观默认。
 */
/** 目录顺序的一份全 false 名单 —— 还没问到 `/platforms` 时先摆这个。 */
export const defaultPlatforms = (): PlatformInfo[] => PLATFORM_CATALOGUE.map(defaultPlatform);

export const mergePlatformStatus = (records: PlatformInfo[]): PlatformInfo[] => {
  const byPlatform = new Map(records.map((r) => [r.platform, r]));
  return PLATFORM_CATALOGUE.map((p) => byPlatform.get(p) ?? defaultPlatform(p));
};
