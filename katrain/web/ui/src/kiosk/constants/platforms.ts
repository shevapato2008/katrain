// Cross-platform Go-server metadata shared by PlatformConnectPage (login flow) and
// PlayPage (对弈 hub 跨平台对弈 section). Kept here instead of duplicated so both
// pages agree on labels/colors when a new platform is added.
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
