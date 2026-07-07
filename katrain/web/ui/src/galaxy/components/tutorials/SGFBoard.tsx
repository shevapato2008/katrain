// Moved to shared territory: src/components/tutorials/SGFBoard.tsx (pure SVG, no
// three.js, so it is kiosk-safe). This re-export keeps existing galaxy imports
// (`../../components/tutorials/SGFBoard`) working.
// TODO(TD-3): migrate galaxy import sites to the shared path and delete this shim.
export * from '../../../components/tutorials/SGFBoard';
export { default } from '../../../components/tutorials/SGFBoard';
