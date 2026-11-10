const TEXT_TAGS = 'button,input,select,textarea,span,b,strong,small,em,i,p,h1,h2,h3,h4,h5,h6,label,div,td,th,li,a,time,dt,dd';
const FIXED_TEXT = '.brand-zh,.kiosk-topbar__brand,.kiosk-icon,.MuiSvgIcon-root,'
  + '[class*="ruler"],[class*="coord"],[data-kiosk-type-fixed]';
const PORTALS = '.MuiModal-root,.MuiPopover-root,.MuiMenu-root,.MuiDrawer-root,.MuiDialog-root';

function hasOwnText(element: HTMLElement): boolean {
  if (element.matches('input,select,textarea')) return true;
  const text = Array.from(element.childNodes)
    .filter(node => node.nodeType === Node.TEXT_NODE)
    .map(node => node.textContent ?? '').join('').trim();
  // Standalone arrows, stones, and icon glyphs retain their designed size.
  return /[\p{L}\p{N}]/u.test(text);
}

/** Measure unscaled text once. Subsequent size changes only update a CSS variable. */
export function installKioskTextSizing(): () => void {
  let frame = 0;
  const pending = new Set<HTMLElement>();
  const scan = () => {
    frame = 0;
    const byScope = new Map<HTMLElement, Set<HTMLElement>>();
    for (const candidate of pending) {
      if (!candidate.isConnected) continue;
      const kiosk = candidate.closest<HTMLElement>('.kiosk-viewport');
      const portal = candidate.matches(PORTALS) ? candidate : candidate.closest<HTMLElement>(PORTALS);
      const root = kiosk ?? portal;
      if (!root) continue;
      if (portal && !kiosk) portal.setAttribute('data-kiosk-type-portal', '');
      const elements = byScope.get(root) ?? new Set<HTMLElement>();
      for (const node of [candidate, ...candidate.querySelectorAll(TEXT_TAGS)]) {
        if (node instanceof HTMLElement && !node.hasAttribute('data-kiosk-base-size')
          && hasOwnText(node) && !node.closest(FIXED_TEXT)) elements.add(node);
      }
      byScope.set(root, elements);
    }
    pending.clear();
    for (const [root, candidates] of byScope) {
      const elements = [...candidates];
      if (!elements.length) continue;
      root.setAttribute('data-kiosk-type-measuring', '');
      const sizes = elements.map(node => getComputedStyle(node).fontSize);
      elements.forEach((node, index) => node.style.setProperty('--kiosk-base-size', sizes[index]));
      elements.forEach(node => node.setAttribute('data-kiosk-base-size', ''));
      root.removeAttribute('data-kiosk-type-measuring');
    }
  };
  const schedule = () => { if (!frame) frame = requestAnimationFrame(scan); };
  const observer = new MutationObserver(records => {
    for (const record of records) {
      if (record.type === 'characterData') {
        const parent = record.target.parentElement;
        if (parent) pending.add(parent);
        continue;
      }
      if (!record.addedNodes.length) continue;
      if ([...record.addedNodes].some(node => node.nodeType === Node.TEXT_NODE)
        && record.target instanceof HTMLElement) pending.add(record.target);
      record.addedNodes.forEach(node => {
        if (node instanceof HTMLElement) pending.add(node);
      });
    }
    if (pending.size) schedule();
  });
  observer.observe(document.body, { childList: true, characterData: true, subtree: true });
  const kiosk = document.querySelector<HTMLElement>('.kiosk-viewport');
  if (kiosk) pending.add(kiosk);
  document.querySelectorAll<HTMLElement>(PORTALS).forEach(portal => pending.add(portal));
  schedule();
  return () => {
    observer.disconnect();
    if (frame) cancelAnimationFrame(frame);
    document.querySelectorAll('[data-kiosk-type-portal]').forEach(node => node.removeAttribute('data-kiosk-type-portal'));
  };
}
