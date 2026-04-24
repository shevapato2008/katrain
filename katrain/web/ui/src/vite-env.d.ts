/// <reference types="vite/client" />

/**
 * Compile-time constant wired by vite.config.ts `define`.
 * true in kiosk-2d builds, false in the regular full build.
 * Source-level guards reading this value are tree-shaken by Rollup.
 */
declare const __KIOSK_2D_ONLY__: boolean;
