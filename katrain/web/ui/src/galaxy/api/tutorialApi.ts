// Moved to shared territory: src/api/tutorialApi.ts (so both galaxy and kiosk
// can consume it without violating the kiosk "no import from galaxy/" boundary).
// This re-export keeps existing galaxy imports (`../../api/tutorialApi`) working.
// TODO(TD-3): once kiosk tutorial lands and galaxy is verified, migrate galaxy
// import sites to `src/api/tutorialApi` and delete this shim.
export * from '../../api/tutorialApi';
