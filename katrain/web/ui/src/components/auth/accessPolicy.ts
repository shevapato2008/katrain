import type { AuthStatus } from '../../context/AuthContext';

export type AccessFeature = 'hall' | 'rated' | 'reports' | 'cross' | 'analysis' | 'growth' | 'local' | 'kifu' | 'tutorial' | 'tsumego' | 'research' | 'settings' | 'vision' | 'cloud' | 'play';
export interface AccessMetadata { label: string; description: string; backLabel: string; backPath: string }
export const accessMetadata: Record<AccessFeature, AccessMetadata> = {
  cloud: { label: '个人棋谱', description: '登录后查看自己的云端棋谱与分组。', backLabel: '继续浏览', backPath: '/research' },
  play: { label: '自由对弈', description: '登录后可继续当前对弈设置。', backLabel: '继续浏览', backPath: '/play' },
  hall: { label: '对战大厅', description: '查看正在进行的对局，邀请棋友或匹配对手。', backLabel: '返回对弈', backPath: '/play' },
  rated: { label: '升降级对弈', description: '定级与升降级成绩需要记录到你的账号。', backLabel: '返回对弈', backPath: '/play' },
  reports: { label: '个人复盘', description: '查看你的棋谱与复盘报告，继续分析对局。', backLabel: '返回首页', backPath: '' },
  cross: { label: '跨平台对弈', description: '先登录智星盒，再连接你的星阵或 OGS 账号。', backLabel: '返回对弈', backPath: '/play' },
  analysis: { label: '研究分析', description: '登录后可使用引擎分析，当前棋盘与设置将保留。', backLabel: '继续浏览', backPath: '/research' },
  growth: { label: '成长记录', description: '登录后查看自己的成绩、活动与成长记录。', backLabel: '返回对弈', backPath: '/play' },
  local: { label: '本地双人对弈', description: '登录后开始双人对弈，并保存自己的棋谱。', backLabel: '返回对弈', backPath: '/play' },
  kifu: { label: '棋谱库', description: '登录后浏览棋谱，回放对局或摆到实体棋盘。', backLabel: '返回对弈', backPath: '/play' },
  tutorial: { label: '教程', description: '登录后浏览教程与章节内容。', backLabel: '返回对弈', backPath: '/play' },
  tsumego: { label: '死活题', description: '登录后进入训练营，继续做题。', backLabel: '返回对弈', backPath: '/play' },
  research: { label: '研究棋盘', description: '登录后进入研究棋盘，继续摆谱。', backLabel: '返回对弈', backPath: '/play' },
  settings: { label: '设置', description: '登录后查看并调整围棋设置。', backLabel: '返回对弈', backPath: '/play' },
  vision: { label: '标定工作台', description: '登录后进入设备视觉与棋盘标定工作台。', backLabel: '返回对弈', backPath: '/play' },
};

// Existing kiosk policy remains strict except for the explicitly public free-play chain.
export function kioskAccessPolicy(path: string): { feature: AccessFeature; realAccount: boolean } | null {
  if (path === '/kiosk/play' || path === '/kiosk' || path === '/kiosk/' || path === '/kiosk/login'
    || path === '/kiosk/play/cross-platform' || path.startsWith('/kiosk/play/ai/game/')) return null;
  if (path.startsWith('/kiosk/play/ai/setup/')) return path.endsWith('/ranked') ? { feature: 'rated', realAccount: true } : null;
  if (path.startsWith('/kiosk/play/pvp/lobby') || path.startsWith('/kiosk/play/pvp/room') || path.startsWith('/kiosk/play/pvp/watch')) return { feature: 'hall', realAccount: true };
  if (path.startsWith('/kiosk/play/pvp/')) return { feature: 'local', realAccount: false };
  if (path.startsWith('/kiosk/play/cross-platform/')) return { feature: 'cross', realAccount: false };
  if (path.startsWith('/kiosk/report')) return { feature: 'reports', realAccount: false };
  if (path.startsWith('/kiosk/growth')) return { feature: 'growth', realAccount: false };
  if (path.startsWith('/kiosk/kifu') || path.startsWith('/kiosk/baipu')) return { feature: 'kifu', realAccount: false };
  if (path.startsWith('/kiosk/tutorial')) return { feature: 'tutorial', realAccount: false };
  if (path.startsWith('/kiosk/tsumego')) return { feature: 'tsumego', realAccount: false };
  if (path.startsWith('/kiosk/research')) return { feature: 'research', realAccount: false };
  if (path.startsWith('/kiosk/vision')) return { feature: 'vision', realAccount: false };
  if (path.startsWith('/kiosk/settings')) return { feature: 'settings', realAccount: false };
  return null;
}

export function accessAllowed(status: AuthStatus, authenticated: boolean, guest: boolean, realAccount: boolean): boolean {
  return authenticated && (status === 'authenticated' || (status === 'guest' && !realAccount)) && (!realAccount || !guest);
}
