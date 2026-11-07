import type { ReactElement } from 'react';
import HomeIcon from '@mui/icons-material/Home';
import SportsEsportsIcon from '@mui/icons-material/SportsEsports';
import ScienceIcon from '@mui/icons-material/Science';
import AssessmentIcon from '@mui/icons-material/Assessment';
import LiveTvIcon from '@mui/icons-material/LiveTv';
import ExtensionIcon from '@mui/icons-material/Extension';
import LibraryBooksIcon from '@mui/icons-material/LibraryBooks';
import MenuBookIcon from '@mui/icons-material/MenuBook';
import CardMembershipIcon from '@mui/icons-material/CardMembership';

type Translate = (key: string, fallback: string) => string;

export interface GalaxyNavigationItem {
  key: string;
  label: string;
  path: string;
  icon: ReactElement;
}

export const getGalaxyNavigation = (t: Translate): GalaxyNavigationItem[] => [
  { key: 'home', label: t('Home', 'Home'), path: '/', icon: <HomeIcon /> },
  { key: 'play', label: t('btn:Play', 'Play'), path: '/play', icon: <SportsEsportsIcon /> },
  { key: 'research', label: t('Research', 'Research'), path: '/research', icon: <ScienceIcon /> },
  { key: 'tsumego', label: t('Tsumego', 'Tsumego'), path: '/tsumego', icon: <ExtensionIcon /> },
  { key: 'review', label: t('analysis:report', 'Review'), path: '/report', icon: <AssessmentIcon /> },
  { key: 'live', label: t('Live', 'Live'), path: '/live', icon: <LiveTvIcon /> },
  { key: 'kifu', label: t('kifu:library', 'Kifu'), path: '/kifu', icon: <LibraryBooksIcon /> },
  { key: 'membership', label: t('membership:galaxy_title', '会员与用量'), path: '/membership', icon: <CardMembershipIcon /> },
  { key: 'tutorials', label: t('Tutorials', 'Tutorials'), path: '/tutorials', icon: <MenuBookIcon /> },
];

export const isGalaxyNavigationActive = (pathname: string, path: string) =>
  path === '/' ? pathname === '/' : pathname.startsWith(path);
