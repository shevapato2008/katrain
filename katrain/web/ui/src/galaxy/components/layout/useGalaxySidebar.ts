import { useCallback, useEffect, useRef, useState } from 'react';
import { useMediaQuery } from '@mui/material';
import { useLocation } from 'react-router-dom';

export const GALAXY_SIDEBAR_STORAGE_KEY = 'galaxy.sidebar.docked.expanded.v1';

export type GalaxyNavMode = 'wide-docked' | 'standard-docked' | 'narrow-overlay' | 'mobile';

export interface GalaxySidebarState {
  mode: GalaxyNavMode;
  dockedWidth: 240 | 216 | 0;
  dockedExpanded: boolean;
  overlayOpen: boolean;
  toggle: () => void;
  closeOverlay: () => void;
  toggleButtonRef: React.RefObject<HTMLButtonElement | null>;
}

interface OverlayState {
  mode: GalaxyNavMode;
  pathname: string;
  open: boolean;
}

const readDockedPreference = () => {
  try {
    const value = window.localStorage?.getItem(GALAXY_SIDEBAR_STORAGE_KEY);
    return value === null || value === undefined ? true : value === 'true';
  } catch {
    return true;
  }
};

const writeDockedPreference = (expanded: boolean) => {
  try {
    window.localStorage?.setItem(GALAXY_SIDEBAR_STORAGE_KEY, String(expanded));
  } catch {
    // Storage can be unavailable in private or embedded browser contexts.
  }
};

export const useGalaxySidebar = (): GalaxySidebarState => {
  const isWide = useMediaQuery('(min-width:1536px)');
  const isDocked = useMediaQuery('(min-width:1200px)');
  const isLandscapeNav = useMediaQuery('(min-width:900px)');
  const mode: GalaxyNavMode = isWide
    ? 'wide-docked'
    : isDocked
      ? 'standard-docked'
      : isLandscapeNav
        ? 'narrow-overlay'
        : 'mobile';
  const pathname = useLocation().pathname;
  const [dockedExpanded, setDockedExpanded] = useState(readDockedPreference);
  const [overlayState, setOverlayState] = useState<OverlayState>({ mode, pathname, open: false });
  const toggleButtonRef = useRef<HTMLButtonElement | null>(null);
  const previousOverlay = useRef({ pathname, open: false });

  const overlayIdentityChanged = overlayState.mode !== mode || overlayState.pathname !== pathname;
  if (overlayIdentityChanged) setOverlayState({ mode, pathname, open: false });
  const overlayOpen = !overlayIdentityChanged && overlayState.open;

  const returnFocus = useCallback(() => {
    window.requestAnimationFrame?.(() => toggleButtonRef.current?.focus());
  }, []);

  const closeOverlay = useCallback(() => {
    setOverlayState({ mode, pathname, open: false });
    returnFocus();
  }, [mode, pathname, returnFocus]);

  const toggle = useCallback(() => {
    if (mode === 'wide-docked' || mode === 'standard-docked') {
      setDockedExpanded((expanded) => {
        const next = !expanded;
        writeDockedPreference(next);
        return next;
      });
      return;
    }
    if (mode === 'narrow-overlay') {
      setOverlayState((current) => {
        const open = current.mode === mode && current.pathname === pathname && current.open;
        if (open) returnFocus();
        return { mode, pathname, open: !open };
      });
    }
  }, [mode, pathname, returnFocus]);

  useEffect(() => {
    if (previousOverlay.current.pathname !== pathname && previousOverlay.current.open) returnFocus();
    previousOverlay.current = { pathname, open: overlayOpen };
  }, [overlayOpen, pathname, returnFocus]);

  const dockedWidth: 240 | 216 | 0 = dockedExpanded
    ? mode === 'wide-docked'
      ? 240
      : mode === 'standard-docked'
        ? 216
        : 0
    : 0;

  return { mode, dockedWidth, dockedExpanded, overlayOpen, toggle, closeOverlay, toggleButtonRef };
};
