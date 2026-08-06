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
  const [overlayOpen, setOverlayOpen] = useState(false);
  const toggleButtonRef = useRef<HTMLButtonElement | null>(null);
  const previousMode = useRef(mode);
  const previousPathname = useRef(pathname);

  const returnFocus = useCallback(() => {
    window.requestAnimationFrame?.(() => toggleButtonRef.current?.focus());
  }, []);

  const closeOverlay = useCallback(() => {
    setOverlayOpen(false);
    returnFocus();
  }, [returnFocus]);

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
      setOverlayOpen((open) => {
        if (open) returnFocus();
        return !open;
      });
    }
  }, [mode, returnFocus]);

  useEffect(() => {
    if (previousMode.current !== mode) {
      setOverlayOpen(false);
      previousMode.current = mode;
    }
  }, [mode]);

  useEffect(() => {
    if (previousPathname.current !== pathname) {
      if (overlayOpen) closeOverlay();
      previousPathname.current = pathname;
    }
  }, [closeOverlay, overlayOpen, pathname]);

  const dockedWidth: 240 | 216 | 0 = dockedExpanded
    ? mode === 'wide-docked'
      ? 240
      : mode === 'standard-docked'
        ? 216
        : 0
    : 0;

  return { mode, dockedWidth, dockedExpanded, overlayOpen, toggle, closeOverlay, toggleButtonRef };
};
