import { useMemo, type ReactNode } from 'react';
import { createTheme, ThemeProvider, useTheme } from '@mui/material/styles';
import ContentPageHeader from './ContentPageHeader';
import '../../../kiosk-shell/fonts.css';
import './PlayPageLayout.css';

export const PLAY_PAGE_FONT = '"SmartBox Kai", "LXGW WenKai", "Kaiti SC", serif';

/** Shared chrome for the three play setup pages; game navigation remains in ModulePlate. */
export default function PlayPageLayout({ title, status, children }: {
  title: ReactNode;
  status?: ReactNode;
  children: ReactNode;
}) {
  const outerTheme = useTheme();
  // Menus/dialogs render in portals, so inheritance alone cannot keep their fonts consistent.
  const theme = useMemo(() => createTheme(outerTheme, {
    typography: Object.fromEntries([
      ['fontFamily', PLAY_PAGE_FONT],
      ...['h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'subtitle1', 'subtitle2', 'body1', 'body2', 'button', 'caption', 'overline']
        .map(variant => [variant, { fontFamily: PLAY_PAGE_FONT }]),
    ]),
  }), [outerTheme]);

  return <ThemeProvider theme={theme}>
    <div className="galaxy-play-page">
      <div className="galaxy-play-page__inner">
        <div className="galaxy-play-page__header">
          <ContentPageHeader title={title} parentLabel="对局" parentTo="/galaxy/play" status={status} />
        </div>
        {children}
      </div>
    </div>
  </ThemeProvider>;
}
