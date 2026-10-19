/** The approved device-board glyph, distinct from calibration's camera icon. */
export function PhysicalBoardIcon() {
  return <span className="kiosk-icon" aria-hidden="true" style={{ display: 'inline-flex', width: 24, height: 24, flex: '0 0 24px' }}><svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round">
    <path d="M3 8h18v10H3zM7 18l-2 3m12-3 2 3M7 11h10M7 15h10M10 8v10m4-10v10" />
    <circle cx="19" cy="4" r="2" />
  </svg></span>;
}
