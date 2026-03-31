import { type ReactNode } from 'react';
import {
  SportsEsports as PlayIcon,
  Extension as TsumegoIcon,
  Science as ResearchIcon,
  MenuBook as KifuIcon,
  LiveTv as LiveIcon,
  Settings as SettingsIcon,
} from '@mui/icons-material';

export interface NavTab {
  label: string;
  icon: ReactNode;
  path: string;
  pattern: string;
}

export const primaryTabs: NavTab[] = [
  { label: '对弈', icon: <PlayIcon />, path: '/kiosk/play', pattern: '/kiosk/play/*' },
  { label: '死活', icon: <TsumegoIcon />, path: '/kiosk/tsumego', pattern: '/kiosk/tsumego/*' },
  { label: '研究', icon: <ResearchIcon />, path: '/kiosk/research', pattern: '/kiosk/research' },
  { label: '棋谱', icon: <KifuIcon />, path: '/kiosk/kifu', pattern: '/kiosk/kifu/*' },
  { label: '直播', icon: <LiveIcon />, path: '/kiosk/live', pattern: '/kiosk/live/*' },
];

export const settingsTab: NavTab = {
  label: '设置', icon: <SettingsIcon />, path: '/kiosk/settings', pattern: '/kiosk/settings',
};
